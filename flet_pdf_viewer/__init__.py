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
    PageShadow,
    SearchOptions,
    SearchResult,
    ShapeType,
    TocItem,
    ViewerCallbacks,
    ViewerMode,
    ViewerStyle,
    ZoomConfig,
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

    def resolve_destination(self, name: str) -> Optional[int]:
        """Resolve a named destination to a page index.

        Args:
            name: The named destination (e.g., "chapter1", "section2.3")

        Returns:
            Page index (0-based) if found, None otherwise

        Example:
            page_idx = document.resolve_destination("chapter1")
            if page_idx is not None:
                viewer.goto(page_idx)
        """
        return self._backend.resolve_named_destination(name)

    def get_destinations(self) -> Dict[str, int]:
        """Get all named destinations in the document.

        Returns:
            Dict mapping destination names to page indices (0-based)

        Example:
            destinations = document.get_destinations()
            for name, page in destinations.items():
                print(f"{name} -> page {page}")
        """
        return self._backend.get_named_destinations()

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

    # =========================================================================
    # Page Manipulation Methods
    # =========================================================================

    def rotate_page(self, page_index: int, angle: int) -> None:
        """Rotate a page to a specific angle.

        Args:
            page_index: Page index (0-based)
            angle: Rotation angle (must be 0, 90, 180, or 270)

        Example:
            document.rotate_page(0, 90)  # Rotate first page 90° clockwise
        """
        self._backend.rotate_page(page_index, angle)

    def rotate_page_by(self, page_index: int, angle: int) -> None:
        """Rotate a page by adding to current rotation.

        Args:
            page_index: Page index (0-based)
            angle: Angle to add (must be multiple of 90)

        Example:
            document.rotate_page_by(0, 90)  # Add 90° to current rotation
        """
        self._backend.rotate_page_by(page_index, angle)

    def add_blank_page(
        self,
        width: float = 612,
        height: float = 792,
        index: int = -1,
    ) -> int:
        """Add a blank page to the document.

        Args:
            width: Page width in points (default: 8.5" = 612pt)
            height: Page height in points (default: 11" = 792pt)
            index: Where to insert (-1 = end, 0 = beginning)

        Returns:
            Index of the new page

        Example:
            # Add blank letter-size page at end
            document.add_blank_page()

            # Add A4 page at beginning
            document.add_blank_page(595, 842, index=0)
        """
        return self._backend.add_blank_page(width, height, index)

    def delete_page(self, page_index: int) -> None:
        """Delete a page from the document.

        Args:
            page_index: Page index to delete (0-based)
        """
        self._backend.delete_page(page_index)

    def delete_pages(self, from_index: int, to_index: int) -> None:
        """Delete a range of pages from the document.

        Args:
            from_index: Start page index (inclusive)
            to_index: End page index (inclusive)

        Example:
            document.delete_pages(5, 10)  # Delete pages 5-10
        """
        self._backend.delete_pages(from_index, to_index)

    def move_page(self, from_index: int, to_index: int) -> None:
        """Move a page to a new position.

        Args:
            from_index: Current page index
            to_index: Target position

        Example:
            document.move_page(5, 0)  # Move page 5 to beginning
        """
        self._backend.move_page(from_index, to_index)

    def copy_page(self, page_index: int, to_index: int = -1) -> int:
        """Copy a page within the document.

        Args:
            page_index: Page to copy
            to_index: Where to insert copy (-1 = after original)

        Returns:
            Index of the new page
        """
        return self._backend.copy_page(page_index, to_index)

    def resize_page(self, page_index: int, width: float, height: float) -> None:
        """Resize a page.

        Args:
            page_index: Page index
            width: New width in points
            height: New height in points

        Example:
            # Resize to A4
            document.resize_page(0, 595, 842)
        """
        self._backend.resize_page(page_index, width, height)

    def crop_page(
        self,
        page_index: int,
        left: float = 0,
        top: float = 0,
        right: float = 0,
        bottom: float = 0,
    ) -> None:
        """Crop a page by removing margins.

        Args:
            page_index: Page index
            left: Points to remove from left edge
            top: Points to remove from top edge
            right: Points to remove from right edge
            bottom: Points to remove from bottom edge

        Example:
            # Remove 1 inch (72pt) from all sides
            document.crop_page(0, 72, 72, 72, 72)
        """
        self._backend.crop_page(page_index, left, top, right, bottom)

    def insert_pdf(
        self,
        source: Union[str, Path, "PdfDocument"],
        from_page: int = 0,
        to_page: int = -1,
        start_at: int = -1,
    ) -> int:
        """Insert pages from another PDF.

        Args:
            source: Path to PDF file or another PdfDocument
            from_page: First page to copy from source (0-based)
            to_page: Last page to copy (-1 = last page)
            start_at: Where to insert in this document (-1 = end)

        Returns:
            Number of pages inserted

        Example:
            # Append all pages from another PDF
            document.insert_pdf("other.pdf")

            # Insert pages 0-4 at position 2
            document.insert_pdf("other.pdf", from_page=0, to_page=4, start_at=2)
        """
        if isinstance(source, PdfDocument):
            source = source._backend
        return self._backend.insert_pdf(source, from_page, to_page, start_at)

    def extract_pages(
        self,
        output_path: Union[str, Path],
        page_indices: List[int],
    ) -> None:
        """Extract specific pages to a new PDF file.

        Args:
            output_path: Path for the new PDF
            page_indices: List of page indices to extract

        Example:
            # Extract pages 0, 2, 4 to a new file
            document.extract_pages("subset.pdf", [0, 2, 4])
        """
        self._backend.extract_pages(output_path, page_indices)

    def split_pdf(
        self,
        output_dir: Union[str, Path],
        prefix: str = "page_",
    ) -> List[str]:
        """Split PDF into individual page files.

        Args:
            output_dir: Directory to save individual pages
            prefix: Filename prefix for each page

        Returns:
            List of created file paths

        Example:
            files = document.split_pdf("./pages/")
            # Creates: pages/page_0000.pdf, pages/page_0001.pdf, ...
        """
        return self._backend.split_pdf(output_dir, prefix)

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
    """Patched init that accepts PdfDocument or DocumentBackend."""
    # If source is PdfDocument, unwrap to backend
    if isinstance(source, PdfDocument):
        source = source._get_backend()
    _original_pdfviewer_init(self, source, **kwargs)


PdfViewer.__init__ = _patched_init


__all__ = [
    # Main classes
    "PdfDocument",
    "PdfViewer",
    # Configuration
    "ViewerStyle",
    "ZoomConfig",
    "ViewerCallbacks",
    "PageShadow",
    # Enums and types
    "ViewerMode",
    "ShapeType",
    "TocItem",
    "SearchResult",
    "SearchOptions",
    "LineEndStyle",
    # Version
    "__version__",
]
