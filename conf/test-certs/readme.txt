openssl req -batch -newkey rsa:2048 -nodes -subj '/CN=archive-server.demo/C=SE' -out conf/test-certs/archive-server-demo.req -keyout conf/test-certs/archive-server-demo.key
openssl req -batch -newkey rsa:2048 -nodes -subj '/CN=archive-client.demo/C=SE' -out conf/test-certs/archive-client-demo.req -keyout conf/test-certs/archive-client-demo.key
