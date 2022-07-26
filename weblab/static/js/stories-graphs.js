var notifications = require('./lib/notifications.js');
var utils = require('./lib/utils.js');
var expt_common = require('./expt_common.js');

var plugins = [
    require('./visualizers/displayPlotFlot/displayPlotFlot.js'),
    require('./visualizers/displayPlotHC/displayPlotHC.js'),
];

var graphGlobal = {};

function displayFile(id, prefix) {
$(graphGlobal[prefix]['fileDisplay']).empty();
    var f = graphGlobal[prefix]['files'][id];
    var pluginName = graphGlobal[prefix]['pluginName'];
    if (!f.div[pluginName]) {
        f.div[pluginName] = $('<div/>').get(0);
        f.viz[pluginName] = graphGlobal[prefix]['visualizers'][pluginName].setUpComparision(f, f.div[pluginName]);
    }

    $(graphGlobal[prefix]['fileDisplay']).empty();
    graphGlobal[prefix]['fileDisplay'].append(f.div[pluginName]);

    f.viz[pluginName].show();
}

function showGraph(prefix){
    displayFile(graphGlobal[prefix]['fileName'].hashCode(), prefix);
}

function reloadGraph(prefix, pluginName){
    graphGlobal[prefix]['pluginName'] = pluginName;
    showGraph(prefix);
}

function initGraph(prefix) {
console.log('start init');
    graphGlobal[prefix] = {
        entities: {}, // Contains information about each experiment being compared
        files: {},
        visualizers: {},
        fileName: null,
        pluginName: null,
        fileDisplay: $(`#${prefix}filedisplay`),
    }

    downloads = [];
    filename_plugin = $(`#${prefix}entityIdsToCompare`).val().replace(/^.*show\//,'').split('/');
    graphGlobal[prefix]['fileName'] = filename_plugin[0];
    graphGlobal[prefix]['pluginName'] = filename_plugin[1];
    basicurl = $(`#${prefix}entityIdsToCompare`).val().replace(/show\/.*$/, '');
    $(plugins).each(function(i, plugin) {
        graphGlobal[prefix]['visualizers'][plugin.name] = plugin.get_visualizer(prefix);
    });
console.log('start loading data');
    info = $.ajax({url: $(`#${prefix}entitiesStorygraph`).data('comparison-href'), dataType: "json", context: {downloads}, async: false})
                   .done((data) => {
console.log('received info data');
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
                                            graphGlobal[prefix]['files'][sig].hasContents = true;
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
                                        var context_object = {file: file};
console.log('get contents');
                                        data_dld = $.ajax({url: download_url,
                                                           context: context_object,
                                                           success: function(data){
                                                                        this.file.contents = data;
                                                                        expt_common.getCSV(this.file);
                                                                        this.file.contents = undefined; // free up memory
                                                                        $(`#${prefix}filedisplay`).append('.');
console.log('got contents');
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
console.log('got all data');
        showGraph(prefix);
console.log('finished setting up graph');
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
    initGraph: initGraph,
    reloadGraph: reloadGraph
}
