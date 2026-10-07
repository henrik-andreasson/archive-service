#!/bin/bash

# run the test suite in a local virtualenv (created in .venv on first run)
#
#   ./run-tests.sh                   all tests
#   ./run-tests.sh -m "not integration"   only the fast tests, no real servers
#   ./run-tests.sh -k delete         tests with "delete" in the name
#
# arguments are passed to pytest, VENV=<dir> uses another virtualenv

set -e
cd "$(dirname "$0")"

VENV="${VENV:-.venv}"

if [ ! -x "${VENV}/bin/python" ] ; then
    echo "creating virtualenv in ${VENV}"
    python3 -m venv "${VENV}"
fi

# only reinstall when the requirements changed
STAMP="${VENV}/.requirements-installed"
if [ ! -f "${STAMP}" ] || [ -n "$(find requirements*.txt -newer "${STAMP}")" ] ; then
    "${VENV}/bin/pip" install -q --upgrade pip
    "${VENV}/bin/pip" install -q -r requirements-dev.txt
    touch "${STAMP}"
fi

exec "${VENV}/bin/python" -m pytest "$@"
