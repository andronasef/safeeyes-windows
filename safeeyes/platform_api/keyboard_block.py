# Safe Eyes is a utility to remind you to take break frequently
# to protect your eyes from eye strain.

# Copyright (C) 2017  Gobinath

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""System-wide keyboard blocking for strict breaks.

Qt can only grab input within the application, so blocking global shortcuts
(Alt+Tab, Super, media keys, ...) during a strict break needs OS-level hooks:
a WH_KEYBOARD_LL low-level hook on Windows and an X11 root keyboard grab on
Linux/X11. Wayland cannot grab globally (degraded, as before) and macOS is a
stub. Secure sequences such as Ctrl+Alt+Del cannot be intercepted by design.
"""

import logging
import threading
import typing

from safeeyes import utility
from safeeyes.platform_api import IS_LINUX, IS_WINDOWS

_blocker: typing.Optional["_Blocker"] = None


def block() -> None:
    """Begin blocking keyboard input system-wide (best effort)."""
    global _blocker
    if _blocker is not None:
        return
    blocker = _make_blocker()
    if blocker is None:
        return
    try:
        blocker.block()
        _blocker = blocker
    except Exception:
        logging.exception("Failed to enable system-wide keyboard block")


def unblock() -> None:
    """Stop blocking keyboard input."""
    global _blocker
    if _blocker is None:
        return
    try:
        _blocker.unblock()
    except Exception:
        logging.exception("Failed to disable system-wide keyboard block")
    finally:
        _blocker = None


def _make_blocker() -> typing.Optional["_Blocker"]:
    if IS_WINDOWS:
        return _WindowsBlocker()
    if IS_LINUX and not utility.IS_WAYLAND:
        return _X11Blocker()
    # Wayland / macOS: no global grab available.
    logging.info("System-wide keyboard block is not supported on this platform")
    return None


class _Blocker:
    def block(self) -> None:
        raise NotImplementedError

    def unblock(self) -> None:
        raise NotImplementedError


# --- Windows --------------------------------------------------------------


class _WindowsBlocker(_Blocker):
    """Swallows all keyboard input via a WH_KEYBOARD_LL hook.

    A low-level hook requires a message loop on the thread that installs it, so
    the hook lives on a dedicated thread; WM_QUIT tears it down.
    """

    def __init__(self) -> None:
        self._thread: typing.Optional[threading.Thread] = None
        self._thread_id: typing.Optional[int] = None
        self._hook = None
        self._proc = None
        self._running = False
        self._ready = threading.Event()

    def block(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=2)

    def _run(self) -> None:
        import ctypes
        from ctypes import wintypes

        WH_KEYBOARD_LL = 13
        HC_ACTION = 0

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # Declare 64-bit-safe signatures: without these, ctypes truncates the
        # pointer arguments/return (HHOOK, proc, HMODULE) to 32 bits and the
        # hook install fails.
        proc_type = ctypes.CFUNCTYPE(
            ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
        )
        user32.SetWindowsHookExW.argtypes = [
            ctypes.c_int,
            proc_type,
            wintypes.HMODULE,
            wintypes.DWORD,
        ]
        user32.SetWindowsHookExW.restype = wintypes.HHOOK
        user32.CallNextHookEx.argtypes = [
            wintypes.HHOOK,
            ctypes.c_int,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        user32.CallNextHookEx.restype = wintypes.LPARAM
        user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
        user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE

        def hook_proc(n_code, w_param, l_param):
            if n_code == HC_ACTION:
                # Non-zero return swallows the keystroke globally.
                return 1
            return user32.CallNextHookEx(None, n_code, w_param, l_param)

        self._proc = proc_type(hook_proc)
        self._thread_id = kernel32.GetCurrentThreadId()
        self._hook = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, self._proc, kernel32.GetModuleHandleW(None), 0
        )

        if not self._hook:
            logging.error("SetWindowsHookExW(WH_KEYBOARD_LL) failed")
            self._running = False
            self._ready.set()
            return

        # Force the thread message queue to exist before we let unblock() post
        # WM_QUIT to it; otherwise an early PostThreadMessage could be dropped
        # and we would block the keyboard indefinitely.
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
        self._ready.set()

        logging.info("Keyboard blocked (Windows low-level hook)")
        while self._running:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0 or ret == -1:
                break

        user32.UnhookWindowsHookEx(self._hook)
        self._hook = None
        logging.info("Keyboard unblocked (Windows)")

    def unblock(self) -> None:
        import ctypes

        WM_QUIT = 0x0012
        self._running = False
        if self._thread_id is not None:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread is not None:
            self._thread.join(timeout=2)
            if self._thread.is_alive() and self._hook:
                # Failsafe: the loop did not exit; an LL hook can be removed from
                # any thread, so never leave the keyboard blocked.
                logging.warning("Keyboard hook thread stuck; unhooking directly")
                ctypes.windll.user32.UnhookWindowsHookEx(self._hook)
                self._hook = None
        self._thread = None
        self._thread_id = None


# --- Linux (X11) ----------------------------------------------------------


class _X11Blocker(_Blocker):
    """Grabs the X11 keyboard at the root window and consumes events.

    Ported from the GTK break screen. Wayland sessions cannot grab globally and
    never reach here.
    """

    def __init__(self) -> None:
        self._thread: typing.Optional[threading.Thread] = None
        self._running = False
        self._display = None

    def block(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        from Xlib import X, display

        logging.info("Lock the keyboard (X11)")
        self._display = display.Display()
        root = self._display.screen().root
        root.grab_keyboard(
            True, X.GrabModeAsync, X.GrabModeAsync, X.CurrentTime
        )

        # Consume keyboard events until released.
        while self._running:
            if self._display.pending_events() > 0:
                self._display.next_event()

        self._display.ungrab_keyboard(X.CurrentTime)
        self._display.flush()
        self._display.close()
        self._display = None
        logging.info("Unlock the keyboard (X11)")

    def unblock(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._thread = None
