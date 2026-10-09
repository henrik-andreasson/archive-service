"""the web front-end in a real headless browser, skipped without Chrome/Chromium and Node"""
import json
import os
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT, clean_env

pytestmark = pytest.mark.integration

# CHROME picks the browser, else the first one found. google-chrome first:
# on Ubuntu chromium-browser can be a stub that only asks to install the snap
CHROME = os.environ.get("CHROME") or next(
    (shutil.which(name) for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
     if shutil.which(name)), None)
NODE = shutil.which("node")

needs_browser = pytest.mark.skipif(CHROME is None or NODE is None, reason="needs Chrome/Chromium and Node")

HOSTILE_NAME = "<img src=x onerror=alert(1)>.txt"


@pytest.fixture(scope="module")
def ui_server(start_server):
    return start_server(ARCHIVE_UI="true")


def cli(url, *args):
    subprocess.run([sys.executable, str(ROOT / "bin" / "archive-cli.py"), *args, "-u", url],
                   env=clean_env(), check=True, capture_output=True)


@needs_browser
def test_ui_in_browser(ui_server, tmp_path):
    hostile = tmp_path / HOSTILE_NAME
    hostile.write_text("x\n")
    cli(ui_server, "store", str(hostile), "-b", "cert")
    upload = tmp_path / "browser-upload.txt"
    upload.write_text("uploaded from the browser\n")

    p = subprocess.run([NODE, str(ROOT / "tests" / "ui_browser.mjs"), CHROME, ui_server + "/ui/", str(upload)],
                       capture_output=True, text=True, timeout=120)
    try:
        result = json.loads(p.stdout)
    except ValueError:
        pytest.fail("ui_browser.mjs printed no result, exit %s\nstdout: %s\nstderr: %s"
                    % (p.returncode, p.stdout[-2000:], p.stderr[-2000:]))
    assert "error" not in result, "%s (step: %s)\nbrowser log: %s\nresult: %s" % (
        result["error"], result.get("step"), result.get("browser_log"), json.dumps(result, indent=1)) \
        if "error" in result else ""

    # 127.0.0.1 is a secure context, so the sha256 is checked in the browser
    assert result["secure_context"] is True
    assert result["client"] == "client address: 127.0.0.1"
    assert result["buckets"][0] == "cert"

    # the hostile name is shown as text
    assert [row[0] for row in result["browse_before"]] == [HOSTILE_NAME]
    assert result["html_elements_in_names"] == 0

    assert result["upload"][0] == "browser-upload.txt"
    assert result["upload"][1] == "stored, sha256 matches"
    assert "browser-upload.txt" in [row[0] for row in result["browse_after_upload"]]

    assert result["dialog"] == "Delete browser-upload.txt from the archive?"
    assert [row[0] for row in result["browse_after_delete"]] == [HOSTILE_NAME]

    assert result["problems"] == []
