"""
Flet PDF Viewer

A pure Python PDF viewer built with Flet Canvas.

Usage:
    import flet as ft
    from flet_pdf_viewer import PdfDocument, PdfViewer, ViewerMode

    def main(page: ft.Page):
        document = PdfDocument("/path/to/file.pdf")
        viewer = PdfViewer(document, mode=ViewerMode.CONTINUOUS)
        page.add(viewer.control)

    ft.app(main)
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from .backends.pymupdf import PyMuPDFBackend
from .types import (
    Color,
    LineEndStyle,
    SearchOptions,
    SearchResult,
    ShapeType,
    TocItem,
    ViewerMode,
)
from .viewer import PdfViewer

__version__ = "0.1.0"


class PdfDocument:
    """
    PDF Document wrapper.

    Can be created from:
    - File path (str or Path)
    - Bytes
    - BytesIO

    Args:
        source: Path to PDF file, bytes, or BytesIO
        password: Password for encrypted PDFs (optional)

    Properties:
    - page_count: Number of pages
    - toc: Table of contents
    - metadata: Document metadata

    Methods:
    - get_page_size(index): Get (width, height)
    - authenticate(password): Unlock encrypted document
    - save(): Save the document
    - close(): Release resources

    Raises:
        ValueError: If document is encrypted and no password provided,
                   or if password is invalid
    """

    def __init__(
        self,
        source: Union[str, Path, bytes, io.BytesIO],
        password: Optional[str] = None,
    ):
        """Open a PDF document.

        Args:
            source: Path to PDF file, bytes, or BytesIO
            password: Password for encrypted PDFs (optional)
        """
        self._backend = PyMuPDFBackend(source, password=password)

    @property
    def page_count(self) -> int:
        """Number of pages."""
        return self._backend.page_count

    @property
    def is_encrypted(self) -> bool:
        """Whether the document has encryption."""
        return self._backend.is_encrypted

    @property
    def needs_password(self) -> bool:
        """Whether password is still needed to access content.

        Returns False after successful authentication.
        """
        return self._backend.needs_password

    def authenticate(self, password: str) -> bool:
        """Authenticate with password to unlock the document.

        Args:
            password: The password to try

        Returns:
            True if authentication succeeded, False otherwise
        """
        return self._backend.authenticate(password)

    @property
    def permissions(self) -> dict:
        """Document permissions.

        Returns:
            dict with keys: 'print', 'copy', 'modify', 'annotate'
            Each value is True if that action is permitted.
        """
        return self._backend.permissions

    def extract_fonts(self, assets_dir: Optional[str] = None) -> Dict[str, str]:
        """Extract embedded fonts from the PDF.

        Args:
            assets_dir: Path to Flet assets directory. If provided, fonts are
                       saved to assets/fonts/ with relative paths that work
                       with Flet's page.fonts.

        Returns:
            Dict mapping font names to font paths for page.fonts.

        Example:
            document = PdfDocument("file.pdf")
            fonts = document.extract_fonts(assets_dir="assets")
            page.fonts = fonts
            # Then run with: ft.app(target=main, assets_dir="assets")
        """
        return self._backend.extract_fonts(assets_dir)

    @property
    def fonts(self) -> Dict[str, str]:
        """Extracted embedded fonts (uses temp directory).

        For production use, prefer extract_fonts(assets_dir="assets").
        """
        return self._backend.fonts

    @property
    def toc(self) -> List[TocItem]:
        """Table of contents."""
        outlines = self._backend.get_outlines()
        return [TocItem.from_outline(o) for o in outlines]

    @property
    def metadata(self) -> dict:
        """Document metadata."""
        return self._backend.get_metadata()

    def get_page_size(self, index: int = 0) -> Tuple[float, float]:
        """Get page size (width, height) in points."""
        page = self._backend.get_page(index)
        return (page.width, page.height)

    def add_highlight(
        self,
        page_index: int,
        rects: List[Tuple[float, float, float, float]],
        color: Color = (1.0, 1.0, 0.0),
    ) -> None:
        """Add highlight annotation."""
        page = self._backend.get_page(page_index)
        page.add_highlight(rects, color)

    def add_underline(
        self,
        page_index: int,
        rects: List[Tuple[float, float, float, float]],
        color: Color = (0.0, 0.0, 1.0),
    ) -> None:
        """Add underline annotation."""
        page = self._backend.get_page(page_index)
        page.add_underline(rects, color)

    def add_strikethrough(
        self,
        page_index: int,
        rects: List[Tuple[float, float, float, float]],
        color: Color = (1.0, 0.0, 0.0),
    ) -> None:
        """Add strikethrough annotation."""
        page = self._backend.get_page(page_index)
        page.add_strikethrough(rects, color)

    def add_squiggly(
        self,
        page_index: int,
        rects: List[Tuple[float, float, float, float]],
        color: Color = (0.0, 0.8, 0.0),
    ) -> None:
        """Add squiggly underline annotation."""
        page = self._backend.get_page(page_index)
        page.add_squiggly(rects, color)

    def add_text_note(
        self,
        page_index: int,
        point: Tuple[float, float],
        text: str,
        icon: str = "Note",
        color: Color = (1.0, 0.92, 0.0),
    ) -> None:
        """Add sticky note annotation."""
        page = self._backend.get_page(page_index)
        page.add_text_note(point, text, icon, color)

    def add_ink(
        self,
        page_index: int,
        paths: List[List[Tuple[float, float]]],
        color: Color = (0.0, 0.0, 0.0),
        width: float = 2.0,
    ) -> None:
        """Add ink (freehand) annotation."""
        page = self._backend.get_page(page_index)
        page.add_ink(paths, color, width)

    # Shape annotations

    def add_freetext(
        self,
        page_index: int,
        rect: Tuple[float, float, float, float],
        text: str,
        font_size: float = 12.0,
        font_name: str = "helv",
        text_color: Color = (0.0, 0.0, 0.0),
        fill_color: Optional[Color] = None,
        border_color: Optional[Color] = None,
        border_width: float = 0.0,
        align: int = 0,
    ) -> None:
        """Add free text annotation (text box).

        Args:
            page_index: Page number (0-based)
            rect: Bounding rectangle (x0, y0, x1, y1)
            text: The text content
            font_size: Font size in points (default: 12)
            font_name: Font name - helv, tiro, cour (default: helv)
            text_color: Text color RGB tuple (default: black)
            fill_color: Background fill color (None for transparent)
            border_color: Border color (None for no border)
            border_width: Border width (default: 0)
            align: Text alignment - 0=left, 1=center, 2=right (default: 0)
        """
        page = self._backend.get_page(page_index)
        page.add_freetext(
            rect,
            text,
            font_size,
            font_name,
            text_color,
            fill_color,
            border_color,
            border_width,
            align,
        )

    def add_rect(
        self,
        page_index: int,
        rect: Tuple[float, float, float, float],
        stroke_color: Optional[Color] = (0.0, 0.0, 0.0),
        fill_color: Optional[Color] = None,
        width: float = 1.0,
    ) -> None:
        """Add rectangle annotation.

        Args:
            page_index: Page number (0-based)
            rect: Rectangle coordinates (x0, y0, x1, y1)
            stroke_color: Border color (None for no border)
            fill_color: Fill color (None for no fill)
            width: Border width (default: 1)
        """
        page = self._backend.get_page(page_index)
        page.add_rect(rect, stroke_color, fill_color, width)

    def add_circle(
        self,
        page_index: int,
        rect: Tuple[float, float, float, float],
        stroke_color: Optional[Color] = (0.0, 0.0, 0.0),
        fill_color: Optional[Color] = None,
        width: float = 1.0,
    ) -> None:
        """Add circle/ellipse annotation.

        Args:
            page_index: Page number (0-based)
            rect: Bounding rectangle for the ellipse (x0, y0, x1, y1)
            stroke_color: Border color (None for no border)
            fill_color: Fill color (None for no fill)
            width: Border width (default: 1)
        """
        page = self._backend.get_page(page_index)
        page.add_circle(rect, stroke_color, fill_color, width)

    def add_line(
        self,
        page_index: int,
        start: Tuple[float, float],
        end: Tuple[float, float],
        color: Color = (0.0, 0.0, 0.0),
        width: float = 1.0,
        start_style: LineEndStyle = LineEndStyle.NONE,
        end_style: LineEndStyle = LineEndStyle.NONE,
    ) -> None:
        """Add line annotation.

        Args:
            page_index: Page number (0-based)
            start: Start point (x, y)
            end: End point (x, y)
            color: Line color (default: black)
            width: Line width (default: 1)
            start_style: Line ending style at start
            end_style: Line ending style at end
        """
        page = self._backend.get_page(page_index)
        page.add_line(start, end, color, width, start_style, end_style)

    def add_arrow(
        self,
        page_index: int,
        start: Tuple[float, float],
        end: Tuple[float, float],
        color: Color = (0.0, 0.0, 0.0),
        width: float = 1.0,
    ) -> None:
        """Add arrow annotation (line with arrow head at end).

        Args:
            page_index: Page number (0-based)
            start: Start point (x, y)
            end: End point (x, y) - arrow head here
            color: Line color (default: black)
            width: Line width (default: 1)
        """
        page = self._backend.get_page(page_index)
        page.add_arrow(start, end, color, width)

    def add_polygon(
        self,
        page_index: int,
        points: List[Tuple[float, float]],
        stroke_color: Optional[Color] = (0.0, 0.0, 0.0),
        fill_color: Optional[Color] = None,
        width: float = 1.0,
    ) -> None:
        """Add polygon annotation (closed shape).

        Args:
            page_index: Page number (0-based)
            points: List of vertices [(x1,y1), (x2,y2), ...]
            stroke_color: Border color
            fill_color: Fill color
            width: Border width (default: 1)
        """
        page = self._backend.get_page(page_index)
        page.add_polygon(points, stroke_color, fill_color, width)

    def add_polyline(
        self,
        page_index: int,
        points: List[Tuple[float, float]],
        color: Color = (0.0, 0.0, 0.0),
        width: float = 1.0,
        start_style: LineEndStyle = LineEndStyle.NONE,
        end_style: LineEndStyle = LineEndStyle.NONE,
    ) -> None:
        """Add polyline annotation (connected line segments).

        Args:
            page_index: Page number (0-based)
            points: List of vertices [(x1,y1), (x2,y2), ...]
            color: Line color (default: black)
            width: Line width (default: 1)
            start_style: Line ending style at start
            end_style: Line ending style at end
        """
        page = self._backend.get_page(page_index)
        page.add_polyline(points, color, width, start_style, end_style)

    def save(self, path: Optional[Union[str, Path]] = None) -> None:
        """Save the document."""
        self._backend.save(path)

    def close(self):
        """Close and release resources."""
        self._backend.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # Internal access for viewer
    def _get_backend(self):
        return self._backend


# Re-export PdfViewer with PdfDocument support
_original_pdfviewer_init = PdfViewer.__init__


def _patched_init(self, source=None, **kwargs):
    # If source is PdfDocument, unwrap to backend
    if isinstance(source, PdfDocument):
        source = source._get_backend()
    _original_pdfviewer_init(self, source, **kwargs)


PdfViewer.__init__ = _patched_init


__all__ = [
    "PdfDocument",
    "PdfViewer",
    "ViewerMode",
    "ShapeType",
    "TocItem",
    "SearchResult",
    "SearchOptions",
    "LineEndStyle",
    "__version__",
]
