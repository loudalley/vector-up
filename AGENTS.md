# Shared working rules for Codex / ChatGPT, Claude and Cursor

Project: **Vector-Up by Koenekt** - a free tool that pushes Vector (Ramset)
POS and back-office upgrades to many shops by plain file copy.

- Local repo: `C:\Projects\koenekt-upgrade-tool` (edit the real source here,
  never in a temporary copy or an assistant's scratch workspace)
- GitHub: `loudalley/vector-up` - **PUBLIC**, branch `master`
- Sister project: the Koenekt Reporter, `C:\Projects\koenekt-daily-report`
  (private). Do not edit it from here. This repo carries its own copy of the
  till helpers (`techtool/tillops.py`, `techtool/terminals.py`).

This file is the single source of truth for the shared rules. Each assistant
has a thin entry point that points here and must not restate or fork them:

| Assistant | Entry point |
|---|---|
| Codex / ChatGPT | `AGENTS.md` (this file, read natively) |
| Claude | `CLAUDE.md` |
| Cursor | `.cursor/rules/handoff.mdc` (always applied) |

## Required handoff routine - ALWAYS, EVERY TIME

The user works with several assistants (Codex/ChatGPT, Claude, Cursor) and
themes and edits in all of them. Every change of hands MUST be recorded and
the user MUST be told. This is not optional and not only for big changes.

1. **Start of work:** read `README-HANDOFF.md`, then `git fetch origin` and
   `git status`. If `master` is behind `origin/master`, `git pull --ff-only`
   before touching anything. If it has diverged, or the tree is dirty with work
   that is not yours, **stop and tell the user** - do not reset, force-pull or
   overwrite. Verify the note against the actual files; it is not a full diff.
2. **Before handing back:** update `README-HANDOFF.md` - date and which
   assistant, version, what changed and why, tests actually run (and their
   result), what was NOT verified, and the exact next step. Keep **one**
   current-state section plus a short dated entry in the log. Do not create a
   competing per-assistant handoff file.
3. **Commit and push:** read what is staged (`git status`, `git diff --stat`),
   commit, then `git push origin master`. Unpushed work is invisible to the
   others. If a push fails on authentication, commit locally and say so; never
   put tokens in remote URLs, files or docs.
4. **Notify the user, every time:** end your reply by stating plainly that the
   handoff note was updated, what you changed, and whether it was pushed. Say
   if anything was only built and not tested on a real shop or till. If you
   could not update the handoff or push, say that instead.

## Git rules

- Never force-push, rewrite published history, or `git reset --hard` without
  the user's say-so. The repo is public: history cannot be taken back.
- Commit identity (do not write to the user's git config):
  `git -c user.name="William (Koenekt)" -c user.email="loudalley@users.noreply.github.com" commit ...`
  Mention which assistant made the change in the message or handoff entry.
- Read `git status` before every `git add`. Avoid `git add -A` blindly.

## Branches and releases (two lines of the app, both usable)

The owner wants the original app AND the multi-back-office spin-off available,
and either usable:

| Line | Branch | Release tags | What it is |
|---|---|---|---|
| Original | `original-1.4` | `v1.4.0` | Vector-Up as first published: shops, tills, one back office per shop. Fixes only. |
| Spin-off | `multi-backoffice` | `v1.5.0`+ | Adds extra back offices and Find back offices. |

`master` currently points at the same commit as `multi-backoffice` (the latest).
Do NOT move or reset `master`, and do not force-push any branch, without the
owner saying so - ask first. Releases are cut from the branch they belong to:
bump `VERSION`, `build_portable.bat`, `gh release create vX.Y.Z` with both EXEs
and SHA-256 in the notes. A fix that belongs to both lines goes on
`original-1.4` first, then is merged or cherry-picked into `multi-backoffice`.

## PUBLIC repo - what must never be committed

- **No credentials or secrets** of any kind. The standard till VNC password
  `1234` is a documented, deliberate default (`techtool/tillops.py`) and is the
  only exception; it is overridable per shop.
- **No real shop data**: no customer/shop names, real IPs or UNC paths, no
  `.dat` files, no copies of a client's back office or `VectorTerminals.ini`.
  Tests use synthetic values (`10.0.0.x`, "Shop 0").
- **No binaries in git.** Exes go on GitHub Releases only
  (`gh release create vX.Y.Z dist\VectorUp-X.Y.Z-win64.exe dist\VectorUp-X.Y.Z-win32.exe`),
  with SHA-256 in the notes. `dist/`, `build/`, `*.spec`, `*.log` and
  `VectorUp_data/` are ignored; keep it that way.
- Vector's own package zips are the client's/vendor's files - do not commit them.

## What the tool does (rules you must not break)

- One window; the user drops Vector's upgrade **zip** containing `BO\` and
  `POS\`. Only the OUTER zip is extracted (`techtool/package.py`). `Utilities\`
  and `InstallationNotes.txt` are never copied.
- BO files -> each shop's back-office folder; POS files -> each till folder read
  from that shop's `VectorTerminals.ini`. Per till, per back office, per shop,
  ticked, or ALL. **Nothing is ever deleted at a destination.**
- **Two kinds of "more than one back office"** (the owner's layout, 2026-10-24):
  (1) the MAIN SERVER runs RP_BACK.exe from the same folder as the data
  (`Ramset.dat`); several such back offices can sit on one machine in folders
  named anything (`Liquor`, `Retail Liq`) - each is its OWN SHOP in the list.
  (2) SECONDARY back offices run RP_BACK.exe from their own folder but their
  `VectorAdminLocal.ini` `AdminDataDirectory` points at the main server's data.
  They need the new files in their own folder on EVERY upgrade - each is an
  EXTRA back office of the shop whose data it uses. Never identify either by
  folder name: `RP_BACK.exe` is the marker, `Ramset.dat` means own data.
- **Extra back offices** (`store.add_extra_bo`, `BackOfficeDialog`, or found by
  `FindBackOfficesDialog`) are plain BO targets: same BO payload, same
  marker-last rule, row keys `<shop>:b<id>` (main is `bo`, tills are `t<n>`).
  Their `id` is stable and NEVER reused (`extra_seq` only grows) so a stale
  tick/result cannot land on another back office. Compare folders with
  `store._norm` (it strips the trailing slash on UNC share roots); never
  `os.path.normpath` alone. A drive-letter path for a remote shop's extra back
  office must warn: it would copy onto this PC.
- **Discovery (`techtool/discovery.py`) is read-only and opt-in.** It only
  lists folders and reads `VectorAdminLocal.ini`; it must never write to, or
  copy onto, a scanned machine. Step one scans only the chosen shop's own
  server (NetShareEnum level 1 + a depth-2 walk with a time limit). The subnet
  sweep (TCP 445 to the server's /24) runs only after an explicit confirm each
  time, and never beyond that /24. Never store credentials; use the Windows
  session the user already has. A found folder is classified `own` (has
  Ramset.dat: new shop), `secondary` (its data dir matches a listed shop: that
  shop's extra), `unclear` (shown, unticked), or `listed` (already in the list,
  not selectable). Only SHARED folders can be found.
- Till folders can be UNC shares, or absolute drive folders for a local
  back-office installation. Never apply a remote shop's drive path to the
  technician PC. Named tills without copy folders must remain visible with a
  clear status, and be excluded from copying. Find each shop's own INI; never
  silently use one global local INI for multiple remote shops.
- The inner `BO_*.zip` / `POS_*.zip` are copied as files, never opened; Vector
  unpacks them itself on next start.
- `_UpgradeRequired` triggers Vector's upgrade. It must be copied **LAST** and
  **withheld if any other file failed**, so a half-copied till cannot start
  upgrading. (`engine.copy_payload`, `package.Payload.files`.)
- Before a POS upgrade, back up ONLY `postrans.dat` and `posdebtor.dat`,
  read-only from the till, to the tool's local `VectorUp_data\POS backups\`
  (fallback settings folder when necessary), under named shop/till/timestamp
  folders. If either file is missing or cannot be backed up, nothing is copied
  to that till; continue with the others. Do not back up replaced upgrade files.
  Back-office backups are manual; Vector handles its own upgrade backups.
- Every destination is checked reachable before copying. Never `makedirs` a
  destination root - a mistyped path must not become a stray folder.
- One bad shop/till never stops the rest. Stop button works between targets.
- **Portable:** settings live in `VectorUp_data\` beside the exe (fallback
  `%LOCALAPPDATA%\Koenekt\VectorUp`). Staged files go to `%TEMP%`, never the
  stick. Keep it working as a single-file exe in both 32-bit and 64-bit.
- **Free for all:** no licence checks, no phone-home, no telemetry.
- Til/INI parsing is read-only. Never write `VectorTerminals.ini` or modify live
  `.dat` databases. The only database access here is reading the two POS files
  above for backup; direct `.dat` files in upgrade payloads are not copied.

## Technical traps

- **Never call Tk from inside the Win32 window procedure** (`techtool/dnd.py`).
  Doing so aborts Python 3.14 intermittently ("PyEval_RestoreThread ... GIL
  released"). The procedure only touches ctypes and a deque; the app's timer
  calls `DropTargets.poll()`. Widget handles are cached in `install()`.
- Worker threads must not touch Tk; they `queue.put(...)` and `App._pump`
  applies it on the Tk thread.
- `tests/check_techtool_gui.py` posts real `WM_DROPFILES` messages. A real drag
  from Explorer has **not** been verified yet.
- Settings JSON is read with `utf-8-sig` (Notepad adds a BOM) - keep that.
- **1.5 and 1.4.x share one settings folder, so `shops.json` must stay in the
  1.4.x shape.** 1.4.x rebuilds every shop from a fixed key set on each load and
  save and silently deletes any other key (verified against the real v1.4.0
  code). Anything 1.5 adds per shop (extra back offices, their id counter) lives
  in `shops_extra.json`, keyed by `store._norm(bo_path)`, which 1.4.x never
  touches. Never put a new per-shop or top-level key into `shops.json`; add it
  to the companion file. `tests/test_compat_14.py` runs the genuine v1.4.0 code
  from the git tag against a 1.5 folder - keep it passing (it skips if the tag
  is missing, which is not a pass).

## Theming / UI edits (the user will do this in several tools)

- Colours and fonts are constants at the top of `techtool/gui.py`
  (`GREEN`, `DARK`, `GREY`, `LIGHT`, `RED`, `FONT`). Brand: Koenekt green
  `#73C509`, dark `#17251F`. Change them there, not scattered through widgets.
- The header text is `VECTOR-UP  by Koenekt`; the product name is
  `techtool/__init__.py: APP_TITLE`. Keep the name "Vector-Up by Koenekt".
- Icon: `app_icon.ico` (bundled into the exe by `build_portable.bat`).
- After any UI change run the GUI check (below) and look at the real window.
  Tk layout bugs (hidden buttons, clipped text) do not show in unit tests.

## Run, test, build

```
python techtool_main.py                 # run from source
python tests/test_techtool.py           # unit tests (run as a file, not -m)
python tests/check_techtool_gui.py      # opens the real window; needs a desktop
build_portable.bat                      # both exes -> dist\ (PyInstaller in py -3.14 and py -3.14-32)
```

- Set `KUT_REAL_ZIP` to a genuine Vector package to run the extra real-package
  test. Do not commit that zip.
- Bump `VERSION` in `techtool/__init__.py` for every release; the exe names and
  the release tag follow it.
- State honestly what was and was not tested. "Built" is not "tested on a till".
