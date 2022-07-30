var utils = require('./lib/utils.js');
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

    file.downsampled = [[], []];
    file.nonDownsampled = file.downsampled;
    data = data.trim().split('\n');
    // check whether we need to downsample the data
    if(file.linestyle == undefined || (file.linestyle != "linespoints" && file.linestyle != "points")){
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
        for(let i = 0; i < data.length; ++i){
            data[i] = data[i].split(',').map(Number);
            file.nonDownsampled[1].push({x: data[i][0], y: data[i][1]});
        }
    }
}


/**
* callback function to signal to plugin that contents were retrieved.
*/
function getContentsCall(graphFiles, data_dld, prefix, callBack) {
    data_dld.done((data) => {
        for (var i = 0; i < graphFiles.entities.length; i++) {
            if(!graph['cancelling']){
                callBack.getContentsCallback(true, prefix);
            }
        }
    });
};

/**
 * Process information to set axes lables & units.
 */
function processAxes(graph){
    if(graph['outputs-default-plots.csv'].length > 1 && graph['outputs-contents.csv'].length > 1){
        default_header_as_arr = Array.from(graph['outputs-default-plots.csv'][0]);
        data_file_name_idx = default_header_as_arr.indexOf('Data file name');
        line_style_idx = default_header_as_arr.indexOf('Line style');
        first_var_id =  default_header_as_arr.indexOf('First variable id');
        second_var_id = default_header_as_arr.indexOf('Optional second variable id');
        var first_var = undefined;
        var second_var = undefined;
        var line_style = undefined;
        for(let i=1; i< graph['outputs-default-plots.csv'].length; i++){
            if(graph['outputs-default-plots.csv'][i][data_file_name_idx] == graph['fileName']){
                first_var = graph['outputs-default-plots.csv'][i][first_var_id];
                second_var = graph['outputs-default-plots.csv'][i][second_var_id];
                line_style = graph['outputs-default-plots.csv'][i][line_style_idx];
            }
        }
        contents_header_as_arr = Array.from(graph['outputs-contents.csv'][0]);
        var_id_idx = contents_header_as_arr.indexOf('Variable id');
        var_name_idx = contents_header_as_arr.indexOf('Variable name');
        units_idx = contents_header_as_arr.indexOf('Units');
        for(let i=1; i< graph['outputs-contents.csv'].length; i++){
            variable = graph['outputs-contents.csv'][i][var_name_idx];
            units = graph['outputs-contents.csv'][i][units_idx];
            if(graph['outputs-contents.csv'][i][var_id_idx] == first_var){
                for(sig of Object.keys(graph['files'])){
                    graph['files'][sig].xAxes = `${variable} (${units})`;
                    graph['files'][sig].xUnits = units;
                    graph['files'][sig].linestyle = line_style;
                }
            }
            if(graph['outputs-contents.csv'][i][var_id_idx] == second_var){
                for(sig of Object.keys(graph['files'])){
                    graph['files'][sig].yAxes = `${variable} (${units})`;
                    graph['files'][sig].yUnits = units;
               }
            }
        }
    }
}

/**
* Show the graph using the plugin.
*/
function showGraph(graph, prefix){
    $.when.apply($, graph['download_requests']).done(() => {
        if(!graph['cancelling']  && graph === graphGlobal[prefix]){
            processAxes(graph);
            graph['shown'] = true;
            var id = graph['fileName'].hashCode();
            var f = graph['files'][id];
            var pluginName = graph['pluginName'];
            if (!f.div[pluginName]) {
                f.div[pluginName] = $('<div/>').get(0);
                f.viz[pluginName] = graph['visualizers'][pluginName].setUpComparision(f, f.div[pluginName]);
            }

            $(graph['fileDisplay']).empty();
            graph['fileDisplay'].append(f.div[pluginName]);

            f.viz[pluginName].show();
        }
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
            showGraph(graphGlobal[prefix], prefix);
        }
    }
}

/**
* If we have an old graph, this canceles the old graph's ajax requetsts and returns plugin name
*/
function cancelGraph(prefix){
    old_graph = graphGlobal[prefix];
    // cancel old graph loading
    if(old_graph != undefined  && !old_graph['shown'] && old_graph['download_requests'] != undefined){
        old_graph['cancelling'] = true;
        for(req of graphGlobal[prefix]['download_requests']){
            req.abort();
        }
    }
    return old_graph
}

/**
* initialise graph, download & parse its contents, and show it
*/
function initGraph(prefix) {
    old_graph = cancelGraph(prefix);
    
    filename_plugin = $(`#${prefix}entityIdsToCompare`).val().replace(/^.*show\//,'').split('/');
    graph = {
        shown: false,
        cancelling: false,
        pluginName: (old_graph != undefined && old_graph['pluginName'] != undefined) ? old_graph['pluginName']: filename_plugin[1],
        fileName: filename_plugin[0],
        download_requests: [],
        entities: {},
        files: {},
        visualizers: {},
        div: {},
        fiz: {},
        fileDisplay: $(`<div id="#${prefix}filedisplay">loading...</div>`)
    }
    $(`#${prefix}filedisplay`).empty();
    $(`#${prefix}filedisplay`).append(graph.fileDisplay);
    
    $(plugins).each(function(i, plugin) {
        graph.visualizers[plugin.name] = plugin.get_visualizer(prefix);
    });

    info_url = $(`#${prefix}entitiesStorygraph`).data('comparison-href');
    var context_obj = {prefix, prefix, graph: graph, info_url: info_url};
    info = $.ajax({url: info_url,
                   dataType: "json",
                   context: context_obj,
                   success: function(data){
                       this.graph.fileDisplay.append('.');
                       $.each(data.getEntityInfos.entities, (_, entity) => {
                           // parse entities (but don't build yet)
                           entity.plotName = entity.modelName;

                            // Fill in the entities and files entries for this entity
                            this.graph.entities[entity.id] = entity;
                            if (entity.files){
                                for (var j = 0; j < entity.files.length; j++) {
                                    var file = entity.files[j];
                                    var sig = file.name.hashCode();
                                    var context_object = {file: file, graph: this.graph};
                                    if(file.name == 'outputs-contents.csv' || file.name == 'outputs-default-plots.csv'){
                                        if(this.graph[file.name] == undefined){ // only retreive once when processing multiple models
                                            outputs_dld =  $.ajax({url: file.url,
                                                                   context: context_object,
                                                                   success: function(data){
                                                                       this.graph[this.file.name] = utils.parseCsvDataRaw(data);
                                                                   },
                                                                   error: function(){
                                                                       if(!this.graph['cancelling']){
                                                                           this.graph.fileDisplay.append(`ERROR loading outputs-contents: ${this.file.url}`);
                                                                       }
                                                                   }});
                                            this.graph.download_requests.push(outputs_dld);
                                        }
                                    }else if(file.name == this.graph.fileName){
                                        file.signature = sig;
                                        file.type = file.filetype;
                                        this.graph.files[sig] = {};
                                        this.graph.files[sig].sig = sig;
                                        this.graph.files[sig].name = file.name;
                                        this.graph.files[sig].entities = new Array();
                                        this.graph.files[sig].div = {};
                                        this.graph.files[sig].viz = {};
                                        this.graph.files[sig].hasContents = true;
                                        this.graph.files[sig].id = this.prefix + file.name;
                                        this.graph.files[sig].entities.push({
                                            entityLink: entity,
                                            entityFileLink: file
                                        });
                                        this.graph.fileDisplay.append('.');
                                        data_dld = $.ajax({url: file.url,
                                                           context: context_object,
                                                           success: function(data){
                                                               this.graph.fileDisplay.append('.');
                                                               parseData(this.file, data)
                                                               this.graph.fileDisplay.append('.');
                                                           },
                                                           error: function(){
                                                               if(!this.graph['cancelling']){
                                                                   this.graph.fileDisplay.append(`ERROR loading data: ${this.file.url}`);
                                                               }
                                                           }});
                                        this.graph.download_requests.push(data_dld);
                                        //set-up plug-in callback to signal data was retrieved
                                        this.graph.files[sig].getContents = getContentsCall.bind(null, this.graph.files[sig], data_dld, this.prefix);
                                    }
                                }
                            }
                       });
                       showGraph(this.graph, this.prefix);
                   },
                   error: function(){
                       if(!this.graph['cancelling']){
                           this.graph.fileDisplay.append(`ERROR loading info: ${this.info_url}`);
                       }
                   }});
    graph['download_requests'].push(info);
    graphGlobal[prefix] = graph;
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
    reloadGraph: reloadGraph,
    cancelGraph: cancelGraph
}
