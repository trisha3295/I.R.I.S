import ctypes
import winsound
from threading import Thread
from typing import Tuple

class WindowsCursorController:
    """
    Sub-millisecond Windows OS Input Dispatcher using native user32.dll API.
    Features:
    - Direct coordinate manipulation
    - Mouse down / up for drag & drop
    - Middle click & smooth scrolling
    - Non-blocking acoustic audio-chimes
    """
    def __init__(self, enable_sound: bool = True):
        self._user32 = ctypes.windll.user32
        self.enable_sound = enable_sound
        
        # System dimensions
        self.screen_w = int(self._user32.GetSystemMetrics(0))
        self.screen_h = int(self._user32.GetSystemMetrics(1))

        # Win32 Mouse Event Flags
        self.MOUSEEVENTF_MOVE = 0x0001
        self.MOUSEEVENTF_LEFTDOWN = 0x0002
        self.MOUSEEVENTF_LEFTUP = 0x0004
        self.MOUSEEVENTF_RIGHTDOWN = 0x0008
        self.MOUSEEVENTF_RIGHTUP = 0x0010
        self.MOUSEEVENTF_MIDDLEDOWN = 0x0020
        self.MOUSEEVENTF_MIDDLEUP = 0x0040
        self.MOUSEEVENTF_WHEEL = 0x0800

        self.is_dragging = False
        self.last_pos = (self.screen_w // 2, self.screen_h // 2)

    def _play_tone(self, freq: int, duration_ms: int) -> None:
        """Asynchronously plays a system sound frequency without blocking inference."""
        if not self.enable_sound:
            return
        def _beep():
            try:
                winsound.Beep(freq, duration_ms)
            except Exception:
                pass
        Thread(target=_beep, daemon=True).start()

    def move_to(self, x: float, y: float) -> Tuple[int, int]:
        """Instantly repositions cursor at (x, y) clipped to screen bounds."""
        cx = max(0, min(self.screen_w - 1, int(round(x))))
        cy = max(0, min(self.screen_h - 1, int(round(y))))
        self._user32.SetCursorPos(cx, cy)
        self.last_pos = (cx, cy)
        return cx, cy

    def left_click(self) -> None:
        self._user32.mouse_event(self.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        self._user32.mouse_event(self.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        self._play_tone(1200, 35)

    def right_click(self) -> None:
        self._user32.mouse_event(self.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
        self._user32.mouse_event(self.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
        self._play_tone(1700, 40)

    def double_click(self) -> None:
        self.left_click()
        self.left_click()

    def toggle_drag(self) -> bool:
        """Toggles between left mouse button down (dragging) and up (dropped)."""
        if not self.is_dragging:
            self._user32.mouse_event(self.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            self.is_dragging = True
            self._play_tone(800, 60)
        else:
            self._user32.mouse_event(self.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            self.is_dragging = False
            self._play_tone(500, 60)
        return self.is_dragging

    def release_drag(self) -> None:
        if self.is_dragging:
            self._user32.mouse_event(self.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            self.is_dragging = False

    def scroll(self, notches: int) -> None:
        """Scrolls mouse wheel (positive: UP, negative: DOWN)."""
        self._user32.mouse_event(self.MOUSEEVENTF_WHEEL, 0, 0, int(notches * 120), 0)

    def play_recenter_tone(self) -> None:
        self._play_tone(1000, 40)

    def play_pause_tone(self) -> None:
        self._play_tone(600, 50)

    def toggle_sound(self) -> bool:
        self.enable_sound = not self.enable_sound
        if self.enable_sound:
            self._play_tone(1400, 50)
        return self.enable_sound

    def get_screen_size(self) -> Tuple[int, int]:
        return self.screen_w, self.screen_h
