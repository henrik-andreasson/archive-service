#!/bin/bash

NAME="archive-service-server"
VERSION="1"
RELEASE=5
DIRECTORIES="--directories /opt/archive"
URL="https://github.com/henrik-andreasson/archive-service"
VENDOR="Henrik Andreasson"
MAINTAINER="Henrik Andreasson <github@han.pp.se>"
DESCRIPTION="archive service to store files"
EXTRARPMS=""
DEPENDS=""

while getopts r:v: flag; do
  case $flag in
    v)
	VERSION="$OPTARG";
      ;;
    r)
	RELEASE=$OPTARG;
      ;;
    ?)
      exit;
      ;;
  esac
done

rm -rf tmp
mkdir -p tmp/var/www/apps/archive/
mkdir -p tmp/etc
mkdir -p tmp/opt/archive/

cp -r app bin conf docs files logs archive-service.py archive.wsgi gunicorn-start.sh tmp/var/www/apps/archive/

fpm -s dir -t deb -n ${NAME} -v ${VERSION} --iteration "${RELEASE}" ${DEPENDS} \
  --url "${URL}" --vendor "${VENDOR}" --maintainer "${MAINTAINER}" \
  --description "${DESCRIPTION}" ${DIRECTORIES}   --force --epoch 0 -C tmp .

rm -rf tmp
