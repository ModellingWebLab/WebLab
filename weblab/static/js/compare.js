var entities = {}, // Contains information about each experiment being compared
	// `files` contains information about each unique (by name) file within the compared experiments,
	// including references to the experiments in which a file of that name appears and that particular instance of the file.
	files = {},
	entityType,
	visualizers = {},
	tableParsed = false,
	fileName = null,
	pluginName = null,
	doc,
	gotInfos = false,
	plotDescription,
	plotFiles = new Array (),
	filesTable = {},
	// Used for determining what graph (if any) to show by default
	metadataToParse = 0, metadataParsed = 0, defaultViz = null, defaultVizCount = 0,
	// State for figuring out whether we're comparing multiple protocols on a single model, or multiple models on a single protocol
	firstModelName = "", firstModelVersion = "", firstProtoName = "", firstProtoVersion = "",
	singleModel = true, singleProto = true,
	// Used for stripping out redundant (repeated) text in plot line labels
	plotLabelStripText = null;


function getFileContent (file, succ)
{
	var xmlhttp = null;
    // !IE
    if (window.XMLHttpRequest)
    {
        xmlhttp = new XMLHttpRequest();
    }
    // IE -- microsoft, we really hate you. every single day.
    else if (window.ActiveXObject)
    {
        xmlhttp = new ActiveXObject("Microsoft.XMLHTTP");
    }
    
    xmlhttp.open("GET", file.url, true);

    xmlhttp.onreadystatechange = function()
    {
        if(xmlhttp.readyState != 4)
        	return;
    	
        if(xmlhttp.status == 200)
        {
        	file.contents = xmlhttp.responseText;
        	succ.getContentsCallback (true);
        }
        else
        	succ.getContentsCallback (false);
    };
    xmlhttp.send(null);
}

function nextPage (url, replace)
{
    if (replace)
        window.history.replaceState(document.location.href, "", url);
    else
        window.history.pushState(document.location.href, "", url);
    parseUrl ();
}

function registerFileDisplayer (elem)
{
	elem.addEventListener("click", function (ev) {
		if (ev.which == 1)
		{
			ev.preventDefault();
			nextPage (elem.href);
		}
    	}, true);
}

/**
 * Add a `getContents` method to the file object f (a member of the global `files` collection) which will call
 * `getFileContent` for the version of the file in each experiment being compared (but only on the first time
 * it is called).
 * @param f  the file
 */
function setupDownloadFileContents (f)
{
	f.getContents = function (callBack)
	{
		if (f.hasContents)
			callBack.getContentsCallback (true);
		f.hasContents = true;
		
		//console.log ("file appears in " + f.entities.length);
		for (var i = 0; i < f.entities.length; i++)
		{
			//console.log ("getting " + f.entities[i].entityFileLink.sig + " --> " + f.entities[i].entityFileLink.url);
			getFileContent (f.entities[i].entityFileLink, callBack);
		}
	};
}

/**
 * Called when we have loaded both the default-plots and output-contents files for an experiment from the server.
 * Note that this will be called once per experiment being compared (at least, for those that have both metadata files).
 * @param entity  the experiment object
 * @param showDefault  whether to show a default visualisation (if available)
 */
function highlightPlots (entity, showDefault)
{
//    console.log(entity);
	// Plot description has fields: Plot title,File name,Data file name,Line style,First variable id,Optional second variable id,Optional key variable id
	// Output contents has fields: Variable id,Variable name,Units,Number of dimensions,File name,Type,Dimensions
	plotDescription = entity.plotDescription;
	outputContents = entity.outputContents;
	for (var i = 1 /* Skip first row - it's a header */; i < plotDescription.length; i++)
	{
		if (plotDescription[i].length < 3)
			continue;
		var data_file_code = plotDescription[i][2].hashCode(),
			f = files[data_file_code];
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
						var thisCount = singleProto ? plotDescription.length : f.entities.length;
						if ((!singleProto || i == 1) && thisCount > defaultVizCount)
						{
//    				        console.log("Set default viz to " + plotDescription[i][0]);
							defaultViz = viz;
							defaultVizCount = thisCount;
						}
					}
				}
			}
			
			// Find the plot x and y object names and units from the output contents file.
			for (var output_idx = 0; output_idx < outputContents.length; output_idx++)
			{
				if (plotDescription[i][4] == outputContents[output_idx][0])
				{
					f.xAxes = outputContents[output_idx][1] + ' (' + outputContents[output_idx][2] + ')';
					f.xUnits = outputContents[output_idx][2];
				}
				if (plotDescription[i][5] == outputContents[output_idx][0])
				{
					f.yAxes = outputContents[output_idx][1] + ' (' + outputContents[output_idx][2] + ')';
					f.yUnits = outputContents[output_idx][2];
				}
				if (plotDescription[i].length > 6 && plotDescription[i][6] == outputContents[output_idx][0])
				{
					// When comparing, f.entities is a list of the experiments containing this output data file (`entityLink`),
					// and the version of the file appearing in each experiment (`entityFileLink`).
					var key_file = files[outputContents[output_idx][4].hashCode()],
						ent_f = findEntityFileLink(f, entity); // This entity's version of f
					if (ent_f && key_file)
					{
						var ent_key_file = findEntityFileLink(key_file, entity); // This entity's version of the key file
						if (ent_key_file)
						{
							ent_f.keyId = outputContents[output_idx][0];
							ent_f.keyName = outputContents[output_idx][1];
							ent_f.keyUnits = outputContents[output_idx][2];
							ent_f.keyFile = ent_key_file;
//							console.log("Found key " + plotDescription[i][6] + " for plot " + plotDescription[i][0] + " entity " + entity.name);
						}
					}
				}
			}
			f.title = plotDescription[i][0];
			f.linestyle = plotDescription[i][3];
			
			plotFiles.push (plotDescription[i][2]);
		}
	}
	sortTable (plotFiles);
	// Show the default visualisation if this is the last experiment to be analysed
	if (defaultViz && metadataParsed == metadataToParse)
	{
		nextPage(defaultViz.href, true); // 'Invisible' redirect
	}
}

/**
 * Find the link to a particular entity's version of this file.
 * @param f  the file to look for
 * @param entity  the entity to look for
 * @returns  f.entities[ent_idx].entityFileLink where f.entities[ent_idx].entityLink === entity
 */
function findEntityFileLink(f, entity)
{
	for (var ent_idx=0; ent_idx<f.entities.length; ent_idx++)
		if (f.entities[ent_idx].entityLink === entity)
			return f.entities[ent_idx].entityFileLink;
}

function parseOutputContents (entity, file, showDefault)
{
    metadataToParse += 1;
    entity.outputContents = null; // Note that there is one to parse
    
	var goForIt = {
		getContentsCallback : function (succ)
		{
			if (succ)
			{
				parseCsvRaw(file);
				entity.outputContents = file.csv;
				metadataParsed += 1;
				if (entity.plotDescription)
                    highlightPlots (entity, showDefault);
			}
		}
	};
	getFileContent (file, goForIt);
	
	return null;
}

function parsePlotDescription (entity, file, showDefault)
{
    metadataToParse += 1;
    entity.plotDescription = null; // Note that there is one to parse
	
	var goForIt = {
		getContentsCallback : function (succ)
		{
			if (succ)
			{
			    parseCsvRaw(file);
			    entity.plotDescription = file.csv;
			    metadataParsed += 1;
				if (entity.outputContents)
				    highlightPlots (entity, showDefault);
			}
		}
	};
	getFileContent (file, goForIt);
	
	return null;
}

function parseEntities (entityObj)
{
	//console.log (entityObj);

	// State for figuring out whether we're comparing multiple protocols on a single model, or multiple models on a single protocol,
	// or indeed multiple versions of the same model / protocol, etc.
	firstModelName = entityObj[0].modelName;
	firstModelVersion = entityObj[0].modelVersion;
	firstProtoName = entityObj[0].protoName;
	firstProtoVersion = entityObj[0].protoVersion;
	needsVersionInfo = {};

    // Sort entityObj list by .name
    entityObj.sort(function(a,b) {return (a.name.toLocaleLowerCase() > b.name.toLocaleLowerCase()) ? 1 : ((b.name.toLocaleLowerCase() > a.name.toLocaleLowerCase()) ? -1 : 0);});

	for (var i = 0; i < entityObj.length; i++)
	{
		var entity = entityObj[i];

		if (singleModel && (entity.modelName != firstModelName || entity.modelVersion != firstModelVersion))
			singleModel = false;
		if (singleProto && (entity.protoName != firstProtoName || entity.protoVersion != firstProtoVersion))
			singleProto = false;
		if (needsVersionInfo[entity.modelName + "/" + entity.protoName] === false)
			needsVersionInfo[entity.modelName + "/" + entity.protoName] = true;
		else if (needsVersionInfo[entity.modelName + "/" + entity.protoName] === undefined)
			needsVersionInfo[entity.modelName + "/" + entity.protoName] = false;

		// Fill in the entities and files entries for this entity
		entities[entity.id] = entity;
		if (entity.files)
			for (var j = 0; j < entity.files.length; j++)
			{
				var file = entity.files[j],
					sig = file.name.hashCode();
				file.signature = sig;
				file.url = contextPath + "/download/" + entityType.charAt(0) + "/" + convertForURL (entity.name) + "/" + entity.id + "/" + file.id + "/" + convertForURL (file.name);
				if (!files[sig])
				{
					files[sig] = {};
					files[sig].sig = sig;
					files[sig].name = file.name;
					files[sig].entities = new Array ();
					files[sig].div = {};
					files[sig].viz = {};
					files[sig].hasContents = false;
					setupDownloadFileContents (files[sig]);
				}
				if (file.name.toLowerCase () == "outputs-default-plots.csv")
					parsePlotDescription (entity, file, !(fileName && pluginName));
				if (file.name.toLowerCase () == "outputs-contents.csv")
					parseOutputContents (entity, file, !(fileName && pluginName));
				
				files[sig].entities.push ({entityLink: entity, entityFileLink: file});
			}
	}
	
	// Add version info to plot labels where needed
	//console.log(needsVersionInfo);
	for (var i = 0; i < entityObj.length; i++)
	{
		var entity = entityObj[i];
		if (needsVersionInfo[entity.modelName + "/" + entity.protoName])
		{
			if (singleModel)
				entity.plotName = entity.protoName + "@" + entity.protoVersion;
			else if (singleProto)
				entity.plotName = entity.modelName + "@" + entity.modelVersion;
			else
				entity.plotName = entity.modelName + "@" + entity.modelVersion + " &amp; " + entity.protoName + "@" + entity.protoVersion;
		}
	}
	
	
	// Alter heading to reflect type of comparison
	doc.heading.innerHTML = "Comparison of " + entityType.charAt(0).toUpperCase() + entityType.slice(1) + "s";
	
	if (entityType == "experiment")
	{
		if (singleModel && !singleProto)
		{
		    doc.heading.innerHTML = firstModelName + " experiments: comparison of protocols";
		    plotLabelStripText = firstModelName + " &amp; ";
		}
		else if (singleProto && !singleModel)
		{
		    doc.heading.innerHTML = firstProtoName + " experiments: comparison of models";
		    plotLabelStripText = " &amp; " + firstProtoName;
		}
	}
	
	doc.outputFileHeadline.innerHTML = "Output files from all compared " + entityType + "s";
	
	// Create a drop-down box that allows display of/navigate to experiments being compared
	var entitiesToCompare = document.getElementById("entitiesToCompare");
	removeChildren (entitiesToCompare);
	var form = document.createElement("form");
	entitiesToCompare.appendChild(form);
	var select_box = document.createElement("select");
	select_box.name = "experiment_box";
	select_box.id = "exptSelect";
	var default_option = document.createElement("option");
	default_option.selected = true;
	default_option.value = document.location.href;
	default_option.innerHTML = "Click to view, select to show a single " + entityType;
	select_box.onchange = function(){sel=document.getElementById("exptSelect"); console.log(sel); document.location.href = sel.options[sel.selectedIndex].value;};
	select_box.appendChild(default_option);
	for (var entity in entities)
	{
		var option = document.createElement("option");
		option.value = contextPath + "/"+entityType+"/" + convertForURL (entities[entity].name) + "/" + entities[entity].entityId + "/" + convertForURL (entities[entity].created) + "/" + entities[entity].id;
		option.innerHTML = entities[entity].name + (entityType == "experiment" ? "" : " &mdash; " + entities[entity].version);
		select_box.appendChild(option);
	}
	form.innerHTML = entityType.charAt(0).toUpperCase() + entityType.slice(1) + "s selected for comparison: ";
	form.appendChild(select_box);
	
	buildSite ();
}


function buildSite ()
{
	var filestable = document.getElementById("filestable");
	filesTable = {};
	filesTable.table = filestable;
	filesTable.plots = {};
	filesTable.pngeps = {};
	filesTable.otherCSV = {};
	filesTable.defaults = {};
	filesTable.text = {};
	filesTable.other = {};
	filesTable.all = new Array ();
	
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
	
	filestable.appendChild(tr);
	
	for (var file in files)
	{
		var ents = files[file];
		var curFileName = ents.name;
		tr = document.createElement("tr");
		tr.id = "filerow-" + ents.sig;
		filestable.appendChild(tr);
		td = document.createElement("td");
		td.appendChild(document.createTextNode(curFileName + " ("+ents.entities.length+")"));
		tr.appendChild(td);
		
		filesTable.all.push ({
			name: curFileName,
			row: tr
		});
		
		td = document.createElement("td");
		var size = 0;
		for (var i = 0; i < ents.entities.length; i++)
		{
			size += ents.entities[i].entityFileLink.size;
		}
		//console.log (size + " --> " + humanReadableBytes (size / ents.length));
		td.appendChild(document.createTextNode(humanReadableBytes (size / ents.entities.length)));
		tr.appendChild(td);
		
		/*td = document.createElement("td");
		td.appendChild(document.createTextNode("action"));*/
		
		td = document.createElement("td");
		for (var vi in visualizers)
		{
			var viz = visualizers[vi];
			if (!viz.canRead (ents.entities[0].entityFileLink))
				continue;
			var a = document.createElement("a");
			a.setAttribute("id", "filerow-" + file + "-viz-" + viz.getName ());
			a.href = basicurl + "show/" + file + "/" + vi;
			var img = document.createElement("img");
			img.src = contextPath + "/res/js/visualizers/" + vi + "/" + viz.getIcon ();
			img.alt = viz.getDescription ();
			img.title = img.alt;
			a.appendChild(img);
			//a.appendChild(document.createTextNode ("view"));
			registerFileDisplayer (a);//, basicurl + convertForURL (v.name) + "/" + v.id + "/");
			td.appendChild(a);
			td.appendChild(document.createTextNode (" "));
		}
		tr.appendChild(td);
		
	}
	handleReq ();
}

function displayFile (id, pluginName)
{
	if (!gotInfos)
		return;
    var f = files[id];
    if (!f)
    {
        addNotification ("no such file", "error");
        return;
    }
	for (var ent_idx=0; ent_idx<f.entities.length; ent_idx++)
	{
	    var entity = f.entities[ent_idx].entityLink;
	    if (entity.outputContents === null || entity.plotDescription === null)
	    {
	        // Try again in 0.1s, by which time hopefully they have been parsed
	        console.log("Waiting for metadata to be parsed.");
	        window.setTimeout(function(){displayFile(id, pluginName)}, 100);
	        return;
	    }
	}
	doc.fileName.innerHTML = f.name;
	
	if (!f.div[pluginName])
	{
//	    console.log("Creating visualizer");
		f.div[pluginName] = document.createElement("div");
		f.viz[pluginName] = visualizers[pluginName].setUpComparision (f, f.div[pluginName]);
//		console.log(f);
	}
//	else
//	{
//	    console.log("Reusing vis");
//	    console.log(f);
//	}
    removeChildren (doc.fileDisplay);
	doc.fileDisplay.appendChild (f.div[pluginName]);
    f.viz[pluginName].show ();

    // Show parent div of the file display, and scroll there
	doc.fileDetails.style.display = "block";
	var pos = getPos (doc.heading);
	window.scrollTo(pos.xPos, pos.yPos);
}

function handleReq ()
{
	if (fileName && pluginName && gotInfos)
	{
		displayFile (fileName, pluginName);
		doc.displayClose.href = basicurl;
	}
	else
	{
		doc.fileDetails.style.display = "none";
	}
}

function getInfos (jsonObject)
{
	var xmlhttp = null;
    // !IE
    if (window.XMLHttpRequest)
    {
        xmlhttp = new XMLHttpRequest();
    }
    // IE -- microsoft, we really hate you. every single day.
    else if (window.ActiveXObject)
    {
        xmlhttp = new ActiveXObject("Microsoft.XMLHTTP");
    }
    
    xmlhttp.open("POST", document.location.href, true);
    xmlhttp.setRequestHeader("Content-type", "application/json");

    xmlhttp.onreadystatechange = function()
    {
        if(xmlhttp.readyState != 4)
        	return;
        
        gotInfos = true;
        
        //console.log (xmlhttp.responseText);
    	var json = JSON.parse(xmlhttp.responseText);
    	//console.log (json);
    	displayNotifications (json);
    	
        if(xmlhttp.status == 200)
        {
        	
        	if (json.getEntityInfos)
        	{
        		parseEntities (json.getEntityInfos.entities);
        	}
        }
    };
    xmlhttp.send(JSON.stringify(jsonObject));
}

function parseUrl (event)
{
	var entityIds = null;
	var t = document.location.href.split ("/");
	//console.log (t);
	for (var i = 0; i < t.length; i++)
	{
		if ("/" + t[i] == contextPath && t[i+2] == "m")
		{
			basicurl = t.slice (0, i + 3).join ("/") + "/";
			entityType = "model";
			entityIds = t.slice (i + 3);
		}
		if ("/" + t[i] == contextPath && t[i+2] == "p")
		{
			basicurl = t.slice (0, i + 3).join ("/") + "/";
			entityType = "protocol";
			entityIds = t.slice (i + 3);
		}
		if ("/" + t[i] == contextPath && t[i+2] == "e")
		{
			basicurl = t.slice (0, i + 3).join ("/") + "/";
			entityType = "experiment";
			entityIds = t.slice (i + 3);
		}
	}
	
	if (!entityIds)
	{
		var entitiesToCompare = document.getElementById("entitiesToCompare");
		removeChildren (entitiesToCompare);
		entitiesToCompare.appendChild(document.createTextNode("ERROR building site"));
		return;
	}
	
	fileName = null;
	pluginName = null;
	var TentityIds = new Array ();
	
	
	for (var i = 0; i < entityIds.length; i++)
	{
		if (entityIds[i] == "show")
		{
			if (i + 2 < entityIds.length)
			{
				fileName = entityIds[i + 1];
				pluginName = entityIds[i + 2];
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
	
	//console.log (entityType);
	//console.log (entityIds);
	
	if (!tableParsed)
	{
		tableParsed = true;
		if (entityType == "experiment")
			getInfos ({
				task: "getEntityInfos",
				ids: entityIds
			});
		else
			getInfos ({
				task: "getEntityInfos",
				getBy: "versionId",
				ids: entityIds
			});
	}
	else
		handleReq ();
		
}

function initCompare ()
{
	doc = {
	    heading: document.getElementById("heading"),
		displayClose: document.getElementById("fileclose"),
		fileName: document.getElementById("filename"),
		fileDisplay: document.getElementById("filedisplay"),
		fileDetails: document.getElementById("filedetails"),
		outputFileHeadline: document.getElementById("outputFileHeadline")
	};
	doc.fileDetails.style.display = "none";
	
	// Prevent redirection to the default plot when we close it
	doc.displayClose.addEventListener("click", function (ev) {
		if (ev.which == 1)
		{
			ev.preventDefault();
			doc.fileDetails.style.display = "none";
			shownDefault = true;
			nextPage (doc.displayClose.href);
		}
    }, true);
	
	window.onpopstate = parseUrl;
	parseUrl ();
}


document.addEventListener("DOMContentLoaded", initCompare, false);