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

   **Shops with more than one back office.** There are two layouts, and they
   are handled differently:

   - *The main server* runs `RP_BACK.exe` from the same folder that holds the
     data (`Ramset.dat`). Several such back offices can sit on one machine,
     in folders called anything (`Liquor`, `Retail Liq`...). Each is **its own
     shop** in the list.
   - *Secondary back offices* run `RP_BACK.exe` from their own folder but point
     at the main server's data (`AdminDataDirectory` in their
     `VectorAdminLocal.ini`). They need the new files in their own folder on
     every upgrade, so each is an **extra back office** of the shop whose data
     it uses.

   **Find back offices** (button, or right-click a shop) scans that shop's
   server for folders holding `RP_BACK.exe` - the folder name does not matter -
   and sorts what it finds: a folder with its own `Ramset.dat` is offered as a
   *New shop*; one that uses a listed shop's data is offered as a *Back office
   of* that shop; one it cannot place is shown unticked. Tick what you want and
   press *Add ticked*. *Also scan this shop's network...* additionally looks at
   the other PCs on the shop's network (one quick connection to each address on
   the same /24, then lists the shared folders of the PCs that answer). It only
   lists folders and reads two small settings files - it never writes to
   anything - but it asks first because security software may notice it. A back
   office can only be found if its folder is **shared** on the network.

   **Add back office** adds one by hand (also right-click a shop, *Add another
   back office...*): give it a name and the shared folder that PC runs
   `RP_BACK.exe` from (for example `\\OFFICE2\Liquor`); *Check folder* tells you
   whether it is reachable and holds `RP_BACK.exe`. Each extra back office
   appears under the main one as *Back office 2, 3, 4...* with its own tick and
   result, gets exactly the same back-office files, and can be upgraded alone,
   ticked, or with the whole shop. Double-click one to edit it; right-click to
   remove it from the list (nothing on that PC is touched).
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

The full Koenekt logo fades in and out briefly at startup. Click it or press
Escape to continue immediately. The main window uses the supplied Koenekt and
Vector logos, geometric accents and rounded tickboxes. A dash marks a partly
ticked shop; grey boxes mark tills without a copy folder. Click a checkbox or
select its row and press Space. The destination count updates with your ticks.

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

## Using 1.5 and the original 1.4 side by side

1.5 adds extra back offices and *Find back offices*; 1.4.0 is the original
without them. Both are on the [releases page](../../releases) and you can keep
either. They can even share one settings folder: they see the same shop list.
1.5 keeps extra back offices in a separate file, `shops_extra.json`, because
1.4 rewrites `shops.json` from a fixed set of fields every time it runs and
would silently delete anything else in it. Opening, editing or closing 1.4 on
that folder therefore cannot erase your extra back offices - 1.4 just does not
show them. (If 1.4 renames a shop's folder, its extras no longer attach to it.)

## Build from source

Python 3.14 (Windows), tkinter included. No Python runtime dependencies.
Get package needs an installed Microsoft Edge or Google Chrome browser.
Brand PNGs in `assets/` are bundled into both portable EXEs. Preparing new
brand assets uses Pillow only during development; see `assets/README.md`.

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
local folders, per-till / per-back-office / extra-back-office targeting, finding
back-office folders (against made-up folders and fakes, plus the real Windows
share-listing call on one PC), sharing a settings folder with the genuine 1.4.0
code, window drag-and-drop using posted `WM_DROPFILES` messages, both frozen
exes starting and unpacking.
Not yet verified on real shops: a drag straight from Explorer, a copy to a
live shop share, and *Find back offices* on a real server or network. Try one
till, and one shop's scan, first.

MIT licensed. © Koenekt (Pty) Ltd.
