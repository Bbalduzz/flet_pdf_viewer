# Flet PDF Viewer
https://github.com/user-attachments/assets/15736e36-9950-4220-a707-a567b919e266

A pure Python PDF viewer built with Flet Canvas, no external Flutter packages.

## Features

- **Text rendering** with font mapping and styling
- **Character-level text selection** with multi-line support
- **Annotations**: highlight, underline, strikethrough, squiggly, sticky notes
- **Ink drawing**: freehand annotations with live preview
- **View modes**: single page, continuous scroll, double page
- **Zoom**: scale-based rendering
- **Save**: persist annotations back to PDF

## Installation

```bash
pip install flet pymupdf
```

## Quick Start

```python
import flet as ft
from flet_pdf_viewer import PdfDocument, PdfViewer, ViewerMode

def main(page: ft.Page):
    document = PdfDocument("/path/to/file.pdf")
    viewer = PdfViewer(document, mode=ViewerMode.CONTINUOUS)
    page.add(viewer.control)

ft.app(main)
```

## API Reference

### PdfDocument

```python
document = PdfDocument(source)  # str, Path, bytes, or BytesIO
```

**Properties:**
- `page_count` - Number of pages
- `toc` - Table of contents (list of `TocItem`)
- `metadata` - Document metadata dict

**Methods:**
- `get_page_size(index)` - Returns `(width, height)` in points
- `save(path=None)` - Save document (to original path if None)
- `close()` - Release resources

**Annotation methods:**
- `add_highlight(page_index, rects, color)`
- `add_underline(page_index, rects, color)`
- `add_strikethrough(page_index, rects, color)`
- `add_squiggly(page_index, rects, color)`
- `add_text_note(page_index, point, text, icon, color)`
- `add_ink(page_index, paths, color, width)`

### PdfViewer

```python
viewer = PdfViewer(
    source=document,           # PdfDocument
    current_page=0,            # Initial page
    scale=1.0,                 # Zoom level
    mode=ViewerMode.SINGLE_PAGE,
    page_gap=16,               # Gap between pages (continuous/double)
    bgcolor="#ffffff",         # Page background
    selection_color="#3390ff", # Selection highlight color
    popup_builder=None,        # Custom popup function
    on_page_change=None,       # Callback(page_index)
    on_selection_change=None,  # Callback(selected_text)
)
```

**Properties:**
- `control` - Flet control to add to page
- `current_page` - Current page index (read/write)
- `scale` - Zoom scale (read/write)
- `mode` - ViewerMode (read/write)
- `page_count` - Total pages
- `selected_text` - Currently selected text
- `drawing_mode` - Whether ink mode is active

**Navigation:**
- `next_page()` - Go to next page
- `previous_page()` - Go to previous page
- `goto(page_index)` - Jump to specific page
- `zoom_in(factor=1.25)`
- `zoom_out(factor=1.25)`

**Selection actions:**
- `clear_selection()`
- `highlight_selection(color)`
- `underline_selection(color)`
- `strikethrough_selection(color)`
- `squiggly_selection(color)`
- `add_note_at_selection(text, icon, color)`
- `copy_selection()`

**Drawing:**
- `enable_drawing(color, width)`
- `disable_drawing()`

### ViewerMode

```python
ViewerMode.SINGLE_PAGE   # One page at a time
ViewerMode.CONTINUOUS    # Scrollable stack of all pages
ViewerMode.DOUBLE_PAGE   # Two pages side by side
```

## Custom Selection Popup

```python
def my_popup(viewer):
    return ft.Container(
        content=ft.Row([
            ft.IconButton(
                icon=ft.Icons.EDIT,
                on_click=lambda e: viewer.highlight_selection((1.0, 1.0, 0.0)),
            ),
            ft.IconButton(
                icon=ft.Icons.COPY,
                on_click=lambda e: viewer.copy_selection(),
            ),
        ]),
        bgcolor="#262626",
        border_radius=8,
        padding=8,
    )

viewer = PdfViewer(document, popup_builder=my_popup)
```

## Architecture

```
flet_pdf_viewer/
├── __init__.py              # Public API
├── types.py                 # Shared dataclasses
├── viewer.py                # Main PdfViewer component
│
├── backends/
│   ├── base.py              # Abstract protocols
│   └── pymupdf.py           # PyMuPDF implementation
│
├── rendering/
│   └── renderer.py          # Page → Canvas shapes
│
└── interactions/
    ├── selection.py         # Text selection state machine
    └── drawing.py           # Ink drawing state machine
```

**Design principles:**
- **Backend abstraction** - Swap PDF libraries via `DocumentBackend` protocol
- **Separated concerns** - Rendering, selection, drawing are independent modules
- **Composable** - PdfViewer orchestrates focused components
- **Testable** - Each module can be tested in isolation

## Limitations

- Performance on large/complex PDFs (canvas-based rendering)
- No form filling or embedded multimedia
- Text rendering fidelity depends on system font availability

## License

MIT
