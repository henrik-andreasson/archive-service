#!/bin/bash

# will try several servers until we find one in the list that works
AR_CLI_BIN="./bin/archive-cli.py"
AR_SRV_URL[0]="http://127.0.0.1:8001"
AR_SRV_URL[1]="http://127.0.0.1:8002"
AR_SRV_URL[2]="http://127.0.0.1:8003"
AR_CLI_CRT="./conf/test-cert/archive-client-demo.crt"
AR_CLI_KEY="./conf/test-cert/archive-client-demo.key"
AR_CLI_CA="./conf/test-cert/archive-demo.ca"


if [ "x$1" == "x" ]; then
    echo "no file supplied as arg1"
    exit
else
    FILENAME="$1"
fi

if [ ! -f "$FILENAME" ] ; then
    echo "arg1 is not a file"
    exit
fi

for (( i = 0 ;  i < ${#AR_SRV_URL[@]} ; i++ )) ; do

    AR_SRV_RESULT=$( "${AR_CLI_BIN}" --clientcert "$AR_CLI_CRT" \
                                    --clientkey "$AR_CLI_KEY"  \
                                    --cacert "$AR_CLI_CA"  \
                                    --store  \
                                    --bucket cert \
                                    --url  "${AR_SRV_URL[$i]}" \
                                    --file "$FILENAME" 2>&1)
    AR_SRV_ERRCODE=$?

    if [ $AR_SRV_ERRCODE == 0 ] ; then
        echo "FILE ARCHIVED OK AT: ${AR_SRV1_URL[$i]} ($AR_SRV_RESULT)"
        exit
    else
        LAST_LINE_OF_ERROR=$(echo "${AR_SRV_RESULT}" | tail -1)
        echo "FILE FAILED TO ARCHIVE AT ${AR_SRV_URL[$i]} ($LAST_LINE_OF_ERROR)"
    fi

done
