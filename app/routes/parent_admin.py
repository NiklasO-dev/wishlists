from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models import Item, Reservation, Wishlist
from app.templating import templates

router = APIRouter(prefix="/list/admin")


async def get_wishlist_by_admin_token(
    admin_token: str, db: AsyncSession
) -> Wishlist | None:
    result = await db.execute(
        select(Wishlist)
        .options(selectinload(Wishlist.items).selectinload(Item.reservations))
        .where(Wishlist.admin_token == admin_token)
    )
    return result.scalar_one_or_none()


@router.get("/{admin_token}")
async def admin_page(
    request: Request, admin_token: str, db: AsyncSession = Depends(get_db)
):
    wishlist = await get_wishlist_by_admin_token(admin_token, db)
    if not wishlist:
        return templates.TemplateResponse(
            request, "error.html", {"message": request.state.t.get("error_not_found", "Wishlist not found.")}, status_code=404
        )

    guest_url = f"{settings.app_base_url}/list/guest/{wishlist.guest_token}"
    admin_url = f"{settings.app_base_url}/list/admin/{wishlist.admin_token}"

    # Calculate deletion date
    max_days = settings.wishlist_max_age_days
    if wishlist.deletion_extended:
        max_days += settings.wishlist_extension_days

    expires_at = wishlist.created_at + timedelta(days=max_days)

    active_items = [i for i in wishlist.items if not i.is_removed]

    return templates.TemplateResponse(
        request,
        "wishlist_admin.html",
        {
            "wishlist": wishlist,
            "items": active_items,
            "guest_url": guest_url,
            "admin_url": admin_url,
            "max_days": max_days,
            "expires_at": expires_at,
            "settings": settings,
        },
    )


@router.post("/{admin_token}/title")
async def update_title(
    admin_token: str,
    title: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    wishlist = await get_wishlist_by_admin_token(admin_token, db)
    if not wishlist:
        return RedirectResponse(url="/", status_code=303)

    wishlist.title = title.strip()
    await db.commit()
    return RedirectResponse(url=f"/list/admin/{admin_token}", status_code=303)


@router.post("/{admin_token}/items/reorder")
async def reorder_items(
    admin_token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    wishlist = await get_wishlist_by_admin_token(admin_token, db)
    if not wishlist or wishlist.is_done:
        return RedirectResponse(url="/", status_code=303)

    form_data = await request.form()
    order_raw = form_data.get("order", "")
    if not order_raw:
        return RedirectResponse(url=f"/list/admin/{admin_token}", status_code=303)

    try:
        item_ids = [int(x) for x in order_raw.split(",") if x.strip()]
    except ValueError:
        return RedirectResponse(url=f"/list/admin/{admin_token}", status_code=303)

    # Update positions based on the new order
    for position, item_id in enumerate(item_ids):
        result = await db.execute(
            select(Item).where(Item.id == item_id, Item.wishlist_id == wishlist.id)
        )
        item = result.scalar_one_or_none()
        if item:
            item.position = position

    await db.commit()
    return RedirectResponse(url=f"/list/admin/{admin_token}", status_code=303)


@router.post("/{admin_token}/items")
async def add_item(
    admin_token: str,
    title: str = Form(...),
    description: str = Form(""),
    url: str = Form(""),
    url2: str = Form(""),
    url3: str = Form(""),
    price_hint: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    wishlist = await get_wishlist_by_admin_token(admin_token, db)
    if not wishlist or wishlist.is_done:
        return RedirectResponse(url="/", status_code=303)

    # Get next position
    max_pos = 0
    for item in wishlist.items:
        if item.position > max_pos:
            max_pos = item.position
    next_pos = max_pos + 1

    item = Item(
        wishlist_id=wishlist.id,
        title=title.strip(),
        description=description.strip() or None,
        url=url.strip() or None,
        url2=url2.strip() or None,
        url3=url3.strip() or None,
        price_hint=price_hint.strip() or None,
        position=next_pos,
    )
    db.add(item)
    await db.commit()
    return RedirectResponse(url=f"/list/admin/{admin_token}", status_code=303)


@router.post("/{admin_token}/items/{item_id}/edit")
async def edit_item(
    admin_token: str,
    item_id: int,
    title: str = Form(...),
    description: str = Form(""),
    url: str = Form(""),
    url2: str = Form(""),
    url3: str = Form(""),
    price_hint: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    wishlist = await get_wishlist_by_admin_token(admin_token, db)
    if not wishlist:
        return RedirectResponse(url="/", status_code=303)

    result = await db.execute(
        select(Item).where(Item.id == item_id, Item.wishlist_id == wishlist.id)
    )
    item = result.scalar_one_or_none()
    if not item:
        return RedirectResponse(url=f"/list/admin/{admin_token}", status_code=303)

    item.title = title.strip()
    item.description = description.strip() or None
    item.url = url.strip() or None
    item.url2 = url2.strip() or None
    item.url3 = url3.strip() or None
    item.price_hint = price_hint.strip() or None
    await db.commit()
    return RedirectResponse(url=f"/list/admin/{admin_token}", status_code=303)


@router.post("/{admin_token}/items/{item_id}/delete")
async def delete_item(
    admin_token: str, item_id: int, db: AsyncSession = Depends(get_db)
):
    wishlist = await get_wishlist_by_admin_token(admin_token, db)
    if not wishlist:
        return RedirectResponse(url="/", status_code=303)

    result = await db.execute(
        select(Item).where(Item.id == item_id, Item.wishlist_id == wishlist.id)
    )
    item = result.scalar_one_or_none()
    if item:
        item.removed_at = datetime.now(timezone.utc)
        await db.commit()
    return RedirectResponse(url=f"/list/admin/{admin_token}", status_code=303)


@router.post("/{admin_token}/reservations/{reservation_id}/delete")
async def delete_reservation(
    admin_token: str, reservation_id: int, db: AsyncSession = Depends(get_db)
):
    wishlist = await get_wishlist_by_admin_token(admin_token, db)
    if not wishlist:
        return RedirectResponse(url="/", status_code=303)

    result = await db.execute(
        select(Reservation)
        .join(Item)
        .where(Reservation.id == reservation_id, Item.wishlist_id == wishlist.id)
    )
    reservation = result.scalar_one_or_none()
    if reservation:
        reservation.removed_at = datetime.now(timezone.utc)
        await db.commit()
    return RedirectResponse(url=f"/list/admin/{admin_token}", status_code=303)


@router.post("/{admin_token}/done")
async def mark_done(
    admin_token: str, db: AsyncSession = Depends(get_db)
):
    wishlist = await get_wishlist_by_admin_token(admin_token, db)
    if not wishlist:
        return RedirectResponse(url="/", status_code=303)

    wishlist.done_at = datetime.now(timezone.utc)
    await db.commit()
    return RedirectResponse(url=f"/list/admin/{admin_token}", status_code=303)


@router.post("/{admin_token}/extend")
async def extend_deletion(
    admin_token: str, db: AsyncSession = Depends(get_db)
):
    wishlist = await get_wishlist_by_admin_token(admin_token, db)
    if not wishlist or wishlist.deletion_extended:
        return RedirectResponse(url=f"/list/admin/{admin_token}", status_code=303)

    wishlist.deletion_extended = True
    await db.commit()
    return RedirectResponse(url=f"/list/admin/{admin_token}", status_code=303)


@router.post("/{admin_token}/toggle-show-buyers")
async def toggle_show_buyers(
    admin_token: str, db: AsyncSession = Depends(get_db)
):
    wishlist = await get_wishlist_by_admin_token(admin_token, db)
    if not wishlist:
        return RedirectResponse(url="/", status_code=303)

    wishlist.show_buyers_to_guests = not wishlist.show_buyers_to_guests
    await db.commit()
    return RedirectResponse(url=f"/list/admin/{admin_token}", status_code=303)


@router.post("/{admin_token}/delete")
async def delete_wishlist(
    admin_token: str, db: AsyncSession = Depends(get_db)
):
    wishlist = await get_wishlist_by_admin_token(admin_token, db)
    if not wishlist:
        return RedirectResponse(url="/", status_code=303)

    # Update site stats before deleting
    from app.models import SiteStats

    result = await db.execute(select(SiteStats).where(SiteStats.id == 1))
    stats = result.scalar_one_or_none()
    if not stats:
        stats = SiteStats(id=1, removed_wishlist_count=0, removed_item_count=0)
        db.add(stats)

    active_items = [i for i in wishlist.items if not i.is_removed]
    stats.removed_wishlist_count += 1
    stats.removed_item_count += len(active_items)

    await db.delete(wishlist)
    await db.commit()
    return RedirectResponse(url="/?deleted=1", status_code=303)


@router.get("/{admin_token}/export")
async def export_wishlist(
    request: Request, admin_token: str, db: AsyncSession = Depends(get_db)
):
    wishlist = await get_wishlist_by_admin_token(admin_token, db)
    if not wishlist:
        return RedirectResponse(url="/", status_code=303)

    active_items = [i for i in wishlist.items if not i.is_removed]
    export_date = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")

    return templates.TemplateResponse(
        request,
        "wishlist_export.html",
        {
            "wishlist": wishlist,
            "items": active_items,
            "export_date": export_date,
        },
    )


@router.get("/{admin_token}/share")
async def share_wishlist(
    request: Request, admin_token: str, db: AsyncSession = Depends(get_db)
):
    wishlist = await get_wishlist_by_admin_token(admin_token, db)
    if not wishlist:
        return RedirectResponse(url="/", status_code=303)

    guest_url = f"{settings.app_base_url}/list/guest/{wishlist.guest_token}"

    return templates.TemplateResponse(
        request,
        "wishlist_share.html",
        {
            "wishlist": wishlist,
            "guest_url": guest_url,
            "wishlist_description": None,
        },
    )
