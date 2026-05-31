import secrets
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Wishlist(Base):
    __tablename__ = "wishlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=generate_token
    )
    guest_token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=generate_token
    )
    parent_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow, onupdate=utcnow
    )
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deletion_extended: Mapped[bool] = mapped_column(default=False)
    show_buyers_to_guests: Mapped[bool] = mapped_column(default=False)

    items: Mapped[list["Item"]] = relationship(
        back_populates="wishlist", cascade="all, delete-orphan", order_by="Item.position"
    )

    @property
    def is_done(self) -> bool:
        return self.done_at is not None

    @property
    def scheduled_deletion(self) -> datetime:
        from datetime import timedelta

        from app.config import settings

        base = self.created_at
        if base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)
        days = settings.wishlist_max_age_days
        if self.deletion_extended:
            days += settings.wishlist_extension_days
        return base + timedelta(days=days)


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    wishlist_id: Mapped[int] = mapped_column(ForeignKey("wishlists.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    url2: Mapped[str | None] = mapped_column(String(500), nullable=True)
    url3: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    price_hint: Mapped[str | None] = mapped_column(String(100), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow, onupdate=utcnow
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    wishlist: Mapped["Wishlist"] = relationship(back_populates="items")
    reservations: Mapped[list["Reservation"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )

    @property
    def is_removed(self) -> bool:
        return self.removed_at is not None

    @property
    def active_reservations(self) -> list["Reservation"]:
        return [r for r in self.reservations if r.removed_at is None]


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    guest_name: Mapped[str] = mapped_column(String(255), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    item: Mapped["Item"] = relationship(back_populates="reservations")

    @property
    def is_removed(self) -> bool:
        return self.removed_at is not None


class SiteStats(Base):
    __tablename__ = "site_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    removed_wishlist_count: Mapped[int] = mapped_column(Integer, default=0)
    removed_item_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow, onupdate=utcnow
    )
