"""Vector-Up by Koenekt: package loading, shop store, copy engine, VNC.
Run: python tests/test_techtool.py
"""
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from techtool import downloads, engine, package, store, terminals, tillops

# Optional: point KUT_REAL_ZIP at a genuine Vector package to test against it.
REAL_ZIP = os.environ.get("KUT_REAL_ZIP", "")


def _write(path, text="x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def make_package(path, bo_files=None, pos_files=None, wrap=None, extra=True):
    """A zip laid out like Vector's: BO/, POS/, Utilities/, notes."""
    bo_files = bo_files or {
        "RP_BACK.exe": "bo-exe", "VectorInitialiser.dll": "d",
        "BO_2_24_0005.zip": "inner-bo", "_UpgradeRequired": "BO_2_24_0005.zip"}
    pos_files = pos_files or {
        "RPOS25.exe": "pos-exe", "VectorInitialiser.dll": "d",
        "POS_2_14_0003.zip": "inner-pos",
        "_UpgradeRequired": "POS_2_14_0003.zip"}
    pre = (wrap + "/") if wrap else ""
    with zipfile.ZipFile(path, "w") as zf:
        for n, c in bo_files.items():
            zf.writestr(f"{pre}BO/{n}", c)
        for n, c in pos_files.items():
            zf.writestr(f"{pre}POS/{n}", c)
        if extra:
            zf.writestr(f"{pre}Utilities/fix.bat", "x")
            zf.writestr(f"{pre}InstallationNotes.txt", "notes")


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.base = self.td.name
        self.scratch = os.path.join(self.base, "scratch")
        os.makedirs(self.scratch)

    def tearDown(self):
        self.td.cleanup()

    def _pkg(self, **kw):
        z = os.path.join(self.base, "pkg.zip")
        make_package(z, **kw)
        return package.load(z, self.scratch)

    def test_zip_is_sorted_into_bo_and_pos(self):
        p = self._pkg()
        self.assertEqual(os.path.basename(p.bo.dir), "BO")
        self.assertEqual(os.path.basename(p.pos.dir), "POS")
        self.assertEqual(len(p.bo.files()), 4)
        self.assertEqual(p.bo.label(), "BO_2_24_0005")
        self.assertEqual(p.pos.label(), "POS_2_14_0003")
        self.assertEqual(sorted(p.ignored),
                         ["InstallationNotes.txt", "Utilities"])
        self.assertIn("Not copied", p.summary())

    def test_marker_is_always_last(self):
        p = self._pkg()
        self.assertEqual(p.bo.files()[-1], "_UpgradeRequired")
        self.assertEqual(p.pos.files()[-1], "_UpgradeRequired")

    def test_inner_zips_are_copied_not_opened(self):
        p = self._pkg()
        self.assertIn("BO_2_24_0005.zip", p.bo.files())
        self.assertEqual(
            Path(p.bo.dir, "BO_2_24_0005.zip").read_text(), "inner-bo")

    def test_wrapper_folder_is_seen_through(self):
        self.assertEqual(len(self._pkg(wrap="Vector_Release").bo.files()), 4)

    def test_already_unzipped_folder(self):
        z = os.path.join(self.base, "pkg.zip")
        make_package(z)
        folder = os.path.join(self.base, "unz")
        zipfile.ZipFile(z).extractall(folder)
        p = package.load(folder, self.scratch)
        self.assertTrue(p.bo and p.pos)

    def test_bo_only_package(self):
        z = os.path.join(self.base, "bo.zip")
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("BO/RP_BACK.exe", "x")
        p = package.load(z, self.scratch)
        self.assertIsNotNone(p.bo)
        self.assertIsNone(p.pos)
        self.assertIn("POS:  not in this package", p.summary())

    def test_zip_without_bo_or_pos_is_refused(self):
        z = os.path.join(self.base, "junk.zip")
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("readme.txt", "x")
            zf.writestr("Utilities/a.dll", "x")
        with self.assertRaises(ValueError) as cm:
            package.load(z, self.scratch)
        self.assertIn("no BO or POS", str(cm.exception))

    def test_loose_file_is_refused(self):
        f = os.path.join(self.base, "a.dll")
        _write(f)
        with self.assertRaises(ValueError):
            package.load(f, self.scratch)

    def test_corrupt_zip_is_refused_politely(self):
        z = os.path.join(self.base, "bad.zip")
        Path(z).write_bytes(b"not a zip at all")
        with self.assertRaises(ValueError) as cm:
            package.load(z, self.scratch)
        self.assertIn("Could not open", str(cm.exception))

    def test_zip_slip_is_refused(self):
        z = os.path.join(self.base, "evil.zip")
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("../escaped.txt", "no")
            zf.writestr("BO/ok.txt", "yes")
        package.load(z, self.scratch)
        self.assertFalse(os.path.exists(os.path.join(self.base, "escaped.txt")))
        self.assertFalse(os.path.exists(
            os.path.join(self.scratch, "escaped.txt")))

    def test_new_drop_replaces_the_old_package(self):
        a = os.path.join(self.base, "a.zip")
        make_package(a)
        b = os.path.join(self.base, "b.zip")
        make_package(b, bo_files={"NEW.exe": "n"})
        package.load(a, self.scratch)
        p = package.load(b, self.scratch)
        self.assertEqual(p.bo.files(), ["NEW.exe"])

    def test_failed_replacement_keeps_loaded_package_files(self):
        previous = self._pkg()
        before = Path(previous.pos.dir, "RPOS25.exe").read_bytes()
        junk = Path(self.base, "junk.zip")
        junk.write_bytes(b"not a zip")
        with self.assertRaises(ValueError):
            package.load(str(junk), self.scratch)
        self.assertEqual(Path(previous.pos.dir, "RPOS25.exe").read_bytes(), before)

    def test_dat_files_in_payload_are_never_copied_to_live_databases(self):
        p = self._pkg(pos_files={"postrans.dat": "vendor data", "nested/other.DAT": "data",
                                 "RPOS25.exe": "exe", "_UpgradeRequired": "POS_9.zip"})
        self.assertEqual(sorted(p.pos.files()), ["RPOS25.exe", "_UpgradeRequired"])

    @unittest.skipUnless(REAL_ZIP and os.path.isfile(REAL_ZIP),
                         "set KUT_REAL_ZIP to a real Vector package to run this")
    def test_the_real_vector_package(self):
        p = package.load(REAL_ZIP, self.scratch)
        self.assertEqual(sorted(p.bo.files()), sorted([
            "BO_2_24_0005.zip", "RP_BACK.exe", "VectorInitialiser.dll",
            "_UpgradeRequired"]))
        self.assertEqual(sorted(p.pos.files()), sorted([
            "POS_2_14_0003.zip", "RPOS25.exe", "VectorInitialiser.dll",
            "_UpgradeRequired"]))
        self.assertEqual(p.bo.files()[-1], "_UpgradeRequired")
        self.assertEqual(p.bo.label(), "BO_2_24_0005")
        self.assertEqual(p.pos.label(), "POS_2_14_0003")
        self.assertEqual(sorted(p.ignored),
                         ["InstallationNotes.txt", "Utilities"])
        # the inner archives were NOT unpacked
        self.assertFalse(os.path.exists(os.path.join(p.bo.dir, "Ramset.exe")))


class TerminalDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
    def tearDown(self):
        self.td.cleanup()
    def ini(self, content, encoding="utf-8"):
        path = self.root / "vectorterminals.ini"
        path.write_text(content, encoding=encoding)
        return path
    def test_local_drive_till_is_a_copy_target_and_ini_is_unchanged(self):
        till = self.root / "till"
        till.mkdir()
        path = self.ini(f"[TERMINAL 1]\nName=TILL 1\nEnabled=True\nTerminalLocation={till}\n")
        before = path.read_bytes()
        info = terminals.read_terminals(str(self.root))
        targets = tillops.tills_for_push(info)
        self.assertEqual(len(targets), 1)
        self.assertEqual(Path(targets[0]["share"]), till)
        plan = engine.build_plan([dict(store.new_shop("Shop 0", str(self.root)), _idx=0)], True, True)
        self.assertEqual([t["key"] for t in plan["targets"]], ["0:bo", "0:t1"])
        self.assertEqual(path.read_bytes(), before)
    def test_named_slots_without_locations_stay_visible_but_are_not_targets(self):
        self.ini("[TERMINAL 1]\nName=TILL 1\nEnabled=False\nTerminalLocation=\n"
                 "[TERMINAL 2]\nName=\nEnabled=False\nTerminalLocation=\n")
        info = terminals.read_terminals(str(self.root))
        visible = tillops.tills_for_display(info)
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0]["problem"], "No till folder")
        self.assertEqual(tillops.tills_for_push(info), [])
    def test_remote_shop_drive_path_never_targets_this_pc(self):
        self.ini("[TERMINAL 1]\nName=TILL 1\nEnabled=True\nTerminalLocation=C:\\POS\n")
        info = terminals.read_terminals(str(self.root))
        info["data_path"] = r"\\10.0.0.1\BO"
        self.assertEqual(tillops.tills_for_push(info), [])
        self.assertEqual(tillops.tills_for_display(info)[0]["problem"], "Remote till needs UNC")
    def test_mapped_remote_bo_drive_does_not_allow_local_paths(self):
        import ctypes
        with patch.object(ctypes.windll.kernel32, "GetDriveTypeW", return_value=4):
            self.assertIsNone(terminals.copy_location(r"C:\POS", r"Z:\BackOffice"))
    def test_unc_tills_are_still_supported(self):
        self.ini("[TERMINAL 2]\nName=TILL 2\nLive=-1\nTerminalLocation=\\\\10.0.0.2\\POS\n")
        info = terminals.read_terminals(str(self.root))
        self.assertEqual(tillops.tills_for_push(info, {2})[0]["share"], r"\\10.0.0.2\POS")
        self.assertEqual(tillops.tills_for_push(info, {1}), [])
    def test_reference_and_relative_paths_are_not_guessed(self):
        for location in ("@1", "POS", r"C:POS", r"\POS"):
            self.assertIsNone(terminals.copy_location(location, str(self.root)))
    def test_parse_error_returns_status_instead_of_stopping_refresh(self):
        self.ini("[TERMINAL 1]\nName=TILL 1\nName=duplicate\n")
        info = terminals.read_terminals(str(self.root))
        self.assertFalse(info["available"])
        self.assertIn("Could not read VectorTerminals.ini", info["error"])
    def test_utf8_bom_and_legacy_live_are_supported(self):
        self.ini("[TERMINAL 1]\nName=TILL 1\nLive=-1\nTerminalLocation=\\\\10.0.0.2\\POS\n", "utf-8-sig")
        info = terminals.read_terminals(str(self.root))
        self.assertTrue(info["available"])
        self.assertEqual(info["enabled_count"], 1)
        self.assertEqual(len(tillops.tills_for_push(info)), 1)


class StoreTests(unittest.TestCase):
    def test_roundtrip_and_default_password(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "shops.json")
            cfg = store.load(p)
            self.assertEqual(cfg["vnc_default"], "1234")
            self.assertNotIn("backup", cfg)
            cfg["shops"].append(store.new_shop("A", r"\\srv\Ramset"))
            cfg["shops"].append(store.new_shop("B", r"\\srv2\Ramset", "9999",
                                               off=["bo", "t3"]))
            store.save(cfg, p)
            again = store.load(p)
            self.assertEqual(len(again["shops"]), 2)
            self.assertEqual(store.vnc_password_for(again, again["shops"][0]),
                             "1234")
            self.assertEqual(store.vnc_password_for(again, again["shops"][1]),
                             "9999")
            self.assertEqual(again["shops"][1]["off"], ["bo", "t3"])

    def test_twenty_shops_survive(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "shops.json")
            cfg = store.load(p)
            for i in range(20):
                cfg["shops"].append(store.new_shop(f"S{i}", rf"\\h{i}\Ramset"))
            store.save(cfg, p)
            self.assertEqual(len(store.load(p)["shops"]), 20)

    def test_corrupt_file_gives_empty_list(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "shops.json")
            Path(p).write_text("{not json")
            self.assertEqual(store.load(p)["shops"], [])

    def test_notepad_bom_is_tolerated(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "shops.json")
            Path(p).write_bytes(b"\xef\xbb\xbf" + json.dumps(
                {"shops": [{"name": "X", "bo_path": r"\\x\R"}]}).encode())
            self.assertEqual(store.load(p)["shops"][0]["name"], "X")

    def test_import_from_reporter_skips_duplicates(self):
        with tempfile.TemporaryDirectory() as td:
            rp = os.path.join(td, "config.json")
            Path(rp).write_text(json.dumps({"shops": [
                {"shop_name": "One", "data_path": r"\\a\Ramset"},
                {"shop_name": "Two", "data_path": r"\\b\Ramset"},
                {"shop_name": "Blank", "data_path": ""}]}))
            cfg = store.load(os.path.join(td, "mine.json"))
            added, skipped, src = store.import_from_reporter(cfg, [rp])
            self.assertEqual((added, skipped, src), (2, 1, rp))
            added, skipped, _ = store.import_from_reporter(cfg, [rp])
            self.assertEqual(added, 0)
            self.assertEqual(len(cfg["shops"]), 2)

    def test_import_without_reporter(self):
        cfg = store.load(os.path.join(tempfile.gettempdir(), "nope.json"))
        self.assertEqual(
            store.import_from_reporter(cfg, [r"C:\no\such\config.json"]),
            (0, 0, None))


class PayloadCopyTests(unittest.TestCase):
    """copy_payload: ordering, marker rules and backups on one destination."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = self.td.name
        src = os.path.join(self.root, "src")
        _write(os.path.join(src, "RPOS25.exe"), "new-exe")
        _write(os.path.join(src, "POS_9.zip"), "inner")
        _write(os.path.join(src, "_UpgradeRequired"), "POS_9.zip")
        self.payload = package.Payload("POS", src)
        self.dest = os.path.join(self.root, "till")
        os.makedirs(self.dest)

    def tearDown(self):
        self.td.cleanup()

    def test_marker_is_copied_last(self):
        order = []
        real = engine.shutil.copy2

        def spy(a, b, **kw):
            order.append(os.path.basename(b))
            return real(a, b, **kw)

        with patch.object(engine.shutil, "copy2", spy):
            r = engine.copy_payload(self.payload, self.dest)
        self.assertEqual(order[-1], "_UpgradeRequired")
        self.assertEqual(r["copied"], 3)
        self.assertFalse(r["marker_withheld"])

    def test_marker_withheld_when_a_file_fails(self):
        real = engine.shutil.copy2

        def flaky(a, b, **kw):
            if b.endswith("RPOS25.exe"):
                raise PermissionError("in use")
            return real(a, b, **kw)

        with patch.object(engine.shutil, "copy2", flaky):
            r = engine.copy_payload(self.payload, self.dest)
        self.assertEqual(len(r["failed"]), 1)
        self.assertTrue(r["marker_withheld"])
        self.assertFalse(os.path.exists(
            os.path.join(self.dest, "_UpgradeRequired")))
        self.assertTrue(os.path.exists(os.path.join(self.dest, "POS_9.zip")))

    def test_replaced_executable_is_not_backed_up(self):
        _write(os.path.join(self.dest, "RPOS25.exe"), "old-exe")
        _write(os.path.join(self.dest, "Ramset.dat"), "live data")
        r = engine.copy_payload(self.payload, self.dest)
        self.assertEqual(r["copied"], 3)
        self.assertEqual(Path(self.dest, "RPOS25.exe").read_text(), "new-exe")
        self.assertEqual(Path(self.dest, "Ramset.dat").read_text(), "live data")
        self.assertFalse(Path(self.dest, "_koenekt_backup").exists())

    def test_copy_never_creates_destination_root(self):
        gone = os.path.join(self.root, "missing")
        result = engine.copy_payload(self.payload, gone)
        self.assertEqual(result["copied"], 0)
        self.assertTrue(result["marker_withheld"])
        self.assertFalse(os.path.exists(gone))


class EngineTests(unittest.TestCase):
    """20 shops, each with its own BO folder and two tills."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = self.td.name
        self.shops, self.tills = [], {}
        for i in range(20):
            bo = os.path.join(self.root, f"shop{i}", "bo")
            t1 = os.path.join(self.root, f"shop{i}", "till1")
            t2 = os.path.join(self.root, f"shop{i}", "till2")
            for d in (bo, t1, t2):
                os.makedirs(d)
            for d in (t1, t2):
                _write(os.path.join(d, "postrans.dat"), "transactions")
                _write(os.path.join(d, "posdebtor.dat"), "debtors")
            self.tills[bo] = [{"name": "TILL 1", "number": 1, "share": t1},
                              {"name": "TILL 2", "number": 2, "share": t2}]
            self.shops.append(dict(store.new_shop(f"Shop {i}", bo), _idx=i))
        pkg = os.path.join(self.root, "pospkg")
        _write(os.path.join(pkg, "Pos.exe"), "pos-new")
        _write(os.path.join(pkg, "lang", "en.dll"), "en")
        _write(os.path.join(pkg, "_UpgradeRequired"), "POS_9.zip")
        self.pos = package.Payload("POS", pkg)
        bopkg = os.path.join(self.root, "bopkg")
        _write(os.path.join(bopkg, "BackOffice.exe"), "bo-new")
        _write(os.path.join(bopkg, "_UpgradeRequired"), "BO_9.zip")
        self.bo = package.Payload("BO", bopkg)

        def fake_read(path):
            # carry the path along so the tills fake knows which shop it is
            return {"available": path in self.tills, "error": "no ini",
                    "_path": path}

        def fake_for_push(info, want=None):
            tills = self.tills.get(info.get("_path"), [])
            return [t for t in tills if want is None or t["number"] in want]

        self._patches = [
            patch.object(engine.vector_terminals, "read_terminals", fake_read),
            patch.object(engine.tillops, "tills_for_push", fake_for_push),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self.td.cleanup()

    def _run(self, targets, bo=True, pos=True, **kw):
        ev = []
        s = engine.run_upgrade(targets, self.bo if bo else None,
                               self.pos if pos else None,
                               lambda *a: ev.append(a),
                               backup_root=os.path.join(self.root, "backups"), **kw)
        return s, ev

    def test_plan_covers_every_destination(self):
        plan = engine.build_plan(self.shops, True, True)
        self.assertEqual(len(plan["targets"]), 20 * 3)
        self.assertEqual(plan["warnings"], [])
        self.assertEqual(
            sum(1 for t in plan["targets"] if t["kind"] == "POS"), 40)

    def test_plan_pos_only_and_bo_only(self):
        self.assertEqual(
            len(engine.build_plan(self.shops, True, False)["targets"]), 40)
        self.assertEqual(
            len(engine.build_plan(self.shops, False, True)["targets"]), 20)

    def test_one_till_only(self):
        s = dict(self.shops[4], want_bo=False, want_tills={2})
        plan = engine.build_plan([s], True, True)
        self.assertEqual([(t["kind"], t["label"], t["key"])
                          for t in plan["targets"]],
                         [("POS", "TILL 2", "4:t2")])

    def test_one_back_office_only(self):
        s = dict(self.shops[7], want_bo=True, want_tills=set())
        plan = engine.build_plan([s], True, True)
        self.assertEqual([(t["kind"], t["key"]) for t in plan["targets"]],
                         [("BO", "7:bo")])

    def test_keys_identify_rows(self):
        plan = engine.build_plan(self.shops[:1], True, True)
        self.assertEqual({t["key"] for t in plan["targets"]},
                         {"0:bo", "0:t1", "0:t2"})

    def test_duplicate_destinations_are_collapsed(self):
        dup = self.shops + [dict(self.shops[0], name="Shop 0 again", _idx=99)]
        self.assertEqual(
            len(engine.build_plan(dup, True, True)["targets"]), 60)

    def test_upgrade_copies_everywhere_and_never_deletes(self):
        keep = os.path.join(self.shops[3]["bo_path"], "Ramset.dat")
        _write(keep, "live data")
        plan = engine.build_plan(self.shops, True, True)
        s, ev = self._run(plan["targets"])
        self.assertEqual(s["ok"], 60)
        self.assertEqual(s["failed"], [])
        self.assertEqual(s["copied"], 20 * (2 * 3 + 2))
        for shop in self.shops:
            self.assertEqual(
                Path(shop["bo_path"], "BackOffice.exe").read_text(), "bo-new")
            for t in self.tills[shop["bo_path"]]:
                self.assertEqual(Path(t["share"], "Pos.exe").read_text(),
                                 "pos-new")
                self.assertTrue(Path(t["share"], "lang", "en.dll").is_file())
                self.assertTrue(Path(t["share"], "_UpgradeRequired").is_file())
            self.assertFalse(Path(shop["bo_path"], "Pos.exe").exists())
        self.assertEqual(Path(keep).read_text(), "live data")
        self.assertEqual(ev[-1][:2], ("progress", 100))
        done = {e[1] for e in ev if e[0] == "target" and e[2] == "ok"}
        self.assertEqual(len(done), 60)

    def test_single_till_leaves_the_rest_untouched(self):
        s = dict(self.shops[2], want_bo=False, want_tills={1})
        plan = engine.build_plan([s], True, True)
        self._run(plan["targets"])
        tills = self.tills[self.shops[2]["bo_path"]]
        self.assertTrue(Path(tills[0]["share"], "Pos.exe").is_file())
        self.assertFalse(Path(tills[1]["share"], "Pos.exe").exists())
        self.assertFalse(
            Path(self.shops[2]["bo_path"], "BackOffice.exe").exists())

    def test_pos_only_leaves_back_office_untouched(self):
        plan = engine.build_plan(self.shops, True, True)
        s, _ = self._run(plan["targets"], bo=False)
        self.assertEqual(s["targets"], 40)
        self.assertFalse(
            Path(self.shops[0]["bo_path"], "BackOffice.exe").exists())

    def test_unreachable_target_is_skipped_not_created(self):
        gone = self.shops[5]["bo_path"]
        os.rmdir(gone)
        plan = engine.build_plan([self.shops[5]] + self.shops[6:8], False, True)
        s, ev = self._run(plan["targets"], pos=False)
        self.assertEqual(s["unreachable"], 1)
        self.assertEqual(s["ok"], 2)
        self.assertFalse(os.path.exists(gone))  # no stray folder invented
        self.assertIn(("target", "5:bo", "unreachable", "not reachable"), ev)

    def test_one_bad_till_does_not_stop_the_rest_and_is_not_triggered(self):
        locked = self.tills[self.shops[0]["bo_path"]][0]["share"]
        real = engine.shutil.copy2

        def flaky(a, b, **kw):
            if b.startswith(locked) and b.endswith("Pos.exe"):
                raise PermissionError("in use")
            return real(a, b, **kw)

        plan = engine.build_plan(self.shops, True, False)
        with patch.object(engine.shutil, "copy2", flaky):
            s, ev = self._run(plan["targets"], bo=False)
        self.assertEqual(s["failed_targets"], 1)
        self.assertEqual(s["withheld"], 1)
        self.assertEqual(s["ok"], 39)
        self.assertFalse(Path(locked, "_UpgradeRequired").exists())
        self.assertTrue(Path(
            self.tills[self.shops[19]["bo_path"]][1]["share"],
            "_UpgradeRequired").is_file())
        self.assertIn(("target", "0:t1", "partial", "failed"), ev)
        self.assertIn("un-triggered", engine.summary_text(s))

    def test_back_office_does_not_get_automatic_backups(self):
        old = os.path.join(self.shops[1]["bo_path"], "BackOffice.exe")
        _write(old, "old-bo")
        plan = engine.build_plan(self.shops[1:2], False, True)
        summary, _ = self._run(plan["targets"], pos=False)
        self.assertEqual(summary["backed_up"], 0)
        self.assertFalse(Path(self.shops[1]["bo_path"], "_koenekt_backup").exists())
        self.assertFalse(Path(self.root, "backups").exists())

    def test_only_two_dat_files_saved_by_shop_and_till_before_payload(self):
        plan = engine.build_plan(self.shops[1:2], True, False)
        dest = plan["targets"][0]["dest"]
        _write(os.path.join(dest, "Pos.exe"), "old-exe")
        _write(os.path.join(dest, "other.dat"), "other")
        order = []
        real = engine.shutil.copy2
        def spy(a, b, **kw):
            order.append((a, b))
            return real(a, b, **kw)
        with patch.object(engine.shutil, "copy2", spy):
            summary, _ = self._run(plan["targets"], bo=False)
        self.assertEqual(summary["backed_up"], 4)
        backups = Path(self.root, "backups")
        saved = [p for p in backups.rglob("*") if p.is_file()]
        self.assertEqual(sorted(p.name for p in saved),
                         ["posdebtor.dat", "posdebtor.dat", "postrans.dat", "postrans.dat"])
        self.assertTrue(all("Shop 1" in p.parts for p in saved))
        self.assertTrue(any("TILL 1" in str(p) for p in saved))
        self.assertTrue(any("TILL 2" in str(p) for p in saved))
        self.assertEqual(Path(dest, "postrans.dat").read_text(), "transactions")
        self.assertEqual([Path(b).name for a, b in order[:2]], list(engine.POS_DATA_FILES))
        self.assertEqual([Path(b).name for a, b in order][4], "_UpgradeRequired")

    def test_failed_pos_backup_withholds_every_payload_file_and_continues(self):
        plan = engine.build_plan(self.shops[:1], True, True)
        dest = plan["targets"][1]["dest"]
        real = engine.shutil.copy2
        def flaky(a, b, **kw):
            if a == os.path.join(dest, "posdebtor.dat"):
                raise PermissionError("locked")
            return real(a, b, **kw)
        with patch.object(engine.shutil, "copy2", flaky):
            summary, _ = self._run(plan["targets"])
        self.assertEqual(summary["failed_targets"], 1)
        self.assertEqual(summary["withheld"], 1)
        self.assertEqual(summary["ok"], 2)
        self.assertFalse(Path(dest, "Pos.exe").exists())
        self.assertFalse(Path(dest, "_UpgradeRequired").exists())

    def test_missing_database_skips_till(self):
        plan = engine.build_plan(self.shops[:1], True, False)
        os.remove(os.path.join(plan["targets"][0]["dest"], "postrans.dat"))
        summary, _ = self._run(plan["targets"], bo=False)
        self.assertEqual(summary["failed_targets"], 1)
        self.assertEqual(summary["ok"], 1)
        self.assertIn("missing postrans.dat", summary["failed"][0])

    def test_repeated_runs_keep_separate_backup_snapshots(self):
        plan = engine.build_plan(self.shops[:1], True, False)
        self._run(plan["targets"], bo=False)
        self._run(plan["targets"], bo=False)
        self.assertEqual(len(list(Path(self.root, "backups").rglob("postrans.dat"))), 4)

    def test_folder_names_are_safe_and_collision_resistant(self):
        self.assertEqual(engine._folder_name("../Shop:/bad"), "_Shop__bad")
        self.assertEqual(engine._folder_name("CON"), "_CON")
        plan = engine.build_plan(self.shops[:1], True, False)
        for target in plan["targets"]:
            target["shop"] = "Shop / 0"
            target["label"] = "Till " + "X" * 100
        self._run(plan["targets"], bo=False)
        self.assertEqual(len(list(Path(self.root, "backups").rglob("postrans.dat"))), 2)

    def test_cancel_stops_between_targets(self):
        plan = engine.build_plan(self.shops, False, True)
        calls = {"n": 0}

        def cancel():
            calls["n"] += 1
            return calls["n"] > 3

        s, _ = self._run(plan["targets"], pos=False, cancel=cancel)
        self.assertTrue(s["cancelled"])
        self.assertEqual(s["ok"], 3)

    def test_shop_without_ini_warns_for_pos_but_still_gets_bo(self):
        self.tills.pop(self.shops[0]["bo_path"])
        plan = engine.build_plan([self.shops[0]], True, True)
        self.assertEqual([t["kind"] for t in plan["targets"]], ["BO"])
        self.assertEqual(len(plan["warnings"]), 1)

    def test_shop_with_no_folder_is_skipped_with_a_warning(self):
        plan = engine.build_plan([store.new_shop("Nowhere", "")], True, True)
        self.assertEqual(plan["targets"], [])
        self.assertIn("Nowhere", plan["warnings"][0])


class VncTests(unittest.TestCase):
    def test_password_per_shop_default_1234(self):
        made = []

        def fake_write(lnk, target, arguments, workdir=None):
            made.append((os.path.basename(lnk), arguments))
            Path(lnk).write_text("lnk")

        info = {"available": True, "terminals": [
            {"number": 1, "name": "TILL 1", "enabled": True,
             "location": r"\\10.0.0.5\rpos25", "raw": {"Name": "TILL 1"}},
            {"number": 2, "name": "TILL 2", "enabled": True,
             "location": r"\\10.0.0.6\rpos25", "raw": {"Name": "TILL 2"}}]}
        cfg = store.load(os.path.join(tempfile.gettempdir(), "absent.json"))
        shops = [store.new_shop("Alpha", r"\\a\Ramset"),
                 store.new_shop("Beta", r"\\b\Ramset", "7777")]
        with tempfile.TemporaryDirectory() as desk, \
                patch.object(engine.vector_terminals, "read_terminals",
                             lambda p: info), \
                patch.object(engine.tillops.vector_terminals,
                             "read_terminals", lambda p: info):
            r = engine.vnc_shortcuts(
                lambda s: store.vnc_password_for(cfg, s), shops, group=True,
                desktop=desk, viewer=r"C:\UltraVNC\vncviewer.exe",
                write=fake_write)
            self.assertTrue(os.path.isdir(os.path.join(desk, "Koenekt Tills")))
        self.assertEqual(r["created"], 4)
        by_shop = {n.split(" - ")[0]: a for n, a in made}
        self.assertTrue(by_shop["Alpha"].endswith("-password 1234"))
        self.assertTrue(by_shop["Beta"].endswith("-password 7777"))

    def test_missing_viewer_is_reported_once_per_shop(self):
        info = {"available": True, "terminals": [
            {"number": 1, "name": "T", "enabled": True,
             "location": r"\\10.0.0.5\rpos25", "raw": {"Name": "T"}}]}
        with tempfile.TemporaryDirectory() as desk, \
                patch.object(engine.vector_terminals, "read_terminals",
                             lambda p: info), \
                patch.object(engine.tillops, "find_vnc_viewer", lambda: None):
            r = engine.vnc_shortcuts(
                lambda s: "1234", [store.new_shop("A", r"\\a\R")],
                group=False, desktop=desk)
        self.assertEqual(r["created"], 0)
        self.assertIn("viewer was not found", r["errors"][0])


class PortableTests(unittest.TestCase):
    def _frozen(self, exe_dir, appdata):
        return (patch.object(sys, "frozen", True, create=True),
                patch.object(sys, "executable", os.path.join(exe_dir, "KUT.exe")),
                patch.dict(os.environ, {"LOCALAPPDATA": appdata}))

    def test_settings_live_beside_the_exe(self):
        with tempfile.TemporaryDirectory() as exe, \
                tempfile.TemporaryDirectory() as app:
            a, b, c = self._frozen(exe, app)
            with a, b, c:
                d = store.data_dir()
                self.assertEqual(d, os.path.join(exe, store.PORTABLE_FOLDER))
                cfg = store.load()
                cfg["shops"].append(store.new_shop("Road", r"\\x\Ramset"))
                store.save(cfg)
            self.assertTrue(os.path.isfile(os.path.join(d, "shops.json")))
            # Copy the exe + folder to another PC: shops come with it.
            with tempfile.TemporaryDirectory() as app2:
                a, b, c = self._frozen(exe, app2)
                with a, b, c:
                    self.assertEqual(store.load()["shops"][0]["name"], "Road")

    def test_first_portable_run_adopts_the_installed_versions_shops(self):
        with tempfile.TemporaryDirectory() as exe, \
                tempfile.TemporaryDirectory() as app:
            legacy = os.path.join(app, "Koenekt", "VectorUp")
            os.makedirs(legacy)
            cfg = store.load(os.path.join(legacy, "none.json"))
            cfg["shops"].append(store.new_shop("Old MSI shop", r"\\o\R"))
            store.save(cfg, os.path.join(legacy, "shops.json"))
            a, b, c = self._frozen(exe, app)
            with a, b, c:
                self.assertEqual(store.load()["shops"][0]["name"],
                                 "Old MSI shop")

    def test_unwritable_exe_folder_falls_back_to_appdata(self):
        with tempfile.TemporaryDirectory() as app:
            a, b, c = self._frozen(r"Z:\no\such\drive", app)
            with a, b, c, patch.object(store, "_writable",
                                       lambda d: not d.startswith("Z:")):
                self.assertIsNone(store.portable_dir())
                self.assertTrue(store.data_dir().startswith(app))

    def test_not_frozen_never_uses_exe_folder(self):
        self.assertIsNone(store.portable_dir())

    def test_scratch_is_in_temp_not_beside_the_exe(self):
        d = store.scratch_dir()
        try:
            self.assertTrue(os.path.isdir(d))
            self.assertTrue(d.startswith(tempfile.gettempdir()))
        finally:
            import shutil
            shutil.rmtree(d, ignore_errors=True)


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.session = downloads.DownloadSession(lambda *a: None)
    def tearDown(self):
        self.session.close()

    def test_only_completed_session_zip_is_emitted_once(self):
        folder = self.session.folder
        partial = folder / "partial.zip.crdownload"
        partial.write_bytes(b"partial")
        (folder / "notes.txt").write_text("ignore")
        complete = folder / "upgrade.zip"
        complete.write_bytes(b"completed")
        self.assertEqual(self.session.completed(), [])
        self.assertEqual(self.session.completed(), [str(complete)])
        self.assertEqual(self.session.completed(), [])
        partial.rename(folder / "partial.zip")
        self.assertEqual(self.session.completed(), [])
        self.assertEqual(len(self.session.completed()), 1)

    def test_changing_download_is_not_ready(self):
        path = self.session.folder / "upgrade.zip"
        path.write_bytes(b"a")
        self.session.completed()
        path.write_bytes(b"ab")
        self.assertEqual(self.session.completed(), [])
        self.assertEqual(self.session.completed(), [str(path)])

    def test_preferences_use_temp_and_disable_password_saving(self):
        preferences = json.loads((self.session.profile / "Default" / "Preferences").read_text())
        self.assertEqual(preferences["download"]["default_directory"], str(self.session.folder))
        self.assertFalse(preferences["download"]["prompt_for_download"])
        self.assertFalse(preferences["credentials_enable_service"])
        self.assertTrue(str(self.session.root).startswith(tempfile.gettempdir()))

    def test_missing_browser_is_clear_and_cleans_temp(self):
        root = self.session.root
        with patch.object(downloads, "find_browser", side_effect=OSError("Edge needed")):
            with self.assertRaisesRegex(OSError, "Edge needed"):
                self.session.start()
        self.assertFalse(root.exists())


class IndependenceTests(unittest.TestCase):
    def test_tool_stands_alone_from_the_reporter(self):
        for mod in ("techtool", "techtool.engine", "techtool.store",
                    "techtool.package", "techtool.dnd", "techtool.tillops",
                    "techtool.terminals"):
            __import__(mod)
        self.assertNotIn("app", sys.modules)
        self.assertNotIn("app.licensing", sys.modules)


if __name__ == "__main__":
    unittest.main()
