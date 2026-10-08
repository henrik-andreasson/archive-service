"""the web front-end at /ui/, update-plan.md §11 step 2"""
import io
import re

import pytest

from conftest import CLIENT_A, ROOT

UI_FILES = ["index.html", "app.js", "app.css"]


@pytest.mark.parametrize("url", ["/ui/", "/ui/index.html", "/ui/app.js", "/static/ui/index.html",
                                 "/static/loading.gif"])
def test_ui_off_by_default(api, url):
    assert api.get(url).status_code == 404


def test_ui_page(make_api):
    api = make_api(ARCHIVE_UI="true")
    r = api.get("/ui/")
    assert r.status_code == 200
    assert r.mimetype == "text/html"
    assert b"Archive Service" in r.data
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]


@pytest.mark.parametrize("name,mimetype", [("app.js", "text/javascript"), ("app.css", "text/css"),
                                           ("favicon.svg", "image/svg+xml")])
def test_ui_assets(make_api, name, mimetype):
    api = make_api(ARCHIVE_UI="true")
    r = api.get("/ui/" + name)
    assert r.status_code == 200
    assert r.mimetype == mimetype


def test_ui_redirects_to_slash(make_api):
    api = make_api(ARCHIVE_UI="true")
    r = api.get("/ui")
    assert r.status_code == 308
    assert r.headers["Location"].endswith("/ui/")


@pytest.mark.parametrize("url", ["/ui/../main/archive.py", "/ui/%2e%2e/main/ui.py", "/ui/missing.js"])
def test_ui_only_serves_its_files(make_api, url):
    api = make_api(ARCHIVE_UI="true")
    assert api.get(url).status_code == 404


def test_page_works_with_the_csp():
    """the Content-Security-Policy blocks inline scripts, styles and event handlers"""
    html = (ROOT / "app" / "static" / "ui" / "index.html").read_text()
    assert re.findall(r"<script[^>]*>", html) == ['<script src="app.js" defer>']
    assert "<style" not in html
    assert not re.search(r"\sstyle=", html)
    assert not re.search(r"\son[a-z]+=", html)


def test_script_does_not_use_inner_html():
    """file names come from users, text must be set with textContent"""
    js = (ROOT / "app" / "static" / "ui" / "app.js").read_text()
    for unsafe in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert unsafe not in js


def test_download_uses_original_name(api):
    r = api.client.post("/archive/store/v1",
                        data={"bucket": "cert", "file": (io.BytesIO(b"x"), "report 2026.pdf")},
                        environ_base={"REMOTE_ADDR": CLIENT_A})
    body = r.get_json()
    r = api.get("/archive/get/v1/cert/%s/%s" % (body["date"], body["uuid"]))
    assert "attachment" in r.headers["Content-Disposition"]
    assert "report 2026.pdf" in r.headers["Content-Disposition"]


def test_download_without_metadata_uses_uuid(api):
    uuid, date = api.stored()
    (api.upload_dir / CLIENT_A / "cert" / date / (uuid + ".json")).unlink()
    r = api.get("/archive/get/v1/cert/%s/%s" % (date, uuid))
    assert uuid in r.headers["Content-Disposition"]


def test_ui_setting_parsed(make_app):
    assert make_app(ARCHIVE_UI="yes").config["ARCHIVE_UI"] is True
    assert make_app().config["ARCHIVE_UI"] is False
