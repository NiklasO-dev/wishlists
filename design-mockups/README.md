# Guest wishlist — four design directions

Static HTML mockups for the **guest** view (family & friends reserving gifts). Each file is self-contained: open in any browser (no server required).

| # | File | Concept | Best for |
|---|------|---------|----------|
| 1 | [01-comfort-classic.html](01-comfort-classic.html) | Warm paper tones, serif titles, numbered steps | Grandparents used to letters and printed lists |
| 2 | [02-clear-and-calm.html](02-clear-and-calm.html) | Soft blues, step strip, minimal chrome | Users who feel overwhelmed by busy sites |
| 3 | [03-festive-family.html](03-festive-family.html) | Celebration colors, gift cues, friendly badges | Birthdays and holidays; emotional warmth |
| 4 | [04-plain-and-bold.html](04-plain-and-bold.html) | Maximum contrast, huge controls, one column | Low vision, motor difficulties, or very little tech experience |

## Shared principles (all four)

- **Light mode by default** — avoids low-contrast dark themes for aging eyes.
- **Base text ≥ 18px** — body copy never below 1.125rem.
- **Single-column gift list** on all viewports — no 3-column grid on the guest page.
- **One primary action per card** — large “I’ll buy this!” button; shop links secondary.
- **Name field first** with plain-language label (“Your first name”).
- **Reserved state** shown with color + words, not color alone.
- **How-to** always visible or one obvious tap away — no hunting in a collapsed menu.

## How to preview

```bash
cd design-mockups
python3 -m http.server 8765
```

Then open `http://localhost:8765/01-comfort-classic.html` (and 02, 03, 04).

Or open each `.html` file directly from the file manager.

## Choosing a direction

You can mix elements (e.g. Festive colors + Plain & Bold typography). Implementation would extend `app/static/style.css` and optionally add a `data-guest-theme` attribute on the guest template only, leaving admin/home on Pico as today.
