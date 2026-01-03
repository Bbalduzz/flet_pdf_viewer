"""
PDF Viewer - Minimal, elegant design with text selection.
"""

from pathlib import Path

import flet as ft

from flet_pdf_viewer import (
    PdfDocument,
    PdfViewer,
    TocItem,
    ViewerMode,
    ViewerStyle,
    ZoomConfig,
)

COLORS = {
    "bg": "#000000",
    "surface": "#0a0a0a",
    "surface_hover": "#171717",
    "border": "#262626",
    "text": "#ededed",
    "text_secondary": "#a1a1a1",
    "text_muted": "#525252",
    "accent": "#ffffff",
    "selection": "#3390ff",
}

HIGHLIGHT_COLORS = [
    ("#c4b5fd", (0.77, 0.71, 0.99)),  # Purple
    ("#fef3c7", (1.0, 0.95, 0.78)),  # Cream
    ("#bfdbfe", (0.75, 0.86, 1.0)),  # Light blue
    ("#bbf7d0", (0.73, 0.97, 0.82)),  # Light green
    ("#fecaca", (1.0, 0.79, 0.79)),  # Pink
]

# PDF_PATH = "TEST - Supporting Student Hall on Arches.pdf"
PDF_PATH = Path("demo_files") / "multicolumn.pdf"


def main(page: ft.Page):
    page.title = "PDF Viewer"
    page.padding = 0
    page.bgcolor = COLORS["bg"]
    page.theme_mode = ft.ThemeMode.DARK

    # Selected highlight color
    selected_color = [0]

    # ToC state
    toc_visible = [False]
    expanded_items = set()  # Track which items are expanded
    selected_toc_item = [None]  # Currently selected ToC item

    def build_popup(viewer):
        """Build toolbar-style popup like Notion/Linear."""

        text_color = "#d4d4d4"
        text_muted = "#737373"
        bg_color = "#262626"
        bg_hover = "#404040"
        border_color = "#404040"

        def icon_btn(icon, on_click, tooltip=None, active=False):
            def on_hover(e):
                e.control.bgcolor = (
                    bg_hover
                    if e.data == "true"
                    else ("transparent" if not active else bg_hover)
                )
                if e.control.page:
                    e.control.update()

            return ft.Container(
                content=ft.Icon(
                    icon, size=18, color=text_color if active else text_muted
                ),
                width=32,
                height=32,
                border_radius=6,
                alignment=ft.alignment.center,
                bgcolor=bg_hover if active else "transparent",
                on_click=on_click,
                on_hover=on_hover,
                tooltip=tooltip,
            )

        def text_btn(text, on_click, has_dropdown=False):
            def on_hover(e):
                e.control.bgcolor = bg_hover if e.data == "true" else "transparent"
                if e.control.page:
                    e.control.update()

            content = ft.Row(
                [
                    ft.Text(
                        text, size=13, color=text_muted, weight=ft.FontWeight.W_500
                    ),
                    ft.Icon(ft.Icons.KEYBOARD_ARROW_DOWN, size=16, color=text_muted)
                    if has_dropdown
                    else ft.Container(),
                ],
                spacing=2,
            )

            return ft.Container(
                content=content,
                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                border_radius=6,
                on_click=on_click,
                on_hover=on_hover,
            )

        def divider():
            return ft.Container(
                width=1,
                height=24,
                bgcolor=border_color,
                margin=ft.margin.symmetric(horizontal=4),
            )

        def color_dot(hex_color, rgb_color, has_dropdown=False):
            def on_click(e):
                viewer.highlight_selection(rgb_color)

            def on_hover(e):
                e.control.bgcolor = bg_hover if e.data == "true" else "transparent"
                if e.control.page:
                    e.control.update()

            return ft.Container(
                content=ft.Row(
                    [
                        ft.Container(
                            width=18,
                            height=18,
                            border_radius=9,
                            bgcolor=hex_color,
                        ),
                        ft.Icon(ft.Icons.KEYBOARD_ARROW_DOWN, size=16, color=text_muted)
                        if has_dropdown
                        else ft.Container(),
                    ],
                    spacing=4,
                ),
                padding=ft.padding.symmetric(horizontal=8, vertical=6),
                border_radius=6,
                on_click=on_click,
                on_hover=on_hover,
            )

        def on_bold(e):
            print(f"Bold: {viewer.selected_text[:30]}...")

        def on_italic(e):
            print(f"Italic: {viewer.selected_text[:30]}...")

        def on_underline(e):
            viewer.underline_selection()

        def on_strikethrough(e):
            viewer.strikethrough_selection()

        def on_squiggly(e):
            viewer.squiggly_selection()

        def on_link(e):
            print(f"Link: {viewer.selected_text[:30]}...")
            viewer.clear_selection()

        def on_note(e):
            # Show dialog to enter note text
            def close_dialog(e):
                dialog.open = False
                page.update()

            def add_note(e):
                note_text = note_field.value
                if note_text:
                    viewer.add_note_at_selection(note_text)
                dialog.open = False
                page.update()

            note_field = ft.TextField(
                hint_text="Enter your note...",
                multiline=True,
                min_lines=3,
                max_lines=5,
                autofocus=True,
                border_color="#404040",
                focused_border_color="#666666",
                text_style=ft.TextStyle(color="#e0e0e0"),
            )

            dialog = ft.AlertDialog(
                title=ft.Text("Add Note", color="#e0e0e0"),
                bgcolor="#262626",
                content=ft.Container(
                    content=note_field,
                    width=300,
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=close_dialog),
                    ft.TextButton("Add", on_click=add_note),
                ],
            )
            page.overlay.append(dialog)
            dialog.open = True
            page.update()

        def on_copy(e):
            viewer.copy_selection()

        return ft.Container(
            content=ft.Row(
                [
                    # Formatting buttons
                    icon_btn(ft.Icons.FORMAT_UNDERLINED, on_underline, "Underline"),
                    icon_btn(
                        ft.Icons.FORMAT_STRIKETHROUGH, on_strikethrough, "Strikethrough"
                    ),
                    icon_btn(ft.Icons.WAVES, on_squiggly, "Squiggly"),
                    divider(),
                    # Color picker (highlight)
                    color_dot("#fef3c7", (1.0, 0.95, 0.78), has_dropdown=True),
                    divider(),
                    # Note button
                    icon_btn(ft.Icons.NOTE_ADD_OUTLINED, on_note, "Add Note"),
                    divider(),
                    # Copy button
                    icon_btn(ft.Icons.COPY, on_copy, "Copy"),
                ],
                spacing=0,
            ),
            bgcolor=bg_color,
            border=ft.border.all(1, border_color),
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=8, vertical=6),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=24,
                color=ft.Colors.with_opacity(0.4, "#000000"),
                offset=ft.Offset(0, 8),
            ),
        )

    # Load document
    document = PdfDocument(PDF_PATH)
    print(document.fonts)
    # Register embedded PDF fonts
    page.fonts = document.fonts

    viewer = PdfViewer(
        document,
        mode=ViewerMode.SINGLE_PAGE,
        style=ViewerStyle(selection_color=COLORS["selection"]),
        zoom=ZoomConfig(initial=1.0),
        popup_builder=build_popup,
    )

    # State
    current_mode = ViewerMode.SINGLE_PAGE
    drawing_active = [False]  # Use list to allow mutation in nested functions
    search_visible = [False]  # Search bar visibility
    shapes_menu_visible = [False]  # Shapes dropdown visibility
    edit_menu_visible = [False]  # Page edit toolbar visibility

    # Text annotation system - annotations that can be selected, moved, and edited
    # Each annotation: {id, x, y, text, selected, page_index, editing}
    text_annotations = []  # List of text annotation dicts
    selected_annotation_id = [None]  # Currently selected annotation ID
    annotation_counter = [0]  # For generating unique IDs
    content_stack_ref = ft.Ref[ft.Stack]()

    def create_annotation_id():
        """Generate a unique annotation ID."""
        annotation_counter[0] += 1
        return f"text_ann_{annotation_counter[0]}"

    def add_text_annotation():
        """Add a new text annotation at default position."""
        ann_id = create_annotation_id()
        annotation = {
            "id": ann_id,
            "x": 100.0,
            "y": 100.0,
            "text": "Text",
            "page_index": viewer.current_page,
            "editing": True,  # Start in editing mode
        }
        text_annotations.append(annotation)
        selected_annotation_id[0] = ann_id
        rebuild_annotations_overlay()

    def get_annotation_by_id(ann_id):
        """Get annotation by ID."""
        return next((a for a in text_annotations if a["id"] == ann_id), None)

    def select_annotation(ann_id):
        """Select an annotation by ID."""
        selected_annotation_id[0] = ann_id
        # Set all annotations to not editing
        for ann in text_annotations:
            ann["editing"] = False
        rebuild_annotations_overlay()

    def deselect_all_annotations():
        """Deselect all annotations."""
        selected_annotation_id[0] = None
        for ann in text_annotations:
            ann["editing"] = False
        rebuild_annotations_overlay()

    def delete_annotation(ann_id):
        """Delete an annotation by ID."""
        text_annotations[:] = [a for a in text_annotations if a["id"] != ann_id]
        if selected_annotation_id[0] == ann_id:
            selected_annotation_id[0] = None
        rebuild_annotations_overlay()

    def confirm_annotation(ann_id):
        """Save an annotation to the PDF and remove from pending list."""
        ann = get_annotation_by_id(ann_id)
        if not ann or not ann["text"].strip():
            delete_annotation(ann_id)
            return

        # Convert screen coordinates to PDF coordinates
        scale = viewer.scale
        pdf_x = ann["x"] / scale
        pdf_y = ann["y"] / scale

        # Estimate size based on text length
        text_width = max(len(ann["text"]) * 8, 50)
        pdf_width = text_width / scale
        pdf_height = 20 / scale

        document.add_freetext(
            page_index=ann["page_index"],
            rect=(pdf_x, pdf_y, pdf_x + pdf_width, pdf_y + pdf_height),
            text=ann["text"],
            font_size=14,
            text_color=(0.0, 0.0, 0.0),
            fill_color=None,  # Transparent background
            border_width=0,
        )
        viewer.source = document._get_backend()

        # Remove from pending annotations
        delete_annotation(ann_id)

        # Deactivate text mode
        active_shape_type[0] = None
        rebuild_toolbar()
        try:
            rebuild_shapes_toolbar()
        except NameError:
            pass

    def build_annotation_widget(ann):
        """Build a widget for a single text annotation."""
        is_selected = ann["id"] == selected_annotation_id[0]
        is_editing = ann.get("editing", False)
        ann_id = ann["id"]

        def on_drag(e: ft.DragUpdateEvent):
            """Handle dragging the annotation."""
            if is_selected and not is_editing:
                ann["x"] += e.delta_x
                ann["y"] += e.delta_y
                rebuild_annotations_overlay()

        def on_click(e):
            """Select this annotation on click."""
            select_annotation(ann_id)

        def on_double_tap(e):
            """Enter edit mode on double-click."""
            ann["editing"] = True
            rebuild_annotations_overlay()

        def on_text_change(e):
            """Update text as user types."""
            ann["text"] = e.control.value if e.control.value else ""

        def on_text_submit(e):
            """Exit edit mode on Enter - confirm the annotation."""
            ann["editing"] = False
            if ann["text"].strip():
                confirm_annotation(ann_id)
            else:
                delete_annotation(ann_id)

        def on_text_blur(e):
            """Exit edit mode when losing focus."""
            ann["editing"] = False
            rebuild_annotations_overlay()

        def on_confirm(e):
            """Confirm and save this annotation."""
            confirm_annotation(ann_id)

        def on_delete(e):
            """Delete this annotation."""
            delete_annotation(ann_id)

        handle_size = 10

        if is_selected:
            if is_editing:
                # Editing mode - show text field with selection box
                text_field = ft.TextField(
                    value=ann["text"],
                    border=ft.InputBorder.NONE,
                    text_style=ft.TextStyle(
                        color="#000000", size=14, weight=ft.FontWeight.BOLD
                    ),
                    content_padding=ft.padding.symmetric(horizontal=4, vertical=2),
                    on_change=on_text_change,
                    on_submit=on_text_submit,
                    on_blur=on_text_blur,
                    autofocus=True,
                    width=150,
                )
                inner_content = text_field
            else:
                # Selected but not editing - show text
                inner_content = ft.Text(
                    ann["text"],
                    size=14,
                    color="#000000",
                    weight=ft.FontWeight.BOLD,
                )

            # Build selection box with corner handles
            inner = ft.Stack(
                [
                    # Main text container with border
                    ft.Container(
                        content=inner_content,
                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                        border=ft.border.all(1.5, "#1976d2"),
                    ),
                    # Corner handles (blue circles)
                    ft.Container(  # Top-left
                        width=handle_size,
                        height=handle_size,
                        bgcolor="#1976d2",
                        border_radius=handle_size // 2,
                        left=-handle_size // 2,
                        top=-handle_size // 2,
                    ),
                    ft.Container(  # Top-right
                        width=handle_size,
                        height=handle_size,
                        bgcolor="#1976d2",
                        border_radius=handle_size // 2,
                        right=-handle_size // 2,
                        top=-handle_size // 2,
                    ),
                    ft.Container(  # Bottom-left
                        width=handle_size,
                        height=handle_size,
                        bgcolor="#1976d2",
                        border_radius=handle_size // 2,
                        left=-handle_size // 2,
                        bottom=-handle_size // 2,
                    ),
                    ft.Container(  # Bottom-right
                        width=handle_size,
                        height=handle_size,
                        bgcolor="#1976d2",
                        border_radius=handle_size // 2,
                        right=-handle_size // 2,
                        bottom=-handle_size // 2,
                    ),
                    # Action buttons above the box
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Container(
                                    content=ft.Icon(
                                        ft.Icons.CHECK, size=14, color="#ffffff"
                                    ),
                                    width=24,
                                    height=24,
                                    bgcolor="#22c55e",
                                    border_radius=4,
                                    alignment=ft.alignment.center,
                                    on_click=on_confirm,
                                    tooltip="Confirm (Enter)",
                                ),
                                ft.Container(
                                    content=ft.Icon(
                                        ft.Icons.DELETE, size=14, color="#ffffff"
                                    ),
                                    width=24,
                                    height=24,
                                    bgcolor="#ef4444",
                                    border_radius=4,
                                    alignment=ft.alignment.center,
                                    on_click=on_delete,
                                    tooltip="Delete",
                                ),
                            ],
                            spacing=4,
                        ),
                        top=-32,
                        left=0,
                    ),
                ],
            )

            widget = ft.GestureDetector(
                content=inner,
                on_pan_update=on_drag,
                on_double_tap=on_double_tap,
            )
        else:
            # Not selected - just show plain text, clickable to select
            widget = ft.GestureDetector(
                content=ft.Container(
                    content=ft.Text(
                        ann["text"],
                        size=14,
                        color="#000000",
                        weight=ft.FontWeight.BOLD,
                    ),
                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                ),
                on_tap=on_click,
            )

        # Position the widget
        return ft.Container(
            content=widget,
            left=ann["x"],
            top=ann["y"],
        )

    def rebuild_annotations_overlay():
        """Rebuild the annotations overlay."""
        if not content_stack_ref.current:
            return

        # Keep only the first control (the main content column)
        controls = content_stack_ref.current.controls
        content_stack_ref.current.controls = controls[:1]

        # Add annotation widgets for current page
        current_page = viewer.current_page
        for ann in text_annotations:
            if ann["page_index"] == current_page:
                widget = build_annotation_widget(ann)
                content_stack_ref.current.controls.append(widget)

        content_stack_ref.current.update()

    active_shape_type = [None]  # Currently active shape drawing mode

    # Page indicator
    page_text = ft.Text(
        f"{viewer.current_page + 1}",
        size=13,
        color=COLORS["text"],
        weight=ft.FontWeight.W_500,
    )
    total_text = ft.Text(
        f"/ {document.page_count}",
        size=13,
        color=COLORS["text_muted"],
    )

    def update_page_info():
        page_text.value = f"{viewer.current_page + 1}"
        if page_text.page:
            page_text.update()

    # Navigation handlers
    def on_prev(e):
        if viewer.previous_page():
            update_page_info()

    def on_next(e):
        if viewer.next_page():
            update_page_info()

    def on_zoom_in(e):
        viewer.zoom_in()

    def on_zoom_out(e):
        viewer.zoom_out()

    # Search functionality
    search_field_ref = ft.Ref[ft.TextField]()
    search_results_text = ft.Text(
        "",
        size=12,
        color=COLORS["text_muted"],
    )

    def on_search_change(e):
        """Perform search as user types."""
        query = e.control.value
        if query:
            results = viewer.search(query)
            if results:
                search_results_text.value = (
                    f"{viewer.current_search_index + 1}/{len(results)}"
                )
            else:
                search_results_text.value = "0/0"
        else:
            viewer.clear_search()
            search_results_text.value = ""
        if search_results_text.page:
            search_results_text.update()

    def on_search_submit(e):
        """Go to next result on Enter."""
        if viewer.search_result_count > 0:
            viewer.search_next()
            search_results_text.value = (
                f"{viewer.current_search_index + 1}/{viewer.search_result_count}"
            )
            if search_results_text.page:
                search_results_text.update()
            update_page_info()

    def on_search_next(e):
        """Go to next search result."""
        if viewer.search_result_count > 0:
            viewer.search_next()
            search_results_text.value = (
                f"{viewer.current_search_index + 1}/{viewer.search_result_count}"
            )
            if search_results_text.page:
                search_results_text.update()
            update_page_info()

    def on_search_prev(e):
        """Go to previous search result."""
        if viewer.search_result_count > 0:
            viewer.search_prev()
            search_results_text.value = (
                f"{viewer.current_search_index + 1}/{viewer.search_result_count}"
            )
            if search_results_text.page:
                search_results_text.update()
            update_page_info()

    def on_search_close(e):
        """Close search bar."""
        search_visible[0] = False
        viewer.clear_search()
        if search_field_ref.current:
            search_field_ref.current.value = ""
        search_results_text.value = ""
        rebuild_toolbar()

    def toggle_search(e):
        """Toggle search bar visibility."""
        search_visible[0] = not search_visible[0]
        rebuild_toolbar()
        # Focus the search field when opened
        if search_visible[0] and search_field_ref.current:
            search_field_ref.current.focus()

    # Shape annotation functions
    def enable_shape_mode(shape_type: str):
        """Enable interactive shape drawing mode."""
        # Disable ink drawing if active
        if drawing_active[0]:
            drawing_active[0] = False
            viewer.disable_drawing()

        # For all shapes (including text), enable interactive drawing mode
        # If clicking the same shape type, toggle it off
        if active_shape_type[0] == shape_type:
            active_shape_type[0] = None
            viewer.disable_shape_drawing()
        else:
            active_shape_type[0] = shape_type
            if shape_type == "rect":
                viewer.enable_rectangle_drawing(
                    stroke_color=(0.8, 0.2, 0.2),  # Red
                    fill_color=None,
                    stroke_width=2,
                )
            elif shape_type == "circle":
                viewer.enable_circle_drawing(
                    stroke_color=(0.2, 0.2, 0.8),  # Blue
                    fill_color=None,
                    stroke_width=2,
                )
            elif shape_type == "line":
                viewer.enable_line_drawing(
                    color=(0.0, 0.0, 0.0),
                    width=2,
                )
            elif shape_type == "arrow":
                viewer.enable_arrow_drawing(
                    color=(0.0, 0.5, 0.0),  # Green
                    width=2,
                )
            elif shape_type == "text":
                # Add a new text annotation
                add_text_annotation()

        rebuild_toolbar()
        rebuild_shapes_toolbar()

    def toggle_shapes_menu(e):
        """Toggle shapes toolbar visibility."""
        shapes_menu_visible[0] = not shapes_menu_visible[0]
        if shapes_menu_visible[0]:
            edit_menu_visible[0] = False  # Close edit menu
        rebuild_toolbar()
        # Also rebuild shapes toolbar if it exists
        try:
            rebuild_shapes_toolbar()
            rebuild_edit_toolbar()
        except NameError:
            pass

    def toggle_edit_menu(e):
        """Toggle page edit toolbar visibility."""
        edit_menu_visible[0] = not edit_menu_visible[0]
        if edit_menu_visible[0]:
            shapes_menu_visible[0] = False  # Close shapes menu
        rebuild_toolbar()
        try:
            rebuild_shapes_toolbar()
            rebuild_edit_toolbar()
        except NameError:
            pass

    # Page manipulation handlers
    def rotate_page_left(e):
        """Rotate current page 90° counter-clockwise."""
        document.rotate_page_by(viewer.current_page, -90)
        viewer._update_content()
        page.update()

    def rotate_page_right(e):
        """Rotate current page 90° clockwise."""
        document.rotate_page_by(viewer.current_page, 90)
        viewer._update_content()
        page.update()

    def delete_current_page(e):
        """Delete the current page."""
        if document.page_count <= 1:
            return  # Don't delete the last page
        current = viewer.current_page
        document.delete_page(current)
        # Navigate to previous page if we deleted the last page
        if current >= document.page_count:
            viewer.goto(document.page_count - 1)
        viewer._update_content()
        rebuild_toolbar()
        page.update()

    def add_blank_page_after(e):
        """Add a blank page after current page."""
        current = viewer.current_page
        w, h = document.get_page_size(current)
        document.add_blank_page(width=w, height=h, index=current + 1)
        viewer.goto(current + 1)
        viewer._update_content()
        rebuild_toolbar()
        page.update()

    def duplicate_current_page(e):
        """Duplicate the current page."""
        current = viewer.current_page
        new_idx = document.copy_page(current)
        viewer.goto(new_idx)
        viewer._update_content()
        rebuild_toolbar()
        page.update()

    def move_page_up(e):
        """Move current page one position earlier."""
        current = viewer.current_page
        if current > 0:
            document.move_page(current, current - 1)
            viewer.goto(current - 1)
            viewer._update_content()
            page.update()

    def move_page_down(e):
        """Move current page one position later."""
        current = viewer.current_page
        if current < document.page_count - 1:
            document.move_page(current, current + 2)
            viewer.goto(current + 1)
            viewer._update_content()
            page.update()

    save_icon_ref = ft.Ref[ft.Icon]()

    def on_save(e):
        document.save()
        # Brief visual feedback - change icon to checkmark
        if save_icon_ref.current:
            save_icon_ref.current.name = ft.Icons.CHECK
            save_icon_ref.current.color = "#4ade80"  # Green
            save_icon_ref.current.update()
            # Reset after delay
            import threading

            def reset_icon():
                import time

                time.sleep(1)
                if save_icon_ref.current and save_icon_ref.current.page:
                    save_icon_ref.current.name = ft.Icons.SAVE_OUTLINED
                    save_icon_ref.current.color = COLORS["text_secondary"]
                    save_icon_ref.current.update()

            threading.Thread(target=reset_icon, daemon=True).start()

    def on_toggle_draw(e):
        drawing_active[0] = not drawing_active[0]
        if drawing_active[0]:
            # Disable shape drawing if active
            if active_shape_type[0]:
                active_shape_type[0] = None
                viewer.disable_shape_drawing()
            viewer.enable_drawing(color=(0.2, 0.2, 0.8), width=2.0)
        else:
            viewer.disable_drawing()
        rebuild_toolbar()
        try:
            rebuild_shapes_toolbar()
        except NameError:
            pass

    # Minimal icon button
    def icon_btn(icon, on_click, tooltip=None):
        def on_hover(e):
            e.control.bgcolor = COLORS["surface_hover"] if e.data == "true" else None
            if e.control.page:
                e.control.update()

        return ft.Container(
            content=ft.Icon(icon, size=16, color=COLORS["text_secondary"]),
            width=32,
            height=32,
            border_radius=6,
            alignment=ft.alignment.center,
            on_click=on_click,
            tooltip=tooltip,
            on_hover=on_hover,
        )

    # Mode button (highlighted when active)
    def mode_btn(icon, mode: ViewerMode, tooltip: str):
        is_active = current_mode == mode

        def on_click(e):
            nonlocal current_mode
            current_mode = mode
            viewer.mode = mode
            rebuild_toolbar()

        def on_hover(e):
            e.control.bgcolor = (
                COLORS["surface_hover"] if e.data == "true" or is_active else None
            )
            if e.control.page:
                e.control.update()

        return ft.Container(
            content=ft.Icon(
                icon,
                size=16,
                color=COLORS["text"] if is_active else COLORS["text_muted"],
            ),
            width=32,
            height=32,
            border_radius=6,
            alignment=ft.alignment.center,
            bgcolor=COLORS["surface_hover"] if is_active else None,
            on_click=on_click,
            tooltip=tooltip,
            on_hover=on_hover,
        )

    # ToC sidebar reference
    toc_sidebar_ref = ft.Ref[ft.Container]()
    toc_content_ref = ft.Ref[ft.Column]()

    def build_toc_item(item: TocItem, level: int = 0) -> ft.Control:
        """Build a single ToC item with expand/collapse."""
        item_id = f"{item.title}_{item.page_index}_{level}"
        has_children = len(item.children) > 0
        is_expanded = item_id in expanded_items
        is_selected = selected_toc_item[0] == item_id

        def on_expand_click(e):
            e.control.data  # Prevent propagation
            if item_id in expanded_items:
                expanded_items.discard(item_id)
            else:
                expanded_items.add(item_id)
            rebuild_toc()

        def on_item_click(e):
            selected_toc_item[0] = item_id
            if item.page_index is not None:
                viewer.current_page = item.page_index
                update_page_info()
            rebuild_toc()

        def on_hover(e):
            if not is_selected:
                e.control.bgcolor = (
                    COLORS["surface_hover"] if e.data == "true" else "transparent"
                )
                if e.control.page:
                    e.control.update()

        # Truncate long titles
        display_title = item.title
        if len(display_title) > 40:
            display_title = display_title[:37] + "..."

        # Build the row content
        row_content = [
            # Expand/collapse icon or spacer
            ft.Container(
                content=ft.Icon(
                    ft.Icons.KEYBOARD_ARROW_DOWN
                    if is_expanded
                    else ft.Icons.KEYBOARD_ARROW_RIGHT,
                    size=16,
                    color=COLORS["text_muted"],
                )
                if has_children
                else None,
                width=20,
                height=20,
                on_click=on_expand_click if has_children else None,
            ),
            # Title
            ft.Text(
                display_title,
                size=13,
                color=COLORS["text"] if is_selected else COLORS["text_secondary"],
                weight=ft.FontWeight.W_500 if is_selected else ft.FontWeight.W_400,
                expand=True,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
        ]

        item_container = ft.Container(
            content=ft.Row(row_content, spacing=4),
            padding=ft.padding.only(left=level * 16 + 8, right=8, top=8, bottom=8),
            border_radius=6,
            bgcolor=COLORS["selection"] if is_selected else "transparent",
            on_click=on_item_click,
            on_hover=on_hover,
        )

        # Build children if expanded
        children_controls = []
        if has_children and is_expanded:
            for child in item.children:
                children_controls.append(build_toc_item(child, level + 1))

        return ft.Column(
            [item_container] + children_controls,
            spacing=0,
        )

    def build_toc_content() -> list:
        """Build the ToC content."""
        toc = document.toc
        if not toc:
            return [
                ft.Container(
                    content=ft.Text(
                        "No table of contents",
                        size=13,
                        color=COLORS["text_muted"],
                        italic=True,
                    ),
                    padding=16,
                )
            ]

        items = []
        for item in toc:
            items.append(build_toc_item(item))
        return items

    def rebuild_toc():
        """Rebuild the ToC content."""
        if toc_content_ref.current:
            toc_content_ref.current.controls = build_toc_content()
            toc_content_ref.current.update()

    def toggle_toc(e):
        """Toggle ToC sidebar visibility."""
        toc_visible[0] = not toc_visible[0]
        if toc_sidebar_ref.current:
            toc_sidebar_ref.current.visible = toc_visible[0]
            toc_sidebar_ref.current.update()
        rebuild_toolbar()

    # Toolbar reference for rebuilding
    toolbar_row = ft.Ref[ft.Row]()

    def rebuild_toolbar():
        toolbar_row.current.controls = build_toolbar_controls()
        toolbar_row.current.update()

    def build_toolbar_controls():
        controls = [
            # ToC toggle button (left side)
            ft.Container(
                content=ft.Container(
                    content=ft.Icon(
                        ft.Icons.TOC,
                        size=16,
                        color=COLORS["text"]
                        if toc_visible[0]
                        else COLORS["text_secondary"],
                    ),
                    width=32,
                    height=32,
                    border_radius=6,
                    alignment=ft.alignment.center,
                    on_click=toggle_toc,
                    bgcolor=COLORS["surface_hover"] if toc_visible[0] else None,
                ),
                bgcolor=COLORS["surface"],
                border=ft.border.all(
                    1,
                    COLORS["selection"] if toc_visible[0] else COLORS["border"],
                ),
                border_radius=8,
                padding=4,
                tooltip="Table of Contents",
            ),
        ]

        # Search bar (shown when search is active)
        if search_visible[0]:
            controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.SEARCH,
                                size=16,
                                color=COLORS["text_muted"],
                            ),
                            ft.TextField(
                                ref=search_field_ref,
                                hint_text="Search...",
                                hint_style=ft.TextStyle(
                                    color=COLORS["text_muted"], size=13
                                ),
                                text_style=ft.TextStyle(color=COLORS["text"], size=13),
                                border=ft.InputBorder.NONE,
                                height=32,
                                width=180,
                                content_padding=ft.padding.only(
                                    left=8, right=8, bottom=8
                                ),
                                on_change=on_search_change,
                                on_submit=on_search_submit,
                                autofocus=True,
                            ),
                            search_results_text,
                            ft.Container(
                                width=1,
                                height=20,
                                bgcolor=COLORS["border"],
                                margin=ft.margin.symmetric(horizontal=4),
                            ),
                            ft.Container(
                                content=ft.Icon(
                                    ft.Icons.KEYBOARD_ARROW_UP,
                                    size=16,
                                    color=COLORS["text_secondary"],
                                ),
                                width=28,
                                height=28,
                                border_radius=4,
                                alignment=ft.alignment.center,
                                on_click=on_search_prev,
                                tooltip="Previous (Shift+Enter)",
                            ),
                            ft.Container(
                                content=ft.Icon(
                                    ft.Icons.KEYBOARD_ARROW_DOWN,
                                    size=16,
                                    color=COLORS["text_secondary"],
                                ),
                                width=28,
                                height=28,
                                border_radius=4,
                                alignment=ft.alignment.center,
                                on_click=on_search_next,
                                tooltip="Next (Enter)",
                            ),
                            ft.Container(
                                content=ft.Icon(
                                    ft.Icons.CLOSE,
                                    size=16,
                                    color=COLORS["text_secondary"],
                                ),
                                width=28,
                                height=28,
                                border_radius=4,
                                alignment=ft.alignment.center,
                                on_click=on_search_close,
                                tooltip="Close (Esc)",
                            ),
                        ],
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    bgcolor=COLORS["surface"],
                    border=ft.border.all(1, COLORS["selection"]),
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                    margin=ft.margin.only(left=8),
                )
            )
        else:
            # Search button (when search is hidden)
            controls.append(
                ft.Container(
                    content=ft.Container(
                        content=ft.Icon(
                            ft.Icons.SEARCH,
                            size=16,
                            color=COLORS["text_secondary"],
                        ),
                        width=32,
                        height=32,
                        border_radius=6,
                        alignment=ft.alignment.center,
                        on_click=toggle_search,
                    ),
                    bgcolor=COLORS["surface"],
                    border=ft.border.all(1, COLORS["border"]),
                    border_radius=8,
                    padding=4,
                    margin=ft.margin.only(left=8),
                    tooltip="Search (Ctrl+F)",
                )
            )

        controls.append(ft.Container(expand=True))

        # Save button
        controls.append(
            ft.Container(
                content=ft.Container(
                    content=ft.Icon(
                        ft.Icons.SAVE_OUTLINED,
                        size=16,
                        color=COLORS["text_secondary"],
                        ref=save_icon_ref,
                    ),
                    width=32,
                    height=32,
                    border_radius=6,
                    alignment=ft.alignment.center,
                    on_click=on_save,
                ),
                bgcolor=COLORS["surface"],
                border=ft.border.all(1, COLORS["border"]),
                border_radius=8,
                padding=4,
                tooltip="Save document",
            )
        )

        # Mode selector
        controls.append(
            ft.Container(
                content=ft.Row(
                    [
                        mode_btn(
                            ft.Icons.ARTICLE_OUTLINED,
                            ViewerMode.SINGLE_PAGE,
                            "Single page",
                        ),
                        mode_btn(
                            ft.Icons.VIEW_AGENDA_OUTLINED,
                            ViewerMode.CONTINUOUS,
                            "Continuous scroll",
                        ),
                        mode_btn(
                            ft.Icons.AUTO_STORIES_OUTLINED,
                            ViewerMode.DOUBLE_PAGE,
                            "Double page",
                        ),
                    ],
                    spacing=0,
                ),
                bgcolor=COLORS["surface"],
                border=ft.border.all(1, COLORS["border"]),
                border_radius=8,
                padding=4,
                margin=ft.margin.only(left=8),
            )
        )

        # Navigation
        controls.append(
            ft.Container(
                content=ft.Row(
                    [
                        icon_btn(ft.Icons.CHEVRON_LEFT, on_prev, "Previous"),
                        ft.Container(
                            content=ft.Row([page_text, total_text], spacing=4),
                            padding=ft.padding.symmetric(horizontal=8),
                        ),
                        icon_btn(ft.Icons.CHEVRON_RIGHT, on_next, "Next"),
                    ],
                    spacing=0,
                ),
                bgcolor=COLORS["surface"],
                border=ft.border.all(1, COLORS["border"]),
                border_radius=8,
                padding=4,
                margin=ft.margin.only(left=8),
            )
        )

        # Zoom
        controls.append(
            ft.Container(
                content=ft.Row(
                    [
                        icon_btn(ft.Icons.REMOVE_ROUNDED, on_zoom_out, "Zoom out"),
                        icon_btn(ft.Icons.ADD_ROUNDED, on_zoom_in, "Zoom in"),
                    ],
                    spacing=0,
                ),
                bgcolor=COLORS["surface"],
                border=ft.border.all(1, COLORS["border"]),
                border_radius=8,
                padding=4,
                margin=ft.margin.only(left=8),
            )
        )

        # Draw toggle
        controls.append(
            ft.Container(
                content=ft.Container(
                    content=ft.Icon(
                        ft.Icons.DRAW_OUTLINED
                        if not drawing_active[0]
                        else ft.Icons.DRAW,
                        size=16,
                        color=COLORS["text"]
                        if drawing_active[0]
                        else COLORS["text_secondary"],
                    ),
                    width=32,
                    height=32,
                    border_radius=6,
                    alignment=ft.alignment.center,
                    on_click=on_toggle_draw,
                    bgcolor=COLORS["surface_hover"] if drawing_active[0] else None,
                ),
                bgcolor=COLORS["surface"],
                border=ft.border.all(
                    1,
                    COLORS["selection"] if drawing_active[0] else COLORS["border"],
                ),
                border_radius=8,
                padding=4,
                margin=ft.margin.only(left=8),
                tooltip="Draw mode",
            )
        )

        # Shapes toggle button
        controls.append(
            ft.Container(
                content=ft.Icon(
                    ft.Icons.CATEGORY_OUTLINED,
                    size=16,
                    color=COLORS["text"]
                    if shapes_menu_visible[0]
                    else COLORS["text_secondary"],
                ),
                width=40,
                height=40,
                border_radius=8,
                alignment=ft.alignment.center,
                on_click=toggle_shapes_menu,
                bgcolor=COLORS["surface"],
                border=ft.border.all(
                    1,
                    COLORS["selection"] if shapes_menu_visible[0] else COLORS["border"],
                ),
                margin=ft.margin.only(left=8),
                tooltip="Shapes & Text",
            )
        )

        # Edit/Page manipulation toggle button
        controls.append(
            ft.Container(
                content=ft.Icon(
                    ft.Icons.EDIT_DOCUMENT,
                    size=16,
                    color=COLORS["text"]
                    if edit_menu_visible[0]
                    else COLORS["text_secondary"],
                ),
                width=40,
                height=40,
                border_radius=8,
                alignment=ft.alignment.center,
                on_click=toggle_edit_menu,
                bgcolor=COLORS["surface"],
                border=ft.border.all(
                    1,
                    COLORS["selection"] if edit_menu_visible[0] else COLORS["border"],
                ),
                margin=ft.margin.only(left=8),
                tooltip="Edit Pages",
            )
        )

        controls.append(ft.Container(expand=True))

        # Info button (right side)
        controls.append(
            ft.Container(
                content=ft.Container(
                    content=ft.Icon(
                        ft.Icons.INFO_OUTLINE,
                        size=16,
                        color=COLORS["text_secondary"],
                    ),
                    width=32,
                    height=32,
                    border_radius=6,
                    alignment=ft.alignment.center,
                    on_click=show_pdf_info,
                ),
                bgcolor=COLORS["surface"],
                border=ft.border.all(1, COLORS["border"]),
                border_radius=8,
                padding=4,
                tooltip="PDF Information",
            )
        )

        return controls

    def show_pdf_info(e):
        """Show PDF information dialog - Vercel design system."""
        import os

        # Data
        file_name = os.path.basename(PDF_PATH)
        try:
            size_bytes = os.path.getsize(PDF_PATH)
            file_size = f"{size_bytes:,} bytes"
        except Exception:
            file_size = "—"

        meta = document.metadata
        w, h = document.get_page_size(0)
        perms = document.permissions
        fonts = sorted(document.fonts.keys()) if document.fonts else []

        # Monochromatic palette
        white = "#fafafa"
        gray1 = "#888888"  # secondary text
        gray2 = "#444444"  # borders, inactive
        gray3 = "#1a1a1a"  # subtle bg
        black = "#000000"

        def label_value(lbl: str, val: str):
            return ft.Container(
                content=ft.Row(
                    [
                        ft.Text(lbl, size=11, color=gray1, weight=ft.FontWeight.W_400),
                        ft.Text(
                            val or "—",
                            size=11,
                            color=white if val else gray2,
                            weight=ft.FontWeight.W_500,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=ft.padding.symmetric(vertical=8),
                border=ft.border.only(bottom=ft.BorderSide(1, gray3)),
            )

        def section_header(title: str):
            return ft.Container(
                content=ft.Text(
                    title, size=10, color=gray1, weight=ft.FontWeight.W_600
                ),
                padding=ft.padding.only(top=20, bottom=2),
            )

        def perm_row(items: list):
            return ft.Container(
                content=ft.Row(
                    [
                        ft.Row(
                            [
                                ft.Container(
                                    width=6,
                                    height=6,
                                    border_radius=3,
                                    bgcolor=white if allowed else gray2,
                                ),
                                ft.Text(
                                    name,
                                    size=11,
                                    color=white if allowed else gray2,
                                    weight=ft.FontWeight.W_400,
                                ),
                            ],
                            spacing=8,
                        )
                        for name, allowed in items
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=ft.padding.symmetric(vertical=8),
            )

        def font_chip(name: str):
            return ft.Container(
                content=ft.Text(name, size=10, color=white, weight=ft.FontWeight.W_400),
                bgcolor=gray3,
                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                border_radius=4,
            )

        # Clean date format
        def fmt_date(d):
            if not d:
                return None
            return d.replace("D:", "").split("+")[0].split("-")[0] if d else None

        content = ft.Column(
            [
                # File
                label_value("Name", file_name),
                label_value("Size", file_size),
                label_value("Pages", str(document.page_count)),
                label_value("Dimensions", f"{w:.0f} × {h:.0f} pt"),
                # Metadata
                section_header("Metadata"),
                label_value("Title", meta.get("title")),
                label_value("Author", meta.get("author")),
                label_value("Subject", meta.get("subject")),
                label_value("Creator", meta.get("creator")),
                label_value("Producer", meta.get("producer")),
                label_value("Created", fmt_date(meta.get("creationDate"))),
                label_value("Modified", fmt_date(meta.get("modDate"))),
                # Security
                section_header("Security"),
                label_value("Encrypted", "Yes" if document.is_encrypted else "No"),
                perm_row(
                    [
                        ("Print", perms.get("print", False)),
                        ("Copy", perms.get("copy", False)),
                    ]
                ),
                perm_row(
                    [
                        ("Modify", perms.get("modify", False)),
                        ("Annotate", perms.get("annotate", False)),
                    ]
                ),
                # Fonts
                section_header(f"Fonts ({len(fonts)})"),
                ft.Container(
                    content=ft.Row(
                        [font_chip(f) for f in fonts]
                        if fonts
                        else [ft.Text("None", size=11, color=gray2)],
                        wrap=True,
                        spacing=6,
                        run_spacing=6,
                    ),
                    padding=ft.padding.only(top=6, bottom=12),
                ),
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
        )

        def close_dialog(e):
            dialog.open = False
            page.update()

        dialog = ft.AlertDialog(
            modal=True,
            bgcolor=black,
            surface_tint_color=black,
            shape=ft.RoundedRectangleBorder(radius=10),
            title=None,
            content=ft.Container(
                content=content,
                width=360,
                height=460,
                bgcolor=black,
                padding=ft.padding.symmetric(horizontal=20, vertical=4),
            ),
            actions=[
                ft.Container(
                    content=ft.Text(
                        "Close", size=11, color=white, weight=ft.FontWeight.W_500
                    ),
                    bgcolor=gray3,
                    padding=ft.padding.symmetric(horizontal=16, vertical=8),
                    border_radius=6,
                    on_click=close_dialog,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            actions_padding=ft.padding.only(right=20, bottom=16),
        )
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    # Toolbar
    toolbar = ft.Container(
        content=ft.Row(
            build_toolbar_controls(),
            ref=toolbar_row,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        padding=ft.padding.symmetric(horizontal=24, vertical=12),
        border=ft.border.only(bottom=ft.BorderSide(1, COLORS["border"])),
    )

    # Shapes toolbar (shown when shapes button is clicked)
    shapes_toolbar_ref = ft.Ref[ft.Container]()

    def build_shapes_toolbar():
        """Build the shapes toolbar row."""

        def shape_btn(icon, label, shape_type):
            """Create a shape button."""
            is_active = active_shape_type[0] == shape_type

            def on_hover(e):
                if not is_active:
                    e.control.bgcolor = (
                        COLORS["surface_hover"] if e.data == "true" else "transparent"
                    )
                    if e.control.page:
                        e.control.update()

            return ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(
                            icon,
                            size=20,
                            color=COLORS["text"]
                            if is_active
                            else COLORS["text_secondary"],
                        ),
                        ft.Text(
                            label,
                            size=11,
                            color=COLORS["text"] if is_active else COLORS["text_muted"],
                        ),
                    ],
                    spacing=4,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                width=70,
                height=56,
                border_radius=8,
                alignment=ft.alignment.center,
                bgcolor=COLORS["surface_hover"] if is_active else "transparent",
                border=ft.border.all(1, COLORS["selection"]) if is_active else None,
                on_click=lambda e, st=shape_type: enable_shape_mode(st),
                on_hover=on_hover,
            )

        return [
            ft.Container(width=24),  # Spacer
            shape_btn(ft.Icons.TEXT_FIELDS, "Text", "text"),
            shape_btn(ft.Icons.RECTANGLE_OUTLINED, "Rectangle", "rect"),
            shape_btn(ft.Icons.CIRCLE_OUTLINED, "Circle", "circle"),
            shape_btn(ft.Icons.HORIZONTAL_RULE, "Line", "line"),
            shape_btn(ft.Icons.ARROW_FORWARD, "Arrow", "arrow"),
            ft.Container(expand=True),
            # Close button
            ft.Container(
                content=ft.Icon(ft.Icons.CLOSE, size=16, color=COLORS["text_muted"]),
                width=32,
                height=32,
                border_radius=6,
                alignment=ft.alignment.center,
                on_click=toggle_shapes_menu,
                tooltip="Close",
            ),
            ft.Container(width=24),  # Spacer
        ]

    shapes_toolbar_row_ref = ft.Ref[ft.Row]()

    shapes_toolbar = ft.Container(
        content=ft.Row(
            build_shapes_toolbar(),
            ref=shapes_toolbar_row_ref,
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=COLORS["surface"],
        padding=ft.padding.symmetric(vertical=8),
        border=ft.border.only(bottom=ft.BorderSide(1, COLORS["border"])),
        visible=shapes_menu_visible[0],
        ref=shapes_toolbar_ref,
    )

    def rebuild_shapes_toolbar():
        """Rebuild the shapes toolbar."""
        if shapes_toolbar_ref.current:
            shapes_toolbar_ref.current.visible = shapes_menu_visible[0]
        if shapes_toolbar_row_ref.current:
            shapes_toolbar_row_ref.current.controls = build_shapes_toolbar()
        if shapes_toolbar_ref.current and shapes_toolbar_ref.current.page:
            shapes_toolbar_ref.current.update()

    # Edit/Page manipulation toolbar
    edit_toolbar_ref = ft.Ref[ft.Container]()
    edit_toolbar_row_ref = ft.Ref[ft.Row]()

    def build_edit_toolbar():
        """Build the page edit toolbar row."""

        def edit_btn(icon, label, on_click_fn, tooltip=None, disabled=False):
            """Create an edit action button."""

            def on_hover(e):
                if not disabled:
                    e.control.bgcolor = (
                        COLORS["surface_hover"] if e.data == "true" else "transparent"
                    )
                    if e.control.page:
                        e.control.update()

            return ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(
                            icon,
                            size=20,
                            color=COLORS["text_muted"]
                            if disabled
                            else COLORS["text_secondary"],
                        ),
                        ft.Text(
                            label,
                            size=11,
                            color=COLORS["text_muted"]
                            if disabled
                            else COLORS["text_secondary"],
                        ),
                    ],
                    spacing=4,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                width=70,
                height=56,
                border_radius=8,
                alignment=ft.alignment.center,
                bgcolor="transparent",
                on_click=None if disabled else on_click_fn,
                on_hover=None if disabled else on_hover,
                tooltip=tooltip,
                opacity=0.5 if disabled else 1.0,
            )

        can_move_up = viewer.current_page > 0
        can_move_down = viewer.current_page < document.page_count - 1
        can_delete = document.page_count > 1

        return [
            ft.Container(width=24),  # Spacer
            edit_btn(
                ft.Icons.ROTATE_LEFT, "Rotate L", rotate_page_left, "Rotate 90° left"
            ),
            edit_btn(
                ft.Icons.ROTATE_RIGHT, "Rotate R", rotate_page_right, "Rotate 90° right"
            ),
            ft.Container(
                width=1,
                height=40,
                bgcolor=COLORS["border"],
                margin=ft.margin.symmetric(horizontal=8),
            ),
            edit_btn(
                ft.Icons.ADD, "Add Page", add_blank_page_after, "Add blank page after"
            ),
            edit_btn(
                ft.Icons.CONTENT_COPY,
                "Duplicate",
                duplicate_current_page,
                "Duplicate page",
            ),
            edit_btn(
                ft.Icons.DELETE_OUTLINE,
                "Delete",
                delete_current_page,
                "Delete page" if can_delete else "Cannot delete last page",
                disabled=not can_delete,
            ),
            ft.Container(
                width=1,
                height=40,
                bgcolor=COLORS["border"],
                margin=ft.margin.symmetric(horizontal=8),
            ),
            edit_btn(
                ft.Icons.ARROW_UPWARD,
                "Move Up",
                move_page_up,
                "Move page earlier",
                disabled=not can_move_up,
            ),
            edit_btn(
                ft.Icons.ARROW_DOWNWARD,
                "Move Down",
                move_page_down,
                "Move page later",
                disabled=not can_move_down,
            ),
            ft.Container(expand=True),
            # Close button
            ft.Container(
                content=ft.Icon(ft.Icons.CLOSE, size=16, color=COLORS["text_muted"]),
                width=32,
                height=32,
                border_radius=6,
                alignment=ft.alignment.center,
                on_click=toggle_edit_menu,
                tooltip="Close",
            ),
            ft.Container(width=24),  # Spacer
        ]

    edit_toolbar = ft.Container(
        content=ft.Row(
            build_edit_toolbar(),
            ref=edit_toolbar_row_ref,
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=COLORS["surface"],
        padding=ft.padding.symmetric(vertical=8),
        border=ft.border.only(bottom=ft.BorderSide(1, COLORS["border"])),
        visible=edit_menu_visible[0],
        ref=edit_toolbar_ref,
    )

    def rebuild_edit_toolbar():
        """Rebuild the edit toolbar."""
        if edit_toolbar_ref.current:
            edit_toolbar_ref.current.visible = edit_menu_visible[0]
        if edit_toolbar_row_ref.current:
            edit_toolbar_row_ref.current.controls = build_edit_toolbar()
        if edit_toolbar_ref.current and edit_toolbar_ref.current.page:
            edit_toolbar_ref.current.update()

    # ToC Sidebar
    toc_sidebar = ft.Container(
        ref=toc_sidebar_ref,
        content=ft.Column(
            [
                # Header
                ft.Container(
                    content=ft.Text(
                        "Contents",
                        size=14,
                        color=COLORS["text"],
                        weight=ft.FontWeight.W_600,
                    ),
                    padding=ft.padding.only(left=16, right=16, top=16, bottom=8),
                ),
                # Scrollable ToC items
                ft.Container(
                    content=ft.Column(
                        build_toc_content(),
                        ref=toc_content_ref,
                        spacing=0,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    expand=True,
                    padding=ft.padding.only(bottom=16),
                ),
            ],
            spacing=0,
            expand=True,
        ),
        width=300,
        bgcolor=COLORS["surface"],
        border=ft.border.only(right=ft.BorderSide(1, COLORS["border"])),
        visible=False,
    )

    # Content area with scroll - wrapped in Stack to allow floating text box overlay
    content = ft.Container(
        content=ft.Stack(
            [
                ft.Column(
                    [
                        ft.Container(
                            content=viewer.control,
                            alignment=ft.alignment.top_center,
                            padding=32,
                        ),
                    ],
                    scroll=ft.ScrollMode.AUTO,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    expand=True,
                ),
                # Floating text boxes will be added here dynamically
            ],
            ref=content_stack_ref,
            expand=True,
        ),
        bgcolor=COLORS["bg"],
        expand=True,
    )

    # Main content area with sidebar
    main_content = ft.Row(
        [
            toc_sidebar,
            content,
        ],
        spacing=0,
        expand=True,
    )

    # Layout
    page.add(
        ft.Column(
            [toolbar, shapes_toolbar, edit_toolbar, main_content],
            spacing=0,
            expand=True,
        )
    )


if __name__ == "__main__":
    ft.app(target=main)
