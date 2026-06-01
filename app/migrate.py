import logging

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession
from sqlalchemy.orm import selectinload

from app.encryption import encrypt, encrypt_optional, generate_encryption_key, hash_key
from app.models import Item, Wishlist
from app.wishlist_crypto import encrypt_item_fields, encrypt_reservation_fields

logger = logging.getLogger(__name__)


async def _column_exists(conn: AsyncConnection, table: str, column: str) -> bool:
    result = await conn.execute(text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in result.fetchall())


async def run_migrations(conn: AsyncConnection) -> None:
    if not await _column_exists(conn, "wishlists", "encryption_key_hash"):
        await conn.execute(
            text("ALTER TABLE wishlists ADD COLUMN encryption_key_hash VARCHAR(64)")
        )
        logger.info("Added encryption_key_hash column to wishlists")

    if not await _column_exists(conn, "wishlists", "key_reveal_pending"):
        await conn.execute(
            text("ALTER TABLE wishlists ADD COLUMN key_reveal_pending BOOLEAN DEFAULT 0")
        )
        logger.info("Added key_reveal_pending column to wishlists")

    if not await _column_exists(conn, "wishlists", "key_reveal_wrapped"):
        await conn.execute(
            text("ALTER TABLE wishlists ADD COLUMN key_reveal_wrapped TEXT")
        )
        logger.info("Added key_reveal_wrapped column to wishlists")

    await _migrate_plaintext_wishlists(conn)


async def _migrate_plaintext_wishlists(conn: AsyncConnection) -> None:
    async with AsyncSession(conn, expire_on_commit=False) as session:
        result = await session.execute(
            select(Wishlist)
            .options(selectinload(Wishlist.items).selectinload(Item.reservations))
            .where(Wishlist.encryption_key_hash.is_(None))
        )
        wishlists = result.scalars().all()
        if not wishlists:
            return

        logger.info("Migrating %d wishlist(s) to encrypted storage", len(wishlists))
        for wishlist in wishlists:
            key = generate_encryption_key()
            wishlist.encryption_key_hash = hash_key(key)
            wishlist.key_reveal_pending = True
            wishlist.key_reveal_wrapped = encrypt(key, wishlist.admin_token)

            plain_title = wishlist.title
            plain_email = wishlist.parent_email
            wishlist.title = encrypt(plain_title, key)
            wishlist.parent_email = encrypt_optional(plain_email, key)

            for item in wishlist.items:
                encrypt_item_fields(
                    item,
                    key,
                    title=item.title,
                    description=item.description,
                    url=item.url,
                    url2=item.url2,
                    url3=item.url3,
                    price_hint=item.price_hint,
                )
                for reservation in item.reservations:
                    encrypt_reservation_fields(
                        reservation, key, guest_name=reservation.guest_name
                    )

        await session.commit()
        logger.info("Encryption migration complete")
