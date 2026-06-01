from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import RedirectResponse

from app.encryption import decrypt, decrypt_optional, encrypt, encrypt_optional, verify_key
from app.models import Item, Reservation, Wishlist
from app.templating import templates


def decrypt_wishlist(wishlist: Wishlist, key: str) -> None:
    wishlist.title = decrypt(wishlist.title, key)
    wishlist.parent_email = decrypt_optional(wishlist.parent_email, key)
    for item in wishlist.items:
        decrypt_item(item, key)


def decrypt_item(item: Item, key: str) -> None:
    item.title = decrypt(item.title, key)
    item.description = decrypt_optional(item.description, key)
    item.url = decrypt_optional(item.url, key)
    item.url2 = decrypt_optional(item.url2, key)
    item.url3 = decrypt_optional(item.url3, key)
    item.price_hint = decrypt_optional(item.price_hint, key)
    item.image_url = decrypt_optional(item.image_url, key)
    for reservation in item.reservations:
        decrypt_reservation(reservation, key)


def decrypt_reservation(reservation: Reservation, key: str) -> None:
    reservation.guest_name = decrypt(reservation.guest_name, key)
    reservation.note = decrypt_optional(reservation.note, key)


def encrypt_wishlist_fields(
    wishlist: Wishlist, key: str, *, title: str | None = None, parent_email: str | None = None
) -> None:
    if title is not None:
        wishlist.title = encrypt(title, key)
    if parent_email is not None:
        wishlist.parent_email = encrypt_optional(parent_email, key)


def encrypt_item_fields(
    item: Item,
    key: str,
    *,
    title: str,
    description: str | None = None,
    url: str | None = None,
    url2: str | None = None,
    url3: str | None = None,
    price_hint: str | None = None,
) -> None:
    item.title = encrypt(title, key)
    item.description = encrypt_optional(description, key)
    item.url = encrypt_optional(url, key)
    item.url2 = encrypt_optional(url2, key)
    item.url3 = encrypt_optional(url3, key)
    item.price_hint = encrypt_optional(price_hint, key)


def encrypt_reservation_fields(reservation: Reservation, key: str, *, guest_name: str) -> None:
    reservation.guest_name = encrypt(guest_name, key)


def build_url(base_path: str, token: str, key: str | None = None, include_key: bool = True) -> str:
    path = f"{base_path}/{token}"
    if include_key and key:
        return f"{path}?{urlencode({'key': key})}"
    return path


def url_with_key(path: str, key: str) -> str:
    return f"{path}?{urlencode({'key': key})}"


def redirect_with_key(path: str, key: str) -> RedirectResponse:
    separator = "&" if "?" in path else "?"
    return RedirectResponse(url=f"{path}{separator}{urlencode({'key': key})}", status_code=303)


def get_key_from_request(request: Request) -> str | None:
    key = request.query_params.get("key")
    if key:
        return key.strip()
    return None


async def get_key_from_request_or_form(request: Request) -> str | None:
    key = get_key_from_request(request)
    if key:
        return key
    if request.method == "POST":
        form = await request.form()
        raw = form.get("key")
        if raw:
            return str(raw).strip()
    return None


def render_unlock_page(
    request: Request,
    *,
    action_url: str,
    list_type: str,
    error: str | None = None,
):
    return templates.TemplateResponse(
        request,
        "unlock.html",
        {
            "action_url": action_url,
            "list_type": list_type,
            "error": error,
        },
        status_code=401 if error else 200,
    )


async def require_key_and_decrypt(
    request: Request,
    wishlist: Wishlist,
    *,
    action_url: str,
    list_type: str,
    reveal_token: str | None = None,
) -> tuple[str | None, object | None]:
    """Return (key, error_response). error_response is a TemplateResponse if unlock needed."""
    if (
        reveal_token
        and wishlist.key_reveal_pending
        and wishlist.key_reveal_wrapped
    ):
        try:
            key = decrypt(wishlist.key_reveal_wrapped, reveal_token)
            if verify_key(key, wishlist.encryption_key_hash):
                decrypt_wishlist(wishlist, key)
                return key, None
        except Exception:
            pass

    key = await get_key_from_request_or_form(request)
    if not key:
        return None, render_unlock_page(request, action_url=action_url, list_type=list_type)
    if not verify_key(key, wishlist.encryption_key_hash):
        return None, render_unlock_page(
            request,
            action_url=action_url,
            list_type=list_type,
            error=request.state.t.get("unlock_error_invalid", "Invalid encryption key."),
        )
    try:
        decrypt_wishlist(wishlist, key)
    except Exception:
        return None, render_unlock_page(
            request,
            action_url=action_url,
            list_type=list_type,
            error=request.state.t.get("unlock_error_invalid", "Invalid encryption key."),
        )
    return key, None
