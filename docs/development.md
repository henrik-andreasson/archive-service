# Development

## Tests

```
./run-tests.sh                        # all tests, creates .venv on the first run
./run-tests.sh -m "not integration"   # only the fast tests, no real servers
./run-tests.sh -k delete              # tests with "delete" in the name
```

`run-tests.sh` creates a virtualenv in `.venv`, installs
`requirements-dev.txt` (again when a requirements file changes) and passes its
arguments on to pytest. Without the script:

```
pip install -r requirements-dev.txt
python -m pytest
```

The tests are in `tests/`:

* the endpoints, security, config, logging and error tests use Flask's test
  client, they are fast
* `test_client.py` and `test_gunicorn_start.py` (marked `integration`) start
  real gunicorn servers, the TLS tests create certificates with `openssl`
  (skipped if it is missing)
* `test_ui_browser.py` (`integration`) uses the web UI in headless
  Chrome/Chromium, driven by `tests/ui_browser.mjs` (Node 22 or newer), it is
  skipped if they are missing

The tests run on GitHub Actions on every push and pull request
(`.github/workflows/tests.yml`): pytest on Python 3.11 - 3.13, a Docker build
that stores and gets a file with the client, and a build of these docs.

## API docs

[API](api-doc.md) is generated from the docstrings in `app/main/archive.py`.
After changing them run:

```
FLASK_APP=archive-service.py flask doc printdoc > docs/api-doc.md
```

A test fails if `docs/api-doc.md` is out of date.

## Documentation

The docs in `docs/` are built with [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/),
configured in `mkdocs.yml`.

With Docker:

```
docker build -f Dockerfile.docs -t archive-service-docs .

# live preview on http://localhost:8000
docker run --rm -it -p 8000:8000 -v "$PWD":/docs archive-service-docs

# build the static site into site/
docker run --rm --user $(id -u):$(id -g) -v "$PWD":/docs archive-service-docs build --strict
```

Without Docker:

```
pip install -r requirements-docs.txt
mkdocs serve
```
