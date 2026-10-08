"""Vector's authenticated downloads in a small, isolated Edge app window.

The installer logs in directly in Edge. No password passes through Python.
Completed ZIPs are handed to Tk through its queue; partial downloads stay put.
Only this session's temporary download directory is watched.
"""
import base64
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request
from urllib.parse import urlsplit

VECTOR_URL = "https://www.vectortech.co.za/dwnlds/login.php"


def find_browser():
    for relative in (r"Microsoft\Edge\Application\msedge.exe",
                     r"Google\Chrome\Application\chrome.exe"):
        for env in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
            base = os.environ.get(env)
            candidate = os.path.join(base, relative) if base else ""
            if candidate and os.path.isfile(candidate):
                return candidate
    raise OSError("Microsoft Edge or Google Chrome is needed for Get package. "
                  "You can still download the ZIP yourself and drop it here.")


class DownloadSession:
    def __init__(self, emit, url=VECTOR_URL):
        self.emit = emit
        self.url = url
        self.root = Path(tempfile.mkdtemp(prefix="vectorup-browser-"))
        self.folder = self.root / "downloads"
        self.profile = self.root / "profile"
        self.folder.mkdir()
        (self.profile / "Default").mkdir(parents=True)
        preferences = {
            "download": {"default_directory": str(self.folder),
                         "prompt_for_download": False, "directory_upgrade": True},
            "credentials_enable_service": False,
            "profile": {"password_manager_enabled": False},
            "browser": {"has_seen_welcome_page": True},
        }
        (self.profile / "Default" / "Preferences").write_text(
            json.dumps(preferences), encoding="utf-8")
        self.stop = threading.Event()
        self.seen = set()
        self.sizes = {}
        self.process = None
        self.active = False
        self.thread = None
        self.endpoint = None

    def start(self):
        try:
            browser = find_browser()
            self.process = subprocess.Popen([
                browser, f"--app={self.url}", f"--user-data-dir={self.profile}",
                "--no-first-run", "--no-default-browser-check",
                "--disable-background-mode", "--window-size=860,680",
                "--disable-extensions",
                "--remote-debugging-port=0"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            shutil.rmtree(self.root, ignore_errors=True)
            raise
        self.active = True
        self.thread = threading.Thread(target=self._watch, daemon=True)
        self.thread.start()

    def _browser_endpoint(self):
        """The real browser may outlive its launcher; track its local endpoint."""
        port = int((self.profile / "DevToolsActivePort").read_text().splitlines()[0])
        # Bypass proxy settings for our own loopback endpoint only.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"http://127.0.0.1:{port}/json/version", timeout=1) as r:
            return json.load(r)["webSocketDebuggerUrl"]

    def _close_browser(self):
        """Send Browser.close only to this temporary profile's loopback socket."""
        if not self.endpoint:
            return
        url = urlsplit(self.endpoint)
        if url.hostname not in ("127.0.0.1", "localhost"):
            raise OSError("Unexpected browser endpoint")
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        with socket.create_connection((url.hostname, url.port), timeout=2) as conn:
            conn.sendall((f"GET {url.path} HTTP/1.1\r\nHost: {url.netloc}\r\n"
                          "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                          f"Sec-WebSocket-Key: {key}\r\n"
                          "Sec-WebSocket-Version: 13\r\n\r\n").encode("ascii"))
            headers = b""
            while b"\r\n\r\n" not in headers and len(headers) < 16384:
                part = conn.recv(4096)
                if not part:
                    raise OSError("Browser closed during handshake")
                headers += part
            if not headers.startswith(b"HTTP/1.1 101"):
                raise OSError("Browser close handshake refused")
            data = json.dumps({"id": 1, "method": "Browser.close"}).encode()
            mask = os.urandom(4)
            conn.sendall(bytes((0x81, 0x80 | len(data))) + mask +
                         bytes(byte ^ mask[i % 4] for i, byte in enumerate(data)))
            try:
                conn.recv(4096)
            except socket.timeout:
                pass

    def completed(self):
        """Wait for final .zip names and a stable size, never .crdownload."""
        ready = []
        for path in self.folder.glob("*"):
            if path.suffix.lower() != ".zip" or path in self.seen:
                continue
            if Path(str(path) + ".crdownload").exists():
                continue
            try:
                stat = path.stat()
                signature = (stat.st_size, stat.st_mtime_ns)
                if stat.st_size and self.sizes.get(path) == signature:
                    self.seen.add(path)
                    ready.append(str(path))
                self.sizes[path] = signature
            except OSError:
                continue
        return ready

    def _watch(self):
        deadline = time.monotonic() + 30
        try:
            while not self.stop.wait(1):
                for path in self.completed():
                    self.emit("download", path)
                try:
                    self.endpoint = self._browser_endpoint()
                except (OSError, ValueError, KeyError):
                    if not self.endpoint and time.monotonic() < deadline:
                        continue
                    # One last stable-size check after browser closure.
                    self.stop.wait(1)
                    for path in self.completed():
                        self.emit("download", path)
                    if not self.endpoint:
                        self.emit("log", "Could not connect to the download browser. "
                                  "Download manually and drop the ZIP here.")
                    self.emit("browser_closed",)
                    break
        except OSError as e:
            self.emit("log", f"Download watcher: {e}")
        finally:
            self.active = False

    def close(self):
        """Close only our browser process, then remove its temporary profile."""
        self.stop.set()
        try:
            # Refresh in case close happens before the watcher's first poll.
            self.endpoint = self._browser_endpoint()
            self._close_browser()
        except (OSError, ValueError, KeyError):
            pass
        if self.thread:
            self.thread.join(timeout=3)
        # Edge needs a moment to release its profile files after Browser.close.
        for attempt in range(6):
            shutil.rmtree(self.root, ignore_errors=True)
            if not self.root.exists():
                break
            time.sleep(0.25)
        if self.root.exists():
            self.emit("log", "Some temporary browser files are still in use; "
                      "close the Vector download browser to release them.")
        self.active = False
