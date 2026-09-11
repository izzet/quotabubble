from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtWidgets import QWidget

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000

_user32 = ctypes.windll.user32

if ctypes.sizeof(ctypes.c_void_p) == 8:
    _get_window_long = _user32.GetWindowLongPtrW
    _set_window_long = _user32.SetWindowLongPtrW
else:
    _get_window_long = _user32.GetWindowLongW
    _set_window_long = _user32.SetWindowLongW

_get_window_long.argtypes = [wintypes.HWND, ctypes.c_int]
_get_window_long.restype = ctypes.c_ssize_t
_set_window_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
_set_window_long.restype = ctypes.c_ssize_t


def configure_window(widget: QWidget) -> None:
    hwnd = wintypes.HWND(int(widget.winId()))
    style = _get_window_long(hwnd, GWL_EXSTYLE)
    style |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    style &= ~WS_EX_APPWINDOW
    _set_window_long(hwnd, GWL_EXSTYLE, style)
