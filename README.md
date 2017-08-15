# WebLab
Django-based front-end for the modelling Web Lab

[![Build Status](https://travis-ci.org/ModellingWebLab/WebLab.svg?branch=master)](https://travis-ci.org/ModellingWebLab/WebLab)

## Setup

### Install system requirements

* Python 3.5+
* Postgres 9.4+ (with dev headers)
* NodeJS 8.x / NPM 5.x (to build static files)

### Install requirements into virtualenv

```bash
pip install -r requirements/base.txt
```

or, for local dev setup:

```bash
pip install -r requirements/dev.txt
```

### Create Postgres (user &) database

The --createdb flag should be set for the database user if running tests (so test databases can be set up and torn down). This should not be done on a production system.

```bash
createuser weblab --createdb
createdb -O weblab weblab
```

### Apply migrations

```bash
weblab/manage.py migrate
```

### Run server

```bash
python weblab/manage.py runserver
```

### Build statics

```bash
$ sudo npm install -g gulp-cli
$ cd static
$ npm install
$ gulp
```

By default, `gulp` will just build the required static files.

`gulp watch` will watch the files for changes and rebuild when necessary.


### Run unit tests

```
cd weblab
pytest
```
