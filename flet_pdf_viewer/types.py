"""
Shared data types for the PDF viewer.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Tuple

if TYPE_CHECKING:
    import flet as ft


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
    gradient: Optional["LinearGradient | RadialGradient"] = None
    # PyMuPDF font flags for classification (bit 3=mono, bit 2=serif)
    font_flags: int = 0


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
    """A graphics element (rect, line, path, circle, curve)."""

    type: str  # "rect", "line", "quad", "circle", "path"
    bbox: Tuple[float, float, float, float]
    linewidth: float = 0
    stroke_color: Optional[str] = None
    fill_color: Optional[str] = None
    # For lines: (x1, y1, x2, y2)
    points: Optional[List[Tuple[float, float]]] = None
    # For paths: list of path commands
    # Each command is a tuple: ("m", x, y) for moveto, ("l", x, y) for lineto,
    # ("c", x1, y1, x2, y2, x3, y3) for cubic bezier, ("h",) for close
    path_commands: Optional[List[Tuple]] = None
    # For circles/ellipses
    center: Optional[Tuple[float, float]] = None
    radius: Optional[Tuple[float, float]] = None  # (rx, ry) for ellipse
    # For gradient fills
    fill_gradient: Optional["LinearGradient | RadialGradient"] = None
    # For dashed strokes: [dash_length, gap_length, ...] or None for solid
    stroke_dashes: Optional[List[float]] = None


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
class LinkInfo:
    """A PDF link (clickable area)."""

    rect: Tuple[float, float, float, float]  # Bounding box (x0, y0, x1, y1)
    kind: str  # "goto", "uri", "named", "launch", "none"
    # "goto" links (internal page navigation)
    page: Optional[int] = None  # Destination page index (0-based)
    # "uri" links (external URLs)
    uri: Optional[str] = None
    # "named" links (named destinations)
    name: Optional[str] = None
    # "launch" links (launch external app/file)
    file: Optional[str] = None


@dataclass
class RenderResult:
    """Result of rendering a page."""

    shapes: List[Any]
    images: List[Tuple[str, float, float, float, float]]
    chars: List[CharInfo] = field(default_factory=list)


@dataclass
class LinearGradient:
    """Linear gradient definition."""

    x0: float  # Start x
    y0: float  # Start y
    x1: float  # End x
    y1: float  # End y
    colors: List[Tuple[float, float, float]]  # List of RGB colors (0-1 range)
    stops: Optional[List[float]] = None  # Color stop positions (0-1 range)
    extend_start: bool = True  # Extend gradient before start point
    extend_end: bool = True  # Extend gradient after end point


@dataclass
class RadialGradient:
    """Radial gradient definition."""

    cx: float  # Center x
    cy: float  # Center y
    r: float  # Radius
    colors: List[Tuple[float, float, float]]
    stops: Optional[List[float]] = None


class LineEndStyle(Enum):
    """Line ending styles for line/arrow annotations."""

    NONE = "none"
    SQUARE = "square"
    CIRCLE = "circle"
    DIAMOND = "diamond"
    OPEN_ARROW = "open_arrow"
    CLOSED_ARROW = "closed_arrow"
    BUTT = "butt"
    R_OPEN_ARROW = "r_open_arrow"
    R_CLOSED_ARROW = "r_closed_arrow"
    SLASH = "slash"


class ShapeType(Enum):
    """Shape types for interactive drawing."""

    NONE = "none"
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    LINE = "line"
    ARROW = "arrow"
    TEXT = "text"


@dataclass
class SearchResult:
    """A single search match in the document."""

    page_index: int
    rect: Tuple[float, float, float, float]  # Bounding box (x0, y0, x1, y1)
    text: str  # The matched text
    # Additional quads for multi-line matches (optional)
    quads: Optional[List[Tuple[float, float, float, float]]] = None


@dataclass
class SearchOptions:
    """Options for text search."""

    case_sensitive: bool = False
    whole_word: bool = False
    # Search direction
    forward: bool = True
    # Wrap around when reaching document end/start
    wrap: bool = True


# Type aliases for clarity
Color = Tuple[float, float, float]
Rect = Tuple[float, float, float, float]
Point = Tuple[float, float]
Path = List[Point]
GradientType = Optional[LinearGradient | RadialGradient]


# =============================================================================
# Viewer Configuration Classes
# =============================================================================


@dataclass
class PageShadow:
    """Shadow configuration for PDF pages.

    Attributes:
        blur_radius: Blur radius of the shadow (default: 20)
        spread_radius: Spread radius of the shadow (default: 0)
        color: Shadow color with opacity (default: semi-transparent black)
        offset_x: Horizontal offset (default: 0)
        offset_y: Vertical offset (default: 0)

    Example:
        shadow = PageShadow(blur_radius=30, color="#00000050")
    """

    blur_radius: float = 20
    spread_radius: float = 0
    color: str = "#0000004D"  # 30% opacity black
    offset_x: float = 0
    offset_y: float = 0


@dataclass
class ViewerStyle:
    """Visual appearance settings for the PDF viewer.

    Attributes:
        bgcolor: Background color of pages (default: white)
        selection_color: Color for text selection highlight
        page_gap: Gap between pages in continuous/double mode (pixels)
        page_shadow: Shadow configuration for pages (None to disable)
        border_radius: Corner radius of pages (default: 2)

    Example:
        style = ViewerStyle(
            bgcolor="#f5f5f5",
            selection_color="#4a90d9",
            page_gap=20,
            page_shadow=PageShadow(blur_radius=30),
        )
    """

    bgcolor: str = "#ffffff"
    selection_color: str = "#3390ff"
    page_gap: int = 16
    page_shadow: Optional["PageShadow"] = field(default_factory=PageShadow)
    border_radius: float = 2


@dataclass
class ZoomConfig:
    """Zoom and scale settings for the PDF viewer.

    Attributes:
        enabled: Whether interactive zoom (pinch/scroll) is enabled
        initial: Initial zoom scale (1.0 = 100%)
        min: Minimum allowed zoom scale
        max: Maximum allowed zoom scale

    Example:
        zoom = ZoomConfig(
            enabled=True,
            initial=1.0,
            min=0.5,
            max=4.0,
        )
    """

    enabled: bool = True
    initial: float = 1.0
    min: float = 0.25
    max: float = 5.0


@dataclass
class ViewerCallbacks:
    """Event callbacks for the PDF viewer.

    All callbacks are optional. Set only the ones you need.

    Attributes:
        on_page_change: Called when current page changes. Receives page index.
        on_selection_change: Called when text selection changes. Receives selected text.
        on_link_click: Called when a link is clicked. Receives LinkInfo.
                       Return True to prevent default handling.
        on_text_box_drawn: Called when a text box shape is drawn.
                           Receives rect coordinates (x0, y0, x1, y1).

    Example:
        def handle_page(page: int):
            print(f"Page changed to {page}")

        callbacks = ViewerCallbacks(
            on_page_change=handle_page,
        )
    """

    on_page_change: Optional[Callable[[int], None]] = None
    on_selection_change: Optional[Callable[[str], None]] = None
    on_link_click: Optional[Callable[["LinkInfo"], bool]] = None
    on_text_box_drawn: Optional[Callable[[Tuple[float, float, float, float]], None]] = (
        None
    )
