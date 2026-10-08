Test certificates, do NOT use in production.

ca.pem                                   Gazonk CA (valid to 2036)
archive-server.test.gazonk.se.{crt,key}  server cert, SAN DNS:archive-server.test.gazonk.se
archive-client.test.gazonk.se.{crt,key}  client cert (TLS Web Client Authentication)
archive-client.test.gazonk.se.p12        client cert, key and CA for importing into a
                                         browser, password: archive-test

The server cert is only valid for archive-server.test.gazonk.se, connect using
that name, eg. add it to /etc/hosts or use curl --resolve:

curl --resolve archive-server.test.gazonk.se:8080:127.0.0.1 \
  --cacert conf/test-certs/ca.pem \
  --cert conf/test-certs/archive-client.test.gazonk.se.crt \
  --key conf/test-certs/archive-client.test.gazonk.se.key \
  https://archive-server.test.gazonk.se:8080/

Python 3.13+ requires the CA cert to have a keyUsage extension, a new CA needs
basicConstraints=critical,CA:TRUE and keyUsage=critical,keyCertSign,cRLSign
