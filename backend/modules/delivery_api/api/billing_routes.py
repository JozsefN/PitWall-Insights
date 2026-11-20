import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from modules.billing.application.service import BillingConflict, BillingService, membership
from modules.billing.domain.plans import Interval, PLANS, PaidPlan
from modules.billing.infrastructure.db_models import BillingAccountRecord
from modules.billing.infrastructure.stripe_gateway import BillingUnavailable, StripeGateway
from modules.delivery_api.api.auth_dependencies import require_current_user
from modules.identity_auth.domain.models import User
from modules.storage.infrastructure.db import get_db

router = APIRouter(prefix="/api/billing", tags=["billing"])


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan: PaidPlan
    interval: Interval


def service_action(db, callback):
    try:
        return callback(BillingService(db, StripeGateway()))
    except BillingConflict as error:
        raise HTTPException(409, str(error)) from error
    except BillingUnavailable as error:
        raise HTTPException(503, str(error)) from error
    except stripe.StripeError as error:
        raise HTTPException(502, "Stripe could not complete the request. Try again shortly.") from error


@router.get("/plans")
def plans():
    return list(PLANS.values())


@router.get("/me")
def my_billing(response: Response, user: User = Depends(require_current_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return membership(db.get(BillingAccountRecord, user.id))


@router.post("/checkout")
def checkout(payload: CheckoutRequest, response: Response, user: User = Depends(require_current_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return {"url": service_action(db, lambda service: service.checkout(user, payload.plan, payload.interval))}


@router.post("/portal")
def portal(response: Response, user: User = Depends(require_current_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return {"url": service_action(db, lambda service: service.portal(user.id))}


@router.post("/cancel")
def cancel(response: Response, user: User = Depends(require_current_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return service_action(db, lambda service: service.cancel(user.id))


@router.post("/sync")
def sync(response: Response, user: User = Depends(require_current_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return service_action(db, lambda service: service.sync(user.id))


@router.post("/webhook", status_code=204)
async def webhook(request: Request, stripe_signature: str | None = Header(default=None)):
    if not stripe_signature:
        raise HTTPException(400, "Missing Stripe signature")
    payload = bytearray()
    async for chunk in request.stream():
        payload.extend(chunk)
        if len(payload) > 1_000_000:
            raise HTTPException(413, "Stripe event is too large")
    await run_in_threadpool(process_webhook, bytes(payload), stripe_signature)
    return Response(status_code=204)


def process_webhook(payload: bytes, signature: str):
    from modules.storage.infrastructure.db import SessionLocal

    def process(service):
        try:
            event = service.gateway.verify_event(payload, signature)
            if event.livemode is not False:
                raise ValueError("Expected a test event")
        except (ValueError, stripe.SignatureVerificationError) as error:
            raise HTTPException(400, "Invalid Stripe test event") from error
        service.apply_event(event)

    with SessionLocal() as db:
        service_action(db, process)
