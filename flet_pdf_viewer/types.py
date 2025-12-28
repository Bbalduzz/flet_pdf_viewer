"""
Shared data types for the PDF viewer.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional, Tuple


class ViewerMode(Enum):
    """PDF viewer display modes."""

    SINGLE_PAGE = "single"
    CONTINUOUS = "continuous"
    DOUBLE_PAGE = "double"


@dataclass
class PageInfo:
    """Information about a PDF page."""

    index: int
    width: float
    height: float
    rotation: int = 0


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
    font_name: str = ""
    font_size: float = 12.0
    color: str = "#000000"


@dataclass
class SelectableChar:
    """A character with scaled position for selection."""

    char: str
    x: float
    y: float
    width: float
    height: float
    page_index: int
    page_offset_x: float = 0
    page_offset_y: float = 0


@dataclass
class OutlineItem:
    """A bookmark/TOC entry."""

    title: str
    page_index: Optional[int]
    level: int
    children: List["OutlineItem"] = field(default_factory=list)


@dataclass
class TocItem:
    """Table of contents item (public API)."""

    title: str
    page_index: Optional[int]
    level: int
    children: List["TocItem"] = field(default_factory=list)

    @classmethod
    def from_outline(cls, outline: OutlineItem) -> "TocItem":
        return cls(
            title=outline.title,
            page_index=outline.page_index,
            level=outline.level,
            children=[cls.from_outline(c) for c in outline.children],
        )


@dataclass
class ImageInfo:
    """An extracted image."""

    bbox: Tuple[float, float, float, float]
    width: int
    height: int
    png_path: Optional[str] = None


@dataclass
class GraphicsInfo:
    """A graphics element (rect, line)."""

    type: str
    bbox: Tuple[float, float, float, float]
    linewidth: float = 0
    stroke_color: Optional[str] = None
    fill_color: Optional[str] = None


@dataclass
class AnnotationInfo:
    """A PDF annotation."""

    type: int
    type_name: str
    rect: Tuple[float, float, float, float]
    color: Tuple[float, float, float] = (1.0, 1.0, 0.0)
    contents: Optional[str] = None
    vertices: Optional[List[Any]] = None
    border_width: float = 1.0


@dataclass
class RenderResult:
    """Result of rendering a page."""

    shapes: List[Any]
    images: List[Tuple[str, float, float, float, float]]
    chars: List[CharInfo] = field(default_factory=list)


# Type aliases for clarity
Color = Tuple[float, float, float]
Rect = Tuple[float, float, float, float]
Point = Tuple[float, float]
Path = List[Point]
