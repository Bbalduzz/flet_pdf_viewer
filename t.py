"""
Test smooth ink drawing with bezier curves.
"""

import flet as ft
import flet.canvas as cv


def main(page: ft.Page):
    page.title = "Smooth Ink Test"
    page.bgcolor = "#1a1a1a"

    # Store the drawing path
    current_path = []
    all_strokes = []  # Store completed strokes

    def smooth_path_to_bezier(points):
        """Convert a list of points to smooth bezier curve path elements."""
        if len(points) < 2:
            return []

        if len(points) == 2:
            # Just two points - draw a line
            return [
                cv.Path.MoveTo(points[0][0], points[0][1]),
                cv.Path.LineTo(points[1][0], points[1][1]),
            ]

        elements = [cv.Path.MoveTo(points[0][0], points[0][1])]

        # Use quadratic bezier curves for smoothing
        # For each point (except first and last), use it as control point
        for i in range(1, len(points) - 1):
            # Current point is control point
            cx, cy = points[i]
            # End point is midpoint between current and next
            nx, ny = points[i + 1]
            ex, ey = (cx + nx) / 2, (cy + ny) / 2

            elements.append(cv.Path.QuadraticTo(cx, cy, ex, ey))

        # Final segment to the last point
        last_x, last_y = points[-1]
        second_last_x, second_last_y = points[-2]
        elements.append(cv.Path.QuadraticTo(second_last_x, second_last_y, last_x, last_y))

        return elements

    def build_shapes():
        """Build all shapes including completed strokes and current path."""
        shapes = []

        # Draw completed strokes (blue)
        for stroke in all_strokes:
            if len(stroke) >= 2:
                elements = smooth_path_to_bezier(stroke)
                shapes.append(
                    cv.Path(
                        elements,
                        paint=ft.Paint(
                            stroke_width=3,
                            color="#3390ff",
                            style=ft.PaintingStyle.STROKE,
                            stroke_cap=ft.StrokeCap.ROUND,
                            stroke_join=ft.StrokeJoin.ROUND,
                        ),
                    )
                )

        # Draw current path (red while drawing)
        if len(current_path) >= 2:
            elements = smooth_path_to_bezier(current_path)
            shapes.append(
                cv.Path(
                    elements,
                    paint=ft.Paint(
                        stroke_width=3,
                        color="#ff5555",
                        style=ft.PaintingStyle.STROKE,
                        stroke_cap=ft.StrokeCap.ROUND,
                        stroke_join=ft.StrokeJoin.ROUND,
                    ),
                )
            )

        return shapes

    canvas = cv.Canvas(
        shapes=[],
        width=800,
        height=600,
    )

    def on_pan_start(e: ft.DragStartEvent):
        current_path.clear()
        current_path.append((e.local_x, e.local_y))
        canvas.shapes = build_shapes()
        canvas.update()

    def on_pan_update(e: ft.DragUpdateEvent):
        current_path.append((e.local_x, e.local_y))
        canvas.shapes = build_shapes()
        canvas.update()

    def on_pan_end(e: ft.DragEndEvent):
        if len(current_path) >= 2:
            all_strokes.append(list(current_path))
        current_path.clear()
        canvas.shapes = build_shapes()
        canvas.update()

    def clear_canvas(e):
        all_strokes.clear()
        current_path.clear()
        canvas.shapes = []
        canvas.update()

    gesture = ft.GestureDetector(
        content=ft.Container(
            content=canvas,
            bgcolor="#2a2a2a",
            border_radius=10,
        ),
        on_pan_start=on_pan_start,
        on_pan_update=on_pan_update,
        on_pan_end=on_pan_end,
    )

    page.add(
        ft.Column(
            [
                ft.Text("Draw with mouse - smooth bezier curves", color="white"),
                ft.Text("Red = current stroke, Blue = completed strokes", color="gray", size=12),
                gesture,
                ft.ElevatedButton("Clear", on_click=clear_canvas),
            ],
            spacing=10,
        )
    )


if __name__ == "__main__":
    ft.app(target=main)
