"""Windows-specific target-window discovery and capture."""

from dataclasses import dataclass
import sys

from PIL import Image


@dataclass(frozen=True)
class TargetWindow:
    handle: int
    title: str


def _require_windows() -> None:
    if sys.platform != "win32":
        raise RuntimeError("Window selection and capture are supported on Windows only.")


def list_windows() -> list[TargetWindow]:
    _require_windows()
    import win32gui

    windows: list[TargetWindow] = []

    def collect(handle: int, _extra: object) -> bool:
        title = win32gui.GetWindowText(handle).strip()
        if win32gui.IsWindowVisible(handle) and title:
            windows.append(TargetWindow(handle=handle, title=title))
        return True

    win32gui.EnumWindows(collect, None)
    return sorted(windows, key=lambda window: window.title.casefold())


def capture_window(handle: int) -> Image.Image:
    """Capture only the selected HWND using Windows' PrintWindow API."""
    _require_windows()
    import ctypes
    from ctypes import wintypes

    import win32gui
    import win32ui

    if not win32gui.IsWindow(handle) or not win32gui.IsWindowVisible(handle):
        raise RuntimeError("The selected window is no longer available.")

    left, top, right, bottom = win32gui.GetWindowRect(handle)
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0:
        raise RuntimeError("The selected window has no capturable area.")

    window_dc = win32gui.GetWindowDC(handle)
    source_dc = win32ui.CreateDCFromHandle(window_dc)
    memory_dc = source_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    previous_bitmap = None
    print_window = ctypes.WinDLL("user32", use_last_error=True).PrintWindow
    print_window.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    print_window.restype = wintypes.BOOL
    try:
        bitmap.CreateCompatibleBitmap(source_dc, width, height)
        previous_bitmap = memory_dc.SelectObject(bitmap)
        if not print_window(handle, memory_dc.GetSafeHdc(), 2):
            raise RuntimeError("Windows could not capture the selected window.")
        pixels = bitmap.GetBitmapBits(True)
        return Image.frombytes("RGB", (width, height), pixels, "raw", "BGRX", 0, -1)
    finally:
        if previous_bitmap is not None:
            memory_dc.SelectObject(previous_bitmap)
        win32gui.DeleteObject(bitmap.GetHandle())
        memory_dc.DeleteDC()
        source_dc.DeleteDC()
        win32gui.ReleaseDC(handle, window_dc)
