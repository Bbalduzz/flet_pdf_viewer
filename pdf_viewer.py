"""
PDF Viewer

Usage:
    import flet as ft
    from pdf_viewer import PdfDocument, PdfViewer, PdfViewerMode

    def main(page: ft.Page):
        document = PdfDocument("/path/to/file.pdf")
        viewer = PdfViewer(source=document, mode=PdfViewerMode.SINGLE_PAGE)
        page.add(viewer.control)

    ft.app(main)
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Union

import flet as ft
import flet.canvas as cv

from pymupdf_document import (
    OutlineItem,
    PyMuPDFDocument,
    PyMuPDFPage,
    render_page_with_pymupdf,
)


@dataclass
class SelectableChar:
    """A single character with scaled position for selection."""

    char: str
    x: float  # Scaled x position (relative to page container)
    y: float  # Scaled y position
    width: float  # Scaled width
    height: float  # Scaled height
    page_index: int  # Which page this block belongs to
    page_offset_x: float = 0  # Offset of the page container
    page_offset_y: float = 0  # Offset of the page container


@dataclass
class SelectableBlock:
    """A text block with scaled position for selection (kept for compatibility)."""

    text: str
    x: float
    y: float
    width: float
    height: float
    page_index: int
    page_offset_x: float = 0
    page_offset_y: float = 0


class PdfViewerMode(Enum):
    """PDF viewer display modes."""

    SINGLE_PAGE = "single"  # One page at a time
    CONTINUOUS = "continuous"  # All pages in scrollable view
    DOUBLE_PAGE = "double"  # Two pages side by side (book view)


@dataclass
class TocItem:
    """Table of contents item."""

    title: str
    page_index: Optional[int]
    level: int
    children: List["TocItem"]

    @classmethod
    def from_outline(cls, outline: OutlineItem) -> "TocItem":
        """Create from OutlineItem."""
        return cls(
            title=outline.title,
            page_index=outline.page_index,
            level=outline.level,
            children=[cls.from_outline(c) for c in outline.children],
        )


class PdfDocument:
    """
    PDF Document wrapper with a clean API.

    Can be created from:
    - File path (str or Path)
    - Bytes
    - BytesIO

    Properties:
    - page_count: Number of pages
    - toc: Table of contents (list of TocItem)
    - metadata: Document metadata dict

    Methods:
    - get_page_size(index): Get (width, height) for a page
    - close(): Close the document
    """

    def __init__(self, source: Union[str, Path, bytes, io.BytesIO]):
        """
        Open a PDF document.

        Args:
            source: Path to PDF file, bytes, or BytesIO object
        """
        self._doc = PyMuPDFDocument(source)
        self._path = source if isinstance(source, (str, Path)) else None

    @property
    def page_count(self) -> int:
        """Number of pages in the document."""
        return self._doc.page_count

    @property
    def toc(self) -> List[TocItem]:
        """Table of contents."""
        outlines = self._doc.get_outlines()
        return [TocItem.from_outline(o) for o in outlines]

    @property
    def metadata(self) -> dict:
        """Document metadata."""
        try:
            return dict(self._doc._doc.metadata) if self._doc._doc.metadata else {}
        except Exception:
            return {}

    def get_page_size(self, index: int = 0) -> Tuple[float, float]:
        """Get the size of a page.

        Args:
            index: Page index (0-based)

        Returns:
            Tuple of (width, height) in points
        """
        page = self._doc.get_page(index)
        return (page.width, page.height)

    def _get_internal_page(self, index: int) -> PyMuPDFPage:
        """Get internal page object (for rendering)."""
        return self._doc.get_page(index)

    def add_highlight(
        self,
        page_index: int,
        rects: List[Tuple[float, float, float, float]],
        color: Tuple[float, float, float] = (1.0, 1.0, 0.0),
    ) -> None:
        """Add highlight annotation to a page.

        Args:
            page_index: Page index (0-based)
            rects: List of rectangles (x0, y0, x1, y1) to highlight
            color: RGB color tuple (0-1 range), default yellow
        """
        page = self._doc.get_page(page_index)
        page.add_highlight(rects, color)

    def add_underline(
        self,
        page_index: int,
        rects: List[Tuple[float, float, float, float]],
        color: Tuple[float, float, float] = (0.0, 0.0, 1.0),
    ) -> None:
        """Add underline annotation to a page."""
        page = self._doc.get_page(page_index)
        page.add_underline(rects, color)

    def add_strikethrough(
        self,
        page_index: int,
        rects: List[Tuple[float, float, float, float]],
        color: Tuple[float, float, float] = (1.0, 0.0, 0.0),
    ) -> None:
        """Add strikethrough annotation to a page."""
        page = self._doc.get_page(page_index)
        page.add_strikethrough(rects, color)

    def add_squiggly(
        self,
        page_index: int,
        rects: List[Tuple[float, float, float, float]],
        color: Tuple[float, float, float] = (0.0, 0.8, 0.0),
    ) -> None:
        """Add squiggly underline annotation to a page."""
        page = self._doc.get_page(page_index)
        page.add_squiggly(rects, color)

    def add_text_note(
        self,
        page_index: int,
        point: Tuple[float, float],
        text: str,
        icon: str = "Note",
        color: Tuple[float, float, float] = (1.0, 0.92, 0.0),
    ) -> None:
        """Add a text (sticky note) annotation to a page."""
        page = self._doc.get_page(page_index)
        page.add_text_note(point, text, icon, color)

    def add_ink(
        self,
        page_index: int,
        paths: List[List[Tuple[float, float]]],
        color: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        width: float = 2.0,
    ) -> None:
        """Add an ink (freehand drawing) annotation to a page."""
        page = self._doc.get_page(page_index)
        page.add_ink(paths, color, width)

    def save(self, path: Optional[Union[str, Path]] = None) -> None:
        """Save the document.

        Args:
            path: Path to save to. If None, saves to original path.
        """
        self._doc.save(path)

    def save_as(self, path: Union[str, Path]) -> None:
        """Save the document to a new path."""
        self._doc.save_as(path)

    def close(self):
        """Close the document and release resources."""
        self._doc.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class PdfViewer:
    """
    PDF Viewer - displays a PDF page.

    This is a minimal viewer that just displays the PDF content.
    You are responsible for creating your own toolbar/controls.

    Properties:
    - source: PdfDocument to display
    - current_page: Current page index (0-based)
    - scale: Zoom scale (1.0 = 100%)
    - mode: Display mode (SINGLE_PAGE, CONTINUOUS, DOUBLE_PAGE)
    - page_count: Total number of pages (read-only)
    - control: The Flet control to add to a page

    Methods:
    - next_page(): Go to next page
    - previous_page(): Go to previous page
    - goto(page_index): Go to specific page
    - zoom_in(): Increase zoom
    - zoom_out(): Decrease zoom

    Events:
    - on_page_change: Called when page changes, receives page index

    Usage:
        document = PdfDocument("/path/to/file.pdf")
        viewer = PdfViewer(source=document, mode=PdfViewerMode.CONTINUOUS)
        page.add(viewer.control)

        # Create your own controls
        next_btn = ft.IconButton(icon=ft.Icons.ARROW_FORWARD, on_click=lambda _: viewer.next_page())
    """

    def __init__(
        self,
        source: Optional[PdfDocument] = None,
        current_page: int = 0,
        scale: float = 1.0,
        mode: PdfViewerMode = PdfViewerMode.SINGLE_PAGE,
        page_gap: int = 16,
        bgcolor: str = "#ffffff",
        selection_color: str = "#3390ff",
        popup_builder: Optional[Callable[["PdfViewer"], ft.Control]] = None,
        on_page_change: Optional[Callable[[int], None]] = None,
        on_selection_change: Optional[Callable[[str], None]] = None,
    ):
        """
        Create a PDF viewer.

        Args:
            source: PdfDocument to display
            current_page: Initial page index (0-based)
            scale: Initial zoom scale (1.0 = 100%)
            mode: Display mode (SINGLE_PAGE, CONTINUOUS, DOUBLE_PAGE)
            page_gap: Gap between pages in continuous/double mode (pixels)
            bgcolor: Page background color
            selection_color: Color for text selection highlight
            popup_builder: Custom function to build selection popup. Receives viewer instance.
                          If None, uses default popup. The function should return a ft.Control.
                          Use viewer.highlight_selection(), viewer.underline_selection(), etc.
            on_page_change: Callback when page changes
            on_selection_change: Callback when selection changes, receives selected text
        """
        self._source = source
        self._current_page = current_page
        self._scale = scale
        self._mode = mode
        self._page_gap = page_gap
        self._bgcolor = bgcolor
        self._selection_color = selection_color
        self._popup_builder = popup_builder
        self._on_page_change = on_page_change
        self._on_selection_change = on_selection_change

        # UI components - use a stable wrapper that we update the content of
        self._wrapper: Optional[ft.Container] = None
        self._content: Optional[ft.Control] = None

        # Text selection state (character-level)
        self._selectable_chars: List[SelectableChar] = []
        self._selected_chars: List[SelectableChar] = []
        self._selection_start: Optional[Tuple[float, float]] = None
        self._selection_end: Optional[Tuple[float, float]] = None
        self._is_selecting: bool = False
        self._selection_overlay: Optional[ft.Container] = None

        # Selection popup
        self._popup: Optional[ft.Container] = None
        self._popup_visible: bool = False

        # Ink/drawing mode
        self._drawing_mode: bool = False
        self._current_ink_path: List[Tuple[float, float]] = []
        self._ink_color: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._ink_width: float = 2.0
        self._ink_overlay: Optional[ft.Container] = None

        # Build the control
        self._build()

    # Properties

    @property
    def control(self) -> ft.Control:
        """The Flet control to add to a page."""
        return self._wrapper

    @property
    def source(self) -> Optional[PdfDocument]:
        """The PDF document being displayed."""
        return self._source

    @source.setter
    def source(self, value: Optional[PdfDocument]):
        self._source = value
        self._current_page = 0
        self._update_content()

    @property
    def current_page(self) -> int:
        """Current page index (0-based)."""
        return self._current_page

    @current_page.setter
    def current_page(self, value: int):
        if self._source and 0 <= value < self._source.page_count:
            self._current_page = value
            self._update_content()
            if self._on_page_change:
                self._on_page_change(value)

    @property
    def scale(self) -> float:
        """Zoom scale (1.0 = 100%)."""
        return self._scale

    @scale.setter
    def scale(self, value: float):
        self._scale = max(0.1, min(5.0, value))
        self._update_content()

    @property
    def mode(self) -> PdfViewerMode:
        """Display mode."""
        return self._mode

    @mode.setter
    def mode(self, value: PdfViewerMode):
        if self._mode != value:
            self._mode = value
            self._update_content()

    @property
    def page_count(self) -> int:
        """Total number of pages."""
        return self._source.page_count if self._source else 0

    @property
    def width(self) -> float:
        """Current page width (scaled)."""
        if self._source:
            w, _ = self._source.get_page_size(self._current_page)
            return w * self._scale
        return 0

    @property
    def height(self) -> float:
        """Current page height (scaled)."""
        if self._source:
            _, h = self._source.get_page_size(self._current_page)
            return h * self._scale
        return 0

    @property
    def selected_text(self) -> str:
        """Get the currently selected text."""
        if not self._selected_chars:
            return ""
        # Sort by page, y position, then x position for proper reading order
        sorted_chars = sorted(
            self._selected_chars,
            key=lambda c: (
                c.page_index,
                round(c.y / 10),
                c.x,
            ),  # Round y to group lines
        )
        # Group characters into lines and join, detecting spaces from gaps
        result = []
        current_line = []
        last_char = None
        last_page = None

        for char in sorted_chars:
            # New line if y position changed significantly or page changed
            if last_char is not None and (
                abs(char.y - last_char.y) > char.height * 0.5
                or char.page_index != last_page
            ):
                if current_line:
                    result.append("".join(current_line))
                current_line = []
                last_char = None

            # Detect space: if there's a gap larger than ~30% of char width between chars
            if last_char is not None and char.page_index == last_page:
                gap = char.x - (last_char.x + last_char.width)
                # If gap is significant (more than ~0.3 of average char width), insert space
                avg_width = (char.width + last_char.width) / 2
                if gap > avg_width * 0.3:
                    current_line.append(" ")

            current_line.append(char.char)
            last_char = char
            last_page = char.page_index

        if current_line:
            result.append("".join(current_line))

        return "\n".join(result)

    def clear_selection(self):
        """Clear the current text selection."""
        self._selected_chars = []
        self._selection_start = None
        self._selection_end = None
        self._is_selecting = False
        self._hide_popup()
        self._update_selection_overlay()

    # Public action methods (for custom popups)

    def highlight_selection(
        self, color: Tuple[float, float, float] = (1.0, 0.92, 0.23)
    ):
        """Add highlight annotation to selected text. Call from custom popup."""
        self._add_annotation("highlight", color)

    def underline_selection(
        self, color: Tuple[float, float, float] = (0.38, 0.65, 0.98)
    ):
        """Add underline annotation to selected text. Call from custom popup."""
        self._add_annotation("underline", color)

    def strikethrough_selection(
        self, color: Tuple[float, float, float] = (0.97, 0.44, 0.44)
    ):
        """Add strikethrough annotation to selected text. Call from custom popup."""
        self._add_annotation("strikethrough", color)

    def squiggly_selection(self, color: Tuple[float, float, float] = (0.0, 0.8, 0.0)):
        """Add squiggly underline annotation to selected text. Call from custom popup."""
        self._add_annotation("squiggly", color)

    def add_note_at_selection(
        self,
        text: str,
        icon: str = "Note",
        color: Tuple[float, float, float] = (1.0, 0.92, 0.0),
    ):
        """Add a sticky note annotation at the selection position.

        Args:
            text: The comment text for the note
            icon: Icon type ("Note", "Comment", "Help", "Insert", "Paragraph")
            color: RGB color tuple (0-1 range), default yellow
        """
        if not self._source or not self._selected_chars:
            return

        # Get the first selected char position
        first_char = min(self._selected_chars, key=lambda c: (c.page_index, c.y, c.x))

        # Position note at the start of selection (unscaled)
        point = (first_char.x / self._scale, first_char.y / self._scale)

        self._source.add_text_note(first_char.page_index, point, text, icon, color)

        self.clear_selection()
        self._update_content()

    # Drawing/Ink mode methods

    @property
    def drawing_mode(self) -> bool:
        """Whether drawing mode is active."""
        return self._drawing_mode

    def enable_drawing(
        self,
        color: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        width: float = 2.0,
    ):
        """Enable ink/drawing mode.

        Args:
            color: RGB color tuple (0-1 range) for the ink
            width: Line width in points
        """
        self._drawing_mode = True
        self._ink_color = color
        self._ink_width = width
        self._current_ink_path = []

    def disable_drawing(self):
        """Disable ink/drawing mode."""
        self._drawing_mode = False
        self._current_ink_path = []
        self._update_ink_overlay()

    def copy_selection(self):
        """Copy selected text to clipboard. Call from custom popup."""
        if self._wrapper and self._wrapper.page and self._selected_chars:
            self._wrapper.page.set_clipboard(self.selected_text)
        self.clear_selection()

    # Navigation methods

    def next_page(self) -> bool:
        """Go to the next page. Returns True if successful."""
        if self._source and self._current_page < self._source.page_count - 1:
            self.current_page = self._current_page + 1
            return True
        return False

    def previous_page(self) -> bool:
        """Go to the previous page. Returns True if successful."""
        if self._source and self._current_page > 0:
            self.current_page = self._current_page - 1
            return True
        return False

    def goto(self, page_index: int) -> bool:
        """Go to a specific page. Returns True if successful."""
        if self._source and 0 <= page_index < self._source.page_count:
            self.current_page = page_index
            return True
        return False

    def zoom_in(self, factor: float = 1.25):
        """Increase zoom."""
        self.scale = self._scale * factor

    def zoom_out(self, factor: float = 1.25):
        """Decrease zoom."""
        self.scale = self._scale / factor

    # Internal methods

    def _create_page_container(
        self, page_index: int, page_offset_x: float = 0, page_offset_y: float = 0
    ) -> Tuple[ft.Container, List[SelectableBlock]]:
        """Create a container for a single page and extract text blocks."""
        if not self._source:
            return ft.Container(), []

        page = self._source._get_internal_page(page_index)
        result = render_page_with_pymupdf(page, self._scale)

        canvas_width = page.width * self._scale
        canvas_height = page.height * self._scale

        canvas = cv.Canvas(
            shapes=result.shapes,
            width=canvas_width,
            height=canvas_height,
        )

        # Build content with images
        content_controls = [canvas]
        for img_path, x, y, w, h in result.images:
            if os.path.exists(img_path):
                img_control = ft.Container(
                    content=ft.Image(
                        src=img_path, width=w, height=h, fit=ft.ImageFit.FILL
                    ),
                    left=x,
                    top=y,
                )
                content_controls.append(img_control)

        content_stack = ft.Stack(
            controls=content_controls,
            width=canvas_width,
            height=canvas_height,
        )

        container = ft.Container(
            content=content_stack,
            width=canvas_width,
            height=canvas_height,
            bgcolor=self._bgcolor,
            border_radius=2,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=20,
                color=ft.Colors.with_opacity(0.3, "#000000"),
            ),
        )

        # Extract characters with scaled positions for selection
        chars = page.extract_chars()
        selectable_chars = []
        for char in chars:
            selectable_chars.append(
                SelectableChar(
                    char=char.char,
                    x=char.x * self._scale,
                    y=char.y * self._scale,
                    width=char.width * self._scale,
                    height=char.height * self._scale,
                    page_index=page_index,
                    page_offset_x=page_offset_x,
                    page_offset_y=page_offset_y,
                )
            )

        return container, selectable_chars

    def _build_content(self) -> ft.Control:
        """Build content based on current mode. Returns the content control."""
        self._selectable_chars = []  # Reset selectable characters

        if not self._source:
            return ft.Container()

        if self._mode == PdfViewerMode.SINGLE_PAGE:
            container, chars = self._create_page_container(self._current_page)
            self._selectable_chars.extend(chars)
            return container

        elif self._mode == PdfViewerMode.CONTINUOUS:
            page_containers = []
            y_offset = 0.0
            for i in range(self._source.page_count):
                container, chars = self._create_page_container(i, 0, y_offset)
                page_containers.append(container)
                self._selectable_chars.extend(chars)
                # Calculate offset for next page
                page = self._source._get_internal_page(i)
                y_offset += page.height * self._scale + self._page_gap

            return ft.Column(
                controls=page_containers,
                spacing=self._page_gap,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )

        elif self._mode == PdfViewerMode.DOUBLE_PAGE:
            left_index = self._current_page
            right_index = self._current_page + 1

            left_container, left_chars = self._create_page_container(left_index)
            self._selectable_chars.extend(left_chars)
            pages = [left_container]

            if right_index < self._source.page_count:
                # Calculate x offset for right page
                left_page = self._source._get_internal_page(left_index)
                x_offset = left_page.width * self._scale + self._page_gap
                right_container, right_chars = self._create_page_container(
                    right_index, x_offset, 0
                )
                # Update offsets for right page characters
                for char in right_chars:
                    char.page_offset_x = x_offset
                self._selectable_chars.extend(right_chars)
                pages.append(right_container)

            return ft.Row(
                controls=pages,
                spacing=self._page_gap,
                alignment=ft.MainAxisAlignment.CENTER,
            )

        return ft.Container()

    def _build(self):
        """Build the wrapper and initial content."""
        self._content = self._build_content()

        # Create selection overlay container (will hold highlight rectangles)
        self._selection_overlay = ft.Container(
            content=ft.Stack(controls=[]),
            left=0,
            top=0,
        )

        # Create ink overlay for drawing mode
        self._ink_overlay = ft.Container(
            content=cv.Canvas(shapes=[], width=10000, height=10000),
            left=0,
            top=0,
        )

        # Create selection popup with annotation actions
        self._popup = self._create_popup()

        # Stack content, selection overlay, ink overlay, and popup
        self._content_with_overlay = ft.Stack(
            controls=[
                self._content,
                self._selection_overlay,
                self._ink_overlay,
                self._popup,
            ],
        )

        # Wrap in GestureDetector for text selection
        self._gesture_detector = ft.GestureDetector(
            content=self._content_with_overlay,
            on_pan_start=self._on_pan_start,
            on_pan_update=self._on_pan_update,
            on_pan_end=self._on_pan_end,
            on_tap=self._on_tap,
            drag_interval=10,  # Throttle updates for performance
        )

        self._wrapper = ft.Container(content=self._gesture_detector)

    def _create_popup(self) -> ft.Container:
        """Create the selection popup with annotation actions."""
        # Use custom builder if provided
        if self._popup_builder:
            custom_content = self._popup_builder(self)
            return ft.Container(
                content=custom_content,
                visible=False,
                left=0,
                top=0,
            )

        # Default popup
        return self._create_default_popup()

    def _create_default_popup(self) -> ft.Container:
        """Create the default selection popup."""

        def action_btn(icon: str, tooltip: str, on_click, color: str = "#a1a1a1"):
            def on_hover(e):
                e.control.bgcolor = (
                    "rgba(255,255,255,0.1)" if e.data == "true" else None
                )
                if e.control.page:
                    e.control.update()

            return ft.Container(
                content=ft.Icon(icon, size=20, color=color),
                width=40,
                height=40,
                border_radius=8,
                alignment=ft.alignment.center,
                on_click=on_click,
                tooltip=tooltip,
                on_hover=on_hover,
            )

        popup_content = ft.Row(
            controls=[
                action_btn(ft.Icons.EDIT, "Highlight", self._on_highlight, "#facc15"),
                action_btn(
                    ft.Icons.FORMAT_UNDERLINED,
                    "Underline",
                    self._on_underline,
                    "#3b82f6",
                ),
                action_btn(
                    ft.Icons.FORMAT_STRIKETHROUGH,
                    "Strikethrough",
                    self._on_strikethrough,
                    "#ef4444",
                ),
                ft.Container(width=1, height=24, bgcolor="rgba(255,255,255,0.15)"),
                action_btn(ft.Icons.COPY_ROUNDED, "Copy", self._on_copy, "#a1a1a1"),
            ],
            spacing=2,
        )

        return ft.Container(
            content=popup_content,
            bgcolor="#18181b",
            border=ft.border.all(1, "rgba(255,255,255,0.1)"),
            border_radius=12,
            padding=ft.padding.symmetric(horizontal=6, vertical=4),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=20,
                color=ft.Colors.with_opacity(0.5, "#000000"),
                offset=ft.Offset(0, 4),
            ),
            visible=False,
            left=0,
            top=0,
        )

    def _update_content(self):
        """Update the content inside the wrapper."""
        if not self._wrapper:
            return

        # Clear selection when content changes
        self._selected_blocks = []
        self._selection_start = None
        self._selection_end = None
        self._hide_popup()

        self._content = self._build_content()

        # Rebuild the stack with new content
        if self._content_with_overlay:
            self._content_with_overlay.controls = [
                self._content,
                self._selection_overlay,
                self._popup,
            ]

        # Clear selection overlay
        if self._selection_overlay and self._selection_overlay.content:
            self._selection_overlay.content.controls = []

        if self._wrapper.page:
            self._wrapper.update()

    # Selection event handlers

    def _on_tap(self, e: ft.TapEvent):
        """Handle tap to clear selection or finish drawing."""
        if self._drawing_mode:
            return
        self.clear_selection()

    def _on_pan_start(self, e: ft.DragStartEvent):
        """Handle start of drag - selection or drawing."""
        if self._drawing_mode:
            # Start drawing
            self._current_ink_path = [(e.local_x, e.local_y)]
            self._update_ink_overlay()
        else:
            # Start selection
            self._is_selecting = True
            self._selection_start = (e.local_x, e.local_y)
            self._selection_end = (e.local_x, e.local_y)
            self._selected_chars = []
            self._hide_popup()

    def _on_pan_update(self, e: ft.DragUpdateEvent):
        """Handle drag update - selection or drawing."""
        if self._drawing_mode:
            # Continue drawing
            self._current_ink_path.append((e.local_x, e.local_y))
            self._update_ink_overlay()
        else:
            # Continue selection
            if not self._is_selecting or not self._selection_start:
                return
            self._selection_end = (e.local_x, e.local_y)
            self._update_selection()

    def _on_pan_end(self, e: ft.DragEndEvent):
        """Handle end of drag - selection or drawing."""
        if self._drawing_mode:
            # Finish drawing - save ink annotation
            self._save_ink_annotation()
        else:
            # Finish selection
            self._is_selecting = False
            if self._selected_chars:
                self._show_popup()
            if self._on_selection_change and self._selected_chars:
                self._on_selection_change(self.selected_text)

    # Popup methods

    def _show_popup(self):
        """Show the selection popup near the selection."""
        if not self._popup or not self._selected_chars:
            return

        # Find the bounding box of all selected characters
        min_x = min(c.x + c.page_offset_x for c in self._selected_chars)
        min_y = min(c.y + c.page_offset_y for c in self._selected_chars)
        max_x = max(c.x + c.page_offset_x + c.width for c in self._selected_chars)

        # Position popup above the selection, centered
        popup_width = 200  # Approximate width
        popup_x = min_x + (max_x - min_x) / 2 - popup_width / 2
        popup_y = min_y - 50  # Above the selection

        # Ensure popup doesn't go off-screen (left edge)
        popup_x = max(10, popup_x)

        self._popup.left = popup_x
        self._popup.top = max(10, popup_y)  # Don't go above top edge
        self._popup.visible = True
        self._popup_visible = True

        if self._popup.page:
            self._popup.update()

    def _hide_popup(self):
        """Hide the selection popup."""
        if self._popup:
            self._popup.visible = False
            self._popup_visible = False
            if self._popup.page:
                self._popup.update()

    # Annotation action handlers

    def _on_highlight(self, e):
        """Add highlight annotation to selected text."""
        self._add_annotation("highlight", (1.0, 0.92, 0.23))  # Yellow

    def _on_underline(self, e):
        """Add underline annotation to selected text."""
        self._add_annotation("underline", (0.38, 0.65, 0.98))  # Blue

    def _on_strikethrough(self, e):
        """Add strikethrough annotation to selected text."""
        self._add_annotation("strikethrough", (0.97, 0.44, 0.44))  # Red

    def _on_copy(self, e):
        """Copy selected text to clipboard."""
        if self._wrapper and self._wrapper.page and self._selected_chars:
            self._wrapper.page.set_clipboard(self.selected_text)
        self.clear_selection()

    def _add_annotation(self, annotation_type: str, color: Tuple[float, float, float]):
        """Add annotation to selected characters and re-render."""
        if not self._source or not self._selected_chars:
            return

        # Group characters by page and merge into line rectangles
        chars_by_page: dict = {}
        for char in self._selected_chars:
            if char.page_index not in chars_by_page:
                chars_by_page[char.page_index] = []
            chars_by_page[char.page_index].append(char)

        # Add annotations to each page
        for page_index, chars in chars_by_page.items():
            # Merge adjacent characters into continuous rectangles
            rects = self._merge_char_rects(chars)
            if annotation_type == "highlight":
                self._source.add_highlight(page_index, rects, color)
            elif annotation_type == "underline":
                self._source.add_underline(page_index, rects, color)
            elif annotation_type == "strikethrough":
                self._source.add_strikethrough(page_index, rects, color)
            elif annotation_type == "squiggly":
                self._source.add_squiggly(page_index, rects, color)

        # Clear selection and hide popup
        self.clear_selection()

        # Re-render to show annotations
        self._update_content()

    def _merge_char_rects(
        self, chars: List[SelectableChar]
    ) -> List[Tuple[float, float, float, float]]:
        """Merge adjacent characters into continuous rectangles for annotations."""
        if not chars:
            return []

        # Sort by y position (line), then x position
        sorted_chars = sorted(chars, key=lambda c: (round(c.y / 10), c.x))

        rects = []
        current_rect = None
        last_y = None

        for char in sorted_chars:
            # Convert to PDF coordinates
            char_rect = (
                char.x / self._scale,
                char.y / self._scale,
                (char.x + char.width) / self._scale,
                (char.y + char.height) / self._scale,
            )

            if current_rect is None:
                current_rect = list(char_rect)
                last_y = char.y
            elif abs(char.y - last_y) < char.height * 0.5:
                # Same line - extend the rectangle
                current_rect[2] = char_rect[2]  # Extend right edge
                current_rect[1] = min(current_rect[1], char_rect[1])  # Min top
                current_rect[3] = max(current_rect[3], char_rect[3])  # Max bottom
            else:
                # New line - save current rect and start new one
                rects.append(tuple(current_rect))
                current_rect = list(char_rect)
                last_y = char.y

        if current_rect:
            rects.append(tuple(current_rect))

        return rects

    def _update_selection(self):
        """Update selected characters based on selection rectangle.

        When spanning multiple lines, extends selection:
        - First line: from first selected char to end of line
        - Middle lines: all characters
        - Last line: from start of line to last selected char
        """
        if not self._selection_start or not self._selection_end:
            return

        # Calculate selection rectangle (normalize coordinates)
        x1 = min(self._selection_start[0], self._selection_end[0])
        y1 = min(self._selection_start[1], self._selection_end[1])
        x2 = max(self._selection_start[0], self._selection_end[0])
        y2 = max(self._selection_start[1], self._selection_end[1])

        # First pass: find directly intersecting characters
        directly_selected = []
        for char in self._selectable_chars:
            char_x1 = char.x + char.page_offset_x
            char_y1 = char.y + char.page_offset_y
            char_x2 = char_x1 + char.width
            char_y2 = char_y1 + char.height

            if self._rects_intersect(
                x1, y1, x2, y2, char_x1, char_y1, char_x2, char_y2
            ):
                directly_selected.append(char)

        if not directly_selected:
            self._selected_chars = []
            self._update_selection_overlay()
            return

        # Group directly selected by line
        lines: dict = {}
        for char in directly_selected:
            y_key = round((char.y + char.page_offset_y) / 10)
            if y_key not in lines:
                lines[y_key] = []
            lines[y_key].append(char)

        # Single line - no extension needed
        if len(lines) <= 1:
            self._selected_chars = directly_selected
            self._update_selection_overlay()
            return

        # Multiple lines - extend selection to line edges
        sorted_line_keys = sorted(lines.keys())
        first_line_key = sorted_line_keys[0]
        last_line_key = sorted_line_keys[-1]

        # Find first selected char x position on first line
        first_line_chars = sorted(
            lines[first_line_key], key=lambda c: c.x + c.page_offset_x
        )
        first_selected_x = first_line_chars[0].x + first_line_chars[0].page_offset_x

        # Find last selected char x position on last line
        last_line_chars = sorted(
            lines[last_line_key], key=lambda c: c.x + c.page_offset_x
        )
        last_selected_x = (
            last_line_chars[-1].x
            + last_line_chars[-1].page_offset_x
            + last_line_chars[-1].width
        )

        # Build extended selection
        self._selected_chars = []
        for char in self._selectable_chars:
            char_x1 = char.x + char.page_offset_x
            char_y1 = char.y + char.page_offset_y
            char_y_key = round(char_y1 / 10)

            # Check if this char's line is within the selected line range
            if char_y_key < first_line_key or char_y_key > last_line_key:
                continue

            if char_y_key == first_line_key:
                # First line: include chars from first selected position to end of line
                if char_x1 >= first_selected_x - 1:  # Small tolerance
                    self._selected_chars.append(char)
            elif char_y_key == last_line_key:
                # Last line: include chars from start of line to last selected position
                char_x2 = char_x1 + char.width
                if char_x2 <= last_selected_x + 1:  # Small tolerance
                    self._selected_chars.append(char)
            else:
                # Middle lines: include all characters
                self._selected_chars.append(char)

        self._update_selection_overlay()

    def _rects_intersect(
        self,
        ax1: float,
        ay1: float,
        ax2: float,
        ay2: float,
        bx1: float,
        by1: float,
        bx2: float,
        by2: float,
    ) -> bool:
        """Check if two rectangles intersect."""
        return ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1

    def _update_selection_overlay(self):
        """Update the selection highlight overlay."""
        if not self._selection_overlay or not self._selection_overlay.content:
            return

        highlight_controls = []

        # Merge adjacent characters into continuous highlight rectangles for better appearance
        if self._selected_chars:
            merged_rects = self._merge_highlight_rects(self._selected_chars)
            for rect in merged_rects:
                highlight = ft.Container(
                    left=rect[0],
                    top=rect[1],
                    width=rect[2] - rect[0],
                    height=rect[3] - rect[1],
                    bgcolor=ft.Colors.with_opacity(0.3, self._selection_color),
                )
                highlight_controls.append(highlight)

        self._selection_overlay.content.controls = highlight_controls

        if self._wrapper and self._wrapper.page:
            self._selection_overlay.update()

    def _update_ink_overlay(self):
        """Update the ink drawing overlay while drawing."""
        if not self._ink_overlay or not self._ink_overlay.content:
            return

        if not self._current_ink_path or len(self._current_ink_path) < 2:
            self._ink_overlay.content.shapes = []
            if self._wrapper and self._wrapper.page and self._ink_overlay.page:
                self._ink_overlay.update()
            return

        # Convert color to hex
        r, g, b = self._ink_color
        hex_color = f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"

        # Create line segments for the path
        shapes = []
        for i in range(len(self._current_ink_path) - 1):
            x1, y1 = self._current_ink_path[i]
            x2, y2 = self._current_ink_path[i + 1]
            shapes.append(
                cv.Line(
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    paint=ft.Paint(
                        stroke_width=self._ink_width * self._scale,
                        color=hex_color,
                        stroke_cap=ft.StrokeCap.ROUND,
                    ),
                )
            )

        self._ink_overlay.content.shapes = shapes
        if self._wrapper and self._wrapper.page and self._ink_overlay.page:
            self._ink_overlay.update()

    def _save_ink_annotation(self):
        """Save the current ink path as an annotation."""
        if (
            not self._source
            or not self._current_ink_path
            or len(self._current_ink_path) < 2
        ):
            self._current_ink_path = []
            self._update_ink_overlay()
            return

        # Convert scaled coordinates to PDF coordinates
        pdf_path = [
            (x / self._scale, y / self._scale) for x, y in self._current_ink_path
        ]

        # Add ink annotation to current page
        self._source.add_ink(
            self._current_page,
            [pdf_path],
            self._ink_color,
            self._ink_width,
        )

        # Clear the drawing path
        self._current_ink_path = []
        self._update_ink_overlay()

        # Re-render to show the annotation
        self._update_content()

    def _merge_highlight_rects(
        self, chars: List[SelectableChar]
    ) -> List[Tuple[float, float, float, float]]:
        """Merge adjacent characters into continuous highlight rectangles.

        When spanning multiple lines, extends:
        - First line: from first selected char to end of line
        - Middle lines: full line width
        - Last line: from start of line to last selected char
        """
        if not chars:
            return []

        # Group characters by line (based on y position)
        lines: dict = {}  # y_key -> list of chars
        for char in chars:
            # Round y to group chars on same line
            y_key = round((char.y + char.page_offset_y) / 10)
            if y_key not in lines:
                lines[y_key] = []
            lines[y_key].append(char)

        if len(lines) <= 1:
            # Single line - just merge normally (no extension)
            sorted_chars = sorted(chars, key=lambda c: c.x + c.page_offset_x)
            if not sorted_chars:
                return []

            first = sorted_chars[0]
            last = sorted_chars[-1]

            x1 = first.x + first.page_offset_x
            x2 = last.x + last.page_offset_x + last.width
            y1 = min(c.y + c.page_offset_y for c in sorted_chars)
            y2 = max(c.y + c.page_offset_y + c.height for c in sorted_chars)

            return [(x1, y1, x2, y2)]

        # Multiple lines - need to extend to line edges
        sorted_line_keys = sorted(lines.keys())
        rects = []

        # Find line boundaries from ALL selectable chars (not just selected)
        line_bounds: dict = {}  # y_key -> (min_x, max_x)
        for char in self._selectable_chars:
            y_key = round((char.y + char.page_offset_y) / 10)
            char_x1 = char.x + char.page_offset_x
            char_x2 = char_x1 + char.width
            if y_key not in line_bounds:
                line_bounds[y_key] = [char_x1, char_x2]
            else:
                line_bounds[y_key][0] = min(line_bounds[y_key][0], char_x1)
                line_bounds[y_key][1] = max(line_bounds[y_key][1], char_x2)

        for i, y_key in enumerate(sorted_line_keys):
            line_chars = sorted(lines[y_key], key=lambda c: c.x + c.page_offset_x)
            if not line_chars:
                continue

            first_char = line_chars[0]
            last_char = line_chars[-1]

            # Get y bounds for this line
            y1 = min(c.y + c.page_offset_y for c in line_chars)
            y2 = max(c.y + c.page_offset_y + c.height for c in line_chars)

            # Get line boundaries
            line_start = line_bounds.get(
                y_key, [first_char.x + first_char.page_offset_x, 0]
            )[0]
            line_end = line_bounds.get(
                y_key, [0, last_char.x + last_char.page_offset_x + last_char.width]
            )[1]

            if i == 0:
                # First line: from first selected char to end of line
                x1 = first_char.x + first_char.page_offset_x
                x2 = line_end
            elif i == len(sorted_line_keys) - 1:
                # Last line: from start of line to last selected char
                x1 = line_start
                x2 = last_char.x + last_char.page_offset_x + last_char.width
            else:
                # Middle line: full line width
                x1 = line_start
                x2 = line_end

            rects.append((x1, y1, x2, y2))

        return rects
