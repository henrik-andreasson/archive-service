import functools
import inspect
import tempfile
import uuid
import os
import re
import ipaddress
from flask import request, send_from_directory, current_app
import hashlib
import datetime
from zoneinfo import ZoneInfo
from os import listdir
from os.path import isfile, isdir
from urllib.parse import urlsplit
import json
from app.main import bp
from flask import jsonify
from werkzeug.exceptions import HTTPException
from conf.defaultserviceconfig import to_bool


DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def now():
    """current time in the configured ARCHIVE_TZ"""
    return datetime.datetime.now(ZoneInfo(current_app.config['ARCHIVE_TZ']))


def get_remote_addr():
    """returns the client ip, or None if it is not a valid ip address

    X-Forwarded-For is only used when ARCHIVE_PROXY_COUNT > 0, then ProxyFix
    has already set remote_addr from the trusted proxies
    """
    try:
        return str(ipaddress.ip_address(request.remote_addr))
    except (ValueError, TypeError):
        current_app.logger.error('invalid client address: %s' % request.remote_addr)
        return None


def check_path_args(date=None, filename=None):
    """returns an error message if date or filename is not safe to use in a path"""
    if date is not None and not DATE_RE.match(date):
        return "Date must be formated YYYY-MM-DD"
    if filename is not None:
        try:
            if str(uuid.UUID(filename)) != filename:
                return "Filename must be a uuid"
        except ValueError:
            return "Filename must be a uuid"
    return None


def calc_hash_from_file(file):
    sha256 = hashlib.sha256()
    with open(file, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def metadata_path(abspathfile):
    """the metadata of a stored file is kept next to it in <uuid>.json"""
    return abspathfile + ".json"


def write_metadata(abspathfile, metadata):
    tmp = metadata_path(abspathfile) + ".tmp"
    with open(tmp, 'w') as f:
        json.dump(metadata, f)
    os.replace(tmp, metadata_path(abspathfile))


def read_metadata(abspathfile):
    """the metadata of a stored file, or None for files stored without it"""
    try:
        with open(metadata_path(abspathfile)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def original_filename(file):
    """the file name sent by the client, without any directories"""
    name = (file.filename or "").replace("\\", "/")
    return os.path.basename(name)[:255]


API_RESPONSES_DOC = """## Responses

All responses except a successful `get` (the file) and `list` (a json list)
are json objects:

    {"module": "<endpoint>", "status_code": <code>, "message": "<text>", ...}

Status codes used by all endpoints:

* 200 ok
* 400 bad request: missing or invalid parameter, invalid client address
* 403 forbidden: bucket not allowed, delete not enabled, not allowed to
  call health, or a cross-site request from a browser (a request that
  changes data with an `Origin` header from another site)
* 404 not found: the file does not exist, or unknown url
* 405 method not allowed
* 413 the upload is larger than ARCHIVE_MAX_UPLOAD_MB
* 500 internal server error
* 503 health check failed
"""


def apidoc():
    """print the api docs (markdown) from the endpoint docstrings"""
    print("# Archive service API\n")
    print(API_RESPONSES_DOC)
    for view in (info, store, get, hash_file, list_files, delete, health):
        print(inspect.getdoc(view) + "\n")


def return_response(retdata):
    response = jsonify(retdata)
    if 'status_code' not in retdata:
        current_app.logger.error('status_code missing in call to return_response')
        response.status_code = 500
    else:
        response.status_code = retdata['status_code']

    current_app.logger.info(json.dumps(retdata))
    return response


def respond(module, status_code, message, **extra):
    """json response with module, status_code, message and any extra fields"""
    retdata = {'module': module, 'status_code': status_code, 'message': message}
    retdata.update(extra)
    return return_response(retdata)


class RequestError(Exception):
    """a request that fails validation, carries the response to return"""

    def __init__(self, response):
        super().__init__()
        self.response = response


def check_bucket(module, bucket):
    if bucket not in current_app.config['ARCHIVE_BUCKETS']:
        raise RequestError(respond(module, 403, "Bucket name is not allowed"))


def client_path(module, bucket=None, date=None, filename=None):
    """validates bucket, date, filename and the client address and returns
    the path in the archive: <upload dir>/<client ip>[/bucket[/date[/filename]]]

    raises RequestError with the error response if anything is not valid
    """
    if bucket is not None:
        check_bucket(module, bucket)

    error = check_path_args(date=date, filename=filename)
    if error:
        raise RequestError(respond(module, 400, error))

    remote_addr = get_remote_addr()
    if remote_addr is None:
        raise RequestError(respond(module, 400, "Invalid client address"))

    parts = [p for p in (bucket, date, filename) if p is not None]
    path = os.path.join(current_app.config['ARCHIVE_UPLOAD_DIR'], remote_addr, *parts)
    current_app.logger.debug('%s: remote ip: %s path: %s' % (module, remote_addr, path))
    return path


def handle_request_errors(view):
    """return the response of a RequestError raised by the view"""
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except RequestError as e:
            return e.response
    return wrapper


@bp.app_errorhandler(HTTPException)
def http_error(e):
    """json instead of the html error pages, eg. 404 unknown url, 405 wrong method"""
    if e.code == 413:
        return respond('error', 413, "Upload too large, the limit is %s MB"
                       % current_app.config['ARCHIVE_MAX_UPLOAD_MB'])
    return respond('error', e.code, e.name)


@bp.app_errorhandler(Exception)
def internal_error(e):
    current_app.logger.exception("unhandled error: %s" % e)
    return respond('error', 500, "Internal server error")


SECURITY_HEADERS = {
    'Content-Security-Policy': "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'no-referrer',
}


@bp.before_app_request
def refuse_cross_site_requests():
    """the client is identified by its address or client certificate, which a
    browser sends to any site, so another web site could make the browser
    store or delete files: refuse requests that change data if the browser
    says they come from another site. curl and the client send no Origin."""
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        return None
    origin = request.headers.get('Origin')
    if origin is not None and urlsplit(origin).netloc != request.host:
        current_app.logger.warning('refused cross-site %s from origin %s' % (request.method, origin))
        return respond('error', 403, "Cross-site request not allowed")
    return None


@bp.after_app_request
def add_security_headers(response):
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response


@bp.route('/', methods=['GET', 'POST'])
def root():
    current_app.logger.info('service root accessed, noop')
    return respond('root', 200, "This is the archive service, please use the api docs or the client")


@bp.route('/archive/info/v1', methods=['GET'])
@handle_request_errors
def info():
    """## info `GET /archive/info/v1`

    returns 200 with the settings a client needs: the allowed buckets, if
    delete is enabled, the upload limit in MB (0 = no limit) and the client
    address the server sees, files are stored per client address.
    """
    remote_addr = get_remote_addr()
    if remote_addr is None:
        return respond('info', 400, "Invalid client address")
    return respond('info', 200, "OK",
                   buckets=current_app.config['ARCHIVE_BUCKETS'],
                   allow_remove=current_app.config['ARCHIVE_ALLOW_REMOVE'],
                   max_upload_mb=current_app.config['ARCHIVE_MAX_UPLOAD_MB'],
                   client_address=remote_addr)


@bp.route('/archive/store/v1', methods=['POST'])
@handle_request_errors
def store():
    """## store `POST /archive/store/v1`

    takes two parameters in a multipart POST:

    * bucket - one of the allowed bucket names
    * file - the file to archive, it is stored under a new uuid, the original
      file name is kept in the metadata

    returns 200 with the uuid, bucket, date, sha256 (server_hash), name and
    size of the stored file, the uuid and date are needed to get the file back.
    400 if bucket or file is missing, 403 if the bucket is not allowed,
    413 if the file is larger than ARCHIVE_MAX_UPLOAD_MB.
    """
    bucket = request.form.get('bucket')
    if bucket is None:
        return respond('store', 400, "Bucket is required")
    check_bucket('store', bucket)

    file = request.files.get('file')
    if file is None:
        return respond('store', 400, "File is required")
    file_uuid = str(uuid.uuid4())
    date_path = now().strftime("%Y-%m-%d")
    path = client_path('store', bucket, date_path)

    os.makedirs(path, exist_ok=True)
    abspathfile = os.path.join(path, file_uuid)
    file.save(abspathfile)
    current_app.logger.info('store: file stored at: %s' % abspathfile)

    metadata = {
        'uuid': file_uuid,
        'name': original_filename(file),
        'size': os.path.getsize(abspathfile),
        'sha256': calc_hash_from_file(abspathfile),
        'stored': now().isoformat(timespec='seconds'),
        'bucket': bucket,
        'date': date_path,
    }
    write_metadata(abspathfile, metadata)

    return respond('store', 200, "OK", filename=file_uuid, bucket=bucket, date=date_path,
                   server_hash=metadata['sha256'], uuid=file_uuid,
                   name=metadata['name'], size=metadata['size'])


@bp.route('/archive/get/v1/<bucket>/<date>/<filename>', methods=['GET'])
@handle_request_errors
def get(bucket, date, filename):
    """## get `GET /archive/get/v1/<bucket>/<date>/<uuid>`

    * bucket - where the file was stored
    * date - when the file was stored, YYYY-MM-DD
    * uuid - returned by store

    returns 200 with the file, 404 if there is no such file.
    """
    abspathfile = client_path('get', bucket, date, filename)

    if not isfile(abspathfile):
        return respond('get', 404, "File not found", filename=filename, bucket=bucket, date=date)

    current_app.logger.info("get: serving file: %s" % abspathfile)
    return send_from_directory(os.path.dirname(abspathfile), filename, as_attachment=True)


@bp.route('/archive/hash/v1/<bucket>/<date>/<filename>', methods=['GET'])
@handle_request_errors
def hash_file(bucket, date, filename):
    """## hash `GET /archive/hash/v1/<bucket>/<date>/<uuid>`

    * bucket - where the file was stored
    * date - when the file was stored, YYYY-MM-DD
    * uuid - returned by store

    returns 200 with the sha256 of the file (hash_remote), 404 if there is no
    such file.
    """
    abspathfile = client_path('hash', bucket, date, filename)
    file_info = {'filename': filename, 'bucket': bucket, 'date': date}

    if not isfile(abspathfile):
        return respond('hash', 404, "File not found", **file_info)

    return respond('hash', 200, "OK", hash_remote=calc_hash_from_file(abspathfile), **file_info)


@bp.route('/archive/delete/v1/<bucket>/<date>/<filename>', methods=['DELETE'])
@handle_request_errors
def delete(bucket, date, filename):
    """## delete `DELETE /archive/delete/v1/<bucket>/<date>/<uuid>`

    must be enabled on the server with ARCHIVE_ALLOW_REMOVE=true (default off)

    * bucket - where the file was stored
    * date - when the file was stored, YYYY-MM-DD
    * uuid - returned by store

    returns 200 with the sha256 (hash_remote) of the deleted file, 403 if delete
    is not enabled, 404 if there is no such file.
    """
    file_info = {'filename': filename, 'bucket': bucket, 'date': date}
    check_bucket('delete', bucket)

    if not to_bool(current_app.config['ARCHIVE_ALLOW_REMOVE']):
        return respond('delete', 403, "FAIL: delete not allowed", **file_info)

    abspathfile = client_path('delete', bucket, date, filename)

    if not os.path.exists(abspathfile):
        return respond('delete', 404, "File not found", **file_info)

    file_hash = calc_hash_from_file(abspathfile)
    os.remove(abspathfile)
    if os.path.exists(metadata_path(abspathfile)):
        os.remove(metadata_path(abspathfile))
    current_app.logger.info("delete: deleted file: %s" % abspathfile)
    return respond('delete', 200, "OK, delete done", hash_remote=file_hash, **file_info)


@bp.route('/archive/list/v1/<bucket>/<date>/')
@bp.route('/archive/list/v1/<bucket>/')
@bp.route('/archive/list/v1/')
@handle_request_errors
def list_files(bucket=None, date=None):
    """## list `GET /archive/list/v1/[<bucket>/[<date>/]]`

    * `/archive/list/v1/` - the buckets the client has stored files in
    * `/archive/list/v1/<bucket>/` - the dates in a bucket
    * `/archive/list/v1/<bucket>/<date>/` - the uuids stored on a date
    * `/archive/list/v1/<bucket>/<date>/?details=1` - the files stored on a
      date as objects with uuid, name, size, sha256 and stored (time), name,
      sha256 and stored are null for files stored before metadata was kept

    returns 200 with a json list, an empty list if nothing is stored.
    """
    abs_path = client_path('list', bucket, date)

    if not isdir(abs_path):
        current_app.logger.info('list: nothing stored at %s' % abs_path)
        return jsonify([])

    current_app.logger.info('list: listing files at %s' % abs_path)
    names = sorted(listdir(abs_path))
    if date is None:
        return jsonify(names)

    # a date dir has the files (uuids) and their metadata files
    uuids = [name for name in names if check_path_args(filename=name) is None]
    if not to_bool(request.args.get('details', 'false')):
        return jsonify(uuids)

    files = []
    for file_uuid in uuids:
        abspathfile = os.path.join(abs_path, file_uuid)
        metadata = read_metadata(abspathfile) or {}
        files.append({
            'uuid': file_uuid,
            'name': metadata.get('name'),
            'size': os.path.getsize(abspathfile),
            'sha256': metadata.get('sha256'),
            'stored': metadata.get('stored'),
        })
    return jsonify(files)


@bp.route('/archive/health/v1/<verbose>/', methods=['GET'])
@bp.route('/archive/health/v1/', methods=['GET'])
def health(verbose=None):
    """## health `GET /archive/health/v1/`

    only allowed from the ips in ARCHIVE_IPS_HEALTH, checks that a file can
    be written to the archive.

    returns 200 with message ALLOK if healthy, 403 if the client is not
    allowed, 503 with message ERROR and the reason if the check fails.
    """
    remote_addr = get_remote_addr()
    if remote_addr is None:
        return respond('health', 400, "Invalid client address")
    date = now().strftime("%Y-%m-%d %H:%M:%S")

    if remote_addr not in current_app.config['ARCHIVE_IPS_HEALTH']:
        return respond('health', 403, "ERROR", date=date, reason="not allowed")

    upload_dir = current_app.config['ARCHIVE_UPLOAD_DIR']
    if not os.path.exists(upload_dir):
        return respond('health', 503, "ERROR", date=date, reason="upload dir does not exist")

    # create a new file like store does, removed again when closed
    try:
        with tempfile.NamedTemporaryFile(dir=upload_dir, prefix=".health-") as fh:
            fh.write(("ALLOK: date: " + date).encode())
    except OSError as e:
        current_app.logger.error("health: can not write to %s: %s" % (upload_dir, e))
        return respond('health', 503, "ERROR", date=date, reason="can not write to the archive")

    return respond('health', 200, "ALLOK", date=date, tests="wrote test file to archive")
