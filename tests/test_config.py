"""config parsing, update-plan.md §3.4, §3.5 and §4"""
import importlib

import pytest

import conf.defaultserviceconfig as defaultserviceconfig
from app import create_app
from conf.defaultserviceconfig import to_bool, to_list
from conftest import ROOT


@pytest.mark.parametrize("value", ["1", "true", "True", "YES", "on", " on ", True, 1])
def test_to_bool_true(value):
    assert to_bool(value) is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "maybe", False, 0, None])
def test_to_bool_false(value):
    assert to_bool(value) is False


@pytest.mark.parametrize("value,expected", [
    ("cert,other", ["cert", "other"]),
    ("cert, other ,", ["cert", "other"]),
    ('"cert","other"', ["cert", "other"]),
    ("'cert'", ["cert"]),
    ("", []),
    (["cert", " other "], ["cert", "other"]),
])
def test_to_list(value, expected):
    assert to_list(value) == expected


def test_types_after_normalize(make_app):
    config = make_app(ARCHIVE_BUCKETS="cert, other", ARCHIVE_ALLOW_REMOVE="YES", ARCHIVE_DEBUG="on",
                      ARCHIVE_PROXY_COUNT="2", ARCHIVE_MAX_UPLOAD_MB="5").config
    assert config["ARCHIVE_BUCKETS"] == ["cert", "other"]
    assert config["ARCHIVE_ALLOW_REMOVE"] is True
    assert config["ARCHIVE_DEBUG"] is True
    assert config["ARCHIVE_PROXY_COUNT"] == 2
    assert config["MAX_CONTENT_LENGTH"] == 5 * 1024 * 1024


def test_no_upload_limit(make_app):
    assert make_app(ARCHIVE_MAX_UPLOAD_MB="0").config["MAX_CONTENT_LENGTH"] is None


@pytest.mark.parametrize("setting,value,message", [
    ("ARCHIVE_PROXY_COUNT", "two", "ARCHIVE_PROXY_COUNT must be a number"),
    ("ARCHIVE_PROXY_COUNT", "-1", "ARCHIVE_PROXY_COUNT must be 0 or more"),
    ("ARCHIVE_MAX_UPLOAD_MB", "lots", "ARCHIVE_MAX_UPLOAD_MB must be a number"),
    ("ARCHIVE_LOG_MAX_MB", "-1", "ARCHIVE_LOG_MAX_MB must be 0 or more"),
    ("ARCHIVE_LOG_BACKUPS", "x", "ARCHIVE_LOG_BACKUPS must be a number"),
    ("ARCHIVE_TZ", "Mars/Olympus", "ARCHIVE_TZ is not a known time zone"),
])
def test_bad_values_stop_startup(make_app, setting, value, message):
    with pytest.raises(ValueError, match=message):
        make_app(**{setting: value})


# --- config file -------------------------------------------------------------

def test_config_file_overrides(make_app, tmp_path):
    config_file = tmp_path / "my-config.py"
    config_file.write_text('ARCHIVE_BUCKETS = "foo,bar"\nARCHIVE_ALLOW_REMOVE = True\n')
    config = make_app(ARCHIVE_CONFIG=str(config_file), ARCHIVE_BUCKETS="cert").config
    assert config["ARCHIVE_BUCKETS"] == ["foo", "bar"]
    assert config["ARCHIVE_ALLOW_REMOVE"] is True


def test_config_file_missing_is_an_error_when_set(make_app, tmp_path, monkeypatch):
    missing = str(tmp_path / "missing.py")
    monkeypatch.setenv("ARCHIVE_CONFIG", missing)
    with pytest.raises(FileNotFoundError):
        make_app(ARCHIVE_CONFIG=missing)


def test_example_config_file_loads(make_app):
    """everything in the example is commented out, so the defaults stay"""
    config = make_app(ARCHIVE_CONFIG=str(ROOT / "conf" / "archive-service-config.py.example")).config
    assert config["ARCHIVE_BUCKETS"] == ["cert", "other", "log"]


# --- environment variables -----------------------------------------------------

@pytest.fixture
def env_config(monkeypatch, tmp_path):
    """reload the config module with environment variables set"""
    def _load(**env):
        monkeypatch.setenv("ARCHIVE_CONFIG", str(tmp_path / "no-config.py"))
        monkeypatch.setenv("ARCHIVE_UPLOAD_DIR", str(tmp_path / "archive"))
        monkeypatch.setenv("ARCHIVE_LOG_DIR", str(tmp_path / "logs"))
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        module = importlib.reload(defaultserviceconfig)
        return module.Config
    yield _load
    monkeypatch.undo()
    importlib.reload(defaultserviceconfig)


def test_env_config_defaults(env_config, tmp_path):
    (tmp_path / "no-config.py").write_text("")
    config = create_app(env_config()).config
    assert config["ARCHIVE_BUCKETS"] == ["cert", "other", "log", "config", "admin", "backups"]
    assert config["ARCHIVE_ALLOW_REMOVE"] is False
    assert config["ARCHIVE_PROXY_COUNT"] == 0
    assert config["ARCHIVE_MAX_UPLOAD_MB"] == 1024
    assert config["ARCHIVE_LOG_FILE"] == "archive-service.log"


def test_env_config_values(env_config, tmp_path):
    (tmp_path / "no-config.py").write_text("")
    config = create_app(env_config(ARCHIVE_BUCKETS="a,b", ARCHIVE_ALLOW_REMOVE="true",
                                   ARCHIVE_TZ="UTC", ARCHIVE_LOG_STDERR="yes")).config
    assert config["ARCHIVE_BUCKETS"] == ["a", "b"]
    assert config["ARCHIVE_ALLOW_REMOVE"] is True
    assert config["ARCHIVE_TZ"] == "UTC"
    assert config["ARCHIVE_LOG_STDERR"] is True


def test_env_old_log_file_name(env_config):
    assert env_config(ARCHIVE_LOGFILE="old.log").ARCHIVE_LOG_FILE == "old.log"
    assert env_config(ARCHIVE_LOGFILE="old.log", ARCHIVE_LOG_FILE="new.log").ARCHIVE_LOG_FILE == "new.log"


def test_env_empty_log_file_disables_file(env_config):
    assert env_config(ARCHIVE_LOG_FILE="").ARCHIVE_LOG_FILE == ""


# --- startup output ------------------------------------------------------------

def test_startup_output_hides_secrets(make_app, capsys):
    make_app(ARCHIVE_API_TOKEN="topsecret123", ARCHIVE_DB_PASSWORD="hunter2")
    err = capsys.readouterr().err
    assert "ARCHIVE_API_TOKEN = ***" in err
    assert "ARCHIVE_DB_PASSWORD = ***" in err
    assert "topsecret123" not in err
    assert "hunter2" not in err


def test_startup_output_only_archive_settings(make_app, capsys):
    make_app()
    captured = capsys.readouterr()
    assert captured.out == ""
    keys = [line.split()[2] for line in captured.err.splitlines() if line.startswith("conf key:")]
    assert keys and all(key.startswith("ARCHIVE_") for key in keys)
