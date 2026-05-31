from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Item, Reservation, Wishlist
from app.templating import templates

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
            {"message": request.state.t.get("error_unavailable", "This wishlist is no longer available.")},
            status_code=404,
        )

    active_items = [i for i in wishlist.items if not i.is_removed]

    return templates.TemplateResponse(
        request,
        "wishlist_guest.html",
        {
            "wishlist": wishlist,
            "items": active_items,
            "guest_token": guest_token,
            "show_buyers": wishlist.show_buyers_to_guests,
        },
    )


@router.post("/{guest_token}/items/{item_id}/reserve")
async def reserve_item(
    guest_token: str,
    item_id: int,
    guest_name: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    wishlist = await get_wishlist_by_guest_token(guest_token, db)
    if not wishlist:
        return RedirectResponse(url="/", status_code=303)

    # Find the item
    result = await db.execute(
        select(Item)
        .options(selectinload(Item.reservations))
        .where(Item.id == item_id, Item.wishlist_id == wishlist.id, Item.removed_at.is_(None))
    )
    item = result.scalar_one_or_none()
    if not item:
        return RedirectResponse(
            url=f"/list/guest/{guest_token}", status_code=303
        )

    # Create reservation (multiple guests can reserve the same item)
    reservation = Reservation(
        item_id=item.id,
        guest_name=guest_name.strip(),
    )
    db.add(reservation)
    await db.commit()
    await db.refresh(reservation)

    # Return JSON with reservation ID so the client can offer undo
    return JSONResponse(
        content={"reservation_id": reservation.id, "redirect": f"/list/guest/{guest_token}"},
        status_code=200,
    )


@router.post("/{guest_token}/reservations/{reservation_id}/undo")
async def undo_reservation(
    guest_token: str,
    reservation_id: int,
    db: AsyncSession = Depends(get_db),
):
    wishlist = await get_wishlist_by_guest_token(guest_token, db)
    if not wishlist:
        return JSONResponse(content={"error": "not_found"}, status_code=404)

    # Find the reservation — must belong to this wishlist
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

    # Only allow undo within 60 seconds of creation
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
