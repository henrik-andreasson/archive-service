#!/bin/bash

NAME="archive-service-cli"
VERSION="1.3"
RELEASE=1
DIRECTORIES="--directories /opt/archive/cli"
URL="http://certificateservices.se/project/archive-service"
VENDOR="Henrik Andreasson"
MAINTAINER="Henrik Andreasson <han@certificateservices.se>"
DESCRIPTION="cli tool to the archive service"
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
mkdir -p                tmp/opt/archive/cli
cp bin/archive-cli.py   tmp/opt/archive/cli
cp bin/archive-cli.sh   tmp/opt/archive/cli
cp -r docs              tmp/opt/archive/cli


fpm -s dir -t rpm -n ${NAME} -v ${VERSION} --iteration "${RELEASE}" ${DEPENDS} \
  --url "${URL}" --vendor "${VENDOR}" --maintainer "${MAINTAINER}" \
  --description "${DESCRIPTION}" ${DIRECTORIES}   --force --epoch 0 -C tmp .

rm -rf tmp
