# WebLab
Django-based front-end for the modelling Web Lab


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

### Create Postgres database

```bash
createdb weblab;
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

By default, `gulp` will build the static files and keep watching for changes. To just build, use `gulp build`. 

### Run unit tests

```
cd weblab
pytest
```
