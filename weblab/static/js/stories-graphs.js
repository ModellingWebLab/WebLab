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
    var sig = graph.fileName.hashCode();
    if(graph.files[sig] != undefined && graph.files[sig]['first_var'] != undefined && graph.files[sig]['axes_csv'] != undefined){
        for(let i=1; i< graph.files[sig]['axes_csv'].length; i++){
            variable_id = graph.files[sig]['axes_csv'][i][graph.files[sig]['var_id_idx']];
            var_name_idx = contents_header_as_arr.indexOf('Variable name');
            variable = graph.files[sig]['axes_csv'][i][var_name_idx];
            units = graph.files[sig]['axes_csv'][i][graph.files[sig]['units_idx']];
            if(variable_id == graph.files[sig]['first_var']){
                graph.files[sig].xAxes = `${variable} (${units})`;
                graph.files[sig].xUnits = units;
            }
            if(variable_id == graph.files[sig]['second_var']){
                graph['files'][sig].yAxes = `${variable} (${units})`;
                graph['files'][sig].yUnits = units;
            }
        }
        // no need to process other instanes of axes info for the other models
        if(graph['files'][sig].xAxes != undefined && graph['files'][sig].yAxes != undefined){
            for(req of graph.axes_info_requests){
                req.abort();
            }
            graph.files[sig]['axes_csv'] = undefined; // free memory
        }
    }
}

/**
* Show the graph using the plugin.
*/
function showGraph(graph, prefix){
    $.when.apply($, graph['download_requests']).done(() => {
        $.when.apply($, graph['axes_info_requests']).always(() => {
            if(!graph['cancelling']  && graph === graphGlobal[prefix]){
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
        axes_info_requests: [],
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
                                      var sig = this.graph.fileName.hashCode();

                                    if(this.graph.files[sig] == undefined){
                                        this.graph.files[sig] = {};
                                        this.graph.files[sig].sig = sig;
                                        this.graph.files[sig].entities = new Array();
                                        this.graph.files[sig].div = {};
                                        this.graph.files[sig].viz = {};
                                        this.graph.files[sig].hasContents = true;
                                    }
                                    var context_object = {file: file, graph: this.graph, sig: sig};
                                    if(file.name == 'outputs-default-plots.csv'){
                                        outputs_dld =  $.ajax({url: file.url,
                                                               context: context_object,
                                                               success: function(data){
                                                                   csv = utils.parseCsvDataRaw(data);
                                                                   default_header_as_arr = Array.from(csv[0]);
                                                                   data_file_name_idx = default_header_as_arr.indexOf('Data file name');
                                                                   line_style_idx = default_header_as_arr.indexOf('Line style');
                                                                   first_var_id =  default_header_as_arr.indexOf('First variable id');
                                                                   second_var_id = default_header_as_arr.indexOf('Optional second variable id');
                                                                   for(let i=1; i< csv.length; i++){
                                                                       if(csv[i][data_file_name_idx] == this.graph['fileName']){
                                                                           this.graph.files[this.sig]['first_var'] = csv[i][first_var_id];
                                                                           this.graph.files[this.sig]['second_var'] = csv[i][second_var_id];
                                                                           this.graph.files[this.sig]['line_style'] = csv[i][line_style_idx];
                                                                      }
                                                                   }
                                                                   processAxes(this.graph);
                                                               },
                                                               error: function(){
                                                                   if(!this.graph['cancelling'] && this.graph.files[this.sig].xAxes == undefined){
                                                                       this.graph.fileDisplay.append(`ERROR loading outputs-contents: ${this.file.url}`);
                                                                   }
                                                               }});
                                            this.graph.axes_info_requests.push(outputs_dld);
                                    }else if(file.name == 'outputs-contents.csv'){
                                        outputs_dld =  $.ajax({url: file.url,
                                                               context: context_object,
                                                               success: function(data){
                                                                   this.graph.files[this.sig]['axes_csv'] = utils.parseCsvDataRaw(data);
                                                                   contents_header_as_arr = Array.from(this.graph.files[this.sig]['axes_csv'][0]);
                                                                   this.graph.files[this.sig]['var_id_idx'] = contents_header_as_arr.indexOf('Variable id');
                                                                   this.graph.files[this.sig]['var_name_idx'] = contents_header_as_arr.indexOf('Variable name');
                                                                   this.graph.files[this.sig]['units_idx'] = contents_header_as_arr.indexOf('Units');
                                                                   processAxes(this.graph);
                                                               },
                                                               error: function(){
                                                                   if(!this.graph['cancelling'] && this.graph.files[this.sig].xAxes == undefined){
                                                                       this.graph.fileDisplay.append(`ERROR loading outputs-contents: ${this.file.url}`);
                                                                   }
                                                               }});
                                        this.graph.axes_info_requests.push(outputs_dld);
                                    }else if(file.name == this.graph.fileName){
                                        file.signature = sig;
                                        file.type = file.filetype;
                                        this.graph.files[sig].name = file.name;
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
