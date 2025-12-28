"""
PDF Document wrapper using PyMuPDF.

PyMuPDF provides excellent text extraction with proper character decoding,
including Type3 fonts and complex encodings.
"""

from __future__ import annotations

import warnings
# Suppress PyMuPDF SWIG deprecation warnings
warnings.filterwarnings("ignore", message="builtin type Swig")

import io
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import flet as ft
import flet.canvas as cv
import pymupdf


@dataclass
class PageInfo:
    """Information about a PDF page."""

    index: int
    width: float
    height: float
    rotation: int
    media_box: Tuple[float, float, float, float]


@dataclass
class TextBlock:
    """Extracted text with position."""

    text: str
    x: float
    y: float
    width: float
    height: float
    font_name: str
    font_size: float
    color: str = "#000000"
    bold: bool = False
    italic: bool = False


@dataclass
class CharInfo:
    """Single character with position info."""

    char: str
    x: float
    y: float
    width: float
    height: float
    font_name: str
    font_size: float
    color: str = "#000000"


@dataclass
class OutlineItem:
    """A bookmark/TOC entry."""

    title: str
    page_index: Optional[int]
    level: int
    children: List["OutlineItem"] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []


@dataclass
class Annotation:
    """A PDF annotation."""

    type: str
    rect: Tuple[float, float, float, float]
    contents: Optional[str] = None
    dest_page: Optional[int] = None
    uri: Optional[str] = None


@dataclass
class GraphicsElement:
    """A graphics element (line, rect, curve)."""

    type: str
    bbox: Tuple[float, float, float, float]
    linewidth: float
    stroke_color: Optional[str] = None
    fill_color: Optional[str] = None
    points: Optional[List[Tuple[float, float]]] = None


@dataclass
class ImageElement:
    """An image element."""

    bbox: Tuple[float, float, float, float]
    name: str
    width: int
    height: int
    data: Optional[bytes] = None
    color_space: str = "RGB"
    bits_per_component: int = 8
    png_path: Optional[str] = None


def _color_to_hex(color) -> str:
    """Convert PyMuPDF color to hex string."""
    if color is None:
        return "#000000"

    if isinstance(color, (int, float)):
        # Grayscale
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
            # CMYK
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
    if "calibri" in lower:
        return "Arial"
    if "georgia" in lower:
        return "Georgia"
    if "mono" in lower or "fixed" in lower:
        return "monospace"
    if "sans" in lower:
        return "sans-serif"
    if "serif" in lower:
        return "serif"

    return "sans-serif"


def _get_font_styles_from_descriptors(doc: pymupdf.Document, page: pymupdf.Page) -> Dict[str, Dict]:
    """Extract font style info from FontDescriptor objects for Type3 fonts."""
    font_styles = {}
    fonts = page.get_fonts(full=True)

    for font_info in fonts:
        xref = font_info[0]
        ref_name = font_info[4]  # e.g., 'F4', 'F5'

        try:
            font_obj = doc.xref_object(xref)
            fd_match = re.search(r'/FontDescriptor\s+(\d+)\s+0\s+R', font_obj)
            if fd_match:
                fd_xref = int(fd_match.group(1))
                fd_obj = doc.xref_object(fd_xref)

                weight_match = re.search(r'/FontWeight\s+(\d+)', fd_obj)
                font_weight = int(weight_match.group(1)) if weight_match else 400

                italic_match = re.search(r'/ItalicAngle\s+(-?\d+)', fd_obj)
                italic_angle = int(italic_match.group(1)) if italic_match else 0

                flags_match = re.search(r'/Flags\s+(\d+)', fd_obj)
                flags = int(flags_match.group(1)) if flags_match else 0

                font_styles[ref_name] = {
                    'bold': font_weight >= 600,
                    'italic': italic_angle != 0 or bool(flags & 64),
                    'xref': xref
                }
        except Exception:
            pass

    return font_styles


def _parse_content_stream_fonts(doc: pymupdf.Document, page: pymupdf.Page,
                                 font_styles: Dict[str, Dict]) -> List[Dict]:
    """Parse content stream to extract font usage and colors at positions."""
    text_items = []

    try:
        xref = page.xref
        page_obj = doc.xref_object(xref)
        contents_match = re.search(r'/Contents\s+(\d+)\s+0\s+R', page_obj)
        if not contents_match:
            return text_items

        contents_xref = int(contents_match.group(1))
        contents = doc.xref_stream(contents_xref)
        if not contents:
            return text_items

        contents_text = contents.decode('latin-1', errors='replace')
    except Exception:
        return text_items

    # Simple content stream parser
    current_font = None
    font_size = 12.0
    text_matrix = [1, 0, 0, 1, 0, 0]
    ctm_stack = [[1, 0, 0, 1, 0, 0]]
    text_x = 0.0
    text_y = 0.0

    # Color state (RGB, 0-1 range)
    current_fill_color = (0.0, 0.0, 0.0)
    color_stack = [(0.0, 0.0, 0.0)]

    def multiply_matrices(m1, m2):
        return [
            m1[0]*m2[0] + m1[2]*m2[1],
            m1[1]*m2[0] + m1[3]*m2[1],
            m1[0]*m2[2] + m1[2]*m2[3],
            m1[1]*m2[2] + m1[3]*m2[3],
            m1[0]*m2[4] + m1[2]*m2[5] + m1[4],
            m1[1]*m2[4] + m1[3]*m2[5] + m1[5]
        ]

    # Tokenize and parse
    tokens = []
    i = 0
    while i < len(contents_text):
        while i < len(contents_text) and contents_text[i] in ' \t\n\r':
            i += 1
        if i >= len(contents_text):
            break

        if contents_text[i] == '%':
            while i < len(contents_text) and contents_text[i] != '\n':
                i += 1
            continue

        if contents_text[i] == '/':
            j = i + 1
            while j < len(contents_text) and contents_text[j] not in ' \t\n\r/<>[()%':
                j += 1
            tokens.append(contents_text[i:j])
            i = j
            continue

        if contents_text[i] in '0123456789.-+':
            j = i
            while j < len(contents_text) and contents_text[j] in '0123456789.-+eE':
                j += 1
            tokens.append(contents_text[i:j])
            i = j
            continue

        if contents_text[i] == '<' and i + 1 < len(contents_text) and contents_text[i+1] != '<':
            j = i + 1
            while j < len(contents_text) and contents_text[j] != '>':
                j += 1
            tokens.append(contents_text[i:j+1])
            i = j + 1
            continue

        j = i
        while j < len(contents_text) and contents_text[j] not in ' \t\n\r/<>[()%':
            j += 1
        if j > i:
            tokens.append(contents_text[i:j])
        i = j if j > i else i + 1

    # Process tokens
    idx = 0
    while idx < len(tokens):
        token = tokens[idx]

        if token == 'cm' and idx >= 6:
            try:
                vals = [float(tokens[idx-6+j]) for j in range(6)]
                ctm_stack[-1] = multiply_matrices(ctm_stack[-1], vals)
            except (ValueError, IndexError):
                pass

        elif token == 'q':
            ctm_stack.append(list(ctm_stack[-1]))
            color_stack.append(current_fill_color)

        elif token == 'Q':
            if len(ctm_stack) > 1:
                ctm_stack.pop()
            if len(color_stack) > 1:
                current_fill_color = color_stack.pop()

        # RGB fill color: r g b rg
        elif token == 'rg' and idx >= 3:
            try:
                r = float(tokens[idx-3])
                g = float(tokens[idx-2])
                b = float(tokens[idx-1])
                current_fill_color = (r, g, b)
            except (ValueError, IndexError):
                pass

        # Grayscale fill color: gray g
        elif token == 'g' and idx >= 1:
            try:
                gray = float(tokens[idx-1])
                current_fill_color = (gray, gray, gray)
            except (ValueError, IndexError):
                pass

        # CMYK fill color: c m y k k
        elif token == 'k' and idx >= 4:
            try:
                c = float(tokens[idx-4])
                m = float(tokens[idx-3])
                y = float(tokens[idx-2])
                k = float(tokens[idx-1])
                # Convert CMYK to RGB
                r = (1 - c) * (1 - k)
                g = (1 - m) * (1 - k)
                b = (1 - y) * (1 - k)
                current_fill_color = (r, g, b)
            except (ValueError, IndexError):
                pass

        elif token == 'Tf' and idx >= 2:
            font_name = tokens[idx-2].lstrip('/')
            current_font = font_name
            try:
                font_size = float(tokens[idx-1])
            except ValueError:
                pass

        elif token == 'Tm' and idx >= 6:
            try:
                text_matrix = [float(tokens[idx-6+j]) for j in range(6)]
                text_x = text_matrix[4]
                text_y = text_matrix[5]
            except (ValueError, IndexError):
                pass

        elif token == 'Td' and idx >= 2:
            try:
                text_x += float(tokens[idx-2])
                text_y += float(tokens[idx-1])
            except ValueError:
                pass

        elif token == 'Tj' and current_font:
            ctm = ctm_stack[-1]
            fx = ctm[0] * text_x + ctm[2] * text_y + ctm[4]
            fy = ctm[1] * text_x + ctm[3] * text_y + ctm[5]

            style = font_styles.get(current_font, {})

            # Convert color to hex
            r, g, b = current_fill_color
            hex_color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

            text_items.append({
                'font': current_font,
                'x': fx,
                'y': fy,
                'size': font_size,
                'bold': style.get('bold', False),
                'italic': style.get('italic', False),
                'color': hex_color
            })

        idx += 1

    return text_items


def _find_style_at_position(text_items: List[Dict], x: float, y: float,
                            page_height: float, tolerance: float = 2.0) -> Optional[Dict]:
    """Find font style info for a given position."""
    for item in text_items:
        item_y_transformed = page_height - item['y']
        if abs(item['x'] - x) < tolerance and abs(item_y_transformed - y) < tolerance:
            return item
    return None


class PyMuPDFPage:
    """A PDF page using PyMuPDF."""

    def __init__(self, doc: "PyMuPDFDocument", page: pymupdf.Page, index: int):
        self._doc = doc
        self._page = page
        self._index = index
        self._font_styles: Optional[Dict[str, Dict]] = None
        self._text_items: Optional[List[Dict]] = None

    def _ensure_font_info(self):
        """Lazily load font style information from content stream."""
        if self._font_styles is None:
            self._font_styles = _get_font_styles_from_descriptors(
                self._doc._doc, self._page
            )
            self._text_items = _parse_content_stream_fonts(
                self._doc._doc, self._page, self._font_styles
            )

    @property
    def width(self) -> float:
        return self._page.rect.width

    @property
    def height(self) -> float:
        return self._page.rect.height

    @property
    def info(self) -> PageInfo:
        rect = self._page.rect
        return PageInfo(
            index=self._index,
            width=self.width,
            height=self.height,
            rotation=self._page.rotation,
            media_box=(rect.x0, rect.y0, rect.x1, rect.y1),
        )

    def extract_text_blocks(self) -> List[TextBlock]:
        """Extract text blocks from the page using PyMuPDF's text extraction."""
        blocks = []

        # Ensure font style info is loaded for Type3 font detection
        self._ensure_font_info()
        page_height = self._page.mediabox.height

        # Get text with detailed info (dict format)
        text_dict = self._page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # type 0 = text block
                continue

            for line in block.get("lines", []):
                # Combine spans into a single line
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
                    origin = span.get("origin", (bbox[0], bbox[1]))

                    if line_x0 is None:
                        line_x0 = bbox[0]
                        line_y0 = bbox[1]
                        line_font = font
                        line_size = size
                        # Convert color (integer) to hex
                        if isinstance(color, int):
                            r = (color >> 16) & 0xFF
                            g = (color >> 8) & 0xFF
                            b = color & 0xFF
                            line_color = f"#{r:02x}{g:02x}{b:02x}"

                        # Check for bold/italic from PyMuPDF flags
                        line_bold = bool(flags & 16)  # TEXT_FONT_BOLD
                        line_italic = bool(flags & 2)  # TEXT_FONT_ITALIC

                        # Also check font name for standard fonts
                        font_lower = font.lower()
                        if "bold" in font_lower:
                            line_bold = True
                        if "italic" in font_lower or "oblique" in font_lower:
                            line_italic = True

                        # For Type3 fonts (Unnamed-T3), use content stream info
                        if "unnamed" in font_lower or "type3" in font_lower:
                            style_info = _find_style_at_position(
                                self._text_items or [],
                                origin[0], origin[1],
                                page_height
                            )
                            if style_info:
                                line_bold = style_info.get('bold', False)
                                line_italic = style_info.get('italic', False)
                                # Also get color from content stream
                                if 'color' in style_info:
                                    line_color = style_info['color']

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
        """Extract individual characters with their bounding boxes."""
        chars = []

        # Get text with detailed info including character-level data
        text_dict = self._page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # type 0 = text block
                continue

            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    font = span.get("font", "Helvetica")
                    size = span.get("size", 12)
                    color = span.get("color", 0)

                    # Convert color to hex
                    if isinstance(color, int):
                        r = (color >> 16) & 0xFF
                        g = (color >> 8) & 0xFF
                        b = color & 0xFF
                        hex_color = f"#{r:02x}{g:02x}{b:02x}"
                    else:
                        hex_color = "#000000"

                    # Check if we have character-level data
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
                        # Fallback: use span bbox for entire text
                        text = span.get("text", "")
                        if text.strip():
                            bbox = span.get("bbox", (0, 0, 0, 0))
                            # Approximate character width
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

    def extract_graphics(self) -> List[GraphicsElement]:
        """Extract graphics elements from the page (excluding text/glyph paths)."""
        graphics = []

        # Get drawings (vector graphics)
        # Note: get_drawings() returns ALL paths including font glyphs
        # We only extract simple rectangles that are likely decorative elements
        drawings = self._page.get_drawings()

        for drawing in drawings:
            rect = drawing.get("rect")
            if not rect:
                continue

            # Skip small elements (likely font glyphs or decorations)
            # Only keep elements that span a significant portion of the page
            if rect.width < 20 and rect.height < 20:
                continue

            color = drawing.get("color")
            fill = drawing.get("fill")

            # Must have fill color for decorative rectangles
            if fill is None:
                continue

            items = drawing.get("items", [])
            width = drawing.get("width") or 0

            stroke_color = _color_to_hex(color) if color else None
            fill_color = _color_to_hex(fill)

            # Only process rectangles
            for item in items:
                item_type = item[0]

                if item_type == "re":  # rectangle
                    r = item[1]
                    # Only keep significant rectangles
                    if r.width >= 20 or r.height >= 10:
                        graphics.append(
                            GraphicsElement(
                                type="rect",
                                bbox=(r.x0, r.y0, r.x1, r.y1),
                                linewidth=width,
                                stroke_color=stroke_color,
                                fill_color=fill_color,
                            )
                        )

        return graphics

    def extract_images(self) -> List[ImageElement]:
        """Extract images from the page."""
        images = []

        image_list = self._page.get_images(full=True)

        for img_info in image_list:
            xref = img_info[0]

            try:
                # Get image bbox
                img_rects = self._page.get_image_rects(xref)
                if not img_rects:
                    continue

                rect = img_rects[0]

                # Extract image
                base_image = self._doc._doc.extract_image(xref)
                if not base_image:
                    continue

                image_data = base_image.get("image")
                width = base_image.get("width", 0)
                height = base_image.get("height", 0)
                ext = base_image.get("ext", "png")

                # Save to temp file
                png_path = None
                if image_data:
                    png_path = tempfile.mktemp(suffix=f".{ext}")
                    with open(png_path, "wb") as f:
                        f.write(image_data)

                images.append(
                    ImageElement(
                        bbox=(rect.x0, rect.y0, rect.x1, rect.y1),
                        name=f"image_{xref}",
                        width=width,
                        height=height,
                        data=image_data,
                        png_path=png_path,
                    )
                )
            except Exception:
                continue

        return images

    def extract_annotations(self) -> List[Annotation]:
        """Extract annotations from the page."""
        annotations = []

        for annot in self._page.annots() or []:
            annot_type = annot.type[1] if annot.type else "Unknown"
            rect = annot.rect

            contents = annot.info.get("content", "")
            uri = None

            # Check for link
            if annot.type[0] == pymupdf.PDF_ANNOT_LINK:
                link = annot.info
                uri = link.get("uri")

            annotations.append(
                Annotation(
                    type=annot_type,
                    rect=(rect.x0, rect.y0, rect.x1, rect.y1),
                    contents=contents,
                    uri=uri,
                )
            )

        return annotations

    def add_highlight(
        self,
        rects: List[Tuple[float, float, float, float]],
        color: Tuple[float, float, float] = (1.0, 1.0, 0.0),  # Yellow
    ) -> None:
        """Add highlight annotation to the page.

        Args:
            rects: List of rectangles (x0, y0, x1, y1) to highlight
            color: RGB color tuple (0-1 range), default yellow
        """
        for rect in rects:
            annot = self._page.add_highlight_annot(pymupdf.Rect(rect))
            annot.set_colors(stroke=color)
            annot.update()

    def add_underline(
        self,
        rects: List[Tuple[float, float, float, float]],
        color: Tuple[float, float, float] = (0.0, 0.0, 1.0),  # Blue
    ) -> None:
        """Add underline annotation to the page.

        Args:
            rects: List of rectangles (x0, y0, x1, y1) to underline
            color: RGB color tuple (0-1 range), default blue
        """
        for rect in rects:
            annot = self._page.add_underline_annot(pymupdf.Rect(rect))
            annot.set_colors(stroke=color)
            annot.update()

    def add_strikethrough(
        self,
        rects: List[Tuple[float, float, float, float]],
        color: Tuple[float, float, float] = (1.0, 0.0, 0.0),  # Red
    ) -> None:
        """Add strikethrough annotation to the page.

        Args:
            rects: List of rectangles (x0, y0, x1, y1) to strikethrough
            color: RGB color tuple (0-1 range), default red
        """
        for rect in rects:
            annot = self._page.add_strikeout_annot(pymupdf.Rect(rect))
            annot.set_colors(stroke=color)
            annot.update()

    def add_squiggly(
        self,
        rects: List[Tuple[float, float, float, float]],
        color: Tuple[float, float, float] = (0.0, 0.8, 0.0),  # Green
    ) -> None:
        """Add squiggly underline annotation to the page.

        Args:
            rects: List of rectangles (x0, y0, x1, y1) for squiggly
            color: RGB color tuple (0-1 range), default green
        """
        for rect in rects:
            annot = self._page.add_squiggly_annot(pymupdf.Rect(rect))
            annot.set_colors(stroke=color)
            annot.update()

    def add_text_note(
        self,
        point: Tuple[float, float],
        text: str,
        icon: str = "Note",
        color: Tuple[float, float, float] = (1.0, 0.92, 0.0),  # Yellow
    ) -> None:
        """Add a text (sticky note) annotation to the page.

        Args:
            point: (x, y) position for the note icon
            text: The comment text
            icon: Icon type ("Note", "Comment", "Help", "Insert", "Paragraph", etc.)
            color: RGB color tuple (0-1 range), default yellow
        """
        annot = self._page.add_text_annot(pymupdf.Point(point), text, icon=icon)
        annot.set_colors(stroke=color)
        annot.update()

    def add_ink(
        self,
        paths: List[List[Tuple[float, float]]],
        color: Tuple[float, float, float] = (0.0, 0.0, 0.0),  # Black
        width: float = 2.0,
    ) -> None:
        """Add an ink (freehand drawing) annotation to the page.

        Args:
            paths: List of paths, each path is a list of (x, y) points
            color: RGB color tuple (0-1 range), default black
            width: Line width in points
        """
        # PyMuPDF expects list of lists of (x, y) tuples, not Point objects
        ink_list = []
        for path in paths:
            # Ensure each point is a tuple of floats
            ink_list.append([(float(x), float(y)) for x, y in path])

        annot = self._page.add_ink_annot(ink_list)
        annot.set_colors(stroke=color)
        annot.set_border(width=width)
        annot.update()


class PyMuPDFDocument:
    """PDF Document using PyMuPDF."""

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
        """Get document outlines (bookmarks/table of contents)."""
        outlines = []

        toc = self._doc.get_toc(simple=False)

        # Build hierarchy
        stack: List[Tuple[int, OutlineItem]] = []

        for item in toc:
            level = item[0]
            title = item[1]
            page_num = item[2] - 1 if item[2] > 0 else None  # Convert to 0-indexed

            outline_item = OutlineItem(
                title=title,
                page_index=page_num,
                level=level,
            )

            # Find parent
            while stack and stack[-1][0] >= level:
                stack.pop()

            if stack:
                parent = stack[-1][1]
                parent.children.append(outline_item)
            else:
                outlines.append(outline_item)

            stack.append((level, outline_item))

        return outlines

    def save(self, path: Optional[Union[str, Path]] = None) -> None:
        """Save the document.

        Args:
            path: Path to save to. If None, saves to original path (if available).
        """
        if path is None:
            if self._path is None:
                raise ValueError("No path specified and document was not loaded from a file")
            path = self._path

        # Use incremental save if saving to same file, otherwise full save
        if self._path and Path(path) == self._path:
            self._doc.save(str(path), incremental=True, encryption=0)
        else:
            self._doc.save(str(path))

    def save_as(self, path: Union[str, Path]) -> None:
        """Save the document to a new path.

        Args:
            path: Path to save to.
        """
        self._doc.save(str(path))

    def close(self):
        if self._doc:
            self._doc.close()
        self._pages.clear()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


@dataclass
class RenderResult:
    """Result of rendering a page."""

    shapes: List[Any]
    images: List[Tuple[str, float, float, float, float]]


def render_page_with_pymupdf(page: PyMuPDFPage, scale: float = 1.0) -> RenderResult:
    """Render a PDF page to Flet canvas shapes using PyMuPDF."""
    shapes = []
    images = []

    # Render graphics FIRST (behind text)
    for gfx in page.extract_graphics():
        x0, y0, x1, y1 = gfx.bbox
        cx0 = x0 * scale
        cy0 = y0 * scale
        cx1 = x1 * scale
        cy1 = y1 * scale

        stroke_color = gfx.stroke_color or "#000000"
        fill_color = gfx.fill_color

        linewidth = gfx.linewidth or 0

        if gfx.type == "line":
            shapes.append(
                cv.Line(
                    x1=cx0,
                    y1=cy0,
                    x2=cx1,
                    y2=cy1,
                    paint=ft.Paint(
                        stroke_width=max(linewidth * scale, 1),
                        color=stroke_color,
                    ),
                )
            )
        elif gfx.type == "rect":
            width = cx1 - cx0
            height = cy1 - cy0
            if width > 0 and height > 0:
                if fill_color:
                    shapes.append(
                        cv.Rect(
                            x=cx0,
                            y=cy0,
                            width=width,
                            height=height,
                            paint=ft.Paint(
                                color=fill_color,
                                style=ft.PaintingStyle.FILL,
                            ),
                        )
                    )
                if linewidth > 0 and stroke_color:
                    shapes.append(
                        cv.Rect(
                            x=cx0,
                            y=cy0,
                            width=width,
                            height=height,
                            paint=ft.Paint(
                                stroke_width=linewidth * scale,
                                color=stroke_color,
                                style=ft.PaintingStyle.STROKE,
                            ),
                        )
                    )

    # Collect images
    for img in page.extract_images():
        x0, y0, x1, y1 = img.bbox
        cx0 = x0 * scale
        cy0 = y0 * scale
        img_width = (x1 - x0) * scale
        img_height = (y1 - y0) * scale

        if img.png_path and os.path.exists(img.png_path):
            images.append((img.png_path, cx0, cy0, img_width, img_height))

    # Render annotations (highlights, underlines, etc.) - before text so they appear behind
    for annot in page._page.annots() or []:
        annot_type = annot.type[0] if annot.type else -1
        rect = annot.rect
        colors = annot.colors

        cx0 = rect.x0 * scale
        cy0 = rect.y0 * scale
        cx1 = rect.x1 * scale
        cy1 = rect.y1 * scale
        width = cx1 - cx0
        height = cy1 - cy0

        # Get annotation color
        stroke_color = colors.get("stroke") if colors else None
        if stroke_color and isinstance(stroke_color, (list, tuple)) and len(stroke_color) >= 3:
            r, g, b = [int(c * 255) for c in stroke_color[:3]]
            hex_color = f"#{r:02x}{g:02x}{b:02x}"
        else:
            hex_color = "#ffff00"  # Default yellow

        # Highlight annotation (type 8)
        if annot_type == pymupdf.PDF_ANNOT_HIGHLIGHT:
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

        # Underline annotation (type 9)
        elif annot_type == pymupdf.PDF_ANNOT_UNDERLINE:
            shapes.append(
                cv.Line(
                    x1=cx0,
                    y1=cy1,
                    x2=cx1,
                    y2=cy1,
                    paint=ft.Paint(
                        stroke_width=max(1.5 * scale, 1),
                        color=hex_color,
                    ),
                )
            )

        # Strikethrough annotation (type 11)
        elif annot_type == pymupdf.PDF_ANNOT_STRIKE_OUT:
            mid_y = cy0 + height / 2
            shapes.append(
                cv.Line(
                    x1=cx0,
                    y1=mid_y,
                    x2=cx1,
                    y2=mid_y,
                    paint=ft.Paint(
                        stroke_width=max(1.5 * scale, 1),
                        color=hex_color,
                    ),
                )
            )

        # Squiggly annotation (type 10) - render as wavy line
        elif annot_type == pymupdf.PDF_ANNOT_SQUIGGLY:
            # Simple approximation with multiple small lines
            wave_height = 2 * scale
            step = 4 * scale
            x = cx0
            points = []
            up = True
            while x < cx1:
                y = cy1 - wave_height if up else cy1
                points.append((x, y))
                x += step
                up = not up
            points.append((cx1, cy1 - wave_height if up else cy1))

            for i in range(len(points) - 1):
                shapes.append(
                    cv.Line(
                        x1=points[i][0],
                        y1=points[i][1],
                        x2=points[i + 1][0],
                        y2=points[i + 1][1],
                        paint=ft.Paint(
                            stroke_width=max(1 * scale, 1),
                            color=hex_color,
                        ),
                    )
                )

        # Text annotation (sticky note) - type 0
        elif annot_type == pymupdf.PDF_ANNOT_TEXT:
            # Draw a small note icon
            icon_size = 16 * scale
            # Background
            shapes.append(
                cv.Rect(
                    x=cx0,
                    y=cy0,
                    width=icon_size,
                    height=icon_size,
                    paint=ft.Paint(
                        color=hex_color,
                        style=ft.PaintingStyle.FILL,
                    ),
                )
            )
            # Border
            shapes.append(
                cv.Rect(
                    x=cx0,
                    y=cy0,
                    width=icon_size,
                    height=icon_size,
                    paint=ft.Paint(
                        color="#000000",
                        style=ft.PaintingStyle.STROKE,
                        stroke_width=1,
                    ),
                )
            )
            # Fold corner
            fold_size = 4 * scale
            shapes.append(
                cv.Path(
                    [
                        cv.Path.MoveTo(cx0 + icon_size - fold_size, cy0),
                        cv.Path.LineTo(cx0 + icon_size, cy0 + fold_size),
                        cv.Path.LineTo(cx0 + icon_size - fold_size, cy0 + fold_size),
                        cv.Path.Close(),
                    ],
                    paint=ft.Paint(
                        color="#ffffff",
                        style=ft.PaintingStyle.FILL,
                    ),
                )
            )

        # Ink annotation (freehand drawing) - type 15
        elif annot_type == pymupdf.PDF_ANNOT_INK:
            # Get ink paths from annotation vertices
            ink_list = annot.vertices
            border = annot.border
            stroke_width = border.get("width", 2) if border else 2

            if ink_list:
                for path in ink_list:
                    if len(path) >= 2:
                        for i in range(len(path) - 1):
                            p1 = path[i]
                            p2 = path[i + 1]
                            # Vertices are tuples (x, y), not Point objects
                            shapes.append(
                                cv.Line(
                                    x1=p1[0] * scale,
                                    y1=p1[1] * scale,
                                    x2=p2[0] * scale,
                                    y2=p2[1] * scale,
                                    paint=ft.Paint(
                                        stroke_width=stroke_width * scale,
                                        color=hex_color,
                                        stroke_cap=ft.StrokeCap.ROUND,
                                    ),
                                )
                            )

    # Render text LAST (on top)
    for block in page.extract_text_blocks():
        canvas_x = block.x * scale
        canvas_y = block.y * scale
        font_size = block.font_size * scale

        font_family = _map_font_name(block.font_name)

        style = ft.TextStyle(
            size=font_size,
            color=block.color,
            font_family=font_family,
        )

        # Use bold/italic from TextBlock (already detected from font name or content stream)
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

    return RenderResult(shapes=shapes, images=images)
