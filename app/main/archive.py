#!/usr/bin/env python3
import uuid
import os
from flask import request, send_from_directory, current_app
from werkzeug.utils import secure_filename
import hashlib
import datetime
from os import listdir
from os.path import isfile, isdir
import json
from app.main import bp
from flask import jsonify


def calc_hash_from_file(file):
    with open(file, 'rb') as f:
        sha256 = hashlib.sha256(f.read())
    return sha256.hexdigest()


def apidoc():
    print(store.__doc__)
    print(get.__doc__)
    print(hash.__doc__)
    print(list.__doc__)
    print(delete.__doc__)
    print(health.__doc__)


def return_response(retdata):
    response = jsonify(retdata)
    if 'status_code' not in retdata:
        current_app.logger.error('status_code missing in call to return_response')
        response.status_code = 500
    else:
        response.status_code = retdata['status_code']

    current_app.logger.info(json.dumps(retdata))
    return response


@bp.route('/', methods=['GET', 'POST'])
def root():
    current_app.logger.info('service root accessed, noop')
    retdata = {}
    retdata['module'] = 'root'
    retdata['status_code'] = 200
    retdata['message'] = "This is the archive service, please use the api docs or the client"
    return return_response(retdata)


@bp.route('/archive/store/v1', methods=['POST'])
def store():
    """## store
    takes two parameters in a POST: bucket and a file

    * bucket is one of the allowed bucket names
    * file is the file to archive, the filename is not used

    returns a list of data first OK or FAIL then:

    filename:%s;bucket:%s;date:%s;sha256:%s;uuid:%s
    """
    current_app.logger.debug("store method called")

    retdata = {}
    retdata['module'] = 'store'
    if request.method != 'POST':
        retdata['status_code'] = 500
        retdata['message'] = "Store only allow POST"
        return return_response(retdata)

    bucket = request.form.get('bucket')
    if bucket is None:
        retdata['status_code'] = 500
        retdata['message'] = "Bucket is required"
        return return_response(retdata)

    if bucket not in current_app.config['ARCHIVE_BUCKETS']:
        retdata['status_code'] = 403
        retdata['message'] = "Bucket name is not allowed"
        return return_response(retdata)

    current_app.logger.debug("store: bucket: %s" % bucket)

    msgid = uuid.uuid4()
    file = request.files['file']
    if file is None:
        retdata['status_code'] = 404
        retdata['message'] = "UUID/Filename not found"
        return return_response(retdata)

    filename = secure_filename(str(msgid))
    current_app.logger.debug('store: file uuid: %s' % filename)

    if request.headers.getlist("X-Forwarded-For"):
        remote_addr = request.headers.getlist("X-Forwarded-For")[0]
    else:
        remote_addr = request.remote_addr
    current_app.logger.debug('store: remote ip: %s ' % remote_addr)

    date_path = datetime.datetime.now().strftime("%Y-%m-%d")
    pathwremote_host = os.path.join(
        current_app.config['ARCHIVE_UPLOAD_DIR'], remote_addr, bucket, date_path)
    current_app.logger.debug('storing file at: %s' % pathwremote_host)

    if not os.path.exists(pathwremote_host):
        os.makedirs(pathwremote_host)
    abspathfile = os.path.join(pathwremote_host, filename)
    file.save(abspathfile)

    current_app.logger.info('store: file stored at: %s' % abspathfile)
    hash = calc_hash_from_file(abspathfile)

    retdata['status_code'] = 200
    retdata['message'] = "OK"
    retdata['filename'] = filename
    retdata['bucket'] = bucket
    retdata['date'] = date_path
    retdata['server_hash'] = hash
    retdata['uuid'] = str(msgid)
    return return_response(retdata)


@bp.route('/archive/get/v1/<bucket>/<date>/<filename>', methods=['GET'])
def get(bucket=None, date=None, filename=None):
    """## get
    takes three parameters in the rest api: bucket, date and a filename
    * bucket where the file was stored (one of the allowed bucket names)
    * date when the file was stored (has to be formated YYYY-MM-DD)
    * filename is the uuid(4) received by the server when storing files
    returns the file or FAIL
    """
    current_app.logger.debug("get method called")

    retdata = {}
    retdata['module'] = 'get'

    if bucket is None:
        retdata['status_code'] = 500
        retdata['message'] = "Bucket is required"
        return return_response(retdata)

    if date is None:
        retdata['status_code'] = 500
        retdata['message'] = "Date is required"
        return return_response(retdata)

    if filename is None:
        retdata['status_code'] = 500
        retdata['message'] = "Filename is required"
        return return_response(retdata)

    if bucket not in current_app.config['ARCHIVE_BUCKETS']:
        retdata['status_code'] = 403
        retdata['message'] = "Bucket name is not allowed"
        return return_response(retdata)

    current_app.logger.info('get: bucket ok: %s' % bucket)

    current_app.logger.debug('get: bucket: %s date: %s file %s' % (bucket, date, filename))
    if request.headers.getlist("X-Forwarded-For"):
        remote_addr = request.headers.getlist("X-Forwarded-For")[0]
    else:
        remote_addr = request.remote_addr
    current_app.logger.debug('get: remote ip: %s ' % remote_addr)

    abspath = os.path.join(current_app.config['ARCHIVE_UPLOAD_DIR'], remote_addr,
                           bucket, date)

    abspathfile = os.path.join(current_app.config['ARCHIVE_UPLOAD_DIR'],
                               remote_addr, bucket, date, filename)

    current_app.logger.debug("get: looking for file on disk: %s" % abspathfile)

    if isfile(abspathfile):
        current_app.logger.info("get: serving file from path: {} and file: {}".format(abspath, filename))
        return send_from_directory(directory=abspath, filename=filename, as_attachment=True)

    else:
        retdata['status_code'] = 500
        retdata['message'] = "FAILED to serve file from disk"
        return return_response(retdata)


@bp.route('/archive/hash/v1/<bucket>/<date>/<filename>', methods=['GET'])
def hash(bucket=None, date=None, filename=None):
    """## hash
    takes three parameters in the rest api:

    * bucket where the file was stored (one of the allowed bucket names)
    * date when the file was stored (has to be formated YYYY-MM-DD)
    * filename is the uuid(4) received by the server when storing files

    returns the hash of the file or FAIL
    """

    current_app.logger.debug("hash method called")

    retdata = {}
    retdata['module'] = 'hash'

    if bucket is None:
        retdata['status_code'] = 500
        retdata['message'] = "Bucket is required"
        return return_response(retdata)

    if date is None:
        retdata['status_code'] = 500
        retdata['message'] = "Date is required"
        return return_response(retdata)

    if filename is None:
        retdata['status_code'] = 500
        retdata['message'] = "Filename is required"
        return return_response(retdata)

    if bucket not in current_app.config['ARCHIVE_BUCKETS']:
        retdata['status_code'] = 403
        retdata['message'] = "Bucket name is not allowed"
        return return_response(retdata)

    current_app.logger.debug('hash: bucket: %s date: %s file %s' % (
                 bucket, date, filename))
    if request.headers.getlist("X-Forwarded-For"):
        remote_addr = request.headers.getlist("X-Forwarded-For")[0]
    else:
        remote_addr = request.remote_addr

    current_app.logger.debug('hash: remote ip: %s ' % remote_addr)

    abspathfile = os.path.join(current_app.config['ARCHIVE_UPLOAD_DIR'], remote_addr,
                               bucket, date, filename)

    current_app.logger.debug("hash: looking for file on disk: %s" % abspathfile)

    if isfile(abspathfile):
        current_app.logger.debug('getting hash of file at: %s' % abspathfile)
        hash = calc_hash_from_file(abspathfile)

        retdata['status_code'] = 200
        retdata['message'] = "OK"
        retdata['filename'] = filename
        retdata['bucket'] = bucket
        retdata['date'] = date
        retdata['hash_remote'] = hash
        return return_response(retdata)

    else:
        retdata['status_code'] = 500
        retdata['message'] = "FAIL, no such file"
        retdata['filename'] = filename
        retdata['bucket'] = bucket
        retdata['date'] = date
        return return_response(retdata)


@bp.route('/archive/delete/v1/<bucket>/<date>/<filename>')
def delete(bucket="other", date=None, filename=None):
    """## delete
    delete must explicitly be allowed (default off) ,
    takes three parameters in the rest api:

    * bucket where the file was stored (one of the allowed bucket names)
    * date when the file was stored (has to be formated YYYY-MM-DD)
    * filename is the uuid(4) received by the server when storing files

    returns DELOK or DELFAIL and a string describing the file
    """
    current_app.logger.debug("delete method called")

    retdata = {}
    retdata['module'] = 'delete'

    if bucket is None:
        retdata['status_code'] = 500
        retdata['message'] = "Bucket is required"
        return return_response(retdata)

    if date is None:
        retdata['status_code'] = 500
        retdata['message'] = "Date is required"
        return return_response(retdata)

    if filename is None:
        retdata['status_code'] = 500
        retdata['message'] = "Filename is required"
        return return_response(retdata)

    if bucket not in current_app.config['ARCHIVE_BUCKETS']:
        retdata['status_code'] = 403
        retdata['message'] = "Bucket name is not allowed"
        return return_response(retdata)

    if current_app.config['ALLOWREMOVE'] == 0:
        retdata['status_code'] = 403
        retdata['message'] = "FAIL: delete not allowed"
        retdata['filename'] = filename
        retdata['bucket'] = bucket
        retdata['date'] = date
        return return_response(retdata)

    current_app.logger.debug('delete: bucket: %s date: %s file %s' % (
        bucket, date, filename))
    if request.headers.getlist("X-Forwarded-For"):
        remote_addr = request.headers.getlist("X-Forwarded-For")[0]
    else:
        remote_addr = request.remote_addr
    current_app.logger.debug('delete: remote ip: %s ' % remote_addr)

    abs_path = os.path.join(current_app.config['ARCHIVE_UPLOAD_DIR'], remote_addr,
                            bucket, date, filename)
    current_app.logger.debug('deleteing file at: %s' % abs_path)

    if not os.path.exists(abs_path):
        retdata['status_code'] = 403
        retdata['filename'] = filename
        retdata['bucket'] = bucket
        retdata['date'] = date
        retdata['message'] = "Filename does not exist"
        return return_response(retdata)

    hash = calc_hash_from_file(abs_path)
    os.remove(abs_path)
    retdata['status_code'] = 200
    retdata['filename'] = filename
    retdata['bucket'] = bucket
    retdata['date'] = date
    retdata['message'] = "OK, delete done"
    retdata['hash_remote'] = hash
    return return_response(retdata)


@bp.route('/archive/list/v1/<bucket>/<date>/')
@bp.route('/archive/list/v1/<bucket>/')
@bp.route('/archive/list/v1/')
def list(bucket=None, date=None):
    """## list

    * if called with /<bucket>/<date>/ the available uuid:s is listed
    * if called with /<bucket>/ the available dates:s is listed
    * if called with / the available buckets:s is listed

    * bucket where the file was stored (one of the allowed bucket names)
    * date when the file was stored (has to be formated YYYY-MM-DD)

    returns json string with findings
    """
    current_app.logger.debug("list method called")

    if request.headers.getlist("X-Forwarded-For"):
        remote_addr = request.headers.getlist("X-Forwarded-For")[0]
    else:
        remote_addr = request.remote_addr
    current_app.logger.debug('list: remote ip: %s ' % remote_addr)

    retdata = {}
    retdata['module'] = 'list'

    if bucket and date:
        abs_path = os.path.join(current_app.config['ARCHIVE_UPLOAD_DIR'], remote_addr,
                                bucket, date)
        retdata['date'] = date

    elif bucket:
        abs_path = os.path.join(current_app.config['ARCHIVE_UPLOAD_DIR'], remote_addr,
                                bucket)
        retdata['bucket'] = bucket

    else:
        abs_path = os.path.join(current_app.config['ARCHIVE_UPLOAD_DIR'], remote_addr)

    if isdir(abs_path) is False:
        retdata['status_code'] = 500
        retdata['message'] = "No files found"
        retdata['bucket'] = bucket
        retdata['date'] = date
        retdata['reason'] = "not allowed"
        return return_response(retdata)

    else:
        onlyfiles = listdir(abs_path)
        response = jsonify(onlyfiles)
        retdata['message'] = "listing files at {}".format(abs_path)
        retdata['status_code'] = 200
        current_app.logger.info(json.dumps(retdata))
        response.status_code = retdata['status_code']
        return response


@bp.route('/archive/health/v1/<verbose>/', methods=['GET'])
@bp.route('/archive/health/v1/', methods=['GET'])
def health(verbose=None):
    """## health

        takes one optional parameter in the rest api

        * verbose - returns more information about health status

        returns 200 ALLOK: date: <date> if all health checks is ok
        returns 403 ERROR date: <date> notallowed if ip not in
             ARCHIVE_IPS_HEALTH
        returns 500 ERROR date: <date>: <description of error> if some error
        is found
    """
    current_app.logger.debug("health method called")

    retdata = {}
    retdata['module'] = 'health'

    if request.headers.getlist("X-Forwarded-For"):
        remote_addr = request.headers.getlist("X-Forwarded-For")[0]
    else:
        remote_addr = request.remote_addr
    current_app.logger.debug('health: remote ip: %s ' % remote_addr)
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if remote_addr in current_app.config['ARCHIVE_IPS_HEALTH']:
        current_app.logger.debug('health: ip allowed to probe health: %s' % remote_addr)
    else:
        retdata['status_code'] = 403
        retdata['message'] = "ERROR"
        retdata['date'] = date
        retdata['reason'] = "not allowed"
        return return_response(retdata)

    filename = "health.check"
    abspathfile = os.path.join(current_app.config['ARCHIVE_UPLOAD_DIR'], filename)

    current_app.logger.debug("health: writing testfile on disk at: %s" % abspathfile)

    if not os.path.exists(current_app.config['ARCHIVE_UPLOAD_DIR']):
        retdata['status_code'] = 500
        retdata['message'] = "ERROR"
        retdata['date'] = date
        retdata['reason'] = "upload dir does not exist"
        return return_response(retdata)

    with open(abspathfile, 'w') as fh:
        try:
            msg = "ALLOK: date: " + date
            fh.write(msg)
            fh.close()
            retdata['status_code'] = 200
            retdata['message'] = "ALLOK"
            retdata['date'] = date
            retdata['tests'] = "wrote test file to archive"
            return return_response(retdata)

        except IOError:
            retdata['status_code'] = 500
            retdata['message'] = "ERROR"
            retdata['date'] = date
            retdata['tests'] = "Failed to write test file to archive"
            return return_response(retdata)
