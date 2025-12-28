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
from typing import List, Optional, Tuple, Union

from .backends.pymupdf import PyMuPDFBackend
from .types import Color, TocItem, ViewerMode
from .viewer import PdfViewer

__version__ = "0.1.0"


class PdfDocument:
    """
    PDF Document wrapper.

    Can be created from:
    - File path (str or Path)
    - Bytes
    - BytesIO

    Properties:
    - page_count: Number of pages
    - toc: Table of contents
    - metadata: Document metadata

    Methods:
    - get_page_size(index): Get (width, height)
    - save(): Save the document
    - close(): Release resources
    """

    def __init__(self, source: Union[str, Path, bytes, io.BytesIO]):
        """Open a PDF document."""
        self._backend = PyMuPDFBackend(source)

    @property
    def page_count(self) -> int:
        """Number of pages."""
        return self._backend.page_count

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
    "TocItem",
    "__version__",
]
