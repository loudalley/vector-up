# Vector-Up by Koenekt - shared handoff (Codex/ChatGPT, Claude, Cursor)

Rules for using this file are in `AGENTS.md`. Update **Current state** and add
a dated line to the **Handoff log** every time you hand work back, then commit,
push, and tell the user.

## Current state

- **Version:** 1.2.0 (released as `v1.2.0`, win32 + win64 portable exes on
  GitHub Releases: https://github.com/loudalley/vector-up/releases/tag/v1.2.0)
- **Repo:** https://github.com/loudalley/vector-up (PUBLIC), `master`
- **Local:** `C:\Projects\koenekt-upgrade-tool`
- **Origin:** split out of the Koenekt Reporter's Terminals-tab upgrade
  (`C:\Projects\koenekt-daily-report`, private) on 2026-10-08. The till/INI
  helpers are vendored here; if the Reporter's copy/skip rules change, mirror
  them.

### What works (tested)

- Package: drop Vector's zip (`BO\`, `POS\`, `Utilities\`, notes); BO/POS
  sorted, only the outer zip opened. Tested against a real package
  (`Vector_BO_2_24_0005b_POS_2_14_0003g_TEST.zip`) and generated ones.
- Upgrade one till / one back office / one shop / ticked / ALL; 20-shop runs on
  local folders; marker `_UpgradeRequired` last and withheld on failure; backup
  of replaced files; unreachable targets skipped; Stop; Check (dry run).
- Portable single-file exes, 64-bit and 32-bit (PyInstaller); both start and
  unpack the real package; settings beside the exe.
- `tests/test_techtool.py` 46 tests; `tests/check_techtool_gui.py` drives the
  real window with real `WM_DROPFILES` messages.

### NOT verified yet (do not claim otherwise)

- A real drag from Windows Explorer (only posted messages were tested).
- A copy to real tills / a real back office, and whether Vector then actually
  upgrades itself from the copied files.
- Whether Vector ignores the `_koenekt_backup` folder inside a live back-office
  data folder.
- VNC shortcut creation beyond a fake writer (needs UltraVNC/TightVNC viewer).
- The exes are unsigned; SmartScreen/antivirus may warn.

### Next steps

1. Real Explorer drag onto the window, then a copy to ONE test till, then check
   Vector upgrades itself. Report results here.
2. User is theming the UI (colours/fonts at the top of `techtool/gui.py`).

## Handoff log

- **2026-10-08 - Claude:** created the project from the Reporter's upgrade
  feature; built the one-window package workflow, per-till/BO/all upgrades,
  portable exes (win32 + win64), named it Vector-Up by Koenekt, published the
  public repo and the v1.2.0 release. Added `AGENTS.md`, `CLAUDE.md`,
  `.cursor/rules/handoff.mdc` and this file so Codex/ChatGPT and Cursor follow
  the same always-notify handoff routine. Tests: 46 unit OK, GUI check OK, both
  frozen exes smoke-tested. Not tested on real tills (see above).
