"""Find back-office program folders on the network. Read-only, no Tk.

Two different things turn up, and they need different handling:

* ANOTHER SHOP: a folder holding RP_BACK.exe AND its own Ramset.dat. Its
  working folder is its data folder (like a main server). Several can sit on
  one machine, named anything ("Liquor", "Retail Liq"). Add it as a new shop.
* A SECONDARY back office: a folder holding RP_BACK.exe but NO Ramset.dat,
  whose VectorAdminLocal.ini says AdminDataDirectory = some other shop's data
  folder. It needs the upgrade files in its own folder every time. Add it as an
  extra back office of the shop whose data it points at.

Folder names mean nothing here: RP_BACK.exe is the marker, and the ini is what
ties a secondary to its shop.

Scanning only ever LISTS folders and reads two small text files. It never
writes to a scanned machine. Looking beyond the shop's own server (the subnet
sweep) is a separate, explicit step.
"""
import configparser
import ctypes
import os
import re
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from . import store

EXE = "rp_back.exe"
DATA = "ramset.dat"
LOCAL_INI = "vectoradminlocal.ini"

# Folders that cannot be a program folder, or are too big/slow to walk.
SKIP_DIRS = {"logs", "log", "backup", "backups", "pos_data_preparation",
             "$recycle.bin", "system volume information", "windows",
             "program files", "program files (x86)", "programdata", "users",
             "node_modules", "temp", "tmp"}

OWN, SECONDARY, UNCLEAR, LISTED = "own", "secondary", "unclear", "listed"


def parse_unc(path):
    """(host, share, rest) for \\\\host\\share[\\rest], else None."""
    s = (path or "").strip().replace("/", "\\")
    if not s.startswith("\\\\"):
        return None
    parts = [p for p in s[2:].split("\\") if p]
    if len(parts) < 2:
        return None
    return parts[0], parts[1], "\\".join(parts[2:])


def unc(host, share, rest=""):
    return "\\\\" + "\\".join(p for p in (host, share, rest) if p)


# ---------------------------------------------------------------- shares
def list_disk_shares(host):
    """Names of the disk shares a Windows machine offers (NetShareEnum).

    Level 1 needs no admin rights, only a session the user already has (they
    reach the shop's server, so they have one). Administrative shares (C$ ...)
    are left out. Raises OSError with a readable message.
    """
    if sys.platform != "win32":
        raise OSError("Listing network shares needs Windows.")

    class SHARE_INFO_1(ctypes.Structure):
        _fields_ = [("name", ctypes.c_wchar_p), ("type", ctypes.c_uint32),
                    ("remark", ctypes.c_wchar_p)]

    netapi = ctypes.WinDLL("netapi32")
    netapi.NetShareEnum.argtypes = [
        ctypes.c_wchar_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32)]
    netapi.NetShareEnum.restype = ctypes.c_uint32
    netapi.NetApiBufferFree.argtypes = [ctypes.c_void_p]
    buf = ctypes.c_void_p()
    read, total, resume = (ctypes.c_uint32(), ctypes.c_uint32(),
                           ctypes.c_uint32())
    rc = netapi.NetShareEnum("\\\\" + host.lstrip("\\"), 1, ctypes.byref(buf),
                             0xFFFFFFFF, ctypes.byref(read),
                             ctypes.byref(total), ctypes.byref(resume))
    if rc not in (0, 234):  # 234 = more data; we asked for all, take what came
        raise OSError({5: "access denied", 53: "network path not found",
                       1219: "conflicting credentials",
                       1231: "network unreachable"}.get(
                           rc, f"error {rc}") + f" listing shares on {host}")
    names = []
    try:
        base = buf.value
        size = ctypes.sizeof(SHARE_INFO_1)
        for i in range(read.value):
            info = SHARE_INFO_1.from_address(base + i * size)
            kind = info.type & 0xFF
            special = bool(info.type & 0x80000000)
            if kind == 0 and not special and info.name:  # STYPE_DISKTREE
                names.append(info.name)
    finally:
        if buf.value:
            netapi.NetApiBufferFree(buf)
    return sorted(names, key=str.lower)


# ---------------------------------------------------------------- folders
def _listing(folder):
    """{lowercase name: (real name, is_dir)} or None if unreadable."""
    try:
        with os.scandir(folder) as it:
            return {e.name.lower(): (e.name, _is_dir(e)) for e in it}
    except OSError:
        return None


def _is_dir(entry):
    try:
        return entry.is_dir()
    except OSError:
        return False


def find_program_folders(root, max_depth=2, deadline=None, cancel=None,
                         listing=_listing):
    """Folders at or under root (to max_depth) that hold RP_BACK.exe.

    deadline is a time.monotonic() value after which the walk stops, so one
    huge or sluggish share cannot hold the scan up. Returns (folders, complete)
    where complete is False if it stopped early.
    """
    found, complete = [], True
    stack = [(root, 0)]
    while stack:
        if cancel and cancel():
            return found, False
        if deadline is not None and time.monotonic() > deadline:
            return found, False
        folder, depth = stack.pop()
        entries = listing(folder)
        if entries is None:
            continue
        if EXE in entries and not entries[EXE][1]:
            found.append(folder)
        if depth >= max_depth:
            continue
        for low, (real, is_dir) in sorted(entries.items(), reverse=True):
            if is_dir and low not in SKIP_DIRS and not low.endswith("$"):
                stack.append((os.path.join(folder, real), depth + 1))
    return sorted(found, key=str.lower), complete


def read_admin_data_dir(folder):
    """AdminDataDirectory from the folder's VectorAdminLocal.ini, or ''."""
    entries = _listing(folder) or {}
    if LOCAL_INI not in entries:
        return ""
    path = os.path.join(folder, entries[LOCAL_INI][0])
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str.lower
    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                cp.read_file(f)
            break
        except UnicodeDecodeError:
            cp = configparser.ConfigParser(interpolation=None, strict=False)
            cp.optionxform = str.lower
        except (OSError, configparser.Error):
            return ""
    for section in cp.sections():
        if cp.has_option(section, "admindatadirectory"):
            return cp.get(section, "admindatadirectory").strip().strip('"')
    return ""


# ---------------------------------------------------------- classification
def classify(folder, cfg_shops, start_shop=None, read_ini=read_admin_data_dir,
             has_data=None):
    """What a found program folder is, relative to the shops already listed.

    Returns {kind, shop_index, note}. kind is one of
      listed     already in the list (main folder or an extra back office)
      own        has its own Ramset.dat: another shop
      secondary  points at a listed shop's data folder: that shop's extra
      unclear    points somewhere we cannot match
    """
    norm = store._norm(folder)
    for i, s in enumerate(cfg_shops):
        if store._norm(s.get("bo_path")) == norm:
            return {"kind": LISTED, "shop_index": i,
                    "note": f"already listed as {s['name']}"}
        for x in s.get("extra_bo") or []:
            if store._norm(x["path"]) == norm:
                return {"kind": LISTED, "shop_index": i,
                        "note": f"already listed under {s['name']}"}
    if has_data is None:
        has_data = DATA in (_listing(folder) or {})
    if has_data:
        return {"kind": OWN, "shop_index": None,
                "note": "has its own Ramset.dat - another shop"}
    data_dir = read_ini(folder)
    if not data_dir:
        return {"kind": UNCLEAR, "shop_index": start_shop,
                "note": "no Ramset.dat or VectorAdminLocal.ini - cannot tell "
                        "whose"}
    want = store._norm(data_dir)
    for i, s in enumerate(cfg_shops):
        if store._norm(s.get("bo_path")) == want:
            return {"kind": SECONDARY, "shop_index": i,
                    "note": f"uses {s['name']}'s data ({data_dir})"}
    if store.is_drive_path(data_dir):
        return {"kind": UNCLEAR, "shop_index": start_shop,
                "note": f"data is {data_dir}, a drive letter on that PC - "
                        f"no match"}
    return {"kind": UNCLEAR, "shop_index": start_shop,
            "note": f"uses {data_dir}, not a listed shop"}


# ----------------------------------------------------------------- hosts
def scan_host(host, cfg_shops, start_shop=None, seconds=25, cancel=None,
              shares=list_disk_shares, walk=find_program_folders,
              classify_fn=classify):
    """Every program folder on one machine, classified.

    Returns {host, shares, found: [candidate...], error, complete}.
    """
    out = {"host": host, "shares": [], "found": [], "error": "",
           "complete": True}
    try:
        out["shares"] = shares(host)
    except OSError as e:
        out["error"] = str(e)
        return out
    deadline = time.monotonic() + seconds
    for share in out["shares"]:
        if cancel and cancel():
            out["complete"] = False
            break
        folders, complete = walk(unc(host, share), 2, deadline, cancel)
        out["complete"] = out["complete"] and complete
        for folder in folders:
            c = classify_fn(folder, cfg_shops, start_shop)
            c.update({"path": folder, "host": host,
                      "name": os.path.basename(folder.rstrip("\\/")) or share})
            out["found"].append(c)
    return out


def _ipv4(host):
    try:
        return socket.gethostbyname(host)
    except OSError:
        return ""


def sweep_subnet(ip, skip=(), port=445, timeout=0.4, workers=64, cancel=None,
                 connect=None):
    """Addresses in ip's /24 that answer on the SMB port, excluding skip.

    A single plain TCP connect each; nothing is sent. Sorted numerically.
    """
    m = re.match(r"^(\d+\.\d+\.\d+)\.\d+$", ip or "")
    if not m:
        return []
    base = m.group(1)
    skip = set(skip) | {ip}

    def probe(n):
        addr = f"{base}.{n}"
        if addr in skip or (cancel and cancel()):
            return None
        try:
            if connect:
                return addr if connect(addr, port, timeout) else None
            with socket.create_connection((addr, port), timeout=timeout):
                return addr
        except OSError:
            return None

    with ThreadPoolExecutor(max_workers=workers) as ex:
        hits = [a for a in ex.map(probe, range(1, 255)) if a]
    return sorted(hits, key=lambda a: int(a.rsplit(".", 1)[1]))


def discover(cfg_shops, start_shop, network=False, cancel=None, emit=None,
             scan=scan_host, sweep=sweep_subnet, resolve=_ipv4):
    """Scan the start shop's server (and, if asked, the rest of its subnet).

    Returns {"candidates": [...], "hosts": [...], "notes": [...]}. Candidates
    are classified against cfg_shops. Nothing is changed anywhere.
    """
    emit = emit or (lambda *a: None)
    shop = cfg_shops[start_shop]
    out = {"candidates": [], "hosts": [], "notes": []}
    parsed = parse_unc(shop.get("bo_path"))
    if not parsed:
        out["notes"].append(
            "This shop's back-office folder is a local path, so there is no "
            "server to look at from here. Add its other back offices by hand, "
            "or run the tool from a PC that reaches the server over the network.")
        return out
    server = parsed[0]
    seen = set()

    def run(host, label):
        emit("status", f"Looking at {label}...")
        r = scan(host, cfg_shops, start_shop, cancel=cancel)
        out["hosts"].append({k: r[k] for k in
                             ("host", "shares", "error", "complete")})
        if r["error"]:
            out["notes"].append(f"{label}: {r['error']}")
        elif not r["complete"]:
            out["notes"].append(f"{label}: stopped early (slow or cancelled) - "
                                f"some folders were not looked at.")
        for c in r["found"]:
            key = store._norm(c["path"])
            if key not in seen:
                seen.add(key)
                out["candidates"].append(c)

    run(server, server)
    if network and not (cancel and cancel()):
        ip = resolve(server)
        if not ip:
            out["notes"].append(f"Could not work out {server}'s address, so "
                                f"the rest of the network was not scanned.")
        else:
            emit("status", f"Checking {ip.rsplit('.', 1)[0]}.x for PCs that "
                           f"share files...")
            hosts = sweep(ip, skip={ip}, cancel=cancel)
            out["notes"].append(f"{len(hosts)} other PC(s) answered on "
                                f"{ip.rsplit('.', 1)[0]}.x.")
            for h in hosts:
                if cancel and cancel():
                    break
                run(h, h)
    return out
