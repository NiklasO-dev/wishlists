from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.encryption import verify_key
from app.models import Item, Reservation, Wishlist
from app.templating import templates
from app.wishlist_crypto import (
    encrypt_reservation_fields,
    get_key_from_request_or_form,
    redirect_with_key,
    require_key_and_decrypt,
)


router = APIRouter(prefix="/list/guest")


async def get_wishlist_by_guest_token(
    guest_token: str, db: AsyncSession
) -> Wishlist | None:
    result = await db.execute(
        select(Wishlist)
        .options(selectinload(Wishlist.items).selectinload(Item.reservations))
        .where(Wishlist.guest_token == guest_token, Wishlist.done_at.is_(None))
    )
    return result.scalar_one_or_none()


@router.get("/{guest_token}")
async def guest_page(
    request: Request, guest_token: str, db: AsyncSession = Depends(get_db)
):
    wishlist = await get_wishlist_by_guest_token(guest_token, db)
    if not wishlist:
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "message": request.state.t.get(
                    "error_unavailable", "This wishlist is no longer available."
                )
            },
            status_code=404,
        )

    key, error_response = await require_key_and_decrypt(
        request,
        wishlist,
        action_url=f"/list/guest/{guest_token}/unlock",
        list_type="guest",
    )
    if error_response:
        return error_response

    active_items = [i for i in wishlist.items if not i.is_removed]

    return templates.TemplateResponse(
        request,
        "wishlist_guest.html",
        {
            "wishlist": wishlist,
            "items": active_items,
            "guest_token": guest_token,
            "encryption_key": key,
            "show_buyers": wishlist.show_buyers_to_guests,
        },
    )


@router.post("/{guest_token}/unlock")
async def unlock_guest(
    guest_token: str,
    encryption_key: str = Form(...),
):
    key = encryption_key.strip()
    return redirect_with_key(f"/list/guest/{guest_token}", key)


@router.post("/{guest_token}/items/{item_id}/reserve")
async def reserve_item(
    request: Request,
    guest_token: str,
    item_id: int,
    guest_name: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    wishlist = await get_wishlist_by_guest_token(guest_token, db)
    if not wishlist:
        return RedirectResponse(url="/", status_code=303)

    key = await get_key_from_request_or_form(request)
    if not key or not verify_key(key, wishlist.encryption_key_hash):
        return RedirectResponse(url=f"/list/guest/{guest_token}", status_code=303)

    result = await db.execute(
        select(Item)
        .options(selectinload(Item.reservations))
        .where(
            Item.id == item_id,
            Item.wishlist_id == wishlist.id,
            Item.removed_at.is_(None),
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        return redirect_with_key(f"/list/guest/{guest_token}", key)

    reservation = Reservation(item_id=item.id)
    encrypt_reservation_fields(reservation, key, guest_name=guest_name.strip())
    db.add(reservation)
    await db.commit()
    await db.refresh(reservation)

    redirect_url = url_with_key(f"/list/guest/{guest_token}", key)

    return JSONResponse(
        content={"reservation_id": reservation.id, "redirect": redirect_url},
        status_code=200,
    )


@router.post("/{guest_token}/reservations/{reservation_id}/undo")
async def undo_reservation(
    request: Request,
    guest_token: str,
    reservation_id: int,
    db: AsyncSession = Depends(get_db),
):
    wishlist = await get_wishlist_by_guest_token(guest_token, db)
    if not wishlist:
        return JSONResponse(content={"error": "not_found"}, status_code=404)

    key = await get_key_from_request_or_form(request)
    if not key or not verify_key(key, wishlist.encryption_key_hash):
        return JSONResponse(content={"error": "not_found"}, status_code=404)

    result = await db.execute(
        select(Reservation)
        .join(Item)
        .where(
            Reservation.id == reservation_id,
            Item.wishlist_id == wishlist.id,
            Reservation.removed_at.is_(None),
        )
    )
    reservation = result.scalar_one_or_none()
    if not reservation:
        return JSONResponse(content={"error": "not_found"}, status_code=404)

    now = datetime.now(timezone.utc)
    created = reservation.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    elapsed = (now - created).total_seconds()
    if elapsed > 60:
        return JSONResponse(content={"error": "expired"}, status_code=410)

    reservation.removed_at = now
    await db.commit()

    return JSONResponse(content={"success": True}, status_code=200)
