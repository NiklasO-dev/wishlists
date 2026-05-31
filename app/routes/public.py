from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.email import send_wishlist_emails
from app.models import Wishlist
from app.templating import templates

router = APIRouter()


@router.get("/")
async def home(request: Request):
    return templates.TemplateResponse(request, "home.html")


@router.post("/wishlists")
async def create_wishlist(
    request: Request,
    title: str = Form(...),
    parent_email: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    wishlist = Wishlist(
        title=title.strip(),
        parent_email=parent_email.strip() or None,
    )
    db.add(wishlist)
    await db.commit()
    await db.refresh(wishlist)

    admin_url = f"{settings.app_base_url}/list/admin/{wishlist.admin_token}"
    guest_url = f"{settings.app_base_url}/list/guest/{wishlist.guest_token}"

    # Send email if address provided and SMTP configured
    if wishlist.parent_email and settings.smtp_host:
        await send_wishlist_emails(
            wishlist.parent_email, wishlist.title, admin_url, guest_url
        )

    return RedirectResponse(
        url=f"/list/admin/{wishlist.admin_token}", status_code=303
    )
