"""
PDF Viewer - Minimal, elegant design with text selection.
"""

import flet as ft

from pdf_viewer import PdfDocument, PdfViewer, PdfViewerMode

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


def main(page: ft.Page):
    page.title = "PDF Viewer"
    page.padding = 0
    page.bgcolor = COLORS["bg"]
    page.theme_mode = ft.ThemeMode.DARK
    page.fonts = {"Inter": "https://rsms.me/inter/font-files/Inter-Regular.woff2"}
    page.theme = ft.Theme(font_family="Inter")

    # Selected highlight color
    selected_color = [0]

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
    document = PdfDocument("/Users/edoardobalducci/Downloads/Restauro-appunti.pdf")
    # document = PdfDocument(
    #     "/Users/edoardobalducci/Downloads/Preventivo Sviluppo Siti Komdo.pdf"
    # )

    viewer = PdfViewer(
        source=document,
        scale=1.0,
        mode=PdfViewerMode.CONTINUOUS,
        selection_color=COLORS["selection"],
        popup_builder=build_popup,
    )

    # State
    current_mode = PdfViewerMode.CONTINUOUS
    drawing_active = [False]  # Use list to allow mutation in nested functions

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
            viewer.enable_drawing(color=(0.2, 0.2, 0.8), width=2.0)
        else:
            viewer.disable_drawing()
        rebuild_toolbar()

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
    def mode_btn(icon, mode: PdfViewerMode, tooltip: str):
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

    # Toolbar reference for rebuilding
    toolbar_row = ft.Ref[ft.Row]()

    def rebuild_toolbar():
        toolbar_row.current.controls = build_toolbar_controls()
        toolbar_row.current.update()

    def build_toolbar_controls():
        return [
            ft.Container(expand=True),
            # Save button
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
            ),
            # Mode selector
            ft.Container(
                content=ft.Row(
                    [
                        mode_btn(
                            ft.Icons.ARTICLE_OUTLINED,
                            PdfViewerMode.SINGLE_PAGE,
                            "Single page",
                        ),
                        mode_btn(
                            ft.Icons.VIEW_AGENDA_OUTLINED,
                            PdfViewerMode.CONTINUOUS,
                            "Continuous scroll",
                        ),
                        mode_btn(
                            ft.Icons.AUTO_STORIES_OUTLINED,
                            PdfViewerMode.DOUBLE_PAGE,
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
            ),
            # Navigation
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
            ),
            # Zoom
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
            ),
            # Draw toggle
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
            ),
            ft.Container(expand=True),
        ]

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

    # Content area with scroll
    content = ft.Container(
        content=ft.Column(
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
        bgcolor=COLORS["bg"],
        expand=True,
    )

    # Layout
    page.add(
        ft.Column(
            [toolbar, content],
            spacing=0,
            expand=True,
        )
    )


if __name__ == "__main__":
    ft.app(target=main)
