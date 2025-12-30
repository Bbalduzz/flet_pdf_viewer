"""
Drawing handler - manages ink/freehand drawing state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from ..types import Color, Path, Point


@dataclass
class DrawingState:
    """Current drawing state."""

    enabled: bool = False
    color: Color = (0.0, 0.0, 0.0)
    width: float = 2.0
    current_path: Path = field(default_factory=list)


class DrawingHandler:
    """Handles ink/freehand drawing logic."""

    def __init__(self):
        self._state = DrawingState()

    @property
    def enabled(self) -> bool:
        """Whether drawing mode is active."""
        return self._state.enabled

    @property
    def color(self) -> Color:
        """Current drawing color."""
        return self._state.color

    @property
    def width(self) -> float:
        """Current stroke width."""
        return self._state.width

    @property
    def current_path(self) -> Path:
        """Current drawing path."""
        return self._state.current_path

    def enable(self, color: Color = (0.0, 0.0, 0.0), width: float = 2.0) -> None:
        """Enable drawing mode."""
        self._state.enabled = True
        self._state.color = color
        self._state.width = width
        self._state.current_path = []

    def disable(self) -> None:
        """Disable drawing mode."""
        self._state.enabled = False
        self._state.current_path = []

    def start_stroke(self, x: float, y: float) -> None:
        """Start a new stroke."""
        if self._state.enabled:
            self._state.current_path = [(x, y)]

    def add_point(self, x: float, y: float, min_distance: float = 5.0) -> None:
        """Add a point to the current stroke if far enough from last point."""
        if self._state.enabled and self._state.current_path:
            last_x, last_y = self._state.current_path[-1]
            dist = ((x - last_x) ** 2 + (y - last_y) ** 2) ** 0.5
            if dist >= min_distance:
                self._state.current_path.append((x, y))
        elif self._state.enabled:
            self._state.current_path.append((x, y))

    def end_stroke(self) -> Path:
        """End the current stroke and return it."""
        path = self._state.current_path
        self._state.current_path = []
        return path

    def clear_path(self) -> None:
        """Clear the current path without saving."""
        self._state.current_path = []

    def get_scaled_path(self, scale: float) -> Path:
        """Get the current path in PDF coordinates."""
        return [(x / scale, y / scale) for x, y in self._state.current_path]

    def get_overlay_color_hex(self) -> str:
        """Get the color as hex string for overlay rendering."""
        r, g, b = self._state.color
        return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"
