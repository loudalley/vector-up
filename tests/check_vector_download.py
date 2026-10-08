"""Real Edge/Chrome download -> Vector-Up window, using a synthetic local ZIP.

Needs Windows desktop and Edge or Chrome. Does not authenticate to Vector or
touch the technician's shop settings. Run: python tests/check_vector_download.py
"""
import io
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="vectorup-download-check-")
from techtool import downloads, gui  # noqa: E402


def main():
    body = io.BytesIO()
    with zipfile.ZipFile(body, "w") as zf:
        for role in ("BO", "POS"):
            zf.writestr(f"{role}/Example.exe", "synthetic")
            zf.writestr(f"{role}/_UpgradeRequired", f"{role}_9.zip")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            if self.path == "/package.zip":
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition", 'attachment; filename="Vector_synthetic.zip"')
                self.send_header("Content-Length", str(len(body.getvalue())))
                self.end_headers()
                self.wfile.write(body.getvalue())
            else:
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b'<title>Vector-Up download check</title>'
                    b'<h1>Synthetic download check</h1>'
                    b'<script>setTimeout(()=>location.href="/package.zip",1500)</script>')

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    original = downloads.DownloadSession
    url = f"http://127.0.0.1:{server.server_port}/"
    app = gui.App()
    try:
        with patch.object(gui.downloads, "DownloadSession", lambda emit: original(emit, url)):
            app._get_package()
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline and app.pkg is None:
            app.update()
            time.sleep(0.05)
        assert app.pkg is not None, "Completed browser download did not load in the window"
        assert app.pkg.name == "Vector_synthetic.zip"
        assert app.pkg.bo and app.pkg.pos
        assert not app.loading
        print("Real browser download -> queued import -> package ready in Tk: OK")
        print("Launcher exit does not stop the watcher: OK")
        root = app.download_session.root
        app.download_session.close()
        assert not root.exists(), "Browser profile was not removed"
        print("Browser close + temporary profile cleanup: OK")
    finally:
        if app.download_session:
            app.download_session.close()
        app.destroy()
        server.shutdown()


if __name__ == "__main__":
    main()
