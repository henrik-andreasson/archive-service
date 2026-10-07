#!/usr/bin/env python3
"""Client for the archive service.

Connection settings can be given as options or environment variables:

  ARCHIVE_URL     url of the archive service, eg. https://archive.example.com:8080
                  several urls can be given, comma or space separated
  ARCHIVE_MODE    first (default): use the first server that works, for
                  clustered servers; all: store on every server, for
                  standalone servers
  ARCHIVE_CERT    client cert (PEM), only needed if the server requires it
  ARCHIVE_KEY     client key (PEM)
  ARCHIVE_CA      CA cert (PEM) used to verify the server, default: system CAs
  ARCHIVE_BUCKET  default bucket (default: other)
  ARCHIVE_TIMEOUT request timeout in seconds (default: 30)

Exit codes: 0 ok, 1 server or hash error (on all servers), 2 usage error.
"""

import argparse
import datetime
import hashlib
import json
import os
import sys
import syslog

import requests

ARCHIVE_SERVER_PATH_STORE = "archive/store/v1"
ARCHIVE_SERVER_PATH_GET = "archive/get/v1"
ARCHIVE_SERVER_PATH_HASH = "archive/hash/v1"
ARCHIVE_SERVER_PATH_DELETE = "archive/delete/v1"
ARCHIVE_SERVER_PATH_LIST = "archive/list/v1"
ARCHIVE_SERVER_PATH_HEALTH = "archive/health/v1"

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2

CHUNK_SIZE = 1024 * 1024

VERBOSE = False


class ArchiveError(Exception):
    """error talking to the archive, exit code 1"""


def debug(msg):
    if VERBOSE:
        print("debug: %s" % msg, file=sys.stderr)


def calc_hash_from_file(filename):
    sha256 = hashlib.sha256()
    with open(filename, 'rb') as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


class ArchiveClient:

    def __init__(self, url, cert=None, key=None, ca=None, timeout=30):
        self.url = url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        if cert:
            self.session.cert = (cert, key) if key else cert
        # no CA given: verify against the system CAs
        self.session.verify = ca if ca else True

    def request(self, method, path, **kwargs):
        url = "%s/%s" % (self.url, path)
        debug("%s %s" % (method, url))
        try:
            r = self.session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.exceptions.SSLError as e:
            raise ArchiveError("TLS error talking to %s: %s" % (self.url, e))
        except requests.exceptions.RequestException as e:
            raise ArchiveError("can not connect to %s: %s" % (self.url, e))
        debug("status %s" % r.status_code)
        return r

    def request_json(self, method, path, **kwargs):
        """returns the json response, raises ArchiveError if not 200"""
        r = self.request(method, path, **kwargs)
        try:
            data = r.json()
        except ValueError:
            data = None
        if r.status_code != 200:
            if isinstance(data, dict) and 'message' in data:
                message = data['message']
            else:
                message = r.text.strip()[:200]
            raise ArchiveError("server returned %s: %s" % (r.status_code, message))
        return data

    def store(self, bucket, filename):
        with open(filename, 'rb') as f:
            return self.request_json('POST', ARCHIVE_SERVER_PATH_STORE,
                                     files={'file': f}, data={'bucket': bucket})

    def hash(self, bucket, date, uuid):
        return self.request_json('GET', "%s/%s/%s/%s" % (ARCHIVE_SERVER_PATH_HASH, bucket, date, uuid))

    def download(self, bucket, date, uuid, filename):
        r = self.request('GET', "%s/%s/%s/%s" % (ARCHIVE_SERVER_PATH_GET, bucket, date, uuid), stream=True)
        if r.status_code != 200:
            try:
                message = r.json().get('message', r.text)
            except ValueError:
                message = r.text.strip()[:200]
            raise ArchiveError("server returned %s: %s" % (r.status_code, message))
        with open(filename, 'wb') as f:
            for chunk in r.iter_content(CHUNK_SIZE):
                f.write(chunk)

    def list(self, bucket=None, date=None):
        path = ARCHIVE_SERVER_PATH_LIST
        if bucket:
            path += "/%s" % bucket
            if date:
                path += "/%s" % date
        return self.request_json('GET', path + "/")

    def delete(self, bucket, date, uuid):
        return self.request_json('DELETE', "%s/%s/%s/%s" % (ARCHIVE_SERVER_PATH_DELETE, bucket, date, uuid))

    def health(self):
        return self.request_json('GET', ARCHIVE_SERVER_PATH_HEALTH + "/")


def print_result(args, data, text):
    """print data as json if asked for, otherwise the text lines"""
    if args.json or args.pretty:
        print(json.dumps(data, indent=2 if args.pretty else None))
    else:
        for line in text:
            print(line)


# the cmd_* functions run one command against one server and return
# (data, text): the json data and the lines to print, errors are raised as
# ArchiveError


def cmd_store(client, args):
    hash_local = calc_hash_from_file(args.file)
    debug("local hash: %s" % hash_local)
    data = client.store(args.bucket, args.file)
    hash_remote = data.get('server_hash')
    debug("remote hash: %s" % hash_remote)

    if hash_local != hash_remote:
        raise ArchiveError("hashes DO NOT match, file NOT archived (local %s, remote %s)"
                           % (hash_local, hash_remote))

    data['local_hash'] = hash_local
    msg = "file archived OK;file:%s;uuid:%s;bucket:%s;date:%s;hash:%s" % (
        args.file, data['uuid'], data['bucket'], data['date'], hash_remote)
    if args.syslog:
        syslog.syslog("%s;server:%s" % (msg, client.url))
    return data, [msg]


def cmd_get(client, args):
    hash_remote = client.hash(args.bucket, args.date, args.uuid)['hash_remote']
    debug("remote hash: %s" % hash_remote)

    # download to a temp file and only keep it if the hash matches
    partial = args.output + ".part"
    try:
        client.download(args.bucket, args.date, args.uuid, partial)
        hash_local = calc_hash_from_file(partial)
        debug("local hash: %s" % hash_local)
        if hash_local != hash_remote:
            raise ArchiveError("hashes DO NOT match, download failed (local %s, remote %s)"
                               % (hash_local, hash_remote))
        os.replace(partial, args.output)
    finally:
        if os.path.exists(partial):
            os.remove(partial)

    data = {'uuid': args.uuid, 'bucket': args.bucket, 'date': args.date,
            'file': args.output, 'hash': hash_local}
    return data, ["file downloaded OK;file:%s;uuid:%s;bucket:%s;date:%s;hash:%s" % (
        args.output, args.uuid, args.bucket, args.date, hash_local)]


def cmd_hash(client, args):
    data = client.hash(args.bucket, args.date, args.uuid)
    return data, [data['hash_remote']]


def cmd_list(client, args):
    data = client.list(args.bucket, args.date)
    return data, sorted(data)


def cmd_delete(client, args):
    data = client.delete(args.bucket, args.date, args.uuid)
    return data, ["deleted;uuid:%s;bucket:%s;date:%s;hash:%s" % (
        args.uuid, args.bucket, args.date, data.get('hash_remote'))]


def cmd_health(client, args):
    data = client.health()
    return data, ["%s %s" % (data.get('message'), data.get('date'))]


def env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def build_parser():
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    common = argparse.ArgumentParser(add_help=False)
    conn = common.add_argument_group("connection (default from environment)")
    conn.add_argument("-u", "--url", action="append",
                      help="archive service url, repeat to try several servers in order [ARCHIVE_URL]")
    conn.add_argument("-c", "--cert", default=os.environ.get("ARCHIVE_CERT"),
                      help="client cert, PEM [ARCHIVE_CERT]")
    conn.add_argument("-k", "--key", default=os.environ.get("ARCHIVE_KEY"),
                      help="client key, PEM [ARCHIVE_KEY]")
    conn.add_argument("-a", "--ca", default=os.environ.get("ARCHIVE_CA"),
                      help="CA cert of the server, PEM [ARCHIVE_CA], default system CAs")
    conn.add_argument("-m", "--mode", default=os.environ.get("ARCHIVE_MODE", "first"),
                      help="with several urls: 'first' uses the first server that works "
                           "(clustered servers), 'all' stores on every server "
                           "(standalone servers) [ARCHIVE_MODE] (default: %(default)s)")
    conn.add_argument("--timeout", type=int, default=env_int("ARCHIVE_TIMEOUT", 30),
                      help="request timeout in seconds [ARCHIVE_TIMEOUT] (default: %(default)s)")
    out = common.add_argument_group("output")
    out.add_argument("-j", "--json", action="store_true", help="print the server response as json")
    out.add_argument("-p", "--pretty", action="store_true", help="pretty print json")
    out.add_argument("-v", "--verbose", action="store_true", help="debug output on stderr")

    bucket = argparse.ArgumentParser(add_help=False)
    bucket.add_argument("-b", "--bucket", default=os.environ.get("ARCHIVE_BUCKET", "other"),
                        help="bucket [ARCHIVE_BUCKET] (default: %(default)s)")

    stored = argparse.ArgumentParser(add_help=False, parents=[bucket])
    stored.add_argument("uuid", help="uuid returned when the file was stored")
    stored.add_argument("-t", "--date", default=today,
                        help="date the file was stored, YYYY-MM-DD (default: today)")

    parser = argparse.ArgumentParser(
        description="Client for the archive service.",
        epilog="Exit codes: 0 ok, 1 server or hash error (on all servers), 2 usage error.")
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")

    p = sub.add_parser("store", parents=[common, bucket], help="store a file in the archive")
    p.add_argument("file", help="file to archive")
    p.add_argument("-x", "--delete-local", action="store_true",
                   help="delete the local file when it is archived and the hashes match")
    p.add_argument("--syslog", action="store_true", help="also log the result to syslog")
    p.set_defaults(func=cmd_store)

    p = sub.add_parser("get", parents=[common, stored], help="download a file from the archive")
    p.add_argument("-o", "--output", help="file to write (default: the uuid)")
    p.add_argument("-f", "--force", action="store_true", help="overwrite the output file")
    p.set_defaults(func=cmd_get)

    p = sub.add_parser("hash", parents=[common, stored], help="sha256 of a file in the archive")
    p.set_defaults(func=cmd_hash)

    p = sub.add_parser("list", parents=[common], help="list buckets, dates in a bucket or files on a date")
    p.add_argument("-b", "--bucket", help="list dates in this bucket")
    p.add_argument("-t", "--date", help="list files on this date, YYYY-MM-DD (needs --bucket)")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("delete", parents=[common, stored], help="delete a file in the archive")
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("health", parents=[common], help="check the server health")
    p.set_defaults(func=cmd_health)

    return parser


def get_urls(args):
    """urls from --url (may be repeated) or ARCHIVE_URL (comma or space separated)"""
    urls = args.url or [os.environ.get("ARCHIVE_URL", "")]
    return [u for value in urls for u in value.replace(',', ' ').split()]


def finish(args, data, text):
    """delete the local file after store --delete-local and print the result"""
    rc = EXIT_OK
    if args.command == "store" and args.delete_local:
        try:
            os.remove(args.file)
            data['local_status'] = "deleted"
            text.append("local file deleted: %s" % args.file)
        except OSError as e:
            print("ERROR: file archived but can not delete the local file: %s" % e, file=sys.stderr)
            data['local_status'] = "delete failed"
            rc = EXIT_FAIL
    print_result(args, data, text)
    return rc


def run_first(urls, args):
    """clustered servers: try the servers in order, stop at the first one that works"""
    for url in urls:
        client = ArchiveClient(url, args.cert, args.key, args.ca, args.timeout)
        try:
            data, text = args.func(client, args)
        except ArchiveError as e:
            if len(urls) > 1:
                print("ERROR: %s: %s" % (url, e), file=sys.stderr)
            else:
                print("ERROR: %s" % e, file=sys.stderr)
            continue
        if len(urls) > 1:
            print("server: %s" % url, file=sys.stderr)
        return finish(args, data, text)

    if len(urls) > 1:
        print("ERROR: failed on all servers: %s" % " ".join(urls), file=sys.stderr)
    return EXIT_FAIL


def run_all(urls, args):
    """standalone servers: run the command on every server, ok only if all
    servers succeed, store --delete-local only deletes when all have the file"""
    results = []
    text = []
    failed = []
    for url in urls:
        client = ArchiveClient(url, args.cert, args.key, args.ca, args.timeout)
        try:
            server_data, server_text = args.func(client, args)
        except ArchiveError as e:
            print("ERROR: %s: %s" % (url, e), file=sys.stderr)
            failed.append(url)
            results.append({'server': url, 'status': 'failed', 'error': str(e)})
            continue
        results.append({'server': url, 'status': 'ok', 'response': server_data})
        if args.command == "store":
            # each server has its own uuid for the file
            text += ["%s;server:%s" % (line, url) for line in server_text]
        else:
            text += ["%s: %s" % (url, line) for line in server_text]

    data = {'mode': 'all', 'results': results}
    if failed:
        if args.command == "store" and args.delete_local:
            print("local file NOT deleted, it is not stored on all servers", file=sys.stderr)
            data['local_status'] = "kept"
        print_result(args, data, text)
        print("ERROR: failed on %d of %d servers: %s" % (len(failed), len(urls), " ".join(failed)),
              file=sys.stderr)
        return EXIT_FAIL
    return finish(args, data, text)


# commands that run on every server in --mode all, the others work on a uuid
# that only exists on one server so they always use the first server that has it
ALL_MODE_COMMANDS = ("store", "list", "health")


def main(argv=None):
    global VERBOSE
    parser = build_parser()
    args = parser.parse_args(argv)
    args.parser = parser
    VERBOSE = args.verbose

    urls = get_urls(args)
    if not urls:
        parser.error("no url, use --url or set ARCHIVE_URL")
    if args.mode not in ("first", "all"):
        parser.error("--mode must be 'first' or 'all', got '%s'" % args.mode)
    if args.key and not args.cert:
        parser.error("--key given without --cert")
    if args.command == "list" and args.date and not args.bucket:
        parser.error("--date needs --bucket")
    if args.command == "store" and not os.path.isfile(args.file):
        parser.error("not a file: %s" % args.file)
    if args.command == "get":
        args.output = args.output or args.uuid
        if os.path.exists(args.output) and not args.force:
            parser.error("%s already exists, use --force to overwrite" % args.output)

    if args.mode == "all" and args.command in ALL_MODE_COMMANDS:
        return run_all(urls, args)
    return run_first(urls, args)


if __name__ == '__main__':
    sys.exit(main())
