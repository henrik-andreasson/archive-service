import json
import logging
import os
from logging.handlers import RotatingFileHandler


def handler_types(app):
    return sorted(type(h).__name__ for h in app.logger.handlers)


def test_default_logs_to_file(make_app):
    app = make_app()
    assert handler_types(app) == ["RotatingFileHandler"]
    app.test_client().get("/")
    log_file = os.path.join(app.config["ARCHIVE_LOG_DIR"], "archive-service.log")
    messages = [json.loads(line)["message"] for line in open(log_file)]
    assert any('"module": "root"' in m for m in messages)


def test_log_lines_are_json(make_app):
    """response logs contain quotes, every line must still be valid json"""
    app = make_app(ARCHIVE_DEBUG="true")
    client = app.test_client()
    client.get("/")
    client.get("/nope")
    client.get("/archive/list/v1/cert/xx/", environ_base={"REMOTE_ADDR": "10.0.0.5"})
    log_file = os.path.join(app.config["ARCHIVE_LOG_DIR"], "archive-service.log")
    entries = [json.loads(line) for line in open(log_file)]
    assert len(entries) > 3
    assert all(set(e) >= {"time", "name", "loglevel", "message"} for e in entries)
    responses = [json.loads(e["message"]) for e in entries if e["message"].startswith('{"module"')]
    assert {"root", "error", "list"} <= {r["module"] for r in responses}


def test_exception_is_logged_as_json(make_app):
    app = make_app()
    try:
        raise ValueError("boom \"quoted\"")
    except ValueError:
        app.logger.exception("unhandled error")
    log_file = os.path.join(app.config["ARCHIVE_LOG_DIR"], "archive-service.log")
    entry = json.loads(open(log_file).readlines()[-1])
    assert entry["message"] == "unhandled error"
    assert 'ValueError: boom "quoted"' in entry["exception"]


def test_rotation_settings(make_app):
    app = make_app(ARCHIVE_LOG_MAX_MB="3", ARCHIVE_LOG_BACKUPS="4")
    handler = [h for h in app.logger.handlers if isinstance(h, RotatingFileHandler)][0]
    assert handler.maxBytes == 3 * 1024 * 1024
    assert handler.backupCount == 4


def test_log_to_stderr_too(make_app):
    assert handler_types(make_app(ARCHIVE_LOG_STDERR="true")) == ["RotatingFileHandler", "StreamHandler"]


def test_no_log_file(make_app, tmp_path):
    log_dir = tmp_path / "no-logs-here"
    app = make_app(ARCHIVE_LOG_FILE="", ARCHIVE_LOG_DIR=str(log_dir))
    assert handler_types(app) == ["StreamHandler"]
    assert not log_dir.exists()


def test_debug_level(make_app):
    assert make_app(ARCHIVE_DEBUG="true").logger.level == logging.DEBUG
    assert make_app(ARCHIVE_DEBUG="false").logger.level == logging.INFO
