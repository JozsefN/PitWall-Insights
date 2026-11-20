from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from modules.billing.application.entitlements import effective_plan
from modules.billing.domain.plans import PLANS
from modules.billing.infrastructure.db_models import BillingAccountRecord, BillingWebhookEventRecord
from modules.billing.infrastructure.stripe_gateway import BillingUnavailable, StripeGateway, billing_enabled
from modules.identity_auth.domain.models import User


SUBSCRIPTION_EVENTS = {
    "customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted",
    "customer.subscription.paused", "customer.subscription.resumed",
    "invoice.paid", "invoice.payment_failed", "invoice.payment_action_required", "invoice.voided",
    "checkout.session.completed", "checkout.session.expired",
}
TERMINAL = {"canceled", "incomplete_expired"}


class BillingConflict(Exception):
    pass


def membership(account: BillingAccountRecord | None) -> dict:
    return {
        "plan": effective_plan(account),
        "subscription_plan": account.plan_code if account else None,
        "interval": account.interval if account else None,
        "status": account.status if account else None,
        "paid_until": account.paid_until if account else None,
        "cancel_at_period_end": bool(account and account.cancel_at_period_end),
        "can_cancel": bool(account and account.subscription_id and not account.cancel_at_period_end),
        "has_customer": bool(account and account.stripe_customer_id),
        "checkout_enabled": billing_enabled(),
        "ai_available": False,
    }


class BillingService:
    def __init__(self, db: Session, gateway: StripeGateway) -> None:
        self.db = db
        self.gateway = gateway

    def _lock(self, user_id: str) -> BillingAccountRecord | None:
        return self.db.get(BillingAccountRecord, user_id, with_for_update=True)

    def _refresh(self, account: BillingAccountRecord) -> None:
        active = []
        for subscription in self.gateway.subscriptions(account.stripe_customer_id):
            if subscription.status not in TERMINAL:
                active.append(subscription.id)
                if len(active) > 1:
                    break

        account.synced_at = datetime.now(timezone.utc)
        account.subscription_id = None
        account.plan_code = None
        account.interval = None
        account.paid_until = None
        account.cancel_at_period_end = False
        account.status = None if not active else "billing_review"
        if len(active) != 1:
            return

        subscription = self.gateway.subscription(active[0])
        if subscription.livemode or subscription.customer != account.stripe_customer_id:
            raise BillingUnavailable("Stripe returned an unrelated subscription.")
        if subscription.status in TERMINAL:
            account.status = None
            return
        account.subscription_id = subscription.id
        items = subscription["items"]
        if items.has_more or len(items.data) != 1 or items.data[0].quantity != 1:
            return
        item = items.data[0]
        selected = next((key for key, price_id in self.gateway.prices.items() if price_id == item.price.id), None)
        if selected is None or not self.gateway.check_price(item.price, *selected):
            return
        account.plan_code, account.interval = selected
        account.status = subscription.status
        account.cancel_at_period_end = bool(subscription.cancel_at_period_end or subscription.cancel_at)
        invoice = subscription.latest_invoice
        if subscription.status == "active" and invoice and invoice.status == "paid":
            period_end = item.current_period_end
            if subscription.cancel_at:
                period_end = min(subscription.cancel_at, period_end)
            account.paid_until = datetime.fromtimestamp(period_end, timezone.utc)
        elif subscription.status == "active":
            account.status = "awaiting_payment"

    def checkout(self, user: User, plan: str, interval: str) -> str:
        self.db.execute(insert(BillingAccountRecord).values(user_id=user.id).on_conflict_do_nothing())
        account = self._lock(user.id)
        if not account.stripe_customer_id:
            account.stripe_customer_id = self.gateway.create_customer(user.id, user.email)
            self.db.commit()
            account = self._lock(user.id)

        self._refresh(account)
        if account.status:
            self.db.commit()
            raise BillingConflict("Manage your existing subscription before starting another one.")

        now = datetime.now(timezone.utc)
        if account.checkout_id:
            existing = self.gateway.get_checkout(account.checkout_id)
            if existing.status == "complete" and now < account.checkout_expires_at:
                self.db.commit()
                raise BillingConflict("Your previous checkout is being confirmed. Refresh billing status shortly.")
            if existing.status == "open":
                if (plan, interval) == (account.checkout_plan, account.checkout_interval):
                    self.db.commit()
                    return existing.url
                self.gateway.expire_checkout(existing.id)
            account.checkout_key = None
            account.checkout_id = None

        if account.checkout_key and now < account.checkout_expires_at:
            if (plan, interval) != (account.checkout_plan, account.checkout_interval):
                raise BillingConflict("Retry the previous plan first. A checkout is still being prepared.")
        else:
            account.checkout_key = str(uuid4())
            account.checkout_plan = plan
            account.checkout_interval = interval
            account.checkout_expires_at = now.replace(microsecond=0) + timedelta(hours=2)
            self.db.commit()
            account = self._lock(user.id)
            if account.checkout_id:
                existing = self.gateway.get_checkout(account.checkout_id)
                self.db.commit()
                if existing.status == "open" and (plan, interval) == (account.checkout_plan, account.checkout_interval):
                    return existing.url
                raise BillingConflict("Checkout changed in another tab. Refresh billing status.")

        checkout = self.gateway.create_checkout(
            account.stripe_customer_id, plan, interval, account.checkout_key, account.checkout_expires_at,
        )
        if checkout.livemode or checkout.customer != account.stripe_customer_id or not checkout.url:
            raise BillingUnavailable("Stripe returned an unrelated checkout.")
        account.checkout_id = checkout.id
        self.db.commit()
        return checkout.url

    def sync(self, user_id: str) -> dict:
        account = self._lock(user_id)
        if account and account.stripe_customer_id:
            now = datetime.now(timezone.utc)
            if not account.synced_at or now - account.synced_at >= timedelta(seconds=5):
                self._refresh(account)
        result = membership(account)
        self.db.commit()
        return result

    def cancel(self, user_id: str) -> dict:
        account = self._lock(user_id)
        if not account or not account.stripe_customer_id:
            raise BillingConflict("There is no subscription to cancel.")
        self._refresh(account)
        if not account.subscription_id:
            self.db.commit()
            raise BillingConflict("There is no subscription available to cancel here.")
        if not account.cancel_at_period_end:
            self.gateway.cancel_renewal(account.subscription_id)
            self._refresh(account)
        result = membership(account)
        self.db.commit()
        return result

    def portal(self, user_id: str) -> str:
        account = self.db.get(BillingAccountRecord, user_id)
        if not account or not account.stripe_customer_id:
            raise BillingConflict("Billing details become available after starting checkout.")
        return self.gateway.portal(account.stripe_customer_id)

    def apply_event(self, event) -> None:
        if event.type not in SUBSCRIPTION_EVENTS:
            return
        customer = getattr(event.data.object, "customer", None)
        if not isinstance(customer, str):
            return
        account = self.db.scalar(select(BillingAccountRecord).where(
            BillingAccountRecord.stripe_customer_id == customer,
        ).with_for_update())
        if account is None or self.db.get(BillingWebhookEventRecord, event.id):
            return
        self._refresh(account)
        if event.type == "checkout.session.expired" and event.data.object.id == account.checkout_id:
            account.checkout_id = None
            account.checkout_key = None
        now = datetime.now(timezone.utc)
        self.db.add(BillingWebhookEventRecord(event_id=event.id, user_id=account.user_id, processed_at=now))
        self.db.execute(delete(BillingWebhookEventRecord).where(
            BillingWebhookEventRecord.processed_at < now - timedelta(days=30),
        ))
        self.db.commit()
