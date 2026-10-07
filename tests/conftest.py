import hashlib
import io
import os
import pathlib
import socket
import subprocess
import sys
import time

import pytest
import requests

from app import create_app
from conf.defaultserviceconfig import Config

ROOT = pathlib.Path(__file__).resolve().parent.parent

CLIENT_A = "10.0.0.5"
CLIENT_B = "10.0.0.9"
HEALTH_IP = "127.0.0.1"
MISSING_UUID = "00000000-0000-4000-8000-000000000000"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture(autouse=True)
def no_archive_env(monkeypatch):
    """settings from the developer's environment must not leak into the tests"""
    for key in list(os.environ):
        if key.startswith("ARCHIVE_"):
            monkeypatch.delenv(key)


@pytest.fixture
def make_app(tmp_path):
    """create an app with test defaults, keyword arguments override settings"""
    def _make(**settings):
        config = dict(
            ARCHIVE_CONFIG=str(tmp_path / "no-config-file.py"),
            ARCHIVE_UPLOAD_DIR=str(tmp_path / "archive"),
            ARCHIVE_LOG_DIR=str(tmp_path / "logs"),
            ARCHIVE_LOG_FILE="archive-service.log",
            ARCHIVE_BUCKETS="cert,other,log",
            ARCHIVE_IPS_HEALTH=HEALTH_IP,
            ARCHIVE_ALLOW_REMOVE="false",
            ARCHIVE_DEBUG="false",
            ARCHIVE_TZ="Europe/Stockholm",
            ARCHIVE_PROXY_COUNT="0",
            ARCHIVE_MAX_UPLOAD_MB="1024",
            ARCHIVE_LOG_MAX_MB="10",
            ARCHIVE_LOG_BACKUPS="10",
            ARCHIVE_LOG_STDERR="false",
        )
        config.update(settings)
        os.makedirs(config["ARCHIVE_UPLOAD_DIR"], exist_ok=True)
        return create_app(type("TestConfig", (Config,), config))
    return _make


class Api:
    """small wrapper around the flask test client, requests come from ip"""

    def __init__(self, client, upload_dir):
        self.client = client
        self.upload_dir = pathlib.Path(upload_dir)

    def store(self, bucket="cert", content=b"hello\n", ip=CLIENT_A, headers=None, file=True):
        data = {}
        if bucket is not None:
            data["bucket"] = bucket
        if file:
            data["file"] = (io.BytesIO(content), "test.txt")
        return self.client.post("/archive/store/v1", data=data,
                                environ_base={"REMOTE_ADDR": ip}, headers=headers or {})

    def stored(self, content=b"hello\n", bucket="cert", ip=CLIENT_A):
        """store a file and return (uuid, date)"""
        r = self.store(bucket=bucket, content=content, ip=ip)
        assert r.status_code == 200, r.get_json()
        return r.get_json()["uuid"], r.get_json()["date"]

    def get(self, url, ip=CLIENT_A, headers=None):
        return self.client.get(url, environ_base={"REMOTE_ADDR": ip}, headers=headers or {})

    def delete(self, url, ip=CLIENT_A, headers=None):
        return self.client.delete(url, environ_base={"REMOTE_ADDR": ip}, headers=headers or {})


@pytest.fixture
def make_api(make_app):
    def _make(**settings):
        app = make_app(**settings)
        return Api(app.test_client(), app.config["ARCHIVE_UPLOAD_DIR"])
    return _make


@pytest.fixture
def api(make_api):
    return make_api()


# --- real servers for the integration tests -------------------------------

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def clean_env(**extra):
    """environment without ARCHIVE_* settings, with the python bin dir on PATH"""
    env = {k: v for k, v in os.environ.items() if not k.startswith("ARCHIVE_")}
    env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
    env.update(extra)
    return env


def wait_for(url, proc, timeout=15, **kwargs):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            out = proc.stdout.read() if proc.stdout else ""
            raise RuntimeError("server exited with %s:\n%s" % (proc.returncode, out))
        try:
            requests.get(url, timeout=1, **kwargs)
            return
        except requests.RequestException:
            time.sleep(0.2)
    raise RuntimeError("server did not start: %s" % url)


def stop(proc):
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="module")
def start_server(tmp_path_factory):
    """start gunicorn with archive-service:app, returns the url"""
    procs = []

    def _start(**settings):
        base = tmp_path_factory.mktemp("server")
        port = free_port()
        env = clean_env(
            ARCHIVE_CONFIG=str(base / "empty-config.py"),
            ARCHIVE_UPLOAD_DIR=str(base / "archive"),
            ARCHIVE_LOG_DIR=str(base / "logs"),
            ARCHIVE_IPS_HEALTH=HEALTH_IP,
            ARCHIVE_ALLOW_REMOVE="true",
            **settings)
        os.makedirs(env["ARCHIVE_UPLOAD_DIR"])
        open(env["ARCHIVE_CONFIG"], "w").close()
        proc = subprocess.Popen(
            [sys.executable, "-m", "gunicorn", "archive-service:app", "-b", "127.0.0.1:%d" % port],
            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        procs.append(proc)
        url = "http://127.0.0.1:%d" % port
        wait_for(url + "/", proc)
        return url

    yield _start
    for proc in procs:
        stop(proc)
