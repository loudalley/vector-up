# Vector-Up by Koenekt - shared handoff (Codex/ChatGPT, Claude, Cursor)

Rules for using this file are in `AGENTS.md`. Update **Current state** and add
a dated line to the **Handoff log** every time you hand work back, then commit,
push, and tell the user.

## Current state

- **Date / assistant:** 2026-10-09, Codex (GPT-6).
- **Version:** 1.4.0. Both portable EXEs built locally in `dist/`; no 1.4.0
  GitHub release published. Published release remains v1.2.0.
- **Repo:** https://github.com/loudalley/vector-up (PUBLIC), `master`.
- **Local:** `C:\Projects\koenekt-upgrade-tool`. Sister project not edited.

### Latest change: branding, startup animation and tickboxes

- Modern light surface/dark green header, original full Koenekt logo,
  supplied Vector logo, subtle geometric accents, coordinated controls and
  clearer spacing. Colour/font constants remain at the top of `gui.py`.
- Rounded antialiased tickboxes have a continuous dark tick on green; mixed
  shop selection uses a dash. Disabled rows and disabled ttk checkbuttons
  have distinct grey states. Mouse and Space toggles preserve tree focus and
  scrolling. The heading counts selected shops and destinations.
- Full Koenekt logo fades in, holds, then fades out in the existing window
  over 1.85 seconds. Click/Escape dismisses it immediately and cancels its
  timer. All animation work stays on the Tk thread; image references are
  released afterward. No extra splash window or runtime dependencies.
- The supplied SVG references Kabel lettering. The owner's matching full-logo
  PNG beside that SVG preserves the original lettering without distributing
  a font. Assets and the prepared opacity strip are bundled in both EXEs.
  `tools/prepare_branding.py` regenerates PNG resources using development-only
  Pillow. Reference theme images are not redistributed; geometry is drawn
  by the app. No personal source paths are embedded in those assets.
- Default window is 1200x860; minimum remains 1000x680. Footer reserved before
  expanding body, with table/activity minima to prevent clipped controls.
  The activity log scrolls to the newest message rather than its trailing
  blank line, keeping it readable in a small window. README describes the
  startup fade and checkbox states.

### Existing safety and discovery behaviour retained

- Each shop reads its own INI; local BO installations support local absolute
  till folders. Remote/mapped/junction drive paths never point at the technician
  PC. Named tills without a copy folder remain visible and cannot be selected.
- Before POS copies, ONLY postrans.dat + posdebtor.dat are saved locally under
  named shop/till/timestamp folders. Missing or failed backups skip that till.
  BO backup remains manual. Live databases/INIs never written.
- Outer ZIP only extracted; inner ZIPs copied intact; direct .dat payloads
  excluded. Marker last and withheld on any copy failure. Nothing deleted.
- Get package temporary Edge/Chrome browser, completed-ZIP import and cleanup
  unchanged. DnD window procedure still only uses ctypes/deque; workers queue
  events for the Tk thread. Portable storage and free/no-telemetry unchanged.

### Tests actually run for 1.4.0

- 64-bit and 32-bit `tests/test_techtool.py`: **64 tests run on each, OK; 1
  genuine-package test skipped on each** because KUT_REAL_ZIP was unset.
- `tests/check_techtool_gui.py`: **passed on both architectures** after final
  layout changes, with synthetic packages/destinations and real synthetic INIs.
  Includes automatic startup fade completion, Escape/click dismissal, assets,
  callback errors, mouse/actual Space events, mixed/disabled selections,
  per-row/ticked/ALL copies, POS backup policy, posted WM_DROPFILES, invalid
  replacement preserving the package, minimum-size buttons/table/log/footer,
  and the newest activity message fitting visibly at minimum size.
- Real Windows UI inspected: full-logo intro, final synthetic destination
  window at default/minimum size, and both frozen EXE windows. Visual inspection caught a squeezed
  activity area; fixed and added minimum-size content assertions.
- `build_portable.bat`: **both 1.4.0 EXEs built**. Both archives contain all
  three brand PNGs; isolated temporary EXE copies started, created portable
  settings and showed logos. Smoke windows closed afterward; no live copies.
- `git diff --check`: passed. Engine/download/DnD code unchanged.

### NOT verified yet

- Backups/copies on real tills, live file locking, Vector's subsequent upgrade.
- Actual authenticated Vector-site download with installer credentials.
- Real Explorer drag (only posted drop messages checked).
- Chrome fallback, restrictive browser policies and actual VNC shortcut launch.
- Genuine package not rerun this turn; previous 1.3.1 genuine-package checks
  passed on both architectures. Physical 32-bit PC/high-DPI multi-monitor
  transitions not tested. EXEs remain unsigned. No release published.

### Exact next step

Close the older upgrader and run `dist\VectorUp-1.4.0-win64.exe` (win32 on a
32-bit PC). Review the startup fade and new tickboxes with your saved shops;
click or press Escape to skip the intro. After manual BO backup and closing
Vector on ONE test till, check the planned destination, upgrade it, and verify
local POS backups and Vector's own next-start upgrade. Record live results
here. Publish EXEs with SHA-256 notes when a release is requested.

## Handoff log

- **2026-10-09 - Codex (GPT-6), 1.4.0:** original Koenekt/Vector branding,
  full-logo startup fade with click/Escape dismissal, rounded antialiased ticks,
  mixed/disabled states, focus/scroll retention, selection counts and modern
  geometric theme. Fixed small-window activity/footer clipping. Both Python
  architectures: 64 unit tests OK (1 real-package skip), expanded synthetic GUI
  checks passed. Both EXEs built, assets/startup visually checked. No live shop
  or till upgrade; no release published. Next: run 1.4.0 and inspect UI, then
  verify one closed test till's backup/copy/Vector upgrade.


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
