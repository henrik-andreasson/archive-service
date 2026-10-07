import pytest

from conftest import CLIENT_A, MISSING_UUID, sha256


def url(date, uuid, bucket="cert"):
    return "/archive/delete/v1/%s/%s/%s" % (bucket, date, uuid)


def test_delete_disabled_by_default(api):
    uuid, date = api.stored()
    r = api.delete(url(date, uuid))
    assert r.status_code == 403
    assert r.get_json()["message"] == "FAIL: delete not allowed"
    assert (api.upload_dir / CLIENT_A / "cert" / date / uuid).exists()


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_delete_enabled(make_api, value):
    api = make_api(ARCHIVE_ALLOW_REMOVE=value)
    content = b"delete me\n"
    uuid, date = api.stored(content=content)
    r = api.delete(url(date, uuid))
    assert r.status_code == 200
    assert r.get_json()["hash_remote"] == sha256(content)
    assert not (api.upload_dir / CLIENT_A / "cert" / date / uuid).exists()

    r = api.delete(url(date, uuid))
    assert r.status_code == 404
    assert r.get_json()["message"] == "File not found"


@pytest.mark.parametrize("value", ["0", "false", "no", "off", ""])
def test_delete_disabled_values(make_api, value):
    api = make_api(ARCHIVE_ALLOW_REMOVE=value)
    uuid, date = api.stored()
    assert api.delete(url(date, uuid)).status_code == 403


def test_delete_with_get_not_allowed(make_api):
    api = make_api(ARCHIVE_ALLOW_REMOVE="true")
    uuid, date = api.stored()
    assert api.get(url(date, uuid)).status_code == 405
    assert (api.upload_dir / CLIENT_A / "cert" / date / uuid).exists()


@pytest.mark.parametrize("date,uuid,status", [
    ("xx", MISSING_UUID, 400),
    ("2026-10-06", "nope", 400),
    ("2026-10-06", MISSING_UUID, 404),
])
def test_delete_bad_parameters(make_api, date, uuid, status):
    api = make_api(ARCHIVE_ALLOW_REMOVE="true")
    assert api.delete(url(date, uuid)).status_code == status


def test_delete_bucket_not_allowed(make_api):
    api = make_api(ARCHIVE_ALLOW_REMOVE="true")
    assert api.delete(url("2026-10-06", MISSING_UUID, bucket="nope")).status_code == 403
