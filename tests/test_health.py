import os
import shutil

import pytest

from conftest import CLIENT_A, HEALTH_IP

needs_non_root = pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0,
                                    reason="root can write to read-only dirs")


def test_health_ok(api):
    r = api.get("/archive/health/v1/", ip=HEALTH_IP)
    assert r.status_code == 200
    assert r.get_json()["message"] == "ALLOK"
    # the test file is removed again
    assert os.listdir(api.upload_dir) == []


def test_health_not_allowed(api):
    r = api.get("/archive/health/v1/", ip=CLIENT_A)
    assert r.status_code == 403
    assert r.get_json()["reason"] == "not allowed"


def test_health_archive_missing(api):
    shutil.rmtree(api.upload_dir)
    r = api.get("/archive/health/v1/", ip=HEALTH_IP)
    assert r.status_code == 503
    assert r.get_json()["reason"] == "upload dir does not exist"


@needs_non_root
def test_health_archive_read_only(api):
    os.chmod(api.upload_dir, 0o555)
    try:
        r = api.get("/archive/health/v1/", ip=HEALTH_IP)
    finally:
        os.chmod(api.upload_dir, 0o755)
    assert r.status_code == 503
    assert r.get_json()["reason"] == "can not write to the archive"


def test_health_ip_list(make_api):
    api = make_api(ARCHIVE_IPS_HEALTH="127.0.0.1, 10.0.0.5")
    assert api.get("/archive/health/v1/", ip="10.0.0.5").status_code == 200
    assert api.get("/archive/health/v1/", ip="10.0.0.9").status_code == 403
