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
* POST `/(model|protocol|experiment)`
    * `{task: 'createNewEntity'}` - creates a new entity version, or an entirely new entity
    * `{task: 'verifyNewEntity'}` - called to check individual properties (e.g. name) as the user fills them in
    * `{task: 'updateEntityFile'}` - creates a new version of an existing entity by changing one file
    * `{task: 'getInfo'}`
    * `{task: 'updateVisibility'}`
    * `{task: 'deleteVersion'}`
    * `{task: 'deleteEntity'}`
    * `{task: 'getInterface'}`
    * `{task: 'updateInterface'}`
