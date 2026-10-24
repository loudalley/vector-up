"""Finding back-office program folders on the network (fakes + temp folders).
Run: python tests/test_discovery.py
"""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from techtool import discovery as d
from techtool import store


def _write(path, text="x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _ini(folder, data_dir, name="VectorAdminLocal.ini"):
    _write(os.path.join(folder, name),
           f"[BOOTSTART]\nRegisteredUserName=\nAdminDataDirectory={data_dir}\n")


class UncTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(d.parse_unc(r"\\SERVER\Retail Liq\sub\x"),
                         ("SERVER", "Retail Liq", r"sub\x"))
        self.assertEqual(d.parse_unc("//srv/share"), ("srv", "share", ""))
        self.assertIsNone(d.parse_unc(r"C:\RP_BACK"))
        self.assertIsNone(d.parse_unc(r"\\onlyhost"))
        self.assertIsNone(d.parse_unc(""))

    def test_build(self):
        self.assertEqual(d.unc("srv", "Liquor"), r"\\srv\Liquor")
        self.assertEqual(d.unc("srv", "a", r"b\c"), r"\\srv\a\b\c")


class FolderWalkTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = self.td.name

    def tearDown(self):
        self.td.cleanup()

    def mk(self, rel, exe="RP_BACK.exe"):
        _write(os.path.join(self.root, rel, exe))
        return os.path.join(self.root, rel)

    def test_finds_by_exe_whatever_the_folder_is_called(self):
        a = self.mk("Liquor")
        b = self.mk("Retail Liq")
        c = self.mk("RP_BACK")
        found, complete = d.find_program_folders(self.root)
        self.assertEqual(sorted(found), sorted([a, b, c]))
        self.assertTrue(complete)

    def test_exe_name_case_does_not_matter(self):
        a = self.mk("one", exe="rp_back.EXE")
        self.assertEqual(d.find_program_folders(self.root)[0], [a])

    def test_root_itself_counts(self):
        _write(os.path.join(self.root, "RP_BACK.exe"))
        self.assertEqual(d.find_program_folders(self.root)[0], [self.root])

    def test_depth_is_limited(self):
        near = self.mk("a/b")           # depth 2: found
        self.mk("a/b/c")                # depth 3: not looked at
        found, _ = d.find_program_folders(self.root, max_depth=2)
        self.assertEqual([os.path.normpath(f) for f in found],
                         [os.path.normpath(near)])

    def test_skips_logs_backups_and_hidden_shares(self):
        self.mk("Logs/x")
        self.mk("Backup/y")
        self.mk("Backups/z")
        self.mk("POS_Data_Preparation/1")
        self.mk("$RECYCLE.BIN/q")
        self.mk("secret$/w")
        real = self.mk("Liquor")
        self.assertEqual(d.find_program_folders(self.root)[0], [real])

    def test_a_folder_named_like_the_exe_is_not_the_exe(self):
        os.makedirs(os.path.join(self.root, "x", "RP_BACK.exe"))
        self.assertEqual(d.find_program_folders(self.root)[0], [])

    def test_unreadable_folder_is_skipped(self):
        found, complete = d.find_program_folders(
            r"Z:\definitely\not\here")
        self.assertEqual((found, complete), ([], True))

    def test_deadline_stops_the_walk_and_says_so(self):
        for i in range(5):
            self.mk(f"f{i}")
        found, complete = d.find_program_folders(
            self.root, deadline=time.monotonic() - 1)
        self.assertEqual((found, complete), ([], False))

    def test_cancel_stops_the_walk(self):
        self.mk("f1")
        found, complete = d.find_program_folders(
            self.root, cancel=lambda: True)
        self.assertEqual((found, complete), ([], False))


class IniTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.f = self.td.name

    def tearDown(self):
        self.td.cleanup()

    def test_reads_the_data_directory(self):
        _ini(self.f, r"\\SERVER\RP_BACK")
        self.assertEqual(d.read_admin_data_dir(self.f), r"\\SERVER\RP_BACK")

    def test_file_name_case_and_notepad_bom(self):
        Path(self.f, "VECTORADMINLOCAL.INI").write_bytes(
            b"\xef\xbb\xbf[BOOTSTART]\r\nAdminDataDirectory=C:\\RP_BACK\r\n")
        self.assertEqual(d.read_admin_data_dir(self.f), r"C:\RP_BACK")

    def test_old_ansi_file_with_odd_bytes(self):
        Path(self.f, "VectorAdminLocal.ini").write_bytes(
            b"[BOOTSTART]\r\nRegisteredUserName=Caf\xe9\r\n"
            b"AdminDataDirectory=\\\\SRV\\Data\r\n")
        self.assertEqual(d.read_admin_data_dir(self.f), r"\\SRV\Data")

    def test_quoted_value_and_missing_things(self):
        _write(os.path.join(self.f, "VectorAdminLocal.ini"),
               '[BOOTSTART]\nAdminDataDirectory="\\\\SRV\\Data"\n')
        self.assertEqual(d.read_admin_data_dir(self.f), r"\\SRV\Data")
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(d.read_admin_data_dir(empty), "")
        self.assertEqual(d.read_admin_data_dir(r"Z:\gone"), "")

    def test_garbage_ini_gives_empty_not_an_exception(self):
        _write(os.path.join(self.f, "VectorAdminLocal.ini"), "not an ini at all")
        self.assertEqual(d.read_admin_data_dir(self.f), "")


class ClassifyTests(unittest.TestCase):
    def setUp(self):
        self.shops = [store.new_shop("Main Shop", r"\\SERVER\RP_BACK"),
                      store.new_shop("Other Shop", r"\\SERVER\Other")]
        store.add_extra_bo(self.shops[0], "Till office", r"\\OFFICE2\Retail")

    def cls(self, folder, ini="", has_data=False, start=0):
        return d.classify(folder, self.shops, start,
                          read_ini=lambda f: ini, has_data=has_data)

    def test_the_main_folder_is_already_listed(self):
        r = self.cls(r"\\server\rp_back" + "\\", has_data=True)
        self.assertEqual((r["kind"], r["shop_index"]), (d.LISTED, 0))

    def test_an_existing_extra_is_already_listed(self):
        r = self.cls(r"\\office2\RETAIL")
        self.assertEqual((r["kind"], r["shop_index"]), (d.LISTED, 0))
        self.assertIn("Main Shop", r["note"])

    def test_own_ramset_dat_means_another_shop(self):
        r = self.cls(r"\\SERVER\Liquor", has_data=True)
        self.assertEqual((r["kind"], r["shop_index"]), (d.OWN, None))

    def test_points_at_a_listed_shops_data_is_that_shops_extra(self):
        r = self.cls(r"\\PC3\Liquor", ini=r"\\server\rp_back\\")
        self.assertEqual((r["kind"], r["shop_index"]), (d.SECONDARY, 0))
        r = self.cls(r"\\PC3\Liquor", ini=r"\\SERVER\OTHER")
        self.assertEqual((r["kind"], r["shop_index"]), (d.SECONDARY, 1))

    def test_a_drive_letter_data_dir_cannot_be_matched(self):
        r = self.cls(r"\\PC3\Liquor", ini=r"Z:\RP_BACK")
        self.assertEqual((r["kind"], r["shop_index"]), (d.UNCLEAR, 0))
        self.assertIn("drive letter", r["note"])

    def test_unknown_data_dir_and_no_ini(self):
        r = self.cls(r"\\PC3\Liquor", ini=r"\\ELSEWHERE\Data")
        self.assertEqual(r["kind"], d.UNCLEAR)
        self.assertIn("not a listed shop", r["note"])
        r = self.cls(r"\\PC3\Liquor", ini="")
        self.assertEqual(r["kind"], d.UNCLEAR)
        self.assertIn("VectorAdminLocal.ini", r["note"])


class RealFilesystemScanTests(unittest.TestCase):
    """One machine hosting several back offices, built from real folders."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.share_root = self.td.name  # stands in for \\SERVER
        self.main = os.path.join(self.share_root, "RP_BACK")
        self.liq = os.path.join(self.share_root, "Liquor")
        self.retail = os.path.join(self.share_root, "Retail Liq")
        self.second = os.path.join(self.share_root, "OfficePC")
        for f in (self.main, self.liq, self.retail):
            _write(os.path.join(f, "RP_BACK.exe"))
            _write(os.path.join(f, "Ramset.dat"))
        _write(os.path.join(self.second, "RP_BACK.exe"))
        _ini(self.second, self.main)  # a secondary: no data, points at main
        _write(os.path.join(self.share_root, "Photos", "a.jpg"))
        self.shops = [store.new_shop("Main", self.main)]

    def tearDown(self):
        self.td.cleanup()

    def scan(self, **kw):
        return d.scan_host(
            "SERVER", self.shops, 0,
            shares=lambda h: ["RP_BACK", "Liquor", "Retail Liq", "OfficePC",
                              "Photos"],
            walk=lambda root, depth, deadline, cancel: d.find_program_folders(
                os.path.join(self.share_root, root.split("\\")[-1]), depth,
                deadline, cancel), **kw)

    def test_one_machine_with_several_back_offices(self):
        # the folder->path mapping above stands in for the share; classify
        # reads the real folders, so compare on names
        r = self.scan(classify_fn=lambda f, s, st: d.classify(
            f, s, st))
        by_name = {c["name"]: c for c in r["found"]}
        self.assertEqual(set(by_name), {"RP_BACK", "Liquor", "Retail Liq",
                                        "OfficePC"})
        self.assertEqual(by_name["Liquor"]["kind"], d.OWN)
        self.assertEqual(by_name["Retail Liq"]["kind"], d.OWN)
        self.assertEqual(by_name["RP_BACK"]["kind"], d.LISTED)
        self.assertEqual(by_name["OfficePC"]["kind"], d.SECONDARY)
        self.assertEqual(by_name["OfficePC"]["shop_index"], 0)

    def test_a_share_that_cannot_be_listed_reports_why(self):
        def refuse(host):
            raise OSError("access denied listing shares on " + host)
        r = d.scan_host("SERVER", self.shops, 0, shares=refuse)
        self.assertEqual(r["found"], [])
        self.assertIn("access denied", r["error"])


class DiscoverTests(unittest.TestCase):
    def setUp(self):
        self.shops = [store.new_shop("Main", r"\\SERVER\RP_BACK")]
        self.calls = []

    def fake_scan(self, per_host):
        def scan(host, shops, start, cancel=None):
            self.calls.append(host)
            found = [dict(c, host=host) for c in per_host.get(host, [])]
            return {"host": host, "shares": ["x"], "found": found,
                    "error": "", "complete": True}
        return scan

    def cand(self, path, kind=d.OWN):
        return {"path": path, "name": path.rstrip("\\").split("\\")[-1],
                "kind": kind,
                "shop_index": None, "note": ""}

    def test_scans_only_the_shops_server_by_default(self):
        out = d.discover(
            self.shops, 0, network=False,
            scan=self.fake_scan({"SERVER": [self.cand(r"\\SERVER\Liquor")]}),
            sweep=lambda *a, **k: self.fail("must not sweep"))
        self.assertEqual(self.calls, ["SERVER"])
        self.assertEqual([c["name"] for c in out["candidates"]], ["Liquor"])

    def test_network_scan_adds_the_other_pcs_and_never_the_server_twice(self):
        swept = {}

        def sweep(ip, skip=(), cancel=None):
            swept["ip"], swept["skip"] = ip, set(skip)
            return ["10.0.5.30", "10.0.5.31"]
        out = d.discover(
            self.shops, 0, network=True, resolve=lambda h: "10.0.5.20",
            sweep=sweep,
            scan=self.fake_scan({
                "SERVER": [self.cand(r"\\SERVER\Liquor")],
                "10.0.5.30": [self.cand(r"\\10.0.5.30\Retail", d.SECONDARY)],
                "10.0.5.31": []}))
        self.assertEqual(self.calls, ["SERVER", "10.0.5.30", "10.0.5.31"])
        self.assertEqual(swept["ip"], "10.0.5.20")
        self.assertIn("10.0.5.20", swept["skip"])
        self.assertEqual(len(out["candidates"]), 2)
        self.assertTrue(any("2 other PC" in n for n in out["notes"]))

    def test_the_same_folder_seen_twice_is_listed_once(self):
        out = d.discover(
            self.shops, 0, network=True, resolve=lambda h: "10.0.5.20",
            sweep=lambda *a, **k: ["10.0.5.30"],
            scan=self.fake_scan({
                "SERVER": [self.cand(r"\\SERVER\Liquor")],
                "10.0.5.30": [self.cand(r"\\server\liquor" + "\\")]}))
        self.assertEqual(len(out["candidates"]), 1)

    def test_a_local_back_office_has_no_server_to_scan(self):
        shops = [store.new_shop("Local", r"C:\RP_BACK")]
        out = d.discover(shops, 0, scan=lambda *a, **k: self.fail("no scan"))
        self.assertEqual(out["candidates"], [])
        self.assertIn("local path", out["notes"][0])

    def test_unresolvable_server_skips_the_sweep_with_a_note(self):
        out = d.discover(
            self.shops, 0, network=True, resolve=lambda h: "",
            scan=self.fake_scan({}),
            sweep=lambda *a, **k: self.fail("must not sweep"))
        self.assertTrue(any("address" in n for n in out["notes"]))

    def test_a_server_that_refuses_is_reported_not_raised(self):
        def scan(host, shops, start, cancel=None):
            return {"host": host, "shares": [], "found": [],
                    "error": "access denied listing shares on " + host,
                    "complete": True}
        out = d.discover(self.shops, 0, scan=scan)
        self.assertEqual(out["candidates"], [])
        self.assertTrue(any("access denied" in n for n in out["notes"]))

    def test_cancel_before_the_network_step_skips_it(self):
        out = d.discover(
            self.shops, 0, network=True, cancel=lambda: True,
            resolve=lambda h: "10.0.5.20", scan=self.fake_scan({}),
            sweep=lambda *a, **k: self.fail("cancelled"))
        self.assertEqual(self.calls, ["SERVER"])

    def test_progress_is_reported(self):
        seen = []
        d.discover(self.shops, 0, scan=self.fake_scan({}),
                   emit=lambda *a: seen.append(a))
        self.assertTrue(seen and seen[0][0] == "status")


class SweepTests(unittest.TestCase):
    def test_only_answering_hosts_in_the_same_24_are_returned(self):
        alive = {"10.0.5.9", "10.0.5.30", "10.0.5.20", "10.0.6.7"}
        asked = []

        def connect(addr, port, timeout):
            asked.append((addr, port))
            return addr in alive
        hits = d.sweep_subnet("10.0.5.20", skip={"10.0.5.9"}, connect=connect)
        self.assertEqual(hits, ["10.0.5.30"])  # server and skipped host left out
        self.assertEqual(len(asked), 252)       # 254 minus server minus skipped
        self.assertTrue(all(p == 445 for _a, p in asked))
        self.assertTrue(all(a.startswith("10.0.5.") for a, _p in asked))

    def test_numeric_order_and_bad_input(self):
        hits = d.sweep_subnet("192.168.1.5", connect=lambda a, p, t: a in
                              ("192.168.1.100", "192.168.1.20"))
        self.assertEqual(hits, ["192.168.1.20", "192.168.1.100"])
        self.assertEqual(d.sweep_subnet("not-an-ip"), [])
        self.assertEqual(d.sweep_subnet(""), [])

    def test_cancel_stops_probing(self):
        asked = []
        d.sweep_subnet("10.0.5.20", cancel=lambda: True,
                       connect=lambda a, p, t: asked.append(a))
        self.assertEqual(asked, [])


class RealShareApiTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Windows only")
    def test_listing_this_pc_works_and_hides_admin_shares(self):
        names = d.list_disk_shares("localhost")
        self.assertIsInstance(names, list)
        self.assertFalse([n for n in names if n.upper() in ("C$", "ADMIN$", "IPC$")])

    @unittest.skipUnless(sys.platform == "win32", "Windows only")
    def test_a_missing_machine_is_an_oserror_with_a_reason(self):
        with self.assertRaises(OSError) as cm:
            d.list_disk_shares("no-such-host-vectorup-test")
        self.assertIn("no-such-host-vectorup-test", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
