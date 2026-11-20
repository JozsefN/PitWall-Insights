from datetime import datetime
from urllib.parse import urlsplit

import stripe

from app.config import settings
from modules.billing.domain.plans import PLANS


class BillingUnavailable(Exception):
    pass


def price_ids() -> dict[tuple[str, str], str]:
    configured = {
        (plan, interval): getattr(settings, f"stripe_{plan}_{interval}_price")
        for plan in ("analyst", "pro")
        for interval in ("month", "year")
    }
    return {key: value for key, value in configured.items() if value and value.startswith("price_")}


def billing_enabled() -> bool:
    key = settings.stripe_test_secret_key
    secret = settings.stripe_webhook_secret
    ids = price_ids()
    origin = urlsplit(settings.web_app_url)
    trusted_url = (
        origin.hostname
        and (origin.scheme == "https" or (origin.scheme == "http" and origin.hostname in {"localhost", "127.0.0.1"}))
        and not (origin.username or origin.password or origin.query or origin.fragment)
    )
    return bool(
        key and key.get_secret_value().startswith(("sk_test_", "rk_test_"))
        and secret and secret.get_secret_value().startswith("whsec_")
        and len(set(ids.values())) == 4 and trusted_url
    )


class StripeGateway:
    def __init__(self) -> None:
        if not billing_enabled():
            raise BillingUnavailable("Stripe test checkout is not configured.")
        self.client = stripe.StripeClient(
            settings.stripe_test_secret_key.get_secret_value(),
            http_client=stripe.RequestsClient(timeout=(3, 8)),
            max_network_retries=1,
        ).v1
        self.return_url = settings.web_app_url.rstrip("/") + "/profile?tab=subscription"
        self.prices = price_ids()

    def verify_event(self, raw: bytes, signature: str):
        return stripe.Webhook.construct_event(raw, signature, settings.stripe_webhook_secret.get_secret_value())

    def create_customer(self, user_id: str, email: str) -> str:
        customer = self.client.customers.create(
            {"email": email}, {"idempotency_key": f"pitwall-test-customer-{user_id}"},
        )
        if customer.livemode:
            raise BillingUnavailable("Expected a Stripe test customer.")
        return customer.id

    def check_price(self, price, plan: str, interval: str) -> bool:
        price = price.to_dict()
        recurring = price.get("recurring") or {}
        return (
            price.get("livemode") is False
            and price.get("currency") == "huf"
            and price.get("unit_amount") == PLANS[plan].prices_huf[interval] * 100
            and recurring.get("interval") == interval
            and recurring.get("interval_count") == 1
        )

    def create_checkout(self, customer: str, plan: str, interval: str, key: str, expires: datetime):
        price_id = self.prices[(plan, interval)]
        price = self.client.prices.retrieve(price_id)
        if not price.active or not self.check_price(price, plan, interval):
            raise BillingUnavailable("Stripe test pricing does not match the plan catalog.")
        return self.client.checkout.sessions.create({
            "mode": "subscription",
            "customer": customer,
            "payment_method_types": ["card"],
            "billing_address_collection": "required",
            "customer_update": {"address": "auto", "name": "auto"},
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": self.return_url + "&checkout=returned",
            "cancel_url": self.return_url + "&checkout=cancelled",
            "expires_at": int(expires.timestamp()),
        }, {"idempotency_key": key})

    def get_checkout(self, checkout_id: str):
        return self.client.checkout.sessions.retrieve(checkout_id)

    def expire_checkout(self, checkout_id: str) -> None:
        self.client.checkout.sessions.expire(checkout_id)

    def subscriptions(self, customer: str):
        return self.client.subscriptions.list({
            "customer": customer, "status": "all", "limit": 10,
        }).auto_paging_iter()

    def subscription(self, subscription_id: str):
        return self.client.subscriptions.retrieve(subscription_id, {"expand": ["latest_invoice"]})

    def cancel_renewal(self, subscription_id: str) -> None:
        self.client.subscriptions.update(subscription_id, {"cancel_at_period_end": True})

    def portal(self, customer: str) -> str:
        params = {"customer": customer, "return_url": self.return_url}
        if settings.stripe_portal_configuration:
            params["configuration"] = settings.stripe_portal_configuration
        return self.client.billing_portal.sessions.create(params).url
