"""Vector-Up by Koenekt window.

One window. Drop Vector's upgrade package (a zip holding BO\\ and POS\\) on it
and it is unpacked and sorted for you. The tree lists every shop with its back
office and each till; tick what to upgrade, or upgrade a single row, or all.
"""
import datetime
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, font as tkfont

from . import terminals as vector_terminals
from . import tillops

from . import APP_TITLE, VERSION, dnd, downloads, engine, package, store

GREEN = "#73C509"
DARK = "#17251F"
GREY = "#596A60"
LIGHT = "#F1F5F2"
RED = "#C0392B"
FONT = ("Segoe UI", 10)
WHITE = "#FFFFFF"
BORDER = "#D8E2DB"
HOVER = "#E5EDE7"
SELECT = "#EAF5DF"
DISABLED = "#A0AAA2"
SUCCESS = "#2E7D32"
ACCENT_HOVER = "#86D51C"
HEADER_PATTERN = "#263A2E"
PATTERN = "#E7EEE9"
FONT_SMALL = ("Segoe UI", 9)
FONT_STRONG = ("Segoe UI Semibold", 10)
FONT_SECTION = ("Segoe UI Semibold", 12)
FONT_TITLE = ("Segoe UI Semibold", 19)
FONT_PACKAGE = ("Segoe UI Semibold", 14)
FONT_LOG = ("Consolas", 9)


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
        self.configure(bg=WHITE, padx=16, pady=14)
        self.result = None
        self.name = tk.StringVar(value=shop.get("name", ""))
        self.path = tk.StringVar(value=shop.get("bo_path", ""))
        self.vnc = tk.StringVar(value=shop.get("vnc_password", ""))

        def row(r, text, var, width=48, browse=False, hint=None):
            tk.Label(self, text=text, bg=WHITE, fg=DARK, font=FONT).grid(
                row=r, column=0, sticky="w", pady=4)
            e = ttk.Entry(self, textvariable=var, width=width)
            e.grid(row=r, column=1, sticky="we", padx=(8, 0))
            if browse:
                ttk.Button(self, text="Browse...", command=self._browse).grid(
                    row=r, column=2, padx=(6, 0))
            if hint:
                tk.Label(self, text=hint, bg=WHITE, fg=GREY,
                         font=FONT_SMALL, wraplength=420,
                         justify="left").grid(row=r + 1, column=1,
                                              columnspan=2, sticky="w")
            return e

        first = row(0, "Shop name", self.name)
        row(2, "Back-office folder", self.path, browse=True,
            hint="The folder with Ramset.dat and VectorTerminals.ini, e.g. "
                 "\\\\SERVER\\Ramset. The tills are read from that file.")
        row(4, "Till VNC password", self.vnc, width=16,
            hint=f"Leave blank to use the standard ({default_vnc}).")
        bar = tk.Frame(self, bg=WHITE)
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
    def __init__(self, initial=None, *, animate=True):
        super().__init__()
        self.title(f"{APP_TITLE} {VERSION}")
        self.geometry("1200x860")
        self.minsize(1000, 680)
        self.configure(bg=LIGHT)
        ico = _resource("app_icon.ico")
        if ico:
            try:
                self.iconbitmap(ico)
            except tk.TclError:
                pass

        self.cfg = store.load()
        self.scratch = store.scratch_dir()
        self.pkg = None
        self.loading = False
        self.download_session = None
        self.pending_downloads = []
        self.q = queue.Queue()
        self.busy = False
        self.cancel_flag = False
        self.tills = {}    # normalised bo_path -> [till dicts] or None (no INI)
        self.till_errors = {}
        self.status = {}   # row key -> (state, text)

        self._build()
        self._intro = None
        self._intro_after = None
        if animate:
            self._start_intro()
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
    def _theme(self):
        self.option_add("*Font", FONT)
        for name in ("TkDefaultFont", "TkTextFont", "TkHeadingFont"):
            tkfont.nametofont(name).configure(family=FONT[0], size=FONT[1])
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=FONT, background=WHITE, foreground=DARK)
        style.configure("TButton", padding=(10, 5), relief="flat",
                        background=LIGHT, bordercolor=BORDER, focuscolor=GREY)
        style.map("TButton", background=[("active", HOVER)],
                  foreground=[("disabled", DISABLED)])
        style.configure("Primary.TButton", background=GREEN, font=FONT_STRONG,
                        bordercolor=GREEN, padding=(14, 7))
        style.map("Primary.TButton", background=[("disabled", LIGHT), ("active", ACCENT_HOVER)],
                  foreground=[("disabled", DISABLED), ("!disabled", DARK)])
        style.configure("Action.TButton", font=FONT_STRONG, padding=(12, 7))
        style.configure("TEntry", padding=5, fieldbackground=WHITE,
                        bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
        style.configure("Treeview", background=WHITE, fieldbackground=WHITE,
                        font=FONT, rowheight=round(self.winfo_fpixels("0.36i")),
                        bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
        style.map("Treeview", background=[("selected", SELECT)],
                  foreground=[("selected", DARK)])
        style.configure("Treeview.Heading", font=FONT_STRONG, background=LIGHT,
                        foreground=GREY, padding=(10, 9), relief="flat")
        style.map("Treeview.Heading", background=[("active", HOVER)])
        style.configure("Horizontal.TProgressbar", background=GREEN,
                        troughcolor=LIGHT, bordercolor=LIGHT, thickness=5)
        style.configure("TScrollbar", background=BORDER, troughcolor=LIGHT,
                        bordercolor=LIGHT, arrowcolor=GREY, relief="flat")
        style.configure("TMenubutton", padding=(10, 5), background=LIGHT,
                        bordercolor=BORDER, relief="flat")
        self.check_images = self._checkbox_images()
        style.element_create("Koenekt.Check", "image", self.check_images["none"],
                             ("disabled", "selected", self.check_images["disabled_all"]),
                             ("disabled", "alternate", self.check_images["disabled_some"]),
                             ("disabled", self.check_images["disabled"]),
                             ("selected", self.check_images["all"]),
                             ("alternate", self.check_images["some"]))
        style.layout("TCheckbutton", [("Checkbutton.padding", {"sticky": "nswe", "children": [
            ("Koenekt.Check", {"side": "left", "sticky": ""}),
            ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [
                ("Checkbutton.label", {"sticky": "nswe"})]})]})])
        style.configure("TCheckbutton", padding=(0, 5, 8, 5))
        style.configure("TCheckbutton", background=LIGHT)
        style.map("TCheckbutton", background=[("active", LIGHT)],
                  foreground=[("disabled", DISABLED)])

    def _checkbox_images(self):
        """Rounded, antialiased controls with a continuous, font-free tick."""
        size = max(20, round(self.winfo_fpixels("1i") * 21 / 96))
        images = {}
        def rgb(color):
            return tuple(int(color[i:i+2], 16) for i in (1, 3, 5))

        def rounded(x, y, inset):
            radius = .20 - inset
            dx = max(inset + radius - x, 0, x - (1 - inset - radius))
            dy = max(inset + radius - y, 0, y - (1 - inset - radius))
            return (inset <= x <= 1-inset and inset <= y <= 1-inset
                    and dx*dx + dy*dy <= radius*radius)

        def segment(x, y, a, b):
            dx, dy = b[0]-a[0], b[1]-a[1]
            t = max(0, min(1, ((x-a[0])*dx + (y-a[1])*dy)/(dx*dx + dy*dy)))
            return (x-a[0]-t*dx)**2 + (y-a[1]-t*dy)**2 < .065**2

        for state in ("none", "some", "all", "disabled", "disabled_all", "disabled_some"):
            im = tk.PhotoImage(master=self, width=size + 10, height=size + 4)
            disabled = state.startswith("disabled")
            selected = state.endswith("all") or state.endswith("some")
            outline = rgb(BORDER if disabled else (GREEN if selected else GREY))
            fill = rgb(LIGHT if disabled else (GREEN if selected else WHITE))
            ink = rgb(DISABLED if disabled else DARK)
            paper = rgb(WHITE)
            rows = []
            for py in range(size):
                pixels = []
                for px in range(size):
                    samples = []
                    for sy in (.125, .375, .625, .875):
                        for sx in (.125, .375, .625, .875):
                            x, y = (px+sx)/size, (py+sy)/size
                            color = paper
                            if rounded(x, y, .04):
                                color = fill if rounded(x, y, .105) else outline
                            if state.endswith("all") and (
                                    segment(x, y, (.26, .51), (.43, .68)) or
                                    segment(x, y, (.43, .68), (.76, .32))):
                                color = ink
                            elif state.endswith("some") and segment(x, y, (.29, .50), (.71, .50)):
                                color = ink
                            samples.append(color)
                    pixels.append("#%02x%02x%02x" % tuple(round(sum(c[i] for c in samples)/16)
                                                           for i in range(3)))
                rows.append("{" + " ".join(pixels) + "}")
            im.put(" ".join(rows), to=(0, 2))
            images[state] = im
        return images

    def _brand_image(self, name):
        path = _resource("assets/" + name)
        if not path:
            return None
        try:
            # Assets are supplied at 2x; no imaging dependency in the EXE.
            return tk.PhotoImage(master=self, file=path).subsample(2)
        except tk.TclError:
            return None

    @staticmethod
    def _geometry_art(canvas, width, height, color):
        """Quiet hexagons and triangles inspired by the supplied theme."""
        canvas.delete("pattern")
        for col in range(5):
            for row in range(3):
                x = width - 25 - col*44
                y = 12 + row*49 + (24 if col % 2 else 0)
                canvas.create_polygon(x-26, y, x-13, y-22, x+13, y-22,
                                      x+26, y, x+13, y+22, x-13, y+22,
                                      fill="", outline=color, width=1, tags="pattern")
        canvas.create_polygon(width-235, height, width-210, height-44,
                              width-185, height, fill=color, outline="", tags="pattern")

    def _start_intro(self):
        path = _resource("assets/koenekt-fade.png")
        if not path:
            return
        try:
            strip = tk.PhotoImage(master=self, file=path)
            self._intro_frames = []
            for n in range(21):
                frame = tk.PhotoImage(master=self)
                self.tk.call(frame, "copy", strip, "-from", 0, n*340, 1320, (n+1)*340,
                             "-subsample", 2, 2)
                self._intro_frames.append(frame)
        except tk.TclError:
            return
        self._intro = tk.Canvas(self, bg=WHITE, highlightthickness=0)
        self._intro.place(x=0, y=0, relwidth=1, relheight=1)
        self._intro.bind("<Configure>", self._layout_intro)
        self._intro.bind("<Button-1>", self._dismiss_intro)
        self._intro_escape = self.bind("<Escape>", self._dismiss_intro, add="+")
        self._intro_started = time.monotonic()
        self._animate_intro()

    def _layout_intro(self, event):
        if not self._intro:
            return
        c = self._intro
        c.delete("layout")
        self._geometry_art(c, event.width, event.height, PATTERN)
        self._intro_logo = c.create_image(event.width/2, event.height/2-25,
                                          image=self._intro_frames[0], tags="layout")
        c.create_text(event.width/2, event.height/2+98, text="VECTOR-UP  by Koenekt",
                      fill=DARK, font=FONT_SECTION, tags="layout")
        c.create_text(event.width/2, event.height/2+127,
                      text="Vector upgrades, shop by shop", fill=GREY, font=FONT, tags="layout")
        c.create_text(event.width/2, event.height-40, text="Click or press Esc to continue",
                      fill=GREY, font=FONT_SMALL, tags="layout")

    def _animate_intro(self):
        self._intro_after = None
        if not self._intro:
            return
        elapsed = time.monotonic() - self._intro_started
        if elapsed >= 1.85:
            self._dismiss_intro()
            return
        opacity = min(1, elapsed/.45, (1.85-elapsed)/.55)
        opacity = max(0, opacity)
        opacity = opacity*opacity*(3-2*opacity)
        if hasattr(self, "_intro_logo"):
            self._intro.itemconfigure(self._intro_logo, image=self._intro_frames[round(opacity*20)])
        self._intro_after = self.after(25, self._animate_intro)

    def _dismiss_intro(self, _event=None):
        if self._intro_after:
            self.after_cancel(self._intro_after)
            self._intro_after = None
        if self._intro:
            self._intro.destroy()
            self._intro = None
            self.unbind("<Escape>", self._intro_escape)
        self._intro_frames = []

    def _build(self):
        self._theme()
        head = tk.Frame(self, bg=DARK)
        head.pack(fill="x")
        title = tk.Frame(head, bg=DARK)
        title.pack(side="left", padx=24, pady=12)
        tk.Label(title, text="VECTOR-UP  by Koenekt", bg=DARK, fg=WHITE,
                 font=FONT_TITLE).pack(anchor="w")
        tk.Label(title, text="Vector upgrades, shop by shop", bg=DARK,
                 fg=GREEN, font=FONT_SMALL).pack(anchor="w", pady=(3, 0))
        brand = tk.Canvas(head, bg=DARK, width=280, height=76, highlightthickness=0)
        brand.pack(side="right", padx=(0, 24))
        self._geometry_art(brand, 280, 84, HEADER_PATTERN)
        self.koenekt_logo = self._brand_image("koenekt-header.png")
        if self.koenekt_logo:
            brand.create_rectangle(82, 13, 280, 69, fill=WHITE, outline="")
            brand.create_image(181, 41, image=self.koenekt_logo)
        else:
            brand.create_text(185, 38, text="koenekt", fill=WHITE, font=FONT_TITLE)
        tk.Frame(self, bg=GREEN, height=3).pack(fill="x")
        self.body = tk.Frame(self, bg=LIGHT)
        self.body.pack(fill="both", expand=True, padx=24, pady=(12, 8))
        self.body.columnconfigure(0, weight=1)
        self.drop = tk.Frame(self.body, bg=WHITE, highlightthickness=1,
                             highlightbackground=BORDER)
        self.drop.grid(row=0, column=0, sticky="we")
        self.vector_logo = self._brand_image("vector.png")
        if self.vector_logo:
            tk.Label(self.drop, image=self.vector_logo, bg=WHITE).pack(
                side="right", padx=24, pady=16)
        package_content = tk.Frame(self.drop, bg=WHITE)
        package_content.pack(side="left", fill="both", expand=True, padx=20, pady=10)
        self.drop_title = tk.Label(package_content,
            text="Drop your Vector upgrade ZIP here", bg=WHITE, fg=DARK,
            font=FONT_PACKAGE)
        self.drop_title.pack(anchor="w", pady=(4, 3))
        self.drop_info = tk.Label(package_content, bg=WHITE, fg=GREY, font=FONT,
            justify="left", anchor="w", text="One package. Back-office and till files sorted for you.")
        self.drop_info.pack(anchor="w", fill="x")
        # Package names must not force the window wider than its minimum.
        package_content.bind("<Configure>", lambda e: self.drop_info.config(wraplength=max(100, e.width)))
        bar = tk.Frame(package_content, bg=WHITE)
        bar.pack(anchor="w", pady=(10, 0))
        self.package_btns = []
        for text, command, sty in (
                ("Get package", self._get_package, "Primary.TButton"),
                ("Browse ZIP", self._browse_zip, "TButton"),
                ("Browse folder", self._browse_folder, "TButton"),
                ("Clear", self._clear_pkg, "TButton")):
            button = ttk.Button(bar, text=text, command=command, style=sty)
            button.pack(side="left", padx=(0, 6))
            self.package_btns.append(button)
        heading = tk.Frame(self.body, bg=LIGHT)
        heading.grid(row=1, column=0, sticky="we", pady=(10, 6))
        tk.Label(heading, text="Back offices and tills", bg=LIGHT,
                 fg=DARK, font=FONT_SECTION).pack(side="left")
        self.count_lbl = tk.Label(heading, bg=LIGHT, fg=GREY, font=FONT_SMALL)
        self.count_lbl.pack(side="right")
        self.body.rowconfigure(2, weight=4, minsize=92)
        treef = tk.Frame(self.body, bg=WHITE)
        treef.grid(row=2, column=0, sticky="nsew")
        self.tree = ttk.Treeview(treef, columns=("status", "where"),
            show="tree headings", selectmode="browse", height=6)
        for column, title, width, stretch in (
                ("#0", "Shop / destination", 300, False),
                ("status", "Result", 180, False),
                ("where", "Folder", 450, True)):
            self.tree.heading(column, text=title, anchor="w")
            self.tree.column(column, width=width, minwidth=100, stretch=stretch)
        tsb = ttk.Scrollbar(treef, command=self.tree.yview)
        xsb = ttk.Scrollbar(treef, orient="horizontal", command=self.tree.xview)
        self.tree.config(yscrollcommand=tsb.set, xscrollcommand=xsb.set)
        xsb.pack(side="bottom", fill="x")
        tsb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("shop", font=FONT_STRONG, background=LIGHT)
        self.tree.tag_configure("unavailable", foreground=GREY)
        self.tree.tag_configure("ok", foreground=SUCCESS)
        self.tree.tag_configure("bad", foreground=RED)
        self.tree.bind("<Button-1>", self._tree_click)
        self.tree.bind("<space>", self._tree_space)
        self.tree.bind("<Double-1>", self._tree_double)
        self.tree.bind("<Button-3>", self._tree_menu)
        self.menu = tk.Menu(self, tearoff=0)
        shopbar = tk.Frame(self.body, bg=LIGHT)
        shopbar.grid(row=3, column=0, sticky="we", pady=(6, 8))
        for text, cmd in (("Add shop", self._add_shop), ("Edit", self._edit_shop),
                          ("Remove", self._remove_shop), ("Refresh tills", self._refresh_tills)):
            ttk.Button(shopbar, text=text, command=cmd).pack(side="left", padx=(0, 6))
        more = ttk.Menubutton(shopbar, text="More")
        menu = tk.Menu(more, tearoff=0)
        menu.add_command(label="Expand shops", command=lambda: self._expand(True))
        menu.add_command(label="Collapse shops", command=lambda: self._expand(False))
        menu.add_separator()
        menu.add_command(label="Import shops from Reporter", command=self._import)
        more.config(menu=menu)
        more.pack(side="right", padx=(6, 0))
        ttk.Button(shopbar, text="Tick none", command=lambda: self._tick_all(False)).pack(side="right", padx=6)
        ttk.Button(shopbar, text="Tick all", command=lambda: self._tick_all(True)).pack(side="right")
        acts = tk.Frame(self.body, bg=WHITE, padx=12, pady=8,
                        highlightbackground=BORDER, highlightthickness=1)
        acts.grid(row=4, column=0, sticky="we")
        self.btns = []
        for text, cmd, primary in (
                ("Upgrade ticked", lambda: self._upgrade("ticked"), True),
                ("Upgrade selected row", lambda: self._upgrade("row"), False),
                ("Upgrade ALL", lambda: self._upgrade("all"), False),
                ("Check destinations", self._check, False)):
            button = ttk.Button(acts, text=text, command=cmd,
                                style="Primary.TButton" if primary else "Action.TButton")
            button.pack(side="left", padx=(0, 8))
            self.btns.append(button)
        self.stop_btn = ttk.Button(acts, text="Stop", command=self._stop, state="disabled")
        self.stop_btn.pack(side="right")
        policy = tk.Frame(self.body, bg=LIGHT)
        policy.grid(row=5, column=0, sticky="we", pady=(6, 4))
        tk.Label(policy, text="Till data saved first: postrans.dat + posdebtor.dat",
                 bg=LIGHT, fg=GREY, font=FONT_SMALL).pack(side="left")
        ttk.Button(policy, text="Open POS backups", command=self._open_backups).pack(side="right")
        tk.Label(policy, text="Back-office backup: manual", bg=LIGHT,
                 fg=GREY, font=FONT_SMALL).pack(side="right", padx=14)
        opts = tk.Frame(self.body, bg=LIGHT)
        opts.grid(row=6, column=0, sticky="we", pady=(0, 6))
        vnc = ttk.Button(opts, text="VNC shortcuts", command=self._vnc)
        vnc.pack(side="left", padx=(0, 14))
        self.btns.append(vnc)
        tk.Label(opts, text="Till VNC password", bg=LIGHT, fg=GREY,
                 font=FONT_SMALL).pack(side="left")
        self.vnc_var = tk.StringVar(value=self.cfg["vnc_default"])
        entry = ttk.Entry(opts, textvariable=self.vnc_var, width=8)
        entry.pack(side="left", padx=(8, 16))
        entry.bind("<FocusOut>", lambda _e: self._save_cfg())
        self.group_var = tk.BooleanVar(value=self.cfg["group_shortcuts"])
        ttk.Checkbutton(opts, text="Group shortcuts in a Koenekt Tills folder",
            variable=self.group_var, command=self._save_cfg).pack(side="left")
        self.bar = ttk.Progressbar(self.body, maximum=100)
        self.bar.grid(row=7, column=0, sticky="we")
        self.body.rowconfigure(8, weight=1, minsize=64)
        logf = tk.Frame(self.body, bg=LIGHT)
        logf.grid(row=8, column=0, sticky="nsew", pady=(8, 0))
        tk.Label(logf, text="ACTIVITY", bg=LIGHT, fg=GREY,
                 font=FONT_SMALL).pack(anchor="w", pady=(0, 4))
        log_content = tk.Frame(logf, bg=WHITE)
        log_content.pack(fill="both", expand=True)
        self.log = tk.Text(log_content, height=2, wrap="word", bg=WHITE, fg=DARK,
            relief="flat", bd=0, padx=10, pady=4, font=FONT_LOG, state="disabled")
        sb = ttk.Scrollbar(log_content, command=self.log.yview)
        self.log.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True)
        footer = tk.Frame(self, bg=LIGHT)
        # Reserve the footer before the expanding body at small window sizes.
        footer.pack(side="bottom", fill="x", padx=24, pady=(0, 8), before=self.body)
        tk.Label(footer, text=f"FREE FOR EVERYONE  /  v{VERSION}", bg=LIGHT,
                 fg=GREY, font=FONT_SMALL).pack(side="right")
        self.status_lbl = tk.Label(footer, text="", bg=LIGHT, fg=GREY,
                                   anchor="w", font=FONT_SMALL)
        self.status_lbl.pack(side="left", fill="x", expand=True)
        self.operation_controls = []
        def collect(widget):
            for child in widget.winfo_children():
                if isinstance(child, (ttk.Button, ttk.Menubutton, ttk.Entry, ttk.Checkbutton)):
                    if child is not self.stop_btn:
                        self.operation_controls.append(child)
                collect(child)
        collect(self.body)

    def _open_backups(self):
        folder = store.pos_backup_dir()
        try:
            os.makedirs(folder, exist_ok=True)
            os.startfile(folder)
        except OSError as e:
            messagebox.showwarning(APP_TITLE, f"Could not open POS backups: {e}")

    # ------------------------------------------------------------ settings
    def _save_cfg(self):
        self.cfg["vnc_default"] = (self.vnc_var.get().strip()
                                   or store.DEFAULT_VNC)
        self.cfg["group_shortcuts"] = bool(self.group_var.get())
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
                         f"Terminal {t['number']}", t.get("share") or t.get("location") or ""))
        return rows

    def _till(self, i, sub):
        if sub == "bo":
            return None
        return next((t for t in self.tills.get(store._norm(self.cfg["shops"][i]["bo_path"])) or []
                     if sub == f"t{t['number']}"), None)

    def _selectable(self, i, sub):
        return sub == "bo" or bool((self._till(i, sub) or {}).get("share"))

    def _ticked(self, i, sub):
        return self._selectable(i, sub) and sub not in self.cfg["shops"][i].get("off", [])

    def _shop_state(self, i):
        kids = [k for k, _l, _p in self._children(i) if self._selectable(i, k)]
        on = sum(1 for k in kids if self._ticked(i, k))
        return "all" if on == len(kids) else ("none" if on == 0 else "some")

    def _fill_tree(self, keep=None):
        scroll = self.tree.yview()
        opened = {iid for iid in self.tree.get_children()
                  if self.tree.item(iid, "open")}
        first = not self.tree.get_children()
        self.tree.delete(*self.tree.get_children())
        for i, s in enumerate(self.cfg["shops"]):
            sid = f"s{i}"
            self.tree.insert(
                "", "end", iid=sid, open=first or sid in opened,
                text=s["name"], tags=("shop",),
                image=self.check_images[self._shop_state(i)],
                values=("", s["bo_path"]))
            for sub, label, folder in self._children(i):
                self._insert_row(i, sub, label, folder)
            self._shop_status(i)
        if keep and self.tree.exists(keep):
            self.tree.selection_set(keep)
            self.tree.focus(keep)
        if scroll:
            self.tree.yview_moveto(scroll[0])
        n = sum(1 for i in range(len(self.cfg["shops"]))
                if self._shop_state(i) != "none")
        targets = sum(self._ticked(i, k) for i in range(len(self.cfg["shops"]))
                      for k, _label, _path in self._children(i))
        self.count_lbl.config(text=f"{n} / {len(self.cfg['shops'])} shops  ·  {targets} destinations ticked")

    def _insert_row(self, i, sub, label, folder):
        key = f"{i}:{sub}"
        state, text = self.status.get(key, ("", ""))
        if not state:
            text = ((self._till(i, sub) or {}).get("problem") or "")
            if sub == "bo":
                text = self.till_errors.get(store._norm(self.cfg["shops"][i]["bo_path"]), "")
        tag = ("ok",) if state == "ok" else (("bad",) if state else ())
        if not self._selectable(i, sub):
            tag = ("unavailable",)
        glyph = {"ok": "✔ ", "partial": "✖ ", "unreachable": "✖ "}.get(state, "")
        self.tree.insert(
            f"s{i}", "end", iid=key, text=label, tags=tag,
            image=self.check_images[("all" if self._ticked(i, sub) else "none")
                                    if self._selectable(i, sub) else "disabled"],
            values=(glyph + text, folder))

    def _shop_status(self, i):
        kids = [(k, l, p) for k, l, p in self._children(i) if self._selectable(i, k)]
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
        if "image" not in self.tree.identify_element(event.x, event.y):
            return
        iid = self.tree.identify_row(event.y)
        if iid:
            return self._toggle_tick(iid)

    def _tree_space(self, _event):
        iid = self._selected_key()
        if iid:
            return self._toggle_tick(iid)

    def _toggle_tick(self, iid):
        if self.busy or self.loading:
            return "break"
        if iid.startswith("s"):
            i = int(iid[1:])
            kids = [k for k, _l, _p in self._children(i)]
            turn_on = self._shop_state(i) != "all"
            self.cfg["shops"][i]["off"] = [] if turn_on else kids
        else:
            i, sub = iid.split(":")
            i = int(i)
            if not self._selectable(i, sub):
                return "break"
            off = set(self.cfg["shops"][i].get("off", []))
            off.symmetric_difference_update({sub})
            self.cfg["shops"][i]["off"] = sorted(off)
        self._save_cfg()
        self._fill_tree(keep=iid)
        self.tree.focus_set()
        return "break"

    def _tree_double(self, event):
        iid = self.tree.identify_row(event.y)
        if iid and iid.startswith("s") and \
                "image" not in self.tree.identify_element(event.x, event.y):
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
        if self.busy or self.loading:
            return
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
        if self.busy or self.loading:
            return
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
            tills = tillops.tills_for_display(info) if info.get("available") \
                else None
            error = info.get("error") or ""
            self.q.put(("tills", key, tills, error))
            if error:
                self.q.put(("log", f"{s['name']}: {error}"))
            else:
                usable = sum(1 for t in tills or [] if t.get("share"))
                self.q.put(("log", f"{s['name']}: {len(tills or [])} configured till(s), "
                            f"{usable} with a usable folder."))

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
        if self.busy or self.loading:
            return self._log("Busy - wait for the current operation to finish.")
        if len(paths) > 1:
            self._log(f"{len(paths)} items dropped - using the first "
                      f"({os.path.basename(paths[0])}).")
        self._load_package(paths[0])

    def _load_package(self, path):
        if self.busy or self.loading:
            return
        self.loading = True
        self._set_busy(False)
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

    def _get_package(self):
        if self.busy or self.loading:
            return
        if self.download_session:
            if self.download_session.active:
                self._log("The Vector download browser is already open. Choose the ZIP there.")
                return
            # Keep completed downloads available while pending imports finish.
            if self.pending_downloads:
                return
            self.download_session.close()
        session = downloads.DownloadSession(lambda *m: self.q.put(m))
        try:
            session.start()
        except OSError as e:
            messagebox.showwarning(APP_TITLE, str(e))
            return
        self.download_session = session
        self._log("Vector download browser opened. Log in, then choose the upgrade ZIP.")
        self.status_lbl.config(text="Waiting for your Vector download...")

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
        if self.busy or self.loading:
            return
        self.pkg = None
        self._show_package()

    def _show_package(self):
        if not self.pkg:
            self.drop_title.config(
                text="Drop your Vector upgrade ZIP here", fg=DARK)
            self.drop_info.config(
                text="One package. Back-office and till files sorted for you.", fg=GREY)
            self.drop.config(highlightbackground=BORDER)
            return
        self.drop_title.config(text="Package ready to copy", fg=DARK)
        labels = [f"{title}: {payload.label() if payload else 'not included'}"
                  for title, payload in (("Back office", self.pkg.bo), ("POS", self.pkg.pos))]
        self.drop_info.config(text="   |   ".join(labels), fg=DARK)
        self.drop.config(highlightbackground=DARK)

    # -------------------------------------------------------------- running
    def _selection(self, mode):
        """Shops (copies) carrying want_bo / want_tills for the run."""
        out = []
        sel = self._selected_key()
        for i, s in enumerate(self.cfg["shops"]):
            d = dict(s, _idx=i, want_bo=True, want_tills=None)
            known = {t["number"] for t in
                     (self.tills.get(store._norm(s["bo_path"])) or []) if t.get("share")}
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
                    if not self._selectable(i, sub):
                        continue
                    d["want_tills"] = {int(sub[1:])} if sub != "bo" else set()
            if d["want_bo"] or d["want_tills"] is None or d["want_tills"]:
                out.append(d)
        return out

    def _ready(self, mode):
        if self.busy or self.loading:
            return None
        if mode == "row" and not self._selected_key():
            messagebox.showinfo(APP_TITLE, "Click a till, a back office or a "
                                           "shop in the list first.")
            return None
        if mode == "row" and ":" in self._selected_key():
            i, sub = self._selected_key().split(":")
            if not self._selectable(int(i), sub):
                messagebox.showinfo(APP_TITLE, "This till has no usable copy folder. "
                                   "Check its TerminalLocation in VectorTerminals.ini. "
                                   "For a remote shop, use a UNC network share.")
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
        for b in self.operation_controls:
            b.config(state="disabled" if busy or self.loading else "normal")
        self.stop_btn.config(state="normal" if busy else "disabled")

    def _count(self, shops):
        bo = sum(1 for s in shops if s["want_bo"] and self.pkg.bo)
        tills = 0
        if self.pkg.pos:
            for s in shops:
                known = [t for t in self.tills.get(store._norm(s["bo_path"])) or [] if t.get("share")]
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
                "\n\nTills: postrans.dat and posdebtor.dat are saved first "
                "in your local POS backups folder. A failed backup skips that till."
                "\nBack offices: make your manual backup before continuing."):
            return
        self._set_busy(True)
        self.cancel_flag = False
        self.bar["value"] = 0
        pkg, backup_root = self.pkg, store.pos_backup_dir()
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
                backup_root=backup_root)
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
        # Keep the newest message visible even when only one line fits.
        self.log.see("end-2c")
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
                    self.till_errors[m[1]] = m[3]
                elif kind == "tills_done":
                    self._fill_tree(keep=self._selected_key())
                elif kind == "download":
                    self.pending_downloads.append(m[1])
                    self._log("Download complete: " + os.path.basename(m[1]))
                elif kind == "browser_closed":
                    self._log("Download browser closed.")
                elif kind == "package":
                    _k, pkg, err = m
                    self.loading = False
                    self._set_busy(False)
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
        if self.pending_downloads and not (self.busy or self.loading):
            self._load_package(self.pending_downloads.pop(0))
        self.after(100, self._pump)

    def _close(self):
        if self.busy and not messagebox.askyesno(
                APP_TITLE, "A copy is still running. Quit anyway?"):
            return
        self._save_cfg()
        if self.download_session:
            self.download_session.close()
        self._dismiss_intro()
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
