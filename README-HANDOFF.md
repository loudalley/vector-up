# Vector-Up by Koenekt - shared handoff (Codex/ChatGPT, Claude, Cursor)

Rules for using this file are in `AGENTS.md`. Update **Current state** and add
a dated line to the **Handoff log** every time you hand work back, then commit,
push, and tell the user.

## Current state

- **Date / assistant:** 2026-10-24, Claude (release 1.5.0).
- **Version:** 1.5.0 is the latest RELEASE (both portable EXEs):
  https://github.com/loudalley/vector-up/releases/tag/v1.5.0. It is the
  multi-back-office spin-off line. The ORIGINAL line is 1.4.0
  (https://github.com/loudalley/vector-up/releases/tag/v1.4.0); both stay
  available and either can be used.
- **Two lines / branches:** `original-1.4` (the original, tag `v1.4.0`,
  fixes only) and `multi-backoffice` (the 1.5 line, tag `v1.5.0`). `master`
  currently points at the same commit as `multi-backoffice`. The owner asked
  for the spin-off to be a branch "so we can use either"; whether `master`
  should go back to the original line is THEIR call and would rewrite public
  history - do not move `master` without being told (see AGENTS.md).
- **SHA-256 (1.5.0):**
  - win64 `C1BE66E0598FEAC7EF2A04E540413A02D0B3EF99D67062EE3E89CCFA99704FCB`
  - win32 `6260355FEA06C07119033FA9C175444AF92590577AA186F9BD70550DD6CCBE9E`
- **Repo:** https://github.com/loudalley/vector-up (PUBLIC), `master`.
- **Local:** `C:\Projects\koenekt-upgrade-tool`. Sister project not edited.

### Using 1.5 and the original 1.4.x side by side (settings are shared)

PROBLEM FOUND: the original 1.4.0 rebuilds every shop from a fixed key set on
each load/save and silently deletes any other key - verified by running the
real v1.4.0 code on a 1.5 `shops.json` (extras gone). Sharing one settings
folder would have wiped a technician's extra back offices without a word.

FIX (in 1.5.0): `shops.json` keeps exactly the 1.4.x shape; extra back offices
and their id counter are stored in a companion file `shops_extra.json`
(`store.save` / `store.load`), keyed by `store._norm(bo_path)`, which 1.4.x
never reads or writes. Both versions see the same shop list; 1.4.x simply does
not show extras and cannot erase them. Behaviours worth knowing:
- A shop removed in 1.4 and re-added at the same folder gets its extras back
  (the companion entry is untouched until 1.5 next saves).
- If 1.4 changes a shop's folder, its extras no longer attach (matched by
  folder). 1.5 drops the orphan entry on its next save.
- A damaged companion file loads as "no extras" and is copied to
  `shops_extra.json.bad` before being overwritten.
- Early dev builds that wrote `extra_bo` inline still load and migrate.
- `tests/test_compat_14.py` (15 tests) runs the GENUINE v1.4.0 code, exported
  from the git tag into a temp folder and run in a subprocess, against a 1.5
  folder: open/close, edit + add a shop, remove, remove + re-add, id reuse. It
  skips (not passes) if the tag is missing.

### 1.5.0: extra back offices + Find back offices (the spin-off line)

The owner's layout (told to us 2026-10-24, treat as ground truth):

- **Main server:** RP_BACK.exe runs from the SAME folder that holds the data
  (`Ramset.dat`). Several such back offices can sit on ONE machine in folders
  named anything (`Liquor`, `Retail Liq`...). Each is its OWN SHOP in the list.
- **Secondary back offices:** run RP_BACK.exe from their OWN folder, but their
  `VectorAdminLocal.ini` `AdminDataDirectory` points at the main server's data.
  They need the new files in their own folder on EVERY upgrade, so each is an
  EXTRA back office of the shop whose data it uses.

So folder names mean nothing: `RP_BACK.exe` marks a program folder, `Ramset.dat`
means it has its own data, and `AdminDataDirectory` ties a secondary to its shop.

- A shop can list extra back offices (`shop["extra_bo"]` = `{id, name, path}`).
  **Add back office** button, or right-click a shop / its main Back office row.
  Rows show under the main one as "Back office 2 - <name>", 3, 4... with their
  own tick, Result and "Upgrade this back office only". Double-click edits;
  right-click removes (from the list only; nothing on the PC is touched).
- They are ordinary BO targets (`engine.build_plan`, keys `<shop>:b<id>`): same
  BO payload, `_UpgradeRequired` last and withheld on failure, reachability
  check first, nothing deleted. Selection supports one / ticked / all via
  `want_extra`. Editing a shop keeps its extras. Limit 20 per shop.
- Ids are never reused (`extra_seq`), so a stale untick or result cannot land
  on a different back office.
- The dialog has a threaded **Check folder** (`engine.inspect_bo_folder`):
  reachable? contains `RP_BACK.exe`? Warns before saving a folder without it,
  refuses a duplicate or the shop's main folder, and warns if a drive-letter
  path (`C:\...`) is used for a remote shop (it would copy onto THIS PC).
- **Bug fixed along the way (older than this change):** `\\pc\share` and
  `\\pc\share\` normalised differently (`os.path.normpath` keeps the trailing
  slash on a UNC share root), so the same folder typed two ways escaped
  duplicate detection in the planner and in Reporter import. `store._norm` now
  strips it and `engine.build_plan` uses it. POS-backup fingerprints still use
  the old normpath on purpose (changing it would rename existing backup folders).
- **Find back offices** (`techtool/discovery.py`, `FindBackOfficesDialog`;
  toolbar button, or right-click a shop / its main Back office row):
  - Scans the chosen shop's SERVER: lists its disk shares (NetShareEnum level 1
    via ctypes - no admin rights; admin shares like `C$` are left out), walks
    each share to depth 2 with a 25 s limit per host, looks for `RP_BACK.exe`
    (case-insensitive, skips Logs/Backup/POS_Data_Preparation/hidden shares).
  - Classifies each hit: `own` (has `Ramset.dat`) -> offered as a NEW SHOP;
    `secondary` (its `VectorAdminLocal.ini` data dir matches a listed shop,
    compared with `store._norm`) -> that shop's EXTRA back office; `unclear`
    (no ini, a drive-letter data dir, or an unlisted shop) -> shown, unticked,
    adds as an extra of the shop the scan started from; `listed` -> greyed.
  - **"Also scan this shop's network..."** is separate and asks first every
    time: one TCP connect to port 445 on each address of the server's /24, then
    the same share listing on the PCs that answer. Read-only; never beyond the
    /24; no credentials stored. Local-path shops have no server to scan and say so.
  - Adding: new shops get the folder name (with the host appended if a shop of
    that name exists); a found shop reads its own tills and upgrades like any
    other. Re-adding is refused with a reason.
  - Only SHARED folders can be found. An unshared folder, a PC that is off, or
    SMB blocked by a firewall/VPN is simply not seen; add those by hand.
- Tests: `tests/test_extra_bo.py` 26 OK (store, planning, real copies,
  unreachable/locked extras, folder inspection, trailing-slash regression);
  `tests/test_discovery.py` 37 OK (UNC parsing, folder walk incl. depth /
  skip-dirs / deadline / cancel, ini reading incl. BOM and ANSI, classification,
  a real-folder "one machine, several back offices" layout, discover() with
  fakes, subnet sweep with an injected connect, plus the REAL NetShareEnum call
  on this PC and on a missing host); `tests/test_techtool.py` 64 OK (1 real-
  package skip). `tests/check_techtool_gui.py` drives the real window and the
  real dialogs: extras (add/duplicate/one row/unticked/ALL/edit/remove/ids/tick
  box), then Find back offices with a fake scan (kinds sorted, listed row not
  tickable, two-step scan with the network confirm, add as shop / extra, the
  found shop reads its tills and upgrades, re-adding refused) and the new
  buttons visible at minimum size. 6/6 passes after the fix below.
- Test flake fixed: the old "Escape dismisses the startup logo" assertion needs
  keyboard focus and failed whenever another window had it (2 of ~9 runs);
  the test now calls `focus_force()` first. The app was not at fault.
- Visually inspected the real window with extras and the Find dialog (fixed a
  stray progress-bar block and a clipped note while doing so).
- Release checks (1.5.0): all unit suites OK (`test_techtool` 64 - also run
  with the real Vector package, nothing skipped - `test_extra_bo` 26,
  `test_discovery` 37, `test_compat_14` 15); window check passed twice; both
  frozen EXEs (win64 14 MB, win32 11.1 MB) started from a fresh folder with a
  seeded settings folder (1.4-shaped `shops.json` + `shops_extra.json`), showed
  "Back office 2 / 3" loaded from the companion file, and opened the real
  package. The frozen EXEs were NOT driven through Find back offices (the
  dialog was tested from source).
- NOT verified: any of this against a real shop network. The real share
  listing was only run on this PC (it has one share) and a missing host; the
  subnet sweep, listing a real server's shares, and `VectorAdminLocal.ini`
  contents from a real secondary back office are only covered by fakes and
  made-up files - the ini key/section layout is taken from one single-back-
  office dump. Whether Vector upgrades secondary copies correctly or needs an
  order/version match across back offices. The right-click popup itself.
- Next: the user tries Find back offices on ONE real shop's server and reports
  what it finds (and what it misses). Open question for the owner: should
  `master` stay as the latest (= the 1.5 line) or go back to the original, with
  the spin-off only on `multi-backoffice`? (Both are already preserved as
  branches and tags either way.)

### Latest handoff: 1.4.0 release published

- 2026-10-09, Codex (GPT-6): user requested immediate release and push. Fetched
  origin and confirmed clean synchronized master and VERSION 1.4.0. Published
  existing tested builds as v1.4.0, tagged at `7d75c5e`, with SHA-256 release
  notes. GitHub confirms both assets uploaded, matching sizes and hashes, a
  public non-draft/non-prerelease release, and v1.4.0 as latest.
- Release checks: both build logs successful; PE headers confirm x64/x86;
  both archives contain all three brand PNGs; SHA-256 upload digests match.
  `git diff --check` passed. No app tests or builds rerun; prior results below
  remain historical. No real shop/till test. Next: download the appropriate
  EXE and verify one closed test till as described below.
- Published SHA-256:
  - win64: `22726357DF9B0E8DF7E652943C2A192C7DC1ECA44D1D08B03918FF1C61647BEC`
  - win32: `23C8AD1E0D3F0D10FAB3019095FFEF9D7B830A80E70288383331DC2692E6057F`

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
  transitions not tested. EXEs remain unsigned.

### Exact next step

Download `VectorUp-1.4.0-win64.exe` from the v1.4.0 release (win32 on a 32-bit
PC), close the older upgrader and run it. Review the UI with your saved shops;
click or press Escape to skip the intro. After manual BO backup and closing
Vector on ONE test till, check the planned destination, upgrade it, and verify
local POS backups and Vector's own next-start upgrade. Record live results
here. Both EXEs and SHA-256 notes are now published.

## Handoff log

- **2026-10-24 - Claude, 1.5.0 released (spin-off line):** version bumped,
  both EXEs built and published as `v1.5.0` with SHA-256 notes. Created
  branches `original-1.4` (at the 1.4.0 commit) and `multi-backoffice` (the 1.5
  line); `master` unchanged. Before releasing, found that the original 1.4.0
  silently erases extra back offices from `shops.json`, so extras now live in
  `shops_extra.json` and 1.4.x and 1.5 can share one settings folder; new
  `tests/test_compat_14.py` proves it with the genuine 1.4.0 code. Unit tests
  142 OK, window check 2/2, both frozen EXEs smoke-tested. Not tried on a real
  shop network or real tills. Next: try Find back offices on one real server;
  owner to say whether `master` should revert to the original line.

- **2026-10-24 - Claude, unreleased (after 1.4.0), part 2:** Find back offices.
  The owner explained the layouts (main server = working folder is data folder,
  several can share one machine under names like Liquor / Retail Liq = separate
  shops; secondary back offices have their own program folder pointing at the
  main server's data and need the files on every upgrade = extras). Built
  `techtool/discovery.py` + `FindBackOfficesDialog`: scans the shop's server
  (read-only), classifies new shop / extra / unclear / listed, optional
  confirmed subnet sweep. New `tests/test_discovery.py` (37 OK); extras 26 OK;
  `test_techtool.py` 64 OK; window check 6/6 (also fixed a focus flake in its
  old Escape test). No EXEs built or released; VERSION unchanged. NOT tried on
  any real shop network. Next: try it on one real server, then release 1.5.0.

- **2026-10-24 - Claude, unreleased (after 1.4.0):** extra back offices added by
  hand (second/third/fourth RP_BACK folders) as ordinary BO targets with their
  own tick/result/row upgrade, a Check folder dialog and duplicate/drive-path
  guards; fixed UNC trailing-slash duplicate detection. New `tests/test_extra_bo.py`
  (26 OK), `test_techtool.py` 64 OK, extended GUI check passed (3/3 re-runs, one
  focus-related flake on the first run of the old Escape assertion). No EXEs
  built or released; VERSION unchanged. Not tried on a real multi-back-office
  shop. Automatic detection NOT built. Next: user describes real layout, then
  release 1.5.0 or build detection.

- **2026-10-09 - Codex (GPT-6), 1.4.0:** published latest GitHub release
  v1.4.0 with both portable EXEs and SHA-256 notes. Verified build logs, PE
  architectures, bundled branding, uploaded asset sizes/digests and latest
  release status. Updated handoff only; diff check passed, no tests/builds
  rerun and no real till test. Next: download and verify one closed test till.

- **2026-10-09 - Codex (GPT-6), 1.4.0:** requested GitHub push confirmed the
  source commit `cfbf823` was already on origin/master. Updated this handoff
  note only; repository/source checks and diff whitespace check passed. No
  tests/builds rerun, no real till test and no release published. Next: review
  1.4.0, then verify one closed test till's backups/copy/Vector upgrade.

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
