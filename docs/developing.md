# Hints for Web Lab developers

This document gives some orientation on where to look for particular development tasks.

## Code layout

This repository is structured as follows:
- [docs](.): this folder
- [requirements](../requirements): Python packages need to run the site
- [weblab](../weblab): the actual code
    - [accounts](../weblab/accounts): app handling user registration etc
    - [config](../weblab/config): settings and main [url routing](../weblab/config/urls.py)
    - [core](../weblab/core): common code used by multiple apps
    - [entities](../weblab/entities): app handling models and protocols
    - [experiments](../weblab/experiments): app handling experiment submission & viewing
    - [static](../weblab/static): Javascript and CSS files
    - [templates](../weblab/templates): web page templates
    - [conftest.py](../weblab/conftest.py): [fixtures](https://docs.pytest.org/en/latest/fixture.html) for use in tests

Each app will contain some of the following files and folders:
- `migrations`: handles updating the database to the latest structure
- `templatetags`: defines new 'tags' that can be used in web page templates
- `tests`: tests for this app
- `admin.py`: register the app with the admin framework, possibly specialising it
- `apps.py`: any extra things that need to happen when the app is initialised
- `context_processors.py`: defines extra variables that are provided to templates
- `forms.py`: defines web forms: fields, validation, etc.
- `managers.py`: special ways of interacting with the database
- `models.py`: defines what this app stores in the database
- `signals.py`: handlers that can be run when particular events happen
- `urls.py`: maps the URLs this app provides to the views that produce content
- `views.py`: the functions that create each web page, REST endpoint, etc.

See also the [Django documentation](https://docs.djangoproject.com/) for more guidance!

## Editing 'static' content

Templates for generated pages are all in the [weblab/templates](../weblab/templates) folder.
There are sub-folders for each app, as well as other related folders.
To find out which file to edit, look at the `urls.py` and `views.py` files to see where the relevant URL is handled.
Most 'static' content however is in the root templates folder.

## Deploying new versions

See the [deployment repository](https://github.com/ModellingWebLab/deployment).
