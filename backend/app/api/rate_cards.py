from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.organisation import User
from app.models.rate_card import GatewayRateCard
from app.models.gateway import GatewayEnum
from app.core.rate_cards import seed_default_rate_cards_for_org
from app.schemas.rate_card import (
    GatewayRateCardCreate,
    GatewayRateCardUpdate,
    GatewayRateCardResponse,
    GatewayRateCardListResponse,
    CalculateFeeRequest,
    CalculateFeeResponse,
)

router = APIRouter(prefix="/rate-cards", tags=["Rate Cards"])


@router.get("", response_model=GatewayRateCardListResponse)
def list_rate_cards(
    gateway: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves all contracted rate cards for the authenticated organisation.
    Auto-seeds standard Indian benchmarks (Razorpay/Stripe) if no cards currently exist.
    """
    query = db.query(GatewayRateCard).filter(
        GatewayRateCard.org_id == current_user.org_id,
        GatewayRateCard.is_active == True,
    )

    if gateway:
        gw_enum = GatewayEnum(gateway.lower().strip())
        query = query.filter(GatewayRateCard.gateway == gw_enum)

    cards = query.order_by(GatewayRateCard.gateway, GatewayRateCard.payment_method).all()

    # If empty, auto-seed defaults for the org
    if not cards:
        target_gw = gateway.lower().strip() if gateway else "razorpay"
        cards = seed_default_rate_cards_for_org(db, current_user.org_id, target_gw)

    return GatewayRateCardListResponse(items=cards, total=len(cards))


@router.post("", response_model=GatewayRateCardResponse, status_code=status.HTTP_201_CREATED)
def create_rate_card(
    payload: GatewayRateCardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Creates a new custom rate card rule for the organisation.
    """
    # Check if active duplicate rule exists
    existing = (
        db.query(GatewayRateCard)
        .filter(
            GatewayRateCard.org_id == current_user.org_id,
            GatewayRateCard.gateway == payload.gateway,
            GatewayRateCard.payment_method == payload.payment_method,
            GatewayRateCard.card_network == payload.card_network,
            GatewayRateCard.is_international == payload.is_international,
            GatewayRateCard.is_active == True,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An active rate card rule already exists for this payment rail. Please edit the existing rule.",
        )

    card = GatewayRateCard(
        org_id=current_user.org_id,
        **payload.model_dump(),
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


@router.put("/{card_id}", response_model=GatewayRateCardResponse)
def update_rate_card(
    card_id: str,
    payload: GatewayRateCardUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Updates an existing rate card rule (e.g. customized percentage MDR, flat fee, or caps).
    """
    card = (
        db.query(GatewayRateCard)
        .filter(
            GatewayRateCard.id == card_id,
            GatewayRateCard.org_id == current_user.org_id,
        )
        .first()
    )
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rate card not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(card, field, value)

    db.commit()
    db.refresh(card)
    return card


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rate_card(
    card_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Deactivates or deletes a rate card rule.
    """
    card = (
        db.query(GatewayRateCard)
        .filter(
            GatewayRateCard.id == card_id,
            GatewayRateCard.org_id == current_user.org_id,
        )
        .first()
    )
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rate card not found")

    db.delete(card)
    db.commit()
    return None


@router.post("/reset-benchmarks", response_model=GatewayRateCardListResponse)
def reset_to_benchmarks(
    gateway: str = "razorpay",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Resets all rate cards for the gateway back to standard Indian industry benchmarks.
    """
    gw_enum = GatewayEnum(gateway.lower().strip())
    # Delete existing cards for this gateway
    db.query(GatewayRateCard).filter(
        GatewayRateCard.org_id == current_user.org_id,
        GatewayRateCard.gateway == gw_enum,
    ).delete()
    db.commit()

    # Re-seed benchmarks
    cards = seed_default_rate_cards_for_org(db, current_user.org_id, gateway)
    return GatewayRateCardListResponse(items=cards, total=len(cards))


@router.post("/calculate", response_model=CalculateFeeResponse)
def preview_rate_calculation(
    payload: CalculateFeeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Interactive calculator: returns exact breakdown of MDR, 18% GST, and Net settlement.
    """
    if payload.rate_card_id:
        card = (
            db.query(GatewayRateCard)
            .filter(
                GatewayRateCard.id == payload.rate_card_id,
                GatewayRateCard.org_id == current_user.org_id,
            )
            .first()
        )
        if not card:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rate card not found")
    else:
        # Default standard 2.0% domestic card
        card = (
            db.query(GatewayRateCard)
            .filter(
                GatewayRateCard.org_id == current_user.org_id,
                GatewayRateCard.is_active == True,
            )
            .first()
        )
        if not card:
            seed_default_rate_cards_for_org(db, current_user.org_id, "razorpay")
            card = db.query(GatewayRateCard).filter(GatewayRateCard.org_id == current_user.org_id).first()

    res = card.calculate_expected_charges(payload.gross_amount)
    effective_take_rate = (
        (res["expected_total_deduction"] / res["gross_amount"]) * 100
        if res["gross_amount"] > 0
        else 0
    )

    return CalculateFeeResponse(
        gross_amount=res["gross_amount"],
        expected_fee=res["expected_fee"],
        expected_gst=res["expected_gst"],
        expected_total_deduction=res["expected_total_deduction"],
        expected_net_amount=res["expected_net_amount"],
        effective_take_rate_pct=effective_take_rate,
    )
