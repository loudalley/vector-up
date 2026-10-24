"""The tool's own shop list. One JSON file per Windows user.

A shop here is only what an upgrade needs: a name, the back-office folder
(the one holding Ramset.dat and VectorTerminals.ini - the till list is read
from that INI, never typed in) and, if the shop differs from the standard, its
own till VNC password.

COMPATIBILITY WITH 1.4.x. The original 1.4.x rebuilds every shop from a fixed
set of keys each time it loads and saves, so any extra key written into
shops.json is silently deleted the next time 1.4.x runs on the same folder.
Extra back offices (1.5) therefore live in a companion file,
shops_extra.json, keyed by the shop's back-office folder, which 1.4.x never
reads or writes. shops.json keeps exactly the 1.4.x shape, so the two versions
can share one settings folder: they see the same shops, and 1.4.x cannot erase
what only 1.5 knows about. Keep it that way: never put a key into shops.json
that 1.4.x would drop.
"""
import atexit
import json
import os
import re
import shutil
import sys
import tempfile

from . import tillops

DEFAULT_VNC = tillops.VNC_PASSWORD
MAX_SHOPS = 50  # the field has 20; this only stops a runaway import
MAX_EXTRA_BO = 20  # extra back offices per shop


PORTABLE_FOLDER = "VectorUp_data"


def _writable(d):
    try:
        os.makedirs(d, exist_ok=True)
        probe = os.path.join(d, ".wtest")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False


def _appdata_dir():
    la = os.environ.get("LOCALAPPDATA") or os.path.join(
        os.path.expanduser("~"), "AppData", "Local")
    return os.path.join(la, "Koenekt", "VectorUp")


def portable_dir():
    """Settings folder beside the exe, or None when not running as an exe.

    The tool is carried from PC to PC, so its settings travel with it: copy
    the exe together with this folder. Only used when that spot is writable
    (not on a read-only stick or under Program Files).
    """
    if not getattr(sys, "frozen", False):
        return None
    d = os.path.join(os.path.dirname(os.path.abspath(sys.executable)),
                     PORTABLE_FOLDER)
    return d if _writable(d) else None


def data_dir():
    """Where the shop list and log live: beside the exe, else per-user."""
    p = portable_dir()
    if p:
        legacy = os.path.join(_appdata_dir(), "shops.json")
        mine = os.path.join(p, "shops.json")
        if not os.path.exists(mine) and os.path.isfile(legacy):
            try:  # first portable run: bring the MSI version's shops along
                shutil.copy2(legacy, mine)
            except OSError:
                pass
        return p
    for d in (_appdata_dir(),
              os.path.join(os.path.expanduser("~"), ".vectorup")):
        if _writable(d):
            return d
    d = os.path.join(tempfile.gettempdir(), "Koenekt", "VectorUp")
    os.makedirs(d, exist_ok=True)
    return d


def scratch_dir():
    """A fresh per-run folder in %TEMP% for staging dropped files.

    Dropped packages can be hundreds of MB; they belong on the local disk, not
    on the stick the tool runs from. Removed again when the window closes.
    """
    d = tempfile.mkdtemp(prefix="vectorup-")
    atexit.register(shutil.rmtree, d, True)
    return d


def pos_backup_dir():
    """Durable local backups; never store live till data in staging temp."""
    return os.path.join(data_dir(), "POS backups")


def _path(path=None):
    return path or os.path.join(data_dir(), "shops.json")


def _clean_extras(raw):
    """Valid extra back offices only: [{"id": int, "name": str, "path": str}]."""
    out, seen = [], set()
    for x in raw or []:
        if not isinstance(x, dict):
            continue
        path = str(x.get("path") or "").strip()
        try:
            xid = int(x.get("id"))
        except (TypeError, ValueError):
            continue
        if not path or xid in seen:
            continue
        seen.add(xid)
        out.append({"id": xid, "name": str(x.get("name") or "").strip() or path,
                    "path": path})
    return out


def new_shop(name="", bo_path="", vnc_password="", selected=True, off=None,
             extra_bo=None, extra_seq=0):
    """off: destinations the technician has unticked, e.g. ["bo", "t3", "b2"].

    extra_bo: further back offices of the same shop (a second, third, ...
    RP_BACK program folder), each with a stable id. extra_seq only ever grows,
    so a removed id is never handed out again - a stale untick or result keyed
    on it can never land on a different back office.
    """
    extras = _clean_extras(extra_bo)
    seq = max([int(extra_seq or 0)] + [x["id"] for x in extras])
    return {"name": name.strip(), "bo_path": bo_path.strip(),
            "vnc_password": vnc_password.strip(), "selected": bool(selected),
            "off": [str(k) for k in (off or [])],
            "extra_bo": extras, "extra_seq": seq}


# Row keys inside a shop: "bo" main back office, "t<n>" till n,
# "b<id>" an extra back office.
def extra_key(extra_id):
    return f"b{int(extra_id)}"


def is_extra_key(sub):
    return len(sub) > 1 and sub[0] == "b" and sub[1:].isdigit()


def extra_id(sub):
    return int(sub[1:])


def find_extra(shop, extra_id_):
    return next((x for x in shop.get("extra_bo") or []
                 if x["id"] == int(extra_id_)), None)


def add_extra_bo(shop, name, path):
    """Add a back office to a shop. Raises ValueError with a message to show."""
    path = (path or "").strip()
    if not path:
        raise ValueError("Enter the back-office folder.")
    if len(shop.get("extra_bo") or []) >= MAX_EXTRA_BO:
        raise ValueError(f"That is the limit of {MAX_EXTRA_BO} extra back "
                         f"offices for one shop.")
    _check_extra_duplicate(shop, path, None)
    shop.setdefault("extra_bo", [])
    shop["extra_seq"] = max(int(shop.get("extra_seq") or 0),
                            *[x["id"] for x in shop["extra_bo"]], 0) + 1
    extra = {"id": shop["extra_seq"], "name": (name or "").strip() or path,
             "path": path}
    shop["extra_bo"].append(extra)
    return extra


def update_extra_bo(shop, extra_id_, name, path):
    path = (path or "").strip()
    x = find_extra(shop, extra_id_)
    if x is None:
        raise ValueError("That back office no longer exists.")
    if not path:
        raise ValueError("Enter the back-office folder.")
    _check_extra_duplicate(shop, path, x["id"])
    x["name"] = (name or "").strip() or path
    x["path"] = path
    return x


def remove_extra_bo(shop, extra_id_):
    """Remove it from the list (nothing on the PC is touched) and forget its tick."""
    shop["extra_bo"] = [x for x in shop.get("extra_bo") or []
                        if x["id"] != int(extra_id_)]
    shop["off"] = [k for k in shop.get("off") or []
                   if k != extra_key(extra_id_)]


def _check_extra_duplicate(shop, path, own_id):
    if _norm(path) == _norm(shop.get("bo_path")):
        raise ValueError("That is this shop's main back-office folder.")
    for x in shop.get("extra_bo") or []:
        if x["id"] != own_id and _norm(x["path"]) == _norm(path):
            raise ValueError(f"Already listed as \"{x['name']}\".")


def _extra_path(p):
    """Companion file for extra back offices: shops.json -> shops_extra.json."""
    return os.path.splitext(p)[0] + "_extra.json"


def _read_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:  # Notepad adds a BOM
        return json.load(f)


def _read_extras(p):
    """{normalised back-office folder: {"extra_bo": [...], "extra_seq": n}}."""
    try:
        raw = _read_json(_extra_path(p))
    except (OSError, ValueError):
        return {}
    shops = raw.get("shops") if isinstance(raw, dict) else None
    return shops if isinstance(shops, dict) else {}


def _merge_extras(shop, side):
    """Attach a companion-file entry to a shop; it wins over anything inline."""
    if not isinstance(side, dict):
        return
    extras = _clean_extras(side.get("extra_bo"))
    try:
        seq = int(side.get("extra_seq") or 0)
    except (TypeError, ValueError):
        seq = 0
    shop["extra_bo"] = extras
    shop["extra_seq"] = max([seq, shop.get("extra_seq", 0)]
                            + [x["id"] for x in extras])


def load(path=None):
    cfg = {"shops": [], "vnc_default": DEFAULT_VNC, "group_shortcuts": True}
    p = _path(path)
    try:
        raw = _read_json(p)
    except (OSError, ValueError):
        return cfg
    if isinstance(raw, dict):
        cfg["vnc_default"] = str(raw.get("vnc_default") or DEFAULT_VNC)
        cfg["group_shortcuts"] = bool(raw.get("group_shortcuts", True))
        for s in raw.get("shops") or []:
            if isinstance(s, dict):
                cfg["shops"].append(new_shop(
                    str(s.get("name") or ""), str(s.get("bo_path") or ""),
                    str(s.get("vnc_password") or ""),
                    s.get("selected", True), s.get("off"),
                    s.get("extra_bo"), s.get("extra_seq", 0)))
    # Extras from the companion file. (An inline extra_bo in shops.json can
    # only come from an early 1.5 development build; it still loads, and the
    # next save moves it to the companion file.)
    side = _read_extras(p)
    for shop in cfg["shops"]:
        if shop["bo_path"]:
            _merge_extras(shop, side.get(_norm(shop["bo_path"])))
    return cfg


def _write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def save(cfg, path=None):
    """Write shops.json in the 1.4.x shape and the extras to shops_extra.json."""
    p = _path(path)
    side, plain = {}, []
    for s in cfg.get("shops", []):
        plain.append({k: v for k, v in s.items()
                      if k not in ("extra_bo", "extra_seq")})
        if (s.get("extra_bo") or s.get("extra_seq")) and s.get("bo_path"):
            side[_norm(s["bo_path"])] = {
                "shop": s.get("name", ""),  # for a human reading the file
                "extra_bo": s.get("extra_bo") or [],
                "extra_seq": s.get("extra_seq", 0)}
    ep = _extra_path(p)
    if side or os.path.exists(ep):
        if os.path.exists(ep):
            try:
                _read_json(ep)
            except (OSError, ValueError):  # keep a damaged file, do not erase it
                try:
                    shutil.copy2(ep, ep + ".bad")
                except OSError:
                    pass
        _write_json(ep, {"version": 1, "shops": side})
    _write_json(p, dict(cfg, shops=plain))
    return p


def vnc_password_for(cfg, shop):
    """The shop's own password, else the tool-wide one, else the standard."""
    return ((shop.get("vnc_password") or "").strip()
            or (cfg.get("vnc_default") or "").strip() or DEFAULT_VNC)


def _norm(p):
    """A comparison key for a folder path: same folder, same key.

    normpath keeps a trailing backslash on a UNC share root (\\\\pc\\share\\)
    but not on \\\\pc\\share, so strip it or the same folder typed two ways
    would look like two folders.
    """
    return os.path.normpath((p or "").strip()).lower().rstrip("\\/")


def reporter_config_paths():
    """Where an installed Reporter keeps its config.json (read-only here)."""
    out = []
    pd = os.environ.get("PROGRAMDATA")
    if pd:
        out.append(os.path.join(pd, "Koenekt", "DailyReport", "config.json"))
    la = os.environ.get("LOCALAPPDATA") or os.path.join(
        os.path.expanduser("~"), "AppData", "Local")
    out.append(os.path.join(la, "Koenekt", "DailyReport", "config.json"))
    out.append(os.path.join(os.path.expanduser("~"), ".koenekt-dailyreport",
                            "config.json"))
    return out


def import_from_reporter(cfg, paths=None):
    """Add the shops an installed Reporter already knows. Never writes to it.

    Shops whose back-office folder is already listed are left alone. Returns
    (added, skipped, source_path_or_None).
    """
    for p in paths or reporter_config_paths():
        if not os.path.isfile(p):
            continue
        try:
            with open(p, "r", encoding="utf-8-sig") as f:
                rep = json.load(f)
        except (OSError, ValueError):
            continue
        shops = rep.get("shops") or []
        if not shops and (rep.get("data_path") or rep.get("shop_name")):
            shops = [{"shop_name": rep.get("shop_name"),
                      "data_path": rep.get("data_path")}]
        have = {_norm(s["bo_path"]) for s in cfg["shops"]}
        added = skipped = 0
        for s in shops:
            path = str(s.get("data_path") or "").strip()
            name = str(s.get("shop_name") or "").strip() or path
            if not path or _norm(path) in have or \
                    len(cfg["shops"]) >= MAX_SHOPS:
                skipped += 1
                continue
            cfg["shops"].append(new_shop(name, path))
            have.add(_norm(path))
            added += 1
        vnc = str(rep.get("vnc_password") or "").strip()
        if vnc and cfg.get("vnc_default") == DEFAULT_VNC:
            cfg["vnc_default"] = vnc
        return added, skipped, p
    return 0, 0, None


def is_drive_path(path):
    """A drive-letter path (C:\\..., Z:\\...) as opposed to a UNC share."""
    return bool(re.match(r"^[A-Za-z]:[\\/]", (path or "").strip()))
