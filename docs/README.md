Archive Service
================

Inspired by S3, but focus is to have a simple front-end for uploading files
to be able to delete them locally.

Each ip accessing the archive has it's own part of the archive eg:

```
archive/1.2.3.4
```

and

```
archive/3.3.3.3
```

When uploading files the client must choose one `bucket` to store the file in.
Currently the default buckets is:

```
cert, backup, logs, other
```

when a file is uploaded the archive server automatically creates a date subdir
below the ip dir eg:


```
archive/3.3.3.3/other/2019-08-06/
```

When a file is uploaded the server returns a UUID (4) this is the reference to
the file at the archive eg:

```
archive/3.3.3.3/other/2019-08-06/f71f4bd0-22de-474e-8554-81f381e766ed
```

# Docs

[docs](https://github.com/henrik-andreasson/archive-service/tree/master/docs)
