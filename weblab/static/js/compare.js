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

function nextPage(url, replace, prefix)
{
    if (replace)
        window.history.replaceState(document.location.href, "", url);
    else
        window.history.pushState(document.location.href, "", url);
    parseUrl(null, prefix);
}

function registerFileDisplayer(elem, prefix)
{
    elem.addEventListener("click", function (ev, pref=prefix) {
        if (ev.which == 1)
        {
            ev.preventDefault();
            nextPage(elem.href, pref);
        }
    }, true);
}

/**
 * Add a `getContents` method to the file object f (a member of the global `files` collection) which will call
 * `utils.getFileContent` for the version of the file in each experiment being compared (but only on the first time
 * it is called).
 * @param f  the file
 */
function setupDownloadFileContents(f, prefix)
{
    f.getContents = function (callBack, pref=prefix)
    {
        if (f.hasContents)
            callBack.getContentsCallback (true, pref);
        f.hasContents = true;

        //console.log ("file appears in " + f.entities.length);
        for (var i = 0; i < f.entities.length; i++)
        {
            //console.log ("getting " + f.entities[i].entityFileLink.sig + " --> " + f.entities[i].entityFileLink.url);
            utils.getFileContent (f.entities[i].entityFileLink, callBack);
        }
    };
}

/**
 * Called when we have loaded both the default-plots and output-contents files for an experiment from the server.
 * Note that this will be called once per experiment being compared (at least, for those that have both metadata files).
 * @param entity  the experiment object
 * @param showDefault  whether to show a default visualisation (if available)
 */
function highlightPlots(entity, showDefault, prefix)
{
//    console.log(entity);
    // Plot description has fields: Plot title,File name,Data file name,Line style,First variable id,Optional second variable id,Optional key variable id
    // Output contents has fields: Variable id,Variable name,Units,Number of dimensions,File name,Type,Dimensions
    graphGlobal[prefix]['plotDescription'] = entity.plotDescription;
    outputContents = entity.outputContents;
    for (var i = 1 /* Skip first row - it's a header */; i < graphGlobal[prefix]['plotDescription'].length; i++)
    {
        if (graphGlobal[prefix]['plotDescription'][i].length < 3)
            continue;
        var data_file_code = graphGlobal[prefix]['plotDescription'][i][2].hashCode(),
            f = graphGlobal[prefix]['files'][data_file_code];
        if (f)
        {
            //console.log(f);

            // See if we should show this as the default plot.
            // If a single protocol, we choose the first listed in the default-plots file
            // (with the proviso that some experiments might have partial results, hence we need to check all default-plots files).
            // Otherwise, we choose the first one appearing in the most experiments.
            var row = document.getElementById("filerow-" + data_file_code);
            if (row)
            {
                if (showDefault)
                {
                    var viz = document.getElementById("filerow-" + data_file_code + "-viz-displayPlotFlot");
                    if (viz)
                    {
                        var thisCount = graphGlobal[prefix]['singleEntities'].protocol ? graphGlobal[prefix]['plotDescription'].length : f.entities.length;
                        if ((!graphGlobal[prefix]['singleEntities'].protocol || i == 1) && thisCount > graphGlobal[prefix]['defaultVizCount'])
                        {
//                            console.log("Set default viz to " + graphGlobal[prefix]['plotDescription'][i][0]);
                            graphGlobal[prefix]['defaultViz'] = viz;
                            graphGlobal[prefix]['defaultVizCount'] = thisCount;
                        }
                    }
                }
            }
            
            // Find the plot x and y object names and units from the output contents file.
            for (var output_idx = 0; output_idx < outputContents.length; output_idx++)
            {
                if (graphGlobal[prefix]['plotDescription'][i][4] == outputContents[output_idx][0])
                {
                    f.xAxes = outputContents[output_idx][1] + ' (' + outputContents[output_idx][2] + ')';
                    f.xUnits = outputContents[output_idx][2];
                }
                if (graphGlobal[prefix]['plotDescription'][i][5] == outputContents[output_idx][0])
                {
                    f.yAxes = outputContents[output_idx][1] + ' (' + outputContents[output_idx][2] + ')';
                    f.yUnits = outputContents[output_idx][2];
                }
                if (graphGlobal[prefix]['plotDescription'][i].length > 6 && graphGlobal[prefix]['plotDescription'][i][6] == outputContents[output_idx][0])
                {
                    // When comparing, f.entities is a list of the experiments containing this output data file (`entityLink`),
                    // and the version of the file appearing in each experiment (`entityFileLink`).
                    var key_file = graphGlobal[prefix]['files'][outputContents[output_idx][4].hashCode()],
                        ent_f = findEntityFileLink(f, entity, prefix); // This entity's version of f
                    if (ent_f && key_file)
                    {
                        var ent_key_file = findEntityFileLink(key_file, entity, prefix); // This entity's version of the key file
                        if (ent_key_file)
                        {
                            ent_f.keyId = outputContents[output_idx][0];
                            ent_f.keyName = outputContents[output_idx][1];
                            ent_f.keyUnits = outputContents[output_idx][2];
                            ent_f.keyFile = ent_key_file;
//                            console.log("Found key " + graphGlobal[prefix]['plotDescription'][i][6] + " for plot " + graphGlobal[prefix]['plotDescription'][i][0] + " entity " + entity.name);
                        }
                    }
                }
            }
            f.title = graphGlobal[prefix]['plotDescription'][i][0];
            f.linestyle = graphGlobal[prefix]['plotDescription'][i][3];
            
            graphGlobal[prefix]['plotFiles'].push (graphGlobal[prefix]['plotDescription'][i][2]);
        }
    }
    expt_common.sortTable (graphGlobal[prefix]['filesTable'], graphGlobal[prefix]['plotFiles']);
    // Show the default visualisation if this is the last experiment to be analysed
    if (graphGlobal[prefix]['defaultViz'] && graphGlobal[prefix]['metadataParsed'] == graphGlobal[prefix]['metadataToParse'])
    {
        nextPage(graphGlobal[prefix]['defaultViz'].href, true, prefix); // 'Invisible' redirect
    }
}

/**
 * Find the link to a particular entity's version of this file.
 * @param f  the file to look for
 * @param entity  the entity to look for
 * @returns  f.entities[ent_idx].entityFileLink where f.entities[ent_idx].entityLink === entity
 */
function findEntityFileLink(f, entity, prefix)
{
    for (var ent_idx=0; ent_idx<f.entities.length; ent_idx++)
        if (f.entities[ent_idx].entityLink === entity)
            return f.entities[ent_idx].entityFileLink;
}

function parseOutputContents (entity, file, showDefault, prefix)
{
    graphGlobal[prefix]['metadataToParse'] += 1;
    entity.outputContents = null; // Note that there is one to parse
    
    var goForIt = {
        getContentsCallback : function (succ, pref=prefix)
        {
            if (succ)
            {
                utils.parseCsvRaw(file);
                entity.outputContents = file.csv;
                graphGlobal[pref]['metadataParsed'] += 1;
                if (entity.plotDescription){
                    highlightPlots (entity, showDefault, pref);
                }
            }
        }
    };
    utils.getFileContent (file, goForIt);
    
    return null;
}

function parsePlotDescription (entity, file, showDefault, prefix)
{
    graphGlobal[prefix]['metadataToParse'] += 1;
    entity.plotDescription = null; // Note that there is one to parse
    
    var goForIt = {
        getContentsCallback : function (succ, pref=prefix)
        {
            if (succ)
            {
                utils.parseCsvRaw(file);
                entity.plotDescription = file.csv;
                graphGlobal[pref]['metadataParsed'] += 1;
                if (entity.outputContents){
                    highlightPlots (entity, showDefault, pref);
                }
            }
        }
    };
    utils.getFileContent (file, goForIt);
    
    return null;
}

function parseEntities(entityObj, prefix)
{
  if (entityObj.length == 0) return;
    //console.log (entityObj);

    // State for figuring out whether we're comparing multiple protocols on a single model, or multiple models on a single protocol,
    // or indeed multiple versions of the same model / protocol, etc.
    graphGlobal[prefix]['firstModelName'] = entityObj[0].modelName;
    graphGlobal[prefix]['firstModelVersion'] = entityObj[0].modelVersion;
    graphGlobal[prefix]['firstProtoName'] = entityObj[0].protoName;
    graphGlobal[prefix]['firstProtoVersion'] = entityObj[0].protoVersion;
    graphGlobal[prefix]['firstFittingSpecName'] = entityObj[0].fittingSpecName;
    graphGlobal[prefix]['firstFittingSpecVersion'] = entityObj[0].fittingSpecVersion;
    graphGlobal[prefix]['firstDatasetName'] = entityObj[0].datasetName;
    var versionsOfModels = {};
    var versionsOfProtocols = {};
    var versionsOfFittingSpecs ={};
    graphGlobal[prefix]['modelsWithMultipleVersions'] = [];
    graphGlobal[prefix]['protocolsWithMultipleVersions'] = [];
    graphGlobal[prefix]['fittingSpecsWithMultipleVersions'] = [];

    // Sort entityObj list by .name
    entityObj.sort(function(a,b) {return (a.name.toLocaleLowerCase() > b.name.toLocaleLowerCase()) ? 1 : ((b.name.toLocaleLowerCase() > a.name.toLocaleLowerCase()) ? -1 : 0);});

    for (var i = 0; i < entityObj.length; i++)
    {
        var entity = entityObj[i];

    if (graphGlobal[prefix]['singleEntities'].model && (entity.modelName != graphGlobal[prefix]['firstModelName'])) {
      graphGlobal[prefix]['singleEntities'].model = false;
    }

    if (versionsOfModels[entity.modelName] === undefined) {
      versionsOfModels[entity.modelName] = entity.modelVersion;
    } else if (versionsOfModels[entity.modelName] != entity.modelVersion) {
      graphGlobal[prefix]['modelsWithMultipleVersions'].push(entity.modelName);
      graphGlobal[prefix]['versionComparisons'].model = true;
    }

    if (graphGlobal[prefix]['singleEntities'].protocol && (entity.protoName != graphGlobal[prefix]['firstProtoName'])) {
      graphGlobal[prefix]['singleEntities'].protocol = false;
    }

    if (versionsOfProtocols[entity.protoName] === undefined) {
      versionsOfProtocols[entity.protoName] = entity.protoVersion;
    } else if (versionsOfProtocols[entity.protoName] != entity.protoVersion) {
      graphGlobal[prefix]['protocolsWithMultipleVersions'].push(entity.protoName);
      graphGlobal[prefix]['versionComparisons'].protocol = true;
    }

    if (graphGlobal[prefix]['singleEntities'].fittingspec && (entity.fittingSpecName != graphGlobal[prefix]['firstFittingSpecName'])) {
      graphGlobal[prefix]['singleEntities'].fittingspec = false;
    }

    if (versionsOfFittingSpecs[entity.fittingSpecName] === undefined) {
      versionsOfFittingSpecs[entity.fittingSpecName] = entity.fittingSpecVersion;
    } else if (versionsOfFittingSpecs[entity.fittingSpecName] != entity.fittingSpecVersion) {
      graphGlobal[prefix]['fittingSpecsWithMultipleVersions'].push(entity.fittingSpecName);
      graphGlobal[prefix]['versionComparisons'].fittingspec = true;
    }

    if (graphGlobal[prefix]['singleEntities'].dataset && (entity.datasetName != graphGlobal[prefix]['firstDatasetName'])) {
      graphGlobal[prefix]['singleEntities'].dataset = false;
    }

        // Fill in the entities and files entries for this entity
        graphGlobal[prefix]['entities'][entity.id] = entity;
        if (entity.files)
            for (var j = 0; j < entity.files.length; j++)
            {
                var file = entity.files[j],
                    sig = file.name.hashCode();
                file.signature = sig;
        file.type = file.filetype;
                if (!graphGlobal[prefix]['files'][sig])
                {
                    graphGlobal[prefix]['files'][sig] = {};
                    graphGlobal[prefix]['files'][sig].sig = sig;
                    graphGlobal[prefix]['files'][sig].name = file.name;
                    graphGlobal[prefix]['files'][sig].entities = new Array ();
                    graphGlobal[prefix]['files'][sig].div = {};
                    graphGlobal[prefix]['files'][sig].viz = {};
                    graphGlobal[prefix]['files'][sig].hasContents = false;
                    graphGlobal[prefix]['files'][sig].id = prefix + file.name;
                    setupDownloadFileContents(graphGlobal[prefix]['files'][sig], prefix);
                }
                if (file.name.toLowerCase () == "outputs-default-plots.csv")
                    parsePlotDescription (entity, file, !(graphGlobal[prefix]['fileName'] && graphGlobal[prefix]['pluginName']), prefix);
                if (file.name.toLowerCase () == "outputs-contents.csv")
                    parseOutputContents (entity, file, !(graphGlobal[prefix]['fileName'] && graphGlobal[prefix]['pluginName']), prefix);
                
                graphGlobal[prefix]['files'][sig].entities.push ({entityLink: entity, entityFileLink: file});
            }
    }

  console.log(graphGlobal[prefix]['singleEntities'].model ? 'single model' : 'multiple models',
              graphGlobal[prefix]['versionComparisons'].model ? ('- compare versions of ' + graphGlobal[prefix]['modelsWithMultipleVersions'].join(',')) : '');
  console.log(graphGlobal[prefix]['singleEntities'].protocol ? 'single protocol' : 'multiple protocols',
              graphGlobal[prefix]['versionComparisons'].protocol ? ('- compare versions of ' + graphGlobal[prefix]['protocolsWithMultipleVersions'].join(',')) : '');
  console.log(graphGlobal[prefix]['singleEntities'].fittingspec ? 'single fitting spec' : 'multiple fitting specs',
              graphGlobal[prefix]['versionComparisons'].fittingspec ? ('- compare versions of ' + graphGlobal[prefix]['fittingSpecsWithMultipleVersions'].join(',')) : '');
  console.log(graphGlobal[prefix]['singleEntities'].dataset ? 'single dataset' : 'multiple datasets')

  /*
  // TESTING / DEBUG of different combinations
  graphGlobal[prefix]['singleEntities'] = {
    model: false,
    protocol: false,
    fittingspec: false,
    dataset: false,
  };
  graphGlobal[prefix]['versionComparisons'] = {
    model: false,
    protocol: true,
    fittingspec: false,
    dataset: false
  };
  // END TESTING / DEBUG
  */

  var entityTypes = ['model', 'protocol'];
  if (graphGlobal[prefix]['entityType'] == 'result') entityTypes.push('fittingspec', 'dataset');

  var entityTypeDisplayStrings = {
    model: 'model',
    protocol: 'protocol',
    fittingspec: 'fitting spec',
    dataset: 'dataset',
  };

  // List of entity types which have multiple objects
  var entityTypesToCompare = entityTypes.filter(entityType => !graphGlobal[prefix]['singleEntities'][entityType]);

  // List of entity types which have multiple versions but not multiple objects
  var entityVersionsToCompare = entityTypes.filter(entityType => graphGlobal[prefix]['versionComparisons'][entityType] && graphGlobal[prefix]['singleEntities'][entityType]);
    
  // Add version info to plot labels where needed
  for (var i = 0; i < entityObj.length; i++)
  {
    var entity = entityObj[i];

    var modelDescription = entity.modelName + (graphGlobal[prefix]['modelsWithMultipleVersions'].includes(entity.modelName) ? ('@' + entity.modelVersion) : '');
    var protoDescription = entity.protoName + (graphGlobal[prefix]['protocolsWithMultipleVersions'].includes(entity.protoName) ? ('@' + entity.protoVersion) : '');
    var fitspecDescription = entity.fittingSpecName + (graphGlobal[prefix]['fittingSpecsWithMultipleVersions'].includes(entity.fittingSpecName) ? ('@' + entity.fittingSpecVersion) : '');
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
      if (entityVersionsToCompare.length== 0) {
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
  var pageTitle = "Comparison of " + graphGlobal[prefix]['entityType'].charAt(0).toUpperCase() + graphGlobal[prefix]['entityType'].slice(1) + "s";

  if (graphGlobal[prefix]['entityType'] == "experiment" || graphGlobal[prefix]['entityType'] == "result")
  {
    if (entityTypesToCompare.length == 0) {
      // All same entities, just possibly different versions of them
      pageTitle = graphGlobal[prefix]['firstModelName'] + " & " + graphGlobal[prefix]['firstProtoName'];
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
      pageTitle = graphGlobal[prefix]['singleEntities'].model ? graphGlobal[prefix]['firstModelName'] : graphGlobal[prefix]['firstProtoName'];
      pageTitle += " experiments : comparison of " + entityTypeDisplayStrings[entityTypesToCompare[0]] + "s";
      // If just one type of version comparison, be specific.
      // Otherwise, just say "versions"
      if (entityVersionsToCompare.length == 1) {
        pageTitle += " and " + entityTypeDisplayStrings[entityVersionsToCompare[0]] + " versions";
        // label: '<model name>@<model version>'
        // label: '<model name> & @<protocol version>'
      } else if (entityVersionsToCompare.length > 1){
        pageTitle += " and versions";
        // label: '<model name>@<model version> & @<protocol version>'
      }
      // } else { label: '<model name>' }
    } else if (entityTypesToCompare.length == 2){
      // Two types of entity comparisons
      // just list those and take the title from one of the other entity types
      var entityName;
      if (graphGlobal[prefix]['singleEntities'].model) {
        entityName = graphGlobal[prefix]['firstModelName'];
      } else if (graphGlobal[prefix]['singleEntities'].protocol) {
        entityName = graphGlobal[prefix]['firstProtoName'];
      } else if (graphGlobal[prefix]['firstFittingSpecName'] && graphGlobal[prefix]['singleEntities'].fittingspec) {
        entityName = graphGlobal[prefix]['firstFittingSpecName'];
      }
      if (entityName !== undefined) {
        pageTitle = entityName + " experiments: comparison of " + entityTypeDisplayStrings[entityTypesToCompare[0]] + "s and " + entityTypeDisplayStrings[entityTypesToCompare[1]] + "s";
      }
      // label: "<model name> & <protocol name>"
    // } else {
    // More than two entity comparisons (possibly multiple versions of each) - page title is default
    }
    if(graphGlobal[prefix]['doc'].heading){
        graphGlobal[prefix]['doc'].heading.innerHTML = pageTitle;
    }

    // This was used in an earlier version and is still expected to exist by plugins
    $.data(document.body, 'plotLabelStripText', '');
  }

    // Create a drop-down box that allows display of/navigate to experiments being compared
    var entitiesToCompare = document.getElementById(prefix + "entitiesToCompare");
        $(entitiesToCompare).empty();
        if(graphGlobal[prefix]['doc'].outputFileHeadline){
            graphGlobal[prefix]['doc'].outputFileHeadline.innerHTML = "Output files from all compared " + graphGlobal[prefix]['entityType'] + "s";
        var form = document.createElement("form");
        entitiesToCompare.appendChild(form);
        var select_box = document.createElement("select");
        select_box.name = "experiment_box";
        select_box.id = "exptSelect";
        var default_option = document.createElement("option");
        default_option.selected = true;
        default_option.value = document.location.href;
        default_option.innerHTML = "Click to view, select to show a single " + graphGlobal[prefix]['entityType'];
        select_box.onchange = function(){sel=document.getElementById("exptSelect"); console.log(sel); document.location.href = sel.options[sel.selectedIndex].value;};
            select_box.appendChild(default_option);
        for (var entity in graphGlobal[prefix]['entities'])
        {
            var option = document.createElement("option");
                    option.value = graphGlobal[prefix]['entities'][entity].url;
                    option.innerHTML = graphGlobal[prefix]['entities'][entity].name + ((graphGlobal[prefix]['entityType'] == "experiment" || graphGlobal[prefix]['entityType'] == "result") ? "" : " &mdash; " + graphGlobal[prefix]['entities'][entity].version);
            select_box.appendChild(option);
            }
            form.innerHTML = graphGlobal[prefix]['entityType'].charAt(0).toUpperCase() + graphGlobal[prefix]['entityType'].slice(1) + "s selected for comparison: ";
        form.appendChild(select_box);
        }

    buildSite(prefix);
}

function buildSite(prefix)
{
    var filestableElement = document.getElementById(prefix + "filestable");
    if(filestableElement)
    {
        graphGlobal[prefix]['filesTable'] = {};
        graphGlobal[prefix]['filesTable'].table = filestableElement;
        graphGlobal[prefix]['filesTable'].plots = {};
        graphGlobal[prefix]['filesTable'].pngeps = {};
        graphGlobal[prefix]['filesTable'].otherCSV = {};
        graphGlobal[prefix]['filesTable'].defaults = {};
        graphGlobal[prefix]['filesTable'].text = {};
        graphGlobal[prefix]['filesTable'].other = {};
        graphGlobal[prefix]['filesTable'].all = new Array ();

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

        for (var file in graphGlobal[prefix]['files'])
        {
            var ents = graphGlobal[prefix]['files'][file];
            var curFileName = ents.name;
            tr = document.createElement("tr");
            tr.id = "filerow-" + ents.sig;
            filestableElement.appendChild(tr);
            td = document.createElement("td");
            td.appendChild(document.createTextNode(curFileName + " ("+ents.entities.length+")"));
            tr.appendChild(td);

            graphGlobal[prefix]['filesTable'].all.push ({
                name: curFileName,
                row: tr
            });

            td = document.createElement("td");
            var size = 0;
            for (var i = 0; i < ents.entities.length; i++)
            {
                size += ents.entities[i].entityFileLink.size;
            }
            td.appendChild(document.createTextNode(utils.humanReadableBytes (size / ents.entities.length)));
            tr.appendChild(td);

            /*td = document.createElement("td");
            td.appendChild(document.createTextNode("action"));*/

            td = document.createElement("td");
            for (var vi in graphGlobal[prefix]['visualizers'])
            {
                var viz = graphGlobal[prefix]['visualizers'][vi];
                if (!viz.canRead (ents.entities[0].entityFileLink))
                    continue;
                var a = document.createElement("a");
                a.setAttribute("id", "filerow-" + file + "-viz-" + viz.getName ());
                a.href = basicurl + 'show/' + encodeURIComponent(graphGlobal[prefix]['files'][file].name) + "/" + vi;
                var img = document.createElement("img");
                img.src = staticPath + "js/visualizers/" + vi + "/" + viz.getIcon ();
                img.alt = viz.getDescription ();
                img.title = img.alt;
                a.appendChild(img);
                //a.appendChild(document.createTextNode ("view"));
                registerFileDisplayer(a, prefix);//, basicurl + convertForURL (v.name) + "/" + v.id + "/");
                td.appendChild(a);
                td.appendChild(document.createTextNode (" "));
            }
            tr.appendChild(td);
        }
    }
    handleReq(prefix);
}

function displayFile(id, pluginName, prefix)
{
    if (!graphGlobal[prefix]['gotInfos'])
        return;
    var f = graphGlobal[prefix]['files'][id];
    if (!f)
    {
        notifications.add("no such file", "error");
        return;
    }
    for (var ent_idx=0; ent_idx<f.entities.length; ent_idx++)
    {
        var entity = f.entities[ent_idx].entityLink;
        if (entity.outputContents === null || entity.plotDescription === null)
        {
            // Try again in 0.1s, by which time hopefully they have been parsed
            //console.log("Waiting for metadata to be parsed.");
            window.setTimeout(function(){displayFile(id, pluginName, prefix)}, 100);
            return;
        }
    }
        if(graphGlobal[prefix]['doc'].fileName){
            graphGlobal[prefix]['doc'].fileName.innerHTML = f.name;
        }
    
    if (!f.div[pluginName])
    {
//        console.log("Creating visualizer");
        f.div[pluginName] = document.createElement("div");
        f.viz[pluginName] = graphGlobal[prefix]['visualizers'][pluginName].setUpComparision (f, f.div[pluginName]);
//        console.log(f);
    }
//    else
//    {
//        console.log("Reusing vis");
//        console.log(f);
//    }
    $(graphGlobal[prefix]['doc'].fileDisplay).empty();
    graphGlobal[prefix]['doc'].fileDisplay.appendChild (f.div[pluginName]);
    f.viz[pluginName].show ();

    // Show parent div of the file display, and scroll there
    graphGlobal[prefix]['doc'].fileDetails.style.display = "block";
    var pos = utils.getPos (graphGlobal[prefix]['doc'].heading);
    if(graphGlobal[prefix]['scroll'])
    {
        window.scrollTo(pos.xPos, pos.yPos);
    }
}

function handleReq(prefix)
{
    if (graphGlobal[prefix]['fileName'] && graphGlobal[prefix]['pluginName'] && graphGlobal[prefix]['gotInfos'])
    {
        displayFile (graphGlobal[prefix]['fileName'].hashCode(), graphGlobal[prefix]['pluginName'], prefix);
                if(graphGlobal[prefix]['doc'].displayClose)
                {
                    graphGlobal[prefix]['doc'].displayClose.href = basicurl;
                }
    }
    else
    {
        graphGlobal[prefix]['doc'].fileDetails.style.display = "none";
    }
}

function getInfos(url, prefix)
{
  $.getJSON(url, function(data) {
    notifications.display(data);
    graphGlobal[prefix]['gotInfos'] = true;

    if (data.getEntityInfos) {
      parseEntities(data.getEntityInfos.entities, prefix);
    }
  })
}

function parseUrl(event, prefix)
{
    var entityIds = null;
        if($('#' + prefix + 'entityIdsToCompare').length){
            var parts = $('#' + prefix + 'entityIdsToCompare').val().split("/");
        }else{
            var parts = document.location.pathname.split("/");
        }

    for (var i = 0; i < parts.length; i++)
        {
            if (parts[i] == 'experiments')
            {
                basicurl = parts.slice(0, i+2).join('/') + '/';
                graphGlobal[prefix]['entityType'] = 'experiment';
                entityIds = parts.slice(i+2);
                break;
            }else if (parts[i] == 'results')
            {
                basicurl = parts.slice(0, i+2).join('/') + '/';
                graphGlobal[prefix]['entityType'] = 'result';
                entityIds = parts.slice(i+2);
            }else if (parts[i+1] == 'compare')
            {
                basicurl = parts.slice(0, i+2).join('/') + '/';
                graphGlobal[prefix]['entityType'] = parts[i].slice(0, parts[i].length-1);
                entityIds = parts.slice(i+2);
                break;
            }
        }

    if (!entityIds)
    {
        var entitiesToCompare = document.getElementById(prefix + "entitiesToCompare");
        $(entitiesToCompare).empty();
        entitiesToCompare.appendChild(document.createTextNode("ERROR building site"));
        return;
    }
    
    graphGlobal[prefix]['fileName'] = null;
    graphGlobal[prefix]['pluginName'] = null;
    var TentityIds = new Array ();
    
    
    for (var i = 0; i < entityIds.length; i++)
    {
        if (entityIds[i] == "show")
        {
            if (i + 2 < entityIds.length)
            {
                graphGlobal[prefix]['fileName'] = entityIds[i + 1];
                graphGlobal[prefix]['pluginName'] = entityIds[i + 2];
            }
            entityIds = entityIds.slice (0, i);
            break;
        }
        else if (entityIds[i])
            TentityIds.push (entityIds[i]);
    }
    entityIds = TentityIds;
    basicurl = basicurl + entityIds.join ("/") + "/";
    //console.log("basicurl" + basicurl);
    
    //console.log (graphGlobal[prefix]['entityType']);
    //console.log (entityIds);
    
    if (!graphGlobal[prefix]['tableParsed'])
    {
        graphGlobal[prefix]['tableParsed'] = true;
        getInfos ($("#" + prefix + "entitiesToCompare").data('comparison-href'), prefix);
    }
    else
        handleReq(prefix);
        
}

function initCompare(prefix, scroll=true)
{
    graphGlobal[prefix] = { entities: {}, // Contains information about each experiment being compared
                                          // `files` contains information about each unique (by name) file within the compared experiments,
                                          // including references to the experiments in which a file of that name appears and that particular instance of the file.
                            files: {},
                            entityType: null,
                            visualizers: {},
                            tableParsed: false,
                            fileName: null,
                            pluginName: null,
                            doc: { heading: document.getElementById(prefix + "heading"),
                                   displayClose: document.getElementById(prefix + "fileclose"),
                                   fileName: document.getElementById(prefix + "filename"),
                                   fileDisplay: document.getElementById(prefix + "filedisplay"),
                                   fileDetails: document.getElementById(prefix + "filedetails"),
                                   outputFileHeadline: document.getElementById(prefix + "outputFileHeadline")
                            },                            
                            gotInfos: false,
                            plotDescription: null,
                            plotFiles: new Array (),
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
                            singleEntities: {model: true,
                                             protocol: true,
                                             fittingspec: true,
                                             dataset: true,
                            },
                            versionComparisons: {model: false,
                                                 protocol: false,
                                                 fittingspec: false,
                                                 dataset: false,
                            },
                            scroll: scroll,
    }

    graphGlobal[prefix]['doc'].fileDetails.style.display = "none";

    // Prevent redirection to the default plot when we close it
        if(graphGlobal[prefix]['doc'].displayClose){
            graphGlobal[prefix]['doc'].displayClose.addEventListener("click", function (ev, pref=prefix) {
                if (ev.which == 1){
                    ev.preventDefault();
                    graphGlobal[pref]['doc'].fileDetails.style.display = "none";
                    shownDefault = true;
                    nextPage(graphGlobal[prefix]['doc'].displayClose.href, prefix);
                }
            }, true);
        }

        if(prefix == '')
        {
        window.onpopstate = parseUrl;
        }
    parseUrl(null, prefix);

    $(plugins).each(function(i, plugin) {
        graphGlobal[prefix]['visualizers'][plugin.name] = plugin.get_visualizer(prefix);
    });
}


$(document).ready(function() {
    $(".entitiesToCompare").each(function() {
       prefix = $(this).attr('id').replace("entitiesToCompare", "");
       initCompare(prefix, prefix == "");
    });

    /* Graph Preview functionality */
    // update graph preview if any of the controls change
    $(body).on('change', '.preview-graph-control', function() {
        // get prefix graph Id
        var match = $(this).attr("id").match(/^id_graph-([0-9]*)-.*$/)
        graphId = match[1];

        //set relevant css class for preview box size
        $('#'+ graphId +'graphPreviewBox').removeClass();
        $('#'+ graphId +'graphPreviewBox').addClass($('#id_graphvisualizer').val() + '-preview');

        if($('#id_graph-'+ graphId +'-update_1').is(':checked'))
        {
            experimentVersions = $('#id_graph-'+ graphId +'-experiment-versions').val();
            currentGraph = $('#id_graph-'+ graphId +'-currentGraph').val();
            currentGraphParts = currentGraph.split(' / ');
            graphFile = currentGraphParts[currentGraphParts.length - 1];
        }
        else
        {
            experimentVersions = $('#id_graph-'+ graphId +'-experimentVersionsUpdate').val();
            graphFile = $('#id_graph-'+ graphId +'-graphfiles').val();
        }
        if(experimentVersions != '/'){
            basePath = $(location).attr('pathname').replace(/stories.*/i, ''); // may be running in subfolder
            // compse url for ids for preview graph
            graphPathIds = basePath + '/experiments/compare/' + experimentVersions + '/show/' + graphFile + '/' + $('#id_graphvisualizer').val();
            // compse url for entities for preview graph
           graphPathEntities = basePath + '/experiments/compare/' + experimentVersions + '/info';
           $('#'+ graphId +'graphPreviewBox').html('<div class="graphPreviewDialog"><input type="hidden" id="'+ graphId +'entityIdsToCompare" value="' + graphPathIds + '"><div class="entitiesToCompare" id="'+ graphId +'entitiesToCompare" data-comparison-href="' + graphPathEntities + '">loading...</div><div id="' + graphId + 'filedetails" class="filedetails"><div id="'+ graphId + 'filedisplay"></div></div></div>');
           initCompare(graphId, false);
        }
        else
        {
            $('#'+ graphId +'graphPreviewBox').html('Please select a graph...');
        }


    });

    // update all graph previews if graph ype changes
    $('#id_graphvisualizer').change(function() {
        $('.graphfiles').each(function(){
            $(this).change();
        });
    });
});


