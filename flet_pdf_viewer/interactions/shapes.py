"""
Shape drawing handler - manages interactive shape drawing state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from ..types import Color, ShapeType


@dataclass
class ShapeDrawingState:
    """Current shape drawing state."""

    shape_type: ShapeType = ShapeType.NONE
    stroke_color: Color = (0.0, 0.0, 0.0)
    fill_color: Optional[Color] = None
    stroke_width: float = 2.0
    # Start and end points for the current shape being drawn
    start_x: Optional[float] = None
    start_y: Optional[float] = None
    end_x: Optional[float] = None
    end_y: Optional[float] = None
    is_drawing: bool = False


class ShapeDrawingHandler:
    """Handles interactive shape drawing logic."""

    def __init__(self):
        self._state = ShapeDrawingState()

    @property
    def enabled(self) -> bool:
        """Whether shape drawing mode is active."""
        return self._state.shape_type != ShapeType.NONE

    @property
    def shape_type(self) -> ShapeType:
        """Current shape type being drawn."""
        return self._state.shape_type

    @property
    def stroke_color(self) -> Color:
        """Current stroke color."""
        return self._state.stroke_color

    @property
    def fill_color(self) -> Optional[Color]:
        """Current fill color."""
        return self._state.fill_color

    @property
    def stroke_width(self) -> float:
        """Current stroke width."""
        return self._state.stroke_width

    @property
    def is_drawing(self) -> bool:
        """Whether currently in the middle of drawing a shape."""
        return self._state.is_drawing

    def enable(
        self,
        shape_type: ShapeType,
        stroke_color: Color = (0.0, 0.0, 0.0),
        fill_color: Optional[Color] = None,
        stroke_width: float = 2.0,
    ) -> None:
        """Enable shape drawing mode with specified shape type."""
        self._state.shape_type = shape_type
        self._state.stroke_color = stroke_color
        self._state.fill_color = fill_color
        self._state.stroke_width = stroke_width
        self._clear_points()

    def disable(self) -> None:
        """Disable shape drawing mode."""
        self._state.shape_type = ShapeType.NONE
        self._clear_points()

    def start_shape(self, x: float, y: float) -> None:
        """Start drawing a shape at the given point."""
        if self.enabled:
            self._state.start_x = x
            self._state.start_y = y
            self._state.end_x = x
            self._state.end_y = y
            self._state.is_drawing = True

    def update_shape(self, x: float, y: float) -> None:
        """Update the current shape's end point."""
        if self._state.is_drawing:
            self._state.end_x = x
            self._state.end_y = y

    def end_shape(
        self,
    ) -> Optional[Tuple[ShapeType, float, float, float, float]]:
        """End the current shape and return its data.

        Returns:
            Tuple of (shape_type, x1, y1, x2, y2) or None if not drawing
        """
        if not self._state.is_drawing:
            return None

        if (
            self._state.start_x is None
            or self._state.start_y is None
            or self._state.end_x is None
            or self._state.end_y is None
        ):
            self._clear_points()
            return None

        result = (
            self._state.shape_type,
            self._state.start_x,
            self._state.start_y,
            self._state.end_x,
            self._state.end_y,
        )
        self._clear_points()
        return result

    def cancel_shape(self) -> None:
        """Cancel the current shape being drawn."""
        self._clear_points()

    def _clear_points(self) -> None:
        """Clear the current drawing points."""
        self._state.start_x = None
        self._state.start_y = None
        self._state.end_x = None
        self._state.end_y = None
        self._state.is_drawing = False

    def get_current_rect(self) -> Optional[Tuple[float, float, float, float]]:
        """Get the current shape bounds as a normalized rect (x0, y0, x1, y1).

        Returns:
            Normalized rect where x0 < x1 and y0 < y1, or None if not drawing
        """
        if not self._state.is_drawing:
            return None

        if (
            self._state.start_x is None
            or self._state.start_y is None
            or self._state.end_x is None
            or self._state.end_y is None
        ):
            return None

        x0 = min(self._state.start_x, self._state.end_x)
        y0 = min(self._state.start_y, self._state.end_y)
        x1 = max(self._state.start_x, self._state.end_x)
        y1 = max(self._state.start_y, self._state.end_y)

        return (x0, y0, x1, y1)

    def get_current_line(self) -> Optional[Tuple[float, float, float, float]]:
        """Get the current line points (start_x, start_y, end_x, end_y).

        Returns:
            Tuple of (x1, y1, x2, y2) or None if not drawing
        """
        if not self._state.is_drawing:
            return None

        if (
            self._state.start_x is None
            or self._state.start_y is None
            or self._state.end_x is None
            or self._state.end_y is None
        ):
            return None

        return (
            self._state.start_x,
            self._state.start_y,
            self._state.end_x,
            self._state.end_y,
        )

    def get_stroke_color_hex(self) -> str:
        """Get the stroke color as hex string for overlay rendering."""
        r, g, b = self._state.stroke_color
        return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"

    def get_fill_color_hex(self) -> Optional[str]:
        """Get the fill color as hex string for overlay rendering."""
        if self._state.fill_color is None:
            return None
        r, g, b = self._state.fill_color
        return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"
