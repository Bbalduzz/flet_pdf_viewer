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
    LineEndStyle,
    LinkInfo,
    OutlineItem,
    PageInfo,
    Point,
    Rect,
    SearchResult,
    TextBlock,
)
from ..types import (
    Path as InkPath,
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

    @abstractmethod
    def get_links(self) -> List[LinkInfo]:
        """Get all links on the page."""
        ...

    @abstractmethod
    def search_text(
        self,
        query: str,
        case_sensitive: bool = False,
        whole_word: bool = False,
    ) -> List[SearchResult]:
        """Search for text on this page.

        Args:
            query: The text to search for
            case_sensitive: Whether search is case-sensitive
            whole_word: Whether to match whole words only

        Returns:
            List of SearchResult with match locations
        """
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

    # Shape annotations
    @abstractmethod
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
        align: int = 0,  # 0=left, 1=center, 2=right
    ) -> None:
        """Add free text annotation.

        Args:
            rect: Bounding rectangle for the text box
            text: The text content
            font_size: Font size in points
            font_name: Font name (helv, tiro, cour, etc.)
            text_color: Text color RGB tuple
            fill_color: Background fill color (None for transparent)
            border_color: Border color (None for no border)
            border_width: Border width
            align: Text alignment (0=left, 1=center, 2=right)
        """
        ...

    @abstractmethod
    def add_rect(
        self,
        rect: Rect,
        stroke_color: Optional[Color] = (0.0, 0.0, 0.0),
        fill_color: Optional[Color] = None,
        width: float = 1.0,
    ) -> None:
        """Add rectangle annotation.

        Args:
            rect: The rectangle coordinates
            stroke_color: Border color (None for no border)
            fill_color: Fill color (None for no fill)
            width: Border width
        """
        ...

    @abstractmethod
    def add_circle(
        self,
        rect: Rect,
        stroke_color: Optional[Color] = (0.0, 0.0, 0.0),
        fill_color: Optional[Color] = None,
        width: float = 1.0,
    ) -> None:
        """Add circle/ellipse annotation.

        Args:
            rect: Bounding rectangle for the ellipse
            stroke_color: Border color (None for no border)
            fill_color: Fill color (None for no fill)
            width: Border width
        """
        ...

    @abstractmethod
    def add_line(
        self,
        start: Point,
        end: Point,
        color: Color = (0.0, 0.0, 0.0),
        width: float = 1.0,
        start_style: LineEndStyle = LineEndStyle.NONE,
        end_style: LineEndStyle = LineEndStyle.NONE,
    ) -> None:
        """Add line annotation.

        Args:
            start: Start point (x, y)
            end: End point (x, y)
            color: Line color
            width: Line width
            start_style: Line ending style at start
            end_style: Line ending style at end
        """
        ...

    @abstractmethod
    def add_arrow(
        self,
        start: Point,
        end: Point,
        color: Color = (0.0, 0.0, 0.0),
        width: float = 1.0,
    ) -> None:
        """Add arrow annotation (line with arrow head at end).

        Args:
            start: Start point (x, y)
            end: End point (x, y) - arrow head here
            color: Line color
            width: Line width
        """
        ...

    @abstractmethod
    def add_polygon(
        self,
        points: List[Point],
        stroke_color: Optional[Color] = (0.0, 0.0, 0.0),
        fill_color: Optional[Color] = None,
        width: float = 1.0,
    ) -> None:
        """Add polygon annotation (closed shape).

        Args:
            points: List of vertices
            stroke_color: Border color
            fill_color: Fill color
            width: Border width
        """
        ...

    @abstractmethod
    def add_polyline(
        self,
        points: List[Point],
        color: Color = (0.0, 0.0, 0.0),
        width: float = 1.0,
        start_style: LineEndStyle = LineEndStyle.NONE,
        end_style: LineEndStyle = LineEndStyle.NONE,
    ) -> None:
        """Add polyline annotation (open shape).

        Args:
            points: List of vertices
            color: Line color
            width: Line width
            start_style: Line ending style at start
            end_style: Line ending style at end
        """
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
