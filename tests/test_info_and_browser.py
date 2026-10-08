"""info endpoint, cross-site protection and security headers, update-plan.md §11 step 1"""
import pytest

from conftest import CLIENT_A, MISSING_UUID

HOST = "localhost"  # the test client's host


def test_info(make_api):
    api = make_api(ARCHIVE_BUCKETS="cert,backups", ARCHIVE_ALLOW_REMOVE="true", ARCHIVE_MAX_UPLOAD_MB="5")
    r = api.get("/archive/info/v1")
    assert r.status_code == 200
    assert r.get_json() == {"module": "info", "status_code": 200, "message": "OK",
                            "buckets": ["cert", "backups"], "allow_remove": True,
                            "max_upload_mb": 5, "client_address": CLIENT_A}


def test_info_invalid_client(api):
    assert api.get("/archive/info/v1", ip="garbage").status_code == 400


# --- cross-site requests ---------------------------------------------------------

@pytest.mark.parametrize("origin", ["https://evil.example", "http://localhost:9999", "null"])
def test_cross_site_store_refused(api, origin):
    r = api.store(headers={"Origin": origin})
    assert r.status_code == 403
    assert r.get_json()["message"] == "Cross-site request not allowed"
    assert not (api.upload_dir / CLIENT_A).exists()


def test_cross_site_delete_refused(make_api):
    api = make_api(ARCHIVE_ALLOW_REMOVE="true")
    uuid, date = api.stored()
    r = api.delete("/archive/delete/v1/cert/%s/%s" % (date, uuid), headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert (api.upload_dir / CLIENT_A / "cert" / date / uuid).exists()


@pytest.mark.parametrize("origin", ["http://%s" % HOST, "https://%s" % HOST])
def test_same_site_store_allowed(api, origin):
    assert api.store(headers={"Origin": origin}).status_code == 200


def test_no_origin_allowed(api):
    """curl and the client send no Origin"""
    assert api.store().status_code == 200


def test_cross_site_get_allowed(api):
    """reading is protected by the browser's same-origin policy, links from other sites keep working"""
    uuid, date = api.stored()
    r = api.get("/archive/get/v1/cert/%s/%s" % (date, uuid), headers={"Origin": "https://other.example"})
    assert r.status_code == 200


# --- security headers -------------------------------------------------------

@pytest.mark.parametrize("url", ["/", "/archive/info/v1", "/archive/list/v1/", "/nope",
                                 "/archive/hash/v1/cert/2026-10-06/%s" % MISSING_UUID])
def test_security_headers(api, url):
    r = api.get(url)
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "no-referrer"


def test_security_headers_on_download(api):
    uuid, date = api.stored()
    r = api.get("/archive/get/v1/cert/%s/%s" % (date, uuid))
    assert r.headers["X-Content-Type-Options"] == "nosniff"
