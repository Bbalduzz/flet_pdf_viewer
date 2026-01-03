"""
PDF Viewer - Main viewer component.

Composes backends, rendering, and interactions into a single component.
"""

from __future__ import annotations

import os
import webbrowser
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple, Union

if TYPE_CHECKING:
    from . import PdfDocument

import flet as ft
import flet.canvas as cv

from .backends.base import DocumentBackend
from .interactions.drawing import DrawingHandler
from .interactions.selection import SelectionHandler
from .interactions.shapes import ShapeDrawingHandler
from .rendering.renderer import PageRenderer
from .types import (
    Color,
    LinkInfo,
    PageShadow,
    SearchOptions,
    SearchResult,
    SelectableChar,
    ShapeType,
    TocItem,
    ViewerCallbacks,
    ViewerMode,
    ViewerStyle,
    ZoomConfig,
)


class PdfViewer:
    """
    PDF Viewer component.

    Usage:
        from flet_pdf_viewer import PdfDocument, PdfViewer, ViewerMode

        document = PdfDocument("/path/to/file.pdf")
        viewer = PdfViewer(document)
        page.add(viewer.control)

    With configuration:
        from flet_pdf_viewer import ViewerStyle, ZoomConfig, ViewerCallbacks

        viewer = PdfViewer(
            document,
            page=0,
            mode=ViewerMode.CONTINUOUS,
            style=ViewerStyle(bgcolor="#f0f0f0"),
            zoom=ZoomConfig(initial=1.5, max=10.0),
            callbacks=ViewerCallbacks(on_page_change=my_handler),
        )
    """

    def __init__(
        self,
        source: Union[DocumentBackend, "PdfDocument", None] = None,
        *,
        # View state
        page: int = 0,
        mode: ViewerMode = ViewerMode.SINGLE_PAGE,
        # Grouped configuration
        style: Optional[ViewerStyle] = None,
        zoom: Optional[ZoomConfig] = None,
        callbacks: Optional[ViewerCallbacks] = None,
        # Customization
        popup_builder: Optional[Callable[["PdfViewer"], ft.Control]] = None,
    ):
        # Apply defaults for config groups
        style = style or ViewerStyle()
        zoom = zoom or ZoomConfig()
        callbacks = callbacks or ViewerCallbacks()

        # Store source and view state
        self._source = source
        self._current_page = page
        self._scale = zoom.initial
        self._mode = mode

        # Store style settings
        self._page_gap = style.page_gap
        self._bgcolor = style.bgcolor
        self._selection_color = style.selection_color
        self._page_shadow = style.page_shadow
        self._border_radius = style.border_radius

        # Store zoom settings
        self._interactive_zoom = zoom.enabled
        self._min_scale = zoom.min
        self._max_scale = zoom.max

        # Store callbacks
        self._on_page_change = callbacks.on_page_change
        self._on_link_click = callbacks.on_link_click
        self._on_text_box_drawn = callbacks.on_text_box_drawn

        # Store popup builder
        self._popup_builder = popup_builder

        # Components
        self._renderer = PageRenderer(self._scale)
        self._selection = SelectionHandler(callbacks.on_selection_change)
        self._drawing = DrawingHandler()
        self._shape_drawing = ShapeDrawingHandler()

        # Search state
        self._search_results: List[SearchResult] = []
        self._search_index: int = -1  # Current result index (-1 = none)
        self._search_query: str = ""
        self._search_options: SearchOptions = SearchOptions()

        # UI state
        self._wrapper: Optional[ft.Container] = None
        self._content: Optional[ft.Control] = None
        self._content_with_overlay: Optional[ft.Stack] = None
        self._selection_overlay: Optional[ft.Container] = None
        self._ink_overlay: Optional[ft.Container] = None
        self._shape_overlay: Optional[ft.Container] = None
        self._link_overlay: Optional[ft.Container] = None
        self._search_overlay: Optional[ft.Container] = None
        self._popup: Optional[ft.Container] = None
        self._interactive_viewer: Optional[ft.InteractiveViewer] = None

        # Links storage: list of (LinkInfo, scaled_rect, page_offset_x, page_offset_y)
        self._links: List[
            Tuple[LinkInfo, Tuple[float, float, float, float], float, float]
        ] = []

        self._build()

    # Properties

    @property
    def control(self) -> ft.Control:
        """The Flet control to add to a page."""
        return self._wrapper

    @property
    def source(self) -> Optional[DocumentBackend]:
        """The PDF document being displayed."""
        return self._source

    @source.setter
    def source(self, value: Optional[DocumentBackend]):
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
        """Zoom scale."""
        return self._scale

    @scale.setter
    def scale(self, value: float):
        self._scale = max(0.1, min(5.0, value))
        self._renderer.scale = self._scale
        self._update_content()

    @property
    def mode(self) -> ViewerMode:
        """Display mode."""
        return self._mode

    @mode.setter
    def mode(self, value: ViewerMode):
        if self._mode != value:
            self._mode = value
            self._update_content()

    @property
    def page_count(self) -> int:
        """Total number of pages."""
        return self._source.page_count if self._source else 0

    @property
    def selected_text(self) -> str:
        """Currently selected text."""
        return self._selection.selected_text

    @property
    def drawing_mode(self) -> bool:
        """Whether ink drawing mode is active."""
        return self._drawing.enabled

    @property
    def shape_drawing_mode(self) -> bool:
        """Whether shape drawing mode is active."""
        return self._shape_drawing.enabled

    @property
    def current_shape_type(self) -> ShapeType:
        """Current shape type being drawn."""
        return self._shape_drawing.shape_type

    # Search properties

    @property
    def search_results(self) -> List[SearchResult]:
        """All search results in the document."""
        return self._search_results

    @property
    def search_result_count(self) -> int:
        """Number of search results."""
        return len(self._search_results)

    @property
    def current_search_index(self) -> int:
        """Current search result index (0-based), or -1 if none."""
        return self._search_index

    @property
    def current_search_result(self) -> Optional[SearchResult]:
        """Current search result, or None if none selected."""
        if 0 <= self._search_index < len(self._search_results):
            return self._search_results[self._search_index]
        return None

    # Navigation

    def next_page(self) -> bool:
        """Go to next page."""
        if self._source and self._current_page < self._source.page_count - 1:
            self.current_page = self._current_page + 1
            return True
        return False

    def previous_page(self) -> bool:
        """Go to previous page."""
        if self._source and self._current_page > 0:
            self.current_page = self._current_page - 1
            return True
        return False

    def goto(self, page_index: int) -> bool:
        """Go to specific page."""
        if self._source and 0 <= page_index < self._source.page_count:
            self.current_page = page_index
            return True
        return False

    def goto_destination(self, name: str) -> bool:
        """Go to a named destination/anchor.

        Args:
            name: The named destination (e.g., "chapter1", "section2.3")

        Returns:
            True if destination was found and navigated to, False otherwise

        Example:
            viewer.goto_destination("chapter1")
            viewer.goto_destination("page.5")  # Some PDFs use this format
        """
        if not self._source:
            return False

        page_index = self._source.resolve_named_destination(name)
        if page_index is not None:
            return self.goto(page_index)
        return False

    def zoom_in(self, factor: float = 1.25):
        """Increase zoom."""
        self.scale = self._scale * factor

    def zoom_out(self, factor: float = 1.25):
        """Decrease zoom."""
        self.scale = self._scale / factor

    # Selection actions

    def clear_selection(self):
        """Clear text selection."""
        self._selection.clear()
        self._hide_popup()
        self._update_selection_overlay()

    def highlight_selection(self, color: Color = (1.0, 0.92, 0.23)):
        """Add highlight annotation."""
        self._add_annotation("highlight", color)

    def underline_selection(self, color: Color = (0.38, 0.65, 0.98)):
        """Add underline annotation."""
        self._add_annotation("underline", color)

    def strikethrough_selection(self, color: Color = (0.97, 0.44, 0.44)):
        """Add strikethrough annotation."""
        self._add_annotation("strikethrough", color)

    def squiggly_selection(self, color: Color = (0.0, 0.8, 0.0)):
        """Add squiggly underline annotation."""
        self._add_annotation("squiggly", color)

    def add_note_at_selection(
        self,
        text: str,
        icon: str = "Note",
        color: Color = (1.0, 0.92, 0.0),
    ):
        """Add sticky note at selection."""
        if not self._source or not self._selection.selected_chars:
            return

        first_char = min(
            self._selection.selected_chars,
            key=lambda c: (c.page_index, c.y, c.x),
        )
        point = (first_char.x / self._scale, first_char.y / self._scale)

        page = self._source.get_page(first_char.page_index)
        page.add_text_note(point, text, icon, color)

        self.clear_selection()
        self._update_content()

    def copy_selection(self):
        """Copy selected text to clipboard."""
        if self._wrapper and self._wrapper.page and self._selection.selected_chars:
            self._wrapper.page.set_clipboard(self.selected_text)
        self.clear_selection()

    # Interactive Viewer control

    def _update_interactive_pan(self):
        """Update InteractiveViewer pan state based on drawing modes."""
        if self._interactive_viewer:
            # Disable pan when any drawing mode is active
            drawing_active = self._drawing.enabled or self._shape_drawing.enabled
            self._interactive_viewer.pan_enabled = not drawing_active
            if self._interactive_viewer.page:
                self._interactive_viewer.update()

    def reset_view(self):
        """Reset the InteractiveViewer to default position and scale."""
        if self._interactive_viewer:
            self._interactive_viewer.reset()

    # Drawing

    def enable_drawing(self, color: Color = (0.0, 0.0, 0.0), width: float = 2.0):
        """Enable ink drawing mode."""
        # Disable shape drawing if active
        self._shape_drawing.disable()
        self._drawing.enable(color, width)
        self._update_interactive_pan()

    def disable_drawing(self):
        """Disable ink drawing mode."""
        self._drawing.disable()
        self._update_ink_overlay()
        self._update_interactive_pan()

    # Shape Drawing

    def enable_shape_drawing(
        self,
        shape_type: ShapeType,
        stroke_color: Color = (0.0, 0.0, 0.0),
        fill_color: Optional[Color] = None,
        stroke_width: float = 2.0,
    ):
        """Enable shape drawing mode.

        Args:
            shape_type: The type of shape to draw (RECTANGLE, CIRCLE, LINE, ARROW)
            stroke_color: Border/stroke color as RGB tuple (0-1 range)
            fill_color: Fill color as RGB tuple, or None for no fill
            stroke_width: Stroke width in points
        """
        # Disable ink drawing if active
        self._drawing.disable()
        self._shape_drawing.enable(shape_type, stroke_color, fill_color, stroke_width)
        self._update_interactive_pan()

    def disable_shape_drawing(self):
        """Disable shape drawing mode."""
        self._shape_drawing.disable()
        self._update_shape_overlay()
        self._update_interactive_pan()

    def enable_rectangle_drawing(
        self,
        stroke_color: Color = (0.0, 0.0, 0.0),
        fill_color: Optional[Color] = None,
        stroke_width: float = 2.0,
    ):
        """Enable rectangle drawing mode (convenience method)."""
        self.enable_shape_drawing(
            ShapeType.RECTANGLE, stroke_color, fill_color, stroke_width
        )

    def enable_circle_drawing(
        self,
        stroke_color: Color = (0.0, 0.0, 0.0),
        fill_color: Optional[Color] = None,
        stroke_width: float = 2.0,
    ):
        """Enable circle/ellipse drawing mode (convenience method)."""
        self.enable_shape_drawing(
            ShapeType.CIRCLE, stroke_color, fill_color, stroke_width
        )

    def enable_line_drawing(
        self,
        color: Color = (0.0, 0.0, 0.0),
        width: float = 2.0,
    ):
        """Enable line drawing mode (convenience method)."""
        self.enable_shape_drawing(ShapeType.LINE, color, None, width)

    def enable_arrow_drawing(
        self,
        color: Color = (0.0, 0.0, 0.0),
        width: float = 2.0,
    ):
        """Enable arrow drawing mode (convenience method)."""
        self.enable_shape_drawing(ShapeType.ARROW, color, None, width)

    def enable_text_drawing(
        self,
        stroke_color: Color = (0.0, 0.0, 0.0),
        fill_color: Optional[Color] = (1.0, 1.0, 0.9),
        stroke_width: float = 1.0,
    ):
        """Enable text box drawing mode (convenience method).

        Draw a rectangle where you want the text box to appear.
        After drawing, the on_text_box_drawn callback will be called
        with the rect coordinates (in PDF points).
        """
        self.enable_shape_drawing(
            ShapeType.TEXT, stroke_color, fill_color, stroke_width
        )

    # Search methods

    def search(
        self,
        query: str,
        case_sensitive: bool = False,
        whole_word: bool = False,
        start_page: Optional[int] = None,
    ) -> List[SearchResult]:
        """Search for text in the document.

        Searches all pages and stores results. Use search_next/search_prev
        to navigate between results.

        Args:
            query: Text to search for
            case_sensitive: Whether search is case-sensitive
            whole_word: Whether to match whole words only
            start_page: Page to start searching from (default: current page)

        Returns:
            List of all SearchResult objects found
        """
        if not self._source or not query:
            self.clear_search()
            return []

        self._search_query = query
        self._search_options = SearchOptions(
            case_sensitive=case_sensitive,
            whole_word=whole_word,
        )
        self._search_results = []

        # Search all pages
        for page_idx in range(self._source.page_count):
            page = self._source.get_page(page_idx)
            page_results = page.search_text(query, case_sensitive, whole_word)
            self._search_results.extend(page_results)

        # Set initial search index
        if self._search_results:
            # Find first result on or after current page
            start = start_page if start_page is not None else self._current_page
            self._search_index = 0
            for i, result in enumerate(self._search_results):
                if result.page_index >= start:
                    self._search_index = i
                    break

            # Navigate to the result
            self._goto_search_result(self._search_index)
        else:
            self._search_index = -1

        self._update_search_overlay()
        return self._search_results

    def search_next(self) -> Optional[SearchResult]:
        """Go to next search result.

        Returns:
            The next SearchResult, or None if no results
        """
        if not self._search_results:
            return None

        self._search_index = (self._search_index + 1) % len(self._search_results)
        self._goto_search_result(self._search_index)
        self._update_search_overlay()
        return self._search_results[self._search_index]

    def search_prev(self) -> Optional[SearchResult]:
        """Go to previous search result.

        Returns:
            The previous SearchResult, or None if no results
        """
        if not self._search_results:
            return None

        self._search_index = (self._search_index - 1) % len(self._search_results)
        self._goto_search_result(self._search_index)
        self._update_search_overlay()
        return self._search_results[self._search_index]

    def goto_search_result(self, index: int) -> Optional[SearchResult]:
        """Go to a specific search result by index.

        Args:
            index: The 0-based index of the result to go to

        Returns:
            The SearchResult at that index, or None if invalid
        """
        if not self._search_results or not (0 <= index < len(self._search_results)):
            return None

        self._search_index = index
        self._goto_search_result(index)
        self._update_search_overlay()
        return self._search_results[index]

    def clear_search(self):
        """Clear search results and highlights."""
        self._search_results = []
        self._search_index = -1
        self._search_query = ""
        self._update_search_overlay()

    def _goto_search_result(self, index: int):
        """Navigate to a search result."""
        if not (0 <= index < len(self._search_results)):
            return

        result = self._search_results[index]

        # Navigate to the page if not in continuous mode
        if self._mode != ViewerMode.CONTINUOUS:
            if result.page_index != self._current_page:
                self.goto(result.page_index)

    # Private methods

    def _build(self):
        """Build the viewer UI."""
        self._content = self._build_content()

        self._selection_overlay = ft.Container(
            content=ft.Stack(controls=[]),
            left=0,
            top=0,
        )

        self._ink_overlay = ft.Container(
            content=cv.Canvas(shapes=[], width=10000, height=10000),
            left=0,
            top=0,
        )

        self._shape_overlay = ft.Container(
            content=cv.Canvas(shapes=[], width=10000, height=10000),
            left=0,
            top=0,
        )

        self._link_overlay = ft.Container(
            content=ft.Stack(controls=[]),
            left=0,
            top=0,
        )

        self._search_overlay = ft.Container(
            content=ft.Stack(controls=[]),
            left=0,
            top=0,
        )

        self._popup = self._create_popup()

        self._content_with_overlay = ft.Stack(
            controls=[
                self._content,
                self._link_overlay,
                self._search_overlay,
                self._selection_overlay,
                self._ink_overlay,
                self._shape_overlay,
                self._popup,
            ],
        )

        gesture_detector = ft.GestureDetector(
            content=self._content_with_overlay,
            on_pan_start=self._on_pan_start,
            on_pan_update=self._on_pan_update,
            on_pan_end=self._on_pan_end,
            on_tap_down=self._on_tap,
            drag_interval=10,
        )

        if self._interactive_zoom:
            self._interactive_viewer = ft.InteractiveViewer(
                content=gesture_detector,
                min_scale=self._min_scale,
                max_scale=self._max_scale,
                pan_enabled=True,
                scale_enabled=True,
                trackpad_scroll_causes_scale=False,
                boundary_margin=100,
            )
            self._wrapper = ft.Container(content=self._interactive_viewer)
        else:
            self._wrapper = ft.Container(content=gesture_detector)

    def _build_content(self) -> ft.Control:
        """Build page content based on mode."""
        selectable_chars: List[SelectableChar] = []
        self._links = []  # Reset links

        if not self._source:
            return ft.Container()

        if self._mode == ViewerMode.SINGLE_PAGE:
            container, chars, links = self._create_page_container(self._current_page)
            selectable_chars.extend(chars)
            self._links.extend(links)
            content = container

        elif self._mode == ViewerMode.CONTINUOUS:
            page_containers = []
            y_offset = 0.0

            # Lazy loading for large documents: only render pages within a window
            # For smaller documents (<=20 pages), render all for smooth scrolling
            # Threshold can be adjusted based on performance needs
            lazy_load_threshold = 20
            use_lazy_loading = self._source.page_count > lazy_load_threshold

            if use_lazy_loading:
                # Render current page +/- buffer, use placeholders for rest
                render_buffer = 5  # Larger buffer for better scroll experience
                render_start = max(0, self._current_page - render_buffer)
                render_end = min(
                    self._source.page_count, self._current_page + render_buffer + 1
                )
            else:
                # Render all pages for small documents
                render_start = 0
                render_end = self._source.page_count

            for i in range(self._source.page_count):
                page = self._source.get_page(i)
                page_height = page.height * self._scale
                page_width = page.width * self._scale

                if render_start <= i < render_end:
                    # Fully render pages in the visible window
                    container, chars, links = self._create_page_container(
                        i, 0, y_offset
                    )
                    selectable_chars.extend(chars)
                    self._links.extend(links)
                else:
                    # Placeholder for pages outside visible window
                    container = ft.Container(
                        width=page_width,
                        height=page_height,
                        bgcolor=self._bgcolor,
                        border_radius=self._border_radius,
                        shadow=self._create_box_shadow(),
                    )

                page_containers.append(container)
                y_offset += page_height + self._page_gap

            content = ft.Column(
                controls=page_containers,
                spacing=self._page_gap,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )

        elif self._mode == ViewerMode.DOUBLE_PAGE:
            left_index = self._current_page
            right_index = self._current_page + 1

            left_container, left_chars, left_links = self._create_page_container(
                left_index
            )
            selectable_chars.extend(left_chars)
            self._links.extend(left_links)
            pages = [left_container]

            if right_index < self._source.page_count:
                left_page = self._source.get_page(left_index)
                x_offset = left_page.width * self._scale + self._page_gap

                right_container, right_chars, right_links = self._create_page_container(
                    right_index, x_offset, 0
                )
                for char in right_chars:
                    char.page_offset_x = x_offset
                selectable_chars.extend(right_chars)
                self._links.extend(right_links)
                pages.append(right_container)

            content = ft.Row(
                controls=pages,
                spacing=self._page_gap,
                alignment=ft.MainAxisAlignment.CENTER,
            )

        else:
            content = ft.Container()

        self._selection.set_selectable_chars(selectable_chars)
        self._update_link_overlay()
        return content

    def _create_box_shadow(self) -> Optional[ft.BoxShadow]:
        """Create a BoxShadow from the page shadow configuration."""
        if self._page_shadow is None:
            return None

        return ft.BoxShadow(
            blur_radius=self._page_shadow.blur_radius,
            spread_radius=self._page_shadow.spread_radius,
            color=self._page_shadow.color,
            offset=ft.Offset(self._page_shadow.offset_x, self._page_shadow.offset_y),
        )

    def _create_page_container(
        self, page_index: int, offset_x: float = 0, offset_y: float = 0
    ) -> Tuple[
        ft.Container,
        List[SelectableChar],
        List[Tuple[LinkInfo, Tuple[float, float, float, float], float, float]],
    ]:
        """Create a container for a single page."""
        if not self._source:
            return ft.Container(), [], []

        page = self._source.get_page(page_index)
        result = self._renderer.render(page)

        canvas_width = page.width * self._scale
        canvas_height = page.height * self._scale

        canvas = cv.Canvas(
            shapes=result.shapes,
            width=canvas_width,
            height=canvas_height,
        )

        content_controls = [canvas]
        for img_path, x, y, w, h in result.images:
            if os.path.exists(img_path):
                content_controls.append(
                    ft.Container(
                        content=ft.Image(
                            src=img_path, width=w, height=h, fit=ft.ImageFit.FILL
                        ),
                        left=x,
                        top=y,
                    )
                )

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
            border_radius=self._border_radius,
            shadow=self._create_box_shadow(),
        )

        chars = self._renderer.build_selectable_chars(
            page, page_index, offset_x, offset_y
        )

        # Extract links and scale them
        links = []
        for link in page.get_links():
            x0, y0, x1, y1 = link.rect
            scaled_rect = (
                x0 * self._scale,
                y0 * self._scale,
                x1 * self._scale,
                y1 * self._scale,
            )
            links.append((link, scaled_rect, offset_x, offset_y))

        return container, chars, links

    def _update_content(self):
        """Update the viewer content."""
        if not self._wrapper:
            return

        self._selection.clear()
        self._hide_popup()

        self._content = self._build_content()

        if self._content_with_overlay:
            self._content_with_overlay.controls = [
                self._content,
                self._link_overlay,
                self._search_overlay,
                self._selection_overlay,
                self._ink_overlay,
                self._shape_overlay,
                self._popup,
            ]

        if self._selection_overlay and self._selection_overlay.content:
            self._selection_overlay.content.controls = []

        if self._wrapper.page:
            self._wrapper.update()

    # Event handlers

    def _on_tap(self, e: ft.TapEvent):
        # Check if tap is on a link
        tap_x, tap_y = e.local_x, e.local_y
        clicked_link = self._find_link_at(tap_x, tap_y)

        if clicked_link:
            self._handle_link_click(clicked_link)
            return

        if not self._drawing.enabled and not self._shape_drawing.enabled:
            self.clear_selection()

    def _on_pan_start(self, e: ft.DragStartEvent):
        if self._drawing.enabled:
            self._drawing.start_stroke(e.local_x, e.local_y)
            self._update_ink_overlay()
        elif self._shape_drawing.enabled:
            self._shape_drawing.start_shape(e.local_x, e.local_y)
            self._update_shape_overlay()
        else:
            self._selection.start_selection(e.local_x, e.local_y)
            self._hide_popup()

    def _on_pan_update(self, e: ft.DragUpdateEvent):
        if self._drawing.enabled:
            self._drawing.add_point(e.local_x, e.local_y)
            self._update_ink_overlay()
        elif self._shape_drawing.enabled:
            self._shape_drawing.update_shape(e.local_x, e.local_y)
            self._update_shape_overlay()
        else:
            self._selection.update_selection(e.local_x, e.local_y)
            self._update_selection_overlay()

    def _on_pan_end(self, e: ft.DragEndEvent):
        if self._drawing.enabled:
            self._save_ink_annotation()
        elif self._shape_drawing.enabled:
            self._save_shape_annotation()
        else:
            self._selection.end_selection()
            if self._selection.selected_chars:
                self._show_popup()

    # Popup

    def _create_popup(self) -> ft.Container:
        """Create selection popup."""
        if self._popup_builder:
            return ft.Container(
                content=self._popup_builder(self),
                visible=False,
                left=0,
                top=0,
            )
        return self._create_default_popup()

    def _create_default_popup(self) -> ft.Container:
        """Create default popup."""

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
                action_btn(
                    ft.Icons.EDIT,
                    "Highlight",
                    lambda e: self.highlight_selection(),
                    "#facc15",
                ),
                action_btn(
                    ft.Icons.FORMAT_UNDERLINED,
                    "Underline",
                    lambda e: self.underline_selection(),
                    "#3b82f6",
                ),
                action_btn(
                    ft.Icons.FORMAT_STRIKETHROUGH,
                    "Strikethrough",
                    lambda e: self.strikethrough_selection(),
                    "#ef4444",
                ),
                ft.Container(width=1, height=24, bgcolor="rgba(255,255,255,0.15)"),
                action_btn(
                    ft.Icons.COPY_ROUNDED,
                    "Copy",
                    lambda e: self.copy_selection(),
                    "#a1a1a1",
                ),
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

    def _show_popup(self):
        """Show popup near selection."""
        if not self._popup or not self._selection.selected_chars:
            return

        chars = self._selection.selected_chars
        min_x = min(c.x + c.page_offset_x for c in chars)
        min_y = min(c.y + c.page_offset_y for c in chars)
        max_x = max(c.x + c.page_offset_x + c.width for c in chars)

        popup_width = 200
        popup_x = max(10, min_x + (max_x - min_x) / 2 - popup_width / 2)
        popup_y = max(10, min_y - 50)

        self._popup.left = popup_x
        self._popup.top = popup_y
        self._popup.visible = True

        if self._popup.page:
            self._popup.update()

    def _hide_popup(self):
        """Hide popup."""
        if self._popup:
            self._popup.visible = False
            if self._popup.page:
                self._popup.update()

    # Overlays

    def _update_selection_overlay(self):
        """Update selection highlight."""
        if not self._selection_overlay or not self._selection_overlay.content:
            return

        rects = self._selection.get_highlight_rects()
        controls = [
            ft.Container(
                left=r[0],
                top=r[1],
                width=r[2] - r[0],
                height=r[3] - r[1],
                bgcolor=ft.Colors.with_opacity(0.3, self._selection_color),
            )
            for r in rects
        ]

        self._selection_overlay.content.controls = controls
        if self._wrapper and self._wrapper.page:
            self._selection_overlay.update()

    def _update_search_overlay(self):
        """Update search result highlights."""
        if not self._search_overlay or not self._search_overlay.content:
            return

        controls = []

        # Calculate page offsets for each page (needed for continuous mode)
        page_offsets: Dict[int, Tuple[float, float]] = {}
        if self._source:
            if self._mode == ViewerMode.CONTINUOUS:
                y_offset = 0.0
                for i in range(self._source.page_count):
                    page_offsets[i] = (0, y_offset)
                    page = self._source.get_page(i)
                    y_offset += page.height * self._scale + self._page_gap
            elif self._mode == ViewerMode.DOUBLE_PAGE:
                page_offsets[self._current_page] = (0, 0)
                if self._current_page + 1 < self._source.page_count:
                    left_page = self._source.get_page(self._current_page)
                    x_offset = left_page.width * self._scale + self._page_gap
                    page_offsets[self._current_page + 1] = (x_offset, 0)
            else:
                page_offsets[self._current_page] = (0, 0)

        # Create highlight rectangles for each search result
        for i, result in enumerate(self._search_results):
            # In single/double page mode, only show results on visible pages
            if self._mode == ViewerMode.SINGLE_PAGE:
                if result.page_index != self._current_page:
                    continue
            elif self._mode == ViewerMode.DOUBLE_PAGE:
                if result.page_index not in (
                    self._current_page,
                    self._current_page + 1,
                ):
                    continue

            offset_x, offset_y = page_offsets.get(result.page_index, (0, 0))
            x0, y0, x1, y1 = result.rect

            # Scale the rect
            sx0 = x0 * self._scale + offset_x
            sy0 = y0 * self._scale + offset_y
            sx1 = x1 * self._scale + offset_x
            sy1 = y1 * self._scale + offset_y

            # Current result gets a different highlight color
            is_current = i == self._search_index
            if is_current:
                bgcolor = ft.Colors.with_opacity(0.5, "#ff9500")  # Orange for current
                border = ft.border.all(2, "#ff9500")
            else:
                bgcolor = ft.Colors.with_opacity(0.3, "#ffff00")  # Yellow for others
                border = None

            controls.append(
                ft.Container(
                    left=sx0,
                    top=sy0,
                    width=sx1 - sx0,
                    height=sy1 - sy0,
                    bgcolor=bgcolor,
                    border=border,
                    border_radius=2,
                )
            )

        self._search_overlay.content.controls = controls
        if self._wrapper and self._wrapper.page:
            self._search_overlay.update()

    def _catmull_rom_to_bezier(
        self, points: List[Tuple[float, float]], tension: float = 0.5
    ) -> List:
        """Convert points to smooth path using Catmull-Rom splines."""
        if len(points) < 2:
            return []

        if len(points) == 2:
            return [
                cv.Path.MoveTo(points[0][0], points[0][1]),
                cv.Path.LineTo(points[1][0], points[1][1]),
            ]

        # Duplicate first and last points for the spline
        pts = [points[0]] + list(points) + [points[-1]]

        elements = [cv.Path.MoveTo(points[0][0], points[0][1])]

        # Convert each Catmull-Rom segment to cubic bezier
        for i in range(1, len(pts) - 2):
            p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]

            cp1x = p1[0] + (p2[0] - p0[0]) * tension / 3
            cp1y = p1[1] + (p2[1] - p0[1]) * tension / 3
            cp2x = p2[0] - (p3[0] - p1[0]) * tension / 3
            cp2y = p2[1] - (p3[1] - p1[1]) * tension / 3

            elements.append(cv.Path.CubicTo(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1]))

        return elements

    def _update_ink_overlay(self):
        """Update ink drawing overlay."""
        if not self._ink_overlay or not self._ink_overlay.content:
            return

        path = self._drawing.current_path
        if not path or len(path) < 2:
            self._ink_overlay.content.shapes = []
            if self._wrapper and self._wrapper.page and self._ink_overlay.page:
                self._ink_overlay.update()
            return

        hex_color = self._drawing.get_overlay_color_hex()
        elements = self._catmull_rom_to_bezier(path)

        shapes = [
            cv.Path(
                elements,
                paint=ft.Paint(
                    stroke_width=self._drawing.width * self._scale,
                    color=hex_color,
                    style=ft.PaintingStyle.STROKE,
                    stroke_cap=ft.StrokeCap.ROUND,
                    stroke_join=ft.StrokeJoin.ROUND,
                ),
            )
        ]

        self._ink_overlay.content.shapes = shapes
        if self._wrapper and self._wrapper.page and self._ink_overlay.page:
            self._ink_overlay.update()

    def _save_ink_annotation(self):
        """Save current ink stroke."""
        path = self._drawing.end_stroke()

        if not self._source or not path or len(path) < 2:
            self._update_ink_overlay()
            return

        pdf_path = [(x / self._scale, y / self._scale) for x, y in path]

        page = self._source.get_page(self._current_page)
        page.add_ink([pdf_path], self._drawing.color, self._drawing.width)

        self._update_ink_overlay()
        self._update_content()

    def _update_shape_overlay(self):
        """Update shape drawing overlay."""
        if not self._shape_overlay or not self._shape_overlay.content:
            return

        if not self._shape_drawing.is_drawing:
            self._shape_overlay.content.shapes = []
            if self._wrapper and self._wrapper.page and self._shape_overlay.page:
                self._shape_overlay.update()
            return

        stroke_hex = self._shape_drawing.get_stroke_color_hex()
        fill_hex = self._shape_drawing.get_fill_color_hex()
        stroke_width = self._shape_drawing.stroke_width * self._scale
        shape_type = self._shape_drawing.shape_type

        shapes = []

        if shape_type in (ShapeType.RECTANGLE, ShapeType.TEXT):
            rect = self._shape_drawing.get_current_rect()
            if rect:
                x0, y0, x1, y1 = rect
                width = x1 - x0
                height = y1 - y0
                # Draw fill first if present
                if fill_hex:
                    shapes.append(
                        cv.Rect(
                            x0,
                            y0,
                            width,
                            height,
                            paint=ft.Paint(
                                color=fill_hex,
                                style=ft.PaintingStyle.FILL,
                            ),
                        )
                    )
                # Draw stroke
                shapes.append(
                    cv.Rect(
                        x0,
                        y0,
                        width,
                        height,
                        paint=ft.Paint(
                            stroke_width=stroke_width,
                            color=stroke_hex,
                            style=ft.PaintingStyle.STROKE,
                        ),
                    )
                )

        elif shape_type == ShapeType.CIRCLE:
            rect = self._shape_drawing.get_current_rect()
            if rect:
                x0, y0, x1, y1 = rect
                # Draw fill first if present
                if fill_hex:
                    shapes.append(
                        cv.Oval(
                            x0,
                            y0,
                            x1,
                            y1,
                            paint=ft.Paint(
                                color=fill_hex,
                                style=ft.PaintingStyle.FILL,
                            ),
                        )
                    )
                # Draw stroke
                shapes.append(
                    cv.Oval(
                        x0,
                        y0,
                        x1,
                        y1,
                        paint=ft.Paint(
                            stroke_width=stroke_width,
                            color=stroke_hex,
                            style=ft.PaintingStyle.STROKE,
                        ),
                    )
                )

        elif shape_type in (ShapeType.LINE, ShapeType.ARROW):
            line = self._shape_drawing.get_current_line()
            if line:
                x1, y1, x2, y2 = line
                shapes.append(
                    cv.Line(
                        x1,
                        y1,
                        x2,
                        y2,
                        paint=ft.Paint(
                            stroke_width=stroke_width,
                            color=stroke_hex,
                            style=ft.PaintingStyle.STROKE,
                            stroke_cap=ft.StrokeCap.ROUND,
                        ),
                    )
                )
                # Draw arrow head for arrow type
                if shape_type == ShapeType.ARROW:
                    arrow_shapes = self._create_arrow_head(
                        x1, y1, x2, y2, stroke_hex, stroke_width
                    )
                    shapes.extend(arrow_shapes)

        self._shape_overlay.content.shapes = shapes
        if self._wrapper and self._wrapper.page and self._shape_overlay.page:
            self._shape_overlay.update()

    def _create_arrow_head(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        color: str,
        stroke_width: float,
    ) -> list:
        """Create arrow head shapes at the end point."""
        import math

        # Calculate angle of the line
        dx = x2 - x1
        dy = y2 - y1
        angle = math.atan2(dy, dx)

        # Arrow head size proportional to stroke width
        arrow_length = max(12, stroke_width * 4)
        arrow_angle = math.pi / 6  # 30 degrees

        # Calculate arrow head points
        ax1 = x2 - arrow_length * math.cos(angle - arrow_angle)
        ay1 = y2 - arrow_length * math.sin(angle - arrow_angle)
        ax2 = x2 - arrow_length * math.cos(angle + arrow_angle)
        ay2 = y2 - arrow_length * math.sin(angle + arrow_angle)

        # Create filled triangle for arrow head
        path_elements = [
            cv.Path.MoveTo(x2, y2),
            cv.Path.LineTo(ax1, ay1),
            cv.Path.LineTo(ax2, ay2),
            cv.Path.Close(),
        ]

        return [
            cv.Path(
                path_elements,
                paint=ft.Paint(
                    color=color,
                    style=ft.PaintingStyle.FILL,
                ),
            )
        ]

    def _save_shape_annotation(self):
        """Save current shape as annotation."""
        shape_data = self._shape_drawing.end_shape()

        if not self._source or not shape_data:
            self._update_shape_overlay()
            return

        shape_type, x1, y1, x2, y2 = shape_data

        # Convert from screen coordinates to PDF coordinates
        pdf_x1 = x1 / self._scale
        pdf_y1 = y1 / self._scale
        pdf_x2 = x2 / self._scale
        pdf_y2 = y2 / self._scale

        page = self._source.get_page(self._current_page)
        stroke_color = self._shape_drawing.stroke_color
        fill_color = self._shape_drawing.fill_color
        stroke_width = self._shape_drawing.stroke_width

        if shape_type == ShapeType.RECTANGLE:
            # Normalize rect
            rx0 = min(pdf_x1, pdf_x2)
            ry0 = min(pdf_y1, pdf_y2)
            rx1 = max(pdf_x1, pdf_x2)
            ry1 = max(pdf_y1, pdf_y2)
            page.add_rect(
                (rx0, ry0, rx1, ry1),
                stroke_color=stroke_color,
                fill_color=fill_color,
                width=stroke_width,
            )

        elif shape_type == ShapeType.CIRCLE:
            # Normalize rect for ellipse bounds
            rx0 = min(pdf_x1, pdf_x2)
            ry0 = min(pdf_y1, pdf_y2)
            rx1 = max(pdf_x1, pdf_x2)
            ry1 = max(pdf_y1, pdf_y2)
            page.add_circle(
                (rx0, ry0, rx1, ry1),
                stroke_color=stroke_color,
                fill_color=fill_color,
                width=stroke_width,
            )

        elif shape_type == ShapeType.LINE:
            page.add_line(
                (pdf_x1, pdf_y1),
                (pdf_x2, pdf_y2),
                color=stroke_color,
                width=stroke_width,
            )

        elif shape_type == ShapeType.ARROW:
            page.add_arrow(
                (pdf_x1, pdf_y1),
                (pdf_x2, pdf_y2),
                color=stroke_color,
                width=stroke_width,
            )

        elif shape_type == ShapeType.TEXT:
            # Normalize rect
            rx0 = min(pdf_x1, pdf_x2)
            ry0 = min(pdf_y1, pdf_y2)
            rx1 = max(pdf_x1, pdf_x2)
            ry1 = max(pdf_y1, pdf_y2)
            # Call the callback instead of adding annotation directly
            if self._on_text_box_drawn:
                self._on_text_box_drawn((rx0, ry0, rx1, ry1))
            self._update_shape_overlay()
            return  # Don't update content yet - callback will handle it

        self._update_shape_overlay()
        self._update_content()

    # Annotations

    def _add_annotation(self, annotation_type: str, color: Color):
        """Add annotation to selected text."""
        if not self._source or not self._selection.selected_chars:
            return

        rects_by_page = self._selection.get_annotation_rects(self._scale)

        for page_index, rects in rects_by_page.items():
            page = self._source.get_page(page_index)

            if annotation_type == "highlight":
                page.add_highlight(rects, color)
            elif annotation_type == "underline":
                page.add_underline(rects, color)
            elif annotation_type == "strikethrough":
                page.add_strikethrough(rects, color)
            elif annotation_type == "squiggly":
                page.add_squiggly(rects, color)

        self.clear_selection()
        self._update_content()

    # Links

    def _update_link_overlay(self):
        """Update link overlay with clickable areas."""
        if not self._link_overlay or not self._link_overlay.content:
            return

        controls = []
        for link_info, scaled_rect, offset_x, offset_y in self._links:
            x0, y0, x1, y1 = scaled_rect
            width = x1 - x0
            height = y1 - y0

            # Create a transparent clickable area with hover effect
            controls.append(
                ft.Container(
                    left=x0 + offset_x,
                    top=y0 + offset_y,
                    width=width,
                    height=height,
                    bgcolor=ft.Colors.TRANSPARENT,
                    border=ft.border.all(0, ft.Colors.TRANSPARENT),
                    # Visual hint on hover
                    on_hover=lambda e, r=(x0, y0, x1, y1): self._on_link_hover(e, r),
                )
            )

        self._link_overlay.content.controls = controls

    def _on_link_hover(self, e, rect):
        """Handle link hover for visual feedback."""
        if e.data == "true":
            e.control.bgcolor = ft.Colors.with_opacity(0.1, "#3390ff")
        else:
            e.control.bgcolor = ft.Colors.TRANSPARENT
        if e.control.page:
            e.control.update()

    def _find_link_at(self, x: float, y: float) -> Optional[LinkInfo]:
        """Find a link at the given coordinates."""
        for link_info, scaled_rect, offset_x, offset_y in self._links:
            x0, y0, x1, y1 = scaled_rect
            # Adjust for page offset
            lx0 = x0 + offset_x
            ly0 = y0 + offset_y
            lx1 = x1 + offset_x
            ly1 = y1 + offset_y

            if lx0 <= x <= lx1 and ly0 <= y <= ly1:
                return link_info

        return None

    def _handle_link_click(self, link: LinkInfo):
        """Handle a link click."""
        # Call custom handler first if provided
        if self._on_link_click:
            handled = self._on_link_click(link)
            if handled:
                return

        # Default handling
        if link.kind == "goto" and link.page is not None:
            # Internal page navigation
            if link.file:
                # Link to another PDF file - can't handle internally
                pass
            else:
                self.goto(link.page)

        elif link.kind == "uri" and link.uri:
            # External URL - open in browser
            try:
                webbrowser.open(link.uri)
            except Exception:
                pass

        elif link.kind == "named" and link.name:
            # Named destination - resolve and navigate
            self.goto_destination(link.name)

        elif link.kind == "launch" and link.file:
            # Launch external file - security risk, don't handle by default
            pass
