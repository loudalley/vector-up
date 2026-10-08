"""An upgrade package as Vector ships it: one zip holding BO\\ and POS\\.

    Vector_BO_2_24_0005b_POS_2_14_0003g.zip
        BO\\   RP_BACK.exe, VectorInitialiser.dll, BO_2_24_0005.zip, _UpgradeRequired
        POS\\  RPOS25.exe,  VectorInitialiser.dll, POS_2_14_0003.zip, _UpgradeRequired
        Utilities\\, InstallationNotes.txt        (not copied anywhere)

Vector's own notes say to copy ALL the files in the relevant folder over the
application folder. The inner zip and the _UpgradeRequired marker are part of
that: Vector unpacks the inner zip itself the next time the program starts. So
only the OUTER zip is ever opened here, and the inner one travels as a file.

BO\\ files go to back offices, POS\\ files to tills.
"""
import os
import shutil
import tempfile

from . import tillops

BO_NAMES = ("bo", "backoffice", "back office", "b/o")
POS_NAMES = ("pos", "till", "tills", "front office", "fo")
MARKER_PREFIX = "_upgraderequired"


class Payload:
    """The files for one role (BO or POS), in the order they must be copied."""

    def __init__(self, role, folder):
        self.role = role
        self.dir = folder
        self._files = None

    def files(self):
        """Relative paths, with the _UpgradeRequired trigger always last.

        Vector starts upgrading when it sees that marker, so it must not exist
        on a till until everything it needs has arrived.
        """
        if self._files is None:
            fs = [f for f in tillops.list_upgrade_files(self.dir)
                  if not f.lower().endswith(".dat")]
            fs.sort(key=lambda r: (
                os.path.basename(r).lower().startswith(MARKER_PREFIX),
                r.lower()))
            self._files = fs
        return list(self._files)

    def marker_files(self):
        return [f for f in self.files()
                if os.path.basename(f).lower().startswith(MARKER_PREFIX)]

    def size(self):
        n = 0
        for rel in self.files():
            try:
                n += os.path.getsize(os.path.join(self.dir, rel))
            except OSError:
                pass
        return n

    def label(self):
        """What Vector will install, from the marker file, else the folder."""
        for m in self.marker_files():
            try:
                with open(os.path.join(self.dir, m), encoding="utf-8-sig",
                          errors="replace") as f:
                    text = f.readline().strip()
                if text:
                    return os.path.splitext(text)[0]
            except OSError:
                pass
        return os.path.basename(self.dir)


class Package:
    def __init__(self, name, root, bo, pos, ignored):
        self.name = name
        self.root = root
        self.bo = Payload("BO", bo) if bo else None
        self.pos = Payload("POS", pos) if pos else None
        self.ignored = ignored  # top-level names that are never copied

    def summary(self):
        lines = [self.name]
        for p, title in ((self.bo, "BACK OFFICE"), (self.pos, "POS")):
            if p:
                lines.append(f"{title}:  {p.label()}  -  {len(p.files())} "
                             f"file(s), {human_size(p.size())}")
            else:
                lines.append(f"{title}:  not in this package")
        if self.ignored:
            lines.append("Not copied: " + ", ".join(sorted(self.ignored)))
        return "\n".join(lines)


def find_roles(folder):
    """(bo_dir, pos_dir, ignored_names) for an extracted package, or Nones.

    Looks in the folder itself and, when a zip wraps everything in a single
    folder, one level down. Never falls back to treating the whole folder as
    one role - guessing wrong would copy Utilities onto a till.
    """
    for root in (folder, tillops._unwrap_root(folder)):
        bo = tillops._named_subdir(root, *BO_NAMES)
        pos = tillops._named_subdir(root, *POS_NAMES)
        if bo or pos:
            used = {os.path.basename(p) for p in (bo, pos) if p}
            ignored = [n for n in os.listdir(root) if n not in used]
            return root, bo, pos, ignored
    return folder, None, None, []


def load(path, scratch, progress=None):
    """Open a dropped zip (or already-unzipped folder) as a Package.

    Raises ValueError with a message fit to show the technician.
    """
    path = os.path.normpath(path)
    name = os.path.basename(path)
    if os.path.isdir(path):
        src = tempfile.mkdtemp(prefix="pkg-", dir=scratch)
        if progress:
            progress(10, f"Reading {name}")
        shutil.copytree(path, src, dirs_exist_ok=True)
    elif path.lower().endswith(".zip") and os.path.isfile(path):
        src = tempfile.mkdtemp(prefix="pkg-", dir=scratch)
        if progress:
            progress(10, f"Extracting {name}")
        try:
            tillops._safe_extract_zip(path, src)
        except Exception as e:  # BadZipFile, truncated download, ...
            shutil.rmtree(src, ignore_errors=True)
            raise ValueError(f"Could not open {name}: {e}")
    else:
        raise ValueError(
            f"{name}: drop the whole upgrade package (.zip, or its "
            f"unzipped folder) - it has to contain a BO and a POS folder.")
    root, bo, pos, ignored = find_roles(src)
    if not (bo or pos):
        seen = ", ".join(sorted(os.listdir(src))[:8]) or "nothing"
        shutil.rmtree(src, ignore_errors=True)
        raise ValueError(
            f"{name} has no BO or POS folder (found: {seen}).")
    if progress:
        progress(100, "Package ready")
    return Package(name, root, bo, pos, ignored)


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
