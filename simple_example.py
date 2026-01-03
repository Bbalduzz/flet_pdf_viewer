"""
Minimal PDF Viewer example.
For a complete demo check example.py
"""

import flet as ft

from flet_pdf_viewer import PdfDocument, PdfViewer, ZoomConfig


def main(page: ft.Page):
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.title = "PDF Viewer"
    page.padding = 0

    document = PdfDocument("demo_files/multicolumn.pdf")
    page.fonts = document.fonts

    viewer = PdfViewer(document, zoom=ZoomConfig(initial=0.7))

    # This is for ease of use - the pdf initializiation
    # and rendering is done :)
    prev_btn = ft.Ref[ft.IconButton]()
    next_btn = ft.Ref[ft.IconButton]()

    def on_prev(e):
        viewer.previous_page()

    def on_next(e):
        viewer.next_page()

    nav_buttons = ft.Container(
        content=ft.Row(
            [
                ft.IconButton(
                    ref=prev_btn,
                    icon=ft.Icons.CHEVRON_LEFT,
                    icon_size=24,
                    on_click=on_prev,
                ),
                ft.IconButton(
                    ref=next_btn,
                    icon=ft.Icons.CHEVRON_RIGHT,
                    icon_size=24,
                    on_click=on_next,
                ),
            ],
            spacing=4,
        ),
        bgcolor=ft.Colors.with_opacity(0.9, ft.Colors.SURFACE),
        border_radius=8,
        padding=4,
        right=16,
        bottom=16,
    )

    page.add(
        ft.Stack(
            [
                viewer.control,
                nav_buttons,
            ],
            expand=True,
        )
    )


if __name__ == "__main__":
    ft.app(target=main)
