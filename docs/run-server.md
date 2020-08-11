
The server can be run on http and https, of course https is preferred in prod.
To test the server you need python3 and python3-flask
On centos7 python3 can be installed from scl:

```
yum install centos-release-scl
yum install rh-python35-python.x86_64 sclo-python35-python-flask.noarch sclo-python35-python-werkzeug.noarch
```

Run the server:

```
scl enable rh-python35 bash
./archive-srv.py
```
