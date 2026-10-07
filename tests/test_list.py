def test_list_nothing_stored(api):
    r = api.get("/archive/list/v1/")
    assert r.status_code == 200
    assert r.get_json() == []


def test_list_levels(api):
    uuid, date = api.stored(bucket="cert")
    api.stored(bucket="other")
    assert sorted(api.get("/archive/list/v1/").get_json()) == ["cert", "other"]
    assert api.get("/archive/list/v1/cert/").get_json() == [date]
    assert api.get("/archive/list/v1/cert/%s/" % date).get_json() == [uuid]


def test_list_empty_bucket(api):
    api.stored(bucket="cert")
    r = api.get("/archive/list/v1/log/")
    assert r.status_code == 200
    assert r.get_json() == []


def test_list_empty_date(api):
    api.stored(bucket="cert")
    assert api.get("/archive/list/v1/cert/2000-01-01/").get_json() == []


def test_list_bucket_not_allowed(api):
    assert api.get("/archive/list/v1/nope/").status_code == 403


def test_list_bad_date(api):
    r = api.get("/archive/list/v1/cert/xx/")
    assert r.status_code == 400
    assert r.get_json()["message"] == "Date must be formated YYYY-MM-DD"
