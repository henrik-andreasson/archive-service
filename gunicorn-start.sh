#!/bin/bash

# Environment:
#   INSTALL_PATH  directory of the service (default the directory of this script)
#   CERT, KEY  server cert and key (PEM, newlines may be replaced with ';')
#              both are needed to enable TLS
#   CA         CA cert (PEM) used to verify client certificates
#   ARCHIVE_CLIENT_CERT  on|off - require client certificates (default on when
#              TLS is enabled), set to off for e.g. automated tests
#   TLS_DIR    where the cert files are written (default a new private dir in
#              /dev/shm, which is in memory, or /tmp)
#   PORT       port to listen on (default 8080)
#   TIMEOUT    gunicorn worker timeout in seconds (default 300, large uploads
#              on slow connections need time)
#   OPTIONS    extra options passed to gunicorn

if [ "x${INSTALL_PATH}" == "x" ] ; then
  INSTALL_PATH="$(cd "$(dirname "$0")" && pwd)"
fi

cd "${INSTALL_PATH}" || exit 1

# --- check the settings before anything is written ---------------------------

CLIENT_CERT=$(echo "${ARCHIVE_CLIENT_CERT}" | tr '[:upper:]' '[:lower:]')
case "${CLIENT_CERT}" in
  ""|on|off) ;;
  *)
    echo "ERROR: ARCHIVE_CLIENT_CERT must be 'on' or 'off', got '${ARCHIVE_CLIENT_CERT}'" >&2
    exit 1
    ;;
esac

LISTEN="${PORT:-8080}"
WORKER_TIMEOUT="${TIMEOUT:-300}"
for VALUE in "${LISTEN}" "${WORKER_TIMEOUT}" ; do
  if ! [[ "${VALUE}" =~ ^[0-9]+$ ]] ; then
    echo "ERROR: PORT and TIMEOUT must be numbers, got '${VALUE}'" >&2
    exit 1
  fi
done

for DIR in "${ARCHIVE_UPLOAD_DIR}" "${ARCHIVE_LOG_DIR}" ; do
  if [ "x${DIR}" != "x" ] && [ -d "${DIR}" ] && [ ! -w "${DIR}" ] ; then
    echo "ERROR: ${DIR} is not writable by uid $(id -u), fix the owner of the mounted dir on the host," >&2
    echo "       eg: sudo chown -R $(id -u) <host dir>, or rebuild with --build-arg ARCHIVE_UID=<owner uid>" >&2
    exit 1
  fi
done

USE_TLS=0
if [ "x$CERT" != "x" ] && [ "x$KEY" != "x" ] ; then
  USE_TLS=1
  if [ "${CLIENT_CERT}" != "off" ] && [ "x$CA" == "x" ] ; then
    echo "ERROR: client certificates required but CA is not set, set CA or ARCHIVE_CLIENT_CERT=off" >&2
    exit 1
  fi
elif [ "x$CERT" != "x" ] || [ "x$KEY" != "x" ] ; then
  echo "ERROR: both CERT and KEY must be set to enable TLS" >&2
  exit 1
elif [ "${CLIENT_CERT}" == "on" ] ; then
  echo "ERROR: ARCHIVE_CLIENT_CERT=on requires TLS, set CERT and KEY" >&2
  exit 1
fi

# --- TLS ---------------------------------------------------------------------

TLS_OPTIONS=""

if [ ${USE_TLS} == 1 ] ; then
  # write the cert files to a private dir in memory, so the key is not stored
  # on disk or in the container's writable layer
  if [ "x${TLS_DIR}" == "x" ] ; then
    if [ -d /dev/shm ] && [ -w /dev/shm ] ; then
      TLS_DIR=$(mktemp -d /dev/shm/archive-service-tls.XXXXXX) || exit 1
    else
      TLS_DIR=$(mktemp -d) || exit 1
    fi
  fi
  mkdir -p "${TLS_DIR}" && chmod 700 "${TLS_DIR}" || exit 1

  umask 077
  echo "$CERT" | tr ';' '\n' > "${TLS_DIR}/cert.pem"
  echo "$KEY" | tr ';' '\n' > "${TLS_DIR}/key.pem"
  TLS_OPTIONS="--keyfile ${TLS_DIR}/key.pem --certfile ${TLS_DIR}/cert.pem"

  if [ "${CLIENT_CERT}" == "off" ] ; then
    echo "WARNING: TLS enabled but client certificates are NOT required (ARCHIVE_CLIENT_CERT=off)" >&2
  else
    echo "$CA" | tr ';' '\n' > "${TLS_DIR}/ca.pem"
    # cert-reqs 2 = ssl.CERT_REQUIRED
    TLS_OPTIONS="${TLS_OPTIONS} --ca-certs ${TLS_DIR}/ca.pem --cert-reqs 2"
    echo "TLS enabled, client certificates required"
  fi
else
  echo "WARNING: running plain HTTP without TLS or client certificates" >&2
fi

exec gunicorn archive-service:app -b 0.0.0.0:${LISTEN} \
     --pid "${INSTALL_PATH}/archive.pid" \
     --timeout "${WORKER_TIMEOUT}" \
     ${TLS_OPTIONS} ${OPTIONS}
