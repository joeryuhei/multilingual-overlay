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

    import pywintypes
    import win32gui
    import win32ui

    try:
        if not win32gui.IsWindow(handle) or not win32gui.IsWindowVisible(handle):
            raise RuntimeError("The selected window is no longer available.")
        left, top, right, bottom = win32gui.GetWindowRect(handle)
    except pywintypes.error:
        raise RuntimeError("The selected window is no longer available.") from None
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0:
        raise RuntimeError("The selected window has no capturable area.")

    window_dc = None
    source_dc = None
    memory_dc = None
    bitmap = None
    previous_bitmap = None
    print_window = ctypes.WinDLL("user32", use_last_error=True).PrintWindow
    print_window.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    print_window.restype = wintypes.BOOL
    try:
        window_dc = win32gui.GetWindowDC(handle)
        if not window_dc:
            raise RuntimeError("Windows could not access the selected window.")
        source_dc = win32ui.CreateDCFromHandle(window_dc)
        memory_dc = source_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(source_dc, width, height)
        previous_bitmap = memory_dc.SelectObject(bitmap)
        if not print_window(handle, memory_dc.GetSafeHdc(), 2):
            raise RuntimeError("Windows could not capture the selected window.")
        pixels = bitmap.GetBitmapBits(True)
        return Image.frombytes("RGB", (width, height), pixels, "raw", "BGRX", 0, -1)
    except (pywintypes.error, OSError, ValueError):
        raise RuntimeError("Windows could not capture the selected window.") from None
    finally:
        if memory_dc is not None and previous_bitmap is not None:
            memory_dc.SelectObject(previous_bitmap)
        if bitmap is not None:
            win32gui.DeleteObject(bitmap.GetHandle())
        if memory_dc is not None:
            memory_dc.DeleteDC()
        if source_dc is not None:
            source_dc.DeleteDC()
        if window_dc is not None:
            win32gui.ReleaseDC(handle, window_dc)
