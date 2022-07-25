var notifications = require('./lib/notifications.js');
var utils = require('./lib/utils.js');
var expt_common = require('./expt_common.js');
var csv_cache = {};

var plugins = [
    require('./visualizers/displayPlotFlot/displayPlotFlot.js'),
    require('./visualizers/displayPlotHC/displayPlotHC.js'),
    require('./visualizers/displayUnixDiff/displayUnixDiff.js'),
    require('./visualizers/displayBivesDiff/displayBivesDiff.js'),
];

var graphGlobal = {};

/**
 * Add a `getContents` method to the file object f (a member of the global `files` collection) which will call
 * `utils.getFileContent` for the version of the file in each experiment being compared (but only on the first time
 * it is called).
 * @param f  the file
 */
function setupDownloadFileContents(f, prefix) {
    f.getContents = function(callBack, pref = prefix) {
        for (var i = 0; i < f.entities.length; i++) {
console.log(Object.keys(csv_cache));
console.log(f.entities[i].entityFileLink.url);
          $.extend(f.entities[i].entityFileLink, csv_cache[f.entities[i].entityFileLink.url]);
          callBack.getContentsCallback(true, pref);
        }
    };
}


function parseOutputContents(entity, file, showDefault, prefix) {
    graphGlobal[prefix]['metadataToParse'] += 1;
    entity.outputContents = null; // Note that there is one to parse

    var goForIt = {
        getContentsCallback: function(succ, pref = prefix) {
            if (succ) {
//if(file.url.endsWith('outputs-contents.csv') || !file.url.endsWith('outputs-default-plots.csv')){
//console.log(file.url);
//console.log(file.contents);
//                utils.parseCsvRaw(file);
//}
                entity.outputContents = file.csv;
                graphGlobal[pref]['metadataParsed'] += 1;
            }
        }
    };
    utils.getFileContent(file, goForIt);

    return null;
}


function parseEntities(entityObj, prefix) {
    if (entityObj.length == 0) return;

    // State for figuring out whether we're comparing multiple protocols on a single model, or multiple models on a single protocol,
    // or indeed multiple versions of the same model / protocol, etc.
    var versionsOfModels = {};
    var versionsOfProtocols = {};
    var versionsOfFittingSpecs = {};
    graphGlobal[prefix]['modelsWithMultipleVersions'] = [];
    graphGlobal[prefix]['protocolsWithMultipleVersions'] = [];
    graphGlobal[prefix]['fittingSpecsWithMultipleVersions'] = [];

    // Sort entityObj list by .name
    entityObj.sort(function(a, b) {
        return (a.name.toLocaleLowerCase() > b.name.toLocaleLowerCase()) ? 1 : ((b.name.toLocaleLowerCase() > a.name.toLocaleLowerCase()) ? -1 : 0);
    });

    for (var i = 0; i < entityObj.length; i++) {
        var entity = entityObj[i];
        entity.plotName = entity.modelName;

        // Fill in the entities and files entries for this entity
        graphGlobal[prefix]['entities'][entity.id] = entity;
        if (entity.files)
            for (var j = 0; j < entity.files.length; j++) {
                var file = entity.files[j],
                    sig = file.name.hashCode();
                file.signature = sig;
                file.type = file.filetype;
                if (!graphGlobal[prefix]['files'][sig]) {
                    graphGlobal[prefix]['files'][sig] = {};
                    graphGlobal[prefix]['files'][sig].sig = sig;
                    graphGlobal[prefix]['files'][sig].name = file.name;
                    graphGlobal[prefix]['files'][sig].entities = new Array();
                    graphGlobal[prefix]['files'][sig].div = {};
                    graphGlobal[prefix]['files'][sig].viz = {};
                    graphGlobal[prefix]['files'][sig].hasContents = false;
                    graphGlobal[prefix]['files'][sig].id = prefix + file.name;
                    setupDownloadFileContents(graphGlobal[prefix]['files'][sig], prefix);
                }
                graphGlobal[prefix]['files'][sig].entities.push({
                    entityLink: entity,
                    entityFileLink: file
                });
            }
    }

//    buildSite(prefix);
}

function buildSite(prefix) {
    var filestableElement = document.getElementById(prefix + "filestable");
    if (filestableElement) {
        graphGlobal[prefix]['filesTable'] = {};
        graphGlobal[prefix]['filesTable'].table = filestableElement;
        graphGlobal[prefix]['filesTable'].plots = {};
        graphGlobal[prefix]['filesTable'].pngeps = {};
        graphGlobal[prefix]['filesTable'].otherCSV = {};
        graphGlobal[prefix]['filesTable'].defaults = {};
        graphGlobal[prefix]['filesTable'].text = {};
        graphGlobal[prefix]['filesTable'].other = {};
        graphGlobal[prefix]['filesTable'].all = new Array();

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

        for (var file in graphGlobal[prefix]['files']) {
            var ents = graphGlobal[prefix]['files'][file];
            var curFileName = ents.name;
            tr = document.createElement("tr");
            tr.id = "filerow-" + ents.sig;
            filestableElement.appendChild(tr);
            td = document.createElement("td");
            td.appendChild(document.createTextNode(curFileName + " (" + ents.entities.length + ")"));
            tr.appendChild(td);

            graphGlobal[prefix]['filesTable'].all.push({
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
            for (var vi in graphGlobal[prefix]['visualizers']) {
                var viz = graphGlobal[prefix]['visualizers'][vi];
                if (!viz.canRead(ents.entities[0].entityFileLink))
                    continue;
                var a = document.createElement("a");
                a.setAttribute("id", "filerow-" + file + "-viz-" + viz.getName());
                a.href = basicurl + 'show/' + encodeURIComponent(graphGlobal[prefix]['files'][file].name) + "/" + vi;
                var img = document.createElement("img");
                img.src = staticPath + "js/visualizers/" + vi + "/" + viz.getIcon();
                img.alt = viz.getDescription();
                img.title = img.alt;
                a.appendChild(img);
//                registerFileDisplayer(a, prefix);
                td.appendChild(a);
                td.appendChild(document.createTextNode(" "));
            }
            tr.appendChild(td);
        }
    }
    handleReq(prefix);
}

function displayFile(id, pluginName, prefix) {
    var f = graphGlobal[prefix]['files'][id];
    if (!f) {
        notifications.add("no such file", "error");
        return;
    }
    for (var ent_idx = 0; ent_idx < f.entities.length; ent_idx++) {
        var entity = f.entities[ent_idx].entityLink;
        if (entity.outputContents === null || entity.plotDescription === null) {
            // Try again in 0.1s, by which time hopefully they have been parsed
            window.setTimeout(function() {
                displayFile(id, pluginName, prefix)
            }, 100);
            return;
        }
    }
    if (graphGlobal[prefix]['doc'].fileName) {
        graphGlobal[prefix]['doc'].fileName.innerHTML = f.name;
    }

    if (!f.div[pluginName]) {
        f.div[pluginName] = document.createElement("div");
        f.viz[pluginName] = graphGlobal[prefix]['visualizers'][pluginName].setUpComparision(f, f.div[pluginName]);
    }
    $(graphGlobal[prefix]['doc'].fileDisplay).empty();
    graphGlobal[prefix]['doc'].fileDisplay.appendChild(f.div[pluginName]);
    f.viz[pluginName].show();

    // Show parent div of the file display, and scroll there
    graphGlobal[prefix]['doc'].fileDetails.style.display = "block";
    var pos = utils.getPos(graphGlobal[prefix]['doc'].heading);
}

function handleReq(prefix) {
    if (graphGlobal[prefix]['fileName'] && graphGlobal[prefix]['pluginName']) {
        displayFile(graphGlobal[prefix]['fileName'].hashCode(), graphGlobal[prefix]['pluginName'], prefix);
        if (graphGlobal[prefix]['doc'].displayClose) {
            graphGlobal[prefix]['doc'].displayClose.href = basicurl;
        }
    } else {
        graphGlobal[prefix]['doc'].fileDetails.style.display = "none";
    }
}

function initGraph(prefix) {
    graphGlobal[prefix] = {
        entities: {}, // Contains information about each experiment being compared
        // `files` contains information about each unique (by name) file within the compared experiments,
        // including references to the experiments in which a file of that name appears and that particular instance of the file.
        files: {},
        visualizers: {},
        fileName: null,
        pluginName: null,
        doc: {
            heading: document.getElementById(prefix + "heading"),
            displayClose: document.getElementById(prefix + "fileclose"),
            fileName: document.getElementById(prefix + "filename"),
            fileDisplay: document.getElementById(prefix + "filedisplay"),
            fileDetails: document.getElementById(prefix + "filedetails"),
            outputFileHeadline: document.getElementById(prefix + "outputFileHeadline")
        },
        plotDescription: null,
        plotFiles: new Array(),
        filesTable: {},
        // Used for determining what graph (if any) to show by default
        metadataToParse: 0,
        metadataParsed: 0,
        defaultViz: null,
        defaultVizCount: 0,
        // State for figuring out whether we're comparing multiple protocols on a single model, or multiple models on a single protocol
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
    }

downloads = [];
filename_plugin = $(`#${prefix}entityIdsToCompare`).val().replace(/^.*show\//,'').split('/');
graphGlobal[prefix]['fileName'] = filename_plugin[0];
graphGlobal[prefix]['pluginName'] = filename_plugin[1];
basicurl = $(`#${prefix}entityIdsToCompare`).val().replace(/show\/.*$/, '');
$(plugins).each(function(i, plugin) {
    graphGlobal[prefix]['visualizers'][plugin.name] = plugin.get_visualizer(prefix);
});

info = $.ajax({url: $(`#${prefix}entitiesStorygraph`).data('comparison-href'), dataType: "json", context: {csv_cache, downloads}, async: false})
               .done((data) => {
                   $.each(data.getEntityInfos.entities, (_, entity) => {
                       // parse entities (but don't build yet)
                       parseEntities(data.getEntityInfos.entities, prefix);
                       //get & save data
                       file_url = entity.download_url.replace('archive', 'download/') + graphGlobal[prefix]['fileName'] ;
                       if(csv_cache[file_url] == undefined){
                           var context_object = {url: file_url};
                           data_dld = $.ajax({url: file_url,
                                              context: context_object,
                                              success: function(data){
                                                   file = {url: this.url, contents: data};
                                                   expt_common.getCSV(file);
                                                   csv_cache[this.url] = file;
                                              }})
                                          .fail(() => {
                                              $(`#${prefix}filedetails`).append(`ERROR loding data: ${file_url}`);
                                          });
                           downloads.push(data_dld);
                       }
                   })
               })
               .fail(() => {
                 $(`#${prefix}filedetails`).append("ERROR retreiving graph info");
               });

    downloads.push(info);
    $.when.apply($, downloads).then(() => {
        buildSite(prefix);
    });
}

// initialise (all) compare graphs on the page
$(document).ready(function() {
  $(".entitiesStorygraph").each(function() {
      prefix = $(this).attr('id').replace("entitiesStorygraph", "");
      initGraph(prefix);
  });
});

// export the initCompare function so stories can create comparisson graph
module.exports = {
  initGraph: initGraph
}
