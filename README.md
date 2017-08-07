# WebLab
Django-based front-end for the modelling Web Lab


## Setup

### Install system requirements

* Python 3.5+
* Postgres 9.4+ (with dev headers)


### Install requirements into virtualenv

```bash
pip install -r requirements/base.txt
```

or, for local dev setup:

```bash
pip install -r requirements/dev.txt
```

### Create Postgres database

```
$ createdb weblab;
```

### Run server

```
python weblab/manage.py runserver
```

### Run unit tests

```
cd weblab
pytest
```
