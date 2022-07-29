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

    data = data.trim().split('\n');
    // check whether we need to downsample the data
    if(file.linestyle == undefined || (file.linestyle != "linespoints" && file.linestyle != "points")){
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
function getContentsCall(graphFiles, prefix, callBack) {
    for (var i = 0; i < graphFiles.entities.length; i++) {
        $.when.apply($, graphGlobal[prefix]['download_requests']).done(() => {
            if(!graphGlobal[prefix]['cancelling']){
                callBack.getContentsCallback(true, prefix);
            }
        });
    }
};

/**
 * Process information to set axes lables & units.
 */
function processAxes(prefix){
    if(graphGlobal[prefix]['outputs-default-plots.csv'].length > 1 && graphGlobal[prefix]['outputs-contents.csv'].length > 1){
        default_header_as_arr = Array.from(graphGlobal[prefix]['outputs-default-plots.csv'][0]);
        data_file_name_idx = default_header_as_arr.indexOf('Data file name');
        line_style_idx = default_header_as_arr.indexOf('Line style');
        first_var_id =  default_header_as_arr.indexOf('First variable id');
        second_var_id = default_header_as_arr.indexOf('Optional second variable id');
        var first_var = undefined;
        var second_var = undefined;
        var line_style = undefined;
        for(let i=1; i< graphGlobal[prefix]['outputs-default-plots.csv'].length; i++){
            if(graphGlobal[prefix]['outputs-default-plots.csv'][i][data_file_name_idx] == graphGlobal[prefix]['fileName']){
                first_var = graphGlobal[prefix]['outputs-default-plots.csv'][i][first_var_id];
                second_var = graphGlobal[prefix]['outputs-default-plots.csv'][i][second_var_id];
                line_style = graphGlobal[prefix]['outputs-default-plots.csv'][i][line_style_idx];
            }
        }
        contents_header_as_arr = Array.from(graphGlobal[prefix]['outputs-contents.csv'][0]);
        var_id_idx = contents_header_as_arr.indexOf('Variable id');
        var_name_idx = contents_header_as_arr.indexOf('Variable name');
        units_idx = contents_header_as_arr.indexOf('Units');
        for(let i=1; i< graphGlobal[prefix]['outputs-contents.csv'].length; i++){
            variable = graphGlobal[prefix]['outputs-contents.csv'][i][var_name_idx];
            units = graphGlobal[prefix]['outputs-contents.csv'][i][units_idx];
            if(graphGlobal[prefix]['outputs-contents.csv'][i][var_id_idx] == first_var){
                for(sig of Object.keys(graphGlobal[prefix]['files'])){
                    graphGlobal[prefix]['files'][sig].xAxes = `${variable} (${units})`;
                    graphGlobal[prefix]['files'][sig].xUnits = units;
                    graphGlobal[prefix]['files'][sig].linestyle = line_style;
                }
            }
            if(graphGlobal[prefix]['outputs-contents.csv'][i][var_id_idx] == second_var){
                for(sig of Object.keys(graphGlobal[prefix]['files'])){
                    graphGlobal[prefix]['files'][sig].yAxes = `${variable} (${units})`;
                    graphGlobal[prefix]['files'][sig].yUnits = units;
               }
            }
        }
    }
}

/**
* Show the graph using the plugin.
*/
function showGraph(prefix){
    $.when.apply($, graphGlobal[prefix]['download_requests']).done(() => {
        if(!graphGlobal[prefix]['cancelling']){
            processAxes(prefix);
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
            showGraph(prefix);
        }
    }
}

/**
* initialise graph, download & parse its contents, and show it
*/
function initGraph(prefix) {
console.log('init');
    filename_plugin = $(`#${prefix}entityIdsToCompare`).val().replace(/^.*show\//,'').split('/');
    if(graphGlobal[prefix] == undefined){
        graphGlobal[prefix] = {pluginName: filename_plugin[1], shown: false};
    }else if(graphGlobal[prefix]['download_requests'] != undefined){
        graphGlobal[prefix]['cancelling'] = true;
        for(req of graphGlobal[prefix]['download_requests']){
            req.abort();
        }
        graphGlobal[prefix]['cancelling'] = false;
//        $.when.apply($, graphGlobal[prefix]['download_requests']).fail(() => {
//            console.log('aborted');
//            graphGlobal[prefix]['cancelling'] = false;
//        });
    }
    graphGlobal[prefix]['cancelling'] = false;
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
                                    var sig = file.name.hashCode();
                                    var context_object = {file: file, prefix: this.prefix};
                                    if(file.name == 'outputs-contents.csv' || file.name == 'outputs-default-plots.csv'){
                                        if(graphGlobal[prefix][file.name] == undefined){ // only retreive once when processing multiple models
                                            outputs_dld =  $.ajax({url: file.url,
                                                                   context: context_object,
                                                                   success: function(data){
                                                                       graphGlobal[this.prefix][this.file.name] = utils.parseCsvDataRaw(data);
                                                                   },
                                                                   error: function(){
                                                                       if(!graphGlobal[this.prefix]['cancelling']){
                                                                           $(`#${this.prefix}filedetails`).append(`ERROR loding outputs-contents: ${this.file.url}`);
                                                                       }
                                                                   }});
                                            graphGlobal[this.prefix]['download_requests'].push(outputs_dld);
                                        }
                                    }else if(file.name == graphGlobal[this.prefix]['fileName']){
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
                                        var context_object = {file: file, prefix: this.prefix};
                                        data_dld = $.ajax({url: file.url,
                                                           context: context_object,
                                                           success: function(data){
                                                               $(`#${this.prefix}filedisplay`).append('.');
                                                               parseData(this.file, data)
                                                               $(`#${this.prefix}filedisplay`).append('.');
                                                           },
                                                           error: function(){
                                                               if(!graphGlobal[this.prefix]['cancelling']){
                                                                   $(`#${this.prefix}filedetails`).append(`ERROR loding data: ${this.file.url}`);
                                                               }
                                                           }});
                                        graphGlobal[this.prefix]['download_requests'].push(data_dld);
                                    }
                                }
                            }
                       });
                       showGraph(this.prefix);
                   },
                   error: function(){
                       if(!graphGlobal[this.prefix]['cancelling']){
                           $(`#${this.prefix}filedetails`).append(`ERROR loding info: ${this.info_url}`);
                       }
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

