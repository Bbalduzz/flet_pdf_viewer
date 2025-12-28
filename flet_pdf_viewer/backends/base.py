"""
Abstract backend protocol for PDF parsing.

Backends must implement these protocols to work with the viewer.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import IO, List, Optional, Tuple, Union

from ..types import (
    AnnotationInfo,
    CharInfo,
    Color,
    GraphicsInfo,
    ImageInfo,
    OutlineItem,
    PageInfo,
    Path as InkPath,
    Rect,
    TextBlock,
)


class PageBackend(ABC):
    """Abstract interface for a PDF page."""

    @property
    @abstractmethod
    def width(self) -> float:
        """Page width in points."""
        ...

    @property
    @abstractmethod
    def height(self) -> float:
        """Page height in points."""
        ...

    @property
    @abstractmethod
    def index(self) -> int:
        """Page index (0-based)."""
        ...

    @abstractmethod
    def get_info(self) -> PageInfo:
        """Get page information."""
        ...

    @abstractmethod
    def extract_text_blocks(self) -> List[TextBlock]:
        """Extract text blocks with styling."""
        ...

    @abstractmethod
    def extract_chars(self) -> List[CharInfo]:
        """Extract individual characters with positions."""
        ...

    @abstractmethod
    def extract_images(self) -> List[ImageInfo]:
        """Extract images from the page."""
        ...

    @abstractmethod
    def extract_graphics(self) -> List[GraphicsInfo]:
        """Extract vector graphics (rects, lines)."""
        ...

    @abstractmethod
    def get_annotations(self) -> List[AnnotationInfo]:
        """Get all annotations on the page."""
        ...

    # Annotation methods
    @abstractmethod
    def add_highlight(self, rects: List[Rect], color: Color) -> None:
        """Add highlight annotation."""
        ...

    @abstractmethod
    def add_underline(self, rects: List[Rect], color: Color) -> None:
        """Add underline annotation."""
        ...

    @abstractmethod
    def add_strikethrough(self, rects: List[Rect], color: Color) -> None:
        """Add strikethrough annotation."""
        ...

    @abstractmethod
    def add_squiggly(self, rects: List[Rect], color: Color) -> None:
        """Add squiggly underline annotation."""
        ...

    @abstractmethod
    def add_text_note(
        self,
        point: Tuple[float, float],
        text: str,
        icon: str,
        color: Color,
    ) -> None:
        """Add sticky note annotation."""
        ...

    @abstractmethod
    def add_ink(
        self,
        paths: List[InkPath],
        color: Color,
        width: float,
    ) -> None:
        """Add ink (freehand) annotation."""
        ...


class DocumentBackend(ABC):
    """Abstract interface for a PDF document."""

    @property
    @abstractmethod
    def page_count(self) -> int:
        """Number of pages in the document."""
        ...

    @abstractmethod
    def get_page(self, index: int) -> PageBackend:
        """Get a page by index."""
        ...

    @abstractmethod
    def get_outlines(self) -> List[OutlineItem]:
        """Get document outline/TOC."""
        ...

    @abstractmethod
    def get_metadata(self) -> dict:
        """Get document metadata."""
        ...

    @abstractmethod
    def save(self, path: Optional[Union[str, Path]] = None) -> None:
        """Save the document."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Close and release resources."""
        ...

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
