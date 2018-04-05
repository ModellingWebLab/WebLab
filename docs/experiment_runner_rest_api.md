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

## Get protocol interface (and check syntax)

Fields:
* `getProtoInterface`: URL from which the protocol COMBINE archive can be downloaded with GET
* `callBack`: URL to send results to when ready
* `signature`: opaque string that the Django site can use to verify that the response is expected and which protocol it is for

Response: empty `text/plain` document unless one of the above fields is missing, in which case an error message as above.
The current front-end ignores this response entirely...

This will schedule a Celery task to parse the protocol and extract its interface.
When the task completes it will send a response to the `callBack` URL, including the `signature`.

The callback will POST JSON data consisting of a single object with fields:
* `signature`: as supplied above
* `returntype`: 'success' or 'failed'
* `returnmsg`: if failed, an error string formatted with simple HTML (`br` tags only I think)
* `required`: if success, a list of strings (the required ontology terms in the protocol's interface)
* `optional`: if success, a list of strings (the optional ontology terms in the protocol's interface)

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

### Experiment task responses

## Cancel experiment

Fields:
* `cancelTask`: a Celery task_id as returned by a 'run experiment' call

Response: an empty `text/plain` document always (ignored)

Will revoke the relevant Celery task using `signal.SIGUSR1`.
This may give the task a chance to report an error via callback if it is already running.
If it has not yet started it just won't run.
