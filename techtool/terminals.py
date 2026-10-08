"""
Read VectorTerminals.ini from a Ramset / Vector back-office folder.

The file lives next to Ramset.dat (the shop's `data_path`). Two layouts have
been seen in the wild:

  * Newer: Enabled=True/False, SourceStockLocation,
    TerminalLocation=\\\\server\\share\\, CENTRAL POS PATHS / MISCELLEANOUS.
  * Older: Live=0/-1, StockLoc, TerminalLocation=@1,
    thinner terminal sections.

This module normalises both into one list for the Setup "Terminals" tab.
Read-only — never write the INI back.
"""
import configparser
import os
import re


INI_NAMES = (
    "VectorTerminals.ini",
    "vectorterminals.ini",
    "VECTORTERMINALS.INI",
)


def find_ini(data_path):
    """Return the path to VectorTerminals.ini under data_path, or None."""
    if not data_path or not os.path.isdir(data_path):
        return None
    for name in INI_NAMES:
        p = os.path.join(data_path, name)
        if os.path.isfile(p):
            return p
    try:
        for name in os.listdir(data_path):
            if name.lower() == "vectorterminals.ini":
                return os.path.join(data_path, name)
    except OSError:
        pass
    return None


def _truthy(v):
    s = str(v or "").strip().lower()
    if s in ("true", "yes", "1", "-1", "on"):
        return True
    if s in ("false", "no", "0", "off", ""):
        return False
    try:
        return int(float(s)) != 0
    except (TypeError, ValueError):
        return bool(s)


def _term_number(section):
    m = re.match(r"(?i)^TERMINAL\s+(\d+)$", (section or "").strip())
    return int(m.group(1)) if m else None


def read_terminals(data_path):
    """Parse terminals for a shop folder.

    Returns a dict:
      available, path, error,
      central (dict of central POS paths),
      misc (misc settings),
      terminals (list of dicts, numbered ascending),
      enabled_count, total_with_name
    """
    out = {
        "available": False,
        "path": None,
        "error": None,
        "central": {},
        "misc": {},
        "terminals": [],
        "enabled_count": 0,
        "total_with_name": 0,
        "file_version": {},
    }
    ini = find_ini(data_path)
    if not ini:
        out["error"] = (
            "VectorTerminals.ini not found in this shop's data folder.")
        return out
    out["path"] = ini

    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = str  # keep key case as in the file
    try:
        # utf-8-sig covers BOM; latin-1 fallback for older Windows dumps
        try:
            with open(ini, "r", encoding="utf-8-sig") as f:
                cp.read_file(f)
        except UnicodeDecodeError:
            with open(ini, "r", encoding="latin-1") as f:
                cp.read_file(f)
    except OSError as e:
        out["error"] = f"Could not read VectorTerminals.ini: {e}"
        return out

    for section in cp.sections():
        su = section.upper().strip()
        items = {k: v for k, v in cp.items(section)}
        if su in ("CENTRAL POS PATHS", "CENTRAL POS PATH"):
            out["central"] = items
        elif su.startswith("MISCEL"):  # typo MISCELLEANOUS is common
            out["misc"] = items
        elif su == "FILE VERSION":
            out["file_version"] = items
        else:
            n = _term_number(section)
            if n is None:
                continue  # skip ECR blocks and unknowns
            name = (items.get("Name") or items.get("name") or "").strip()
            loc = (items.get("TerminalLocation")
                   or items.get("terminallocation") or "").strip()
            # Newer: Enabled=; older: Live= (-1/0) or Standalone
            if "Enabled" in items:
                enabled = _truthy(items.get("Enabled"))
            elif "Live" in items:
                enabled = _truthy(items.get("Live"))
            else:
                # nameless empty slots with no Enabled key → treat as off
                enabled = bool(name or loc) and _truthy(
                    items.get("Standalone", "0"))
            stock = (items.get("SourceStockLocation")
                     or items.get("StockLoc")
                     or items.get("stockloc") or "").strip()
            group = (items.get("TillGroup") or items.get("tillgroup")
                     or "").strip()
            out["terminals"].append({
                "number": n,
                "name": name or f"Terminal {n}",
                "location": loc,
                "enabled": enabled,
                "till_group": group,
                "stock_location": stock,
                "dept": (items.get("Dept") or "").strip(),
                "group": (items.get("Group") or "").strip(),
                "auto_cashup": _truthy(items.get("AutoCashup")),
                "do_debtors": _truthy(items.get("DoDebtors")),
                "raw": items,
            })

    out["terminals"].sort(key=lambda t: t["number"])
    out["enabled_count"] = sum(1 for t in out["terminals"] if t["enabled"])
    out["total_with_name"] = sum(
        1 for t in out["terminals"]
        if (t.get("raw", {}).get("Name") or "").strip() or t["location"])
    out["available"] = True
    return out


def host_from_location(location):
    """Hostname or IP from a TerminalLocation UNC, or None if not remote."""
    s = (location or "").strip().strip('"')
    if not s or s.startswith("@"):
        return None
    s = s.replace("/", "\\")
    if s.startswith("\\\\"):
        host = s[2:].split("\\", 1)[0].strip()
        if host and host not in (".", "?"):
            return host
        return None
    if re.match(r"^\d{1,3}(?:\.\d{1,3}){3}$", s):
        return s
    return None


def share_from_location(location):
    """Normalised UNC folder (\\\\host\\share\\...) or None."""
    s = (location or "").strip().strip('"').replace("/", "\\")
    if not s.startswith("\\\\"):
        return None
    parts = [p for p in s.split("\\") if p]
    if len(parts) < 2:
        return None
    return "\\\\" + "\\".join(parts)


def configured_tills(info):
    """Terminals that have a name or UNC path (skip empty INI slots)."""
    tills = []
    for t in (info or {}).get("terminals") or []:
        raw_name = (t.get("raw", {}).get("Name") or "").strip()
        loc = (t.get("location") or "").strip()
        if not raw_name and not loc and not t.get("enabled"):
            continue
        tills.append(t)
    return tills


def summary_lines(info):
    """Short text block for status labels."""
    if not info or not info.get("available"):
        return info.get("error") or "No terminal list available."
    lines = [
        f"{info['enabled_count']} enabled of "
        f"{info['total_with_name']} configured "
        f"({len(info['terminals'])} slots in file)",
    ]
    if info.get("path"):
        lines.append(os.path.basename(info["path"]))
    return "\n".join(lines)
