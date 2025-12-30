"""
Page renderer - converts PDF page content to Flet canvas shapes.
"""

from __future__ import annotations

import os
from typing import Any, List, Tuple

import flet as ft
import flet.canvas as cv
import pymupdf

from ..backends.base import PageBackend
from ..types import AnnotationInfo, LinearGradient, RadialGradient, RenderResult, SelectableChar


def _get_font_family(pdf_font: str, flags: int = 0) -> str:
    """Get font family name for Flet.

    Returns the clean PDF font name, which should match the key in page.fonts
    if fonts were extracted and registered.

    Args:
        pdf_font: The PDF font name (may include subset prefix like "ABCDEF+")
        flags: PyMuPDF span flags (unused, kept for API compatibility)

    Returns:
        Clean font name like "Effloresce" or "LiberationSerif"
    """
    if not pdf_font:
        return "sans-serif"

    # Remove subset prefix (e.g., "PXAAAB+FontName" -> "FontName")
    clean_name = pdf_font.split("+")[-1] if "+" in pdf_font else pdf_font

    return clean_name


class PageRenderer:
    """Renders PDF page content to Flet canvas shapes."""

    def __init__(self, scale: float = 1.0):
        self.scale = scale

    def render(self, page: PageBackend) -> RenderResult:
        """Render a page to canvas shapes."""
        shapes = []
        images = []

        # 1. Render graphics (background)
        self._render_graphics(page, shapes)

        # 2. Render images
        self._render_images(page, images)

        # 3. Render annotations (before text)
        self._render_annotations(page, shapes)

        # 4. Render text (foreground)
        self._render_text(page, shapes)

        # 5. Extract chars for selection
        chars = page.extract_chars()

        return RenderResult(shapes=shapes, images=images, chars=chars)

    def _render_graphics(self, page: PageBackend, shapes: List[Any]) -> None:
        """Render vector graphics (rects, paths, lines, curves)."""
        for gfx in page.extract_graphics():
            x0, y0, x1, y1 = gfx.bbox
            cx0 = x0 * self.scale
            cy0 = y0 * self.scale
            cx1 = x1 * self.scale
            cy1 = y1 * self.scale
            width = cx1 - cx0
            height = cy1 - cy0

            if gfx.type == "rect" and width > 0 and height > 0:
                self._render_rect(gfx, cx0, cy0, width, height, shapes)

            elif gfx.type == "path" and gfx.path_commands:
                self._render_path(gfx, shapes)

    def _render_rect(
        self,
        gfx: Any,
        x: float,
        y: float,
        width: float,
        height: float,
        shapes: List[Any],
    ) -> None:
        """Render a rectangle."""
        # Check for gradient fill first
        if gfx.fill_gradient:
            gradient_paint = self._create_gradient_paint(gfx.fill_gradient)
            if gradient_paint:
                gradient_paint.style = ft.PaintingStyle.FILL
                shapes.append(
                    cv.Rect(
                        x=x,
                        y=y,
                        width=width,
                        height=height,
                        paint=gradient_paint,
                    )
                )
        elif gfx.fill_color:
            shapes.append(
                cv.Rect(
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    paint=ft.Paint(
                        color=gfx.fill_color,
                        style=ft.PaintingStyle.FILL,
                    ),
                )
            )
        if gfx.linewidth > 0 and gfx.stroke_color:
            stroke_paint = ft.Paint(
                stroke_width=gfx.linewidth * self.scale,
                color=gfx.stroke_color,
                style=ft.PaintingStyle.STROKE,
            )
            # Apply dash pattern if present
            if gfx.stroke_dashes:
                stroke_paint.stroke_dash_pattern = [d * self.scale for d in gfx.stroke_dashes]
            shapes.append(
                cv.Rect(
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    paint=stroke_paint,
                )
            )

    def _render_path(self, gfx: Any, shapes: List[Any]) -> None:
        """Render a path with lines and bezier curves."""
        path_elements = []

        for cmd in gfx.path_commands:
            op = cmd[0]

            if op == "m":  # MoveTo
                x, y = cmd[1] * self.scale, cmd[2] * self.scale
                path_elements.append(cv.Path.MoveTo(x, y))

            elif op == "l":  # LineTo
                x, y = cmd[1] * self.scale, cmd[2] * self.scale
                path_elements.append(cv.Path.LineTo(x, y))

            elif op == "c":  # Cubic bezier
                x1, y1 = cmd[1] * self.scale, cmd[2] * self.scale
                x2, y2 = cmd[3] * self.scale, cmd[4] * self.scale
                x3, y3 = cmd[5] * self.scale, cmd[6] * self.scale
                path_elements.append(cv.Path.CubicTo(x1, y1, x2, y2, x3, y3))

            elif op == "h":  # Close path
                path_elements.append(cv.Path.Close())

        if not path_elements:
            return

        # Render fill first, then stroke
        if gfx.fill_color:
            shapes.append(
                cv.Path(
                    path_elements,
                    paint=ft.Paint(
                        color=gfx.fill_color,
                        style=ft.PaintingStyle.FILL,
                    ),
                )
            )

        if gfx.stroke_color and gfx.linewidth > 0:
            stroke_paint = ft.Paint(
                color=gfx.stroke_color,
                stroke_width=gfx.linewidth * self.scale,
                style=ft.PaintingStyle.STROKE,
                stroke_cap=ft.StrokeCap.ROUND,
                stroke_join=ft.StrokeJoin.ROUND,
            )
            # Apply dash pattern if present
            if gfx.stroke_dashes:
                stroke_paint.stroke_dash_pattern = [d * self.scale for d in gfx.stroke_dashes]
            shapes.append(
                cv.Path(
                    path_elements,
                    paint=stroke_paint,
                )
            )

    def _render_images(
        self, page: PageBackend, images: List[Tuple[str, float, float, float, float]]
    ) -> None:
        """Collect image paths and positions."""
        for img in page.extract_images():
            x0, y0, x1, y1 = img.bbox
            if img.png_path and os.path.exists(img.png_path):
                images.append(
                    (
                        img.png_path,
                        x0 * self.scale,
                        y0 * self.scale,
                        (x1 - x0) * self.scale,
                        (y1 - y0) * self.scale,
                    )
                )

    def _render_annotations(self, page: PageBackend, shapes: List[Any]) -> None:
        """Render PDF annotations."""
        for annot in page.get_annotations():
            self._render_annotation(annot, shapes)

    def _render_annotation(self, annot: AnnotationInfo, shapes: List[Any]) -> None:
        """Render a single annotation."""
        cx0 = annot.rect[0] * self.scale
        cy0 = annot.rect[1] * self.scale
        cx1 = annot.rect[2] * self.scale
        cy1 = annot.rect[3] * self.scale
        width = cx1 - cx0
        height = cy1 - cy0

        r, g, b = annot.color
        hex_color = f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"

        # Highlight
        if annot.type == pymupdf.PDF_ANNOT_HIGHLIGHT:
            shapes.append(
                cv.Rect(
                    x=cx0,
                    y=cy0,
                    width=width,
                    height=height,
                    paint=ft.Paint(
                        color=ft.Colors.with_opacity(0.35, hex_color),
                        style=ft.PaintingStyle.FILL,
                    ),
                )
            )

        # Underline
        elif annot.type == pymupdf.PDF_ANNOT_UNDERLINE:
            shapes.append(
                cv.Line(
                    x1=cx0,
                    y1=cy1,
                    x2=cx1,
                    y2=cy1,
                    paint=ft.Paint(
                        stroke_width=max(1.5 * self.scale, 1),
                        color=hex_color,
                    ),
                )
            )

        # Strikethrough
        elif annot.type == pymupdf.PDF_ANNOT_STRIKE_OUT:
            mid_y = cy0 + height / 2
            shapes.append(
                cv.Line(
                    x1=cx0,
                    y1=mid_y,
                    x2=cx1,
                    y2=mid_y,
                    paint=ft.Paint(
                        stroke_width=max(1.5 * self.scale, 1),
                        color=hex_color,
                    ),
                )
            )

        # Squiggly
        elif annot.type == pymupdf.PDF_ANNOT_SQUIGGLY:
            self._render_squiggly(cx0, cx1, cy1, hex_color, shapes)

        # Text note (sticky note)
        elif annot.type == pymupdf.PDF_ANNOT_TEXT:
            self._render_note_icon(cx0, cy0, hex_color, shapes)

        # Ink (freehand)
        elif annot.type == pymupdf.PDF_ANNOT_INK:
            self._render_ink(annot, hex_color, shapes)

    def _render_squiggly(
        self, x0: float, x1: float, y: float, color: str, shapes: List[Any]
    ) -> None:
        """Render squiggly underline."""
        wave_height = 2 * self.scale
        step = 4 * self.scale
        x = x0
        points = []
        up = True

        while x < x1:
            py = y - wave_height if up else y
            points.append((x, py))
            x += step
            up = not up

        points.append((x1, y - wave_height if up else y))

        for i in range(len(points) - 1):
            shapes.append(
                cv.Line(
                    x1=points[i][0],
                    y1=points[i][1],
                    x2=points[i + 1][0],
                    y2=points[i + 1][1],
                    paint=ft.Paint(
                        stroke_width=max(1 * self.scale, 1),
                        color=color,
                    ),
                )
            )

    def _render_note_icon(
        self, x: float, y: float, color: str, shapes: List[Any]
    ) -> None:
        """Render sticky note icon."""
        icon_size = 16 * self.scale
        fold_size = 4 * self.scale

        # Background
        shapes.append(
            cv.Rect(
                x=x,
                y=y,
                width=icon_size,
                height=icon_size,
                paint=ft.Paint(color=color, style=ft.PaintingStyle.FILL),
            )
        )

        # Border
        shapes.append(
            cv.Rect(
                x=x,
                y=y,
                width=icon_size,
                height=icon_size,
                paint=ft.Paint(
                    color="#000000", style=ft.PaintingStyle.STROKE, stroke_width=1
                ),
            )
        )

        # Fold corner
        shapes.append(
            cv.Path(
                [
                    cv.Path.MoveTo(x + icon_size - fold_size, y),
                    cv.Path.LineTo(x + icon_size, y + fold_size),
                    cv.Path.LineTo(x + icon_size - fold_size, y + fold_size),
                    cv.Path.Close(),
                ],
                paint=ft.Paint(color="#ffffff", style=ft.PaintingStyle.FILL),
            )
        )

    def _catmull_rom_to_bezier(
        self, points: List[Tuple[float, float]], scale: float = 1.0, tension: float = 0.5
    ) -> List:
        """Convert points to smooth path using Catmull-Rom splines converted to cubic beziers."""
        if len(points) < 2:
            return []

        scaled = [(p[0] * scale, p[1] * scale) for p in points]

        if len(scaled) == 2:
            return [
                cv.Path.MoveTo(scaled[0][0], scaled[0][1]),
                cv.Path.LineTo(scaled[1][0], scaled[1][1]),
            ]

        # Duplicate first and last points for the spline
        pts = [scaled[0]] + scaled + [scaled[-1]]

        elements = [cv.Path.MoveTo(scaled[0][0], scaled[0][1])]

        # Convert each Catmull-Rom segment to cubic bezier
        for i in range(1, len(pts) - 2):
            p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]

            # Calculate control points for cubic bezier
            # Using tension parameter (0.5 = standard Catmull-Rom)
            cp1x = p1[0] + (p2[0] - p0[0]) * tension / 3
            cp1y = p1[1] + (p2[1] - p0[1]) * tension / 3
            cp2x = p2[0] - (p3[0] - p1[0]) * tension / 3
            cp2y = p2[1] - (p3[1] - p1[1]) * tension / 3

            elements.append(cv.Path.CubicTo(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1]))

        return elements

    def _render_ink(
        self, annot: AnnotationInfo, color: str, shapes: List[Any]
    ) -> None:
        """Render ink annotation with Catmull-Rom splines."""
        if not annot.vertices:
            return

        stroke_width = annot.border_width

        for path in annot.vertices:
            if len(path) >= 2:
                elements = self._catmull_rom_to_bezier(path, self.scale)
                shapes.append(
                    cv.Path(
                        elements,
                        paint=ft.Paint(
                            stroke_width=stroke_width * self.scale,
                            color=color,
                            style=ft.PaintingStyle.STROKE,
                            stroke_cap=ft.StrokeCap.ROUND,
                            stroke_join=ft.StrokeJoin.ROUND,
                        ),
                    )
                )

    def _render_text(self, page: PageBackend, shapes: List[Any]) -> None:
        """Render text blocks."""
        for block in page.extract_text_blocks():
            canvas_x = block.x * self.scale
            canvas_y = block.y * self.scale
            font_size = block.font_size * self.scale

            font_family = _get_font_family(block.font_name, block.font_flags)

            style = ft.TextStyle(
                size=font_size,
                font_family=font_family,
            )

            if block.bold:
                style.weight = ft.FontWeight.BOLD
            if block.italic:
                style.italic = True

            # Apply gradient or solid color
            if block.gradient:
                gradient_paint = self._create_gradient_paint(block.gradient)
                if gradient_paint:
                    style.foreground = gradient_paint
                else:
                    style.color = block.color
            else:
                style.color = block.color

            shapes.append(
                cv.Text(
                    x=canvas_x,
                    y=canvas_y,
                    text=block.text,
                    style=style,
                )
            )

    def _create_gradient_paint(
        self, gradient: LinearGradient | RadialGradient
    ) -> ft.Paint | None:
        """Convert gradient definition to Flet Paint with gradient."""
        try:
            # Convert RGB tuples (0-1) to hex colors
            colors = []
            for c in gradient.colors:
                r, g, b = int(c[0] * 255), int(c[1] * 255), int(c[2] * 255)
                colors.append(f"#{r:02x}{g:02x}{b:02x}")

            if isinstance(gradient, LinearGradient):
                # Handle extend properties
                # PDF allows asymmetric extension (extend before start but not after end)
                begin_x = gradient.x0 * self.scale
                begin_y = gradient.y0 * self.scale
                end_x = gradient.x1 * self.scale
                end_y = gradient.y1 * self.scale

                # Calculate gradient vector
                dx = end_x - begin_x
                dy = end_y - begin_y

                # If extend_start is True but extend_end is False, we need special handling
                # Extend the start point far backwards to simulate infinite extension
                if gradient.extend_start and not gradient.extend_end:
                    # Extend start backwards by a large factor
                    begin_x -= dx * 10
                    begin_y -= dy * 10
                    # Adjust color stops to compensate
                    # Original gradient is now from 10/11 to 11/11
                    colors_adjusted = [colors[0], colors[0], colors[1]]
                    stops_adjusted = [0.0, 10.0 / 11.0, 1.0]
                    return ft.Paint(
                        gradient=ft.PaintLinearGradient(
                            begin=(begin_x, begin_y),
                            end=(end_x, end_y),
                            colors=colors_adjusted,
                            color_stops=stops_adjusted,
                            tile_mode=ft.GradientTileMode.DECAL,
                        ),
                    )

                # Determine tile mode for other cases
                tile_mode = ft.GradientTileMode.CLAMP
                if not gradient.extend_start and not gradient.extend_end:
                    tile_mode = ft.GradientTileMode.DECAL

                return ft.Paint(
                    gradient=ft.PaintLinearGradient(
                        begin=(begin_x, begin_y),
                        end=(end_x, end_y),
                        colors=colors,
                        color_stops=gradient.stops,
                        tile_mode=tile_mode,
                    ),
                )
            elif isinstance(gradient, RadialGradient):
                return ft.Paint(
                    gradient=ft.PaintRadialGradient(
                        center=(gradient.cx * self.scale, gradient.cy * self.scale),
                        radius=gradient.r * self.scale,
                        colors=colors,
                        color_stops=gradient.stops,
                    ),
                )
        except Exception:
            pass

        return None

    def build_selectable_chars(
        self, page: PageBackend, page_index: int, offset_x: float = 0, offset_y: float = 0
    ) -> List[SelectableChar]:
        """Build selectable characters from a page."""
        chars = page.extract_chars()
        return [
            SelectableChar(
                char=c.char,
                x=c.x * self.scale,
                y=c.y * self.scale,
                width=c.width * self.scale,
                height=c.height * self.scale,
                page_index=page_index,
                page_offset_x=offset_x,
                page_offset_y=offset_y,
            )
            for c in chars
        ]
