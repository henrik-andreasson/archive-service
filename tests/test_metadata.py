"""metadata next to stored files and list with details, update-plan.md §11 step 1"""
import datetime
import io
import json

from conftest import CLIENT_A, sha256


def stored_path(api, uuid, date, bucket="cert"):
    return api.upload_dir / CLIENT_A / bucket / date / uuid


def store_named(api, name, content=b"hello\n", bucket="cert"):
    r = api.client.post("/archive/store/v1",
                        data={"bucket": bucket, "file": (io.BytesIO(content), name)},
                        environ_base={"REMOTE_ADDR": CLIENT_A})
    assert r.status_code == 200
    return r.get_json()


def test_store_writes_metadata(api):
    content = b"metadata test\n"
    body = store_named(api, "report.pdf", content)
    assert body["name"] == "report.pdf"
    assert body["size"] == len(content)

    metadata = json.loads((stored_path(api, body["uuid"], body["date"]).parent / (body["uuid"] + ".json")).read_text())
    assert metadata["uuid"] == body["uuid"]
    assert metadata["name"] == "report.pdf"
    assert metadata["size"] == len(content)
    assert metadata["sha256"] == sha256(content)
    assert metadata["bucket"] == "cert"
    assert metadata["date"] == body["date"]
    assert datetime.datetime.fromisoformat(metadata["stored"]).tzinfo is not None


def test_store_keeps_only_the_file_name(api):
    assert store_named(api, "../../etc/passwd")["name"] == "passwd"
    windows = store_named(api, "C:\\Users\\me\\backup.zip")["name"]
    assert windows.endswith("backup.zip") and "\\" not in windows and "/" not in windows
    assert store_named(api, "x" * 400 + ".txt")["name"] == "x" * 255


def test_list_hides_metadata_files(api):
    body = store_named(api, "a.txt")
    assert api.get("/archive/list/v1/cert/%s/" % body["date"]).get_json() == [body["uuid"]]


def test_list_details(api):
    first = store_named(api, "a.txt", b"aaa")
    second = store_named(api, "b.bin", b"bbbbbb")
    r = api.get("/archive/list/v1/cert/%s/?details=1" % first["date"])
    assert r.status_code == 200
    files = {f["uuid"]: f for f in r.get_json()}
    assert files[first["uuid"]] == {"uuid": first["uuid"], "name": "a.txt", "size": 3,
                                    "sha256": sha256(b"aaa"), "stored": files[first["uuid"]]["stored"]}
    assert files[second["uuid"]]["name"] == "b.bin"
    assert files[second["uuid"]]["size"] == 6


def test_list_details_file_without_metadata(api):
    """files stored before the metadata was kept"""
    body = store_named(api, "old.txt", b"old")
    path = stored_path(api, body["uuid"], body["date"])
    (path.parent / (body["uuid"] + ".json")).unlink()
    files = api.get("/archive/list/v1/cert/%s/?details=1" % body["date"]).get_json()
    assert files == [{"uuid": body["uuid"], "name": None, "size": 3, "sha256": None, "stored": None}]


def test_list_details_only_on_date_level(api):
    body = store_named(api, "a.txt")
    assert api.get("/archive/list/v1/?details=1").get_json() == ["cert"]
    assert api.get("/archive/list/v1/cert/?details=1").get_json() == [body["date"]]


def test_metadata_file_can_not_be_fetched(api):
    body = store_named(api, "a.txt")
    r = api.get("/archive/get/v1/cert/%s/%s.json" % (body["date"], body["uuid"]))
    assert r.status_code == 400


def test_delete_removes_metadata(make_api):
    api = make_api(ARCHIVE_ALLOW_REMOVE="true")
    body = store_named(api, "a.txt")
    path = stored_path(api, body["uuid"], body["date"])
    assert api.delete("/archive/delete/v1/cert/%s/%s" % (body["date"], body["uuid"])).status_code == 200
    assert list(path.parent.iterdir()) == []


def test_get_and_hash_unchanged(api):
    content = b"same as before\n"
    body = store_named(api, "a.txt", content)
    assert api.get("/archive/get/v1/cert/%s/%s" % (body["date"], body["uuid"])).data == content
    assert api.get("/archive/hash/v1/cert/%s/%s" % (body["date"], body["uuid"])).get_json()["hash_remote"] == sha256(content)
