# Flet PDF Viewer
https://github.com/user-attachments/assets/8548970f-36ae-4438-94db-b1c8edb8a159

A pure Python PDF viewer built with Flet Canvas, no external Flutter packages.

## Features

- **Text rendering** with embedded font extraction and registration
- **Character-level text selection** with multi-line support
- **Text annotations**: highlight, underline, strikethrough, squiggly, sticky notes
- **Shape annotations**: rectangles, circles, lines, arrows - draw interactively by click-and-drag
- **Text boxes**: add text anywhere on the page with movable, editable text annotations
- **Ink drawing**: freehand annotations with live preview
- **Search**: find text across all pages with result navigation
- **Table of Contents**: navigate document outline
- **Named destinations**: navigate to PDF anchors/bookmarks by name
- **Page manipulation**: rotate, add, delete, move, copy, resize, crop pages
- **PDF operations**: merge PDFs, extract pages, split into individual files
- **View modes**: single page, continuous scroll, double page
- **Zoom**: scale-based rendering
- **Save**: persist all changes back to PDF

## Installation

```bash
pip install flet pymupdf fonttools
```

## Quick Start

```python
import flet as ft
from flet_pdf_viewer import PdfDocument, PdfViewer, ViewerMode

def main(page: ft.Page):
    document = PdfDocument("/path/to/file.pdf")
    page.fonts = document.fonts

    viewer = PdfViewer(document, mode=ViewerMode.CONTINUOUS)
    page.add(viewer.control)

ft.app(main)
```

### With Configuration

```python
from flet_pdf_viewer import (
    PdfDocument, PdfViewer, ViewerMode,
    ViewerStyle, ZoomConfig, ViewerCallbacks, PageShadow
)

def handle_page_change(page_index: int):
    print(f"Page changed to {page_index}")

viewer = PdfViewer(
    document,
    page=0,
    mode=ViewerMode.CONTINUOUS,
    style=ViewerStyle(
        bgcolor="#f5f5f5",
        selection_color="#4a90d9",
        page_gap=20,
        page_shadow=PageShadow(blur_radius=30, color="#00000066"),
        border_radius=8,
    ),
    zoom=ZoomConfig(
        enabled=True,
        initial=1.0,
        min=0.5,
        max=4.0,
    ),
    callbacks=ViewerCallbacks(
        on_page_change=handle_page_change,
    ),
)
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
- `fonts` - Extracted embedded fonts (dict mapping font names to file paths)

**Methods:**
- `get_page_size(index)` - Returns `(width, height)` in points
- `extract_fonts(assets_dir=None)` - Extract embedded fonts, returns dict for `page.fonts`
- `save(path=None)` - Save document (to original path if None)
- `close()` - Release resources

**Text annotation methods:**
- `add_highlight(page_index, rects, color)`
- `add_underline(page_index, rects, color)`
- `add_strikethrough(page_index, rects, color)`
- `add_squiggly(page_index, rects, color)`
- `add_text_note(page_index, point, text, icon, color)`
- `add_ink(page_index, paths, color, width)`

**Shape annotation methods:**
- `add_rect(page_index, rect, stroke_color, fill_color, width)`
- `add_circle(page_index, rect, stroke_color, fill_color, width)`
- `add_line(page_index, start, end, color, width, start_style, end_style)`
- `add_arrow(page_index, start, end, color, width)`
- `add_freetext(page_index, rect, text, font_size, text_color, fill_color, ...)`
- `add_polygon(page_index, points, stroke_color, fill_color, width)`
- `add_polyline(page_index, points, color, width, start_style, end_style)`

**Page manipulation methods:**
- `rotate_page(page_index, angle)` - Set rotation (0, 90, 180, 270)
- `rotate_page_by(page_index, angle)` - Add to current rotation
- `add_blank_page(width, height, index)` - Insert blank page
- `delete_page(page_index)` - Remove a page
- `delete_pages(from_index, to_index)` - Remove page range
- `move_page(from_index, to_index)` - Reorder pages
- `copy_page(page_index, to_index)` - Duplicate a page
- `resize_page(page_index, width, height)` - Change page dimensions
- `crop_page(page_index, left, top, right, bottom)` - Crop margins

**PDF merge/split methods:**
- `insert_pdf(source, from_page, to_page, start_at)` - Insert pages from another PDF
- `extract_pages(output_path, page_indices)` - Save specific pages to new PDF
- `split_pdf(output_dir, prefix)` - Split into individual page files

**Named destination methods:**
- `resolve_destination(name)` - Get page index for named destination
- `get_destinations()` - Get all named destinations as dict

### PdfViewer

```python
viewer = PdfViewer(
    source,                    # PdfDocument or DocumentBackend
    *,                         # Keyword-only arguments below
    page=0,                    # Initial page index
    mode=ViewerMode.SINGLE_PAGE,
    style=ViewerStyle(...),    # Visual appearance (optional)
    zoom=ZoomConfig(...),      # Zoom settings (optional)
    callbacks=ViewerCallbacks(...),  # Event handlers (optional)
    popup_builder=None,        # Custom popup function
)
```

### Configuration Classes

```python
# Visual appearance
ViewerStyle(
    bgcolor="#ffffff",         # Page background color
    selection_color="#3390ff", # Text selection highlight
    page_gap=16,               # Gap between pages (px)
    page_shadow=PageShadow(),  # Shadow config (or None)
    border_radius=2,           # Page corner radius
)

# Page shadow
PageShadow(
    blur_radius=20,            # Shadow blur
    spread_radius=0,           # Shadow spread
    color="#0000004D",         # Shadow color (with opacity)
    offset_x=0,                # Horizontal offset
    offset_y=0,                # Vertical offset
)

# Zoom settings
ZoomConfig(
    enabled=True,              # Enable interactive zoom
    initial=1.0,               # Initial scale (1.0 = 100%)
    min=0.25,                  # Minimum zoom
    max=5.0,                   # Maximum zoom
)

# Event callbacks
ViewerCallbacks(
    on_page_change=None,       # Callback(page_index: int)
    on_selection_change=None,  # Callback(selected_text: str)
    on_link_click=None,        # Callback(link: LinkInfo) -> bool
    on_text_box_drawn=None,    # Callback(rect: tuple)
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
- `shape_drawing_mode` - Whether shape drawing mode is active
- `current_shape_type` - Current shape type being drawn

**Navigation:**
- `next_page()` - Go to next page
- `previous_page()` - Go to previous page
- `goto(page_index)` - Jump to specific page
- `goto_destination(name)` - Jump to named destination/anchor
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

**Ink drawing:**
- `enable_drawing(color, width)` - Enable freehand drawing
- `disable_drawing()`

**Shape drawing (interactive click-and-drag):**
- `enable_shape_drawing(shape_type, stroke_color, fill_color, stroke_width)`
- `enable_rectangle_drawing(stroke_color, fill_color, stroke_width)`
- `enable_circle_drawing(stroke_color, fill_color, stroke_width)`
- `enable_line_drawing(color, width)`
- `enable_arrow_drawing(color, width)`
- `disable_shape_drawing()`

**Search:**
- `search(query, case_sensitive, whole_word)` - Search document, returns results
- `search_next()` - Go to next result
- `search_prev()` - Go to previous result
- `clear_search()` - Clear search highlights

### ViewerMode

```python
ViewerMode.SINGLE_PAGE   # One page at a time
ViewerMode.CONTINUOUS    # Scrollable stack of all pages
ViewerMode.DOUBLE_PAGE   # Two pages side by side
```

### ShapeType

```python
ShapeType.RECTANGLE  # Rectangle annotation
ShapeType.CIRCLE     # Circle/ellipse annotation
ShapeType.LINE       # Line annotation
ShapeType.ARROW      # Arrow annotation
```

## Font Handling

PDFs often embed custom fonts. The viewer extracts these fonts and registers them with Flet for accurate text rendering:

```python
document = PdfDocument("/path/to/file.pdf")

# Option 1: Use fonts property (extracts to temp directory)
page.fonts = document.fonts

# Option 2: Extract to assets directory (for production)
fonts = document.extract_fonts(assets_dir="assets")
page.fonts = fonts
# Run with: ft.app(target=main, assets_dir="assets")
```

The font extraction:
- Converts all fonts to TTF for Flet/Flutter compatibility
- Supports TTF, OTF, CFF (Type1C), and Type1 (PFA/PFB) font formats
- Works with LaTeX/TeX documents using Computer Modern fonts
- Handles subset font names (e.g., `ABCDEF+Arial` → `Arial`)
- Falls back to system fonts when extraction fails

## Interactive Shape Drawing

Enable shape drawing mode to let users draw shapes by clicking and dragging on the page:

```python
# Enable rectangle drawing - user can click and drag to draw
viewer.enable_rectangle_drawing(
    stroke_color=(1.0, 0.0, 0.0),  # Red border
    fill_color=None,               # No fill (transparent)
    stroke_width=2.0,
)

# Enable arrow drawing
viewer.enable_arrow_drawing(
    color=(0.0, 0.0, 0.0),  # Black
    width=2.0,
)

# Disable shape drawing mode
viewer.disable_shape_drawing()
```

When shape drawing is enabled:
1. User clicks and drags on the page
2. A live preview shows the shape being drawn
3. On release, the shape is saved as a PDF annotation

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

## Page Manipulation

Rotate, add, delete, move, and resize pages:

```python
document = PdfDocument("input.pdf")

# Rotate pages
document.rotate_page(0, 90)       # Set first page to 90°
document.rotate_page_by(1, 180)   # Add 180° to second page

# Add and delete pages
document.add_blank_page()                    # Add blank page at end
document.add_blank_page(595, 842, index=0)   # Add A4 page at beginning
document.delete_page(5)                      # Delete page 5
document.delete_pages(10, 15)                # Delete pages 10-15

# Reorder pages
document.move_page(5, 0)          # Move page 5 to beginning
document.copy_page(0)             # Duplicate first page

# Resize and crop
document.resize_page(0, 612, 792)            # Resize to Letter
document.crop_page(0, 72, 72, 72, 72)        # Crop 1" from all sides

document.save()  # Save changes
```

## PDF Merge and Split

Combine PDFs, extract pages, or split into individual files:

```python
document = PdfDocument("main.pdf")

# Merge: Insert pages from another PDF
document.insert_pdf("appendix.pdf")                      # Append all pages
document.insert_pdf("cover.pdf", start_at=0)             # Insert at beginning
document.insert_pdf("chapter2.pdf", from_page=0, to_page=10, start_at=5)

# Extract specific pages to new PDF
document.extract_pages("summary.pdf", [0, 5, 10])        # Pages 0, 5, 10

# Split into individual page files
files = document.split_pdf("./pages/", prefix="page_")
# Creates: pages/page_0000.pdf, pages/page_0001.pdf, ...

document.save()
```

## Named Destinations

Navigate to PDF anchors/bookmarks by name:

```python
# In viewer - jump to named destination
viewer.goto_destination("chapter1")
viewer.goto_destination("section2.3")

# In document - resolve destination to page number
page_idx = document.resolve_destination("appendix-a")
if page_idx is not None:
    print(f"Appendix A is on page {page_idx}")

# List all named destinations
destinations = document.get_destinations()
for name, page in destinations.items():
    print(f"{name} -> page {page}")
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
    ├── drawing.py           # Ink drawing state machine
    └── shapes.py            # Shape drawing state machine
```

**Design principles:**
- **Backend abstraction** - Swap PDF libraries via `DocumentBackend` protocol
- **Separated concerns** - Rendering, selection, drawing are independent modules
- **Composable** - PdfViewer orchestrates focused components
- **Testable** - Each module can be tested in isolation

## Limitations

- Performance on large/complex PDFs (canvas-based rendering)
- No form filling or embedded multimedia
- Some fonts may not render correctly if not extractable from the PDF

## License

MIT
