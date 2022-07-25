var notifications = require('./lib/notifications.js');
var utils = require('./lib/utils.js');
var expt_common = require('./expt_common.js');
//var csv_cache = {};

var plugins = [
    require('./visualizers/displayPlotFlot/displayPlotFlot.js'),
    require('./visualizers/displayPlotHC/displayPlotHC.js'),
];

var graphGlobal = {};

function displayFile(id, pluginName, prefix) {
    var f = graphGlobal[prefix]['files'][id];
    if (!f.div[pluginName]) {
        f.div[pluginName] = document.createElement("div");
        f.viz[pluginName] = graphGlobal[prefix]['visualizers'][pluginName].setUpComparision(f, f.div[pluginName]);
    }
    $(graphGlobal[prefix]['doc'].fileDisplay).empty();
    graphGlobal[prefix]['doc'].fileDisplay.appendChild(f.div[pluginName]);
    f.viz[pluginName].show();
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
    info = $.ajax({url: $(`#${prefix}entitiesStorygraph`).data('comparison-href'), dataType: "json", context: {downloads}, async: false})
                   .done((data) => {
                       $(`#${prefix}filedisplay`).append('.');
                       $.each(data.getEntityInfos.entities, (_, entity) => {
                           // parse entities (but don't build yet)
                           entity.plotName = entity.modelName;

                            // Fill in the entities and files entries for this entity
                            graphGlobal[prefix]['entities'][entity.id] = entity;
                            if (entity.files){
                                for (var j = 0; j < entity.files.length; j++) {
                                    var file = entity.files[j];
                                    if(file.name == graphGlobal[prefix]['fileName']){
                                        var sig = file.name.hashCode();
                                        file.signature = sig;
                                        file.type = file.filetype;
                                        if (!graphGlobal[prefix]['files'][sig]) {
                                            graphGlobal[prefix]['files'][sig] = {};
                                            graphGlobal[prefix]['files'][sig].sig = sig;
                                            graphGlobal[prefix]['files'][sig].name = file.name;
                                            graphGlobal[prefix]['files'][sig].entities = new Array();
                                            graphGlobal[prefix]['files'][sig].div = {};
                                            graphGlobal[prefix]['files'][sig].viz = {};
                                            graphGlobal[prefix]['files'][sig].hasContents = true; //false;
                                            graphGlobal[prefix]['files'][sig].id = prefix + file.name;

                                            //getContents method should just call callback, as we will seperately pre-download contents
                                           graphGlobal[prefix]['files'][sig].getContents = function(callBack, pref = prefix) {
                                               for (var i = 0; i < graphGlobal[prefix]['files'][sig].entities.length; i++) {
                                                   callBack.getContentsCallback(true, pref);
                                               }
                                           };

                                        }
                                        graphGlobal[prefix]['files'][sig].entities.push({
                                            entityLink: entity,
                                            entityFileLink: file
                                        });
                                        $(`#${prefix}filedisplay`).append('.');
                                        download_url = entity.download_url.replace('archive', 'download/') + graphGlobal[prefix]['fileName'] ;
                                        var context_object = {url: download_url, file: file};
                                        data_dld = $.ajax({url: download_url,
                                                           context: context_object,
                                                           success: function(data){
                                                                        this.file.contents = data;
                                                                        expt_common.getCSV(this.file);
                                                                        $(`#${prefix}filedisplay`).append('.');
                                                          }})
                                                          .fail(() => {
                                                              $(`#${prefix}filedetails`).append(`ERROR loding data: ${file_url}`);
                                                          });
                                        downloads.push(data_dld);
                                    }
                                }
                            }
                       });
                   });

    downloads.push(info);
    $.when.apply($, downloads).then(() => {
        displayFile(graphGlobal[prefix]['fileName'].hashCode(), graphGlobal[prefix]['pluginName'], prefix);
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
