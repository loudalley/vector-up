# Vector-Up by Koenekt

Free tool for technicians: push a Vector (Ramset) **POS** and **back-office**
upgrade to many shops by plain file copy. Drop the upgrade package on the
window, then upgrade one till, one back office, one shop, the ticked ones, or
everything.

## Download

Portable single-file exes, no install. Get them from the
[latest release](../../releases/latest):

| PC | File |
|---|---|
| 64-bit Windows | `VectorUp-<version>-win64.exe` |
| 32-bit Windows | `VectorUp-<version>-win32.exe` |

The exes are not code-signed, so Windows SmartScreen or antivirus may warn on
first run ("More info" then "Run anyway"). Check the SHA-256 in the release
notes if you want to confirm the file.

## Using it

1. **Add your shops** (name + the back-office folder holding `Ramset.dat` and
   `VectorTerminals.ini`, e.g. `\\SERVER\Ramset`). The tills are read from that
   INI. Handles 20+ shops. Local installations also work: select the local
   back-office folder containing the INI. A local shop's absolute till folder
   is supported as well as UNC network shares. Named tills without a usable
   `TerminalLocation` remain visible with a status message and cannot be
   selected for copying. A drive path inside a remote shop's INI is never
   treated as a folder on the technician's PC; remote tills need UNC paths.
2. **Get or drop Vector's upgrade zip** (the one containing `BO\` and `POS\` folders)
   on the window. It is unpacked and sorted for you. `Utilities\` and
   `InstallationNotes.txt` are never copied. **Get package** opens
   [Vector's downloads](https://www.vectortech.co.za/dwnlds/login.php) in a small
   Edge browser window (Chrome is a fallback). The installer supplies the login
   details directly there. Choose an upgrade ZIP; once its download finishes,
   it loads automatically into Vector-Up. Partial downloads are not imported.
   The browser uses a separate temporary profile with password saving off;
   its profile and downloads are removed when Vector-Up closes. If browser
   policies prevent automatic import, download the ZIP normally and drop it
   here or use **Browse ZIP**.
3. **Upgrade.** Tick what you want (a whole shop, just its back office, just
   one till) and press *Upgrade ticked*, or select a row and press *Upgrade
   selected row* (right-click works too), or *Upgrade ALL*. *Check* shows what
   would be copied and whether each PC is reachable, without copying.
4. **VNC shortcuts** for every till can be created in one click (default
   password `1234`, overridable per shop).

You can also drag the zip onto the exe icon to start with it loaded.

**Close Vector on the PCs being upgraded first, and manually back up the back
office.** Locked files are reported per row, not skipped silently.

## How the copy works

Vector's own notes say: copy all the files in the BO or POS folder over the
application folder, overwriting. Vector then upgrades itself the next time it
starts. So:

- BO files go to each back-office folder, POS files to each till share.
  Nothing is deleted.
- The inner `BO_*.zip` / `POS_*.zip` are copied as files, never opened.
- `_UpgradeRequired` is the file that tells Vector to start upgrading. It is
  copied **last**, and **not at all** if any other file failed, so a half-copied
  till cannot start upgrading. Run it again to finish.
- Before copying to a till, only `postrans.dat` and `posdebtor.dat` are backed
  up locally. In the portable EXE they go to
  `VectorUp_data\POS backups\<shop>\<till - number - identifier>\<timestamp>\`.
  The identifier separates tills with the same name. **Open POS backups**
  opens this folder. Both data files must exist and be saved successfully;
  otherwise that till is skipped before any upgrade files are copied, while
  other destinations continue. A fresh timestamp keeps every backup separate.
- There are no automatic back-office or replaced-file backups. Make the
  back-office backup manually; Vector handles its own upgrade backups.
- Live databases are never written by Vector-Up; direct `.dat` files supplied
  in a package are excluded from the copied payload.
- Every destination is checked reachable first. A mistyped path is reported,
  never created.

## Portable settings

Settings (shops, ticks, `upgrade.log`) are saved in a `VectorUp_data` folder
**beside the exe**. Copy the exe and that folder together to move to another
PC. POS backups are also kept under that folder. If the exe's folder is
read-only, settings go to
`%LOCALAPPDATA%\Koenekt\VectorUp` instead.

## Build from source

Python 3.14 (Windows), tkinter included. No Python runtime dependencies.
Get package needs an installed Microsoft Edge or Google Chrome browser.

```
python techtool_main.py                  # run from source
python tests/test_techtool.py            # unit tests
python tests/check_techtool_gui.py       # opens the real window, needs a desktop
python tests/check_vector_download.py    # real browser -> app, synthetic local ZIP
build_portable.bat                       # both exes (needs PyInstaller in each Python)
```

Set `KUT_REAL_ZIP` to a genuine Vector package to run the extra test against it.

## Status

Tested: package unpacking against a real Vector package, 20-shop copy runs on
local folders, per-till / per-back-office targeting, window drag-and-drop using
posted `WM_DROPFILES` messages, both frozen exes starting and unpacking.
Not yet verified on real tills: a drag straight from Explorer and a copy to a
live shop share. Try one till first.

MIT licensed. © Koenekt (Pty) Ltd.
