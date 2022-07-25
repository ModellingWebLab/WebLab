var notifications = require('./lib/notifications.js');
var utils = require('./lib/utils.js');
var expt_common = require('./expt_common.js');

var plugins = [
    require('./visualizers/displayPlotFlot/displayPlotFlot.js'),
    require('./visualizers/displayPlotHC/displayPlotHC.js'),
    require('./visualizers/displayUnixDiff/displayUnixDiff.js'),
    require('./visualizers/displayBivesDiff/displayBivesDiff.js'),
];

var graphGlobal = {};

function nextPage(url, replace) {
    if (replace)
        window.history.replaceState(document.location.href, "", url);
    else
        window.history.pushState(document.location.href, "", url);
    parseUrl(null);
}

function registerFileDisplayer(elem) {
    elem.addEventListener("click", function(ev) {
        if (ev.which == 1) {
            ev.preventDefault();
            nextPage(elem.href, false);
        }
    }, true);
}

/**
 * Add a `getContents` method to the file object f (a member of the global `files` collection) which will call
 * `utils.getFileContent` for the version of the file in each experiment being compared (but only on the first time
 * it is called).
 * @param f  the file
 */
function setupDownloadFileContents(f) {
    f.getContents = function(callBack) {
        if (f.hasContents)
            callBack.getContentsCallback(true);
        f.hasContents = true;

        for (var i = 0; i < f.entities.length; i++) {
            utils.getFileContent(f.entities[i].entityFileLink, callBack);
        }
    };
}

/**
 * Called when we have loaded both the default-plots and output-contents files for an experiment from the server.
 * Note that this will be called once per experiment being compared (at least, for those that have both metadata files).
 * @param entity  the experiment object
 * @param showDefault  whether to show a default visualisation (if available)
 */
function highlightPlots(entity, showDefault) {
    // Plot description has fields: Plot title,File name,Data file name,Line style,First variable id,Optional second variable id,Optional key variable id
    // Output contents has fields: Variable id,Variable name,Units,Number of dimensions,File name,Type,Dimensions
    graphGlobal['plotDescription'] = entity.plotDescription;
    outputContents = entity.outputContents;
    for (var i = 1 /* Skip first row - it's a header */ ; i < graphGlobal['plotDescription'].length; i++) {
        if (graphGlobal['plotDescription'][i].length < 3)
            continue;
        var data_file_code = graphGlobal['plotDescription'][i][2].hashCode(),
            f = graphGlobal['files'][data_file_code];
        if (f) {

            // See if we should show this as the default plot.
            // If a single protocol, we choose the first listed in the default-plots file
            // (with the proviso that some experiments might have partial results, hence we need to check all default-plots files).
            // Otherwise, we choose the first one appearing in the most experiments.
            var row = document.getElementById("filerow-" + data_file_code);
            if (row) {
                if (showDefault) {
                    var viz = document.getElementById("filerow-" + data_file_code + "-viz-displayPlotFlot");
                    if (viz) {
                        var thisCount = graphGlobal['singleEntities'].protocol ? graphGlobal['plotDescription'].length : f.entities.length;
                        if ((!graphGlobal['singleEntities'].protocol || i == 1) && thisCount > graphGlobal['defaultVizCount']) {
                            graphGlobal['defaultViz'] = viz;
                            graphGlobal['defaultVizCount'] = thisCount;
                        }
                    }
                }
            }

            // Find the plot x and y object names and units from the output contents file.
            for (var output_idx = 0; output_idx < outputContents.length; output_idx++) {
                if (graphGlobal['plotDescription'][i][4] == outputContents[output_idx][0]) {
                    f.xAxes = outputContents[output_idx][1] + ' (' + outputContents[output_idx][2] + ')';
                    f.xUnits = outputContents[output_idx][2];
                }
                if (graphGlobal['plotDescription'][i][5] == outputContents[output_idx][0]) {
                    f.yAxes = outputContents[output_idx][1] + ' (' + outputContents[output_idx][2] + ')';
                    f.yUnits = outputContents[output_idx][2];
                }
                if (graphGlobal['plotDescription'][i].length > 6 && graphGlobal['plotDescription'][i][6] == outputContents[output_idx][0]) {
                    // When comparing, f.entities is a list of the experiments containing this output data file (`entityLink`),
                    // and the version of the file appearing in each experiment (`entityFileLink`).
                    var key_file = graphGlobal['files'][outputContents[output_idx][4].hashCode()],
                        ent_f = findEntityFileLink(f, entity); // This entity's version of f
                    if (ent_f && key_file) {
                        var ent_key_file = findEntityFileLink(key_file, entity); // This entity's version of the key file
                        if (ent_key_file) {
                            ent_f.keyId = outputContents[output_idx][0];
                            ent_f.keyName = outputContents[output_idx][1];
                            ent_f.keyUnits = outputContents[output_idx][2];
                            ent_f.keyFile = ent_key_file;
                        }
                    }
                }
            }
            f.title = graphGlobal['plotDescription'][i][0];
            f.linestyle = graphGlobal['plotDescription'][i][3];

            graphGlobal['plotFiles'].push(graphGlobal['plotDescription'][i][2]);
        }
    }
    expt_common.sortTable(graphGlobal['filesTable'], graphGlobal['plotFiles']);
    // Show the default visualisation if this is the last experiment to be analysed
    if (graphGlobal['defaultViz'] && graphGlobal['metadataParsed'] == graphGlobal['metadataToParse']) {
        nextPage(graphGlobal['defaultViz'].href, true); // 'Invisible' redirect
    }
}

/**
 * Find the link to a particular entity's version of this file.
 * @param f  the file to look for
 * @param entity  the entity to look for
 * @returns  f.entities[ent_idx].entityFileLink where f.entities[ent_idx].entityLink === entity
 */
function findEntityFileLink(f, entity) {
    for (var ent_idx = 0; ent_idx < f.entities.length; ent_idx++)
        if (f.entities[ent_idx].entityLink === entity)
            return f.entities[ent_idx].entityFileLink;
}

function parseOutputContents(entity, file, showDefault) {
    graphGlobal['metadataToParse'] += 1;
    entity.outputContents = null; // Note that there is one to parse

    var goForIt = {
        getContentsCallback: function(succ) {
            if (succ) {
                utils.parseCsvRaw(file);
                entity.outputContents = file.csv;
                graphGlobal['metadataParsed'] += 1;
                if (entity.plotDescription) {
                    highlightPlots(entity, showDefault);
                }
            }
        }
    };
    utils.getFileContent(file, goForIt);

    return null;
}

function parsePlotDescription(entity, file, showDefault) {
    graphGlobal['metadataToParse'] += 1;
    entity.plotDescription = null; // Note that there is one to parse

    var goForIt = {
        getContentsCallback: function(succ) {
            if (succ) {
                utils.parseCsvRaw(file);
                entity.plotDescription = file.csv;
                graphGlobal['metadataParsed'] += 1;
                if (entity.outputContents) {
                    highlightPlots(entity, showDefault);
                }
            }
        }
    };
    utils.getFileContent(file, goForIt);

    return null;
}

function parseEntities(entityObj) {
    if (entityObj.length == 0) return;

    // State for figuring out whether we're comparing multiple protocols on a single model, or multiple models on a single protocol,
    // or indeed multiple versions of the same model / protocol, etc.
    graphGlobal['firstModelName'] = entityObj[0].modelName;
    graphGlobal['firstModelVersion'] = entityObj[0].modelVersion;
    graphGlobal['firstProtoName'] = entityObj[0].protoName;
    graphGlobal['firstProtoVersion'] = entityObj[0].protoVersion;
    graphGlobal['firstFittingSpecName'] = entityObj[0].fittingSpecName;
    graphGlobal['firstFittingSpecVersion'] = entityObj[0].fittingSpecVersion;
    graphGlobal['firstDatasetName'] = entityObj[0].datasetName;
    var versionsOfModels = {};
    var versionsOfProtocols = {};
    var versionsOfFittingSpecs = {};
    graphGlobal['modelsWithMultipleVersions'] = [];
    graphGlobal['protocolsWithMultipleVersions'] = [];
    graphGlobal['fittingSpecsWithMultipleVersions'] = [];

    // Sort entityObj list by .name
    entityObj.sort(function(a, b) {
        return (a.name.toLocaleLowerCase() > b.name.toLocaleLowerCase()) ? 1 : ((b.name.toLocaleLowerCase() > a.name.toLocaleLowerCase()) ? -1 : 0);
    });

    for (var i = 0; i < entityObj.length; i++) {
        var entity = entityObj[i];

        if (graphGlobal['singleEntities'].model && (entity.modelName != graphGlobal['firstModelName'])) {
            graphGlobal['singleEntities'].model = false;
        }

        if (versionsOfModels[entity.modelName] === undefined) {
            versionsOfModels[entity.modelName] = entity.modelVersion;
        } else if (versionsOfModels[entity.modelName] != entity.modelVersion) {
            graphGlobal['modelsWithMultipleVersions'].push(entity.modelName);
            graphGlobal['versionComparisons'].model = true;
        }

        if (graphGlobal['singleEntities'].protocol && (entity.protoName != graphGlobal['firstProtoName'])) {
            graphGlobal['singleEntities'].protocol = false;
        }

        if (versionsOfProtocols[entity.protoName] === undefined) {
            versionsOfProtocols[entity.protoName] = entity.protoVersion;
        } else if (versionsOfProtocols[entity.protoName] != entity.protoVersion) {
            graphGlobal['protocolsWithMultipleVersions'].push(entity.protoName);
            graphGlobal['versionComparisons'].protocol = true;
        }

        if (graphGlobal['singleEntities'].fittingspec && (entity.fittingSpecName != graphGlobal['firstFittingSpecName'])) {
            graphGlobal['singleEntities'].fittingspec = false;
        }

        if (versionsOfFittingSpecs[entity.fittingSpecName] === undefined) {
            versionsOfFittingSpecs[entity.fittingSpecName] = entity.fittingSpecVersion;
        } else if (versionsOfFittingSpecs[entity.fittingSpecName] != entity.fittingSpecVersion) {
            graphGlobal['fittingSpecsWithMultipleVersions'].push(entity.fittingSpecName);
            graphGlobal['versionComparisons'].fittingspec = true;
        }

        if (graphGlobal['singleEntities'].dataset && (entity.datasetName != graphGlobal['firstDatasetName'])) {
            graphGlobal['singleEntities'].dataset = false;
        }

        // Fill in the entities and files entries for this entity
        graphGlobal['entities'][entity.id] = entity;
        if (entity.files)
            for (var j = 0; j < entity.files.length; j++) {
                var file = entity.files[j],
                    sig = file.name.hashCode();
                file.signature = sig;
                file.type = file.filetype;
                if (!graphGlobal['files'][sig]) {
                    graphGlobal['files'][sig] = {};
                    graphGlobal['files'][sig].sig = sig;
                    graphGlobal['files'][sig].name = file.name;
                    graphGlobal['files'][sig].entities = new Array();
                    graphGlobal['files'][sig].div = {};
                    graphGlobal['files'][sig].viz = {};
                    graphGlobal['files'][sig].hasContents = false;
                    graphGlobal['files'][sig].id = file.name;
                    setupDownloadFileContents(graphGlobal['files'][sig]);
                }
                if (file.name.toLowerCase() == "outputs-default-plots.csv")
                    parsePlotDescription(entity, file, !(graphGlobal['fileName'] && graphGlobal['pluginName']));
                if (file.name.toLowerCase() == "outputs-contents.csv")
                    parseOutputContents(entity, file, !(graphGlobal['fileName'] && graphGlobal['pluginName']));

                graphGlobal['files'][sig].entities.push({
                    entityLink: entity,
                    entityFileLink: file
                });
            }
    }

//    console.log(graphGlobal['singleEntities'].model ? 'single model' : 'multiple models',
//        graphGlobal['versionComparisons'].model ? ('- compare versions of ' + graphGlobal['modelsWithMultipleVersions'].join(',')) : '');
//    console.log(graphGlobal['singleEntities'].protocol ? 'single protocol' : 'multiple protocols',
//        graphGlobal['versionComparisons'].protocol ? ('- compare versions of ' + graphGlobal['protocolsWithMultipleVersions'].join(',')) : '');
//    console.log(graphGlobal['singleEntities'].fittingspec ? 'single fitting spec' : 'multiple fitting specs',
//        graphGlobal['versionComparisons'].fittingspec ? ('- compare versions of ' + graphGlobal['fittingSpecsWithMultipleVersions'].join(',')) : '');
//    console.log(graphGlobal['singleEntities'].dataset ? 'single dataset' : 'multiple datasets')


    var entityTypes = ['model', 'protocol'];
    if (graphGlobal['entityType'] == 'result') entityTypes.push('fittingspec', 'dataset');

    var entityTypeDisplayStrings = {
        model: 'model',
        protocol: 'protocol',
        fittingspec: 'fitting spec',
        dataset: 'dataset',
    };

    // List of entity types which have multiple objects
    var entityTypesToCompare = entityTypes.filter(entityType => !graphGlobal['singleEntities'][entityType]);

    // List of entity types which have multiple versions but not multiple objects
    var entityVersionsToCompare = entityTypes.filter(entityType => graphGlobal['versionComparisons'][entityType] && graphGlobal['singleEntities'][entityType]);

    // Add version info to plot labels where needed
    for (var i = 0; i < entityObj.length; i++) {
        var entity = entityObj[i];

        var modelDescription = entity.modelName + (graphGlobal['modelsWithMultipleVersions'].includes(entity.modelName) ? ('@' + entity.modelVersion) : '');
        var protoDescription = entity.protoName + (graphGlobal['protocolsWithMultipleVersions'].includes(entity.protoName) ? ('@' + entity.protoVersion) : '');
        var fitspecDescription = entity.fittingSpecName + (graphGlobal['fittingSpecsWithMultipleVersions'].includes(entity.fittingSpecName) ? ('@' + entity.fittingSpecVersion) : '');
        var datasetDescription = entity.datasetName;

        // Descriptions of things that have entity comparisons
        var descriptions = [];
        if (entityTypesToCompare.includes('model')) descriptions.push(modelDescription);
        if (entityTypesToCompare.includes('protocol')) descriptions.push(protoDescription);
        if (entityTypesToCompare.includes('fittingspec')) descriptions.push(fitspecDescription);
        if (entityTypesToCompare.includes('dataset')) descriptions.push(datasetDescription);
        var entityDescription = descriptions.join(' & ');

        // Version labels of things that have version comparisons
        var versionLabels = [];
        if (entityVersionsToCompare.includes('model')) versionLabels.push('@' + entity.modelVersion);
        if (entityVersionsToCompare.includes('protocol')) versionLabels.push('@' + entity.protoVersion);
        if (entityVersionsToCompare.includes('fittingspec')) versionLabels.push('@' + entity.fittingSpecVersion);
        var versionString = versionLabels.join(' & ');

        if (entityTypesToCompare.length == 0) {
            // All same entities, possibly different versions of them
            if (entityVersionsToCompare.length == 0) {
                // Single versions of everything - show the run number
                entity.plotName = 'Run ' + entity.runNumber;
            } else {
                // Just version comparisons
                entity.plotName = versionString;
            }
        } else {
            // List versions and entities that vary between experiments
            if (versionString.length > 0) {
                entity.plotName = versionString + ' & ' + entityDescription;
            } else {
                entity.plotName = entityDescription;
            }
        }
    }

    // Alter heading to reflect type of comparison
    var pageTitle = "Comparison of " + graphGlobal['entityType'].charAt(0).toUpperCase() + graphGlobal['entityType'].slice(1) + "s";

    if (graphGlobal['entityType'] == "experiment" || graphGlobal['entityType'] == "result") {
        if (entityTypesToCompare.length == 0) {
            // All same entities, just possibly different versions of them
            pageTitle = graphGlobal['firstModelName'] + " & " + graphGlobal['firstProtoName'];
            if (entityVersionsToCompare.length == 1) {
                // Just one type of version comparison
                pageTitle += " experiments: comparison of " + entityTypeDisplayStrings[entityVersionsToCompare[0]] + " versions";
                // label: '@<version>'
            } else if (entityVersionsToCompare.length > 1) {
                // Multiple types of version comparison
                pageTitle += " experiments: comparison of versions";
                // label: '@<model version> & @<protocol version>' etc.
            } else {
                // Single versions of everything
                pageTitle += ": comparison of repeat experiments";
                // label: 'Run <n>'
            }
        } else if (entityTypesToCompare.length == 1) {
            // Just one type of entity comparison, possibly also with version comparisons
            pageTitle = graphGlobal['singleEntities'].model ? graphGlobal['firstModelName'] : graphGlobal['firstProtoName'];
            pageTitle += " experiments : comparison of " + entityTypeDisplayStrings[entityTypesToCompare[0]] + "s";
            // If just one type of version comparison, be specific.
            // Otherwise, just say "versions"
            if (entityVersionsToCompare.length == 1) {
                pageTitle += " and " + entityTypeDisplayStrings[entityVersionsToCompare[0]] + " versions";
                // label: '<model name>@<model version>'
                // label: '<model name> & @<protocol version>'
            } else if (entityVersionsToCompare.length > 1) {
                pageTitle += " and versions";
                // label: '<model name>@<model version> & @<protocol version>'
            }
        } else if (entityTypesToCompare.length == 2) {
            // Two types of entity comparisons
            // just list those and take the title from one of the other entity types
            var entityName;
            if (graphGlobal['singleEntities'].model) {
                entityName = graphGlobal['firstModelName'];
            } else if (graphGlobal['singleEntities'].protocol) {
                entityName = graphGlobal['firstProtoName'];
            } else if (graphGlobal['firstFittingSpecName'] && graphGlobal['singleEntities'].fittingspec) {
                entityName = graphGlobal['firstFittingSpecName'];
            }
            if (entityName !== undefined) {
                pageTitle = entityName + " experiments: comparison of " + entityTypeDisplayStrings[entityTypesToCompare[0]] + "s and " + entityTypeDisplayStrings[entityTypesToCompare[1]] + "s";
            }
            // label: "<model name> & <protocol name>"
        }
        if (graphGlobal['doc'].heading) {
            graphGlobal['doc'].heading.innerHTML = pageTitle;
        }

        // This was used in an earlier version and is still expected to exist by plugins
        $.data(document.body, 'plotLabelStripText', '');
    }

    // Create a drop-down box that allows display of/navigate to experiments being compared
    var entitiesToCompare = document.getElementById("entitiesToCompare");

    $(entitiesToCompare).empty();
    if (graphGlobal['doc'].outputFileHeadline) {
        graphGlobal['doc'].outputFileHeadline.innerHTML = "Output files from all compared " + graphGlobal['entityType'] + "s";
        var form = document.createElement("form");
        entitiesToCompare.appendChild(form);
        var select_box = document.createElement("select");
        select_box.name = "experiment_box";
        select_box.id = "exptSelect";
        var default_option = document.createElement("option");
        default_option.selected = true;
        default_option.value = document.location.href;
        default_option.innerHTML = "Click to view, select to show a single " + graphGlobal['entityType'];
        select_box.onchange = function() {
            sel = document.getElementById("exptSelect");
            console.log(sel);
            document.location.href = sel.options[sel.selectedIndex].value;
        };
        select_box.appendChild(default_option);
        for (var entity in graphGlobal['entities']) {
            var option = document.createElement("option");
            option.value = graphGlobal['entities'][entity].url;
            option.innerHTML = graphGlobal['entities'][entity].name + ((graphGlobal['entityType'] == "experiment" || graphGlobal['entityType'] == "result") ? "" : " &mdash; " + graphGlobal['entities'][entity].version);
            select_box.appendChild(option);
        }
        form.innerHTML = graphGlobal['entityType'].charAt(0).toUpperCase() + graphGlobal['entityType'].slice(1) + "s selected for comparison: ";
        form.appendChild(select_box);
    }

    buildSite();
}

function buildSite() {
    var filestableElement = document.getElementById("filestable");
    if (filestableElement) {
        graphGlobal['filesTable'] = {};
        graphGlobal['filesTable'].table = filestableElement;
        graphGlobal['filesTable'].plots = {};
        graphGlobal['filesTable'].pngeps = {};
        graphGlobal['filesTable'].otherCSV = {};
        graphGlobal['filesTable'].defaults = {};
        graphGlobal['filesTable'].text = {};
        graphGlobal['filesTable'].other = {};
        graphGlobal['filesTable'].all = new Array();

        var tr = document.createElement("tr");

        var td = document.createElement("th");
        td.appendChild(document.createTextNode("Name"));
        tr.appendChild(td);

        td = document.createElement("th");
        td.appendChild(document.createTextNode("Avg size"));
        tr.appendChild(td);

        td = document.createElement("th");
        td.appendChild(document.createTextNode("Action"));
        tr.appendChild(td);

        filestableElement.appendChild(tr);

        for (var file in graphGlobal['files']) {
            var ents = graphGlobal['files'][file];
            var curFileName = ents.name;
            tr = document.createElement("tr");
            tr.id = "filerow-" + ents.sig;
            filestableElement.appendChild(tr);
            td = document.createElement("td");
            td.appendChild(document.createTextNode(curFileName + " (" + ents.entities.length + ")"));
            tr.appendChild(td);

            graphGlobal['filesTable'].all.push({
                name: curFileName,
                row: tr
            });

            td = document.createElement("td");
            var size = 0;
            for (var i = 0; i < ents.entities.length; i++) {
                size += ents.entities[i].entityFileLink.size;
            }
            td.appendChild(document.createTextNode(utils.humanReadableBytes(size / ents.entities.length)));
            tr.appendChild(td);

            /*td = document.createElement("td");
            td.appendChild(document.createTextNode("action"));*/

            td = document.createElement("td");
            for (var vi in graphGlobal['visualizers']) {
                var viz = graphGlobal['visualizers'][vi];
                if (!viz.canRead(ents.entities[0].entityFileLink))
                    continue;
                var a = document.createElement("a");
                a.setAttribute("id", "filerow-" + file + "-viz-" + viz.getName());
                a.href = basicurl + 'show/' + encodeURIComponent(graphGlobal['files'][file].name) + "/" + vi;
                var img = document.createElement("img");
                img.src = staticPath + "js/visualizers/" + vi + "/" + viz.getIcon();
                img.alt = viz.getDescription();
                img.title = img.alt;
                a.appendChild(img);
                registerFileDisplayer(a);
                td.appendChild(a);
                td.appendChild(document.createTextNode(" "));
            }
            tr.appendChild(td);
        }
    }
    handleReq();
}

function displayFile(id, pluginName) {
    if (!graphGlobal['gotInfos'])
        return;
    var f = graphGlobal['files'][id];
    if (!f) {
        notifications.add("no such file", "error");
        return;
    }
    for (var ent_idx = 0; ent_idx < f.entities.length; ent_idx++) {
        var entity = f.entities[ent_idx].entityLink;
        if (entity.outputContents === null || entity.plotDescription === null) {
            // Try again in 0.1s, by which time hopefully they have been parsed
            window.setTimeout(function() {
                displayFile(id, pluginName)
            }, 100);
            return;
        }
    }
    if (graphGlobal['doc'].fileName) {
        graphGlobal['doc'].fileName.innerHTML = f.name;
    }

    if (!f.div[pluginName]) {
        f.div[pluginName] = document.createElement("div");
        f.viz[pluginName] = graphGlobal['visualizers'][pluginName].setUpComparision(f, f.div[pluginName]);
    }
    $(graphGlobal['doc'].fileDisplay).empty();
    graphGlobal['doc'].fileDisplay.appendChild(f.div[pluginName]);
    f.viz[pluginName].show();

    // Show parent div of the file display, and scroll there
    graphGlobal['doc'].fileDetails.style.display = "block";
    var pos = utils.getPos(graphGlobal['doc'].heading);
    if (graphGlobal['scroll']) {
        window.scrollTo(pos.xPos, pos.yPos);
    }
}

function handleReq() {
    if (graphGlobal['fileName'] && graphGlobal['pluginName'] && graphGlobal['gotInfos']) {
        displayFile(graphGlobal['fileName'].hashCode(), graphGlobal['pluginName']);
        if (graphGlobal['doc'].displayClose) {
            graphGlobal['doc'].displayClose.href = basicurl;
        }
    } else {
        graphGlobal['doc'].fileDetails.style.display = "none";
    }
}

function getInfos(url) {
    $.getJSON(url, function(data) {
        notifications.display(data);
        graphGlobal['gotInfos'] = true;

        if (data.getEntityInfos) {
            parseEntities(data.getEntityInfos.entities);
        }
    })
}

function parseUrl(event) {
    var entityIds = null;
    if ($('#entityIdsToCompare').length) {
        var parts = $('#entityIdsToCompare').val().split("/");
    } else {
        var parts = document.location.pathname.split("/");
    }

    for (var i = 0; i < parts.length; i++) {
        if (parts[i] == 'experiments') {
            basicurl = parts.slice(0, i + 2).join('/') + '/';
            graphGlobal['entityType'] = 'experiment';
            entityIds = parts.slice(i + 2);
            break;
        } else if (parts[i] == 'results') {
            basicurl = parts.slice(0, i + 2).join('/') + '/';
            graphGlobal['entityType'] = 'result';
            entityIds = parts.slice(i + 2);
        } else if (parts[i + 1] == 'compare') {
            basicurl = parts.slice(0, i + 2).join('/') + '/';
            graphGlobal['entityType'] = parts[i].slice(0, parts[i].length - 1);
            entityIds = parts.slice(i + 2);
            break;
        }
    }

    if (!entityIds) {
        var entitiesToCompare = document.getElementById("entitiesToCompare");
        $(entitiesToCompare).empty();
        entitiesToCompare.appendChild(document.createTextNode("ERROR building site"));
        return;
    }

    graphGlobal['fileName'] = null;
    graphGlobal['pluginName'] = null;
    var TentityIds = new Array();


    for (var i = 0; i < entityIds.length; i++) {
        if (entityIds[i] == "show") {
            if (i + 2 < entityIds.length) {
                graphGlobal['fileName'] = entityIds[i + 1];
                graphGlobal['pluginName'] = entityIds[i + 2];
            }
            entityIds = entityIds.slice(0, i);
            break;
        } else if (entityIds[i])
            TentityIds.push(entityIds[i]);
    }
    entityIds = TentityIds;
    basicurl = basicurl + entityIds.join("/") + "/";

    if (!graphGlobal['tableParsed']) {
        graphGlobal['tableParsed'] = true;
        getInfos($("#entitiesToCompare").data('comparison-href'));
    } else
        handleReq();

}

function initCompare(scroll = true) {
    graphGlobal = {
        entities: {}, // Contains information about each experiment being compared
        // `files` contains information about each unique (by name) file within the compared experiments,
        // including references to the experiments in which a file of that name appears and that particular instance of the file.
        files: {},
        entityType: null,
        visualizers: {},
        tableParsed: false,
        fileName: null,
        pluginName: null,
        doc: {
            heading: document.getElementById("heading"),
            displayClose: document.getElementById("fileclose"),
            fileName: document.getElementById("filename"),
            fileDisplay: document.getElementById("filedisplay"),
            fileDetails: document.getElementById("filedetails"),
            outputFileHeadline: document.getElementById("outputFileHeadline")
        },
        gotInfos: false,
        plotDescription: null,
        plotFiles: new Array(),
        filesTable: {},
        // Used for determining what graph (if any) to show by default
        metadataToParse: 0,
        metadataParsed: 0,
        defaultViz: null,
        defaultVizCount: 0,
        // State for figuring out whether we're comparing multiple protocols on a single model, or multiple models on a single protocol
        firstModelName: "",
        firstModelVersion: "",
        firstProtoName: "",
        firstProtoVersion: "",
        firstFittingSpecName: "",
        firstFittingSpecVersion: "",
        firstDatasetName: "",
        modelsWithMultipleVersions: [],
        protocolsWithMultipleVersions: [],
        fittingSpecsWithMultipleVersions: [],
        singleEntities: {
            model: true,
            protocol: true,
            fittingspec: true,
            dataset: true,
        },
        versionComparisons: {
            model: false,
            protocol: false,
            fittingspec: false,
            dataset: false,
        },
        scroll: scroll,
    }

//    graphGlobal['doc'].fileDetails.style.display = "none";

    // Prevent redirection to the default plot when we close it
    if (graphGlobal['doc'].displayClose) {
        graphGlobal['doc'].displayClose.addEventListener("click", function(ev) {
            if (ev.which == 1) {
                ev.preventDefault();
                graphGlobal['doc'].fileDetails.style.display = "none";
                shownDefault = true;
                nextPage(graphGlobal['doc'].displayClose.href, false);
            }
        }, true);
    }

    window.onpopstate = (event) => {parseUrl(event, '');}
    parseUrl(null);

    $(plugins).each(function(i, plugin) {
        graphGlobal['visualizers'][plugin.name] = plugin.get_visualizer();
    });
}

// initialise (all) compare graphs on the page
$(document).ready(function() {
    if($('#entitiesToCompare').length){
        initCompare('', true);
    }
});
