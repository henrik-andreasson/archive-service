"""bin/archive-cli.py against real gunicorn servers"""
import json
import subprocess
import sys

import pytest

from conftest import ROOT, clean_env, sha256

pytestmark = pytest.mark.integration

DEAD = "http://127.0.0.1:1"


def cli(*args, cwd=None, **env):
    """run the client, returns (exit code, stdout, stderr)"""
    p = subprocess.run([sys.executable, str(ROOT / "bin" / "archive-cli.py"), *args],
                       cwd=cwd, env=clean_env(ARCHIVE_TIMEOUT="5", **env),
                       capture_output=True, text=True, timeout=60)
    return p.returncode, p.stdout, p.stderr


def field(line, name):
    """value of name:<value> in a ;-separated output line"""
    return dict(part.split(":", 1) for part in line.strip().split(";")[1:])[name]


@pytest.fixture(scope="module")
def servers(start_server):
    return start_server(), start_server()


@pytest.fixture
def server(servers):
    return servers[0]


@pytest.fixture
def a_file(tmp_path):
    path = tmp_path / "a.txt"
    path.write_bytes(b"client test\n")
    return path


def test_store_hash_get_delete(server, a_file, tmp_path):
    rc, out, _ = cli("store", str(a_file), "-b", "cert", "-u", server)
    assert rc == 0
    assert out.startswith("file archived OK;")
    uuid, date = field(out, "uuid"), field(out, "date")
    assert field(out, "hash") == sha256(a_file.read_bytes())

    rc, out, _ = cli("hash", uuid, "-b", "cert", "-t", date, "-u", server)
    assert (rc, out.strip()) == (0, sha256(a_file.read_bytes()))

    rc, out, _ = cli("list", "-b", "cert", "-t", date, "-u", server)
    assert rc == 0 and uuid in out.split()

    output = tmp_path / "back.txt"
    rc, _, _ = cli("get", uuid, "-b", "cert", "-t", date, "-o", str(output), "-u", server)
    assert rc == 0 and output.read_bytes() == a_file.read_bytes()

    rc, _, err = cli("get", uuid, "-b", "cert", "-t", date, "-o", str(output), "-u", server)
    assert rc == 2 and "already exists" in err
    rc, _, _ = cli("get", uuid, "-b", "cert", "-t", date, "-o", str(output), "-f", "-u", server)
    assert rc == 0

    rc, out, _ = cli("delete", uuid, "-b", "cert", "-t", date, "-u", server)
    assert rc == 0 and out.startswith("deleted;")
    rc, _, err = cli("delete", uuid, "-b", "cert", "-t", date, "-u", server)
    assert rc == 1 and "404" in err


def test_get_default_output_is_uuid(server, a_file, tmp_path):
    _, out, _ = cli("store", str(a_file), "-u", server)
    uuid, date = field(out, "uuid"), field(out, "date")
    rc, _, _ = cli("get", uuid, "-t", date, "-u", server, cwd=tmp_path)
    assert rc == 0 and (tmp_path / uuid).read_bytes() == a_file.read_bytes()
    assert not list(tmp_path.glob("*.part"))


def test_store_json(server, a_file):
    rc, out, _ = cli("store", str(a_file), "-j", "-u", server)
    assert rc == 0
    data = json.loads(out)
    assert data["server_hash"] == data["local_hash"] == sha256(a_file.read_bytes())


def test_store_delete_local(server, a_file):
    rc, out, _ = cli("store", str(a_file), "-x", "-u", server)
    assert rc == 0 and "local file deleted" in out
    assert not a_file.exists()


def test_env_settings(server, a_file):
    rc, out, _ = cli("store", str(a_file), ARCHIVE_URL=server, ARCHIVE_BUCKET="log")
    assert rc == 0 and field(out, "bucket") == "log"


def test_list_empty(server):
    rc, out, _ = cli("list", "-b", "log", "-t", "2000-01-01", "-u", server)
    assert (rc, out) == (0, "")


def test_health(server):
    rc, out, _ = cli("health", "-u", server)
    assert rc == 0 and out.startswith("ALLOK")


@pytest.mark.parametrize("args,message", [
    (["list"], "no url"),
    (["store", "missing.txt", "-u", "http://x"], "not a file"),
    (["list", "-t", "2026-10-06", "-u", "http://x"], "--date needs --bucket"),
    (["health", "-k", "key.pem", "-u", "http://x"], "--key given without --cert"),
    (["health", "-m", "bogus", "-u", "http://x"], "--mode must be"),
])
def test_usage_errors(args, message):
    rc, _, err = cli(*args)
    assert rc == 2 and message in err


def test_server_errors(server, a_file):
    rc, _, err = cli("store", str(a_file), "-b", "nope", "-u", server)
    assert rc == 1 and "403" in err
    rc, _, err = cli("hash", "not-a-uuid", "-u", server)
    assert rc == 1 and "400" in err


def test_dead_server(a_file):
    rc, _, err = cli("store", str(a_file), "-u", DEAD)
    assert rc == 1 and "can not connect" in err


# --- several servers ---------------------------------------------------------

def test_first_mode_skips_dead_server(server, a_file):
    rc, out, err = cli("store", str(a_file), "-u", DEAD, "-u", server)
    assert rc == 0 and out.startswith("file archived OK")
    assert "server: %s" % server in err


@pytest.mark.parametrize("sep", [",", " "])
def test_urls_from_env(server, sep):
    rc, _, err = cli("health", ARCHIVE_URL=DEAD + sep + server)
    assert rc == 0 and "server: %s" % server in err


def test_first_mode_all_dead():
    rc, _, err = cli("health", "-u", DEAD, "-u", "http://127.0.0.1:2")
    assert rc == 1 and "failed on all servers" in err


def test_first_mode_only_first_server_stores(servers, a_file):
    s1, s2 = servers
    _, out, _ = cli("store", str(a_file), "-b", "other", "-u", s1, "-u", s2)
    date = field(out, "date")
    assert cli("list", "-b", "other", "-t", date, "-u", s1)[1].strip() != ""
    assert field(out, "uuid") not in cli("list", "-b", "other", "-t", date, "-u", s2)[1]


def test_get_uses_server_that_has_the_file(servers, a_file, tmp_path):
    s1, s2 = servers
    _, out, _ = cli("store", str(a_file), "-u", s2)
    rc, _, err = cli("get", field(out, "uuid"), "-t", field(out, "date"), "-o", str(tmp_path / "x"),
                     "-u", s1, "-u", s2)
    assert rc == 0 and "404" in err and "server: %s" % s2 in err


def test_all_mode_stores_everywhere(servers, a_file):
    s1, s2 = servers
    rc, out, _ = cli("store", str(a_file), "-m", "all", "-u", s1, "-u", s2)
    assert rc == 0
    lines = out.strip().splitlines()
    assert [line.rsplit(";server:", 1)[1] for line in lines] == [s1, s2]
    assert field(lines[0], "uuid") != field(lines[1], "uuid")


def test_all_mode_delete_local_only_when_all_ok(servers, a_file):
    s1, s2 = servers
    rc, _, _ = cli("store", str(a_file), "-x", "-m", "all", "-u", s1, "-u", s2)
    assert rc == 0 and not a_file.exists()


def test_all_mode_keeps_local_file_on_failure(server, a_file):
    rc, out, err = cli("store", str(a_file), "-x", "-m", "all", "-u", server, "-u", DEAD)
    assert rc == 1
    assert "server:%s" % server in out
    assert "NOT deleted" in err and "failed on 1 of 2 servers" in err
    assert a_file.exists()


def test_all_mode_json(server, a_file):
    rc, out, _ = cli("store", str(a_file), "-j", "-m", "all", "-u", server, "-u", DEAD)
    assert rc == 1
    data = json.loads(out)
    assert [r["status"] for r in data["results"]] == ["ok", "failed"]


def test_all_mode_health(servers):
    s1, s2 = servers
    rc, out, _ = cli("health", "-m", "all", "-u", s1, "-u", s2)
    assert rc == 0 and len(out.strip().splitlines()) == 2
    rc, _, _ = cli("health", "-m", "all", "-u", s1, "-u", DEAD)
    assert rc == 1
