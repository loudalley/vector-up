# Vector-Up by Koenekt - shared handoff (Codex/ChatGPT, Claude, Cursor)

Rules for using this file are in `AGENTS.md`. Update **Current state** and add
a dated line to the **Handoff log** every time you hand work back, then commit,
push, and tell the user.

## Current state

- **Date / assistant:** 2026-10-08, Codex (GPT-6).
- **Git confirmation:** UI/backup/download changes committed as `7628b6d` and
  verified on `origin/master` on 2026-10-08. No application changes in this
  commit/push follow-up; no tests rerun. Live checks below remain outstanding.
- **Version:** 1.3.0. Both portable EXEs built locally in `dist/`; no 1.3.0
  GitHub release published in this turn. Published release remains v1.2.0.
- **Repo:** https://github.com/loudalley/vector-up (PUBLIC), `master`.
- **Local:** `C:\Projects\koenekt-upgrade-tool`.
- **Origin:** extracted from the private Koenekt Reporter; till helpers are
  vendored here. The sister project was not edited.

### What changed and why

- User requested nicer theming, fonts and tickboxes. Shared font/colour roles,
  consistent ttk controls, matching raster checkbox indicators in the tree
  and settings, clear mixed shop selection, Space to toggle, roomier rows,
  simpler shop toolbar, high-contrast drop-zone text, and compact package
  versions keep the destination list usable after a package is loaded.
- Removed replaced-file backups and their switch. BO backups are manual.
  Before a POS copy, ONLY `postrans.dat` and `posdebtor.dat` are read from the
  till and saved beside the portable EXE under
  `VectorUp_data\POS backups\<shop>\<till - number - identifier>\<timestamp>\`.
  Source mode/read-only EXE folders use the settings fallback. Both files must
  exist and be copied successfully or that till receives no upgrade files;
  other targets continue. Live databases are never modified. An **Open POS
  backups** button opens the local folder. AGENTS.md now reflects the user's
  revised policy; thin Claude/Cursor entry points remain unchanged.
- **Get package** in the drop zone opens Vector's login URL in a small Edge
  app window (Chrome fallback). Installer enters credentials directly there.
  A temporary separate browser profile disables password saving and optional
  browser extensions. Finished session ZIPs import automatically through the
  Tk queue; partial downloads are ignored. Browser lifetime uses its private
  loopback endpoint because Edge's launcher can exit while the window remains
  open. Closing Vector-Up closes that session and removes temporary files.
  No extra Python dependencies; installed Edge/Chrome required for this button.
- Package replacements stage into separate temp folders, so an invalid ZIP
  cannot erase the previous loaded package. Direct `.dat` payload files are
  excluded. Upgrade marker remains last/withheld on failure. Editing and
  package controls are disabled while copying or loading.

### Tests actually run (this version)

- `python tests/test_techtool.py` and `py -3.14-32 tests/test_techtool.py`:
  **56 tests passed on each**, including the genuine-package test with
  `KUT_REAL_ZIP`. Initial runs skipped that optional test; final runs did not.
- `tests/check_techtool_gui.py` on 64-bit and 32-bit Python: **passed**. Real
  posted WM_DROPFILES, per-row/ticked/ALL copying, mouse checkbox hit testing,
  keyboard toggling/mixed selection, minimum-size button bounds, local POS
  snapshots and no automatic BO backups. Uses synthetic shop/till data.
- `tests/check_vector_download.py` on both architectures: **passed**. Actual
  Edge app window downloads a synthetic ZIP from a local fixture; Vector-Up
  imports it and displays package-ready state. Browser/profile cleanup passed.
  An initial launcher-lifetime failure was fixed before these final checks.
- Real Windows UI inspected with synthetic destinations at normal and minimum
  size, including the DPI-aware path. Fonts, checkbox states and spacing viewed.
- `build_portable.bat`: **both 1.3.0 EXEs built**. Each frozen EXE then started,
  loaded a synthetic package, and used beside-EXE portable storage in an
  isolated test directory. EXEs remain ignored; no binaries committed.
- `git diff --check`: passed. Live Vector login URL returns HTTP 401 when
  unauthenticated, consistent with its authentication challenge.

### NOT verified yet

- Actual authenticated Vector-site download with the installer's credentials.
  The end-to-end browser test uses a synthetic local package.
- Real Explorer drag (only posted drop messages checked).
- Copies/backups on real till shares, live database file availability/locking,
  or Vector's own subsequent upgrade. No real shop/till was touched.
- Chrome fallback or machines with browser policies blocking custom profiles,
  downloads or the local browser endpoint. Manual ZIP browsing/drop remains.
- Actual VNC viewer shortcut launching. EXEs remain unsigned.

### Exact next step

Installer: run `dist\VectorUp-1.3.0-win64.exe` (win32 on a 32-bit PC), use
**Get package**, enter the Vector login and select the upgrade ZIP. Check that
its BO/POS versions appear automatically. Manually back up BO; close Vector
on ONE test till, upgrade that till and check the two files in **Open POS
backups**, then check Vector upgrades itself. Record those live results here.
Publish v1.3.0 with the two EXEs and SHA-256 notes when a release is requested.

## Handoff log

- **2026-10-08 - Codex (GPT-6):** user requested push/commit. Fetched origin
  and confirmed the clean local master matched origin/master, including the
  1.3.0 implementation commit `7628b6d`. Updated this handoff confirmation;
  no source changes or tests rerun. Next: installer login and one test till
  as described above. Real shops/tills remain untested.
- **2026-10-08 - Codex (GPT-6), 1.3.0:** refreshed styling/fonts/checkboxes;
  replaced upgrade-file backups with mandatory local two-file POS snapshots
  grouped by shop/till/time; BO backups manual. Added Get package mini browser
  with automatic completed-ZIP import and temp profile cleanup. Updated shared
  rules/docs. Both architectures: 56 unit tests including genuine package,
  GUI checks and real-browser synthetic download check passed; both EXEs built
  and frozen startup/package/storage smoke checks passed. UI visually inspected.
  Not tested with actual Vector login or real tills. No release published;
  next: installer login/download, then one closed test till and verify backups.
- **2026-10-08 - Codex (GPT-6):** read up on the current UI and official styling
  guidance at the user's request. Recorded mixed Tk/ttk styling, default 9pt
  fonts, Unicode tree tickboxes and low-contrast drop-zone text. Runtime/font
  probe and contrast calculation passed; no app code changes, build, GUI
  workflow test or real-till test. Next: implement and visually check the UI
  styling pass. Version remains 1.2.0.
- **2026-10-08 - Claude:** created the project from the Reporter's upgrade
  feature; built the one-window package workflow, per-till/BO/all upgrades,
  portable exes (win32 + win64), named it Vector-Up by Koenekt, published the
  public repo and the v1.2.0 release. Added `AGENTS.md`, `CLAUDE.md`,
  `.cursor/rules/handoff.mdc` and this file so Codex/ChatGPT and Cursor follow
  the same always-notify handoff routine. Tests: 46 unit OK, GUI check OK, both
  frozen exes smoke-tested. Not tested on real tills (see above).
