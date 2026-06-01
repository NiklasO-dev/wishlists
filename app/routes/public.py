from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.email import send_wishlist_emails
from app.encryption import encrypt, encrypt_optional, generate_encryption_key, hash_key
from app.models import Wishlist
from app.templating import templates
from app.wishlist_crypto import build_url, redirect_with_key

router = APIRouter()


@router.get("/")
async def home(request: Request):
    return templates.TemplateResponse(request, "home.html")


@router.get("/privacy")
async def privacy_page(request: Request):
    return templates.TemplateResponse(request, "privacy.html")


@router.post("/wishlists")
async def create_wishlist(
    request: Request,
    title: str = Form(...),
    parent_email: str = Form(""),
    encryption_key: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    plain_title = title.strip()
    plain_email = parent_email.strip() or None
    key = encryption_key.strip() or generate_encryption_key()

    wishlist = Wishlist(
        title=encrypt(plain_title, key),
        parent_email=encrypt_optional(plain_email, key),
        encryption_key_hash=hash_key(key),
    )
    db.add(wishlist)
    await db.commit()
    await db.refresh(wishlist)

    admin_url = build_url(
        f"{settings.app_base_url}/list/admin",
        wishlist.admin_token,
        key,
        include_key=True,
    )
    guest_url = build_url(
        f"{settings.app_base_url}/list/guest",
        wishlist.guest_token,
        key,
        include_key=True,
    )

    if plain_email and settings.smtp_host:
        await send_wishlist_emails(plain_email, plain_title, admin_url, guest_url)

    return redirect_with_key(f"/list/admin/{wishlist.admin_token}", key)
