"""the security fixes from update-plan.md §3"""
import pytest

from conftest import CLIENT_A, CLIENT_B, HEALTH_IP, MISSING_UUID


# --- each client only sees its own files, X-Forwarded-For is not trusted ----

def test_other_client_can_not_get_file(api):
    uuid, date = api.stored(ip=CLIENT_A)
    assert api.get("/archive/get/v1/cert/%s/%s" % (date, uuid), ip=CLIENT_B).status_code == 404


def test_xff_ignored_by_default(api):
    uuid, date = api.stored(ip=CLIENT_A)
    spoof = {"X-Forwarded-For": CLIENT_A}
    assert api.get("/archive/get/v1/cert/%s/%s" % (date, uuid), ip=CLIENT_B, headers=spoof).status_code == 404


def test_xff_ignored_on_store(api):
    r = api.store(ip=CLIENT_A, headers={"X-Forwarded-For": CLIENT_B})
    assert r.status_code == 200
    assert (api.upload_dir / CLIENT_A).is_dir()
    assert not (api.upload_dir / CLIENT_B).exists()


def test_xff_path_can_not_list_other_dirs(api):
    r = api.get("/archive/list/v1/", headers={"X-Forwarded-For": "/etc"})
    assert r.status_code == 200
    assert r.get_json() == []


def test_xff_can_not_fake_health_ip(api):
    r = api.get("/archive/health/v1/", ip=CLIENT_A, headers={"X-Forwarded-For": HEALTH_IP})
    assert r.status_code == 403


def test_invalid_client_address(api):
    r = api.get("/archive/list/v1/", ip="garbage")
    assert r.status_code == 400
    assert r.get_json()["message"] == "Invalid client address"


# --- with trusted proxies ---------------------------------------------------

def test_proxy_count_uses_xff(make_api):
    api = make_api(ARCHIVE_PROXY_COUNT="1")
    proxy = "172.17.0.1"
    r = api.store(ip=proxy, headers={"X-Forwarded-For": CLIENT_A})
    assert r.status_code == 200
    assert (api.upload_dir / CLIENT_A).is_dir()


def test_proxy_count_uses_rightmost_entry(make_api):
    """the client can add entries to the left, the proxy appends the real address"""
    api = make_api(ARCHIVE_PROXY_COUNT="1")
    uuid, date = api.stored(ip=CLIENT_A)
    url = "/archive/get/v1/cert/%s/%s" % (date, uuid)
    assert api.get(url, ip="172.17.0.1", headers={"X-Forwarded-For": CLIENT_B + ", " + CLIENT_A}).status_code == 200
    assert api.get(url, ip="172.17.0.1", headers={"X-Forwarded-For": CLIENT_A + ", " + CLIENT_B}).status_code == 404


def test_proxy_count_rejects_path_in_xff(make_api):
    api = make_api(ARCHIVE_PROXY_COUNT="1")
    r = api.get("/archive/list/v1/", ip="172.17.0.1", headers={"X-Forwarded-For": "/etc"})
    assert r.status_code == 400


# --- path traversal --------------------------------------------------------

def test_list_dotdot_bucket(api):
    api.stored(ip=CLIENT_B)
    assert api.get("/archive/list/v1/../").status_code == 403


@pytest.mark.parametrize("url,status", [
    ("/archive/get/v1/cert/../%s" % MISSING_UUID, 400),
    ("/archive/get/v1/cert/2026-10-06/..", 400),
    ("/archive/hash/v1/cert/../%s" % MISSING_UUID, 400),
    ("/archive/hash/v1/cert/2026-10-06/..", 400),
    ("/archive/hash/v1/../2026-10-06/%s" % MISSING_UUID, 403),
    ("/archive/list/v1/cert/../", 400),
])
def test_dotdot_in_path(api, url, status):
    assert api.get(url).status_code == status


def test_delete_dotdot(make_api):
    api = make_api(ARCHIVE_ALLOW_REMOVE="true")
    assert api.delete("/archive/delete/v1/cert/2026-10-06/..").status_code == 400
    assert api.delete("/archive/delete/v1/cert/../%s" % MISSING_UUID).status_code == 400


# --- exact matching of buckets and health ips ---------------------------------

@pytest.mark.parametrize("bucket", ["ce", "r", "t,o", "cert,other", " cert"])
def test_bucket_exact_match(make_api, bucket):
    api = make_api(ARCHIVE_BUCKETS="cert,other")
    assert api.store(bucket=bucket).status_code == 403


@pytest.mark.parametrize("ip", ["27.0.0.1", "7.0.0.1", "127.0.0.11"])
def test_health_ip_exact_match(make_api, ip):
    api = make_api(ARCHIVE_IPS_HEALTH="127.0.0.1")
    assert api.get("/archive/health/v1/", ip=ip).status_code == 403
