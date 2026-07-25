"""Regenerate PWA icons + favicon with the Timelined red-on-dark theme.

Draws a bold red 'T' centered on the dark background. The 'T' uses a subtle
timeline-tick motif on the crossbar to hint at what the app is about,
without needing custom SVG design software.

Run: python scripts/gen_icons.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PUBLIC = Path(__file__).resolve().parent.parent / "web" / "public"
BG = (10, 10, 10, 255)          # #0a0a0a — matches manifest background_color
RED = (220, 38, 38, 255)        # #dc2626 — Tailwind red-600, matches theme_color
TICK = (239, 68, 68, 220)       # slightly lighter, ~red-500 with alpha


def _pick_font(size: int) -> ImageFont.FreeTypeFont:
    # Try a few common bold system fonts; fall back to default if none found.
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf",   # Segoe UI Bold
        "C:/Windows/Fonts/arialbd.ttf",    # Arial Bold
        "C:/Windows/Fonts/calibrib.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def _round_rect(draw: ImageDraw.ImageDraw, size: int) -> None:
    # Rounded-square background (matches the dark chip look of the app).
    r = int(size * 0.18)
    draw.rounded_rectangle([(0, 0), (size, size)], radius=r, fill=BG)


def _draw_t(draw: ImageDraw.ImageDraw, size: int) -> None:
    # Centered bold red T with a thin lighter tick row above the crossbar
    # to evoke a timeline scale.
    font = _pick_font(int(size * 0.68))
    text = "T"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (size - tw) // 2 - bbox[0]
    y = (size - th) // 2 - bbox[1] - int(size * 0.02)
    draw.text((x, y), text, fill=RED, font=font)

    # Timeline tick marks along the top crossbar for a subtle "timeline" hint.
    tick_y = int(size * 0.22)
    tick_len = int(size * 0.05)
    step = int(size * 0.09)
    start_x = int(size * 0.22)
    end_x = int(size * 0.78)
    for tx in range(start_x, end_x + 1, step):
        draw.line([(tx, tick_y), (tx, tick_y + tick_len)], fill=TICK, width=max(1, size // 128))


def render(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    _round_rect(draw, size)
    _draw_t(draw, size)
    return img


def main() -> None:
    PUBLIC.mkdir(parents=True, exist_ok=True)

    for size, name in [(192, "icon-192.png"), (512, "icon-512.png"), (180, "apple-touch-icon.png")]:
        img = render(size)
        img.save(PUBLIC / name, "PNG", optimize=True)
        print(f"wrote {name} ({size}x{size})")

    # Multi-resolution favicon.
    fav = render(64)
    fav.save(
        PUBLIC / "favicon.ico",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64)],
    )
    print("wrote favicon.ico")

    # OG social share image: wide, dark, big red brand mark + wordmark.
    og_w, og_h = 1200, 630
    og = Image.new("RGBA", (og_w, og_h), BG)
    d = ImageDraw.Draw(og)
    # Left-side red T tile.
    tile_size = 380
    tile_x = 80
    tile_y = (og_h - tile_size) // 2
    tile = render(tile_size)
    og.alpha_composite(tile, (tile_x, tile_y))
    # Wordmark and tagline on the right.
    title_font = _pick_font(96)
    tagline_font = _pick_font(36)
    d.text((tile_x + tile_size + 60, tile_y + 60), "Timelined", fill=(240, 240, 240, 255), font=title_font)
    d.text(
        (tile_x + tile_size + 60, tile_y + 180),
        "Indian news as interactive timelines",
        fill=(180, 180, 180, 255),
        font=tagline_font,
    )
    og.convert("RGB").save(PUBLIC / "og-default.png", "PNG", optimize=True)
    print("wrote og-default.png (1200x630)")


if __name__ == "__main__":
    main()
