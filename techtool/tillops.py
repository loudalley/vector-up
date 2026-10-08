"""Till helpers shared with the Koenekt Reporter's upgrade feature.

Vendored from koenekt-daily-report `app/tillops.py` (the parts this tool uses:
VNC shortcuts, the till list, the file-skip rules and the safe zip extractor).
The Reporter's web/FTP upgrade-source code is deliberately not carried over.
If a rule here changes in the Reporter, change it here too.
"""
import os
import re
import shutil
import subprocess
import sys

from . import terminals as vector_terminals

# The standard till VNC password. Every shop's tills are set to this, which is
# deliberate: one password across the estate is what makes remote support
# workable. A shop that differs gets its own in the shop's settings.
VNC_PASSWORD = "1234"

# Shop UltraVNC / TightVNC installs. First match wins.
_VIEWER_CANDIDATES = (
    r"C:\Program Files\uvnc bvba\UltraVNC\vncviewer.exe",
    r"C:\Program Files (x86)\uvnc bvba\UltraVNC\vncviewer.exe",
    r"C:\Program Files\UltraVNC\vncviewer.exe",
    r"C:\Program Files (x86)\UltraVNC\vncviewer.exe",
    r"C:\Program Files\uvnc\UltraVNC\vncviewer.exe",
    r"C:\Program Files (x86)\uvnc\UltraVNC\vncviewer.exe",
    r"C:\Program Files\TightVNC\tvnviewer.exe",
    r"C:\Program Files (x86)\TightVNC\tvnviewer.exe",
)


def desktop_dir():
    """Current user's Desktop (honours OneDrive redirection)."""
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        # CSIDL_DESKTOPDIRECTORY = 0x0010
        if ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf) == 0:
            p = buf.value
            if p and os.path.isdir(p):
                return p
    except Exception:
        pass
    for key in ("USERPROFILE", "HOME"):
        base = os.environ.get(key)
        if base:
            p = os.path.join(base, "Desktop")
            if os.path.isdir(p):
                return p
    return os.path.join(os.path.expanduser("~"), "Desktop")


def find_vnc_viewer():
    """Return path to UltraVNC/TightVNC viewer, or None."""
    for p in _VIEWER_CANDIDATES:
        if os.path.isfile(p):
            return p
    for name in ("vncviewer.exe", "tvnviewer.exe"):
        found = shutil.which(name)
        if found and os.path.isfile(found):
            return found
    return None


def vnc_arguments(viewer, host, password=VNC_PASSWORD):
    base = os.path.basename(viewer or "").lower()
    if "tvnviewer" in base:
        return f"{host} -password={password}"
    return f"{host} -password {password}"


def _safe_filename(name):
    s = re.sub(r'[<>:"/\\|?*]', " ", str(name or "").strip())
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s or "Till"


def shortcut_name(shop_name, till):
    shop = _safe_filename(shop_name or "Shop")
    till_name = _safe_filename(till.get("name") or f"Terminal {till.get('number')}")
    host = vector_terminals.host_from_location(till.get("location") or "")
    return f"{shop} - {till_name} ({host}).lnk" if host else f"{shop} - {till_name}.lnk"


def _ps_quote(s):
    return "'" + str(s).replace("'", "''") + "'"


def write_lnk(lnk_path, target, arguments, workdir=None):
    """Create/overwrite a Windows .lnk via WScript.Shell."""
    workdir = workdir or os.path.dirname(target) or ""
    cmd = (
        f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut("
        f"{_ps_quote(lnk_path)}); "
        f"$s.TargetPath = {_ps_quote(target)}; "
        f"$s.Arguments = {_ps_quote(arguments)}; "
        f"$s.WorkingDirectory = {_ps_quote(workdir)}; "
        f"$s.IconLocation = {_ps_quote(target)}; "
        f"$s.Description = {_ps_quote('VNC to till')}; "
        f"$s.Save()"
    )
    flags = 0
    if sys.platform == "win32":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    r = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
        capture_output=True, text=True, timeout=45, creationflags=flags,
    )
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip() or f"exit {r.returncode}"
        raise OSError(f"Could not create shortcut: {err}")
    if not os.path.isfile(lnk_path):
        raise OSError(f"Shortcut was not created: {lnk_path}")


def tills_with_host(info):
    out = []
    for t in vector_terminals.configured_tills(info):
        host = vector_terminals.host_from_location(t.get("location") or "")
        if host:
            row = dict(t)
            row["host"] = host
            row["share"] = vector_terminals.share_from_location(t.get("location") or "")
            out.append(row)
    return out


def tills_for_display(info):
    """Keep configured tills visible even when their location cannot be copied."""
    out = []
    for terminal in vector_terminals.configured_tills(info):
        row = dict(terminal)
        location = row.get("location") or ""
        row["share"] = vector_terminals.copy_location(location, info.get("data_path"))
        row["problem"] = ""
        if not row["share"]:
            if not location.strip():
                row["problem"] = "No till folder"
            elif len(location) > 1 and location[1] == ":":
                row["problem"] = "Remote till needs UNC"
            else:
                row["problem"] = "No usable till folder"
        out.append(row)
    return out


def tills_for_push(info, till_numbers=None):
    """Tills with a safe copy folder, optionally limited to terminal numbers."""
    tills = [t for t in tills_for_display(info or {}) if t.get("share")]
    if till_numbers is None:
        return tills
    want = set()
    for n in till_numbers:
        try:
            want.add(int(n))
        except (TypeError, ValueError):
            continue
    return [t for t in tills if int(t.get("number") or 0) in want]


def create_vnc_shortcuts(info, shop_name, desktop=None, viewer=None,
                         password=VNC_PASSWORD, write=write_lnk):
    """Write one VNC shortcut per till that has a UNC host.

    Returns dict: created, skipped, viewer, desktop, error, names
    """
    desktop = desktop or desktop_dir()
    viewer = viewer or find_vnc_viewer()
    result = {
        "created": 0,
        "skipped": 0,
        "viewer": viewer,
        "desktop": desktop,
        "error": None,
        "names": [],
        "skipped_names": [],
    }
    if not viewer:
        result["error"] = (
            "UltraVNC (or TightVNC) viewer was not found. Install UltraVNC "
            "on this PC so the shortcuts can open with the till password.")
        return result
    if not desktop or not os.path.isdir(desktop):
        result["error"] = "Desktop folder was not found."
        return result
    tills = tills_with_host(info)
    if not tills:
        result["error"] = (
            "No till has a network path (\\\\server\\share). "
            "Empty slots and @-style locations are skipped.")
        return result
    for t in tills:
        name = shortcut_name(shop_name, t)
        lnk = os.path.join(desktop, name)
        try:
            write(lnk, viewer, vnc_arguments(viewer, t["host"], password),
                  os.path.dirname(viewer))
        except Exception as e:
            result["skipped"] += 1
            result["skipped_names"].append(f"{name}: {e}")
            continue
        result["created"] += 1
        result["names"].append(name)
    if result["created"] == 0 and result["skipped"]:
        result["error"] = "No shortcuts were created.\n" + "\n".join(
            result["skipped_names"][:8])
    return result


def list_upgrade_files(source):
    """Relative file paths under a folder (files only, lock/temp skipped)."""
    if not source or not os.path.isdir(source):
        return []
    skip_ext = {".ldb", ".laccdb", ".lock"}
    out = []
    for root, _dirs, files in os.walk(source):
        for name in files:
            if name.startswith(".") or name.lower() == "thumbs.db":
                continue
            if name.lower() in ("version.txt", "version"):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext in skip_ext:
                continue
            out.append(os.path.relpath(os.path.join(root, name), source))
    out.sort()
    return out


def _unwrap_root(folder):
    """If a zip extracted to a single wrapper folder, use that folder."""
    try:
        names = [n for n in os.listdir(folder)
                 if n not in (".", "..") and n.lower() != "__macosx"]
    except OSError:
        return folder
    files = [n for n in names if os.path.isfile(os.path.join(folder, n))]
    dirs = [n for n in names if os.path.isdir(os.path.join(folder, n))]
    if len(dirs) == 1 and not files:
        return _unwrap_root(os.path.join(folder, dirs[0]))
    return folder


def _named_subdir(root, *names):
    try:
        listing = {n.lower(): n for n in os.listdir(root)}
    except OSError:
        return None
    for want in names:
        real = listing.get(want.lower())
        if real:
            p = os.path.join(root, real)
            if os.path.isdir(p):
                return p
    return None


def _safe_extract_zip(zpath, dest):
    """Extract, skipping any member that would land outside dest (zip-slip)."""
    import zipfile
    with zipfile.ZipFile(zpath) as zf:
        dest_abs = os.path.abspath(dest)
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or ".." in name.split("/"):
                continue
            target = os.path.abspath(os.path.join(dest, name))
            if not target.startswith(dest_abs + os.sep) and target != dest_abs:
                continue
            zf.extract(info, dest)
