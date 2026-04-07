"""
Video Slide Renderer — creates 1920x1080 PNG slides for video scenes.

Uses Pillow to render themed slide images from scene data.
Applies the teacher's design theme colors.
"""
import logging
import os
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from src.lms_agents.tools.template_renderer import THEMES

log = logging.getLogger(__name__)

WIDTH, HEIGHT = 1920, 1080

# Try to load fonts, fall back to default
def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Get a font, trying system paths."""
    candidates = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def render_slide(scene: dict, theme: str = "modern_clean") -> str:
    """
    Render a single scene as a 1920x1080 PNG.
    Returns path to the generated image file.
    """
    t = THEMES.get(theme, THEMES["modern_clean"])
    bg_color = _hex_to_rgb(t["bg_tint"])
    primary = _hex_to_rgb(t["primary"])
    text_color = _hex_to_rgb(t["text"])
    muted = _hex_to_rgb(t["text_muted"])

    img = Image.new("RGB", (WIDTH, HEIGHT), bg_color)
    draw = ImageDraw.Draw(img)

    # Bottom accent bar
    draw.rectangle([(0, HEIGHT - 60), (WIDTH, HEIGHT)], fill=primary)
    draw.text((WIDTH // 2, HEIGHT - 35), "Lulia AI", fill=(255, 255, 255), font=_get_font(20), anchor="mm")

    slide_content = scene.get("slide_content", {})
    slide_type = slide_content.get("type", "title")

    if slide_type == "title":
        title = slide_content.get("title", scene.get("narration", "")[:40])
        subtitle = slide_content.get("subtitle", "")
        draw.text((WIDTH // 2, HEIGHT // 2 - 40), title, fill=text_color, font=_get_font(72, True), anchor="mm")
        if subtitle:
            draw.text((WIDTH // 2, HEIGHT // 2 + 40), subtitle, fill=muted, font=_get_font(36), anchor="mm")

    elif slide_type == "definition":
        term = slide_content.get("term", "")
        definition = slide_content.get("definition", "")
        example = slide_content.get("example", "")
        draw.text((WIDTH // 2, 200), term, fill=primary, font=_get_font(56, True), anchor="mm")
        # Definition box
        draw.rounded_rectangle([(200, 300), (WIDTH - 200, 520)], radius=20, fill=(255, 255, 255))
        draw.text((WIDTH // 2, 380), definition, fill=text_color, font=_get_font(32), anchor="mm")
        if example:
            draw.text((WIDTH // 2, 450), f"Example: {example}", fill=primary, font=_get_font(40, True), anchor="mm")

    elif slide_type == "example":
        title = slide_content.get("title", "Example")
        content = slide_content.get("content", "")
        draw.text((WIDTH // 2, 150), title, fill=primary, font=_get_font(48, True), anchor="mm")
        draw.rounded_rectangle([(200, 250), (WIDTH - 200, HEIGHT - 150)], radius=20, fill=(255, 255, 255))
        # Wrap long text
        y = 320
        for line in content.split("\n"):
            if y > HEIGHT - 180:
                break
            draw.text((WIDTH // 2, y), line[:80], fill=text_color, font=_get_font(28), anchor="mm")
            y += 45

    elif slide_type == "question":
        question = slide_content.get("question", "")
        draw.text((WIDTH // 2, 150), "Practice Problem", fill=primary, font=_get_font(40, True), anchor="mm")
        draw.rounded_rectangle([(200, 250), (WIDTH - 200, 600)], radius=20, fill=(255, 255, 255))
        draw.text((WIDTH // 2, 400), question[:100], fill=text_color, font=_get_font(36), anchor="mm")

    else:
        # Generic slide
        narration = scene.get("narration", "")[:120]
        draw.text((WIDTH // 2, HEIGHT // 2), narration, fill=text_color, font=_get_font(36), anchor="mm")

    # Scene number badge
    scene_num = scene.get("scene_number", "")
    if scene_num:
        draw.ellipse([(40, 40), (100, 100)], fill=primary)
        draw.text((70, 70), str(scene_num), fill=(255, 255, 255), font=_get_font(24, True), anchor="mm")

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    img.save(tmp.name, "PNG")
    tmp.close()
    return tmp.name
