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
* callback frunction to signal to plugin that contents were retreived.
*/
function getContentsCall(graphFiles, pref, callBack) {
    for (var i = 0; i < graphFiles.entities.length; i++) {
        callBack.getContentsCallback(true, pref);
    }
};

/**
* Show the graph using the plugin.
*/
function showGraph(prefix){
    $.when.apply($, graphGlobal[prefix]['download_requests']).then(() => {
        graphGlobal[prefix]['shown'] = true;
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
    });
}

/**
* Change the plugin name and reload the graph, if it has already been loaded
*/
function reloadGraph(prefix, pluginName){
    if(graphGlobal[prefix] == undefined){
        graphGlobal[prefix] = {pluginName: pluginName, shown: false};
    }else{
        graphGlobal[prefix]['pluginName'] = pluginName;
        if(graphGlobal[prefix]['shown']){
            showGraph(prefix);
        }
    }
}

/**
* initialise graph, download & parse its contents, and show it
*/
function initGraph(prefix) {
    filename_plugin = $(`#${prefix}entityIdsToCompare`).val().replace(/^.*show\//,'').split('/');
    if(graphGlobal[prefix] == undefined){
        graphGlobal[prefix] = {pluginName: filename_plugin[1], shown: false};
    }
    graphGlobal[prefix]['fileName'] = filename_plugin[0];
    graphGlobal[prefix]['download_requests'] = [];
    graphGlobal[prefix]['entities'] = {};
    graphGlobal[prefix]['files'] = {};
    graphGlobal[prefix]['visualizers'] = {};
    graphGlobal[prefix]['fileDisplay'] = $(`#${prefix}filedisplay`);
    $(plugins).each(function(i, plugin) {
        graphGlobal[prefix]['visualizers'][plugin.name] = plugin.get_visualizer(prefix);
    });

    info_url = $(`#${prefix}entitiesStorygraph`).data('comparison-href');
    var context_obj = {prefix: prefix, info_url: info_url};
    info = $.ajax({url: info_url,
                   dataType: "json",
                   context: context_obj,
                   prefix: prefix,
                   success: function(data){
                       $(`#${this.prefix}filedisplay`).append('.');
                       $.each(data.getEntityInfos.entities, (_, entity) => {
                           // parse entities (but don't build yet)
                           entity.plotName = entity.modelName;

                            // Fill in the entities and files entries for this entity
                            graphGlobal[this.prefix]['entities'][entity.id] = entity;
                            if (entity.files){
                                for (var j = 0; j < entity.files.length; j++) {
                                    var file = entity.files[j];
                                    if(file.name == graphGlobal[this.prefix]['fileName']){
                                        var sig = file.name.hashCode();
                                        file.signature = sig;
                                        file.type = file.filetype;
                                        if (!graphGlobal[this.prefix]['files'][sig]) {
                                            graphGlobal[this.prefix]['files'][sig] = {};
                                            graphGlobal[this.prefix]['files'][sig].sig = sig;
                                            graphGlobal[this.prefix]['files'][sig].name = file.name;
                                            graphGlobal[this.prefix]['files'][sig].entities = new Array();
                                            graphGlobal[this.prefix]['files'][sig].div = {};
                                            graphGlobal[this.prefix]['files'][sig].viz = {};
                                            graphGlobal[this.prefix]['files'][sig].hasContents = true;
                                            graphGlobal[this.prefix]['files'][sig].id = this.prefix + file.name;
                                            //set-up plug-in callback to signal data was retreived
                                            graphGlobal[this.prefix]['files'][sig].getContents = getContentsCall.bind(null, graphGlobal[this.prefix]['files'][sig], this.prefix);

                                        }
                                        graphGlobal[this.prefix]['files'][sig].entities.push({
                                            entityLink: entity,
                                            entityFileLink: file
                                        });
                                        $(`#${this.prefix}filedisplay`).append('.');
                                        download_url = entity.download_url.replace('archive', 'download/') + graphGlobal[this.prefix]['fileName'];
                                        var context_object = {file: file, prefix: this.prefix};
                                        data_dld = $.ajax({url: download_url,
                                                           context: context_object,
                                                           success: function(data){
                                                               $(`#${this.prefix}filedisplay`).append('.');
                                                               parseData(this.file, data)
                                                               $(`#${this.prefix}filedisplay`).append('.');
                                                           },
                                                           error: function(){
                                                               $(`#${this.prefix}filedetails`).append(`ERROR loding data: ${this.file.url}`);
                                                           }});
                                        graphGlobal[this.prefix]['download_requests'].push(data_dld);
                                    }
                                }
                            }
                       });
                       showGraph(this.prefix);
                   },
                   error: function(){
                       $(`#${this.prefix}filedetails`).append(`ERROR loding info: ${this.info_url}`);
                   }});
    graphGlobal[prefix]['download_requests'].push(info);
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
