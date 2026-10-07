"""gunicorn-start.sh: TLS and client certificate options, update-plan.md §3.1"""
import os
import shutil
import subprocess

import pytest
import requests

from conftest import ROOT, clean_env, free_port, stop, wait_for

pytestmark = pytest.mark.integration

needs_openssl = pytest.mark.skipif(shutil.which("openssl") is None, reason="needs openssl")


@pytest.fixture
def install(tmp_path):
    """a copy of the service, gunicorn-start.sh writes the cert files into it"""
    path = tmp_path / "install"
    path.mkdir()
    shutil.copytree(ROOT / "app", path / "app", ignore=shutil.ignore_patterns("__pycache__"))
    (path / "conf").mkdir()
    shutil.copy(ROOT / "conf" / "defaultserviceconfig.py", path / "conf")
    for name in ("archive-service.py", "gunicorn-start.sh"):
        shutil.copy(ROOT / name, path)
    (tmp_path / "archive").mkdir()
    return path


def start_env(install, port, set_install_path=True, **extra):
    settings = dict(PORT=str(port),
                    ARCHIVE_UPLOAD_DIR=str(install.parent / "archive"),
                    ARCHIVE_LOG_DIR=str(install.parent / "logs"))
    settings.update(extra)
    env = clean_env(**settings)
    if set_install_path:
        env["INSTALL_PATH"] = str(install)
    return env


def cmdline(pid):
    """command line of a running process (linux)"""
    with open("/proc/%d/cmdline" % pid, "rb") as f:
        return f.read().split(b"\0")


def run_start(install, **extra):
    """for configurations that exit before gunicorn starts"""
    return subprocess.run([str(install / "gunicorn-start.sh")], env=start_env(install, free_port(), **extra),
                          capture_output=True, text=True, timeout=30)


def pem(path):
    """PEM as an environment value, newlines replaced by ;"""
    return path.read_text().replace("\n", ";")


@pytest.fixture(scope="module")
def certs(tmp_path_factory):
    """CA, server cert for localhost, client cert and a client cert from another CA"""
    if shutil.which("openssl") is None:
        pytest.skip("needs openssl")
    d = tmp_path_factory.mktemp("certs")

    def ossl(*args):
        subprocess.run(["openssl", *args], cwd=d, check=True, capture_output=True)

    ossl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=Test CA",
         "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign",
         "-keyout", "ca.key", "-out", "ca.crt")
    for name, eku in (("server", "serverAuth"), ("client", "clientAuth")):
        (d / ("%s.ext" % name)).write_text("subjectAltName=DNS:localhost\n"
                                           "keyUsage=critical,digitalSignature,keyEncipherment\n"
                                           "extendedKeyUsage=%s\n" % eku)
        ossl("req", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=%s" % name,
             "-keyout", "%s.key" % name, "-out", "%s.csr" % name)
        ossl("x509", "-req", "-in", "%s.csr" % name, "-CA", "ca.crt", "-CAkey", "ca.key", "-CAcreateserial",
             "-days", "1", "-extfile", "%s.ext" % name, "-out", "%s.crt" % name)
    ossl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=other",
         "-keyout", "other.key", "-out", "other.crt")
    return d


@pytest.fixture
def start_tls(install, certs):
    procs = []

    def _start(**extra):
        port = free_port()
        env = start_env(install, port, CERT=pem(certs / "server.crt"), KEY=pem(certs / "server.key"), **extra)
        proc = subprocess.Popen([str(install / "gunicorn-start.sh")], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        procs.append(proc)
        url = "https://localhost:%d/" % port
        wait_for(url, proc, verify=str(certs / "ca.crt"),
                 cert=(str(certs / "client.crt"), str(certs / "client.key")))
        return url, proc

    yield _start
    for proc in procs:
        stop(proc)


# --- configurations that must not start --------------------------------------

@pytest.mark.parametrize("extra,message", [
    ({"ARCHIVE_CLIENT_CERT": "maybe"}, "must be 'on' or 'off'"),
    ({"ARCHIVE_CLIENT_CERT": "on"}, "requires TLS"),
    ({"CERT": "x"}, "both CERT and KEY"),
    ({"KEY": "x"}, "both CERT and KEY"),
    ({"CERT": "x", "KEY": "x"}, "CA is not set"),
    ({"PORT": "http"}, "must be numbers"),
    ({"TIMEOUT": "long"}, "must be numbers"),
])
def test_refuses_to_start(install, tmp_path, extra, message):
    tls_dir = tmp_path / "tls"
    p = run_start(install, TLS_DIR=str(tls_dir), **extra)
    assert p.returncode == 1
    assert message in p.stderr
    # nothing is written when the settings are refused
    assert not list(install.glob("*.pem"))
    assert not tls_dir.exists()


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root can write to read-only dirs")
def test_refuses_unwritable_upload_dir(install):
    archive = install.parent / "archive"
    os.chmod(archive, 0o555)
    try:
        p = run_start(install)
    finally:
        os.chmod(archive, 0o755)
    assert p.returncode == 1
    assert "is not writable" in p.stderr


# --- TLS ---------------------------------------------------------------------

def start_plain(install, set_install_path=True, cwd=None, **extra):
    port = free_port()
    proc = subprocess.Popen([str(install / "gunicorn-start.sh")],
                            env=start_env(install, port, set_install_path, **extra), cwd=cwd,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    wait_for("http://127.0.0.1:%d/" % port, proc)
    return "http://127.0.0.1:%d/" % port, proc


def test_plain_http(install):
    url, proc = start_plain(install)
    try:
        assert requests.get(url).status_code == 200
        assert (install / "archive.pid").exists()
    finally:
        stop(proc)


def test_install_path_defaults_to_script_dir(install, tmp_path):
    """started from another directory without INSTALL_PATH, eg. ./gunicorn-start.sh in the repo"""
    url, proc = start_plain(install, set_install_path=False, cwd=tmp_path)
    try:
        assert requests.get(url).status_code == 200
        assert (install / "archive.pid").exists()
    finally:
        stop(proc)


@pytest.mark.skipif(not os.path.exists("/proc/self/cmdline"), reason="needs /proc")
@pytest.mark.parametrize("extra,timeout", [({}, b"300"), ({"TIMEOUT": "60"}, b"60")])
def test_worker_timeout(install, extra, timeout):
    url, proc = start_plain(install, **extra)
    try:
        args = cmdline(proc.pid)
        assert args[args.index(b"--timeout") + 1] == timeout
    finally:
        stop(proc)


@needs_openssl
def test_client_cert_required(start_tls, certs, install):
    url, _ = start_tls(CA=pem(certs / "ca.crt"))
    ca = str(certs / "ca.crt")
    r = requests.get(url, verify=ca, cert=(str(certs / "client.crt"), str(certs / "client.key")))
    assert r.status_code == 200
    with pytest.raises(requests.exceptions.SSLError):
        requests.get(url, verify=ca)
    with pytest.raises(requests.exceptions.SSLError):
        requests.get(url, verify=ca, cert=(str(certs / "other.crt"), str(certs / "other.key")))
    # the cert files are not written into the install dir
    assert not list(install.glob("*.pem"))


@needs_openssl
def test_client_cert_off(start_tls, certs):
    url, _ = start_tls(ARCHIVE_CLIENT_CERT="off")
    assert requests.get(url, verify=str(certs / "ca.crt")).status_code == 200


@needs_openssl
def test_tls_files_private(start_tls, certs, tmp_path):
    tls_dir = tmp_path / "tls"
    start_tls(CA=pem(certs / "ca.crt"), TLS_DIR=str(tls_dir))
    assert oct(tls_dir.stat().st_mode & 0o777) == "0o700"
    assert sorted(p.name for p in tls_dir.iterdir()) == ["ca.pem", "cert.pem", "key.pem"]
    assert oct((tls_dir / "key.pem").stat().st_mode & 0o777) == "0o600"


@needs_openssl
@pytest.mark.skipif(not os.path.isdir("/dev/shm"), reason="needs /dev/shm")
def test_tls_files_in_memory_by_default(start_tls, certs):
    _, proc = start_tls(CA=pem(certs / "ca.crt"))
    args = cmdline(proc.pid)
    keyfile = args[args.index(b"--keyfile") + 1].decode()
    assert keyfile.startswith("/dev/shm/archive-service-tls.")
