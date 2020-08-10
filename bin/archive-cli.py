#!/usr/bin/python3

import requests
import optparse
import datetime
import hashlib
import json
import os
import syslog

ARCHIVE_SERVER_PATH_STORE = "archive/store/v1"
ARCHIVE_SERVER_PATH_GET = "archive/get/v1"
ARCHIVE_SERVER_PATH_HASH = "archive/hash/v1"
ARCHIVE_SERVER_PATH_DELETE = "archive/delete/v1"
ARCHIVE_SERVER_PATH_LIST = "archive/list/v1"
ARCHIVE_SERVER_PATH_HEALTH = "archive/health/v1"
DEBUG = 1
SEND_LOG = 0
PRINTJSON = 0
PRITTYJSON = 0


def store_file(url, bucket, filename):

    hash_local = calc_hash_from_file(filename)

    filein = open(filename, 'rb')
    files = {'file': filein}
    data = {'bucket': bucket}
    abs_url = "%s/%s" % (url, ARCHIVE_SERVER_PATH_STORE)
    r = requests.post(abs_url, cert=(opts.clientcert, opts.clientkey),
                      verify=opts.cacert, files=files, data=data)
    filein.close()

    if r.status_code == 200:
        data = r.json() or {}
        uuid = data['uuid']
        bucket = data['bucket']
        date = data['date']
        hash = data['server_hash']

        if PRINTJSON:
            print(json.dumps(data, indent=PRITTYJSON))
            return
        if DEBUG:
            print("status: uuid: %s bucket: %s date: %s hash: %s" % (
                                                                     uuid,
                                                                     bucket,
                                                                     date,
                                                                     hash))
            print("local  hash: %s" % hash_local)
            print("remote hash: %s" % hash)
        if hash_local == hash:
            if DEBUG:
                print("hashes matches, file securly archived")
            if DEBUG:
                print("the local file can be removed")

            msg1 = "file archived OK;"
            msg2 = "file:%s;uuid:%s;bucket:%s;date:%s;hash:%s" % (filename,
                                                                  uuid,
                                                                  bucket,
                                                                  date,
                                                                  hash)
            print(msg1, msg2)
            if SEND_LOG:
                syslog.syslog(msg1 + msg2)
        else:
            print("hashes DO NOT match, file NOT archived")
    else:
        print("%s;%s" % (r.status_code, r.text))


def store_delete_local_file(url, bucket, filename):

    hash_local = calc_hash_from_file(filename)
    filein = open(filename, 'rb')
    files = {'file': filein}
    data = {'bucket': bucket}
    abs_url = "%s/%s" % (url, ARCHIVE_SERVER_PATH_STORE)
    r = requests.post(abs_url, cert=(opts.clientcert, opts.clientkey),
                      verify=opts.cacert, files=files, data=data)
    if r.status_code == 200:
        retdata = r.json() or {}
        uuid = retdata['uuid']
        bucket = retdata['bucket']
        date = retdata['date']
        hash_remote = retdata['server_hash']
        if DEBUG:
            print("local  hash: %s" % hash_local)
        if DEBUG:
            print("remote hash: %s" % hash_remote)
        if hash_local == hash_remote:

            try:
                os.remove(filename)
                if PRINTJSON:
                    retdata['local_status'] = "OK, hashes matches"
                    retdata['local_hash'] = hash_local

                    print(json.dumps(retdata, indent=PRITTYJSON))
                    return

                print("Local/remote hashes matches: file is archived and ",
                      "locally deleted")
                msg1 = "file archived OK;"
                msg2 = "file:%s;uuid:%s;bucket:%s;date:%s;hash:%s" % (filename,
                                                                      uuid,
                                                                      bucket,
                                                                      date,
                                                                      hash_remote)

                print(msg1, msg2)

            except Exception as e:
                print("Can not delete the file", filename, e)

        else:
            if PRINTJSON:
                retdata['local_status'] = "FAIL, hashes DO NOT match"
                retdata['local_hash'] = hash_local
                print(json.dumps(retdata, indent=PRITTYJSON))
                return

            print("hashes DO NOT match, file NOT archived NOR deleted")
    else:
        print("%s;%s" % (r.status_code, r.text))

    filein.close()


def get_file(url, bucket, date, uuid, filename):

    hash_url = "%s/%s/%s/%s/%s" % (url, ARCHIVE_SERVER_PATH_HASH, bucket,
                                   date, uuid)
    r = requests.get(hash_url, cert=(opts.clientcert, opts.clientkey),
                     verify=opts.cacert)
    if r.status_code == 200:
        retdata = r.json() or {}
        uuid = retdata['uuid']
        bucket = retdata['bucket']
        date = retdata['date']
        hash_remote = retdata['server_hash']
        if DEBUG:
            print("remote hash: ", hash_remote)

    else:
        if PRINTJSON:
            print(json.dumps(r.json(), indent=PRITTYJSON))
            return
        print(r.status_code, r.text)

    get_url = "%s/%s/%s/%s/%s" % (url, ARCHIVE_SERVER_PATH_GET, bucket,
                                  date, uuid)
    r = requests.get(get_url, cert=(opts.clientcert, opts.clientkey),
                     verify=opts.cacert)
    if r.status_code == 200:
        with open(filename, mode='wb') as localfile:
            localfile.write(r.content)

        hash_local = calc_hash_from_file(filename)
        if hash_local == hash_remote:
            if DEBUG:
                print("local hash:  ", hash_local)
            print("Local/remote hashes matches: file is downloaded ok")
        else:
            print("problem downloadning file")

    else:
        print(r.status_code, r.text)


def get_hash(url, bucket, date, uuid, filename):

    abs_url = "%s/%s/%s/%s/%s" % (url, ARCHIVE_SERVER_PATH_HASH, bucket,
                                  date, uuid)
    r = requests.get(abs_url, cert=(opts.clientcert, opts.clientkey),
                     verify=opts.cacert)
    if r.status_code == 200:
        ret = json.loads(r.text)
        if PRINTJSON:
            print(json.dumps(ret, indent=PRITTYJSON))
            return

        for element in ret:
            print("{}: {}".format(element, ret[element]))
    else:
        print(r.status_code, r.text)


def get_health(url):

    abs_url = "%s/%s" % (url, ARCHIVE_SERVER_PATH_HEALTH)
    r = requests.get(abs_url, cert=(opts.clientcert, opts.clientkey),
                     verify=opts.cacert)
    if PRINTJSON:
        print(json.dumps(r.json(), indent=PRITTYJSON))
        return

    ret = json.loads(r.text)
    for element in ret:
        print("{}: {}".format(element, ret[element]))


def list(url, bucket=None, date=None):

    if bucket and date:
        abs_url = "%s/%s/%s/%s" % (url, ARCHIVE_SERVER_PATH_LIST, bucket,
                                   date)
    elif bucket:
        abs_url = "%s/%s/%s" % (url, ARCHIVE_SERVER_PATH_LIST, bucket)
    else:
        abs_url = "%s/%s" % (url, ARCHIVE_SERVER_PATH_LIST)

    r = requests.get(abs_url, cert=(opts.clientcert, opts.clientkey),
                     verify=opts.cacert)
    if r.status_code == 200:
        x = json.loads(r.text)
        if PRINTJSON:
            print(json.dumps(x, indent=PRITTYJSON))
            return
        for i in x:
            print(i)
    else:
        if PRINTJSON:
            print(json.dumps(r.json, indent=PRITTYJSON))
            return

        print(r.status_code, r.text)


def calc_hash_from_file(file):
    with open(file, 'rb') as f:
        sha256 = hashlib.sha256(f.read())
    return sha256.hexdigest()


def delete_file(url, bucket, date, uuid):

    abs_url = "%s/%s/%s/%s/%s" % (url, ARCHIVE_SERVER_PATH_DELETE, bucket,
                                  date, uuid)
    r = requests.get(abs_url, cert=(opts.clientcert, opts.clientkey),
                     verify=opts.cacert)
    if r.status_code == 200:
        x = json.loads(r.text)
        if PRINTJSON:
            print(x)
            return

        print("deleted remote uuid", uuid)
        print(r.status_code, r.text)
    else:
        print("FAILED to delete remote uuid", uuid)
        print(r.status_code, r.text)


parser = optparse.OptionParser(usage="usage: %prog [options]")
parser.add_option("-s", "--store", action='store_true',
                  help="store in archive")
parser.add_option("-g", "--get", action='store_true', help="get from archive")
parser.add_option("-2", "--hash", action='store_true', help="get hash of file")
parser.add_option("-d", "--delete_remote", action='store_true',
                  help="delete at archive")
parser.add_option("-x", "--delete_local", action='store_true',
                  help="delete local file if uploaded ok")
parser.add_option("-l", "--list", action='store_true', help="list")
parser.add_option("-f", "--file", help="file name")
parser.add_option("-i", "--uuid", help="file uuid to get from archive")
parser.add_option("-b", "--bucket", help="bucket to put file in")
parser.add_option("-t", "--date", help="date to get file from")
parser.add_option("-u", "--url", help="url")
parser.add_option("-c", "--clientcert", help="PEM formated client cert")
parser.add_option("-k", "--clientkey", help="PEM formated client key")
parser.add_option("-a", "--cacert", help="PEM formated ca cert of server")
parser.add_option("-y", "--health", action='store_true',
                  help="Check server health")
parser.add_option("-j", "--json", action='store_true', help="Use JSON")
parser.add_option("-p", "--pritty", action='store_true', help="Pritty Print JSON")

opts, args = parser.parse_args()

if not opts.url:
    parser.error('--url must be supplied')

if not opts.clientcert:
    parser.error('--clientcert must be supplied')

if not opts.cacert:
    parser.error('--cacert must be supplied')

if not opts.clientkey:
    parser.error('--clientkey must be supplied')

if opts.json:
    PRINTJSON = 1

if opts.pritty:
    PRINTJSON = 1
    PRITTYJSON = 2

if not opts.bucket:   # if url is not given
    bucket = "default"
else:
    bucket = opts.bucket

if not opts.date:
    date = datetime.datetime.now().strftime("%Y-%m-%d")
else:
    date = opts.date

if opts.store and opts.delete_local:
    store_delete_local_file(opts.url, bucket, opts.file)

elif opts.store:
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    if not opts.file:   # if filename is not given
        parser.error('Filename not given')
    store_file(opts.url, bucket, opts.file)

elif opts.get:
    if not opts.uuid:   # if url is not given
        parser.error('UUID not given')

    if not opts.file:   # if filename is not given
        parser.error('Filename not given')

    get_file(opts.url, bucket, date, opts.uuid, opts.file)

elif opts.hash:
    if not opts.uuid:   # if url is not given
        parser.error('UUID not given')

    get_hash(opts.url, bucket, date, opts.uuid, opts.file)

if opts.delete_remote:
    if not opts.uuid:   # if url is not given
        parser.error('UUID not given')

    delete_file(opts.url, bucket, date, opts.uuid)

if opts.health:
    get_health(opts.url)

if opts.list:
    if not opts.date:
        date = datetime.datetime.now().strftime("%Y-%m-%d")
    else:
        date = opts.date

    if opts.date:
        list(opts.url, bucket, date)
    elif opts.bucket:
        list(opts.url, bucket)
    else:
        list(opts.url)
