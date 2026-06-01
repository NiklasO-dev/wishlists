from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models import Item, Reservation, SiteStats, Wishlist
from app.templating import templates

router = APIRouter(prefix="/admin")

ADMIN_COOKIE_NAME = "wishlist_admin_auth"
SESSION_MAX_AGE = 24 * 3600  # 24 hours


def _get_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.admin_password, salt="wishlist-admin-session")


def is_authenticated(request: Request) -> bool:
    token = request.cookies.get(ADMIN_COOKIE_NAME)
    if not token:
        return False
    try:
        _get_serializer().loads(token, max_age=SESSION_MAX_AGE)
        return True
    except (BadSignature, SignatureExpired):
        return False


async def run_cleanup(db: AsyncSession) -> dict:
    """Delete wishlists that are past their retention period.

    - Active wishlists older than wishlist_max_age_days
    - Done wishlists older than done_wishlist_cleanup_days (since done_at)
    """
    now = datetime.now(timezone.utc)
    deleted_count = 0
    deleted_items = 0

    # 1. Active wishlists past max age
    max_age_cutoff = now - timedelta(days=settings.wishlist_max_age_days)
    result = await db.execute(
        select(Wishlist)
        .options(selectinload(Wishlist.items))
        .where(Wishlist.done_at.is_(None), Wishlist.created_at < max_age_cutoff)
    )
    expired_active = result.scalars().all()
    to_delete = list(expired_active)

    # 2. Done wishlists past cleanup period
    done_cutoff = now - timedelta(days=settings.done_wishlist_cleanup_days)
    result = await db.execute(
        select(Wishlist)
        .options(selectinload(Wishlist.items))
        .where(Wishlist.done_at.is_not(None), Wishlist.done_at < done_cutoff)
    )
    expired_done = result.scalars().all()
    to_delete += list(expired_done)

    # Deduplicate
    seen_ids = set()
    unique_to_delete = []
    for w in to_delete:
        if w.id not in seen_ids:
            seen_ids.add(w.id)
            unique_to_delete.append(w)

    # Update stats and delete
    if unique_to_delete:
        result = await db.execute(select(SiteStats).where(SiteStats.id == 1))
        stats = result.scalar_one_or_none()
        if not stats:
            stats = SiteStats(id=1, removed_wishlist_count=0, removed_item_count=0)
            db.add(stats)

        for wishlist in unique_to_delete:
            active_items = [i for i in wishlist.items if not i.is_removed]
            stats.removed_wishlist_count += 1
            stats.removed_item_count += len(active_items)
            deleted_items += len(active_items)
            await db.delete(wishlist)
            deleted_count += 1

        await db.commit()

    return {"deleted_wishlists": deleted_count, "deleted_items": deleted_items}


@router.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse(request, "admin_login.html")


@router.post("/login")
async def login(request: Request, password: str = Form(...)):
    if password == settings.admin_password:
        token = _get_serializer().dumps("admin")
        response = RedirectResponse(url="/admin", status_code=303)
        response.set_cookie(
            ADMIN_COOKIE_NAME, token,
            max_age=SESSION_MAX_AGE, httponly=True, samesite="lax"
        )
        return response
    return templates.TemplateResponse(
        request, "admin_login.html", {"error": True}, status_code=401
    )


@router.post("/logout")
async def logout():
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie(ADMIN_COOKIE_NAME)
    return response


@router.get("")
async def site_admin_dashboard(
    request: Request, db: AsyncSession = Depends(get_db)
):
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=303)

    # Active wishlists
    result = await db.execute(
        select(func.count()).select_from(Wishlist).where(Wishlist.done_at.is_(None))
    )
    active_wishlists = result.scalar() or 0

    # Done wishlists (still in DB)
    result = await db.execute(
        select(func.count()).select_from(Wishlist).where(Wishlist.done_at.is_not(None))
    )
    done_wishlists_in_db = result.scalar() or 0

    # Get removed count from stats table
    result = await db.execute(select(SiteStats).where(SiteStats.id == 1))
    stats = result.scalar_one_or_none()
    removed_count = stats.removed_wishlist_count if stats else 0
    total_done = done_wishlists_in_db + removed_count

    # Total active items (not removed, in active wishlists)
    result = await db.execute(
        select(func.count())
        .select_from(Item)
        .join(Wishlist)
        .where(Wishlist.done_at.is_(None), Item.removed_at.is_(None))
    )
    total_active_items = result.scalar() or 0

    # Average items per active wishlist
    avg_items = (
        round(total_active_items / active_wishlists, 1) if active_wishlists > 0 else 0
    )

    # Total active reservations
    result = await db.execute(
        select(func.count())
        .select_from(Reservation)
        .join(Item)
        .join(Wishlist)
        .where(
            Wishlist.done_at.is_(None),
            Item.removed_at.is_(None),
            Reservation.removed_at.is_(None),
        )
    )
    total_reservations = result.scalar() or 0

    # Check cleanup message
    cleanup_result = request.query_params.get("cleanup")

    return templates.TemplateResponse(
        request,
        "site_admin.html",
        {
            "active_wishlists": active_wishlists,
            "done_wishlists": total_done,
            "total_active_items": total_active_items,
            "avg_items": avg_items,
            "total_reservations": total_reservations,
            "cleanup_result": cleanup_result,
            "settings": settings,
        },
    )


@router.post("/cleanup")
async def trigger_cleanup(request: Request, db: AsyncSession = Depends(get_db)):
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=303)
    result = await run_cleanup(db)
    deleted = result["deleted_wishlists"]
    return RedirectResponse(url=f"/admin?cleanup={deleted}", status_code=303)
