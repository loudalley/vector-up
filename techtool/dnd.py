"""Drag files from Explorer onto Tk widgets, with no third-party package.

Tk cannot receive files from Explorer by itself, and tkinterdnd2 would be one
more thing to freeze into the MSI. Windows will deliver WM_DROPFILES to any
window that asks for it, so this subclasses the top-level window, asks, and
works out which drop zone the cursor was over.

Windows only. On any other platform install() is a harmless no-op, so the
module still imports for the tests.
"""
import collections
import ctypes
import sys
from ctypes import wintypes

WM_DROPFILES = 0x0233
WM_COPYGLOBALDATA = 0x0049
GWL_WNDPROC = -4
GA_ROOT = 2
MSGFLT_ALLOW = 1

_WIN = sys.platform == "win32"

if _WIN:
    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(
        LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
        wintypes.LPARAM)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)

    _set_wndproc = getattr(user32, "SetWindowLongPtrW", None) \
        or user32.SetWindowLongW
    _set_wndproc.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    _set_wndproc.restype = ctypes.c_void_p
    user32.CallWindowProcW.argtypes = [
        ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
        wintypes.LPARAM]
    user32.CallWindowProcW.restype = LRESULT
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    user32.ClientToScreen.argtypes = [wintypes.HWND,
                                      ctypes.POINTER(wintypes.POINT)]
    user32.GetWindowRect.argtypes = [wintypes.HWND,
                                     ctypes.POINTER(wintypes.RECT)]
    shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
    shell32.DragQueryFileW.argtypes = [ctypes.c_void_p, wintypes.UINT,
                                       wintypes.LPWSTR, wintypes.UINT]
    shell32.DragQueryFileW.restype = wintypes.UINT
    shell32.DragQueryPoint.argtypes = [ctypes.c_void_p,
                                       ctypes.POINTER(wintypes.POINT)]
    shell32.DragFinish.argtypes = [ctypes.c_void_p]


def read_dropped_files(hdrop):
    """Every path in an HDROP, plus the drop point in client coordinates."""
    count = shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
    paths = []
    for i in range(count):
        n = shell32.DragQueryFileW(hdrop, i, None, 0)
        buf = ctypes.create_unicode_buffer(n + 1)
        shell32.DragQueryFileW(hdrop, i, buf, n + 1)
        paths.append(buf.value)
    pt = wintypes.POINT()
    shell32.DragQueryPoint(hdrop, ctypes.byref(pt))
    return paths, (pt.x, pt.y)


class DropTargets:
    """Route files dropped on the window to whichever zone is under the cursor.

    zones: list of (widget, callback). callback(paths) runs from poll(), which
    the app calls from its own timer.

    The window procedure is called by Windows from inside Tk's own event
    dispatch. Calling back into Tk from there (winfo_id, after, ...) aborts
    the interpreter on Python 3.14, so the procedure touches only ctypes and a
    deque: widget handles are looked up once in install(), and drops are
    queued for poll() to run.
    """

    def __init__(self, root, zones, on_miss=None):
        self.root = root
        self.zones = zones
        self.on_miss = on_miss
        self._hwnd = None
        self._old = None
        self._proc = None  # keep a reference or the callback is collected
        self._zone_hwnds = []
        self._pending = collections.deque()

    def install(self):
        if not _WIN:
            return False
        self.root.update_idletasks()
        self._hwnd = user32.GetAncestor(self.root.winfo_id(), GA_ROOT)
        if not self._hwnd:
            return False
        self._zone_hwnds = [(w.winfo_id(), cb) for w, cb in self.zones]
        # Let drops through when this runs elevated and Explorer does not.
        try:
            for msg in (WM_DROPFILES, WM_COPYGLOBALDATA):
                user32.ChangeWindowMessageFilterEx(
                    self._hwnd, msg, MSGFLT_ALLOW, None)
        except (AttributeError, OSError):
            pass
        self._proc = WNDPROC(self._wndproc)
        self._old = _set_wndproc(self._hwnd, GWL_WNDPROC,
                                 ctypes.cast(self._proc, ctypes.c_void_p))
        shell32.DragAcceptFiles(self._hwnd, True)
        return True

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_DROPFILES:
            try:
                paths, pt = read_dropped_files(wparam)
            finally:
                shell32.DragFinish(wparam)
            if paths:
                self._pending.append((self.zone_at(hwnd, pt), paths))
            return 0
        return user32.CallWindowProcW(self._old, hwnd, msg, wparam, lparam)

    def poll(self):
        """Run queued drops. Call this from the Tk thread, e.g. an after() loop."""
        while self._pending:
            callback, paths = self._pending.popleft()
            if callback is not None:
                callback(paths)
            elif self.on_miss:
                self.on_miss()

    def zone_at(self, hwnd, client_pt):
        """Callback for the zone containing a client-area point, else None."""
        p = wintypes.POINT(client_pt[0], client_pt[1])
        user32.ClientToScreen(hwnd, ctypes.byref(p))
        for zhwnd, callback in self._zone_hwnds:
            r = wintypes.RECT()
            if not user32.GetWindowRect(zhwnd, ctypes.byref(r)):
                continue
            if r.left <= p.x < r.right and r.top <= p.y < r.bottom:
                return callback
        return None
