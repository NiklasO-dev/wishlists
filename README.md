# Wishlist App

A simple wishlist web app for sharing gift ideas with family and friends. No accounts needed — just secret links.

This project was developed with the help of AI (Kiro).

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
| `APP_BASE_URL` | `http://localhost:8000` | Public URL of the app |
| `DATABASE_URL` | `sqlite+aiosqlite:////data/wishlist.db` | Database connection string |
| `ADMIN_PASSWORD` | `change-this-password` | Password for site admin dashboard |
| `SMTP_HOST` | *(empty)* | SMTP server hostname |
| `SMTP_PORT` | `587` | SMTP server port |
| `SMTP_USER` | *(empty)* | SMTP username |
| `SMTP_PASSWORD` | *(empty)* | SMTP password |
| `SMTP_FROM` | *(empty)* | From address for emails |
| `SMTP_TLS` | `true` | Use TLS for SMTP |
| `WISHLIST_MAX_AGE_DAYS` | `180` | Days until automatic deletion |
| `DONE_WISHLIST_CLEANUP_DAYS` | `30` | Days until done wishlists are cleaned up |
| `WISHLIST_EXTENSION_DAYS` | `90` | Extra days when parent extends |

## Caddy Reverse Proxy

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

## Podman Compose

```bash
podman-compose up -d
```

for local testing

```bash
podman-compose -f docker-compose.local.yml up --build
```

Clean rebuild:

```bash
podman-compose -f docker-compose.local.yml down && podman rmi localhost/wishlists_wishlist-app:latest 2>/dev/null; podman build --no-cache -t wishlists_wishlist-app . && podman-compose -f docker-compose.local.yml up -d
```

## License

MIT — see [LICENSE](LICENSE).
