"""Plan and run an upgrade across many shops. No Tk in here, so it is testable.

Per shop:
  POS -> the till shares found in that shop's VectorTerminals.ini
  BO  -> the shop's back-office folder (the one holding Ramset.dat)

Any subset can be chosen: one till, one back office, a whole shop, everything.
A shop dict may carry  want_bo (default True)  and  want_tills (None = every
till, else a set of terminal numbers)  and  _idx  (its row in the window).

A target is checked for reachability before anything is copied: a mistyped
path must not turn into a stray folder, and a dead till must not cost one
network timeout per file.
"""
import datetime
import os
import shutil
from concurrent.futures import ThreadPoolExecutor

from . import terminals as vector_terminals
from . import tillops

POS, BO = "POS", "BO"
BACKUP_FOLDER = "_koenekt_backup"


def target_key(shop, kind, till=None):
    idx = shop.get("_idx", shop.get("name"))
    return f"{idx}:bo" if kind == BO else f"{idx}:t{till}"


def build_plan(shops, do_pos, do_bo):
    """Work out every destination for the chosen shops / tills.

    Returns {"targets": [...], "warnings": [...]}. A target is
    {key, shop, kind, label, dest}. Duplicate destinations are dropped.
    """
    targets, warnings, seen = [], [], set()

    def add(key, shop, kind, label, dest):
        dup = (kind, os.path.normpath(dest).lower())
        if dup in seen:
            return
        seen.add(dup)
        targets.append({"key": key, "shop": shop, "kind": kind,
                        "label": label, "dest": dest})

    for s in shops:
        name = s.get("name") or s.get("bo_path") or "(unnamed)"
        bo_path = (s.get("bo_path") or "").strip()
        want_tills = s.get("want_tills")
        if not bo_path:
            warnings.append(f"{name}: no back-office folder set - skipped.")
            continue
        if do_bo and s.get("want_bo", True):
            add(target_key(s, BO), name, BO, "Back office", bo_path)
        if do_pos and (want_tills is None or want_tills):
            info = vector_terminals.read_terminals(bo_path)
            if not info.get("available"):
                warnings.append(f"{name}: {info.get('error')} No tills to "
                                f"copy POS files to.")
                continue
            tills = tillops.tills_for_push(info, want_tills)
            if not tills and want_tills is None:
                warnings.append(
                    f"{name}: no till has a network share "
                    f"(\\\\ip\\share) in VectorTerminals.ini.")
            for t in tills:
                add(target_key(s, POS, t.get("number")), name, POS,
                    t.get("name") or f"Terminal {t.get('number')}", t["share"])
    return {"targets": targets, "warnings": warnings}


def check_reachable(targets, workers=8):
    """Set target['reachable'] for each, checking in parallel.

    An unreachable UNC path can block for tens of seconds, so many shops are
    checked together rather than one after another.
    """
    def probe(t):
        try:
            return os.path.isdir(t["dest"])
        except OSError:
            return False

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for t, ok in zip(targets, ex.map(probe, targets)):
            t["reachable"] = ok
    return targets


def copy_payload(payload, dest, backup=True, progress=None, done_base=0,
                 done_total=1, stamp=None):
    """Copy one payload into dest. Never deletes anything at dest.

    1. If backup: every file about to be replaced is first copied to
       dest\\_koenekt_backup\\<stamp>\\ . If that fails nothing is copied.
    2. All files except the _UpgradeRequired marker.
    3. The marker, only if every other file arrived - it is what tells Vector
       to start upgrading, and it must not fire on a half-copied folder.

    Returns {copied, failed, backed_up, marker_withheld, backup_dir}.
    """
    files = payload.files()
    markers = set(payload.marker_files())
    out = {"copied": 0, "failed": [], "backed_up": 0,
           "marker_withheld": False, "backup_dir": None}
    stamp = stamp or datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    if backup:
        existing = [f for f in files if os.path.isfile(os.path.join(dest, f))]
        if existing:
            bdir = os.path.join(dest, BACKUP_FOLDER, stamp)
            try:
                for rel in existing:
                    tgt = os.path.join(bdir, rel)
                    os.makedirs(os.path.dirname(tgt), exist_ok=True)
                    shutil.copy2(os.path.join(dest, rel), tgt)
                    out["backed_up"] += 1
                out["backup_dir"] = bdir
            except OSError as e:
                out["failed"].append(
                    f"backup of {rel} failed ({e}) - nothing was copied")
                out["marker_withheld"] = bool(markers)
                return out

    order = [f for f in files if f not in markers] + \
            [f for f in files if f in markers]
    for i, rel in enumerate(order):
        if rel in markers and out["failed"]:
            out["marker_withheld"] = True
            break
        try:
            tgt = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(tgt), exist_ok=True)
            shutil.copy2(os.path.join(payload.dir, rel), tgt)
            out["copied"] += 1
        except OSError as e:
            out["failed"].append(f"{rel}: {e}")
        if progress and done_total:
            progress(min(99, int(100 * (done_base + i + 1) / done_total)),
                     os.path.basename(rel))
    return out


def run_upgrade(targets, bo_payload, pos_payload, emit, cancel=None,
                backup=True):
    """Copy the package to every target.

    emit(kind, *args):
        ("progress", pct, text)   ("log", text)
        ("target", key, status, text)  status: ok | partial | unreachable
    Returns a summary dict.
    """
    payloads = {BO: bo_payload, POS: pos_payload}
    todo = [t for t in targets if payloads.get(t["kind"])
            and payloads[t["kind"]].files()]
    total = max(1, sum(len(payloads[t["kind"]].files()) for t in todo))
    summary = {"ok": 0, "failed_targets": 0, "unreachable": 0, "copied": 0,
               "failed": [], "cancelled": False, "targets": len(todo),
               "withheld": 0, "backed_up": 0}
    done = 0
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    emit("log", f"Checking {len(todo)} destination(s)...")
    check_reachable(todo)

    for t in todo:
        payload = payloads[t["kind"]]
        n = len(payload.files())
        head = f"{t['shop']}  {t['kind']}  {t['label']}"
        if cancel and cancel():
            summary["cancelled"] = True
            emit("log", "Stopped - the remaining destinations were not touched.")
            break
        if not t["reachable"]:
            summary["unreachable"] += 1
            summary["failed"].append(f"{head}: not reachable ({t['dest']})")
            emit("log", f"SKIPPED  {head}  - {t['dest']} is not reachable.")
            emit("target", t["key"], "unreachable", "not reachable")
            done += n
            emit("progress", min(99, int(100 * done / total)), head)
            continue
        emit("progress", min(99, int(100 * done / total)), head)
        r = copy_payload(
            payload, t["dest"], backup=backup, done_base=done,
            done_total=total, stamp=stamp,
            progress=lambda pct, _txt, _h=head: emit("progress", pct, _h))
        done += n
        summary["copied"] += r["copied"]
        summary["backed_up"] += r["backed_up"]
        if r["failed"]:
            summary["failed_targets"] += 1
            summary["failed"].extend(f"{head}: {f}" for f in r["failed"])
            if r["marker_withheld"]:
                summary["withheld"] += 1
            emit("log", f"PARTIAL  {head}  - {r['copied']}/{n} copied, "
                        f"{len(r['failed'])} failed"
                        + ("; upgrade NOT triggered" if r["marker_withheld"]
                           else "") + ".")
            for f in r["failed"][:5]:
                emit("log", f"           {f}")
            emit("target", t["key"], "partial", "failed")
        else:
            summary["ok"] += 1
            extra = (f", {r['backed_up']} old file(s) saved to "
                     f"{os.path.relpath(r['backup_dir'], t['dest'])}"
                     if r["backed_up"] else "")
            emit("log", f"OK       {head}  - {r['copied']} file(s){extra}")
            emit("target", t["key"], "ok", payload.label())
    emit("progress", 100, "Done")
    return summary


def summary_text(s):
    bits = [f"{s['ok']} of {s['targets']} destination(s) completed"]
    if s["unreachable"]:
        bits.append(f"{s['unreachable']} not reachable")
    if s["failed_targets"]:
        bits.append(f"{s['failed_targets']} with failed files")
    if s["withheld"]:
        bits.append(f"{s['withheld']} left un-triggered (re-run to finish)")
    bits.append(f"{s['copied']} file(s) copied")
    if s["cancelled"]:
        bits.append("stopped early")
    return ", ".join(bits) + "."


def vnc_shortcuts(cfg_vnc_for, shops, group=True, desktop=None, viewer=None,
                  write=None):
    """Create VNC shortcuts for the given shops.

    cfg_vnc_for(shop) -> password. Shortcuts go in a 'Koenekt Tills' folder on
    the desktop when group is true: 20 shops of tills is a lot of icons.
    Returns {"created", "skipped", "errors", "viewer", "folder"}.
    """
    desktop = desktop or tillops.desktop_dir()
    folder = desktop
    if group:
        folder = os.path.join(desktop, "Koenekt Tills")
        os.makedirs(folder, exist_ok=True)
    out = {"created": 0, "skipped": 0, "errors": [], "viewer": None,
           "folder": folder}
    kwargs = {"write": write} if write else {}
    for s in shops:
        name = s.get("name") or s.get("bo_path") or "Shop"
        bo_path = (s.get("bo_path") or "").strip()
        info = vector_terminals.read_terminals(bo_path) if bo_path else {}
        if not info.get("available"):
            out["errors"].append(f"{name}: {info.get('error') or 'no folder'}")
            out["skipped"] += 1
            continue
        r = tillops.create_vnc_shortcuts(
            info, name, desktop=folder, viewer=viewer,
            password=cfg_vnc_for(s), **kwargs)
        out["viewer"] = r.get("viewer") or out["viewer"]
        out["created"] += r["created"]
        out["skipped"] += r["skipped"]
        if r.get("error"):
            out["errors"].append(f"{name}: {r['error']}")
    return out
