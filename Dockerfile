# Use an official Python runtime as a parent image
FROM centos:latest

# Set the working directory to /app
#DEV: WORKDIR /archive-service

COPY . /archive-service

# Install any needed packages
RUN yum install -y python3 sqlite

RUN pip3 install  flask-login  \
  flask-bootstrap flask-httpauth  gunicorn

# Make port available to the world outside this container
EXPOSE 5002

ENV FLASK_APP=archive.py

# Run flask when the container launches
CMD [ "/archive-service/gunicorn-start.sh"]
