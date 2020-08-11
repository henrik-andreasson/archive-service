
## Running in Docker

build docker:

    docker build -t archive-service .

Run the app

    docker run -it -p8080:8080 archive-service

Developer mode, ie mount the current directory into the docker container and have it self reload when python files are written

    docker run -p8080:8080 -it  --mount type=bind,source="$(pwd)",target=/archive-service archive-service flask run --host=0.0.0.0 --reload

# docs
