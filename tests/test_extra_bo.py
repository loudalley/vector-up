"""Extra back offices (second, third, ... RP_BACK folders of one shop).
Run: python tests/test_extra_bo.py
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from techtool import engine, package, store


def _write(path, text="x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


class StoreExtraTests(unittest.TestCase):
    def shop(self):
        return store.new_shop("Shop A", r"\\srv\RP_BACK")

    def test_add_gives_each_a_stable_id(self):
        s = self.shop()
        a = store.add_extra_bo(s, "Office", r"\\pc2\RP_BACK")
        b = store.add_extra_bo(s, "Stock", r"\\pc3\RP_BACK")
        self.assertEqual((a["id"], b["id"]), (1, 2))
        self.assertEqual([x["name"] for x in s["extra_bo"]], ["Office", "Stock"])

    def test_ids_are_never_reused_after_removal(self):
        s = self.shop()
        store.add_extra_bo(s, "A", r"\\pc2\RP_BACK")
        store.add_extra_bo(s, "B", r"\\pc3\RP_BACK")
        store.remove_extra_bo(s, 2)
        c = store.add_extra_bo(s, "C", r"\\pc4\RP_BACK")
        self.assertEqual(c["id"], 3)  # not 2: a stale tick on b2 must not land on C

    def test_removal_forgets_its_untick(self):
        s = self.shop()
        x = store.add_extra_bo(s, "A", r"\\pc2\RP_BACK")
        s["off"] = ["bo", store.extra_key(x["id"]), "t1"]
        store.remove_extra_bo(s, x["id"])
        self.assertEqual(s["off"], ["bo", "t1"])
        self.assertEqual(s["extra_bo"], [])

    def test_blank_name_falls_back_to_the_path(self):
        s = self.shop()
        x = store.add_extra_bo(s, "  ", r"\\pc2\RP_BACK")
        self.assertEqual(x["name"], r"\\pc2\RP_BACK")

    def test_refuses_empty_and_duplicates(self):
        s = self.shop()
        store.add_extra_bo(s, "A", r"\\pc2\RP_BACK")
        for bad, msg in ((" ", "Enter"),
                         (r"\\SRV\rp_back", "main back-office"),
                         (r"\\PC2\rp_back\\", "Already listed")):
            with self.assertRaises(ValueError) as cm:
                store.add_extra_bo(s, "dup", bad)
            self.assertIn(msg, str(cm.exception))
        self.assertEqual(len(s["extra_bo"]), 1)

    def test_edit_keeps_id_and_refuses_clashes(self):
        s = self.shop()
        a = store.add_extra_bo(s, "A", r"\\pc2\RP_BACK")
        store.add_extra_bo(s, "B", r"\\pc3\RP_BACK")
        store.update_extra_bo(s, a["id"], "A renamed", r"\\pc9\RP_BACK")
        self.assertEqual(store.find_extra(s, a["id"])["path"], r"\\pc9\RP_BACK")
        with self.assertRaises(ValueError):
            store.update_extra_bo(s, a["id"], "A", r"\\pc3\RP_BACK")
        # saving a back office over its own path is not a clash
        store.update_extra_bo(s, a["id"], "A again", r"\\pc9\RP_BACK")

    def test_limit(self):
        s = self.shop()
        for i in range(store.MAX_EXTRA_BO):
            store.add_extra_bo(s, f"B{i}", rf"\\pc{i}\RP_BACK")
        with self.assertRaises(ValueError):
            store.add_extra_bo(s, "one too many", r"\\pcX\RP_BACK")

    def test_survives_save_and_load_with_20_shops(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "shops.json")
            cfg = store.load(p)
            for i in range(20):
                sh = store.new_shop(f"S{i}", rf"\\h{i}\RP_BACK")
                for j in range(3):  # a main plus three more back offices
                    store.add_extra_bo(sh, f"BO{j + 2}", rf"\\h{i}pc{j}\RP_BACK")
                cfg["shops"].append(sh)
            cfg["shops"][4]["off"] = ["b2"]
            store.save(cfg, p)
            again = store.load(p)
            self.assertEqual(len(again["shops"]), 20)
            self.assertTrue(all(len(s["extra_bo"]) == 3 for s in again["shops"]))
            self.assertEqual(again["shops"][4]["off"], ["b2"])
            n = store.add_extra_bo(again["shops"][0], "next", r"\\new\RP_BACK")
            self.assertEqual(n["id"], 4)  # sequence survived the reload

    def test_old_settings_file_without_extras_still_loads(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "shops.json")
            Path(p).write_text(json.dumps({"shops": [
                {"name": "Old", "bo_path": r"\\o\R", "off": ["t1"]}]}))
            s = store.load(p)["shops"][0]
            self.assertEqual((s["extra_bo"], s["extra_seq"], s["off"]),
                             ([], 0, ["t1"]))

    def test_damaged_extras_are_dropped_not_fatal(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "shops.json")
            Path(p).write_text(json.dumps({"shops": [{
                "name": "S", "bo_path": r"\\s\R", "extra_bo": [
                    {"id": 1, "name": "ok", "path": r"\\a\R"},
                    {"id": "x", "path": r"\\b\R"}, {"id": 2, "path": ""},
                    {"id": 1, "name": "dup id", "path": r"\\c\R"}, "junk"]}]}))
            ex = store.load(p)["shops"][0]["extra_bo"]
            self.assertEqual([x["name"] for x in ex], ["ok"])

    def test_key_helpers_do_not_confuse_kinds(self):
        self.assertTrue(store.is_extra_key("b3"))
        self.assertFalse(store.is_extra_key("bo"))
        self.assertFalse(store.is_extra_key("t3"))
        self.assertFalse(store.is_extra_key("b"))
        self.assertEqual(store.extra_id("b12"), 12)

    def test_drive_path_detection(self):
        self.assertTrue(store.is_drive_path(r"C:\RP_BACK"))
        self.assertTrue(store.is_drive_path("z:/rp_back"))
        self.assertFalse(store.is_drive_path(r"\\pc\RP_BACK"))
        self.assertFalse(store.is_drive_path(""))


class PlanAndCopyTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = self.td.name
        self.main = os.path.join(self.root, "main")
        self.office = os.path.join(self.root, "office")
        self.stock = os.path.join(self.root, "stock")
        for d in (self.main, self.office, self.stock):
            os.makedirs(d)
        _write(os.path.join(self.office, "RP_BACK.exe"), "old-office")
        src = os.path.join(self.root, "bo")
        _write(os.path.join(src, "RP_BACK.exe"), "new-exe")
        _write(os.path.join(src, "BO_9.zip"), "inner")
        _write(os.path.join(src, "_UpgradeRequired"), "BO_9.zip")
        self.payload = package.Payload("BO", src)
        self.shop = store.new_shop("Shop A", self.main)
        self.x1 = store.add_extra_bo(self.shop, "Office PC", self.office)
        self.x2 = store.add_extra_bo(self.shop, "Stock room", self.stock)
        self.shop["_idx"] = 0

    def tearDown(self):
        self.td.cleanup()

    def plan(self, **want):
        s = dict(self.shop, **want)
        return engine.build_plan([s], False, True)["targets"]

    def test_main_and_extras_are_all_planned_in_order(self):
        t = self.plan()
        self.assertEqual([x["key"] for x in t], ["0:bo", "0:b1", "0:b2"])
        self.assertEqual([x["label"] for x in t],
                         ["Back office", "Back office 2 - Office PC",
                          "Back office 3 - Stock room"])
        self.assertTrue(all(x["kind"] == engine.BO for x in t))

    def test_one_extra_only(self):
        t = self.plan(want_bo=False, want_extra={self.x2["id"]})
        self.assertEqual([x["key"] for x in t], ["0:b2"])

    def test_main_only_leaves_extras_alone(self):
        t = self.plan(want_extra=set())
        self.assertEqual([x["key"] for x in t], ["0:bo"])

    def test_all_extras_without_main(self):
        t = self.plan(want_bo=False, want_extra=None)
        self.assertEqual([x["key"] for x in t], ["0:b1", "0:b2"])

    def test_extras_are_not_planned_for_a_pos_only_package(self):
        s = dict(self.shop)
        with patch.object(engine.vector_terminals, "read_terminals",
                          lambda p: {"available": False, "error": "no ini"}):
            t = engine.build_plan([s], True, False)["targets"]
        self.assertEqual(t, [])

    def test_same_folder_twice_is_planned_once(self):
        other = store.new_shop("Shop B", self.office)  # same folder as A's extra
        other["_idx"] = 1
        t = engine.build_plan([dict(self.shop), other], False, True)["targets"]
        self.assertEqual(sum(1 for x in t if x["dest"] == self.office), 1)

    def test_same_folder_typed_with_a_trailing_backslash_is_planned_once(self):
        # normpath keeps the slash on a UNC share root, so these used to differ
        s = store.new_shop("Shop C", r"\\srv\RP_BACK" + "\\")
        s["_idx"] = 0
        with self.assertRaises(ValueError):  # the dialog/store refuse it ...
            store.add_extra_bo(s, "same", r"\\SRV\rp_back")
        # ... but a hand-edited settings file could still hold it
        s["extra_bo"] = [{"id": 1, "name": "same", "path": r"\\SRV\rp_back"}]
        t = engine.build_plan([s], False, True)["targets"]
        self.assertEqual([x["key"] for x in t], ["0:bo"])

    def test_extras_get_the_bo_files_marker_last_and_nothing_deleted(self):
        _write(os.path.join(self.office, "Ramset.dat"), "live data")
        ev = []
        s = engine.run_upgrade(self.plan(), self.payload, None,
                               lambda *a: ev.append(a))
        self.assertEqual((s["ok"], s["failed"]), (3, []))
        for d in (self.main, self.office, self.stock):
            self.assertEqual(Path(d, "RP_BACK.exe").read_text(), "new-exe")
            self.assertTrue(Path(d, "_UpgradeRequired").is_file())
        self.assertEqual(Path(self.office, "Ramset.dat").read_text(), "live data")
        oks = {e[1] for e in ev if e[0] == "target" and e[2] == "ok"}
        self.assertEqual(oks, {"0:bo", "0:b1", "0:b2"})

    def test_upgrading_one_extra_touches_nothing_else(self):
        s = engine.run_upgrade(
            self.plan(want_bo=False, want_extra={self.x1["id"]}),
            self.payload, None, lambda *a: None)
        self.assertEqual(s["ok"], 1)
        self.assertEqual(Path(self.office, "RP_BACK.exe").read_text(), "new-exe")
        self.assertFalse(Path(self.main, "RP_BACK.exe").exists())
        self.assertFalse(Path(self.stock, "RP_BACK.exe").exists())

    def test_an_unreachable_extra_is_skipped_never_created(self):
        gone = os.path.join(self.root, "pc-is-off")
        store.update_extra_bo(self.shop, self.x2["id"], "Stock room", gone)
        ev = []
        s = engine.run_upgrade(self.plan(), self.payload, None,
                               lambda *a: ev.append(a))
        self.assertEqual((s["ok"], s["unreachable"]), (2, 1))
        self.assertFalse(os.path.exists(gone))
        self.assertIn(("target", "0:b2", "unreachable", "not reachable"), ev)
        self.assertTrue(Path(self.office, "_UpgradeRequired").is_file())

    def test_a_locked_extra_does_not_trigger_and_the_rest_continue(self):
        real = engine.shutil.copy2

        def flaky(a, b, **kw):
            if b.startswith(self.office) and b.endswith("RP_BACK.exe"):
                raise PermissionError("in use")
            return real(a, b, **kw)

        with patch.object(engine.shutil, "copy2", flaky):
            s = engine.run_upgrade(self.plan(), self.payload, None,
                                   lambda *a: None)
        self.assertEqual((s["ok"], s["failed_targets"], s["withheld"]), (2, 1, 1))
        self.assertFalse(Path(self.office, "_UpgradeRequired").exists())
        self.assertTrue(Path(self.stock, "_UpgradeRequired").is_file())

    def test_extras_with_no_bo_in_the_package_are_skipped(self):
        s = engine.run_upgrade(self.plan(), None, self.payload,
                               lambda *a: None)
        self.assertEqual(s["targets"], 0)


class InspectFolderTests(unittest.TestCase):
    def test_reports_what_is_there(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(engine.inspect_bo_folder(os.path.join(td, "no")),
                             {"reachable": False, "has_exe": False, "exe": "",
                              "has_data": False})
            r = engine.inspect_bo_folder(td)
            self.assertEqual((r["reachable"], r["has_exe"]), (True, False))
            _write(os.path.join(td, "rp_back.EXE"))
            _write(os.path.join(td, "Ramset.dat"))
            r = engine.inspect_bo_folder(td)
            self.assertEqual((r["has_exe"], r["exe"], r["has_data"]),
                             (True, "rp_back.EXE", True))

    def test_a_file_path_is_not_a_folder(self):
        with tempfile.TemporaryDirectory() as td:
            f = os.path.join(td, "a.txt")
            _write(f)
            self.assertFalse(engine.inspect_bo_folder(f)["reachable"])


if __name__ == "__main__":
    unittest.main()
