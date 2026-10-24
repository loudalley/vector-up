"""1.5 and the original 1.4.x can share one settings folder.

1.4.x rebuilds each shop from a fixed set of keys on every load/save, so it
deletes anything extra it finds in shops.json. 1.5 keeps extra back offices in
shops_extra.json instead. These tests include a round trip through the REAL
1.4.0 code (exported from the v1.4.0 git tag, run in a subprocess).
Run: python tests/test_compat_14.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from techtool import store

PLAIN_KEYS = {"name", "bo_path", "vnc_password", "selected", "off"}


def make_cfg(path):
    cfg = store.load(path)
    a = store.new_shop("Shop A", r"\\srv\RP_BACK", "7777", off=["t2", "b2"])
    store.add_extra_bo(a, "Office PC", r"\\pc2\Liquor")
    store.add_extra_bo(a, "Retail", r"\\pc3\Retail Liq")
    b = store.new_shop("Shop B", r"\\srv2\Data")
    cfg["shops"] += [a, b]
    store.save(cfg, path)
    return cfg


class FileShapeTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.p = os.path.join(self.td.name, "shops.json")

    def tearDown(self):
        self.td.cleanup()

    def test_shops_json_keeps_the_14_shape(self):
        make_cfg(self.p)
        raw = json.loads(Path(self.p).read_text(encoding="utf-8"))
        for shop in raw["shops"]:
            self.assertEqual(set(shop), PLAIN_KEYS, shop)
        self.assertEqual(set(raw), {"shops", "vnc_default", "group_shortcuts"})

    def test_extras_live_in_the_companion_file(self):
        make_cfg(self.p)
        side = json.loads(Path(self.td.name, "shops_extra.json")
                          .read_text(encoding="utf-8"))
        self.assertEqual(side["version"], 1)
        entry = side["shops"][store._norm(r"\\srv\RP_BACK")]
        self.assertEqual([x["name"] for x in entry["extra_bo"]],
                         ["Office PC", "Retail"])
        self.assertEqual(entry["extra_seq"], 2)
        self.assertNotIn(store._norm(r"\\srv2\Data"), side["shops"])

    def test_no_companion_file_for_a_shop_list_without_extras(self):
        cfg = store.load(self.p)
        cfg["shops"].append(store.new_shop("Plain", r"\\s\R"))
        store.save(cfg, self.p)
        self.assertFalse(os.path.exists(os.path.join(self.td.name,
                                                     "shops_extra.json")))

    def test_roundtrip_through_15_loses_nothing(self):
        make_cfg(self.p)
        again = store.load(self.p)
        a = again["shops"][0]
        self.assertEqual([x["name"] for x in a["extra_bo"]],
                         ["Office PC", "Retail"])
        self.assertEqual((a["extra_seq"], a["off"], a["vnc_password"]),
                         (2, ["t2", "b2"], "7777"))
        self.assertEqual(again["shops"][1]["extra_bo"], [])

    def test_removing_the_last_extra_empties_the_companion_entry(self):
        cfg = make_cfg(self.p)
        for x in list(cfg["shops"][0]["extra_bo"]):
            store.remove_extra_bo(cfg["shops"][0], x["id"])
        store.save(cfg, self.p)
        side = json.loads(Path(self.td.name, "shops_extra.json")
                          .read_text(encoding="utf-8"))
        entry = side["shops"][store._norm(r"\\srv\RP_BACK")]
        self.assertEqual(entry["extra_bo"], [])
        self.assertEqual(entry["extra_seq"], 2)  # ids still never reused

    def test_early_dev_build_files_with_inline_extras_still_load_and_migrate(self):
        Path(self.p).write_text(json.dumps({"shops": [{
            "name": "Old dev", "bo_path": r"\\s\R",
            "extra_bo": [{"id": 1, "name": "X", "path": r"\\x\R"}],
            "extra_seq": 1}]}), encoding="utf-8")
        cfg = store.load(self.p)
        self.assertEqual(cfg["shops"][0]["extra_bo"][0]["name"], "X")
        store.save(cfg, self.p)
        raw = json.loads(Path(self.p).read_text(encoding="utf-8"))
        self.assertNotIn("extra_bo", raw["shops"][0])
        self.assertEqual(store.load(self.p)["shops"][0]["extra_bo"][0]["name"],
                         "X")

    def test_a_damaged_companion_file_is_ignored_and_kept(self):
        make_cfg(self.p)
        side = Path(self.td.name, "shops_extra.json")
        side.write_text("{not json", encoding="utf-8")
        cfg = store.load(self.p)
        self.assertEqual(cfg["shops"][0]["extra_bo"], [])  # no crash
        store.save(cfg, self.p)  # would overwrite - must keep the damaged copy
        self.assertEqual(Path(str(side) + ".bad").read_text(), "{not json")

    def test_companion_entries_match_by_folder_not_by_position(self):
        make_cfg(self.p)
        cfg = store.load(self.p)
        cfg["shops"].reverse()  # Shop B first now
        store.save(cfg, self.p)
        again = store.load(self.p)
        by = {s["name"]: s for s in again["shops"]}
        self.assertEqual(len(by["Shop A"]["extra_bo"]), 2)
        self.assertEqual(by["Shop B"]["extra_bo"], [])

    def test_a_companion_entry_for_a_missing_shop_is_ignored(self):
        make_cfg(self.p)
        raw = json.loads(Path(self.p).read_text(encoding="utf-8"))
        raw["shops"][0]["bo_path"] = r"\\moved\RP_BACK"  # as 1.4.x would leave it
        Path(self.p).write_text(json.dumps(raw), encoding="utf-8")
        cfg = store.load(self.p)
        self.assertEqual(cfg["shops"][0]["extra_bo"], [])
        self.assertEqual(len(cfg["shops"]), 2)


def export_v140(dest):
    """Export the original 1.4.0 code from git, or None if unavailable."""
    import zipfile
    zpath = os.path.join(dest, "v140.zip")
    try:  # zip + zipfile: no dependence on whichever tar is first on PATH
        subprocess.run(
            ["git", "archive", "--format=zip", "-o", zpath, "v1.4.0",
             "techtool"], cwd=ROOT, check=True, capture_output=True,
            timeout=60)
        with zipfile.ZipFile(zpath) as zf:
            zf.extractall(dest)
    except (OSError, subprocess.SubprocessError, zipfile.BadZipFile):
        return None
    return dest if Path(dest, "techtool", "store.py").is_file() else None


OLD_RUN = r'''
import sys
sys.path.insert(0, sys.argv[1])
from techtool import store, VERSION
assert VERSION == "1.4.0", VERSION
p = sys.argv[2]
cfg = store.load(p)
action = sys.argv[3]
if action == "touch":
    pass
elif action == "edit":      # what a technician does in 1.4.0
    cfg["shops"][0]["name"] = "Shop A (edited in 1.4)"
    cfg["shops"].append(store.new_shop("Added in 1.4", r"\\new\Ramset"))
    cfg["shops"][1]["off"] = ["bo"]
elif action == "remove":
    del cfg["shops"][0]
elif action == "readd":     # same folder, typed differently
    cfg["shops"].insert(0, store.new_shop("Shop A again", r"\\SRV\rp_back" + "\\"))
store.save(cfg, p)
'''


class RealOriginalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.old = export_v140(cls.tmp)
        cls.script = os.path.join(cls.tmp, "run_old.py")
        Path(cls.script).write_text(OLD_RUN, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        if not self.old:
            self.skipTest("v1.4.0 tag not available in this checkout")
        self.td = tempfile.TemporaryDirectory()
        self.p = os.path.join(self.td.name, "shops.json")
        make_cfg(self.p)

    def tearDown(self):
        if getattr(self, "td", None):
            self.td.cleanup()

    def run_old(self, action):
        r = subprocess.run([sys.executable, self.script, self.old, self.p,
                            action], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_the_original_cannot_erase_extra_back_offices(self):
        self.run_old("touch")  # just opening and closing the original
        a = store.load(self.p)["shops"][0]
        self.assertEqual([x["name"] for x in a["extra_bo"]],
                         ["Office PC", "Retail"])
        self.assertEqual(a["extra_seq"], 2)

    def test_the_original_still_sees_the_shared_shop_list(self):
        # what 1.4.0 itself sees in a file 1.5 wrote
        r = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, sys.argv[1]);"
             "from techtool import store;"
             "c = store.load(sys.argv[2]);"
             "print([ (s['name'], s['vnc_password']) for s in c['shops']])",
             self.old, self.p], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("('Shop A', '7777')", r.stdout)
        self.assertIn("('Shop B', '')", r.stdout)

    def test_edits_made_in_the_original_are_kept_and_so_are_the_extras(self):
        self.run_old("edit")
        cfg = store.load(self.p)
        names = [s["name"] for s in cfg["shops"]]
        self.assertEqual(names, ["Shop A (edited in 1.4)", "Shop B",
                                 "Added in 1.4"])
        self.assertEqual(len(cfg["shops"][0]["extra_bo"]), 2)
        self.assertEqual(cfg["shops"][1]["off"], ["bo"])

    def test_a_shop_removed_in_the_original_leaves_no_ghost_in_15(self):
        self.run_old("remove")
        cfg = store.load(self.p)
        self.assertEqual([s["name"] for s in cfg["shops"]], ["Shop B"])
        # the removed shop's extras are still on disk, untouched by the original
        side = json.loads(Path(self.td.name, "shops_extra.json")
                          .read_text(encoding="utf-8"))
        self.assertIn(store._norm(r"\\srv\RP_BACK"), side["shops"])

    def test_a_shop_removed_then_re_added_in_the_original_gets_its_extras_back(self):
        self.run_old("remove")
        self.run_old("readd")
        cfg = store.load(self.p)
        a = next(s for s in cfg["shops"] if s["name"] == "Shop A again")
        self.assertEqual([x["name"] for x in a["extra_bo"]],
                         ["Office PC", "Retail"])

    def test_ids_stay_unique_after_a_trip_through_the_original(self):
        self.run_old("touch")
        a = store.load(self.p)["shops"][0]
        x = store.add_extra_bo(a, "Third", r"\\pc4\Stock")
        self.assertEqual(x["id"], 3)


if __name__ == "__main__":
    unittest.main()
