"""
Visual Renderer — converts structured visual data into inline SVG/HTML.

The Content Agent emits structured visual objects on questions instead of
bracketed text descriptions like "[Image: ten-frame with 5 dots]". This
module converts those objects into actual graphics that template renderers
can inline into worksheets, task cards, and other student-facing output.

A `visual` object on a question looks like:

    {
      "type": "ten_frame",
      "value": 5,
      "label": "Maya has 5 cookies"
    }

Each handler is responsible for one type. Unknown types fall through to a
labeled placeholder so the system never breaks if the LLM invents a type
we haven't implemented yet.

All output is self-contained inline SVG with no external dependencies.
Colors come from CSS custom properties set by template_renderer's theme
system (--t-primary, --t-text, --t-border) so visuals match the active
design theme automatically.

Visual types currently supported:
  K-2 math:    ten_frame, number_bond, counting_objects, base_ten_blocks
  3-5 math:    fraction_bar, fraction_circle, array, bar_model, area_model
  6-8 math:    number_line, coordinate_grid, equation_box
  9-12 math:   coordinate_grid (extended), function_table
  Science:     data_table, simple_diagram, labeled_diagram
  ELA:         letter_box, word_box, handwriting_lines, picture_choice
  Generic:     placeholder
"""
import html
import logging
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_visual(visual: Any) -> str:
    """
    Convert a structured visual dict into inline SVG/HTML.

    Returns an empty string if visual is None, empty, or malformed.
    Returns a labeled placeholder if the type is unknown.
    """
    if not visual or not isinstance(visual, dict):
        return ""

    vtype = visual.get("type", "").strip().lower()
    if not vtype:
        return ""

    handler = VISUAL_HANDLERS.get(vtype, _render_placeholder)
    try:
        body = handler(visual)
    except Exception as e:
        log.warning(f"[VisualRenderer] Failed to render {vtype}: {e}")
        body = _render_placeholder({"type": vtype, "label": f"({vtype})"})

    label = visual.get("label") or ""
    label_html = (
        f'<div class="visual-label">{html.escape(label)}</div>' if label else ""
    )
    return f'<div class="question-visual">{body}{label_html}</div>'


# ---------------------------------------------------------------------------
# CSS — appended once to template <style> via get_visual_css()
# ---------------------------------------------------------------------------

VISUAL_CSS = """
.question-visual {
  margin: 8px 0 12px 28px;
  padding: 8px 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}
.question-visual svg {
  display: block;
  max-width: 100%;
  height: auto;
}
.visual-label {
  font-size: 0.85em;
  color: var(--t-text-secondary, #78716C);
  font-style: italic;
}
.visual-placeholder {
  border: 2px dashed var(--t-border, #E7E5E4);
  background: var(--t-bg-tint, #FEF9F2);
  padding: 12px 16px;
  border-radius: 8px;
  color: var(--t-text-secondary, #78716C);
  font-size: 0.9em;
  font-style: italic;
}
.visual-placeholder strong {
  display: block;
  font-style: normal;
  color: var(--t-text, #1C1917);
  margin-bottom: 4px;
}
.hotspot-diagram img { border-radius: 8px; border: 1px solid var(--t-border, #E7E5E4); }
.hotspot-legend {
  list-style: none; padding: 0; margin: 10px 0 0 0;
  display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 4px 12px;
}
.hotspot-legend li { font-size: 0.85em; color: var(--t-text, #1C1917); display: flex; align-items: center; gap: 6px; }
.hotspot-legend .legend-num {
  display: inline-flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border-radius: 50%;
  background: #F97316; color: white; font-weight: 700; font-size: 11px;
}
"""


def get_visual_css() -> str:
    """Return the CSS for visuals — embed inside a <style> tag."""
    return VISUAL_CSS


# ---------------------------------------------------------------------------
# Color helpers — use CSS variables so themes apply automatically
# ---------------------------------------------------------------------------

PRIMARY = "var(--t-primary, #F97316)"
PRIMARY_LIGHT = "var(--t-primary-light, #FB923C)"
PRIMARY_LIGHTER = "var(--t-primary-lighter, #FDBA74)"
PRIMARY_LIGHTEST = "var(--t-primary-lightest, #FED7AA)"
TEXT = "var(--t-text, #1C1917)"
TEXT_SECONDARY = "var(--t-text-secondary, #78716C)"
BORDER = "var(--t-border, #E7E5E4)"
BG = "var(--t-bg, #FFFFFF)"
BG_TINT = "var(--t-bg-tint, #FEF9F2)"


# ---------------------------------------------------------------------------
# K-2 Math visuals
# ---------------------------------------------------------------------------

def _render_ten_frame(v: dict) -> str:
    """
    Ten-frame: 2x5 grid with N filled cells.
    Required: value (int 0-10).
    """
    value = max(0, min(10, int(v.get("value", 0))))
    cell = 36
    margin = 6
    width = cell * 5 + margin * 2
    height = cell * 2 + margin * 2

    cells = []
    for i in range(10):
        row = i // 5
        col = i % 5
        x = margin + col * cell
        y = margin + row * cell
        filled = i < value
        fill = PRIMARY if filled else BG
        circle = ""
        if filled:
            circle = (
                f'<circle cx="{x + cell // 2}" cy="{y + cell // 2}" '
                f'r="{cell // 2 - 6}" fill="{BG}" stroke="none"/>'
            )
        cells.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
            f'fill="{fill}" stroke="{TEXT}" stroke-width="2"/>{circle}'
        )

    return (
        f'<svg width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
        + "".join(cells)
        + "</svg>"
    )


def _render_number_bond(v: dict) -> str:
    """
    Number bond: whole circle with two part circles below, connected.
    Required: whole (int). Optional: part1, part2 (use "?" if missing).
    """
    whole = v.get("whole", "?")
    part1 = v.get("part1", "?")
    part2 = v.get("part2", "?")
    r = 28
    width = 200
    height = 130

    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
  <line x1="100" y1="50" x2="55" y2="100" stroke="{TEXT}" stroke-width="2"/>
  <line x1="100" y1="50" x2="145" y2="100" stroke="{TEXT}" stroke-width="2"/>
  <circle cx="100" cy="30" r="{r}" fill="{PRIMARY_LIGHTEST}" stroke="{TEXT}" stroke-width="2"/>
  <text x="100" y="38" text-anchor="middle" font-size="22" font-weight="bold" fill="{TEXT}">{html.escape(str(whole))}</text>
  <circle cx="55" cy="100" r="{r}" fill="{BG}" stroke="{TEXT}" stroke-width="2"/>
  <text x="55" y="108" text-anchor="middle" font-size="22" font-weight="bold" fill="{TEXT}">{html.escape(str(part1))}</text>
  <circle cx="145" cy="100" r="{r}" fill="{BG}" stroke="{TEXT}" stroke-width="2"/>
  <text x="145" y="108" text-anchor="middle" font-size="22" font-weight="bold" fill="{TEXT}">{html.escape(str(part2))}</text>
</svg>"""


def _render_counting_objects(v: dict) -> str:
    """
    Row of N simple icons. K-1 counting practice.
    Required: count (int). Optional: icon (circle|square|star), label.
    """
    count = max(0, min(20, int(v.get("count", 0))))
    icon = v.get("icon", "circle")
    size = 28
    gap = 8
    margin = 6
    cols = min(10, count) if count > 0 else 1
    rows = max(1, (count + cols - 1) // cols) if count > 0 else 1
    width = margin * 2 + cols * (size + gap) - gap
    height = margin * 2 + rows * (size + gap) - gap

    objs = []
    for i in range(count):
        row = i // cols
        col = i % cols
        x = margin + col * (size + gap)
        y = margin + row * (size + gap)
        cx = x + size // 2
        cy = y + size // 2
        if icon == "square":
            objs.append(
                f'<rect x="{x}" y="{y}" width="{size}" height="{size}" '
                f'rx="4" fill="{PRIMARY_LIGHTER}" stroke="{TEXT}" stroke-width="2"/>'
            )
        elif icon == "star":
            # simple 5-pointed star centered at (cx, cy)
            r1 = size // 2
            r2 = r1 // 2
            points = []
            import math
            for k in range(10):
                angle = -math.pi / 2 + k * math.pi / 5
                rad = r1 if k % 2 == 0 else r2
                px = cx + rad * math.cos(angle)
                py = cy + rad * math.sin(angle)
                points.append(f"{px:.1f},{py:.1f}")
            objs.append(
                f'<polygon points="{" ".join(points)}" fill="{PRIMARY}" stroke="{TEXT}" stroke-width="1"/>'
            )
        else:  # circle default
            objs.append(
                f'<circle cx="{cx}" cy="{cy}" r="{size // 2 - 2}" '
                f'fill="{PRIMARY_LIGHTER}" stroke="{TEXT}" stroke-width="2"/>'
            )

    return (
        f'<svg width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
        + "".join(objs)
        + "</svg>"
    )


def _render_base_ten_blocks(v: dict) -> str:
    """
    Base-10 blocks: hundreds (10x10), tens (1x10), ones (1x1).
    Optional: hundreds, tens, ones (ints).
    """
    hundreds = max(0, min(9, int(v.get("hundreds", 0))))
    tens = max(0, min(20, int(v.get("tens", 0))))
    ones = max(0, min(20, int(v.get("ones", 0))))
    unit = 10
    gap_group = 16
    margin = 6

    pieces = []
    cursor_x = margin

    # Hundreds: 10x10 grid blocks
    for _ in range(hundreds):
        for r in range(10):
            for c in range(10):
                pieces.append(
                    f'<rect x="{cursor_x + c * unit}" y="{margin + r * unit}" '
                    f'width="{unit}" height="{unit}" fill="{PRIMARY_LIGHTER}" '
                    f'stroke="{TEXT}" stroke-width="0.5"/>'
                )
        # outer border
        pieces.append(
            f'<rect x="{cursor_x}" y="{margin}" width="{unit * 10}" height="{unit * 10}" '
            f'fill="none" stroke="{TEXT}" stroke-width="2"/>'
        )
        cursor_x += unit * 10 + gap_group

    # Tens: 1x10 columns
    for _ in range(tens):
        for r in range(10):
            pieces.append(
                f'<rect x="{cursor_x}" y="{margin + r * unit}" '
                f'width="{unit}" height="{unit}" fill="{PRIMARY_LIGHT}" '
                f'stroke="{TEXT}" stroke-width="0.5"/>'
            )
        pieces.append(
            f'<rect x="{cursor_x}" y="{margin}" width="{unit}" height="{unit * 10}" '
            f'fill="none" stroke="{TEXT}" stroke-width="2"/>'
        )
        cursor_x += unit + 4

    if tens:
        cursor_x += gap_group - 4

    # Ones: 1x1 squares stacked in rows of 5
    for i in range(ones):
        row = i // 5
        col = i % 5
        pieces.append(
            f'<rect x="{cursor_x + col * (unit + 2)}" y="{margin + row * (unit + 2)}" '
            f'width="{unit}" height="{unit}" fill="{PRIMARY}" stroke="{TEXT}" stroke-width="2"/>'
        )

    height = margin * 2 + unit * 10
    width = max(120, cursor_x + 5 * (unit + 2) + margin)
    return (
        f'<svg width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
        + "".join(pieces)
        + "</svg>"
    )


# ---------------------------------------------------------------------------
# 3-5 Math visuals
# ---------------------------------------------------------------------------

def _render_fraction_bar(v: dict) -> str:
    """
    Fraction bar: rectangle divided into N parts with K shaded.
    Required: denominator (int), numerator (int).
    """
    denom = max(1, min(20, int(v.get("denominator", 1))))
    num = max(0, min(denom, int(v.get("numerator", 0))))
    cell_w = 36
    height = 50
    margin = 6
    width = margin * 2 + cell_w * denom

    cells = []
    for i in range(denom):
        x = margin + i * cell_w
        fill = PRIMARY if i < num else BG
        cells.append(
            f'<rect x="{x}" y="{margin}" width="{cell_w}" height="{height - margin}" '
            f'fill="{fill}" stroke="{TEXT}" stroke-width="2"/>'
        )

    return (
        f'<svg width="{width}" height="{height + margin}" '
        f'viewBox="0 0 {width} {height + margin}" xmlns="http://www.w3.org/2000/svg">'
        + "".join(cells)
        + "</svg>"
    )


def _render_fraction_circle(v: dict) -> str:
    """
    Fraction circle: pie chart with N slices and K shaded.
    Required: denominator (int), numerator (int).
    """
    import math
    denom = max(1, min(16, int(v.get("denominator", 1))))
    num = max(0, min(denom, int(v.get("numerator", 0))))
    r = 50
    cx, cy = 60, 60
    width = height = 120

    slices = []
    for i in range(denom):
        a1 = -math.pi / 2 + 2 * math.pi * i / denom
        a2 = -math.pi / 2 + 2 * math.pi * (i + 1) / denom
        x1 = cx + r * math.cos(a1)
        y1 = cy + r * math.sin(a1)
        x2 = cx + r * math.cos(a2)
        y2 = cy + r * math.sin(a2)
        large = 1 if (a2 - a1) > math.pi else 0
        path = f"M{cx},{cy} L{x1:.1f},{y1:.1f} A{r},{r} 0 {large},1 {x2:.1f},{y2:.1f} Z"
        fill = PRIMARY if i < num else BG
        slices.append(f'<path d="{path}" fill="{fill}" stroke="{TEXT}" stroke-width="2"/>')

    return (
        f'<svg width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
        + "".join(slices)
        + "</svg>"
    )


def _render_array(v: dict) -> str:
    """
    Array of dots for multiplication: rows × cols.
    Required: rows (int), cols (int).
    """
    rows = max(1, min(12, int(v.get("rows", 1))))
    cols = max(1, min(12, int(v.get("cols", 1))))
    spacing = 24
    r = 8
    margin = 12
    width = margin * 2 + (cols - 1) * spacing
    height = margin * 2 + (rows - 1) * spacing

    dots = []
    for i in range(rows):
        for j in range(cols):
            cx = margin + j * spacing
            cy = margin + i * spacing
            dots.append(
                f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{PRIMARY}" '
                f'stroke="{TEXT}" stroke-width="1.5"/>'
            )

    return (
        f'<svg width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
        + "".join(dots)
        + "</svg>"
    )


def _render_bar_model(v: dict) -> str:
    """
    Tape diagram / bar model for word problems.
    Required: parts (list of {label, size?}). Optional: total (str).
    """
    parts = v.get("parts") or []
    if not parts:
        return _render_placeholder({"type": "bar_model", "label": "(no parts)"})

    total_label = v.get("total")
    total_size = sum(int(p.get("size", 1)) for p in parts) or len(parts)
    width = 360
    bar_height = 44
    margin = 6
    height = bar_height + margin * 2 + (24 if total_label else 0)

    segs = []
    cursor = margin
    palette = [PRIMARY, PRIMARY_LIGHT, PRIMARY_LIGHTER, PRIMARY_LIGHTEST]
    for idx, p in enumerate(parts):
        size = int(p.get("size", 1))
        seg_w = (width - margin * 2) * size / total_size
        label = str(p.get("label", ""))
        color = palette[idx % len(palette)]
        segs.append(
            f'<rect x="{cursor:.1f}" y="{margin}" width="{seg_w:.1f}" height="{bar_height}" '
            f'fill="{color}" stroke="{TEXT}" stroke-width="2"/>'
        )
        text_x = cursor + seg_w / 2
        text_y = margin + bar_height / 2 + 5
        segs.append(
            f'<text x="{text_x:.1f}" y="{text_y:.1f}" text-anchor="middle" '
            f'font-size="14" font-weight="600" fill="{TEXT}">{html.escape(label)}</text>'
        )
        cursor += seg_w

    total_html = ""
    if total_label:
        total_html = (
            f'<text x="{width // 2}" y="{margin + bar_height + 18}" text-anchor="middle" '
            f'font-size="13" fill="{TEXT_SECONDARY}">Total: {html.escape(str(total_label))}</text>'
        )

    return (
        f'<svg width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
        + "".join(segs)
        + total_html
        + "</svg>"
    )


def _render_area_model(v: dict) -> str:
    """
    Area model for multiplication. e.g. (20 + 3) × (10 + 4).
    Required: row_parts (list[int]), col_parts (list[int]).
    """
    row_parts = v.get("row_parts") or []
    col_parts = v.get("col_parts") or []
    if not row_parts or not col_parts:
        return _render_placeholder({"type": "area_model", "label": "(missing parts)"})

    cell_max = 70
    cell_min = 30
    total_rows = sum(row_parts)
    total_cols = sum(col_parts)
    label_pad = 36
    grid_w = 280
    grid_h = 200

    width = grid_w + label_pad
    height = grid_h + label_pad

    pieces = []
    # Column labels
    cursor_x = label_pad
    for cp in col_parts:
        cell_w = grid_w * cp / total_cols
        pieces.append(
            f'<text x="{cursor_x + cell_w / 2:.1f}" y="22" text-anchor="middle" '
            f'font-size="14" font-weight="600" fill="{TEXT}">{cp}</text>'
        )
        cursor_x += cell_w

    # Row labels and grid cells
    cursor_y = label_pad
    for rp in row_parts:
        cell_h = grid_h * rp / total_rows
        pieces.append(
            f'<text x="{label_pad - 8}" y="{cursor_y + cell_h / 2 + 5:.1f}" text-anchor="end" '
            f'font-size="14" font-weight="600" fill="{TEXT}">{rp}</text>'
        )
        cursor_x = label_pad
        for cp in col_parts:
            cell_w = grid_w * cp / total_cols
            product = rp * cp
            pieces.append(
                f'<rect x="{cursor_x:.1f}" y="{cursor_y:.1f}" '
                f'width="{cell_w:.1f}" height="{cell_h:.1f}" '
                f'fill="{PRIMARY_LIGHTEST}" stroke="{TEXT}" stroke-width="2"/>'
            )
            pieces.append(
                f'<text x="{cursor_x + cell_w / 2:.1f}" y="{cursor_y + cell_h / 2 + 5:.1f}" '
                f'text-anchor="middle" font-size="14" fill="{TEXT}">{product}</text>'
            )
            cursor_x += cell_w
        cursor_y += cell_h

    return (
        f'<svg width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
        + "".join(pieces)
        + "</svg>"
    )


# ---------------------------------------------------------------------------
# 6-12 Math visuals
# ---------------------------------------------------------------------------

def _render_number_line(v: dict) -> str:
    """
    Number line with marks, optional highlights and arrows.
    Required: min (number), max (number), interval (number).
    Optional: highlights (list of numbers), label (str), show_labels (bool).
    """
    nmin = float(v.get("min", 0))
    nmax = float(v.get("max", 10))
    interval = float(v.get("interval", 1))
    highlights = v.get("highlights") or []
    show_labels = v.get("show_labels", True)

    if nmax <= nmin or interval <= 0:
        return _render_placeholder({"type": "number_line", "label": "(invalid range)"})

    width = 460
    height = 70
    margin_x = 30
    line_y = 40
    span = nmax - nmin
    line_w = width - margin_x * 2

    def x_for(n: float) -> float:
        return margin_x + (n - nmin) / span * line_w

    pieces = [
        f'<line x1="{margin_x}" y1="{line_y}" x2="{width - margin_x}" y2="{line_y}" '
        f'stroke="{TEXT}" stroke-width="2"/>',
        # Arrows
        f'<polygon points="{margin_x - 8},{line_y} {margin_x},{line_y - 6} {margin_x},{line_y + 6}" fill="{TEXT}"/>',
        f'<polygon points="{width - margin_x + 8},{line_y} {width - margin_x},{line_y - 6} {width - margin_x},{line_y + 6}" fill="{TEXT}"/>',
    ]

    # Tick marks
    n = nmin
    while n <= nmax + 1e-9:
        x = x_for(n)
        pieces.append(
            f'<line x1="{x:.1f}" y1="{line_y - 6}" x2="{x:.1f}" y2="{line_y + 6}" '
            f'stroke="{TEXT}" stroke-width="2"/>'
        )
        if show_labels:
            label = str(int(n)) if n == int(n) else f"{n:g}"
            pieces.append(
                f'<text x="{x:.1f}" y="{line_y + 22}" text-anchor="middle" '
                f'font-size="12" fill="{TEXT}">{label}</text>'
            )
        n += interval

    # Highlights
    for h in highlights:
        try:
            hv = float(h)
        except (TypeError, ValueError):
            continue
        x = x_for(hv)
        pieces.append(
            f'<circle cx="{x:.1f}" cy="{line_y}" r="7" '
            f'fill="{PRIMARY}" stroke="{TEXT}" stroke-width="2"/>'
        )

    return (
        f'<svg width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
        + "".join(pieces)
        + "</svg>"
    )


def _render_coordinate_grid(v: dict) -> str:
    """
    Coordinate grid with optional points and lines.
    Optional: x_min, x_max, y_min, y_max (defaults -10..10),
              points (list of [x, y] or {x, y, label}),
              lines (list of {from: [x,y], to: [x,y]}).
    """
    x_min = int(v.get("x_min", -10))
    x_max = int(v.get("x_max", 10))
    y_min = int(v.get("y_min", -10))
    y_max = int(v.get("y_max", 10))
    points = v.get("points") or []
    lines = v.get("lines") or []

    if x_max <= x_min or y_max <= y_min:
        return _render_placeholder({"type": "coordinate_grid", "label": "(bad range)"})

    width = 280
    height = 280
    margin = 18
    plot_w = width - margin * 2
    plot_h = height - margin * 2

    def to_px(px: float, py: float) -> tuple[float, float]:
        sx = margin + (px - x_min) / (x_max - x_min) * plot_w
        sy = margin + (1 - (py - y_min) / (y_max - y_min)) * plot_h
        return sx, sy

    pieces = []
    # Light grid lines
    x = x_min
    while x <= x_max:
        sx, _ = to_px(x, 0)
        pieces.append(
            f'<line x1="{sx:.1f}" y1="{margin}" x2="{sx:.1f}" y2="{height - margin}" '
            f'stroke="{BORDER}" stroke-width="1"/>'
        )
        x += 1
    y = y_min
    while y <= y_max:
        _, sy = to_px(0, y)
        pieces.append(
            f'<line x1="{margin}" y1="{sy:.1f}" x2="{width - margin}" y2="{sy:.1f}" '
            f'stroke="{BORDER}" stroke-width="1"/>'
        )
        y += 1

    # Axes
    if x_min <= 0 <= x_max:
        zero_x, _ = to_px(0, 0)
        pieces.append(
            f'<line x1="{zero_x:.1f}" y1="{margin}" x2="{zero_x:.1f}" y2="{height - margin}" '
            f'stroke="{TEXT}" stroke-width="2"/>'
        )
    if y_min <= 0 <= y_max:
        _, zero_y = to_px(0, 0)
        pieces.append(
            f'<line x1="{margin}" y1="{zero_y:.1f}" x2="{width - margin}" y2="{zero_y:.1f}" '
            f'stroke="{TEXT}" stroke-width="2"/>'
        )

    # Lines
    for line in lines:
        try:
            f_pt = line.get("from")
            t_pt = line.get("to")
            x1, y1 = to_px(float(f_pt[0]), float(f_pt[1]))
            x2, y2 = to_px(float(t_pt[0]), float(t_pt[1]))
            pieces.append(
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="{PRIMARY}" stroke-width="2.5"/>'
            )
        except Exception:
            continue

    # Points
    for pt in points:
        try:
            if isinstance(pt, dict):
                px = float(pt.get("x", 0))
                py = float(pt.get("y", 0))
                label = pt.get("label", "")
            else:
                px = float(pt[0])
                py = float(pt[1])
                label = ""
            sx, sy = to_px(px, py)
            pieces.append(
                f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="5" '
                f'fill="{PRIMARY}" stroke="{TEXT}" stroke-width="1.5"/>'
            )
            if label:
                pieces.append(
                    f'<text x="{sx + 8:.1f}" y="{sy - 8:.1f}" font-size="12" '
                    f'fill="{TEXT}">{html.escape(str(label))}</text>'
                )
        except Exception:
            continue

    return (
        f'<svg width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
        + "".join(pieces)
        + "</svg>"
    )


def _render_equation_box(v: dict) -> str:
    """
    Vertically stacked equation (K-2 / 3-5 math).
    Required: top (str), bottom (str), operator ('+' or '-' or '×' or '÷').
    """
    top = str(v.get("top", ""))
    bottom = str(v.get("bottom", ""))
    op = str(v.get("operator", "+"))
    width = 130
    height = 130

    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
  <text x="100" y="42" text-anchor="end" font-size="36" font-family="monospace" font-weight="600" fill="{TEXT}">{html.escape(top)}</text>
  <text x="40" y="84" text-anchor="middle" font-size="36" font-family="monospace" fill="{TEXT}">{html.escape(op)}</text>
  <text x="100" y="84" text-anchor="end" font-size="36" font-family="monospace" font-weight="600" fill="{TEXT}">{html.escape(bottom)}</text>
  <line x1="20" y1="98" x2="115" y2="98" stroke="{TEXT}" stroke-width="3"/>
</svg>"""


def _render_function_table(v: dict) -> str:
    """
    Function input/output table for 6-12 math.
    Required: rows (list of {x, y} or [x, y]).
    Optional: x_label, y_label.
    """
    rows = v.get("rows") or []
    if not rows:
        return _render_placeholder({"type": "function_table", "label": "(no rows)"})
    x_label = v.get("x_label", "x")
    y_label = v.get("y_label", "y")

    cells = ['<thead><tr>',
             f'<th>{html.escape(x_label)}</th>',
             f'<th>{html.escape(y_label)}</th>',
             '</tr></thead><tbody>']
    for r in rows:
        if isinstance(r, dict):
            x = r.get("x", "")
            y = r.get("y", "")
        else:
            x = r[0] if len(r) > 0 else ""
            y = r[1] if len(r) > 1 else ""
        cells.append(
            f'<tr><td>{html.escape(str(x))}</td><td>{html.escape(str(y))}</td></tr>'
        )
    cells.append("</tbody>")

    return (
        f'<table class="visual-table" style="border-collapse:collapse;font-size:14px;">'
        + "".join(cells)
        + "</table>"
        + "<style>.visual-table th,.visual-table td{border:2px solid "
        + TEXT
        + ";padding:6px 14px;text-align:center;}"
        + ".visual-table th{background:"
        + PRIMARY_LIGHTEST
        + ";}</style>"
    )


# ---------------------------------------------------------------------------
# Science visuals
# ---------------------------------------------------------------------------

def _render_data_table(v: dict) -> str:
    """
    Generic data table for science worksheets.
    Required: headers (list of str), rows (list of lists or list of dicts).
    """
    headers = v.get("headers") or []
    rows = v.get("rows") or []
    if not headers:
        return _render_placeholder({"type": "data_table", "label": "(no headers)"})

    parts = ['<table class="visual-table" style="border-collapse:collapse;font-size:14px;">',
             "<thead><tr>"]
    for h in headers:
        parts.append(f'<th>{html.escape(str(h))}</th>')
    parts.append("</tr></thead><tbody>")

    for r in rows:
        parts.append("<tr>")
        if isinstance(r, dict):
            for h in headers:
                parts.append(f'<td>{html.escape(str(r.get(h, "")))}</td>')
        else:
            for cell in r:
                parts.append(f'<td>{html.escape(str(cell))}</td>')
            # pad if short
            for _ in range(len(headers) - len(r)):
                parts.append("<td></td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")

    return (
        "".join(parts)
        + "<style>.visual-table th,.visual-table td{border:2px solid "
        + TEXT
        + ";padding:6px 12px;text-align:center;}"
        + ".visual-table th{background:"
        + PRIMARY_LIGHTEST
        + ";}</style>"
    )


def _render_labeled_diagram(v: dict) -> str:
    """
    Generic labeled-diagram fallback when the LLM identifies a science
    diagram but we don't have a specific renderer (cell, plant, body part).
    Renders an outlined box with the diagram description and labeled callouts.
    Required: subject (str). Optional: labels (list of str).
    """
    subject = v.get("subject", "diagram")
    labels = v.get("labels") or []
    label_html = "".join(
        f'<li style="margin:2px 0;">{html.escape(str(l))}</li>' for l in labels
    )
    label_block = (
        f'<ul style="margin:6px 0 0 18px;font-size:0.9em;color:{TEXT_SECONDARY};">{label_html}</ul>'
        if labels
        else ""
    )
    return (
        f'<div class="visual-placeholder">'
        f'<strong>Diagram: {html.escape(str(subject))}</strong>'
        f'<div>Teacher: insert printed or projected diagram here.</div>'
        f"{label_block}"
        f'</div>'
    )


# ---------------------------------------------------------------------------
# ELA visuals
# ---------------------------------------------------------------------------

def _render_letter_box(v: dict) -> str:
    """
    Large letter box for K-2 phonics.
    Required: letter (str). Optional: case ('upper' | 'lower' | 'both').
    """
    letter = str(v.get("letter", "?"))
    case = v.get("case", "both")
    if case == "upper":
        display = letter.upper()
    elif case == "lower":
        display = letter.lower()
    else:
        display = f"{letter.upper()} {letter.lower()}"
    return (
        f'<svg width="120" height="80" viewBox="0 0 120 80" xmlns="http://www.w3.org/2000/svg">'
        f'<rect x="2" y="2" width="116" height="76" rx="8" fill="{PRIMARY_LIGHTEST}" '
        f'stroke="{TEXT}" stroke-width="2"/>'
        f'<text x="60" y="58" text-anchor="middle" font-size="48" font-weight="bold" '
        f'fill="{TEXT}" font-family="serif">{html.escape(display)}</text>'
        f'</svg>'
    )


def _render_word_box(v: dict) -> str:
    """
    Word box for sight word practice or vocabulary.
    Required: word (str).
    """
    word = str(v.get("word", "?"))
    width = max(80, len(word) * 18 + 20)
    return (
        f'<svg width="{width}" height="50" viewBox="0 0 {width} 50" xmlns="http://www.w3.org/2000/svg">'
        f'<rect x="2" y="2" width="{width - 4}" height="46" rx="6" fill="{BG}" '
        f'stroke="{TEXT}" stroke-width="2"/>'
        f'<text x="{width // 2}" y="33" text-anchor="middle" font-size="22" '
        f'font-weight="600" fill="{TEXT}">{html.escape(word)}</text>'
        f'</svg>'
    )


def _render_handwriting_lines(v: dict) -> str:
    """
    3-line handwriting paper (K-2 writing).
    Required: lines (int, default 2).
    """
    lines = max(1, min(8, int(v.get("lines", 2))))
    line_h = 38
    margin = 6
    width = 460
    height = margin * 2 + lines * (line_h + 8)

    pieces = []
    cursor_y = margin
    for _ in range(lines):
        # top solid
        pieces.append(
            f'<line x1="{margin}" y1="{cursor_y}" x2="{width - margin}" y2="{cursor_y}" '
            f'stroke="{TEXT}" stroke-width="1.5"/>'
        )
        # mid dashed
        pieces.append(
            f'<line x1="{margin}" y1="{cursor_y + line_h // 2}" x2="{width - margin}" '
            f'y2="{cursor_y + line_h // 2}" stroke="{TEXT_SECONDARY}" '
            f'stroke-width="1" stroke-dasharray="4,4"/>'
        )
        # baseline solid
        pieces.append(
            f'<line x1="{margin}" y1="{cursor_y + line_h}" x2="{width - margin}" '
            f'y2="{cursor_y + line_h}" stroke="{TEXT}" stroke-width="1.5"/>'
        )
        cursor_y += line_h + 8

    return (
        f'<svg width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
        + "".join(pieces)
        + "</svg>"
    )


def _render_picture_choice(v: dict) -> str:
    """
    Row of placeholder picture boxes for circle-the-picture activities.
    Required: count (int) OR options (list of str labels).
    """
    options = v.get("options")
    if options:
        labels = [str(o) for o in options]
    else:
        count = max(1, min(6, int(v.get("count", 3))))
        labels = [f"({chr(65 + i)})" for i in range(count)]

    box_w = 80
    gap = 12
    margin = 6
    width = margin * 2 + len(labels) * (box_w + gap) - gap
    height = 100

    pieces = []
    for i, lbl in enumerate(labels):
        x = margin + i * (box_w + gap)
        pieces.append(
            f'<rect x="{x}" y="{margin}" width="{box_w}" height="80" rx="8" '
            f'fill="{BG}" stroke="{TEXT}" stroke-width="2"/>'
        )
        pieces.append(
            f'<text x="{x + box_w // 2}" y="50" text-anchor="middle" '
            f'font-size="14" fill="{TEXT_SECONDARY}">picture</text>'
        )
        pieces.append(
            f'<text x="{x + box_w // 2}" y="74" text-anchor="middle" '
            f'font-size="14" font-weight="600" fill="{TEXT}">{html.escape(lbl)}</text>'
        )

    return (
        f'<svg width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
        + "".join(pieces)
        + "</svg>"
    )


# ---------------------------------------------------------------------------
# Generic placeholder
# ---------------------------------------------------------------------------

def _render_placeholder(v: dict) -> str:
    """
    Fallback for unknown visual types. Renders a styled box with the
    type name and any description so the teacher knows what was intended.
    """
    vtype = v.get("type", "image")
    label = v.get("label") or v.get("description") or v.get("subject") or ""
    label_safe = html.escape(str(label)) if label else ""
    return (
        f'<div class="visual-placeholder">'
        f'<strong>{html.escape(str(vtype))}</strong>'
        + (f'<div>{label_safe}</div>' if label_safe else "")
        + "</div>"
    )


# ---------------------------------------------------------------------------
# Type registry
# ---------------------------------------------------------------------------

def _render_hotspot_diagram(v: dict) -> str:
    """
    AI-generated labeled diagram with optional hotspot coordinates.
    Input shape (populated by hotspot_diagram_generator):
      { "type": "hotspot_diagram",
        "image_url": "https://...",
        "image_width": 1024, "image_height": 1024,
        "hotspots": [{"label": "nucleus", "x": 234, "y": 156, "w": 80, "h": 80}, ...],
        "parts": ["nucleus", ...],      # fallback if image not yet generated
        "subject": "plant cell" }

    For worksheets this renders the image with numbered circles overlaid
    on each hotspot so students can identify parts for paper-based
    answering. For interactive activities the PlayHotspotLabeling React
    component reads image_url + hotspots directly and handles clicks —
    this renderer output is ignored in that path.
    """
    image_url = v.get("image_url")
    if not image_url:
        # Diagram not yet generated — show a titled placeholder
        subject = v.get("subject") or "diagram"
        parts = v.get("parts") or []
        parts_str = ", ".join(parts[:6]) + ("..." if len(parts) > 6 else "")
        return (
            f'<div class="visual-placeholder">'
            f'<strong>Labeled diagram: {html.escape(subject)}</strong>'
            f'{html.escape(parts_str)}'
            f'</div>'
        )

    hotspots = v.get("hotspots") or []
    w = int(v.get("image_width", 1024))
    h = int(v.get("image_height", 1024))

    pieces = [
        f'<div class="hotspot-diagram" style="position:relative; display:inline-block; max-width:100%;">',
        f'<img src="{html.escape(image_url)}" alt="{html.escape(v.get("subject", "diagram"))}" '
        f'style="display:block; max-width:100%; height:auto;" />',
    ]
    # Numbered overlays for print / worksheet use
    for i, hs in enumerate(hotspots, start=1):
        cx_pct = (hs["x"] / w) * 100
        cy_pct = (hs["y"] / h) * 100
        pieces.append(
            f'<span class="hotspot-pin" style="'
            f'position:absolute; left:{cx_pct:.2f}%; top:{cy_pct:.2f}%; '
            f'transform:translate(-50%,-50%); width:26px; height:26px; '
            f'border-radius:50%; background:#F97316; color:white; '
            f'display:flex; align-items:center; justify-content:center; '
            f'font-weight:700; font-size:13px; border:2px solid white; '
            f'box-shadow:0 1px 3px rgba(0,0,0,0.3);">{i}</span>'
        )
    pieces.append('</div>')

    # Legend below the image
    if hotspots:
        legend_rows = "".join(
            f'<li><span class="legend-num">{i}</span> {html.escape(hs["label"])}</li>'
            for i, hs in enumerate(hotspots, start=1)
        )
        pieces.append(f'<ol class="hotspot-legend">{legend_rows}</ol>')

    return "".join(pieces)


VISUAL_HANDLERS = {
    # K-2 math
    "ten_frame": _render_ten_frame,
    "number_bond": _render_number_bond,
    "counting_objects": _render_counting_objects,
    "base_ten_blocks": _render_base_ten_blocks,
    # 3-5 math
    "fraction_bar": _render_fraction_bar,
    "fraction_circle": _render_fraction_circle,
    "array": _render_array,
    "bar_model": _render_bar_model,
    "tape_diagram": _render_bar_model,           # alias
    "area_model": _render_area_model,
    # 6-12 math
    "number_line": _render_number_line,
    "coordinate_grid": _render_coordinate_grid,
    "coordinate_plane": _render_coordinate_grid,  # alias
    "equation_box": _render_equation_box,
    "function_table": _render_function_table,
    "input_output_table": _render_function_table, # alias
    # Science
    "data_table": _render_data_table,
    "labeled_diagram": _render_labeled_diagram,
    "diagram": _render_labeled_diagram,           # alias
    "hotspot_diagram": _render_hotspot_diagram,   # AI-generated image + coords
    # ELA
    "letter_box": _render_letter_box,
    "word_box": _render_word_box,
    "sight_word_box": _render_word_box,           # alias
    "handwriting_lines": _render_handwriting_lines,
    "picture_choice": _render_picture_choice,
    "picture_options": _render_picture_choice,    # alias
}


def supported_visual_types() -> list[str]:
    """Return the canonical (non-alias) list for use in agent prompts."""
    return [
        "ten_frame", "number_bond", "counting_objects", "base_ten_blocks",
        "fraction_bar", "fraction_circle", "array", "bar_model", "area_model",
        "number_line", "coordinate_grid", "equation_box", "function_table",
        "data_table", "labeled_diagram",
        "letter_box", "word_box", "handwriting_lines", "picture_choice",
    ]
