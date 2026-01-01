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
    LineEndStyle,
    LinkInfo,
    OutlineItem,
    PageInfo,
    Point,
    RadialGradient,
    Rect,
    SearchResult,
    TextBlock,
)
from ..types import (
    Path as InkPath,
)
from .base import DocumentBackend, PageBackend  # noqa: E402


def _convert_font_to_ttf(font_data: bytes, font_ext: str, output_path: str) -> bool:
    """Convert font data to TTF format.

    Flet/Flutter works best with TTF fonts. This function converts various
    font formats (CFF, OTF, PFA, PFB) to TTF with TrueType outlines.

    Args:
        font_data: Raw font bytes
        font_ext: Original extension ('cff', 'otf', 'ttf', 'ttc', 'pfa', 'pfb')
        output_path: Path to save the TTF file

    Returns:
        True if conversion succeeded, False otherwise
    """
    try:
        from fontTools.fontBuilder import FontBuilder
        from fontTools.pens.cu2quPen import Cu2QuPen
        from fontTools.pens.ttGlyphPen import TTGlyphPen
        from fontTools.ttLib import TTFont

        # Handle based on format
        if font_ext == "cff":
            # Raw CFF data - parse and convert
            from fontTools.cffLib import CFFFontSet
            from fontTools.pens.recordingPen import RecordingPen

            cff = CFFFontSet()
            cff.decompile(io.BytesIO(font_data), None)

            font_name = cff.fontNames[0]
            top_dict = cff.topDictIndex[0]
            private_dict = top_dict.Private
            char_strings = top_dict.CharStrings

            # Get default width for fallback
            default_width = getattr(private_dict, "defaultWidthX", 500)

            # Build glyph order
            glyph_order = [".notdef"] if ".notdef" not in top_dict.charset else []
            glyph_order.extend(g for g in top_dict.charset if g not in glyph_order)

            # Build TTF with quadratic outlines
            fb = FontBuilder(1000, isTTF=True)
            fb.setupGlyphOrder(glyph_order)

            # Convert each glyph and extract metrics
            pen_glyphs = {}
            metrics = {}
            for g in glyph_order:
                tt_pen = TTGlyphPen(None)
                width = default_width
                if g in char_strings:
                    cs = char_strings[g]
                    try:
                        # First draw to a recording pen to extract the width
                        # (drawing populates cs.width)
                        rec = RecordingPen()
                        cs.draw(rec, char_strings)
                        width = getattr(cs, "width", default_width) or default_width

                        # Now convert to quadratic curves for TTF
                        cu2qu_pen = Cu2QuPen(tt_pen, max_err=1.0, reverse_direction=True)
                        rec.replay(cu2qu_pen)
                    except Exception:
                        pass
                pen_glyphs[g] = tt_pen.glyph()
                metrics[g] = (int(width), 0)  # (advance width, left side bearing)

            fb.setupGlyf(pen_glyphs)
            fb.setupHorizontalMetrics(metrics)
            fb.setupHorizontalHeader(ascent=800, descent=-200)
            fb.setupHead(unitsPerEm=1000)
            fb.setupNameTable({"familyName": font_name, "styleName": "Regular"})

            cmap = {}
            for g in glyph_order:
                if len(g) == 1:
                    cmap[ord(g)] = g
                elif g == "space":
                    cmap[32] = "space"
            fb.setupCharacterMap(cmap)
            fb.setupOS2()
            fb.setupPost()

            fb.save(output_path)
            return True

        elif font_ext in ("pfa", "pfb"):
            # Type1 PostScript fonts (ASCII or binary)
            from fontTools.pens.recordingPen import RecordingPen
            from fontTools.t1Lib import T1Font

            # Type1 fonts from PDFs often lack the cleartomark ending
            # Add it to make fontTools happy
            cleartomark_padding = (
                b"\n"
                + b"0" * 64 + b"\n"
                + b"0" * 64 + b"\n"
                + b"0" * 64 + b"\n"
                + b"0" * 64 + b"\n"
                + b"0" * 64 + b"\n"
                + b"0" * 64 + b"\n"
                + b"0" * 64 + b"\n"
                + b"0" * 64 + b"\n"
                + b"cleartomark\n"
            )
            font_data_fixed = font_data + cleartomark_padding

            # Write to temp file (T1Font requires file path)
            temp_pfa = output_path + ".tmp.pfa"
            with open(temp_pfa, "wb") as f:
                f.write(font_data_fixed)

            try:
                t1 = T1Font(temp_pfa)
                t1.parse()
                font_dict = t1.font

                font_name = font_dict.get("FontName", "Unknown")
                char_strings = font_dict.get("CharStrings", {})

                glyph_order = list(char_strings.keys())
                if ".notdef" not in glyph_order:
                    glyph_order.insert(0, ".notdef")

                fb = FontBuilder(1000, isTTF=True)
                fb.setupGlyphOrder(glyph_order)

                # Convert glyphs and extract metrics
                pen_glyphs = {}
                metrics = {}
                for g in glyph_order:
                    tt_pen = TTGlyphPen(None)
                    width = 500  # default

                    if g in char_strings:
                        cs = char_strings[g]
                        if cs.needsDecompilation():
                            cs.decompile()

                        # Extract width from hsbw command: [sbx, width, 'hsbw', ...]
                        prog = cs.program
                        if len(prog) >= 3 and prog[2] == "hsbw":
                            width = prog[1]  # Second arg is width
                        elif len(prog) >= 5 and prog[4] == "sbw":
                            width = prog[2]  # sbw: sbx, sby, wx, wy

                        try:
                            rec = RecordingPen()
                            cs.draw(rec)
                            cu2qu_pen = Cu2QuPen(
                                tt_pen, max_err=1.0, reverse_direction=True
                            )
                            rec.replay(cu2qu_pen)
                        except Exception:
                            pass

                    pen_glyphs[g] = tt_pen.glyph()
                    metrics[g] = (int(width), 0)

                fb.setupGlyf(pen_glyphs)
                fb.setupHorizontalMetrics(metrics)
                fb.setupHorizontalHeader(ascent=800, descent=-200)
                fb.setupHead(unitsPerEm=1000)
                fb.setupNameTable({"familyName": font_name, "styleName": "Regular"})

                # Build cmap
                cmap = {}
                for g in glyph_order:
                    if len(g) == 1:
                        cmap[ord(g)] = g
                    elif g == "space":
                        cmap[32] = "space"
                fb.setupCharacterMap(cmap)
                fb.setupOS2()
                fb.setupPost()

                fb.save(output_path)
                return True
            finally:
                # Clean up temp file
                if Path(temp_pfa).exists():
                    Path(temp_pfa).unlink()

        elif font_ext == "otf":
            # OTF can have CFF or TrueType outlines
            font = TTFont(io.BytesIO(font_data))

            if "CFF " in font:
                # OTF with CFF outlines - convert to TTF
                from fontTools.pens.cu2quPen import Cu2QuPen

                glyph_order = font.getGlyphOrder()
                cff = font["CFF "].cff
                top_dict = cff.topDictIndex[0]
                char_strings = top_dict.CharStrings

                fb = FontBuilder(font["head"].unitsPerEm, isTTF=True)
                fb.setupGlyphOrder(glyph_order)

                pen_glyphs = {}
                for g in glyph_order:
                    tt_pen = TTGlyphPen(None)
                    if g in char_strings:
                        try:
                            cu2qu_pen = Cu2QuPen(
                                tt_pen, max_err=1.0, reverse_direction=True
                            )
                            char_strings[g].draw(cu2qu_pen, char_strings)
                        except Exception:
                            pass
                    pen_glyphs[g] = tt_pen.glyph()

                fb.setupGlyf(pen_glyphs)

                # Copy metrics from original
                if "hmtx" in font:
                    fb.setupHorizontalMetrics(dict(font["hmtx"].metrics))
                else:
                    fb.setupHorizontalMetrics({g: (500, 0) for g in glyph_order})

                if "hhea" in font:
                    fb.setupHorizontalHeader(
                        ascent=font["hhea"].ascent, descent=font["hhea"].descent
                    )
                else:
                    fb.setupHorizontalHeader(ascent=800, descent=-200)

                fb.setupHead(unitsPerEm=font["head"].unitsPerEm)

                # Get font name
                font_name = glyph_order[1] if len(glyph_order) > 1 else "Unknown"
                if "name" in font:
                    for record in font["name"].names:
                        if record.nameID == 1:
                            try:
                                font_name = record.toUnicode()
                            except Exception:
                                pass
                            break

                fb.setupNameTable({"familyName": font_name, "styleName": "Regular"})

                if "cmap" in font:
                    best_cmap = font.getBestCmap()
                    if best_cmap:
                        fb.setupCharacterMap(best_cmap)
                    else:
                        fb.setupCharacterMap({})
                else:
                    fb.setupCharacterMap({})

                fb.setupOS2()
                fb.setupPost()
                fb.save(output_path)
                return True
            else:
                # OTF with TrueType outlines - just save as is
                font.save(output_path)
                return True

        elif font_ext in ("ttf", "ttc"):
            # Already TTF - just write it
            with open(output_path, "wb") as f:
                f.write(font_data)
            return True

        return False
    except Exception:
        return False


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


class PyMuPDFPage(PageBackend):
    """PyMuPDF page implementation."""

    def __init__(self, doc: "PyMuPDFBackend", page: pymupdf.Page, index: int):
        self._doc = doc
        self._page = page
        self._index = index
        self._shadings: Optional[Dict[str, Union[LinearGradient, RadialGradient]]] = (
            None
        )
        self._text_gradient: Optional[Union[LinearGradient, RadialGradient]] = None
        # Track temp image files for cleanup
        self._temp_image_files: List[str] = []

        # Extraction cache - avoids re-parsing PDF on every render
        self._cached_text_blocks: Optional[List[TextBlock]] = None
        self._cached_chars: Optional[List[CharInfo]] = None
        self._cached_graphics: Optional[List[GraphicsInfo]] = None
        self._cached_images: Optional[List[ImageInfo]] = None
        self._cached_annotations: Optional[List[AnnotationInfo]] = None
        self._cached_links: Optional[List[LinkInfo]] = None

    def invalidate_cache(self):
        """Invalidate all extraction caches. Call after modifying page content."""
        self._cached_text_blocks = None
        self._cached_chars = None
        self._cached_graphics = None
        self._cached_images = None
        self._cached_annotations = None
        self._cached_links = None
        # Also reset gradient detection since it may have changed
        self._shadings = None
        self._text_gradient = None

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

            # First, find and follow the Resources reference
            resources_obj = page_obj
            for name, xref_str in all_refs:
                if name == "Resources":
                    resources_xref = int(xref_str)
                    resources_obj = doc.xref_object(resources_xref)
                    break

            # Find Pattern dictionary in resources
            pattern_dict_xref = None
            resource_refs = re.findall(r"/(\w+)\s+(\d+)\s+0\s+R", resources_obj)
            for name, xref_str in resource_refs:
                if name == "Pattern":
                    pattern_dict_xref = int(xref_str)
                    break

            # Also check for inline Pattern dictionary: /Pattern << /P1 5 0 R >>
            if not pattern_dict_xref:
                inline_pattern = re.search(
                    r"/Pattern\s*<<([^>]+)>>", resources_obj, re.DOTALL
                )
                if inline_pattern:
                    pattern_content = inline_pattern.group(1)
                    pattern_refs = re.findall(r"/(\w+)\s+(\d+)\s+0\s+R", pattern_content)
                    for pattern_name, xref_str in pattern_refs:
                        xref = int(xref_str)
                        try:
                            obj = doc.xref_object(xref)
                            if "/PatternType 2" in obj:
                                shading_match = re.search(
                                    r"/Shading\s+(\d+)\s+0\s+R", obj
                                )
                                if shading_match:
                                    shading_xref = int(shading_match.group(1))
                                    gradient = self._parse_shading(doc, shading_xref)
                                    if gradient:
                                        self._shadings[pattern_name] = gradient
                        except Exception:
                            continue

            # If we have a Pattern dictionary reference, look inside it for patterns
            if pattern_dict_xref:
                try:
                    pattern_dict = doc.xref_object(pattern_dict_xref)
                    pattern_refs = re.findall(r"/(\w+)\s+(\d+)\s+0\s+R", pattern_dict)
                    for pattern_name, xref_str in pattern_refs:
                        xref = int(xref_str)
                        try:
                            obj = doc.xref_object(xref)
                            if "/PatternType 2" in obj:
                                shading_match = re.search(
                                    r"/Shading\s+(\d+)\s+0\s+R", obj
                                )
                                if shading_match:
                                    shading_xref = int(shading_match.group(1))
                                    gradient = self._parse_shading(doc, shading_xref)
                                    if gradient:
                                        self._shadings[pattern_name] = gradient
                        except Exception:
                            continue
                except Exception:
                    pass

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

            # Determine function type
            func_type_match = re.search(r"/FunctionType\s+(\d+)", func_obj)
            func_type = int(func_type_match.group(1)) if func_type_match else 2

            colors = []

            if func_type == 0:
                # Sampled function - read sample data to extract colors
                # Get number of samples and extract first/last colors
                size_match = re.search(r"/Size\s+\[\s*(\d+)\s*\]", func_obj)
                if size_match:
                    num_samples = int(size_match.group(1))
                    try:
                        # Read the stream data (contains RGB samples)
                        stream_data = doc.xref_stream(func_xref)
                        if stream_data and len(stream_data) >= 6:
                            # First 3 bytes = start color (RGB 0-255)
                            c0 = (
                                stream_data[0] / 255.0,
                                stream_data[1] / 255.0,
                                stream_data[2] / 255.0,
                            )
                            # Last 3 bytes = end color (RGB 0-255)
                            c1 = (
                                stream_data[-3] / 255.0,
                                stream_data[-2] / 255.0,
                                stream_data[-1] / 255.0,
                            )
                            colors = [c0, c1]
                    except Exception:
                        pass

            elif func_type == 2:
                # Exponential interpolation function with C0 and C1
                c0_match = re.search(r"/C0\s+\[\s*([\d.\s-]+)\s*\]", func_obj)
                c1_match = re.search(r"/C1\s+\[\s*([\d.\s-]+)\s*\]", func_obj)

                if c0_match and c1_match:
                    c0 = tuple(float(x) for x in c0_match.group(1).split())
                    c1 = tuple(float(x) for x in c1_match.group(1).split())
                    if len(c0) >= 3 and len(c1) >= 3:
                        colors = [c0[:3], c1[:3]]

            elif func_type == 3:
                # Stitching function - get colors from subfunctions
                # Find the Functions array
                funcs_match = re.search(r"/Functions\s+\[([\s\d]+0\s+R)+\]", func_obj)
                if funcs_match:
                    sub_refs = re.findall(r"(\d+)\s+0\s+R", funcs_match.group(0))
                    for sub_xref_str in sub_refs:
                        sub_xref = int(sub_xref_str)
                        try:
                            sub_obj = doc.xref_object(sub_xref)
                            c0_match = re.search(
                                r"/C0\s+\[\s*([\d.\s-]+)\s*\]", sub_obj
                            )
                            c1_match = re.search(
                                r"/C1\s+\[\s*([\d.\s-]+)\s*\]", sub_obj
                            )
                            if c0_match:
                                c0 = tuple(
                                    float(x) for x in c0_match.group(1).split()
                                )
                                if len(c0) >= 3:
                                    if not colors:
                                        colors.append(c0[:3])
                            if c1_match:
                                c1 = tuple(
                                    float(x) for x in c1_match.group(1).split()
                                )
                                if len(c1) >= 3:
                                    colors.append(c1[:3])
                        except Exception:
                            continue

            if not colors or len(colors) < 2:
                return None

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

    def _get_text_color_map(self) -> Dict[str, str]:
        """Parse content stream to determine which text uses gradient vs solid color.

        Returns a dict mapping text content to color type: 'gradient' or 'solid'.
        """
        color_map = {}

        try:
            contents = self._page.read_contents()
            if not contents:
                return color_map

            content_str = contents.decode("latin-1", errors="replace")

            # Track current fill state: 'pattern' or 'solid'
            current_fill = "solid"

            # Split into tokens/operations
            # Look for color operations and text operations
            lines = content_str.replace("\r", "\n").split("\n")

            in_text_block = False
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Pattern colorspace + pattern: indicates gradient
                if "cs" in line and "scn" in line:
                    current_fill = "pattern"
                elif " scn" in line or line.endswith(" scn"):
                    # Setting a pattern
                    current_fill = "pattern"
                elif " rg" in line or line.endswith(" rg"):
                    # Setting solid RGB color
                    current_fill = "solid"
                elif " g" in line and "rg" not in line:
                    # Setting solid gray
                    current_fill = "solid"
                elif "BT" in line:
                    in_text_block = True
                elif "ET" in line:
                    in_text_block = False
                elif in_text_block and ("Tj" in line or "TJ" in line):
                    # Extract text from Tj or TJ operator
                    # Format: (text)Tj or [(text)]TJ
                    import re as re_mod

                    text_matches = re_mod.findall(r"\(([^)]*)\)", line)
                    for text in text_matches:
                        if text:
                            color_map[text] = current_fill

        except Exception:
            pass

        return color_map

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
            doc = self._doc._doc

            # Check if Pattern colorspace is used
            uses_pattern_colorspace = False

            # Direct Pattern colorspace: /Pattern cs
            if "/Pattern cs" in content_str or "/Pattern CS" in content_str:
                uses_pattern_colorspace = True

            # Named colorspace that might be Pattern: /Rname cs
            # Need to check if the colorspace resolves to [ /Pattern ]
            if not uses_pattern_colorspace:
                cs_match = re.search(r"/(\w+)\s+cs", content_str)
                if cs_match:
                    cs_name = cs_match.group(1)
                    # Look up colorspace in page resources
                    page_xref = self._page.xref
                    page_obj = doc.xref_object(page_xref)

                    # Find Resources reference
                    res_match = re.search(r"/Resources\s+(\d+)\s+0\s+R", page_obj)
                    if res_match:
                        res_xref = int(res_match.group(1))
                        res_obj = doc.xref_object(res_xref)
                    else:
                        # Resources might be inline
                        res_obj = page_obj

                    # Find ColorSpace dictionary
                    cs_dict_match = re.search(
                        r"/ColorSpace\s+(\d+)\s+0\s+R", res_obj
                    )
                    if cs_dict_match:
                        cs_dict_xref = int(cs_dict_match.group(1))
                        cs_dict = doc.xref_object(cs_dict_xref)

                        # Find the named colorspace reference
                        named_cs_match = re.search(
                            rf"/{cs_name}\s+(\d+)\s+0\s+R", cs_dict
                        )
                        if named_cs_match:
                            named_cs_xref = int(named_cs_match.group(1))
                            named_cs_obj = doc.xref_object(named_cs_xref)
                            # Check if it's [ /Pattern ]
                            if "/Pattern" in named_cs_obj:
                                uses_pattern_colorspace = True

            if uses_pattern_colorspace:
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
        # Return cached result if available
        if self._cached_text_blocks is not None:
            return self._cached_text_blocks

        blocks = []
        text_dict = self._page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)

        # Detect if page uses gradient for text
        text_gradient = self._detect_text_gradient()

        # Get color map to know which text uses gradient vs solid color
        text_color_map = self._get_text_color_map() if text_gradient else {}

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

                            # Check if this text uses gradient based on content stream parsing
                            if text_gradient and text_color_map:
                                # Check if any part of this text uses pattern fill
                                # Use flexible matching since text can be truncated differently
                                if text_color_map.get(text) == "pattern":
                                    uses_gradient = True
                                else:
                                    # Try prefix matching
                                    for map_text, fill_type in text_color_map.items():
                                        if fill_type == "pattern":
                                            # Check if either starts with the other
                                            if (
                                                text.startswith(map_text[:20])
                                                or map_text.startswith(text[:20])
                                            ):
                                                uses_gradient = True
                                                break
                            elif color == 0 and text_gradient and not text_color_map:
                                # Fallback: if color is black and we have a gradient but no map
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
                            font_flags=flags,  # Pass PyMuPDF font flags for classification
                        )
                    )

        self._cached_text_blocks = blocks
        return blocks

    def extract_chars(self) -> List[CharInfo]:
        """Extract individual characters."""
        # Return cached result if available
        if self._cached_chars is not None:
            return self._cached_chars

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

        self._cached_chars = chars
        return chars

    def extract_images(self) -> List[ImageInfo]:
        """Extract images from the page.

        Images are rendered in page context to preserve colorspace transformations
        (CalRGB, ICC profiles, etc.).
        """
        # Return cached result if available, but validate files still exist
        if self._cached_images is not None:
            # Check if cached image files still exist (may have been cleaned up)
            if all(
                Path(img.png_path).exists()
                for img in self._cached_images
                if img.png_path
            ):
                return self._cached_images
            # Files were deleted, need to re-extract
            self._cached_images = None
            self._temp_image_files.clear()

        images = []

        # Use get_image_info for accurate positions and colorspace info
        image_info_list = self._page.get_image_info()

        for img_info in image_info_list:
            try:
                bbox = img_info.get("bbox")
                if not bbox:
                    continue

                width = img_info.get("width", 0)
                height = img_info.get("height", 0)

                # Render the image in page context to apply colorspace transformations
                # This handles CalRGB, ICC profiles, and other colorspaces correctly
                clip = pymupdf.Rect(bbox)

                # Calculate scale to get original resolution
                scale_x = width / clip.width if clip.width > 0 else 1
                scale_y = height / clip.height if clip.height > 0 else 1
                scale = max(scale_x, scale_y, 1)  # At least 1x

                mat = pymupdf.Matrix(scale, scale)
                pix = self._page.get_pixmap(matrix=mat, clip=clip, alpha=False)

                # Save as PNG and track for cleanup
                png_path = tempfile.mktemp(suffix=".png")
                pix.save(png_path)
                self._temp_image_files.append(png_path)

                images.append(
                    ImageInfo(
                        bbox=(bbox[0], bbox[1], bbox[2], bbox[3]),
                        width=pix.width,
                        height=pix.height,
                        png_path=png_path,
                    )
                )
            except Exception:
                continue

        self._cached_images = images
        return images

    def cleanup_temp_files(self):
        """Clean up temporary image files created by this page."""
        for path in self._temp_image_files:
            try:
                if Path(path).exists():
                    Path(path).unlink()
            except Exception:
                pass
        self._temp_image_files.clear()

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

    def _detect_even_odd_border(
        self, drawing: dict
    ) -> Optional[Tuple[List, float]]:
        """Detect even-odd fill patterns that create borders.

        When even_odd is True and the path contains two nested subpaths,
        it creates a border effect. We detect this and return the outer
        path with calculated border width.

        Returns:
            None if not an even-odd border, or (outer_path_items, border_width)
        """
        if not drawing.get("even_odd"):
            return None

        items = drawing.get("items", [])
        if not items:
            return None

        # Even-odd borders typically have 2 subpaths (16 items for rounded rects)
        # Each subpath has 8 items (4 curves + 4 lines for rounded rect)
        if len(items) != 16:
            return None

        # Check if it's two similar subpaths (same structure)
        first_half = items[:8]
        second_half = items[8:]

        # Verify both halves have same command structure
        if [i[0] for i in first_half] != [i[0] for i in second_half]:
            return None

        # Calculate border width from the difference in positions
        # Compare first point of outer vs inner path
        outer_start = first_half[0][1]  # Start point of first item
        inner_start = second_half[0][1]  # Start point of second subpath

        border_width = abs(inner_start.x - outer_start.x)
        if border_width < 0.1:
            # Try y difference
            border_width = abs(inner_start.y - outer_start.y)

        if border_width < 0.1:
            return None

        return (first_half, border_width)

    def _detect_soft_mask_compositing(
        self, drawings: list
    ) -> Tuple[set, dict]:
        """Detect soft mask compositing patterns and determine correct rendering.

        PDFs use soft masks (SMask) for transparency compositing. A common pattern:
        - Colored background path
        - Black/white rectangles (compositing artifacts)
        - Black filled path (the mask shape, should render as white)
        - More white rectangles

        Returns:
            skip_indices: Set of drawing indices to skip (mask constructs)
            color_overrides: Dict mapping index -> new fill color
        """
        skip_indices = set()
        color_overrides = {}

        # Find colored backgrounds (non-black, non-white, non-gray fills)
        colored_backgrounds = []
        for i, d in enumerate(drawings):
            fill = d.get("fill")
            if fill and len(d.get("items", [])) > 1:  # Complex path (not simple rect)
                # Check if it's a "colorful" fill (not grayscale)
                r, g, b = fill
                if not (r == g == b) or (r > 0.3 and r < 0.9):  # Has color or mid-gray
                    colored_backgrounds.append((i, d))

        for bg_idx, bg_drawing in colored_backgrounds:
            bg_rect = bg_drawing.get("rect")
            if not bg_rect:
                continue

            # Look for soft mask pattern in subsequent drawings
            # Pattern: black rect -> white rect -> black path -> white rect
            # within the background's bounding box
            mask_candidates = []
            for j in range(bg_idx + 1, min(bg_idx + 10, len(drawings))):
                d = drawings[j]
                rect = d.get("rect")
                if not rect:
                    continue

                # Check if this drawing is inside/overlapping the background
                if not (
                    rect.x0 < bg_rect.x1
                    and rect.x1 > bg_rect.x0
                    and rect.y0 < bg_rect.y1
                    and rect.y1 > bg_rect.y0
                ):
                    continue

                fill = d.get("fill")
                items = d.get("items", [])
                is_rect = len(items) == 1 and items[0][0] == "re"
                is_path = len(items) > 1

                if fill == (1.0, 1.0, 1.0) and is_rect:
                    # White rect - likely mask construct
                    mask_candidates.append(("white_rect", j))
                elif fill == (0.0, 0.0, 0.0) and is_rect:
                    # Black rect - border or shadow
                    mask_candidates.append(("black_rect", j))
                elif fill == (0.0, 0.0, 0.0) and is_path:
                    # Black path - could be the mask shape (checkmark, icon, etc.)
                    mask_candidates.append(("black_path", j))

            # Detect the compositing pattern:
            # black_rect -> white_rect -> black_path -> white_rect
            if len(mask_candidates) >= 3:
                types = [c[0] for c in mask_candidates]
                # Look for: (black_rect?, white_rect, black_path, white_rect)
                for k, (ctype, cidx) in enumerate(mask_candidates):
                    if ctype == "black_path":
                        # Check if surrounded by white rects
                        has_white_before = any(
                            t == "white_rect" for t, _ in mask_candidates[:k]
                        )
                        has_white_after = any(
                            t == "white_rect" for t, _ in mask_candidates[k + 1 :]
                        )
                        if has_white_before and has_white_after:
                            # This is a soft mask pattern!
                            # Skip white rects, render black path as white
                            for t, idx in mask_candidates:
                                if t == "white_rect":
                                    skip_indices.add(idx)
                                elif t == "black_rect":
                                    skip_indices.add(idx)
                            # Render the black path as white
                            color_overrides[cidx] = "#ffffff"
                            break

        return skip_indices, color_overrides

    def extract_graphics(self) -> List[GraphicsInfo]:
        """Extract vector graphics (rects, lines, paths, curves)."""
        # Return cached result if available
        if self._cached_graphics is not None:
            return self._cached_graphics

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

        # Detect soft mask compositing patterns (checkboxes, icons, etc.)
        skip_indices, color_overrides = self._detect_soft_mask_compositing(drawings)

        for idx, drawing in enumerate(drawings):
            # Skip drawings that are soft mask constructs
            if idx in skip_indices:
                continue
            rect = drawing.get("rect")
            if not rect:
                continue

            fill = drawing.get("fill")
            color = drawing.get("color")
            width = drawing.get("width") or 0
            fill_opacity = drawing.get("fill_opacity", 1.0)
            stroke_opacity = drawing.get("stroke_opacity", 1.0)

            # Skip if no stroke and no fill
            if fill is None and color is None:
                continue

            # Skip fully transparent fills
            if fill is not None and fill_opacity == 0.0:
                fill = None
            # Skip fully transparent strokes
            if color is not None and stroke_opacity == 0.0:
                color = None
                width = 0

            # Skip if both are now None after opacity check
            if fill is None and color is None:
                continue

            # Skip fill-only drawings if they're Type3 glyph outlines
            if skip_fill_only and fill is not None and (color is None or width == 0):
                continue

            # Handle even-odd fill patterns (borders)
            even_odd_border = self._detect_even_odd_border(drawing)
            if even_odd_border:
                outer_items, border_width = even_odd_border
                # Convert to stroked path instead of filled
                fill_hex = None
                stroke_hex = _color_to_hex(fill)  # Use fill color as stroke
                width = border_width
                # Replace items with just the outer path
                drawing = dict(drawing)
                drawing["items"] = outer_items
            else:
                stroke_hex = _color_to_hex(color) if color else None
                fill_hex = _color_to_hex(fill) if fill else None

            # Apply color override from soft mask compositing detection
            if idx in color_overrides:
                fill_hex = color_overrides[idx]

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
            current_pos = None  # Track current position for proper path building

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

                elif cmd == "l":  # Line from p1 to p2
                    p1, p2 = item[1], item[2]
                    points.append((p1.x, p1.y))
                    points.append((p2.x, p2.y))
                    # Only add moveto if we're not already at p1
                    if current_pos != (p1.x, p1.y):
                        path_commands.append(("m", p1.x, p1.y))
                    path_commands.append(("l", p2.x, p2.y))
                    current_pos = (p2.x, p2.y)

                elif cmd == "c":  # Cubic bezier: start at p1, controls p2/p3, end at p4
                    p1, p2, p3, p4 = item[1], item[2], item[3], item[4]
                    points.extend(
                        [
                            (p1.x, p1.y),
                            (p2.x, p2.y),
                            (p3.x, p3.y),
                            (p4.x, p4.y),
                        ]
                    )
                    # Only add moveto if we're not already at p1
                    if current_pos != (p1.x, p1.y):
                        path_commands.append(("m", p1.x, p1.y))
                    path_commands.append(("c", p2.x, p2.y, p3.x, p3.y, p4.x, p4.y))
                    current_pos = (p4.x, p4.y)

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
                    current_pos = (pts[0][0], pts[0][1])  # Closed path returns to start

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

        self._cached_graphics = graphics
        return graphics

    def get_annotations(self) -> List[AnnotationInfo]:
        """Get all annotations on the page."""
        # Return cached result if available
        if self._cached_annotations is not None:
            return self._cached_annotations

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

        self._cached_annotations = annotations
        return annotations

    def get_links(self) -> List[LinkInfo]:
        """Get all links on the page."""
        # Return cached result if available
        if self._cached_links is not None:
            return self._cached_links

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

        self._cached_links = links
        return links

    def search_text(
        self,
        query: str,
        case_sensitive: bool = False,
        whole_word: bool = False,
    ) -> List[SearchResult]:
        """Search for text on this page.

        Uses PyMuPDF's search_for method which returns quads/rects
        for each match occurrence.
        """
        if not query:
            return []

        results = []

        # Build search flags
        flags = pymupdf.TEXT_PRESERVE_WHITESPACE
        if not case_sensitive:
            flags |= pymupdf.TEXT_PRESERVE_LIGATURES

        # PyMuPDF search_for returns list of Rect or Quad objects
        # quads=True returns Quad for better accuracy with rotated text
        matches = self._page.search_for(query, quads=True)

        for match in matches:
            # Each match is a Quad object
            if hasattr(match, "rect"):
                # It's a Quad, get the bounding rect
                rect = match.rect
                quads = [(match.ul.x, match.ul.y, match.lr.x, match.lr.y)]
            else:
                # It's already a Rect
                rect = match
                quads = None

            # Check whole word if required
            if whole_word:
                # Get text around the match to verify word boundaries
                # We extract text from the page and check the match context
                page_text = self._page.get_text("text")
                # Simple heuristic: check if the match is a whole word
                # This is approximate - PyMuPDF doesn't have built-in whole word search
                match_text = query
                # For now, include all matches - whole word filtering would need
                # character-level position checking which is complex
                pass

            results.append(
                SearchResult(
                    page_index=self._index,
                    rect=(rect.x0, rect.y0, rect.x1, rect.y1),
                    text=query,
                    quads=quads,
                )
            )

        return results

    def add_highlight(self, rects: List[Rect], color: Color) -> None:
        for rect in rects:
            annot = self._page.add_highlight_annot(pymupdf.Rect(rect))
            annot.set_colors(stroke=color)
            annot.update()
        self._cached_annotations = None  # Invalidate annotation cache

    def add_underline(self, rects: List[Rect], color: Color) -> None:
        for rect in rects:
            annot = self._page.add_underline_annot(pymupdf.Rect(rect))
            annot.set_colors(stroke=color)
            annot.update()
        self._cached_annotations = None  # Invalidate annotation cache

    def add_strikethrough(self, rects: List[Rect], color: Color) -> None:
        for rect in rects:
            annot = self._page.add_strikeout_annot(pymupdf.Rect(rect))
            annot.set_colors(stroke=color)
            annot.update()
        self._cached_annotations = None  # Invalidate annotation cache

    def add_squiggly(self, rects: List[Rect], color: Color) -> None:
        for rect in rects:
            annot = self._page.add_squiggly_annot(pymupdf.Rect(rect))
            annot.set_colors(stroke=color)
            annot.update()
        self._cached_annotations = None  # Invalidate annotation cache

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
        self._cached_annotations = None  # Invalidate annotation cache

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
        self._cached_annotations = None  # Invalidate annotation cache

    # Shape annotations

    def _line_end_to_pymupdf(self, style: LineEndStyle) -> int:
        """Convert LineEndStyle to PyMuPDF constant."""
        mapping = {
            LineEndStyle.NONE: pymupdf.PDF_ANNOT_LE_NONE,
            LineEndStyle.SQUARE: pymupdf.PDF_ANNOT_LE_SQUARE,
            LineEndStyle.CIRCLE: pymupdf.PDF_ANNOT_LE_CIRCLE,
            LineEndStyle.DIAMOND: pymupdf.PDF_ANNOT_LE_DIAMOND,
            LineEndStyle.OPEN_ARROW: pymupdf.PDF_ANNOT_LE_OPEN_ARROW,
            LineEndStyle.CLOSED_ARROW: pymupdf.PDF_ANNOT_LE_CLOSED_ARROW,
            LineEndStyle.BUTT: pymupdf.PDF_ANNOT_LE_BUTT,
            LineEndStyle.R_OPEN_ARROW: pymupdf.PDF_ANNOT_LE_R_OPEN_ARROW,
            LineEndStyle.R_CLOSED_ARROW: pymupdf.PDF_ANNOT_LE_R_CLOSED_ARROW,
            LineEndStyle.SLASH: pymupdf.PDF_ANNOT_LE_SLASH,
        }
        return mapping.get(style, pymupdf.PDF_ANNOT_LE_NONE)

    def add_freetext(
        self,
        rect: Rect,
        text: str,
        font_size: float = 12.0,
        font_name: str = "helv",
        text_color: Color = (0.0, 0.0, 0.0),
        fill_color: Optional[Color] = None,
        border_color: Optional[Color] = None,
        border_width: float = 0.0,
        align: int = 0,
    ) -> None:
        """Add free text annotation.

        Note: FreeText annotations in PyMuPDF have limited border support.
        border_color is ignored due to PyMuPDF limitations.
        """
        annot = self._page.add_freetext_annot(
            pymupdf.Rect(rect),
            text,
            fontsize=font_size,
            fontname=font_name,
            text_color=text_color,
            fill_color=fill_color,
            align=align,
        )
        # FreeText annotations don't support set_colors for stroke
        # Only set border width if specified
        if border_width > 0:
            annot.set_border(width=border_width)
        annot.update()
        self._cached_annotations = None  # Invalidate annotation cache

    def add_rect(
        self,
        rect: Rect,
        stroke_color: Optional[Color] = (0.0, 0.0, 0.0),
        fill_color: Optional[Color] = None,
        width: float = 1.0,
    ) -> None:
        """Add rectangle annotation."""
        annot = self._page.add_rect_annot(pymupdf.Rect(rect))
        annot.set_colors(stroke=stroke_color, fill=fill_color)
        annot.set_border(width=width)
        annot.update()
        self._cached_annotations = None  # Invalidate annotation cache

    def add_circle(
        self,
        rect: Rect,
        stroke_color: Optional[Color] = (0.0, 0.0, 0.0),
        fill_color: Optional[Color] = None,
        width: float = 1.0,
    ) -> None:
        """Add circle/ellipse annotation."""
        annot = self._page.add_circle_annot(pymupdf.Rect(rect))
        annot.set_colors(stroke=stroke_color, fill=fill_color)
        annot.set_border(width=width)
        annot.update()
        self._cached_annotations = None  # Invalidate annotation cache

    def add_line(
        self,
        start: Point,
        end: Point,
        color: Color = (0.0, 0.0, 0.0),
        width: float = 1.0,
        start_style: LineEndStyle = LineEndStyle.NONE,
        end_style: LineEndStyle = LineEndStyle.NONE,
    ) -> None:
        """Add line annotation."""
        annot = self._page.add_line_annot(
            pymupdf.Point(start),
            pymupdf.Point(end),
        )
        annot.set_colors(stroke=color)
        annot.set_border(width=width)
        # Set line endings
        annot.set_line_ends(
            self._line_end_to_pymupdf(start_style),
            self._line_end_to_pymupdf(end_style),
        )
        annot.update()
        self._cached_annotations = None  # Invalidate annotation cache

    def add_arrow(
        self,
        start: Point,
        end: Point,
        color: Color = (0.0, 0.0, 0.0),
        width: float = 1.0,
    ) -> None:
        """Add arrow annotation (line with arrow head at end)."""
        self.add_line(
            start=start,
            end=end,
            color=color,
            width=width,
            start_style=LineEndStyle.NONE,
            end_style=LineEndStyle.CLOSED_ARROW,
        )
        # Note: cache invalidation happens in add_line

    def add_polygon(
        self,
        points: List[Point],
        stroke_color: Optional[Color] = (0.0, 0.0, 0.0),
        fill_color: Optional[Color] = None,
        width: float = 1.0,
    ) -> None:
        """Add polygon annotation (closed shape)."""
        if len(points) < 3:
            return
        pymupdf_points = [pymupdf.Point(p) for p in points]
        annot = self._page.add_polygon_annot(pymupdf_points)
        annot.set_colors(stroke=stroke_color, fill=fill_color)
        annot.set_border(width=width)
        annot.update()
        self._cached_annotations = None  # Invalidate annotation cache

    def add_polyline(
        self,
        points: List[Point],
        color: Color = (0.0, 0.0, 0.0),
        width: float = 1.0,
        start_style: LineEndStyle = LineEndStyle.NONE,
        end_style: LineEndStyle = LineEndStyle.NONE,
    ) -> None:
        """Add polyline annotation (open shape)."""
        if len(points) < 2:
            return
        pymupdf_points = [pymupdf.Point(p) for p in points]
        annot = self._page.add_polyline_annot(pymupdf_points)
        annot.set_colors(stroke=color)
        annot.set_border(width=width)
        annot.set_line_ends(
            self._line_end_to_pymupdf(start_style),
            self._line_end_to_pymupdf(end_style),
        )
        annot.update()
        self._cached_annotations = None  # Invalidate annotation cache


class PyMuPDFBackend(DocumentBackend):
    """PyMuPDF document backend."""

    # Default LRU cache size for page objects
    # Should be larger than the render buffer (5+1+5=11 in continuous mode)
    DEFAULT_PAGE_CACHE_SIZE = 15

    def __init__(
        self,
        source: Union[str, Path, bytes, io.BytesIO],
        password: Optional[str] = None,
        page_cache_size: int = DEFAULT_PAGE_CACHE_SIZE,
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

        # LRU cache for page objects using OrderedDict
        from collections import OrderedDict

        self._pages: OrderedDict[int, PyMuPDFPage] = OrderedDict()
        self._page_cache_size = max(1, page_cache_size)

        # Font extraction state
        self._extracted_fonts: Optional[Dict[str, str]] = None
        self._font_temp_dir: Optional[str] = None
        self._use_relative_paths: bool = False

    @property
    def page_count(self) -> int:
        return len(self._doc)

    def extract_fonts(self, assets_dir: Optional[str] = None) -> Dict[str, str]:
        """Extract embedded fonts from the PDF.

        Args:
            assets_dir: Optional path to assets directory. If provided, fonts
                       are saved there with relative paths for Flet compatibility.
                       If None, fonts are saved to a temp directory.

        Returns:
            Dict mapping clean font names to font paths.
            Use with Flet: page.fonts.update(document.fonts)
        """
        if self._extracted_fonts is not None:
            return self._extracted_fonts

        self._extracted_fonts = {}

        # Determine where to save fonts
        if assets_dir:
            # Use assets directory - save to fonts subfolder
            fonts_dir = Path(assets_dir) / "fonts"
            fonts_dir.mkdir(parents=True, exist_ok=True)
            self._font_temp_dir = str(fonts_dir)
            self._use_relative_paths = True
        else:
            # Use temp directory
            self._font_temp_dir = tempfile.mkdtemp(prefix="pdf_fonts_")
            self._use_relative_paths = False

        # Collect all unique font xrefs from all pages
        seen_xrefs = set()
        for page_num in range(len(self._doc)):
            for font_info in self._doc.get_page_fonts(page_num, full=True):
                xref = font_info[0]
                if xref not in seen_xrefs:
                    seen_xrefs.add(xref)
                    self._extract_single_font(xref)

        return self._extracted_fonts

    def _extract_single_font(self, xref: int) -> None:
        """Extract a single font by xref and add to extracted_fonts dict.

        All fonts are converted to TTF for best Flet/Flutter compatibility.
        Supports: TTF, TTC, OTF, CFF (Type1C).
        """
        try:
            extracted = self._doc.extract_font(xref)
            if not extracted:
                return

            name, ext, subtype, buffer = extracted

            # Skip fonts with no data
            if not buffer or len(buffer) < 100:
                return

            # Skip unsupported formats
            if ext not in ("ttf", "ttc", "otf", "cff", "pfa", "pfb"):
                return

            # Clean font name (remove subset prefix like "ABCDEF+")
            clean_name = name.split("+")[-1] if "+" in name else name

            # Skip if already extracted (same clean name)
            if clean_name in self._extracted_fonts:
                return

            # All fonts are saved as TTF for consistency
            font_path = Path(self._font_temp_dir) / f"{clean_name}.ttf"

            # Convert to TTF (handles TTF, OTF, CFF)
            if not _convert_font_to_ttf(buffer, ext, str(font_path)):
                return

            # Use relative path for assets, absolute for temp
            if self._use_relative_paths:
                self._extracted_fonts[clean_name] = f"fonts/{clean_name}.ttf"
            else:
                self._extracted_fonts[clean_name] = str(font_path)

        except Exception:
            # Skip fonts that can't be extracted
            pass

    @property
    def fonts(self) -> Dict[str, str]:
        """Get extracted fonts dict (clean name -> file path).

        Automatically extracts fonts on first access.
        Use with Flet: page.fonts.update(document.fonts)
        """
        return self.extract_fonts()

    @property
    def is_encrypted(self) -> bool:
        """Whether the document has encryption."""
        return self._doc.is_encrypted

    @property
    def needs_password(self) -> bool:
        """Whether password is needed to access content."""
        return self._doc.needs_pass

    def authenticate(self, password: str) -> bool:
        """Authenticate with password to unlock the document.

        Args:
            password: The password to try

        Returns:
            True if authentication succeeded, False otherwise
        """
        if not self._doc.is_encrypted:
            return True
        return self._doc.authenticate(password)

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
            # Move to end (most recently used) for LRU behavior
            self._pages.move_to_end(index)
            return self._pages[index]

        if index < 0 or index >= len(self._doc):
            raise IndexError(f"Page index {index} out of range")

        # Evict oldest page if cache is full
        while len(self._pages) >= self._page_cache_size:
            oldest_index, oldest_page = self._pages.popitem(last=False)
            # Clean up temp files for evicted page
            oldest_page.cleanup_temp_files()

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
        # Clean up temp image files from all cached pages
        for page in self._pages.values():
            page.cleanup_temp_files()

        if self._doc:
            self._doc.close()
        self._pages.clear()

        # Cleanup extracted fonts temp directory
        if self._font_temp_dir:
            import shutil

            try:
                shutil.rmtree(self._font_temp_dir)
            except Exception:
                pass
            self._font_temp_dir = None
            self._extracted_fonts = None
