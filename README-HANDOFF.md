# Vector-Up by Koenekt - shared handoff (Codex/ChatGPT, Claude, Cursor)

Rules for using this file are in `AGENTS.md`. Update **Current state** and add
a dated line to the **Handoff log** every time you hand work back, then commit,
push, and tell the user.

## Current state

- **Date / assistant:** 2026-10-08, Codex (GPT-6).
- **Version:** 1.3.1. Both portable EXEs built locally in `dist/`; no 1.3.1
  GitHub release published. Published release remains v1.2.0.
- **Repo:** https://github.com/loudalley/vector-up (PUBLIC), `master`.
- **Local:** `C:\Projects\koenekt-upgrade-tool`.
- **Origin:** extracted from the private Reporter; helpers are vendored here.
  The sister project was not edited.

### Latest fix: tills missing from the list

- User reported only the pointed BO appeared. The supplied live INI parsed
  successfully, but its local drive-based till location was filtered out by
  the UNC-only `tills_for_push` helper. Earlier GUI tests mocked discovery,
  which hid this defect.
- Local back-office installations now support absolute local till folders.
  UNC shares still work. Drive paths from remote BOs, mapped remote BO drives
  or UNC junctions are never applied to the technician PC. No global INI
  fallback is used: each shop still reads its own VectorTerminals.ini.
- All configured/named tills are displayed. Missing/unsupported folders have
  clear row statuses and disabled tickboxes; those rows are excluded from
  selection totals and copying. Empty slots remain hidden. Refresh reports
  configured and usable counts, and INI errors reach the window/log.
- Malformed INIs return a diagnostic instead of aborting discovery. Engine
  warnings identify skipped terminal numbers. The GUI check now writes and
  parses synthetic INIs instead of mocking terminal parsing or path selection.
- Updated README and the shared AGENTS.md rules. No customer data or real INI
  was copied into the repo. The supplied INI was read-only; its hash stayed
  unchanged, and its local POS folder was verified to exist. No upgrade,
  backup or reachability probe was run against those live destinations.

### Existing 1.3.0 behaviour retained

- Shared font/colour roles, consistent ttk controls, matching checkbox images,
  mixed shop selection and Space-to-toggle; Get package in the drop zone.
- POS saves ONLY postrans.dat + posdebtor.dat before copying, under local
  `VectorUp_data\POS backups\<shop>\<till - number - identifier>\<timestamp>\`
  (settings fallback when needed). Missing/failed backups skip that till.
  BO backups are manual; no replaced-file backups. Live databases never written.
- Get package uses a temporary Edge app window/profile, Chrome fallback,
  installer login, completed-ZIP queue import and profile cleanup. Installed
  browser required; no extra Python dependencies. Invalid package replacement
  preserves the loaded package. Marker still last/withheld; nothing deleted.

### Tests actually run for 1.3.1

- 64-bit and 32-bit `tests/test_techtool.py`: **64 tests passed on each** with
  KUT_REAL_ZIP set, including the genuine-package test. New coverage: actual
  local INI discovery/plan, no-folder slots, remote/mapped path safety, UNC,
  invalid INIs, BOM and read-only parsing.
- `tests/check_techtool_gui.py`: **passed on both architectures** with real
  synthetic INI discovery, local-folder copying, mouse/keyboard tickboxes,
  disabled no-folder rows, per-row/ticked/ALL selection, backup/marker rules,
  posted WM_DROPFILES and minimum button bounds. 32-bit run also used the
  genuine package on synthetic destination folders.
- Real Windows window inspected with synthetic local and no-folder rows.
- `build_portable.bat`: **both 1.3.1 EXEs built**. Both frozen EXEs then
  discovered tills from a synthetic INI at startup, reporting configured and
  usable counts. INI unchanged; no file copies performed in that smoke check.
- Live INI read-only parse/plan verification passed; hash unchanged. Public
  tests use only synthetic shop/terminal values.
- `git diff --check`: passed. The browser code did not change; its actual
  synthetic download/cleanup tests passed on both architectures in 1.3.0 and
  were not rerun this turn.

### NOT verified yet

- Backups/copies on real tills, live file locking, Vector's subsequent upgrade.
- Actual authenticated Vector-site download with installer credentials.
- Real Explorer drag (only posted drop messages checked).
- Chrome fallback, restrictive browser policies and actual VNC shortcut launch.
- EXEs remain unsigned. Build/startup verification is not a real-till upgrade.

### Exact next step

Close the older upgrader and run `dist\VectorUp-1.3.1-win64.exe` (win32 on a
32-bit PC), keeping the shop pointed at its BO folder containing the INI.
Press Refresh tills: local tills should now appear. No INI edits are needed
for a valid local location. After manual BO backup and closing Vector on ONE
test till, check the planned destination, upgrade it and verify local POS
backups and Vector's own next-start upgrade. Record those live results here.
Publish EXEs with SHA-256 notes when a release is requested.

## Handoff log

- **2026-10-08 - Codex (GPT-6), 1.3.1:** fixed tills hidden by UNC-only filtering;
  local BO/till folders now supported, missing folders visible and unselectable,
  remote drive paths guarded. GUI check now exercises real synthetic INIs.
  Both architectures: 64 unit tests including genuine package, GUI checks,
  builds and frozen discovery smoke checks passed. Synthetic UI inspected.
  Supplied live INI parsed/planned read-only and stayed unchanged; no live copy
  or backup. Updated shared rules/docs. Next: run 1.3.1, refresh tills, then
  verify ONE closed test till's backup/copy/Vector upgrade. No release published.
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
