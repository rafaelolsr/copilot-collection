#!/usr/bin/env python3
"""Generate the repo banner + social preview images using PIL.

Outputs:
  assets/banner.png        — README banner (1600x400)
  assets/social-preview.png — GitHub social card (1280x640)

Run: python3 _generate_images.py
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).parent

# GitHub-ish dark palette (consistent across both images)
BG_DEEP = (13, 17, 23)         # GitHub dark BG
BG_PANEL = (22, 27, 34)        # slightly lighter panel
ACCENT_BLUE = (88, 166, 255)   # GitHub link blue
ACCENT_GREEN = (63, 185, 80)   # GitHub success green
ACCENT_PURPLE = (167, 130, 255) # Copilot brand-ish purple
TEXT_PRIMARY = (240, 246, 252)
TEXT_MUTED = (139, 148, 158)
BORDER = (48, 54, 61)


def _try_font(candidates: list[tuple[str, int]]) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try several font paths; fall back to default if none found."""
    for path, size in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    """Resolve to a system font that exists on macOS / Linux runners."""
    if mono:
        candidates = [
            ("/System/Library/Fonts/SFNSMono.ttf", size),
            ("/System/Library/Fonts/Menlo.ttc", size),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", size),
            ("/Library/Fonts/Courier New.ttf", size),
        ]
    elif bold:
        candidates = [
            ("/System/Library/Fonts/SFNS.ttf", size),
            ("/System/Library/Fonts/Helvetica.ttc", size),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size),
            ("/Library/Fonts/Arial Bold.ttf", size),
        ]
    else:
        candidates = [
            ("/System/Library/Fonts/SFNS.ttf", size),
            ("/System/Library/Fonts/Helvetica.ttc", size),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size),
            ("/Library/Fonts/Arial.ttf", size),
        ]
    return _try_font(candidates)


def _measure(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _rounded_rect(draw, xy, radius, fill=None, outline=None, width=1):
    """Compatibility wrapper — Pillow rounded_rectangle exists on 8.2+."""
    if hasattr(draw, "rounded_rectangle"):
        draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)
    else:
        draw.rectangle(xy, fill=fill, outline=outline, width=width)


# ---------- Banner (1600x400) ----------

def make_banner() -> None:
    W, H = 1600, 400
    img = Image.new("RGB", (W, H), BG_DEEP)
    draw = ImageDraw.Draw(img)

    # Subtle gradient strip on left
    for x in range(0, 8):
        draw.line([(x, 0), (x, H)], fill=ACCENT_PURPLE)

    # Title
    title_font = _font(72, bold=True)
    title = "copilot-collection"
    tw, th = _measure(draw, title, title_font)
    draw.text((80, 70), title, fill=TEXT_PRIMARY, font=title_font)

    # Tagline
    tag_font = _font(28)
    tagline = "Production-grade GitHub Copilot agents, skills, hooks, and workflows."
    draw.text((80, 165), tagline, fill=TEXT_MUTED, font=tag_font)

    # Stats row — three pill-style boxes
    pill_font = _font(20, bold=True)
    pill_font_small = _font(16)
    pills = [
        ("7", "Specialists",  ACCENT_BLUE),
        ("5", "Skills",       ACCENT_GREEN),
        ("105", "KB files",   ACCENT_PURPLE),
    ]

    px = 80
    py = 240
    pad = 30
    for value, label, color in pills:
        # measure
        vw, vh = _measure(draw, value, _font(48, bold=True))
        lw, lh = _measure(draw, label, pill_font_small)
        box_w = max(vw, lw) + pad * 2
        box_h = vh + lh + 30

        # box
        _rounded_rect(
            draw,
            (px, py, px + box_w, py + box_h),
            radius=14,
            fill=BG_PANEL,
            outline=BORDER,
            width=2,
        )

        # value
        draw.text(
            (px + (box_w - vw) // 2, py + 12),
            value,
            fill=color,
            font=_font(48, bold=True),
        )
        # label
        draw.text(
            (px + (box_w - lw) // 2, py + 12 + vh + 6),
            label,
            fill=TEXT_MUTED,
            font=pill_font_small,
        )
        px += box_w + 20

    # Right side: code-shaped block hinting at agent invocation
    code_font = _font(20, mono=True)
    code_lines = [
        "$ copilot --agent=ms-foundry-specialist \\",
        "    --prompt 'scaffold a Foundry agent'",
        "",
        "/simplify     — refactor changed code",
        "/ultrathink   — deep deliberation",
        "/code-review  — systematic 8-cat review",
    ]
    cx = 920
    cy = 80
    box_w = 640
    box_h = 240
    _rounded_rect(
        draw,
        (cx, cy, cx + box_w, cy + box_h),
        radius=14,
        fill=BG_PANEL,
        outline=BORDER,
        width=2,
    )
    # window dots (mac-style)
    for i, color in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        dx = cx + 20 + i * 22
        dy = cy + 20
        draw.ellipse((dx, dy, dx + 12, dy + 12), fill=color)

    # code lines
    line_y = cy + 56
    for line in code_lines:
        if line.startswith("$"):
            color = ACCENT_GREEN
        elif line.startswith("/"):
            # split into command and rest
            parts = line.split("—", 1)
            if len(parts) == 2:
                cmd, rest = parts
                draw.text((cx + 24, line_y), cmd, fill=ACCENT_BLUE, font=code_font)
                cmd_w, _ = _measure(draw, cmd, code_font)
                draw.text((cx + 24 + cmd_w, line_y), "— " + rest.strip(), fill=TEXT_MUTED, font=code_font)
                line_y += 30
                continue
            color = ACCENT_BLUE
        else:
            color = TEXT_PRIMARY
        draw.text((cx + 24, line_y), line, fill=color, font=code_font)
        line_y += 30

    out = HERE / "banner.png"
    img.save(out, optimize=True)
    print(f"Wrote {out} ({img.size})")


# ---------- Social preview (1280x640) ----------

def make_social_preview() -> None:
    W, H = 1280, 640
    img = Image.new("RGB", (W, H), BG_DEEP)
    draw = ImageDraw.Draw(img)

    # Diagonal gradient stripe in background (suggestion of activity)
    for i in range(0, 200, 4):
        alpha = 18  # subtle
        c = (
            min(255, ACCENT_PURPLE[0] // 6 + 13),
            min(255, ACCENT_PURPLE[1] // 6 + 17),
            min(255, ACCENT_PURPLE[2] // 6 + 23),
        )
        draw.line([(0, i * 3), (W, i * 3 - 200)], fill=c, width=1)

    # Title block (centered)
    title_font = _font(96, bold=True)
    title = "copilot-collection"
    tw, th = _measure(draw, title, title_font)
    draw.text(((W - tw) // 2, 100), title, fill=TEXT_PRIMARY, font=title_font)

    # Subtitle
    sub_font = _font(34)
    subtitle = "Curated GitHub Copilot agents, skills, and workflows"
    sw, sh = _measure(draw, subtitle, sub_font)
    draw.text(((W - sw) // 2, 220), subtitle, fill=TEXT_MUTED, font=sub_font)

    # Three columns of feature labels
    section_font = _font(26, bold=True)
    item_font = _font(22)
    cols = [
        ("AGENTS", ACCENT_BLUE, [
            "ms-foundry-specialist",
            "python-specialist",
            "microsoft-fabric-specialist",
            "powerbi-tmdl-specialist",
            "azure-devops-specialist",
            "observability-specialist",
            "eval-framework-specialist",
        ]),
        ("SKILLS", ACCENT_GREEN, [
            "/simplify",
            "/ultrathink",
            "/code-review",
            "/kb-revalidate",
            "/agentic-eval",
        ]),
        ("ALSO", ACCENT_PURPLE, [
            "Instructions (auto-applied)",
            "Hooks (sessionStart)",
            "Agentic workflows",
            "Cookbook recipes",
            "Plugin manifests",
            "90-day KB re-validation",
        ]),
    ]

    col_w = (W - 160) // 3
    cy_start = 320
    cx = 80
    item_step = 28                            # tighter line height
    for header, accent, items in cols:
        # header
        draw.text((cx, cy_start), header, fill=accent, font=section_font)
        # underline
        draw.line([(cx, cy_start + 38), (cx + 60, cy_start + 38)], fill=accent, width=3)
        # items
        ty = cy_start + 56
        for item in items:
            draw.text((cx, ty), "•  " + item, fill=TEXT_PRIMARY, font=item_font)
            ty += item_step
        cx += col_w

    # Footer line
    foot_font = _font(20)
    foot = "github.com/rafaelolsr/copilot-collection  ·  MIT"
    fw, fh = _measure(draw, foot, foot_font)
    draw.text(((W - fw) // 2, H - 50), foot, fill=TEXT_MUTED, font=foot_font)

    out = HERE / "social-preview.png"
    img.save(out, optimize=True)
    print(f"Wrote {out} ({img.size})")


if __name__ == "__main__":
    make_banner()
    make_social_preview()
