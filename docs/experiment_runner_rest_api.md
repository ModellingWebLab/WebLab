# Experiment runner web service - REST API

This document describes the interface that the Django app needs to talk to for running experiments.
This web service also provides end points for tasks such as checking protocol syntax and determining a protocol's 'interface'.

There is a single URL (configurable) for the end points, with the behaviour depending on what parameters are passed as form fields in a POST request.

Generic fields:
* `password`: needs to match the password configured for this service, or an error response is returned.
  This should be settable from the Django config so it can be provided as a secret when deployed.

An error response here means (currently) a small HTML page with an error message in the body.
The message may include a Python traceback in rare cases, so some formatting is helpful.

We could easily change all responses to be consistently JSON formatted data, or anything else sensible.

## Callback authentication

The web service needs to be able to GET private entities.
To support this, the `signature` passed to it by the Django app can also be used as an authentication token in GET requests.
When making GET requests, the web service will supply the HTTP header `Authorization: Token <signature>`, where `<signature>` is replaced by the supplied signature.

## Get protocol interface (and check syntax)

Fields:
* `getProtoInterface`: URL from which the protocol COMBINE archive can be downloaded with GET
* `callBack`: URL to send results to when ready
* `signature`: opaque string that the Django site can use to verify that the response is expected and which protocol it is for

Response: empty `text/plain` document unless one of the above fields is missing, in which case an error message as above.
The front-end ignores this response entirely.

This will schedule a Celery task to parse the protocol and extract its interface.
When the task completes it will send a response to the `callBack` URL, including the `signature`.

The callback will POST JSON data consisting of a single object with fields:
* `signature`: as supplied above
* `returntype`: 'success' or 'failed'
* `returnmsg`: if failed, an error string formatted with simple HTML (`br` tags only I think)
* `required`: if success, a list of strings (the required ontology terms in the protocol's interface)
* `optional`: if success, a list of strings (the optional ontology terms in the protocol's interface)
* `ioputs`: if success, a list of {'name', 'units', 'kind'} objects detailing the inputs & outputs to the protocol

This callback will be retried up to a configurable number of times if there is no response.
After that, a new Celery task will be scheduled to send a brief error message (to the same callback URL) reporting that it gave up trying.
This error payload will similarly be a JSON object with `returntype` and `returnmsg` fields.

## Get model interface (and check syntax)

Fields:
* `getModelInterface`: URL from which the model COMBINE archive can be downloaded with GET
* `callBack`: URL to send results to when ready
* `signature`: opaque string that the Django site can use to verify that the response is expected and which protocol it is for

Response: empty `text/plain` document unless one of the above fields is missing, in which case an error message as above.
The front-end ignores this response entirely.

This will schedule a Celery task to parse the model and extract its ontology interface.
When the task completes it will send a response to the `callBack` URL, including the `signature`.

The callback will POST JSON data consisting of a single object with fields:
* `signature`: as supplied above
* `returntype`: 'success' or 'failed'
* `returnmsg`: if failed, an error string formatted with simple HTML (`br` tags only I think)
* `model_terms`: if success, a list of strings (the ontology terms used to annotate model variables)

This callback will be retried up to a configurable number of times if there is no response.
After that, a new Celery task will be scheduled to send a brief error message (to the same callback URL) reporting that it gave up trying.
This error payload will similarly be a JSON object with `returntype` and `returnmsg` fields.

## Run experiment

Fields:
* `callBack`: URL to send results to when ready (also used for status pings as the task runs)
* `signature`: opaque string that the Django site can use to verify that the response is expected and which experiment it is for
* `model`: URL from which the model COMBINE archive can be downloaded with GET
* `protocol`: URL from which the protocol COMBINE archive can be downloaded with GET
* `user`: ID (email address currently) of the user running the experiment; used for task prioritisation
* `isAdmin`: 'true' or 'false' depending on whether the user is a site admin; used for task prioritisation

Response: `text/plain` unless one of the above fields is missing, in which case an error message as above.

This schedules a Celery task to run the experiment and return the results to the callBack URL.
Once the task is submitted the original web service call returns immediately with the string `'{} succ {}'.format(signature, task_id)`.
When this is received the front-end sets the experiment status as 'queued'.

The run experiment task performs several steps:
1. Download model & protocol from supplied URLs
2. Check protocol is applicable to model; send an 'inapplicable' callback if not and stop
3. Send a 'running' callback ping
4. Runs the experiment, maybe sending further occasional 'running' callback pings
5. Sends a final callback response with the results

### Experiment task responses

The Celery task will POST to the callback URL at various stages of job running.
In each case it will supply JSON data consisting of a single object with fields:
* `signature`: as supplied above
* `returntype`: an experiment status code as a string;
  one of 'inapplicable', 'failed', 'running', 'partial', 'success'
* `returnmsg`: a message string formatted with simple HTML (`br` tags and `&nbsp;` only I think),
  depending on the status code:
    - for 'inapplicable' it lists the missing required and optional ontology terms
    - for 'failed' it will typically include the Python traceback for the error, but may be omitted
      if the failure occurred after the experiment started
    - for 'running', 'partial', 'success' and some 'failure' cases this field is omitted

If the experiment got as far as starting, there will also be a file upload named 'experiment' of a COMBINE Archive with the experiment results.
This archive will contain at least:
* `stdout.txt`: stdout and stderr combined from the experiment run
* `errors.txt`: a summary of key errors if the experiment did not succeed (status is 'partial' or 'failure')

For the 'running' pings during execution, `stdout.txt` will be the only file.
Each time the complete output from the start of the run will be submitted, so any previously sent file can be replaced.

If the experiment was successful, there will be some additional metadata files:
* `outputs-default-plots.csv` lists the plots produced in the order defined by the protocol.
  It has columns: Plot title,File name,Data file name,Line style,First variable id,Optional second variable id,Optional key variable id
* `outputs-contents.csv` lists all data CSV files produced by the protocol.
  It has columns: Variable id,Variable name,Units,Number of dimensions,File name,Type,Dimensions

(When displaying an entity, WL1 will show one of its files automatically: error.txt if it exists; otherwise readme.md if a model/protocol or the first plot if an experiment. This is done by the JS code.)

The final status is 'success' if the experiment ran without error,
'partial' if there was an error but at least some of the expected output graphs were produced,
and 'failure' otherwise.

## Cancel experiment

Fields:
* `cancelTask`: a Celery task_id as returned by a 'run experiment' call

Response: an empty `text/plain` document always (ignored)

Will revoke the relevant Celery task using `signal.SIGUSR1`.
This may give the task a chance to report an error via callback if it is already running.
If it has not yet started it just won't run.
