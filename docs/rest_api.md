# Web Lab REST API

This document outlines the API calls made by the Javascript code to the Tomcat server, and hence what will need to be reproduced by the Django code.
For details of what the calls do, see the indicated Java source file.

Note that in the current system some of these URLs actually have .html after the initial component (e.g. `admin.html` instead of `admin`), which I don't think we want to keep.
There is probably further scope for tidying - feel free to suggest things!

All POST requests take JSON data, and usually return JSON.
The returned object has some common fields, some defined in the base `WebModule.java` file:
* `notifications: { errors: [ <string> ], notes: [ <string> ] }`
* An object named depending on the call, with fields (indicated by `<defaults>` below):
    * `response: true|false` - indicates success or (normal) failure; if the Java code throws an exception this becomes a 500 HTTP response
    * `responseText: <string>` - message usually displayed to user
A `?` after a JSON field name indicates that the field is optional.

Arguably we'd be more RESTful to turn some of these POST requests into GET ones, since they don't actually change anything on the server...

Pretty much all these calls check the identity of the logged in user (if any) and whether they are permitted to view/modify the relevant state.

## Admin.java

* POST `/admin`
    * `{task: 'updateUserRole', user: <id>, role: <string>}` - change role for a user; returns `{ updateUserRole: { <defaults> }`

## Batch.java

* POST `/batch/(model|protocol)/*/<version_id>`
    * `{task: 'batchSubmit', force?: <bool>, entities: [<version_id>]}` - batch-create new experiments with a single model/protocol and multiple protocols/models; returns `{ batchSubmit: { <defaults>, createdExps: [{versId: <version_id>, url: <url>}] } }`
* POST `/batch/batch`
    * `{force?: <bool>, batchTasks: [ { model?: <version_id>, protocol?: <version_id>, experiment?: <version_id>|'*' } ] }` - re-run some experiments; either all (if `experiment: '*'` is given) or specific ones, or ones for a specific model/protocol. Returns `{batchTasks: { <defaults>, createdExps: [{versId: <version_id>, url: <url>}] }}`

With both of the above notifications are added indicating success/failure for individual experiment launches.

## Compare.java

* POST `/compare/(m|p|e)/`
    * `{task: 'getEntityInfos', getBy?: 'versionId', ids: [<version_or_entity_id>]}` - get info about the latest or specified version of given entities. Returns `{getEntityInfos: {<defaults>, entities: [{JSON repr of entity version}]}}`
    * `{task: 'getUnixDiff', entity1: <version_id>, entity2: <version_id>, file1: <id>, file2: <id>}` - do a diff between two versions of a file. Returns `{getUnixDiff: {<defaults>, unixDiff: <string>}}`
    * `{task: 'getBivesDiff'}` - as above, but diffs two models using an external service. There's a Java client (written by the person that wrote the original Web Lab interface) so doing this in Python will be harder!

## DB.java

* POST `/db/*`
    * `{task: 'getMatrix', showAll?: <bool>, publicOnly?: <bool>, mineOnly?: <bool>, modelIds?: [<entity_id>], protoIds?: [<entity_id>], includeModeratedModels?: <bool>, includeModeratedProtocols?: <bool>}` - get the information for the experiments matrix. The various optional arguments allow the view to be filtered in various ways. Returns `{getMatrix: {models: [{JSON repr}], protocols: [], experiments: []}}`

## EntityView.java

This file does a lot! It handles the pages for both initial creation of new entities/versions, as well as displaying info about existing ones, or individual files within them:
* GET `/(model|protocol|experiment)/createnew`
* GET `/(model|protocol|experiment)/<entity_name (ignored)>/<entity_id>/latest`
* GET `/(model|protocol|experiment)/<entity_name (ignored)>/<entity_id>/<version_name (ignored)>/<version_id>/<file_id?>/<action?>`

There are also API calls:
* POST `/protocol/submitInterface.html`
    * `{signature: <string>, returntype: 'success'|'failed', returnmsg?: <string>, optional: [<uri>], required: [<uri>]}` - callback for a Celery task updating a protocol's interface info in the DB
* POST `/(model|protocol|experiment)`
    * `{task: 'createNewEntity', many other fields!}` - creates a new entity version, or an entirely new entity
    * `{task: 'verifyNewEntity', entityName, visibility, versionName, commitMsg}` - called to check individual properties (e.g. name) as the user fills them in
    * `{task: 'updateEntityFile', baseVersionId: <id>, fileName: <string>, fileContents: <string>}` - creates a new version of an existing entity by changing one file
    * `{task: 'getInfo', version: <id>}` - get a JSON dump of an entity version
    * `{task: 'updateVisibility', version: <id>, visibility: <string>}` - change the visibility field for an entity version
    * `{task: 'deleteVersion', version: <id>}` - remove a version of an entity (and the whole entity if this was the only version)
    * `{task: 'deleteEntity', entity: <id>}` - remove an entire entity
    * `{task: 'getInterface'}` - returns interface info for all protocols a user can see
    * `{task: 'updateInterface', version: <version_id>}` - submit a Celery task to update a protocol's interface info in the DB

## FileTransfer.java

This handles GET requests to download files, whether individual files within an entity, or a '[COMBINE Archive](http://co.mbine.org/documents/archive)' (ZIP file) of all the file making up an entity.

It also has a `cleanUP` that gets run randomly every 20 or so page requests to check there aren't any stale files in the filestore that are no longer referenced by the DB.

It also handles the API calls for returning experiment results and file uploads:
* `POST /submitExperiment.html`
    * This takes request parameters rather than a JSON object, since there will (hopefully) be a file upload involved
    * `signature` - indicates which experiment this is a result for
    * `taskid` - if given, this is just a ping with the Celery id of the running tasks, in case the user wants to cancel it. If not present, we should have the following:
    * `returnmsg` - contains any error message
    * `returntype` - gives the status of the experiment (success, partial, failed, inapplicable, running).
        * If 'running' or 'inapplicable' we just update the status and stop processing.
        * Otherwise, we will send mail to the user (if they chose to receive status emails), and process the results.
    * `experiment` - a [COMBINE Archive](http://co.mbine.org/documents/archive) containing the result files. This will be unpacked and the contents stored
* `POST /upload.html`
    * Again this takes request parameters rather than a JSON object, but it returns a JSON object as response with the name of the file in the temporary store. This supports users uploading files individually when creating a new entity version.
    * `file` - the uploading file

The class also has further utility methods for communicating with the Celery experiment runner (sending messages), e.g. `submitExperiment`, `getProtocolInterface`, `cancelExperiments`

## Index.java

Just displays the index page. No API calls.

## Login.java, Logout.java, Register.java

Just handle user login/logout/registration, via web pages & API calls; will be obsolete.

## Me.java

A GET request to `/myfiles.html` displays the user's entities on different tabs. `GET /myaccount.html` shows the user's profile.

APIs:
* `POST /myaccount.html` - change various fields in the user's profile
    * `{task: updatePassword, prev, next}` - change password
    * `{task: updateInstitute, institute: <string>}` - change Institute
    * `{task: updateSendMails, sendMail: <bool>}` - change whether user wants automated emails when experiments finish
    * `{task: updatePref, prefKey: <string>, prefVal: <string>}` - change arbitrary user preference field

## NewExperiment.java

This provides a single API, and no corresponding web page.

* `POST /newexperiment.html`
    * `{task: newExperiment, model: <version_id>, protocol: <version_id>, forceNewVersion: <bool>}` - start a new experiment running; optionally creating a new version of an already-run expt if the user has permission to do so (admins only at present)
