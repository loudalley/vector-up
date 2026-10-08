"""Vector-Up by Koenekt window.

One window. Drop Vector's upgrade package (a zip holding BO\\ and POS\\) on it
and it is unpacked and sorted for you. The tree lists every shop with its back
office and each till; tick what to upgrade, or upgrade a single row, or all.
"""
import datetime
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import terminals as vector_terminals
from . import tillops

from . import APP_TITLE, VERSION, dnd, engine, package, store

GREEN = "#73C509"
DARK = "#17251F"
GREY = "#596A60"
LIGHT = "#F3F6F1"
RED = "#C0392B"
FONT = ("Segoe UI", 10)
CHECK = {"all": "☑", "some": "▣", "none": "☐"}


def _resource(name):
    import sys
    if getattr(sys, "frozen", False):  # one-file exe unpacks to _MEIPASS
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = os.path.join(base, name)
    return p if os.path.isfile(p) else None


class ShopDialog(tk.Toplevel):
    """Add or edit one shop."""

    def __init__(self, parent, shop, default_vnc):
        super().__init__(parent)
        self.title("Shop")
        self.transient(parent)
        self.resizable(False, False)
        self.configure(bg="white", padx=16, pady=14)
        self.result = None
        self.name = tk.StringVar(value=shop.get("name", ""))
        self.path = tk.StringVar(value=shop.get("bo_path", ""))
        self.vnc = tk.StringVar(value=shop.get("vnc_password", ""))

        def row(r, text, var, width=48, browse=False, hint=None):
            tk.Label(self, text=text, bg="white", fg=DARK, font=FONT).grid(
                row=r, column=0, sticky="w", pady=4)
            e = ttk.Entry(self, textvariable=var, width=width)
            e.grid(row=r, column=1, sticky="we", padx=(8, 0))
            if browse:
                ttk.Button(self, text="Browse...", command=self._browse).grid(
                    row=r, column=2, padx=(6, 0))
            if hint:
                tk.Label(self, text=hint, bg="white", fg=GREY,
                         font=("Segoe UI", 9), wraplength=420,
                         justify="left").grid(row=r + 1, column=1,
                                              columnspan=2, sticky="w")
            return e

        first = row(0, "Shop name", self.name)
        row(2, "Back-office folder", self.path, browse=True,
            hint="The folder with Ramset.dat and VectorTerminals.ini, e.g. "
                 "\\\\SERVER\\Ramset. The tills are read from that file.")
        row(4, "Till VNC password", self.vnc, width=16,
            hint=f"Leave blank to use the standard ({default_vnc}).")
        bar = tk.Frame(self, bg="white")
        bar.grid(row=6, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(bar, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(bar, text="Save", command=self._save).pack(
            side="right", padx=(0, 8))
        self.bind("<Return>", lambda _e: self._save())
        self.bind("<Escape>", lambda _e: self.destroy())
        first.focus_set()
        self.grab_set()
        self.wait_window(self)

    def _browse(self):
        d = filedialog.askdirectory(parent=self, title="Back-office folder")
        if d:
            self.path.set(os.path.normpath(d))
            if not self.name.get().strip():
                self.name.set(os.path.basename(os.path.normpath(d)))

    def _save(self):
        if not self.path.get().strip():
            messagebox.showwarning(APP_TITLE, "Enter the back-office folder.",
                                   parent=self)
            return
        self.result = store.new_shop(
            self.name.get() or self.path.get(), self.path.get(),
            self.vnc.get())
        self.destroy()


class App(tk.Tk):
    def __init__(self, initial=None):
        super().__init__()
        self.title(f"{APP_TITLE} {VERSION}")
        self.geometry("1200x820")
        self.minsize(1000, 680)
        self.configure(bg="white")
        ico = _resource("app_icon.ico")
        if ico:
            try:
                self.iconbitmap(ico)
            except tk.TclError:
                pass

        self.cfg = store.load()
        self.scratch = store.scratch_dir()
        self.pkg = None
        self.q = queue.Queue()
        self.busy = False
        self.cancel_flag = False
        self.tills = {}    # normalised bo_path -> [till dicts] or None (no INI)
        self.status = {}   # row key -> (state, text)

        self._build()
        self.dnd = dnd.DropTargets(
            self, [(self.body, self._dropped)],
            on_miss=lambda: self._log("Drop the upgrade package on the window."))
        if not self.dnd.install():
            self._log("Drag-and-drop is not available here - use Browse...")
        self._fill_tree()
        self.after(100, self._pump)
        self.after(300, self._refresh_tills)
        if initial and os.path.exists(initial):  # zip dragged onto the exe icon
            self.after(500, self._load_package, initial)
        self.protocol("WM_DELETE_WINDOW", self._close)

    # ---------------------------------------------------------------- layout
    def _build(self):
        head = tk.Frame(self, bg=DARK)
        head.pack(fill="x")
        tk.Label(head, text="VECTOR-UP  by Koenekt", bg=DARK, fg="white",
                 font=("Segoe UI Semibold", 15)).pack(side="left", padx=16,
                                                      pady=10)
        tk.Label(head, text="Free - drop the Vector upgrade package, then "
                            "upgrade a till, a back office, a shop or all",
                 bg=DARK, fg=GREEN, font=("Segoe UI", 10)).pack(side="left")

        self.body = tk.Frame(self, bg="white")
        self.body.pack(fill="both", expand=True, padx=14, pady=12)
        self.body.columnconfigure(0, weight=1)

        # ---- the one drop zone
        self.drop = tk.Frame(self.body, bg=LIGHT, highlightthickness=2,
                             highlightbackground=GREEN)
        self.drop.grid(row=0, column=0, sticky="we")
        self.drop_title = tk.Label(
            self.drop, text="Drop the upgrade package (.zip) here",
            bg=LIGHT, fg=GREEN, font=("Segoe UI Semibold", 14))
        self.drop_title.pack(pady=(12, 2))
        self.drop_info = tk.Label(
            self.drop, bg=LIGHT, fg=GREY, font=FONT, justify="center",
            text="It must hold a BO folder and a POS folder. BO files go to "
                 "back offices, POS files to tills.")
        self.drop_info.pack()
        bar = tk.Frame(self.drop, bg=LIGHT)
        bar.pack(pady=(8, 12))
        ttk.Button(bar, text="Browse for zip...",
                   command=self._browse_zip).pack(side="left")
        ttk.Button(bar, text="Browse for unzipped folder...",
                   command=self._browse_folder).pack(side="left", padx=(8, 0))
        ttk.Button(bar, text="Clear", command=self._clear_pkg).pack(
            side="left", padx=(8, 0))

        # ---- destinations tree
        tk.Label(self.body, text="Back offices and tills", bg="white",
                 fg=DARK, font=("Segoe UI Semibold", 12)).grid(
            row=1, column=0, sticky="sw", pady=(10, 0))
        # row 1 holds the heading; the tree gets its own expanding row
        self.body.rowconfigure(1, weight=0)
        self.body.rowconfigure(2, weight=3)
        treef = tk.Frame(self.body, bg="white")
        treef.grid(row=2, column=0, sticky="nsew", pady=(4, 6))
        self.tree = ttk.Treeview(
            treef, columns=("sel", "status", "where"),
            show="tree headings", selectmode="browse", height=10)
        self.tree.heading("#0", text="Shop / destination")
        self.tree.heading("sel", text="Tick")
        self.tree.heading("status", text="Result")
        self.tree.heading("where", text="Folder")
        self.tree.column("#0", width=300, stretch=False)
        self.tree.column("sel", width=50, anchor="center", stretch=False)
        self.tree.column("status", width=210, stretch=False)
        self.tree.column("where", width=520, stretch=True)
        tsb = ttk.Scrollbar(treef, command=self.tree.yview)
        self.tree.config(yscrollcommand=tsb.set)
        tsb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("shop", font=("Segoe UI Semibold", 10))
        self.tree.tag_configure("ok", foreground="#2E7D32")
        self.tree.tag_configure("bad", foreground=RED)
        self.tree.bind("<Button-1>", self._tree_click)
        self.tree.bind("<Double-1>", self._tree_double)
        self.tree.bind("<Button-3>", self._tree_menu)
        self.menu = tk.Menu(self, tearoff=0)

        shopbar = tk.Frame(self.body, bg="white")
        shopbar.grid(row=3, column=0, sticky="we")
        for text, cmd in (("Add shop", self._add_shop),
                          ("Edit", self._edit_shop),
                          ("Remove", self._remove_shop),
                          ("Tick all", lambda: self._tick_all(True)),
                          ("Tick none", lambda: self._tick_all(False)),
                          ("Expand", lambda: self._expand(True)),
                          ("Collapse", lambda: self._expand(False)),
                          ("Refresh tills", self._refresh_tills),
                          ("Import shops from Reporter", self._import)):
            ttk.Button(shopbar, text=text, command=cmd).pack(
                side="left", padx=(0, 4))
        self.count_lbl = tk.Label(shopbar, text="", bg="white", fg=GREY,
                                  font=("Segoe UI", 9))
        self.count_lbl.pack(side="right")

        # ---- actions
        acts = tk.Frame(self.body, bg="white")
        acts.grid(row=4, column=0, sticky="we", pady=(10, 4))
        self.btns = []

        def big(text, cmd, primary=False):
            b = tk.Button(
                acts, text=text, command=cmd, relief="flat", padx=14, pady=6,
                bg=GREEN if primary else "#E3E8E1", fg=DARK,
                font=("Segoe UI Semibold", 10))
            b.pack(side="left", padx=(0, 8))
            self.btns.append(b)
            return b

        big("Upgrade ticked", lambda: self._upgrade("ticked"), True)
        big("Upgrade selected row", lambda: self._upgrade("row"))
        big("Upgrade ALL", lambda: self._upgrade("all"))
        big("Check (copy nothing)", self._check)
        big("Create VNC shortcuts", self._vnc)
        self.stop_btn = ttk.Button(acts, text="Stop", command=self._stop,
                                   state="disabled")
        self.stop_btn.pack(side="right")

        opts = tk.Frame(self.body, bg="white")
        opts.grid(row=5, column=0, sticky="w", pady=(0, 6))
        self.backup_var = tk.BooleanVar(value=self.cfg["backup"])
        ttk.Checkbutton(
            opts, text="Back up the files being replaced first",
            variable=self.backup_var, command=self._save_cfg).pack(
            side="left")
        tk.Label(opts, text="   Standard till VNC password", bg="white",
                 fg=DARK, font=("Segoe UI", 9)).pack(side="left")
        self.vnc_var = tk.StringVar(value=self.cfg["vnc_default"])
        e = ttk.Entry(opts, textvariable=self.vnc_var, width=8)
        e.pack(side="left", padx=(4, 0))
        e.bind("<FocusOut>", lambda _e: self._save_cfg())
        self.group_var = tk.BooleanVar(value=self.cfg["group_shortcuts"])
        ttk.Checkbutton(opts, text="shortcuts in a 'Koenekt Tills' folder",
                        variable=self.group_var,
                        command=self._save_cfg).pack(side="left", padx=(10, 0))

        self.bar = ttk.Progressbar(self.body, maximum=100)
        self.bar.grid(row=6, column=0, sticky="we")
        self.body.rowconfigure(5, weight=0)
        self.body.rowconfigure(6, weight=0)
        self.body.rowconfigure(7, weight=2)
        logf = tk.Frame(self.body, bg="white")
        logf.grid(row=7, column=0, sticky="nsew", pady=(8, 0))
        self.log = tk.Text(logf, height=7, wrap="word", bg="#FAFAFA",
                           fg=DARK, relief="solid", bd=1,
                           font=("Consolas", 9), state="disabled")
        sb = ttk.Scrollbar(logf, command=self.log.yview)
        self.log.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True)

        self.status_lbl = tk.Label(self, text="", bg="white", fg=GREY,
                                   anchor="w", font=("Segoe UI", 9))
        self.status_lbl.pack(fill="x", padx=14, pady=(0, 2))
        where = store.data_dir()
        tk.Label(self, bg="white", fg=GREY, anchor="w", font=("Segoe UI", 8),
                 text=("Settings travel with the exe: " if store.portable_dir()
                       else "Settings saved in: ") + where
                 ).pack(fill="x", padx=14, pady=(0, 6))

    # ------------------------------------------------------------ settings
    def _save_cfg(self):
        self.cfg["vnc_default"] = (self.vnc_var.get().strip()
                                   or store.DEFAULT_VNC)
        self.cfg["group_shortcuts"] = bool(self.group_var.get())
        self.cfg["backup"] = bool(self.backup_var.get())
        try:
            store.save(self.cfg)
        except OSError as e:
            self._log(f"Could not save settings: {e}")

    # ----------------------------------------------------------------- tree
    def _children(self, i):
        """[(key, label, folder)] for one shop: its back office, then tills."""
        s = self.cfg["shops"][i]
        rows = [("bo", "Back office", s["bo_path"])]
        for t in self.tills.get(store._norm(s["bo_path"])) or []:
            rows.append((f"t{t['number']}", t.get("name") or
                         f"Terminal {t['number']}", t["share"]))
        return rows

    def _ticked(self, i, sub):
        return sub not in self.cfg["shops"][i].get("off", [])

    def _shop_state(self, i):
        kids = [k for k, _l, _p in self._children(i)]
        on = sum(1 for k in kids if self._ticked(i, k))
        return "all" if on == len(kids) else ("none" if on == 0 else "some")

    def _fill_tree(self, keep=None):
        opened = {iid for iid in self.tree.get_children()
                  if self.tree.item(iid, "open")}
        first = not self.tree.get_children()
        self.tree.delete(*self.tree.get_children())
        for i, s in enumerate(self.cfg["shops"]):
            sid = f"s{i}"
            self.tree.insert(
                "", "end", iid=sid, open=first or sid in opened,
                text=s["name"], tags=("shop",),
                values=(CHECK[self._shop_state(i)], "", s["bo_path"]))
            for sub, label, folder in self._children(i):
                self._insert_row(i, sub, label, folder)
            self._shop_status(i)
        if keep and self.tree.exists(keep):
            self.tree.selection_set(keep)
        n = sum(1 for i in range(len(self.cfg["shops"]))
                if self._shop_state(i) != "none")
        self.count_lbl.config(
            text=f"{n} of {len(self.cfg['shops'])} shop(s) have something "
                 f"ticked")

    def _insert_row(self, i, sub, label, folder):
        key = f"{i}:{sub}"
        state, text = self.status.get(key, ("", ""))
        tag = ("ok",) if state == "ok" else (("bad",) if state else ())
        glyph = {"ok": "✔ ", "partial": "✖ ", "unreachable": "✖ "}.get(state, "")
        self.tree.insert(
            f"s{i}", "end", iid=key, text=label, tags=tag,
            values=(CHECK["all" if self._ticked(i, sub) else "none"],
                    glyph + text if state else "", folder))

    def _shop_status(self, i):
        kids = self._children(i)
        done = sum(1 for k, _l, _p in kids
                   if self.status.get(f"{i}:{k}", ("",))[0] == "ok")
        bad = sum(1 for k, _l, _p in kids
                  if self.status.get(f"{i}:{k}", ("",))[0] in
                  ("partial", "unreachable"))
        text = ""
        if done or bad:
            text = f"{done}/{len(kids)} done" + (f", {bad} failed" if bad else "")
        sid = f"s{i}"
        if self.tree.exists(sid):
            self.tree.set(sid, "status", text)
            self.tree.item(sid, tags=("shop", "bad") if bad else (
                ("shop", "ok") if done == len(kids) and done else ("shop",)))

    def _selected_key(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _tree_click(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        if self.tree.identify_column(event.x) != "#1":
            return
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        if iid.startswith("s"):
            i = int(iid[1:])
            kids = [k for k, _l, _p in self._children(i)]
            turn_on = self._shop_state(i) != "all"
            self.cfg["shops"][i]["off"] = [] if turn_on else kids
        else:
            i, sub = iid.split(":")
            i = int(i)
            off = set(self.cfg["shops"][i].get("off", []))
            off.symmetric_difference_update({sub})
            self.cfg["shops"][i]["off"] = sorted(off)
        self._save_cfg()
        self._fill_tree(keep=iid)
        return "break"

    def _tree_double(self, event):
        iid = self.tree.identify_row(event.y)
        if iid and iid.startswith("s") and \
                self.tree.identify_column(event.x) != "#1":
            self._edit_shop()

    def _tick_all(self, state):
        for s in self.cfg["shops"]:
            s["off"] = []
        if not state:
            for i, s in enumerate(self.cfg["shops"]):
                s["off"] = [k for k, _l, _p in self._children(i)]
        self._save_cfg()
        self._fill_tree()

    def _expand(self, state):
        for iid in self.tree.get_children():
            self.tree.item(iid, open=state)

    def _tree_menu(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        self.tree.selection_set(iid)
        self.menu.delete(0, "end")
        what = ("shop" if iid.startswith("s") else
                "back office" if iid.endswith(":bo") else "till")
        self.menu.add_command(label=f"Upgrade this {what} only",
                              command=lambda: self._upgrade("row"))
        self.menu.add_command(label="Open folder in Explorer",
                              command=lambda: self._open_folder(iid))
        if iid.startswith("s"):
            self.menu.add_command(label="Edit shop...",
                                  command=self._edit_shop)
        self.menu.tk_popup(event.x_root, event.y_root)

    def _open_folder(self, iid):
        path = self.tree.set(iid, "where")
        try:
            os.startfile(path)
        except OSError as e:
            self._log(f"Could not open {path}: {e}")

    # ---------------------------------------------------------------- shops
    def _shop_index(self):
        k = self._selected_key()
        if not k:
            return None
        return int(k[1:]) if k.startswith("s") else int(k.split(":")[0])

    def _add_shop(self):
        if len(self.cfg["shops"]) >= store.MAX_SHOPS:
            return messagebox.showinfo(APP_TITLE, "That is the shop limit.")
        d = ShopDialog(self, {}, self.vnc_var.get())
        if d.result:
            self.cfg["shops"].append(d.result)
            self._save_cfg()
            self._fill_tree()
            self._refresh_tills()

    def _edit_shop(self):
        i = self._shop_index()
        if i is None:
            return
        d = ShopDialog(self, self.cfg["shops"][i], self.vnc_var.get())
        if d.result:
            d.result["off"] = self.cfg["shops"][i].get("off", [])
            self.cfg["shops"][i] = d.result
            self._save_cfg()
            self._fill_tree(keep=f"s{i}")
            self._refresh_tills()

    def _remove_shop(self):
        i = self._shop_index()
        if i is None:
            return
        name = self.cfg["shops"][i]["name"]
        if messagebox.askyesno(APP_TITLE, f"Remove {name} from this list?\n"
                               "Nothing on the shop's PCs is touched."):
            del self.cfg["shops"][i]
            self.status = {}
            self._save_cfg()
            self._fill_tree()

    def _import(self):
        added, skipped, src = store.import_from_reporter(self.cfg)
        if src is None:
            return messagebox.showinfo(
                APP_TITLE, "No Koenekt Reporter settings were found on this "
                           "PC. Add the shops by hand.")
        self.vnc_var.set(self.cfg["vnc_default"])
        self._save_cfg()
        self._fill_tree()
        self._log(f"Imported {added} shop(s) from Reporter "
                  f"({skipped} already listed or empty).")
        self._refresh_tills()

    def _refresh_tills(self):
        shops = [dict(s) for s in self.cfg["shops"]]

        def one(s):
            key = store._norm(s["bo_path"])
            info = vector_terminals.read_terminals(s["bo_path"]) \
                if s["bo_path"] else {"available": False}
            tills = tillops.tills_for_push(info) if info.get("available") \
                else None
            self.q.put(("tills", key, tills))

        def work():
            # An unreachable server can hold a read for a long time; do the
            # shops side by side so one dead PC does not stall the other 19.
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=8) as ex:
                list(ex.map(one, shops))
            self.q.put(("tills_done",))

        threading.Thread(target=work, daemon=True).start()

    # -------------------------------------------------------------- package
    def _dropped(self, paths):
        if self.busy:
            return self._log("Busy - wait for the copy to finish.")
        if len(paths) > 1:
            self._log(f"{len(paths)} items dropped - using the first "
                      f"({os.path.basename(paths[0])}).")
        self._load_package(paths[0])

    def _load_package(self, path):
        self.status_lbl.config(text="Unpacking the package...")
        self.drop_title.config(text="Unpacking...", fg=GREY)

        def work():
            try:
                pkg = package.load(
                    path, self.scratch,
                    progress=lambda p, t: self.q.put(("progress", p, t)))
                self.q.put(("package", pkg, None))
            except Exception as e:
                self.q.put(("package", None, str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _browse_zip(self):
        p = filedialog.askopenfilename(
            title="Upgrade package", filetypes=[("Zip", "*.zip"), ("All", "*")])
        if p:
            self._dropped([p])

    def _browse_folder(self):
        p = filedialog.askdirectory(title="Unzipped upgrade package folder")
        if p:
            self._dropped([p])

    def _clear_pkg(self):
        if self.busy:
            return
        self.pkg = None
        self._show_package()

    def _show_package(self):
        if not self.pkg:
            self.drop_title.config(
                text="Drop the upgrade package (.zip) here", fg=GREEN)
            self.drop_info.config(
                text="It must hold a BO folder and a POS folder. BO files go "
                     "to back offices, POS files to tills.", fg=GREY)
            self.drop.config(highlightbackground=GREEN)
            return
        self.drop_title.config(text="Package ready - drop another to replace "
                                    "it", fg=DARK)
        self.drop_info.config(text=self.pkg.summary(), fg=DARK)
        self.drop.config(highlightbackground=DARK)

    # -------------------------------------------------------------- running
    def _selection(self, mode):
        """Shops (copies) carrying want_bo / want_tills for the run."""
        out = []
        sel = self._selected_key()
        for i, s in enumerate(self.cfg["shops"]):
            d = dict(s, _idx=i, want_bo=True, want_tills=None)
            known = {t["number"] for t in
                     (self.tills.get(store._norm(s["bo_path"])) or [])}
            off = set(s.get("off", []))
            if mode == "all":
                pass
            elif mode == "ticked":
                d["want_bo"] = "bo" not in off
                off_t = {int(k[1:]) for k in off if k.startswith("t")}
                d["want_tills"] = (known - off_t) if off_t else None
            else:  # one row
                if not sel:
                    continue
                if sel.startswith("s"):
                    if int(sel[1:]) != i:
                        continue
                else:
                    si, sub = sel.split(":")
                    if int(si) != i:
                        continue
                    d["want_bo"] = sub == "bo"
                    d["want_tills"] = {int(sub[1:])} if sub != "bo" else set()
            if d["want_bo"] or d["want_tills"] is None or d["want_tills"]:
                out.append(d)
        return out

    def _ready(self, mode):
        if self.busy:
            return None
        if mode == "row" and not self._selected_key():
            messagebox.showinfo(APP_TITLE, "Click a till, a back office or a "
                                           "shop in the list first.")
            return None
        shops = self._selection(mode)
        if not shops:
            messagebox.showinfo(APP_TITLE, "Nothing is ticked.")
            return None
        return shops

    def _need_package(self):
        if not self.pkg:
            messagebox.showinfo(APP_TITLE, "Drop the upgrade package first.")
            return False
        return True

    def _set_busy(self, busy):
        self.busy = busy
        for b in self.btns:
            b.config(state="disabled" if busy else "normal")
        self.stop_btn.config(state="normal" if busy else "disabled")

    def _count(self, shops):
        bo = sum(1 for s in shops if s["want_bo"] and self.pkg.bo)
        tills = 0
        if self.pkg.pos:
            for s in shops:
                known = self.tills.get(store._norm(s["bo_path"])) or []
                w = s["want_tills"]
                tills += len([t for t in known
                              if w is None or t["number"] in w])
        return bo, tills

    def _check(self):
        if not self._need_package():
            return
        shops = self._ready("ticked")
        if not shops:
            return
        self._set_busy(True)
        pkg = self.pkg

        def work():
            plan = engine.build_plan(shops, bool(pkg.pos), bool(pkg.bo))
            engine.check_reachable(plan["targets"])
            lines = []
            for t in plan["targets"]:
                mark = "reachable    " if t["reachable"] else "NOT REACHABLE"
                lines.append(f"{mark}  {t['shop']}  {t['kind']}  "
                             f"{t['label']}  {t['dest']}")
            lines.extend(plan["warnings"])
            lines.append(f"{len(plan['targets'])} destination(s); nothing "
                         f"was copied.")
            self.q.put(("lines", lines))
            self.q.put(("idle",))

        threading.Thread(target=work, daemon=True).start()

    def _upgrade(self, mode):
        if not self._need_package():
            return
        shops = self._ready(mode)
        if not shops:
            return
        bo, tills = self._count(shops)
        scope = {"all": "EVERY shop", "ticked": "the ticked destinations",
                 "row": "the selected row only"}[mode]
        parts = []
        if bo:
            parts.append(f"{bo} back office(s) get {self.pkg.bo.label()}")
        if tills:
            parts.append(f"{tills} till(s) get {self.pkg.pos.label()}")
        if not parts:
            parts.append("(tills not read yet - Refresh tills first, or "
                         "only back offices apply)")
        if not messagebox.askyesno(
                APP_TITLE,
                f"Upgrade {scope}?\n\n" + "\n".join(parts) +
                "\n\nVector must be CLOSED on those PCs. Files are copied "
                "over the old ones and Vector upgrades itself the next time "
                "it starts. Nothing is deleted."
                + ("\nOld versions of replaced files are saved first."
                   if self.backup_var.get() else
                   "\nBackup is OFF - replaced files cannot be restored.")):
            return
        self._set_busy(True)
        self.cancel_flag = False
        self.bar["value"] = 0
        pkg, backup = self.pkg, bool(self.backup_var.get())
        for s in shops:  # fresh results for what is about to run
            for k in list(self.status):
                if k.startswith(f"{s['_idx']}:"):
                    del self.status[k]

        def work():
            started = datetime.datetime.now()
            plan = engine.build_plan(shops, bool(pkg.pos), bool(pkg.bo))
            self.q.put(("lines", plan["warnings"]))
            if not plan["targets"]:
                self.q.put(("lines", ["Nothing to copy to."]))
                self.q.put(("idle",))
                return
            summary = engine.run_upgrade(
                plan["targets"], pkg.bo, pkg.pos,
                lambda *a: self.q.put(a), cancel=lambda: self.cancel_flag,
                backup=backup)
            self.q.put(("lines", [
                engine.summary_text(summary),
                f"Took {(datetime.datetime.now() - started).seconds}s."]))
            self.q.put(("done", summary))

        threading.Thread(target=work, daemon=True).start()

    def _stop(self):
        self.cancel_flag = True
        self.stop_btn.config(state="disabled")

    def _vnc(self):
        if self.busy:
            return
        shops = [dict(s, _idx=i) for i, s in enumerate(self.cfg["shops"])
                 if self._shop_state(i) != "none"]
        if not shops:
            return messagebox.showinfo(APP_TITLE, "Nothing is ticked.")
        if not messagebox.askyesno(
                APP_TITLE,
                f"Create VNC shortcuts for {len(shops)} shop(s)?\n"
                "Each shop's till VNC password is stored in its shortcuts."):
            return
        self._set_busy(True)
        cfg = dict(self.cfg)
        group = bool(self.group_var.get())

        def work():
            r = engine.vnc_shortcuts(
                lambda s: store.vnc_password_for(cfg, s), shops, group=group)
            lines = [f"Created {r['created']} VNC shortcut(s) in {r['folder']}"
                     + (f" ({r['skipped']} skipped)" if r["skipped"] else "")]
            lines += r["errors"]
            self.q.put(("lines", lines))
            self.q.put(("idle",))

        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------------- log
    def _log(self, text):
        self.log.config(state="normal")
        self.log.insert("end", f"{datetime.datetime.now():%H:%M:%S}  {text}\n")
        self.log.see("end")
        self.log.config(state="disabled")
        try:
            with open(os.path.join(store.data_dir(), "upgrade.log"), "a",
                      encoding="utf-8") as f:
                f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  "
                        f"{text}\n")
        except OSError:
            pass

    def _row_status(self, key, state, text):
        self.status[key] = (state, text)
        if self.tree.exists(key):
            glyph = "✔ " if state == "ok" else "✖ "
            self.tree.set(key, "status", glyph + text)
            self.tree.item(key, tags=("ok",) if state == "ok" else ("bad",))
        self._shop_status(int(key.split(":")[0]))

    def _pump(self):
        self.dnd.poll()
        try:
            while True:
                m = self.q.get_nowait()
                kind = m[0]
                if kind == "log":
                    self._log(m[1])
                elif kind == "lines":
                    for line in m[1]:
                        self._log(line)
                elif kind == "progress":
                    self.bar["value"] = m[1]
                    self.status_lbl.config(text=m[2])
                elif kind == "target":
                    self._row_status(m[1], m[2], m[3])
                elif kind == "tills":
                    self.tills[m[1]] = m[2]
                elif kind == "tills_done":
                    self._fill_tree(keep=self._selected_key())
                elif kind == "package":
                    _k, pkg, err = m
                    self.status_lbl.config(text="")
                    self.bar["value"] = 0
                    if err:
                        self._log(err)
                        self._show_package()
                        messagebox.showwarning(APP_TITLE, err)
                    else:
                        self.pkg = pkg
                        self.status.clear()
                        self._fill_tree(keep=self._selected_key())
                        self._show_package()
                        for line in pkg.summary().splitlines():
                            self._log(line)
                elif kind in ("done", "idle"):
                    self._set_busy(False)
                    self.status_lbl.config(text="")
        except queue.Empty:
            pass
        self.after(100, self._pump)

    def _close(self):
        if self.busy and not messagebox.askyesno(
                APP_TITLE, "A copy is still running. Quit anyway?"):
            return
        self._save_cfg()
        self.destroy()


def main(argv=None):
    import sys
    args = list(sys.argv[1:] if argv is None else argv)
    try:  # sharp text on high-DPI laptops
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    App(initial=args[0] if args else None).mainloop()
