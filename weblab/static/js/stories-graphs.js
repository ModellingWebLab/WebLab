var notifications = require('./lib/notifications.js');
var utils = require('./lib/utils.js');
var expt_common = require('./expt_common.js');

var plugins = [
    require('./visualizers/displayPlotFlot/displayPlotFlot.js'),
    require('./visualizers/displayPlotHC/displayPlotHC.js'),
];

var graphGlobal = {};



/**
* Parse the (downsampled or unDownsampled) data for a file.
*/
function parseData(file, data){
    function maxDist (val1, val2, val3){
        return Math.max(val1, val2, val3) - Math.min(val1, val2, val3);
    }
    
    data = data.trim().split('\n');
    if(file.linestyle == undefined || (file.linestyle != "linespoints" && file.linestyle != "points")){// use downsampling
        file.downsampled = [[], []];
        var maxX = Number.NEGATIVE_INFINITY;
        var minX = Number.POSITIVE_INFINITY;
        var maxY = Number.NEGATIVE_INFINITY;
        var minY = Number.POSITIVE_INFINITY;
        for(let i = 0; i < data.length; ++i){
            data[i] = data[i].split(',').map(Number);
            maxX = Math.max(maxX, data[i][0]);
            minX = Math.min(minX, data[i][0]);
            maxY = Math.max(maxY, data[i][1]);
            minY = Math.min(minY, data[i][1]);
        }
        for(let i = 0; i < data.length; ++i){
            if(i==0 || i == data.length -1){
                file.downsampled[1].push({x: data[i][0], y: data[i][1]});
            }else{
                last = file.downsampled[1][file.downsampled[1].length -1];
                cur = data[i];
                next = data[i+1];
                if(i==0 || i == data.length -1 || maxDist(last.x, cur[0], next[0]) > (maxX - minX)/500.0 || maxDist(last.y, cur[1], next[1]) > (maxY - minY)/500.0 ){
                    file.downsampled[1].push({x: data[i][0], y: data[i][1]});
                }
            }
        }
    }else{
        file.nonDownsampled = [[], []];
        for(let i = 0; i < data.length; ++i){
            data[i] = data[i].split(',').map(Number);
            file.nonDownsampled[1].push({x: data[i][0], y: data[i][1]});
        }
    
    }
}

/**
* Show the graph using the plugin.
*/
function showGraph(prefix){
    var id = graphGlobal[prefix]['fileName'].hashCode();
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

/**
* Reload a graph that had already been loaded using plugin pluginName
*/
function reloadGraph(prefix, pluginName){
    graphGlobal[prefix]['pluginName'] = pluginName;
    showGraph(prefix);
}

/**
* initialise graph, download & parse its contents, and show it
*/
function initGraph(prefix) {
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
                                        data_dld = $.ajax({url: download_url,
                                                           context: context_object,
                                                           success: function(data){
                                                                        $(`#${prefix}filedisplay`).append('.');
                                                                        parseData(this.file, data)
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
        showGraph(prefix);
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
