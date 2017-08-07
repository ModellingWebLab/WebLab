
var pages = [ "matrix" ],//, "search" ],
	comparisonMode = false,
	experimentsToCompare = [],
	linesToCompare = {row: [], col: []},
	baseUrls = {row: "", col: ""}; // These are filled in if we are viewing a sub-matrix

/**
 * Submit a request to create an experiment.
 * @param jsonObject  the data to send
 * @param $td  the table cell to contain this experiment
 * @param entry  the entry for this experiment in the data matrix
 */
function submitNewExperiment(jsonObject, $td, entry)
{
	$td.append("<img src='"+contextPath+"/res/img/loading2-new.gif' alt='loading' />");

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

    xmlhttp.open("POST", contextPath + '/newexperiment.html', true);
    xmlhttp.setRequestHeader("Content-type", "application/json");

    xmlhttp.onreadystatechange = function()
    {
        if (xmlhttp.readyState != 4)
        	return;

    	var json = JSON.parse(xmlhttp.responseText);
    	displayNotifications(json);

    	$td.removeClass("experiment-QUEUED experiment-RUNNING experiment-INAPPLICABLE experiment-FAILED experiment-PARTIAL experiment-SUCCESS");
		$td.unbind("click");
		$td.contents().remove();

    	if (xmlhttp.status == 200)
        {
        	if (json.newExperiment)
        	{
        		var msg = json.newExperiment.responseText;
    			if (json.newExperiment.response)
    			{
    				addNotification(msg, "info");
    				entry.experiment = {name: json.newExperiment.expName,
    									id: json.newExperiment.expId,
    									latestResult: "QUEUED"};
    				var expUrl = contextPath + "/experiment/" + convertForURL(entry.experiment.name) + "/" + entry.experiment.id + "/latest";
    				$td.addClass("experiment-QUEUED");
    				setExpListeners($td, entry);
    			}
    			else
    			{
    				addNotification(msg, "error");
    				$td.addClass("experiment-INAPPLICABLE");
    			}
        	}
        }
        else
        {
        	addNotification("Server-side error occurred submitting experiment.", "error");
        	$td.addClass("experiment-INAPPLICABLE");
        }
    };
    xmlhttp.send(JSON.stringify(jsonObject));
}


function drawMatrix (matrix)
{
	//console.log (matrix);
	var models = [],
		protocols = [],
		modelMapper = {},
		protocolMapper = {},
		mat = [];
	
	for (var key in matrix.models)
		if (matrix.models.hasOwnProperty (key))
		{
			var version = matrix.models[key].id;
			modelMapper[version] = matrix.models[key];
//			modelMapper[version].name = matrix.models[key].name;
			models.push(version);
		}

	for (var key in matrix.protocols)
		if (matrix.protocols.hasOwnProperty (key))
		{
			var version = matrix.protocols[key].id;
			protocolMapper[version] = matrix.protocols[key];
//			protocolMapper[version].name = matrix.protocols[key].name;
			protocols.push(version);
		}

    // Sort rows & columns alphabetically (case insensitive)
    models.sort(function(a,b) {return (modelMapper[a].name.toLocaleLowerCase() > modelMapper[b].name.toLocaleLowerCase()) ? 1 : ((modelMapper[b].name.toLocaleLowerCase() > modelMapper[a].name.toLocaleLowerCase()) ? -1 : 0);});
    protocols.sort(function(a,b) {return (protocolMapper[a].name.toLocaleLowerCase() > protocolMapper[b].name.toLocaleLowerCase()) ? 1 : ((protocolMapper[b].name.toLocaleLowerCase() > protocolMapper[a].name.toLocaleLowerCase()) ? -1 : 0);});
	
	/*console.log ("models");
	console.log (modelMapper);
	console.log ("protocols");
	console.log (protocolMapper);*/
	
	for (var i = 0; i < models.length; i++)
	{
		mat[i] = [];
		for (var j = 0; j < protocols.length; j++)
		{
			mat[i][j] = {
					model: modelMapper[models[i]],
					protocol: protocolMapper[protocols[j]]
			};
			modelMapper[models[i]].row = i;
			protocolMapper[protocols[j]].col = j;
			//console.log (mat[i][j]);
		}
	}
	//console.log ("matrix");
	//console.log (mat);
	
	for (var key in matrix.experiments)
	{
		if (matrix.experiments.hasOwnProperty (key))
		{
			var exp = matrix.experiments[key],
				row = modelMapper[exp.model.id].row,
				col = protocolMapper[exp.protocol.id].col;
			exp.name = exp.model.name + " @ " + exp.model.version + " & " + exp.protocol.name + " @ " + exp.protocol.version;
			mat[row][col].experiment = exp;
		}
	}
	
	var div = document.getElementById("matrixdiv"),
		table = document.createElement("table");
	removeChildren(div);
	table.setAttribute("class", "matrixTable");
	div.appendChild(table);

	if (mat.length == 0)
	{
		table.innerHTML = "<p class='failed'>No experiments found matching the selected view criteria.</p>";
		return;
	}

	for (var row = -1; row < mat.length; row++)
	{
		var tr = document.createElement("tr");
		table.appendChild(tr);
		for (var col = -1; col < mat[0].length; col++)
		{
			var td = document.createElement("td"),
				$td = $(td);
			tr.appendChild(td);
			td.setAttribute("id", "matrix-entry-" + row + "-" + col);
			
			//console.log ("row " + row + " col " + col);
			
			if (row == -1 && col == -1)
				continue;
			
			// Top row: protocol names
			if (row == -1)
			{
				var d1 = document.createElement("div"),
					d2 = document.createElement("div"),
					a = document.createElement("a"),
					proto = mat[0][col].protocol;
				a.href = contextPath + "/protocol/" + convertForURL(proto.name) + "/" + proto.entityId
					+ "/" + convertForURL(proto.version) + "/" + proto.id;
				d2.setAttribute("class", "vertical-text");
				d1.setAttribute("class", "vertical-text__inner");
				d2.appendChild(d1);
				a.appendChild(document.createTextNode(proto.name));
				d1.appendChild(a);
				td.appendChild(d2);
				$td.addClass("matrixTableCol")
					.data({col: col, protoId: proto.entityId})
					.click(function (ev) {
						if (comparisonMode) {
							ev.preventDefault();
							addToComparison($(this), 'col');
						}
					});
				continue;
			}
			
			// Left column: model names
			if (col == -1)
			{
				var a = document.createElement("a"),
					model = mat[row][0].model;
				a.href = contextPath + "/model/" + convertForURL(model.name) + "/" + model.entityId
					+ "/" + convertForURL(model.version) + "/" + model.id;
				a.appendChild(document.createTextNode(model.name));
				td.appendChild(a);
				$td.addClass("matrixTableRow")
					.data({row: row, modelId: model.entityId})
					.click(function (ev) {
						if (comparisonMode) {
							ev.preventDefault();
							addToComparison($(this), 'row');
						}
					});
				continue;
			}
			
			// Normal case
			var entry = mat[row][col];
			entry.row = row;
			entry.col = col;
			$td.data("entry", entry).addClass("matrix-row-" + row).addClass("matrix-col-" + col);
			if (entry.experiment)
				$td.addClass("experiment experiment-"+entry.experiment.latestResult);
			else
				$td.addClass("experiment experiment-NONE");
			
			setExpListeners($td, entry);
		}
	}
	
	// Fix the matrix layout, so it doesn't jump on hovers
	var rowWidth = 0, rowHeight = 0, colWidth = 0, colHeight = 0;
	$(table).find("td.matrixTableRow").addClass("matrixHover").each(function () {
		rowWidth = Math.max(rowWidth, this.offsetWidth);
		rowHeight = Math.max(rowHeight, this.offsetHeight);
	});
	$(table).find("td.matrixTableCol").addClass("matrixHover").each(function () {
		colWidth = Math.max(colWidth, this.offsetWidth);
		colHeight = Math.max(colHeight, this.offsetHeight);
	});
	$(table).find("td.matrixTableRow").removeClass("matrixHover").each(function () {
		$(this).height(rowHeight).width(rowWidth);
	});
	$(table).find("td.matrixTableCol").removeClass("matrixHover").each(function () {
		$(this).height(colHeight).width(colWidth);
	});
}


/**
 * Set up the click/hover listeners for the given matrix entry
 * @param $td  the table cell
 * @param entry  mat[row][col] for this table cell
 */
function setExpListeners($td, entry)
{
	// Click listener
	if (entry.experiment)
	{
		var expUrl = contextPath + "/experiment/" + convertForURL(entry.experiment.name) + "/" + entry.experiment.id + "/latest";
		addMatrixClickListener($td, expUrl, entry.experiment.id, entry.experiment.latestResult);
	}
	else
	{
		$td.click(function () {
			submitNewExperiment ({
				task: "newExperiment",
				model: entry.model.id,
				protocol: entry.protocol.id
			}, $td, entry);
		});
	}

	// Highlight the relevant row & column labels when the mouse is over this cell
	$td.mouseenter(function (ev) {
		$("#matrix-entry--1-" + entry.col).addClass("matrixHover");
		$("#matrix-entry-" + entry.row + "--1").addClass("matrixHover");
	}).mouseleave(function (ev) {
		$("#matrix-entry--1-" + entry.col).removeClass("matrixHover");
		$("#matrix-entry-" + entry.row + "--1").removeClass("matrixHover");
	});
}

/**
 * Handle a click on a row or column header when in comparison mode.
 * 
 * Toggles the selected state of this row/column.  If only one ends up selected, then all cells in that row/column are
 * included in the comparison.  If at least one row and column are selected, then we only compare experiments that
 * feature both a selected row and column.
 * 
 * Note that users MAY select extra experiments not in a selected row/column.  Such choices should not be affected by
 * this method.  Clicking on individual experiments selected via this mechanism will also toggle their state, but may
 * be overridden by a subsequent selection via this method.
 * 
 * @param $td  the header clicked on
 * @param rowOrCol  either 'row' or 'col'
 */
function addToComparison($td, rowOrCol)
{
	var index = $td.data(rowOrCol),
		lineIndex = linesToCompare[rowOrCol].indexOf(index),
		cells = $(".matrix-" + rowOrCol + "-" + index),
		colOrRow = (rowOrCol == 'row' ? 'col' : 'row'),
		otherTypeSelected = (linesToCompare[colOrRow].length > 0);
	if (lineIndex != -1)
	{
		// Was selected already -> unselect
		linesToCompare[rowOrCol].splice(lineIndex, 1);
		$td.removeClass("patternized");
		// Clear any selected experiments in this line
		cells.filter(".patternized").each(function () {
			var $cell = $(this),
				cellIndex = experimentsToCompare.indexOf($cell.data("entry").experiment.id);
			if (cellIndex != -1)
			{
				experimentsToCompare.splice(cellIndex, 1);
				$cell.removeClass("patternized");
			}
		});
		// If this was the only line of this type selected, select all experiments in any selected colOrRow
		if (linesToCompare[rowOrCol].length == 0)
		{
			$.each(linesToCompare[colOrRow], function (i, otherLineIndex) {
				$(".matrix-" + colOrRow + "-" + otherLineIndex).not(".patternized").each(function (i, elt) {
					var $cell = $(elt),
						exp = $cell.data("entry").experiment;
					if (exp && isSelectableResult(exp.latestResult))
					{
						experimentsToCompare.push(exp.id);
						$cell.addClass("patternized");
					}
				});
			});
		}
	}
	else
	{
		// Select this row/col
		linesToCompare[rowOrCol].push(index);
		$td.addClass("patternized");
		$("#comparisonMatrix").show();
		// If this is the first line of this type, clear lines of the other type
		if (linesToCompare[rowOrCol].length == 1)
		{
			$.each(linesToCompare[colOrRow], function (i, otherLineIndex) {
				$(".matrix-" + colOrRow + "-" + otherLineIndex).filter(".patternized").each(function (i, elt) {
					var $cell = $(elt),
						cellIndex = experimentsToCompare.indexOf($cell.data("entry").experiment.id);
					experimentsToCompare.splice(cellIndex, 1);
					$cell.removeClass("patternized");
				});
			});
		}
		// Select experiments in this line
		cells.not(".patternized").each(function () {
			var $cell = $(this),
				entry = $cell.data("entry"),
				exp = entry.experiment;
			if (exp && isSelectableResult(exp.latestResult) &&
					(!otherTypeSelected || linesToCompare[colOrRow].indexOf(entry[colOrRow]) != -1))
			{
				experimentsToCompare.push(exp.id);
				$cell.addClass("patternized");
			}
		});
	}
	computeComparisonLink();
}

/**
 * Toggle whether the given experiment is selected in comparison mode.
 * @param $td  the table cell
 * @param expId  the experiment id
 * @returns whether the experiment is now selected
 */
function toggleSelected($td, expId)
{
	var index = experimentsToCompare.indexOf(expId);
	if (index != -1)
	{
		// was selected -> unselect
		experimentsToCompare.splice(index, 1);
		$td.removeClass("patternized");
	}
	else
	{
		// add a new element to the list
		experimentsToCompare.push(expId);
		$td.addClass("patternized");
	}
	return (index == -1);
}

/**
 * Compute the 'compare experiments' link in comparison mode,
 * and show the button iff there are experiments to compare.
 */
function computeComparisonLink()
{
	if (experimentsToCompare.length > 0)
	{
		var newHref = contextPath + "/compare/e/";
		for (var i = 0; i < experimentsToCompare.length; i++)
			newHref += experimentsToCompare[i] + "/";
		$("#comparisonLink").show().data("href", newHref);
	}
	else
	{
		$("#comparisonMatrix").hide();
		$("#comparisonLink").hide();
	}
}

/**
 * Determine whether an experiment with the given result status can be selected for comparison.
 */
function isSelectableResult(result)
{
	return (result == "SUCCESS" || result == "PARTIAL");
}

function addMatrixClickListener($td, link, expId, result)
{
	$td.click(function (ev) {
		if (comparisonMode)
		{
			if (!isSelectableResult(result))
				return;
			toggleSelected($td, expId);
			computeComparisonLink();
		}
		else
		{
			document.location.href = link;
		}
	});
}


function getMatrix (jsonObject, actionIndicator)
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
        
    	var json = JSON.parse(xmlhttp.responseText);
    	//console.log (json);
    	displayNotifications (json);
    	
        if(xmlhttp.status == 200)
        {
        	if (json.getMatrix)
        	{
        		drawMatrix (json.getMatrix);
        	}
        }
        else
        {
        	actionIndicator.innerHTML = "<img src='"+contextPath+"/res/img/failed.png' alt='error' />Sorry, serverside error occurred.";
        }
    };
    xmlhttp.send(JSON.stringify(jsonObject));
}

/**
 * Parse the current location URL to determine what part of the matrix to show.
 * The URL pathname should look like: {contextPath}/db/models/id1/id2/protocols/id3/id4
 * If no models or protocols are given, we show everything.
 * The URL can also be {contextPath}/db/public to show only what anonymous users can view.
 * Returns a JSON object to be passed to getMatrix();
 */
function parseLocation ()
{
	var base = contextPath + "/db/",
		rest = "",
		ret = { task: "getMatrix" };
	if (document.location.pathname.substr(0, base.length) == base)
		rest = document.location.pathname.substr(base.length);
	$('.showButton').removeClass("selected");
	$('.showMyButton').hide();
	if (rest.length > 0)
	{
		var items = rest.split("/"),
			modelIndex = items.indexOf("models"),
			protoIndex = items.indexOf("protocols");
		if (protoIndex != -1)
		{
			if (modelIndex != -1)
				ret.modelIds = items.slice(modelIndex + 1, protoIndex);
			ret.protoIds = items.slice(protoIndex + 1);
		}
		else if (modelIndex != -1)
			ret.modelIds = items.slice(modelIndex + 1);
		if (modelIndex != -1)
			baseUrls.row = "/models/" + ret.modelIds.join("/");
		if (protoIndex != -1)
			baseUrls.col = "/protocols/" + ret.protoIds.join("/");
		if (modelIndex == -1 && protoIndex == -1)
		{
			if (items[0] == "public")
			{
				$('#showPublicExpts').addClass("selected");
				ret.publicOnly = "1";
			}
			else if (items[0].substr(0,4) == "mine")
			{
				$('#showMyExpts').addClass("selected");
				$('.showMyButton').show();
				ret.mineOnly = "1";
				if (items[0].indexOf("-m") != -1)
				{
					ret.includeModeratedModels = "0";
					console.log('Show model');
					$('#showMyExptsModels').text("Show moderated models");
				}
				else
					$('#showMyExptsModels').text("Hide moderated models");
				if (items[0].indexOf("-p") != -1)
				{
					ret.includeModeratedProtocols = "0";
					console.log('Show proto');
					$('#showMyExptsProtocols').text("Show moderated protocols");
				}
				else
					$('#showMyExptsProtocols').text("Hide moderated protocols");
			}
			else if (items[0] == "all")
			{
				$('#showAllExpts').addClass("selected");
				ret.showAll = "1";
			}
			else
				$('#showModeratedExpts').addClass("selected");
		}
	}
	else
		$('#showModeratedExpts').addClass("selected");
	return ret;
}

function prepareMatrix ()
{
	var div = document.getElementById("matrixdiv");
	
	var loadingImg = document.createElement("img");
	loadingImg.src = contextPath+"/res/img/loading2-new.gif";
	div.appendChild(loadingImg);
	div.appendChild(document.createTextNode("Preparing experiment matrix; please be patient."));

	getMatrix(parseLocation(), div);
	
	$("#comparisonModeButton").text(comparisonMode ? "Disable" : "Enable")
	                          .click(function () {
		comparisonMode = !comparisonMode;
		$("#comparisonModeButton").text(comparisonMode ? "Disable" : "Enable");
		if (!comparisonMode)
		{
			// Clear all selections
			experimentsToCompare.splice(0, experimentsToCompare.length);
			linesToCompare.row.splice(0, linesToCompare.row.length);
			linesToCompare.col.splice(0, linesToCompare.col.length);
			$(".patternized").removeClass("patternized");
			$("#comparisonLink").hide();
			$("#comparisonMatrix").hide();
		}
	});
	$("#comparisonLink").click(function () {
	    document.location = $(this).data("href");
	});
	$("#comparisonMatrix").click(function () {
		var url = contextPath + "/db";
		if (linesToCompare.row.length > 0)
		{
			url += "/models";
			for (var i=0; i<linesToCompare.row.length; i++)
				url += "/" + $("#matrix-entry-" + linesToCompare.row[i] + "--1").data("modelId");
		}
		else
			url += baseUrls.row;
		if (linesToCompare.col.length > 0)
		{
			url += "/protocols";
			for (var i=0; i<linesToCompare.col.length; i++)
				url += "/" + $("#matrix-entry--1-" + linesToCompare.col[i]).data("protoId");
		}
		else
			url += baseUrls.col;
		document.location.href = url; // TODO: use history API instead?
	});
	$("#comparisonLink").hide();
	$("#comparisonMatrix").hide();
	
	// The my/public/moderated view buttons
	$("#showModeratedExpts").click(function () {
		if (!$(this).hasClass("selected"))
			document.location.href = contextPath + "/db";
	});
	$("#showPublicExpts").click(function () {
		if (!$(this).hasClass("selected"))
			document.location.href = contextPath + "/db/public";
	});
	$("#showAllExpts").click(function () {
		if (!$(this).hasClass("selected"))
			document.location.href = contextPath + "/db/all";
	});
	$("#showMyExpts").click(function () {
		if (!$(this).hasClass("selected"))
			document.location.href = contextPath + "/db/mine";
	});
	$("#showMyExptsModels").click(function () {
		var hideModels = hiddenToggle($(this)),
			hideProtocols = $("#showMyExptsProtocols").text().substr(0,4) == 'Show';
		console.log('M.click ' + hideModels + ' ' + hideProtocols);
		document.location.href = contextPath + "/db/mine"
			+ (hideModels ? "-m" : "") + (hideProtocols ? "-p" : "");
	});
	$("#showMyExptsProtocols").click(function () {
		var hideModels = $("#showMyExptsModels").text().substr(0,4) == 'Show',
			hideProtocols = hiddenToggle($(this));
		console.log('P.click ' + hideModels + ' ' + hideProtocols);
		document.location.href = contextPath + "/db/mine"
			+ (hideModels ? "-m" : "") + (hideProtocols ? "-p" : "");
	});
}

/**
 * Toggle whether a button's text starts 'Hide' or 'Show'.
 * @param $button  the button to check
 * @returns true iff the text previously started 'Hide' (so the state was shown, now hidden)
 */
function hiddenToggle($button)
{
	var oldText = $button.text(),
		hide;
	if (oldText.substr(0,4) == 'Show')
	{
		hide = false;
		$button.text('Hide' + oldText.substr(4));
	}
	else
	{
		hide = true;
		$button.text('Show' + oldText.substr(4));
	}
	return hide;
}

function switchPage (page)
{
	//console.log ("switching to " + page);
	for (var i = 0; i < pages.length; i++)
	{
		if (pages[i] == page)
		{
			document.getElementById(pages[i] + "Tab").style.display = "block";
			$("#" + pages[i] + "chooser").addClass("selected");
		}
		else
		{
			document.getElementById(pages[i] + "Tab").style.display = "none";
			$("#" + pages[i] + "chooser").removeClass("selected");
		}
	}
}
function registerSwitchPagesListener (btn, page)
{
	//console.log ("register switch listener: " + page);
	btn.addEventListener("click", function () {
		switchPage (page);
	}, true);
}

function initDb ()
{
//	for (var i = 0; i < pages.length; i++)
//	{
//		var btn = document.getElementById(pages[i] + "chooser");
//		registerSwitchPagesListener (btn, pages[i]);
//	}
	switchPage (pages[0]);
	
	prepareMatrix ();
}
document.addEventListener("DOMContentLoaded", initDb, false);