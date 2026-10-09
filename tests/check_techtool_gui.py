"""Opens the real window, drops the real Vector package on it, and upgrades.

Needs a Windows desktop session (it creates a Tk window), so it is a check
script, not part of the unit suite. Run: python tests/check_techtool_gui.py

Shops are local folders standing in for network shares; the real package in
Downloads is used if present, else a generated one of the same layout.
"""
import ctypes
import os
import struct
import sys
import tempfile
from ctypes import wintypes
from pathlib import Path
from tkinter import messagebox
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

# Never touch the technician's real shop list while checking.
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp()

from techtool import dnd, gui, store  # noqa: E402
from test_techtool import REAL_ZIP, make_package  # noqa: E402

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                wintypes.WPARAM, wintypes.LPARAM]


def make_hdrop(paths, x, y):
    """A genuine DROPFILES block: header (20 bytes) + double-null wide list."""
    body = ("\0".join(paths) + "\0\0").encode("utf-16-le")
    blob = struct.pack("<IiiII", 20, x, y, 0, 1) + body
    h = kernel32.GlobalAlloc(0x0002 | 0x0040, len(blob))  # MOVEABLE|ZEROINIT
    p = kernel32.GlobalLock(h)
    ctypes.memmove(p, blob, len(blob))
    kernel32.GlobalUnlock(h)
    return h


def drop(app, widget, paths):
    hwnd = user32.GetAncestor(app.winfo_id(), 2)
    r = wintypes.RECT()
    user32.GetWindowRect(widget.winfo_id(), ctypes.byref(r))
    pt = wintypes.POINT((r.left + r.right) // 2, (r.top + r.bottom) // 2)
    user32.ScreenToClient(hwnd, ctypes.byref(pt))
    user32.PostMessageW(hwnd, dnd.WM_DROPFILES, make_hdrop(paths, pt.x, pt.y), 0)


def wait_for(app, cond, secs=20):
    import time
    end = time.time() + secs
    while time.time() < end:
        app.update()
        if cond():
            return True
        time.sleep(0.05)
    return False


def main():
    work = Path(tempfile.mkdtemp())
    zip_path = REAL_ZIP
    if not os.path.isfile(zip_path):
        zip_path = str(work / "pkg.zip")
        make_package(zip_path)
    print("package:", os.path.basename(zip_path))

    # three shops, two tills each, all local folders
    tills = {}
    cfg = store.load()
    for i in range(3):
        bo = work / f"shop{i}" / "bo"
        bo.mkdir(parents=True)
        t = []
        for n in (1, 2):
            d = work / f"shop{i}" / f"till{n}"
            d.mkdir()
            (d / "postrans.dat").write_text("synthetic transactions")
            (d / "posdebtor.dat").write_text("synthetic debtors")
            t.append({"number": n, "name": f"TILL {n}", "share": str(d)})
        (bo / "VectorTerminals.ini").write_text(
            "\n".join(f"[TERMINAL {n}]\nName=TILL {n}\nEnabled=True\nTerminalLocation={d['share']}"
                        for n, d in enumerate(t, 1)) +
            "\n[TERMINAL 3]\nName=TILL 3\nEnabled=False\nTerminalLocation=\n",
            encoding="utf-8")
        tills[store._norm(str(bo))] = t
        cfg["shops"].append(store.new_shop(f"Shop {i}", str(bo)))
    store.save(cfg)

    def has(p):
        return (Path(p) / "_UpgradeRequired").is_file()

    with patch.object(messagebox, "askyesno", lambda *a, **k: True), \
            patch.object(messagebox, "showinfo", lambda *a, **k: None), \
            patch.object(messagebox, "showwarning", lambda *a, **k: None):
        app = gui.App()
        callback_errors = []
        app.report_callback_exception = lambda *args: callback_errors.append(args)
        app.geometry("1200x820+30+30")
        app.update()
        assert app._intro and app._intro.winfo_ismapped(), "startup logo not visible"
        assert len(app._intro_frames) == 21, "startup logo frames missing"
        assert app.koenekt_logo and app.vector_logo, "brand assets missing"
        assert wait_for(app, lambda: app._intro is None, 4), "startup animation did not finish"
        assert not app._intro_frames and not app._intro_after
        # Dismissal must cancel its timer and release images without stale callbacks.
        app._start_intro()
        app.update()
        app.event_generate("<Escape>")
        app.update()
        assert app._intro is None and not app._intro_after, "Escape did not dismiss startup logo"
        app._start_intro()
        app.update()
        app._intro.event_generate("<Button-1>")
        app.update()
        assert app._intro is None and not app._intro_after, "click did not dismiss startup logo"
        print("Brand resources + automatic fade + Escape/click dismissal: OK")
        assert wait_for(app, lambda: len(app.tills) == 3), "tills not read"
        app.update()
        assert app.dnd._hwnd, "drop target was not installed"
        rows = [i for i in app.tree.get_children()]
        assert len(rows) == 3 and len(app.tree.get_children(rows[0])) == 4

        assert app.tree.set("0:t3", "status") == "No till folder"
        assert not app._ticked(0, "t3")
        app._toggle_tick("0:t3")
        assert not app._ticked(0, "t3")
        assert len(app._selection("ticked")) == 3
        print("Real INI discovery: local tills shown; missing folders visible and unselectable: OK")

        # --- real checkbox hit testing, keyboard toggle and mixed shop state
        iid = "0:t1"
        x, y, width, height = app.tree.bbox(iid, "#0")
        image_x = next(px for px in range(x, x + width)
                       if "image" in app.tree.identify_element(px, y + height//2))
        app.tree.event_generate("<Button-1>", x=image_x, y=y+height//2)
        app.update()
        assert not app._ticked(0, "t1") and app._shop_state(0) == "some"
        app._tree_space(None)
        assert app._ticked(0, "t1") and app._shop_state(0) == "all"
        app.tree.focus_set()
        app.tree.event_generate("<space>")
        app.update()
        assert not app._ticked(0, "t1"), "actual Space event did not toggle focused row"
        app.tree.event_generate("<space>")
        app.update()
        assert app._ticked(0, "t1")
        # Check geometry at minimum size, including all primary actions.
        app.geometry("1000x680+30+30")
        app.update()
        for button in app.btns + app.package_btns + [app.stop_btn]:
            assert button.winfo_ismapped(), button.cget("text")
            assert button.winfo_rootx() + button.winfo_width() <= app.winfo_rootx() + app.winfo_width()
            assert button.winfo_rooty() + button.winfo_height() <= app.winfo_rooty() + app.winfo_height()
        for widget in (app.tree, app.log, app.status_lbl):
            assert widget.winfo_ismapped()
            assert widget.winfo_height() >= 16, "main content collapsed at minimum size"
            assert widget.winfo_rooty() + widget.winfo_height() <= app.winfo_rooty() + app.winfo_height(), \
                "main content clipped at minimum size"
        app._log("Minimum-size activity message")
        app.update()
        visible_line = app.log.dlineinfo("end-2c")
        assert visible_line and visible_line[1] + visible_line[3] <= app.log.winfo_height(), \
            "newest activity message not readable at minimum size"
        app.geometry("1200x860+30+30")
        app.update()

        # --- drop the package on the window (over the shop list, not a pane)
        drop(app, app.tree, [zip_path])
        assert wait_for(app, lambda: app.pkg is not None), "package not loaded"
        print(app.pkg.summary())
        assert app.pkg.bo and app.pkg.pos
        assert "\n" not in app.drop_info.cget("text"), "package summary crowds destination rows"
        assert "BO_" in app.drop_info.cget("text") and "POS_" in app.drop_info.cget("text")

        # --- upgrade ONE till
        app.tree.selection_set("1:t2")
        app._upgrade("row")
        assert wait_for(app, lambda: not app.busy and app.status.get("1:t2"))
        shop1 = tills[store._norm(cfg["shops"][1]["bo_path"])]
        assert has(shop1[1]["share"]), "selected till not upgraded"
        assert not has(shop1[0]["share"]), "other till was touched"
        assert not has(cfg["shops"][1]["bo_path"]), "BO was touched"
        assert not has(tills[store._norm(cfg["shops"][0]["bo_path"])][0]["share"])
        print("one till only: OK  ->", ascii(app.tree.set("1:t2", "status")))

        # --- upgrade ONE back office
        app.tree.selection_set("2:bo")
        app._upgrade("row")
        assert wait_for(app, lambda: not app.busy and app.status.get("2:bo"))
        assert has(cfg["shops"][2]["bo_path"])
        assert not has(cfg["shops"][0]["bo_path"])
        assert not has(tills[store._norm(cfg["shops"][2]["bo_path"])][0]["share"])
        bo2 = Path(cfg["shops"][2]["bo_path"])
        assert (bo2 / "RP_BACK.exe").is_file() and not (bo2 / "RPOS25.exe").exists()
        print("one back office only: OK")

        # --- untick a till, upgrade the ticked ones
        app.tree.event_generate("<Button-1>")  # no-op, keeps the loop honest
        cfg_s = app.cfg["shops"]
        cfg_s[0]["off"] = ["t1"]
        app._fill_tree()
        app._upgrade("ticked")
        assert wait_for(app, lambda: not app.busy and app.status.get("0:bo"))
        s0 = tills[store._norm(cfg_s[0]["bo_path"])]
        assert not has(s0[0]["share"]), "unticked till was upgraded"
        assert has(s0[1]["share"]) and has(cfg_s[0]["bo_path"])
        print("unticked till skipped: OK")

        # --- ALL ignores ticks
        app._upgrade("all")
        assert wait_for(app, lambda: not app.busy and app.status.get("0:t1"))
        for bo, ts in tills.items():
            for t in ts:
                assert has(t["share"]), t
        assert all(has(s["bo_path"]) for s in cfg_s)
        marks = [ascii(app.tree.set(f"{i}:t1", "status")) for i in range(3)]
        print("ALL: OK  ->", marks)
        snapshots = list(Path(store.pos_backup_dir()).rglob("postrans.dat"))
        assert snapshots and all(p.parent.joinpath("posdebtor.dat").is_file() for p in snapshots)
        assert not any(Path(s["bo_path"], "_koenekt_backup").exists() for s in cfg_s)
        print("POS data backups + manual BO policy: OK")

        # --- a junk drop is refused, the loaded package survives
        junk = work / "junk.zip"
        junk.write_bytes(b"nope")
        before = app.pkg
        drop(app, app.tree, [str(junk)])
        wait_for(app, lambda: False, 1.5)
        assert app.pkg is before
        print("bad drop refused, package kept: OK")
        assert not callback_errors, callback_errors
        app.destroy()
    print("GUI + package + per-till upgrade check: OK")


if __name__ == "__main__":
    main()
