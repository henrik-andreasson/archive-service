
## client


The client is not strictly needed, but simplify interacting with the server.
The protocol is strictly HTTP.  


**Usage**


```

Usage: archive-cli.py [options]

Options:
  -h, --help            show this help message and exit
  -s, --store           store in archive
  -g, --get             get from archive
  -2, --hash            get hash of file
  -d, --delete_remote   delete at archive
  -x, --delete_local    delete local file if uploaded ok
  -l, --list            list
  -f FILE, --file=FILE  file name
  -i UUID, --uuid=UUID  file uuid to get from archive
  -b BUCKET, --bucket=BUCKET
                        bucket to put file in
  -t DATE, --date=DATE  date to get file from
  -u URL, --url=URL     url
  -c CLIENTCERT, --clientcert=CLIENTCERT
                        PEM formated client cert
  -k CLIENTKEY, --clientkey=CLIENTKEY
                        PEM formated client key
  -a CACERT, --cacert=CACERT
                        PEM formated ca cert of server
  -y, --health          Check server health
  -j, --json            Use JSON
  -p, --pritty          Pritty Print JSON

```


### Store File example

Create a file to upload
```
echo "foo" > dummy.file
```

If cert is required, the client has support for cert/key in files:

```
    python3 ./archive-cli.py \
      --clientcert ar-cli.crt \
      --clientkey ar-cli.key \
      --cacert ar-srv.ca  \
      --store \
      --file dummy.file \
      --bucket other \
      --url https://1.3.4.5
```

Sample run:

```
local  hash: b14a26bccfaafcf815b4832921446594ab9527154a5950db4fb16918ead38958
remote hash: b14a26bccfaafcf815b4832921446594ab9527154a5950db4fb16918ead38958
hashes matches, file securly archived
the local file can be removed
```


### Store File example


Create a file to upload
    echo "foo" > dummy.file

If cert is required, the client has support for cert/key in files:

```
python3 ./archive-cli.py \
      --clientcert ar-cli.crt \
      --clientkey ar-cli.key \
      --cacert ar-srv.ca  \
      --store \
      --file dummy.file \
      --bucket other \
      --url https://1.3.4.5
```


Sample run:

```
local  hash: b14a26bccfaafcf815b4832921446594ab9527154a5950db4fb16918ead38958
remote hash: b14a26bccfaafcf815b4832921446594ab9527154a5950db4fb16918ead38958
hashes matches, file securly archived
the local file can be removed
```

### list buckets


not specifying any bucket nor date, thus getting a list of buckets

```
python3 ./archive-cli.py \
        --clientcert ar-cli.crt  \
        --clientkey ar-cli.key \
        --cacert ar-srv.ca \
        --url http://127.0.0.1:5000 \
        --list
```


### list dates


only specifying a bucket but not a date, thus getting a list of dates

```
python3 ./archive-cli.py \
        --clientcert ar-cli.crt  \
        --clientkey ar-cli.key \
        --cacert ar-srv.ca \
        --url http://127.0.0.1:5000 \
        --list --bucket other
```


### list files


specify bucket and date, thus getting a list of "files/uuid"

```
python3 ./archive-cli.py \
        --clientcert ar-cli.crt  \
        --clientkey ar-cli.key \
        --cacert ar-srv.ca \
        --url http://127.0.0.1:5000 \
         --list  --bucket other --date 2019-08-06
```
