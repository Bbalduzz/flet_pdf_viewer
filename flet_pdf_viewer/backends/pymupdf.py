"""
PyMuPDF backend implementation.
"""

from __future__ import annotations

import io
import re
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
    LinearGradient,
    LinkInfo,
    OutlineItem,
    PageInfo,
    RadialGradient,
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
        self._shadings: Optional[
            Dict[str, Union[LinearGradient, RadialGradient]]
        ] = None
        self._text_gradient: Optional[Union[LinearGradient, RadialGradient]] = None

    def _extract_shadings(self) -> Dict[str, Union[LinearGradient, RadialGradient]]:
        """Extract shading/gradient definitions from page resources."""
        if self._shadings is not None:
            return self._shadings

        self._shadings = {}
        doc = self._doc._doc

        try:
            # Get page object to find pattern resources
            page_xref = self._page.xref
            page_obj = doc.xref_object(page_xref)

            # Find all xref references in the page object
            all_refs = re.findall(r"/(\w+)\s+(\d+)\s+0\s+R", page_obj)

            # First pass: find Pattern dictionary reference
            pattern_dict_xref = None
            for name, xref_str in all_refs:
                if name == "Pattern":
                    pattern_dict_xref = int(xref_str)
                    break

            # If we have a Pattern dictionary, look inside it for patterns
            xrefs_to_check = []
            if pattern_dict_xref:
                try:
                    pattern_dict = doc.xref_object(pattern_dict_xref)
                    # Find pattern references inside: /R9 9 0 R or /P1 2 0 R
                    pattern_refs = re.findall(r"/(\w+)\s+(\d+)\s+0\s+R", pattern_dict)
                    xrefs_to_check.extend(pattern_refs)
                except Exception:
                    pass

            # Also check direct references in page object
            xrefs_to_check.extend(all_refs)

            for pattern_name, xref_str in xrefs_to_check:
                xref = int(xref_str)
                try:
                    obj = doc.xref_object(xref)

                    # Check if this is a shading pattern (PatternType 2)
                    if "/PatternType 2" in obj:
                        # Find the shading reference
                        shading_match = re.search(r"/Shading\s+(\d+)\s+0\s+R", obj)
                        if shading_match:
                            shading_xref = int(shading_match.group(1))
                            gradient = self._parse_shading(doc, shading_xref)
                            if gradient:
                                self._shadings[pattern_name] = gradient
                except Exception:
                    continue

        except Exception:
            pass

        return self._shadings

    def _parse_shading(
        self, doc: pymupdf.Document, xref: int
    ) -> Optional[Union[LinearGradient, RadialGradient]]:
        """Parse a shading object into a gradient definition."""
        try:
            obj = doc.xref_object(xref)

            # Get shading type
            type_match = re.search(r"/ShadingType\s+(\d+)", obj)
            if not type_match:
                return None

            shading_type = int(type_match.group(1))

            # Get function reference for colors
            func_match = re.search(r"/Function\s+(\d+)\s+0\s+R", obj)
            if not func_match:
                return None

            func_xref = int(func_match.group(1))
            func_obj = doc.xref_object(func_xref)

            # Extract colors from function (Type 2 exponential interpolation)
            c0_match = re.search(r"/C0\s+\[\s*([\d.\s-]+)\s*\]", func_obj)
            c1_match = re.search(r"/C1\s+\[\s*([\d.\s-]+)\s*\]", func_obj)

            if not c0_match or not c1_match:
                return None

            c0 = tuple(float(x) for x in c0_match.group(1).split())
            c1 = tuple(float(x) for x in c1_match.group(1).split())

            # Ensure RGB (3 components)
            if len(c0) < 3 or len(c1) < 3:
                return None

            colors = [c0[:3], c1[:3]]

            if shading_type == 2:  # Axial (linear) gradient
                coords_match = re.search(r"/Coords\s+\[\s*([\d.\s-]+)\s*\]", obj)
                if coords_match:
                    coords = [float(x) for x in coords_match.group(1).split()]
                    if len(coords) >= 4:
                        # Parse Extend property [extend_start extend_end]
                        extend_start, extend_end = True, True
                        extend_match = re.search(
                            r"/Extend\s+\[\s*(\w+)\s+(\w+)\s*\]", obj
                        )
                        if extend_match:
                            extend_start = extend_match.group(1).lower() == "true"
                            extend_end = extend_match.group(2).lower() == "true"

                        return LinearGradient(
                            x0=coords[0],
                            y0=coords[1],
                            x1=coords[2],
                            y1=coords[3],
                            colors=colors,
                            extend_start=extend_start,
                            extend_end=extend_end,
                        )

            elif shading_type == 3:  # Radial gradient
                coords_match = re.search(r"/Coords\s+\[\s*([\d.\s-]+)\s*\]", obj)
                if coords_match:
                    coords = [float(x) for x in coords_match.group(1).split()]
                    # Radial: [x0, y0, r0, x1, y1, r1]
                    if len(coords) >= 6:
                        return RadialGradient(
                            cx=coords[3],  # Use end circle center
                            cy=coords[4],
                            r=coords[5],
                            colors=colors,
                        )

        except Exception:
            pass

        return None

    def _detect_text_gradient(self) -> Optional[Union[LinearGradient, RadialGradient]]:
        """Detect if text on this page uses a gradient fill."""
        if self._text_gradient is not None:
            return self._text_gradient

        try:
            # Read the content stream
            contents = self._page.read_contents()
            if not contents:
                return None

            content_str = contents.decode("latin-1", errors="replace")

            # Look for pattern color space usage before text
            # Pattern: /Pattern cs /Pname scn ... BT ... text ... ET
            if "/Pattern cs" in content_str or "/Pattern CS" in content_str:
                # Find which pattern is used for non-stroking color
                pattern_match = re.search(r"/(\w+)\s+scn", content_str)
                if pattern_match:
                    pattern_name = pattern_match.group(1)
                    shadings = self._extract_shadings()
                    if pattern_name in shadings:
                        self._text_gradient = shadings[pattern_name]
                        return self._text_gradient

        except Exception:
            pass

        return None

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

        # Detect if page uses gradient for text
        text_gradient = self._detect_text_gradient()

        # Detect symbolic Type3 fonts (where graphics = content, not glyph outlines)
        # Heuristic: symbolic Type3 fonts have stroked drawings, text outline fonts are fill-only
        type3_fonts = set()
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        font = span.get("font", "")
                        if "T3" in font or font.startswith("Unnamed"):
                            type3_fonts.add(font)

        # Only skip Type3 text if drawings have stroke operations (symbolic fonts)
        # Text outline Type3 fonts have fill-only drawings (glyph outlines)
        if type3_fonts:
            drawings = self._page.get_drawings()
            has_stroked_drawings = any(
                d.get("color") is not None and (d.get("width") or 0) > 0
                for d in drawings[:100]  # Check first 100 for performance
            )
            if not has_stroked_drawings:
                # Fill-only drawings = text outlines, render text normally
                type3_fonts = set()

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
                uses_gradient = False

                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text:
                        continue

                    font = span.get("font", "Helvetica")

                    # Skip Type 3 fonts - their graphics are in get_drawings()
                    if font in type3_fonts:
                        continue

                    bbox = span.get("bbox", (0, 0, 0, 0))
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
                            # If color is black (0) and we have a gradient, it likely uses the gradient
                            if color == 0 and text_gradient:
                                uses_gradient = True

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
                            gradient=text_gradient if uses_gradient else None,
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

    def _extract_gradient_fills(self) -> List[GraphicsInfo]:
        """Extract gradient-filled shapes from content stream."""
        graphics = []
        shadings = self._extract_shadings()
        if not shadings:
            return graphics

        try:
            contents = self._page.read_contents()
            if not contents:
                return graphics

            content_str = contents.decode("latin-1", errors="replace")

            # Look for pattern usage: either "/Pattern cs" or "/Rname cs" where Rname is a pattern colorspace
            # Also check for scn which sets the pattern
            # Pattern: /Rname cs /Pname scn ... x y w h re f
            pattern_match = re.search(r"/(\w+)\s+scn", content_str)
            if not pattern_match:
                return graphics

            pattern_name = pattern_match.group(1)
            if pattern_name not in shadings:
                return graphics

            gradient = shadings[pattern_name]

            # Find rectangle fills: x y w h re f
            # The pattern is: number number number number re ... f
            rect_pattern = r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+re\s*\n?f"
            for match in re.finditer(rect_pattern, content_str):
                try:
                    x = float(match.group(1))
                    y = float(match.group(2))
                    w = float(match.group(3))
                    h = float(match.group(4))
                    # PDF coordinates: y increases upward, convert to top-left origin
                    # bbox is (x0, y0, x1, y1) where y0 < y1
                    graphics.append(
                        GraphicsInfo(
                            type="rect",
                            bbox=(x, y, x + w, y + h),
                            fill_gradient=gradient,
                        )
                    )
                except (ValueError, IndexError):
                    continue

        except Exception:
            pass

        return graphics

    def extract_graphics(self) -> List[GraphicsInfo]:
        """Extract vector graphics (rects, lines, paths, curves)."""
        graphics = []

        # First, add gradient-filled shapes
        graphics.extend(self._extract_gradient_fills())

        drawings = self._page.get_drawings()

        # Detect if this page has text-outline Type3 fonts (fill-only drawings)
        # If so, skip those drawings as they're glyph outlines rendered via text
        skip_fill_only = False
        text_dict = self._page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)
        has_type3 = any(
            "T3" in span.get("font", "") or span.get("font", "").startswith("Unnamed")
            for block in text_dict.get("blocks", [])
            if block.get("type") == 0
            for line in block.get("lines", [])
            for span in line.get("spans", [])
        )
        if has_type3:
            # Check if drawings are fill-only (text outlines)
            has_stroked = any(
                d.get("color") is not None and (d.get("width") or 0) > 0
                for d in drawings[:100]
            )
            if not has_stroked:
                skip_fill_only = True  # Skip fill-only drawings (glyph outlines)

        for drawing in drawings:
            rect = drawing.get("rect")
            if not rect:
                continue

            fill = drawing.get("fill")
            color = drawing.get("color")
            width = drawing.get("width") or 0

            # Skip if no stroke and no fill
            if fill is None and color is None:
                continue

            # Skip fill-only drawings if they're Type3 glyph outlines
            if skip_fill_only and fill is not None and (color is None or width == 0):
                continue

            stroke_hex = _color_to_hex(color) if color else None
            fill_hex = _color_to_hex(fill) if fill else None

            # Extract dash pattern
            dashes_str = drawing.get("dashes")
            stroke_dashes = None
            if dashes_str:
                # Parse dash pattern like "[ 1.5 1.5 ] 0"
                import re as re_mod

                dash_match = re_mod.search(r"\[\s*([\d.\s]+)\s*\]", dashes_str)
                if dash_match:
                    stroke_dashes = [float(x) for x in dash_match.group(1).split()]

            items = drawing.get("items", [])
            if not items:
                continue

            # Build path commands from all items in this drawing
            path_commands = []
            points = []

            for item in items:
                cmd = item[0]

                if cmd == "re":  # Rectangle
                    r = item[1]
                    if r.width >= 1 or r.height >= 1:
                        graphics.append(
                            GraphicsInfo(
                                type="rect",
                                bbox=(r.x0, r.y0, r.x1, r.y1),
                                linewidth=width,
                                stroke_color=stroke_hex,
                                fill_color=fill_hex,
                                stroke_dashes=stroke_dashes,
                            )
                        )

                elif cmd == "l":  # Line
                    p1, p2 = item[1], item[2]
                    points.append((p1.x, p1.y))
                    points.append((p2.x, p2.y))
                    path_commands.append(("m", p1.x, p1.y))
                    path_commands.append(("l", p2.x, p2.y))

                elif cmd == "c":  # Cubic bezier curve
                    p1, p2, p3, p4 = item[1], item[2], item[3], item[4]
                    points.extend(
                        [
                            (p1.x, p1.y),
                            (p2.x, p2.y),
                            (p3.x, p3.y),
                            (p4.x, p4.y),
                        ]
                    )
                    path_commands.append(("m", p1.x, p1.y))
                    path_commands.append(("c", p2.x, p2.y, p3.x, p3.y, p4.x, p4.y))

                elif cmd == "qu":  # Quad (4 points)
                    quad = item[1]
                    pts = [
                        (quad.ul.x, quad.ul.y),
                        (quad.ur.x, quad.ur.y),
                        (quad.lr.x, quad.lr.y),
                        (quad.ll.x, quad.ll.y),
                    ]
                    points.extend(pts)
                    path_commands.append(("m", pts[0][0], pts[0][1]))
                    for pt in pts[1:]:
                        path_commands.append(("l", pt[0], pt[1]))
                    path_commands.append(("h",))  # Close path

            # If we collected path commands, create a path graphic
            if path_commands and len(path_commands) > 1:
                # Calculate bounding box from points
                if points:
                    xs = [p[0] for p in points]
                    ys = [p[1] for p in points]
                    bbox = (min(xs), min(ys), max(xs), max(ys))
                else:
                    bbox = (rect.x0, rect.y0, rect.x1, rect.y1)

                graphics.append(
                    GraphicsInfo(
                        type="path",
                        bbox=bbox,
                        linewidth=width,
                        stroke_color=stroke_hex,
                        fill_color=fill_hex,
                        path_commands=path_commands,
                        points=points,
                        stroke_dashes=stroke_dashes,
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

    def get_links(self) -> List[LinkInfo]:
        """Get all links on the page."""
        links = []

        for link in self._page.get_links():
            rect = link.get("from", pymupdf.Rect())
            kind = link.get("kind", 0)

            # Map PyMuPDF link kinds to our type
            # LINK_NONE=0, LINK_GOTO=1, LINK_URI=2, LINK_LAUNCH=3, LINK_NAMED=4, LINK_GOTOR=5
            if kind == pymupdf.LINK_GOTO:
                # Internal link to a page
                page_num = link.get("page", 0)
                links.append(
                    LinkInfo(
                        rect=(rect.x0, rect.y0, rect.x1, rect.y1),
                        kind="goto",
                        page=page_num,
                    )
                )
            elif kind == pymupdf.LINK_URI:
                # External URL
                uri = link.get("uri", "")
                links.append(
                    LinkInfo(
                        rect=(rect.x0, rect.y0, rect.x1, rect.y1),
                        kind="uri",
                        uri=uri,
                    )
                )
            elif kind == pymupdf.LINK_NAMED:
                # Named destination
                name = link.get("name", "")
                links.append(
                    LinkInfo(
                        rect=(rect.x0, rect.y0, rect.x1, rect.y1),
                        kind="named",
                        name=name,
                    )
                )
            elif kind == pymupdf.LINK_LAUNCH:
                # Launch external file/app
                file_spec = link.get("file", "")
                links.append(
                    LinkInfo(
                        rect=(rect.x0, rect.y0, rect.x1, rect.y1),
                        kind="launch",
                        file=file_spec,
                    )
                )
            elif kind == pymupdf.LINK_GOTOR:
                # Link to another PDF file
                file_spec = link.get("file", "")
                page_num = link.get("page", 0)
                links.append(
                    LinkInfo(
                        rect=(rect.x0, rect.y0, rect.x1, rect.y1),
                        kind="goto",  # Treat as goto for simplicity
                        page=page_num,
                        file=file_spec,
                    )
                )

        return links

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

    def __init__(
        self,
        source: Union[str, Path, bytes, io.BytesIO],
        password: Optional[str] = None,
    ):
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

        # Handle encrypted documents
        if self._doc.is_encrypted:
            if password is None:
                raise ValueError("Document is encrypted and requires a password")
            if not self._doc.authenticate(password):
                raise ValueError("Invalid password")

        self._pages: Dict[int, PyMuPDFPage] = {}

    @property
    def page_count(self) -> int:
        return len(self._doc)

    @property
    def is_encrypted(self) -> bool:
        """Whether the document has encryption."""
        return self._doc.is_encrypted

    @property
    def needs_password(self) -> bool:
        """Whether password is needed to access content."""
        return self._doc.needs_pass

    @property
    def permissions(self) -> dict:
        """Document permissions (print, copy, modify, etc.)."""
        return {
            "print": self._doc.permissions & pymupdf.PDF_PERM_PRINT != 0,
            "copy": self._doc.permissions & pymupdf.PDF_PERM_COPY != 0,
            "modify": self._doc.permissions & pymupdf.PDF_PERM_MODIFY != 0,
            "annotate": self._doc.permissions & pymupdf.PDF_PERM_ANNOTATE != 0,
        }

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
