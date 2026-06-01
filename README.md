# Wishlist App

A simple web app for children's wishlists. Parents create a list, add gift ideas, and share a link with family and friends. Guests can reserve items so nobody buys the same gift twice.

No user accounts are required — access works through secret links. All wishlist content is **encrypted in the database** with a per-list encryption key.

## Features

- **Create a wishlist** with a title and optional email (to receive admin and guest links)
- **Per-wishlist encryption** — titles, item details, and guest names are encrypted before storage (AES-256-GCM)
- **Encryption key** — auto-generated (UUID) or set by the parent at creation; included in share links by default
- **Two link types**
  - **Admin link** — manage the list (add/edit/delete items, see reservations, mark as done)
  - **Guest link** — view the list and reserve items
- **Guest reservations** with optional buyer names visible to other guests
- **Share page** with QR code and printable handout
- **Export / print** view for the parent
- **Automatic cleanup** of old wishlists (configurable retention period)
- **English and German** UI
- **Optional SMTP** to email links to the parent on creation
- **Site admin dashboard** (`/admin`) for aggregate stats and manual cleanup

## How to use

### For parents

1. Open the app and create a wishlist (optionally set a custom encryption key).
2. You land on the **admin page** — bookmark this link. It contains your admin token and, by default, the encryption key.
3. Add wishes (name, price hint, shop links, description).
4. Copy the **guest link** and send it to family and friends, or open **Share / QR Code** to print a handout.
5. On the admin page you can toggle whether links include the encryption key. If you share links **without** the key, recipients must enter the key on an unlock screen.
6. When the occasion is over, mark the list as **done** (the guest link stops working) or delete it entirely.

**Save your encryption key** if you plan to share links without the key in the URL. The key is not stored in the database and cannot be recovered from it.

### For guests

1. Open the guest link you received (from email, chat, or QR code).
2. If the link has no key, enter the encryption key you were given separately.
3. Enter your name once at the top.
4. Click **I'll buy this!** on any item you plan to purchase. You can undo a reservation within 60 seconds.

## Quick Start (Podman)

```bash
# Build the image
podman build -t wishlist-app .

# Run with a named volume for persistence
podman run -d \
  --name wishlist-app \
  -p 8000:8000 \
  -v wishlist_data:/data \
  -e APP_BASE_URL=https://wishlist.example.com \
  -e DATABASE_URL="sqlite+aiosqlite:////data/wishlist.db" \
  -e ADMIN_PASSWORD=your-secure-password \
  wishlist-app
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_BASE_URL` | `http://localhost:8000` | Public URL of the app (used in generated links and emails) |
| `DATABASE_URL` | `sqlite+aiosqlite:////data/wishlist.db` | Database connection string |
| `ADMIN_PASSWORD` | `change-this-password` | Password for site admin dashboard (`/admin`) |
| `SMTP_HOST` | *(empty)* | SMTP server hostname |
| `SMTP_PORT` | `587` | SMTP server port |
| `SMTP_USER` | *(empty)* | SMTP username |
| `SMTP_PASSWORD` | *(empty)* | SMTP password |
| `SMTP_FROM` | *(empty)* | From address for emails |
| `SMTP_TLS` | `true` | Use TLS for SMTP |
| `WISHLIST_MAX_AGE_DAYS` | `548` | Days until an active wishlist is deleted automatically |
| `DONE_WISHLIST_CLEANUP_DAYS` | `30` | Days until done wishlists are cleaned up |
| `WISHLIST_EXTENSION_DAYS` | `90` | Extra days when the parent extends retention once |

## Caddy Reverse Proxy

Protect the site admin route with basic auth in front of the app:

```
wishlist.example.com {
    handle /admin* {
        basicauth {
            admin <hashed-password>
        }
        reverse_proxy wishlist-app:8000
    }

    handle {
        reverse_proxy wishlist-app:8000
    }
}
```

Generate the password hash with `caddy hash-password`.

## Development

```bash
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Copy `.env.example` to `.env` and adjust settings for local use.

## Podman Compose

```bash
podman-compose up -d
```

For local testing:

```bash
podman-compose -f docker-compose.local.yml up --build
```

Clean rebuild:

```bash
podman-compose -f docker-compose.local.yml down && podman rmi localhost/wishlists_wishlist-app:latest 2>/dev/null; podman build --no-cache -t wishlists_wishlist-app . && podman-compose -f docker-compose.local.yml up -d
```

## Some minor Information

- I need two workspace files because in Kiro the terminal did not work on Fedora/Nobara/Bazzite using the user default terminal. So i use the basic bash terminal without any fuzz.

## License

MIT — see [LICENSE](LICENSE).
