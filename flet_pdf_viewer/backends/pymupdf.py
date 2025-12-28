"""
PyMuPDF backend implementation.
"""

from __future__ import annotations

import io
import tempfile
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

warnings.filterwarnings("ignore", message="builtin type Swig")

import pymupdf

from ..types import (  # noqa: E402
    AnnotationInfo,
    CharInfo,
    Color,
    GraphicsInfo,
    ImageInfo,
    OutlineItem,
    PageInfo,
    Rect,
    TextBlock,
)
from ..types import (
    Path as InkPath,
)
from .base import DocumentBackend, PageBackend  # noqa: E402


def _color_to_hex(color) -> str:
    """Convert PyMuPDF color to hex string."""
    if color is None:
        return "#000000"

    if isinstance(color, (int, float)):
        gray = int(color * 255)
        return f"#{gray:02x}{gray:02x}{gray:02x}"

    if isinstance(color, (list, tuple)):
        if len(color) == 1:
            gray = int(color[0] * 255)
            return f"#{gray:02x}{gray:02x}{gray:02x}"
        elif len(color) == 3:
            r, g, b = [int(c * 255) for c in color]
            return f"#{r:02x}{g:02x}{b:02x}"
        elif len(color) == 4:
            c, m, y, k = color
            r = int(255 * (1 - c) * (1 - k))
            g = int(255 * (1 - m) * (1 - k))
            b = int(255 * (1 - y) * (1 - k))
            return f"#{r:02x}{g:02x}{b:02x}"

    return "#000000"


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


class PyMuPDFPage(PageBackend):
    """PyMuPDF page implementation."""

    def __init__(self, doc: "PyMuPDFBackend", page: pymupdf.Page, index: int):
        self._doc = doc
        self._page = page
        self._index = index

    @property
    def width(self) -> float:
        return self._page.rect.width

    @property
    def height(self) -> float:
        return self._page.rect.height

    @property
    def index(self) -> int:
        return self._index

    def get_info(self) -> PageInfo:
        return PageInfo(
            index=self._index,
            width=self.width,
            height=self.height,
            rotation=self._page.rotation,
        )

    def extract_text_blocks(self) -> List[TextBlock]:
        """Extract text blocks with styling."""
        blocks = []
        text_dict = self._page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue

            for line in block.get("lines", []):
                line_text_parts = []
                line_x0 = None
                line_y0 = None
                line_x1 = 0
                line_height = 0
                line_font = "Helvetica"
                line_size = 12
                line_color = "#000000"
                line_bold = False
                line_italic = False

                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text:
                        continue

                    bbox = span.get("bbox", (0, 0, 0, 0))
                    font = span.get("font", "Helvetica")
                    size = span.get("size", 12)
                    color = span.get("color", 0)
                    flags = span.get("flags", 0)

                    if line_x0 is None:
                        line_x0 = bbox[0]
                        line_y0 = bbox[1]
                        line_font = font
                        line_size = size

                        if isinstance(color, int):
                            r = (color >> 16) & 0xFF
                            g = (color >> 8) & 0xFF
                            b = color & 0xFF
                            line_color = f"#{r:02x}{g:02x}{b:02x}"

                        line_bold = bool(flags & 16)
                        line_italic = bool(flags & 2)

                        font_lower = font.lower()
                        if "bold" in font_lower:
                            line_bold = True
                        if "italic" in font_lower or "oblique" in font_lower:
                            line_italic = True

                    line_text_parts.append(text)
                    line_x1 = max(line_x1, bbox[2])
                    line_height = max(line_height, bbox[3] - bbox[1])

                line_text = "".join(line_text_parts).strip()
                if line_text and line_x0 is not None:
                    blocks.append(
                        TextBlock(
                            text=line_text,
                            x=line_x0,
                            y=line_y0,
                            width=line_x1 - line_x0,
                            height=line_height,
                            font_name=line_font,
                            font_size=line_size,
                            color=line_color,
                            bold=line_bold,
                            italic=line_italic,
                        )
                    )

        return blocks

    def extract_chars(self) -> List[CharInfo]:
        """Extract individual characters."""
        chars = []
        text_dict = self._page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue

            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    font = span.get("font", "Helvetica")
                    size = span.get("size", 12)
                    color = span.get("color", 0)

                    if isinstance(color, int):
                        r = (color >> 16) & 0xFF
                        g = (color >> 8) & 0xFF
                        b = color & 0xFF
                        hex_color = f"#{r:02x}{g:02x}{b:02x}"
                    else:
                        hex_color = "#000000"

                    span_chars = span.get("chars", [])
                    if span_chars:
                        for char_info in span_chars:
                            c = char_info.get("c", "")
                            if not c:
                                continue
                            bbox = char_info.get("bbox", (0, 0, 0, 0))
                            chars.append(
                                CharInfo(
                                    char=c,
                                    x=bbox[0],
                                    y=bbox[1],
                                    width=bbox[2] - bbox[0],
                                    height=bbox[3] - bbox[1],
                                    font_name=font,
                                    font_size=size,
                                    color=hex_color,
                                )
                            )
                    else:
                        text = span.get("text", "")
                        if text.strip():
                            bbox = span.get("bbox", (0, 0, 0, 0))
                            char_width = (bbox[2] - bbox[0]) / max(len(text), 1)
                            x = bbox[0]
                            for c in text:
                                chars.append(
                                    CharInfo(
                                        char=c,
                                        x=x,
                                        y=bbox[1],
                                        width=char_width,
                                        height=bbox[3] - bbox[1],
                                        font_name=font,
                                        font_size=size,
                                        color=hex_color,
                                    )
                                )
                                x += char_width

        return chars

    def extract_images(self) -> List[ImageInfo]:
        """Extract images from the page."""
        images = []
        image_list = self._page.get_images(full=True)

        for img_info in image_list:
            xref = img_info[0]
            try:
                img_rects = self._page.get_image_rects(xref)
                if not img_rects:
                    continue

                rect = img_rects[0]
                base_image = self._doc._doc.extract_image(xref)
                if not base_image:
                    continue

                image_data = base_image.get("image")
                width = base_image.get("width", 0)
                height = base_image.get("height", 0)
                ext = base_image.get("ext", "png")

                png_path = None
                if image_data:
                    png_path = tempfile.mktemp(suffix=f".{ext}")
                    with open(png_path, "wb") as f:
                        f.write(image_data)

                images.append(
                    ImageInfo(
                        bbox=(rect.x0, rect.y0, rect.x1, rect.y1),
                        width=width,
                        height=height,
                        png_path=png_path,
                    )
                )
            except Exception:
                continue

        return images

    def extract_graphics(self) -> List[GraphicsInfo]:
        """Extract vector graphics."""
        graphics = []
        drawings = self._page.get_drawings()

        for drawing in drawings:
            rect = drawing.get("rect")
            if not rect or (rect.width < 20 and rect.height < 20):
                continue

            fill = drawing.get("fill")
            if fill is None:
                continue

            color = drawing.get("color")
            width = drawing.get("width") or 0

            for item in drawing.get("items", []):
                if item[0] == "re":
                    r = item[1]
                    if r.width >= 20 or r.height >= 10:
                        graphics.append(
                            GraphicsInfo(
                                type="rect",
                                bbox=(r.x0, r.y0, r.x1, r.y1),
                                linewidth=width,
                                stroke_color=_color_to_hex(color) if color else None,
                                fill_color=_color_to_hex(fill),
                            )
                        )

        return graphics

    def get_annotations(self) -> List[AnnotationInfo]:
        """Get all annotations on the page."""
        annotations = []

        for annot in self._page.annots() or []:
            annot_type = annot.type[0] if annot.type else -1
            annot_name = annot.type[1] if annot.type else "Unknown"
            rect = annot.rect
            colors = annot.colors or {}

            stroke = colors.get("stroke", (1.0, 1.0, 0.0))
            if isinstance(stroke, (list, tuple)) and len(stroke) >= 3:
                color = (stroke[0], stroke[1], stroke[2])
            else:
                color = (1.0, 1.0, 0.0)

            border = annot.border or {}
            border_width = border.get("width", 1.0)

            annotations.append(
                AnnotationInfo(
                    type=annot_type,
                    type_name=annot_name,
                    rect=(rect.x0, rect.y0, rect.x1, rect.y1),
                    color=color,
                    contents=annot.info.get("content", ""),
                    vertices=annot.vertices,
                    border_width=border_width,
                )
            )

        return annotations

    def add_highlight(self, rects: List[Rect], color: Color) -> None:
        for rect in rects:
            annot = self._page.add_highlight_annot(pymupdf.Rect(rect))
            annot.set_colors(stroke=color)
            annot.update()

    def add_underline(self, rects: List[Rect], color: Color) -> None:
        for rect in rects:
            annot = self._page.add_underline_annot(pymupdf.Rect(rect))
            annot.set_colors(stroke=color)
            annot.update()

    def add_strikethrough(self, rects: List[Rect], color: Color) -> None:
        for rect in rects:
            annot = self._page.add_strikeout_annot(pymupdf.Rect(rect))
            annot.set_colors(stroke=color)
            annot.update()

    def add_squiggly(self, rects: List[Rect], color: Color) -> None:
        for rect in rects:
            annot = self._page.add_squiggly_annot(pymupdf.Rect(rect))
            annot.set_colors(stroke=color)
            annot.update()

    def add_text_note(
        self,
        point: Tuple[float, float],
        text: str,
        icon: str = "Note",
        color: Color = (1.0, 0.92, 0.0),
    ) -> None:
        annot = self._page.add_text_annot(pymupdf.Point(point), text, icon=icon)
        annot.set_colors(stroke=color)
        annot.update()

    def add_ink(
        self,
        paths: List[InkPath],
        color: Color = (0.0, 0.0, 0.0),
        width: float = 2.0,
    ) -> None:
        ink_list = [[(float(x), float(y)) for x, y in path] for path in paths]
        annot = self._page.add_ink_annot(ink_list)
        annot.set_colors(stroke=color)
        annot.set_border(width=width)
        annot.update()


class PyMuPDFBackend(DocumentBackend):
    """PyMuPDF document backend."""

    def __init__(self, source: Union[str, Path, bytes, io.BytesIO]):
        if isinstance(source, (str, Path)):
            self._path = Path(source)
            self._doc = pymupdf.open(str(source))
        elif isinstance(source, bytes):
            self._path = None
            self._doc = pymupdf.open(stream=source, filetype="pdf")
        elif isinstance(source, io.BytesIO):
            self._path = None
            self._doc = pymupdf.open(stream=source.read(), filetype="pdf")
        else:
            raise TypeError(f"Unsupported source type: {type(source)}")

        self._pages: Dict[int, PyMuPDFPage] = {}

    @property
    def page_count(self) -> int:
        return len(self._doc)

    def get_page(self, index: int) -> PyMuPDFPage:
        if index in self._pages:
            return self._pages[index]

        if index < 0 or index >= len(self._doc):
            raise IndexError(f"Page index {index} out of range")

        page = self._doc[index]
        pdf_page = PyMuPDFPage(self, page, index)
        self._pages[index] = pdf_page
        return pdf_page

    def get_outlines(self) -> List[OutlineItem]:
        outlines = []
        toc = self._doc.get_toc(simple=False)
        stack: List[Tuple[int, OutlineItem]] = []

        for item in toc:
            level = item[0]
            title = item[1]
            page_num = item[2] - 1 if item[2] > 0 else None

            outline_item = OutlineItem(
                title=title,
                page_index=page_num,
                level=level,
            )

            while stack and stack[-1][0] >= level:
                stack.pop()

            if stack:
                stack[-1][1].children.append(outline_item)
            else:
                outlines.append(outline_item)

            stack.append((level, outline_item))

        return outlines

    def get_metadata(self) -> dict:
        try:
            return dict(self._doc.metadata) if self._doc.metadata else {}
        except Exception:
            return {}

    def save(self, path: Optional[Union[str, Path]] = None) -> None:
        if path is None:
            if self._path is None:
                raise ValueError(
                    "No path specified and document was not loaded from file"
                )
            path = self._path

        if self._path and Path(path) == self._path:
            self._doc.save(str(path), incremental=True, encryption=0)
        else:
            self._doc.save(str(path))

    def close(self) -> None:
        if self._doc:
            self._doc.close()
        self._pages.clear()
