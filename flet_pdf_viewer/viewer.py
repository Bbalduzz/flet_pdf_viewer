"""
PDF Viewer - Main viewer component.

Composes backends, rendering, and interactions into a single component.
"""

from __future__ import annotations

import os
from typing import Callable, List, Optional, Tuple

import flet as ft
import flet.canvas as cv

import webbrowser

from .backends.base import DocumentBackend
from .interactions.drawing import DrawingHandler
from .interactions.selection import SelectionHandler
from .rendering.renderer import PageRenderer
from .types import Color, LinkInfo, SelectableChar, TocItem, ViewerMode


class PdfViewer:
    """
    PDF Viewer component.

    Usage:
        from flet_pdf_viewer import PdfDocument, PdfViewer, ViewerMode

        document = PdfDocument("/path/to/file.pdf")
        viewer = PdfViewer(document)
        page.add(viewer.control)
    """

    def __init__(
        self,
        source: Optional[DocumentBackend] = None,
        current_page: int = 0,
        scale: float = 1.0,
        mode: ViewerMode = ViewerMode.SINGLE_PAGE,
        page_gap: int = 16,
        bgcolor: str = "#ffffff",
        selection_color: str = "#3390ff",
        popup_builder: Optional[Callable[["PdfViewer"], ft.Control]] = None,
        on_page_change: Optional[Callable[[int], None]] = None,
        on_selection_change: Optional[Callable[[str], None]] = None,
        on_link_click: Optional[Callable[[LinkInfo], bool]] = None,
    ):
        self._source = source
        self._current_page = current_page
        self._scale = scale
        self._mode = mode
        self._page_gap = page_gap
        self._bgcolor = bgcolor
        self._selection_color = selection_color
        self._popup_builder = popup_builder
        self._on_page_change = on_page_change
        self._on_link_click = on_link_click

        # Components
        self._renderer = PageRenderer(scale)
        self._selection = SelectionHandler(on_selection_change)
        self._drawing = DrawingHandler()

        # UI state
        self._wrapper: Optional[ft.Container] = None
        self._content: Optional[ft.Control] = None
        self._content_with_overlay: Optional[ft.Stack] = None
        self._selection_overlay: Optional[ft.Container] = None
        self._ink_overlay: Optional[ft.Container] = None
        self._link_overlay: Optional[ft.Container] = None
        self._popup: Optional[ft.Container] = None

        # Links storage: list of (LinkInfo, scaled_rect, page_offset_x, page_offset_y)
        self._links: List[Tuple[LinkInfo, Tuple[float, float, float, float], float, float]] = []

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
        """Whether drawing mode is active."""
        return self._drawing.enabled

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

    # Drawing

    def enable_drawing(self, color: Color = (0.0, 0.0, 0.0), width: float = 2.0):
        """Enable ink drawing mode."""
        self._drawing.enable(color, width)

    def disable_drawing(self):
        """Disable ink drawing mode."""
        self._drawing.disable()
        self._update_ink_overlay()

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

        self._link_overlay = ft.Container(
            content=ft.Stack(controls=[]),
            left=0,
            top=0,
        )

        self._popup = self._create_popup()

        self._content_with_overlay = ft.Stack(
            controls=[
                self._content,
                self._link_overlay,
                self._selection_overlay,
                self._ink_overlay,
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

            for i in range(self._source.page_count):
                container, chars, links = self._create_page_container(i, 0, y_offset)
                page_containers.append(container)
                selectable_chars.extend(chars)
                self._links.extend(links)

                page = self._source.get_page(i)
                y_offset += page.height * self._scale + self._page_gap

            content = ft.Column(
                controls=page_containers,
                spacing=self._page_gap,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )

        elif self._mode == ViewerMode.DOUBLE_PAGE:
            left_index = self._current_page
            right_index = self._current_page + 1

            left_container, left_chars, left_links = self._create_page_container(left_index)
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

    def _create_page_container(
        self, page_index: int, offset_x: float = 0, offset_y: float = 0
    ) -> Tuple[ft.Container, List[SelectableChar], List[Tuple[LinkInfo, Tuple[float, float, float, float], float, float]]]:
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
                        content=ft.Image(src=img_path, width=w, height=h, fit=ft.ImageFit.FILL),
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
            border_radius=2,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=20,
                color=ft.Colors.with_opacity(0.3, "#000000"),
            ),
        )

        chars = self._renderer.build_selectable_chars(page, page_index, offset_x, offset_y)

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
                self._selection_overlay,
                self._ink_overlay,
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

        if not self._drawing.enabled:
            self.clear_selection()

    def _on_pan_start(self, e: ft.DragStartEvent):
        if self._drawing.enabled:
            self._drawing.start_stroke(e.local_x, e.local_y)
            self._update_ink_overlay()
        else:
            self._selection.start_selection(e.local_x, e.local_y)
            self._hide_popup()

    def _on_pan_update(self, e: ft.DragUpdateEvent):
        if self._drawing.enabled:
            self._drawing.add_point(e.local_x, e.local_y)
            self._update_ink_overlay()
        else:
            self._selection.update_selection(e.local_x, e.local_y)
            self._update_selection_overlay()

    def _on_pan_end(self, e: ft.DragEndEvent):
        if self._drawing.enabled:
            self._save_ink_annotation()
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
                e.control.bgcolor = "rgba(255,255,255,0.1)" if e.data == "true" else None
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
                action_btn(ft.Icons.EDIT, "Highlight", lambda e: self.highlight_selection(), "#facc15"),
                action_btn(ft.Icons.FORMAT_UNDERLINED, "Underline", lambda e: self.underline_selection(), "#3b82f6"),
                action_btn(ft.Icons.FORMAT_STRIKETHROUGH, "Strikethrough", lambda e: self.strikethrough_selection(), "#ef4444"),
                ft.Container(width=1, height=24, bgcolor="rgba(255,255,255,0.15)"),
                action_btn(ft.Icons.COPY_ROUNDED, "Copy", lambda e: self.copy_selection(), "#a1a1a1"),
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
        shapes = []

        for i in range(len(path) - 1):
            x1, y1 = path[i]
            x2, y2 = path[i + 1]
            shapes.append(
                cv.Line(
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    paint=ft.Paint(
                        stroke_width=self._drawing.width * self._scale,
                        color=hex_color,
                        stroke_cap=ft.StrokeCap.ROUND,
                    ),
                )
            )

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
            # Named destination - try to resolve
            # Most PDFs use page numbers directly, so this is less common
            pass

        elif link.kind == "launch" and link.file:
            # Launch external file - security risk, don't handle by default
            pass
