import datetime
from zoneinfo import ZoneInfo

import pytest

from conftest import CLIENT_A, sha256


def test_store_ok(api):
    content = b"some file content\n"
    r = api.store(content=content)
    assert r.status_code == 200
    body = r.get_json()
    assert body["message"] == "OK"
    assert body["bucket"] == "cert"
    assert body["server_hash"] == sha256(content)
    assert body["filename"] == body["uuid"]

    stored = api.upload_dir / CLIENT_A / "cert" / body["date"] / body["uuid"]
    assert stored.read_bytes() == content


def test_store_missing_bucket(api):
    r = api.store(bucket=None)
    assert r.status_code == 400
    assert r.get_json()["message"] == "Bucket is required"


def test_store_missing_file(api):
    r = api.store(file=False)
    assert r.status_code == 400
    assert r.get_json()["message"] == "File is required"


def test_store_bucket_not_allowed(api):
    r = api.store(bucket="nope")
    assert r.status_code == 403
    assert r.get_json()["message"] == "Bucket name is not allowed"


def test_store_wrong_method(api):
    r = api.get("/archive/store/v1")
    assert r.status_code == 405
    assert r.get_json()["module"] == "error"


@pytest.mark.parametrize("tz", ["Pacific/Kiritimati", "Pacific/Pago_Pago", "UTC"])
def test_store_date_dir_follows_tz(make_api, tz):
    api = make_api(ARCHIVE_TZ=tz)
    _, date = api.stored()
    assert date == datetime.datetime.now(ZoneInfo(tz)).strftime("%Y-%m-%d")


def test_store_too_large(make_api):
    api = make_api(ARCHIVE_MAX_UPLOAD_MB="1")
    assert api.store(content=b"x" * 512 * 1024).status_code == 200
    r = api.store(content=b"x" * 2 * 1024 * 1024)
    assert r.status_code == 413
    assert r.get_json()["message"] == "Upload too large, the limit is 1 MB"


def test_store_no_upload_limit(make_api):
    api = make_api(ARCHIVE_MAX_UPLOAD_MB="0")
    assert api.store(content=b"x" * 2 * 1024 * 1024).status_code == 200
