import pytest

from conftest import MISSING_UUID, sha256


def test_get_ok(api):
    content = b"get me back\n"
    uuid, date = api.stored(content=content)
    r = api.get("/archive/get/v1/cert/%s/%s" % (date, uuid))
    assert r.status_code == 200
    assert r.data == content
    assert "attachment" in r.headers["Content-Disposition"]


def test_hash_ok(api):
    content = b"hash me\n"
    uuid, date = api.stored(content=content)
    r = api.get("/archive/hash/v1/cert/%s/%s" % (date, uuid))
    assert r.status_code == 200
    body = r.get_json()
    assert body["hash_remote"] == sha256(content)
    assert body == {"module": "hash", "status_code": 200, "message": "OK", "filename": uuid,
                    "bucket": "cert", "date": date, "hash_remote": sha256(content)}


@pytest.mark.parametrize("endpoint", ["get", "hash"])
def test_not_found(api, endpoint):
    _, date = api.stored()
    r = api.get("/archive/%s/v1/cert/%s/%s" % (endpoint, date, MISSING_UUID))
    assert r.status_code == 404
    assert r.get_json()["message"] == "File not found"


@pytest.mark.parametrize("endpoint", ["get", "hash"])
def test_wrong_date_is_not_found(api, endpoint):
    uuid, _ = api.stored()
    r = api.get("/archive/%s/v1/cert/2000-01-01/%s" % (endpoint, uuid))
    assert r.status_code == 404


@pytest.mark.parametrize("endpoint", ["get", "hash"])
@pytest.mark.parametrize("date,filename,message", [
    ("2026-1-1", MISSING_UUID, "Date must be formated YYYY-MM-DD"),
    ("yesterday", MISSING_UUID, "Date must be formated YYYY-MM-DD"),
    ("2026-10-06", "not-a-uuid", "Filename must be a uuid"),
    ("2026-10-06", "6F9619FF-8B86-4011-B42D-00C04FC964FF", "Filename must be a uuid"),
])
def test_bad_parameters(api, endpoint, date, filename, message):
    r = api.get("/archive/%s/v1/cert/%s/%s" % (endpoint, date, filename))
    assert r.status_code == 400
    assert r.get_json()["message"] == message


@pytest.mark.parametrize("endpoint", ["get", "hash"])
def test_bucket_not_allowed(api, endpoint):
    r = api.get("/archive/%s/v1/nope/2026-10-06/%s" % (endpoint, MISSING_UUID))
    assert r.status_code == 403
