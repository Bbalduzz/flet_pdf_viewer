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
from ..types import AnnotationInfo, RenderResult, SelectableChar


def _map_font_name(pdf_font: str) -> str:
    """Map PDF font name to system font family."""
    if not pdf_font:
        return "sans-serif"

    if "+" in pdf_font:
        pdf_font = pdf_font.split("+")[-1]

    lower = pdf_font.lower().replace("-", "").replace("_", "")

    if "helvetica" in lower or "arial" in lower:
        return "Helvetica"
    if "times" in lower:
        return "Times New Roman"
    if "courier" in lower:
        return "Courier New"
    if "mono" in lower or "fixed" in lower:
        return "monospace"
    if "sans" in lower:
        return "sans-serif"
    if "serif" in lower:
        return "serif"

    return "sans-serif"


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
        """Render vector graphics."""
        for gfx in page.extract_graphics():
            x0, y0, x1, y1 = gfx.bbox
            cx0 = x0 * self.scale
            cy0 = y0 * self.scale
            cx1 = x1 * self.scale
            cy1 = y1 * self.scale
            width = cx1 - cx0
            height = cy1 - cy0

            if gfx.type == "rect" and width > 0 and height > 0:
                if gfx.fill_color:
                    shapes.append(
                        cv.Rect(
                            x=cx0,
                            y=cy0,
                            width=width,
                            height=height,
                            paint=ft.Paint(
                                color=gfx.fill_color,
                                style=ft.PaintingStyle.FILL,
                            ),
                        )
                    )
                if gfx.linewidth > 0 and gfx.stroke_color:
                    shapes.append(
                        cv.Rect(
                            x=cx0,
                            y=cy0,
                            width=width,
                            height=height,
                            paint=ft.Paint(
                                stroke_width=gfx.linewidth * self.scale,
                                color=gfx.stroke_color,
                                style=ft.PaintingStyle.STROKE,
                            ),
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

    def _render_ink(
        self, annot: AnnotationInfo, color: str, shapes: List[Any]
    ) -> None:
        """Render ink annotation."""
        if not annot.vertices:
            return

        stroke_width = annot.border_width

        for path in annot.vertices:
            if len(path) >= 2:
                for i in range(len(path) - 1):
                    p1 = path[i]
                    p2 = path[i + 1]
                    shapes.append(
                        cv.Line(
                            x1=p1[0] * self.scale,
                            y1=p1[1] * self.scale,
                            x2=p2[0] * self.scale,
                            y2=p2[1] * self.scale,
                            paint=ft.Paint(
                                stroke_width=stroke_width * self.scale,
                                color=color,
                                stroke_cap=ft.StrokeCap.ROUND,
                            ),
                        )
                    )

    def _render_text(self, page: PageBackend, shapes: List[Any]) -> None:
        """Render text blocks."""
        for block in page.extract_text_blocks():
            canvas_x = block.x * self.scale
            canvas_y = block.y * self.scale
            font_size = block.font_size * self.scale

            font_family = _map_font_name(block.font_name)

            style = ft.TextStyle(
                size=font_size,
                color=block.color,
                font_family=font_family,
            )

            if block.bold:
                style.weight = ft.FontWeight.BOLD
            if block.italic:
                style.italic = True

            shapes.append(
                cv.Text(
                    x=canvas_x,
                    y=canvas_y,
                    text=block.text,
                    style=style,
                )
            )

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
