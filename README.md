# WebLab
Django-based front-end for the modelling Web Lab

[![Build Status](https://github.com/ModellingWebLab/Weblab/actions/workflows/pytest.yml/badge.svg)]

## Setup

The easiest way to get a complete working Web Lab setup is to use the developer version of our Ansible deployment.
See https://github.com/ModellingWebLab/deployment for details.

This VM can also be used to run experiments with a local Django server for development.

If you want to install Django locally for development purposes, read on...

### Install system requirements

* Python 3.6+
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

### Create social apps

To run social login, you will need to set up apps on Google and/or GitHub:

* Google OAuth2: http://code.google.com/apis/accounts/docs/OAuth2.html#Registering
* GitHub: https://github.com/settings/applications/new

You can set these up via environment variables:
* `SOCIAL_AUTH_GOOGLE_OAUTH2_KEY`
* `SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET`
* `SOCIAL_AUTH_GITHUB_KEY`
* `SOCIAL_AUTH_GITHUB_SECRET`

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

### Create initial admin user account

```bash
weblab/manage.py createsuperuser
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

### Install latest ontology for metadata editor

The Ansible deployment will install the XML/RDF file from https://github.com/ModellingWebLab/ontologies into the appropriate locations for both front-end and back-end on the VM, which will suffice for running experiments.
(This is what happens on the production systems.)

If you wish to have the latest annotations available in the metadata editor on your local development setup, you can copy `oxford-metadata.rdf` from that repository into `weblab/static/js/visualizers/editMetadata`.


## Run unit tests (needs requirements installed e.g. in virtual environment)

```
cd weblab
pytest
```

If you encounter database access issues, you may need to give the weblab user rights to create databases:
```
sudo -u postgres psql postgres
ALTER USER weblab CREATEDB;
```
When running these tests in a vagant VM (using the vagant file & ansible playbook provided in [deployment](https://github.com/ModellingWebLab/deployment):
Edit pytest.ini and change DJANGO_SETTINGS_MODULE to: 
```
DJANGO_SETTINGS_MODULE=config.settings.vagrant
```
*Make sure not to commit the modified pytest.ini!*
