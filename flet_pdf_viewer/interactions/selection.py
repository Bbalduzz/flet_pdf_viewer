"""
Text selection handler - manages selection state and logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from ..types import Color, Rect, SelectableChar


@dataclass
class SelectionState:
    """Current selection state."""

    start: Optional[Tuple[float, float]] = None
    end: Optional[Tuple[float, float]] = None
    is_selecting: bool = False
    selected_chars: List[SelectableChar] = field(default_factory=list)


class SelectionHandler:
    """Handles text selection logic."""

    def __init__(
        self,
        on_selection_change: Optional[Callable[[str], None]] = None,
    ):
        self._state = SelectionState()
        self._selectable_chars: List[SelectableChar] = []
        self._on_selection_change = on_selection_change

    @property
    def selected_chars(self) -> List[SelectableChar]:
        """Currently selected characters."""
        return self._state.selected_chars

    @property
    def is_selecting(self) -> bool:
        """Whether selection is in progress."""
        return self._state.is_selecting

    @property
    def selected_text(self) -> str:
        """Get the currently selected text."""
        if not self._state.selected_chars:
            return ""

        sorted_chars = sorted(
            self._state.selected_chars,
            key=lambda c: (c.page_index, round(c.y / 10), c.x),
        )

        result = []
        current_line = []
        last_char = None
        last_page = None

        for char in sorted_chars:
            if last_char is not None and (
                abs(char.y - last_char.y) > char.height * 0.5
                or char.page_index != last_page
            ):
                if current_line:
                    result.append("".join(current_line))
                current_line = []
                last_char = None

            if last_char is not None and char.page_index == last_page:
                gap = char.x - (last_char.x + last_char.width)
                avg_width = (char.width + last_char.width) / 2
                if gap > avg_width * 0.3:
                    current_line.append(" ")

            current_line.append(char.char)
            last_char = char
            last_page = char.page_index

        if current_line:
            result.append("".join(current_line))

        return "\n".join(result)

    def set_selectable_chars(self, chars: List[SelectableChar]) -> None:
        """Update the list of selectable characters."""
        self._selectable_chars = chars

    def start_selection(self, x: float, y: float) -> None:
        """Start a new selection."""
        self._state = SelectionState(
            start=(x, y),
            end=(x, y),
            is_selecting=True,
            selected_chars=[],
        )

    def update_selection(self, x: float, y: float) -> None:
        """Update selection end point."""
        if not self._state.is_selecting:
            return

        self._state.end = (x, y)
        self._update_selected_chars()

    def end_selection(self) -> None:
        """End the current selection."""
        self._state.is_selecting = False
        if self._on_selection_change and self._state.selected_chars:
            self._on_selection_change(self.selected_text)

    def clear(self) -> None:
        """Clear the current selection."""
        self._state = SelectionState()

    def _update_selected_chars(self) -> None:
        """Update selected characters based on selection rectangle."""
        if not self._state.start or not self._state.end:
            return

        x1 = min(self._state.start[0], self._state.end[0])
        y1 = min(self._state.start[1], self._state.end[1])
        x2 = max(self._state.start[0], self._state.end[0])
        y2 = max(self._state.start[1], self._state.end[1])

        # Find directly intersecting characters
        directly_selected = []
        for char in self._selectable_chars:
            char_x1 = char.x + char.page_offset_x
            char_y1 = char.y + char.page_offset_y
            char_x2 = char_x1 + char.width
            char_y2 = char_y1 + char.height

            if self._rects_intersect(
                x1, y1, x2, y2, char_x1, char_y1, char_x2, char_y2
            ):
                directly_selected.append(char)

        if not directly_selected:
            self._state.selected_chars = []
            return

        # Group by line
        lines: Dict[int, List[SelectableChar]] = {}
        for char in directly_selected:
            y_key = round((char.y + char.page_offset_y) / 10)
            if y_key not in lines:
                lines[y_key] = []
            lines[y_key].append(char)

        # Single line - no extension
        if len(lines) <= 1:
            self._state.selected_chars = directly_selected
            return

        # Multiple lines - extend to line edges
        sorted_line_keys = sorted(lines.keys())
        first_line_key = sorted_line_keys[0]
        last_line_key = sorted_line_keys[-1]

        first_line_chars = sorted(
            lines[first_line_key], key=lambda c: c.x + c.page_offset_x
        )
        first_selected_x = first_line_chars[0].x + first_line_chars[0].page_offset_x

        last_line_chars = sorted(
            lines[last_line_key], key=lambda c: c.x + c.page_offset_x
        )
        last_selected_x = (
            last_line_chars[-1].x
            + last_line_chars[-1].page_offset_x
            + last_line_chars[-1].width
        )

        # Build extended selection
        self._state.selected_chars = []
        for char in self._selectable_chars:
            char_x1 = char.x + char.page_offset_x
            char_y1 = char.y + char.page_offset_y
            char_y_key = round(char_y1 / 10)

            if char_y_key < first_line_key or char_y_key > last_line_key:
                continue

            if char_y_key == first_line_key:
                if char_x1 >= first_selected_x - 1:
                    self._state.selected_chars.append(char)
            elif char_y_key == last_line_key:
                char_x2 = char_x1 + char.width
                if char_x2 <= last_selected_x + 1:
                    self._state.selected_chars.append(char)
            else:
                self._state.selected_chars.append(char)

    def _rects_intersect(
        self,
        ax1: float,
        ay1: float,
        ax2: float,
        ay2: float,
        bx1: float,
        by1: float,
        bx2: float,
        by2: float,
    ) -> bool:
        """Check if two rectangles intersect."""
        return ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1

    def get_highlight_rects(self) -> List[Rect]:
        """Get rectangles for visual highlight."""
        chars = self._state.selected_chars
        if not chars:
            return []

        # Group by line
        lines: Dict[int, List[SelectableChar]] = {}
        for char in chars:
            y_key = round((char.y + char.page_offset_y) / 10)
            if y_key not in lines:
                lines[y_key] = []
            lines[y_key].append(char)

        if len(lines) <= 1:
            sorted_chars = sorted(chars, key=lambda c: c.x + c.page_offset_x)
            if not sorted_chars:
                return []

            first = sorted_chars[0]
            last = sorted_chars[-1]

            x1 = first.x + first.page_offset_x
            x2 = last.x + last.page_offset_x + last.width
            y1 = min(c.y + c.page_offset_y for c in sorted_chars)
            y2 = max(c.y + c.page_offset_y + c.height for c in sorted_chars)

            return [(x1, y1, x2, y2)]

        # Multiple lines - compute line bounds
        sorted_line_keys = sorted(lines.keys())
        line_bounds: Dict[int, Tuple[float, float]] = {}

        for char in self._selectable_chars:
            y_key = round((char.y + char.page_offset_y) / 10)
            char_x1 = char.x + char.page_offset_x
            char_x2 = char_x1 + char.width
            if y_key not in line_bounds:
                line_bounds[y_key] = (char_x1, char_x2)
            else:
                line_bounds[y_key] = (
                    min(line_bounds[y_key][0], char_x1),
                    max(line_bounds[y_key][1], char_x2),
                )

        rects = []
        for i, y_key in enumerate(sorted_line_keys):
            line_chars = sorted(lines[y_key], key=lambda c: c.x + c.page_offset_x)
            if not line_chars:
                continue

            first_char = line_chars[0]
            last_char = line_chars[-1]

            y1 = min(c.y + c.page_offset_y for c in line_chars)
            y2 = max(c.y + c.page_offset_y + c.height for c in line_chars)

            line_start = line_bounds.get(
                y_key, (first_char.x + first_char.page_offset_x, 0)
            )[0]
            line_end = line_bounds.get(
                y_key, (0, last_char.x + last_char.page_offset_x + last_char.width)
            )[1]

            if i == 0:
                x1 = first_char.x + first_char.page_offset_x
                x2 = line_end
            elif i == len(sorted_line_keys) - 1:
                x1 = line_start
                x2 = last_char.x + last_char.page_offset_x + last_char.width
            else:
                x1 = line_start
                x2 = line_end

            rects.append((x1, y1, x2, y2))

        return rects

    def get_annotation_rects(self, scale: float) -> Dict[int, List[Rect]]:
        """Get rectangles for annotations, grouped by page, in PDF coordinates."""
        chars = self._state.selected_chars
        if not chars:
            return {}

        chars_by_page: Dict[int, List[SelectableChar]] = {}
        for char in chars:
            if char.page_index not in chars_by_page:
                chars_by_page[char.page_index] = []
            chars_by_page[char.page_index].append(char)

        result: Dict[int, List[Rect]] = {}
        for page_index, page_chars in chars_by_page.items():
            result[page_index] = self._merge_char_rects(page_chars, scale)

        return result

    def _merge_char_rects(
        self, chars: List[SelectableChar], scale: float
    ) -> List[Rect]:
        """Merge adjacent characters into continuous rectangles."""
        if not chars:
            return []

        sorted_chars = sorted(chars, key=lambda c: (round(c.y / 10), c.x))

        rects = []
        current_rect = None
        last_y = None

        for char in sorted_chars:
            char_rect = (
                char.x / scale,
                char.y / scale,
                (char.x + char.width) / scale,
                (char.y + char.height) / scale,
            )

            if current_rect is None:
                current_rect = list(char_rect)
                last_y = char.y
            elif abs(char.y - last_y) < char.height * 0.5:
                current_rect[2] = char_rect[2]
                current_rect[1] = min(current_rect[1], char_rect[1])
                current_rect[3] = max(current_rect[3], char_rect[3])
            else:
                rects.append(tuple(current_rect))
                current_rect = list(char_rect)
                last_y = char.y

        if current_rect:
            rects.append(tuple(current_rect))

        return rects
