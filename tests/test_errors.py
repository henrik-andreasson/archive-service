import os

import pytest

from conftest import CLIENT_A


def test_root(api):
    r = api.get("/")
    assert r.status_code == 200
    assert r.get_json()["module"] == "root"


def test_unknown_url_is_json(api):
    r = api.get("/nope")
    assert r.status_code == 404
    assert r.get_json() == {"module": "error", "status_code": 404, "message": "Not Found"}


def test_wrong_method_is_json(api):
    r = api.client.put("/archive/list/v1/")
    assert r.status_code == 405
    assert r.get_json()["message"] == "Method Not Allowed"


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root can write to read-only dirs")
def test_internal_error_is_json(api, caplog):
    os.chmod(api.upload_dir, 0o555)
    try:
        r = api.store(ip=CLIENT_A)
    finally:
        os.chmod(api.upload_dir, 0o755)
    assert r.status_code == 500
    assert r.get_json() == {"module": "error", "status_code": 500, "message": "Internal server error"}
