var utils = require('../../lib/utils.js');
var common = require('../../expt_common.js');

var choicesDivId = 'choices',
	resetButtonDivId = 'flot-buttons-div',
	colouredSpanIdPrefix = 'legend-colour-span-',
	legendDivId = 'legend',
	tooltipId = 'flotTooltip',
	plottedGraph = {}, // TODO: probably safer if this is an instance property!
	resetButtonId = 'resetButton',
	legendHideButtonId = 'hideButton',
	selectTogglerId = 'selectToggler';

/* create and append the div for showing the plot choices */
function createAppendChoicesDiv(parentDiv) {
    var choicesDiv = document.createElement("div");
    choicesDiv.id = choicesDivId;
    parentDiv.appendChild (choicesDiv);
}

/* create and append the flot plotting div element with specified id attr */
function createAppendFlotPlotDiv(parentDiv, flotPlotDivId) {
    var flotPlotDiv = document.createElement("div");
    flotPlotDiv.id = flotPlotDivId;
    //flotPlotDiv.title = "Zoom available by selecting an area of the plot";
    flotPlotDiv.style.width = "780px";
    flotPlotDiv.style.height = "450px";
    parentDiv.appendChild(flotPlotDiv);
}

/* create and append the div for showing the legend */
function createAppendLegendDiv(parentDiv) {
    var legendContainer =  document.createElement("div");
    legendContainer.id = legendDivId;
    parentDiv.appendChild (legendContainer);
}

/* create and append a reset button to the div element */
function createAppendResetButton(parentDiv) {
    var resetButtonDiv = document.createElement("div");
    resetButtonDiv.id = resetButtonDivId;
    parentDiv.appendChild(resetButtonDiv);

    var resetButton = document.createElement('input');
    resetButton.id = resetButtonId;
    resetButton.title = 'Reset graph zoom based on currently selected datasets';
    resetButton.type = 'button';
    resetButton.value = 'Reset zoom';
    resetButtonDiv.appendChild (resetButton);

    var legendHideButton = document.createElement('input');
    legendHideButton.id = legendHideButtonId;
    legendHideButton.title = 'Toggle the visibility of the legend.';
    legendHideButton.type = 'button';
    legendHideButton.value = 'Toggle legend';
    resetButtonDiv.appendChild (legendHideButton);
}

/* create and append a select toggler to the div element */
function createAppendSelectToggler(parentDiv) {
    var selectTogglerEl = document.createElement('input');
    selectTogglerEl.id = selectTogglerId;
    selectTogglerEl.type = 'checkbox';
    parentDiv.appendChild (selectTogglerEl);

    var label = document.createElement('label');
    label.setAttribute('for', selectTogglerId);
    label.innerHTML = 'Select all';
    parentDiv.appendChild(label);

    var selectToggler = $('#' + selectTogglerId);
    selectToggler.attr({ 'checked': 'checked' });
    setTogglerTitle(selectToggler);
}

/* indicator of linestyle type */
function isStyleLinespointsOrPoints(lineStyle) {
  return (lineStyle == "linespoints" || lineStyle == "points");
}

/* Plot the graph */
function plotAccordingToChoices(plotProperties, selectedCoords) {
    if ($.plot === undefined)
    {
        /// Wait 0.1s for flot to load and try again
        console.log("Waiting for flot to load.");
        window.setTimeout(function(){plotAccordingToChoices(plotProperties, selectedCoords);}, 100);
        return;
    }

    var choicesContainer = plotProperties.choicesContainer;
    var datasets = plotProperties.datasets;
    var styleLinespointsOrPoints = plotProperties.styleLinespointsOrPoints;
    var flotPlotDivId = plotProperties.flotPlotDivId;
    var x_label = plotProperties.x_label;
    var y_label = plotProperties.y_label;

    var data = [];

    choicesContainer.find("input:checked").each(function () {
        var key = $(this).attr("name");
        if (key && datasets[key]) {
            data.push(datasets[key]);
        }
    });

    var genericSettings = retrieveGenericSettings($('#' + legendDivId));
    var settings;
    if (selectedCoords != undefined)
    {
        settings = $.extend(true, {}, genericSettings, {
          xaxis: { min: selectedCoords.x[0], max: selectedCoords.x[1] },
          yaxis: { min: selectedCoords.y[0], max: selectedCoords.y[1] }
        });
    }
    else
    {
        settings = genericSettings;
    }
    settings.xaxis.axisLabel = x_label;
    settings.yaxis.axisLabel = y_label;

    if (styleLinespointsOrPoints)
        settings.points = { show: true, radius: 2 };

    if (plotProperties.histogram)
    {
        settings.points = {show: false};
        settings.lines = {show: false};
        for (var i=0; i<data.length; i++)
        {
            data[i].bars = {
                show : true,
                barWidth : data[i].data[1][0] - data[i].data[0][0],
                align : 'left'
            };
        }
    }

    plottedGraph = $.plot("#" + flotPlotDivId, data, settings);
};

/* retrieve min and max x and y axes values of current plot */
function retrieveCurrentPlotCoords(plottedGraph) {
  var xAxis = plottedGraph.getAxes().xaxis;
  var yAxis = plottedGraph.getAxes().yaxis;
  var coords = { 'x': [xAxis.min, xAxis.max],
                 'y': [yAxis.min, yAxis.max] };
  return coords;
}

/* Retrieve generic plot settings */
function retrieveGenericSettings(legendContainer) {
  var genericSettings = {
      xaxis: { //tickDecimals: 0,
               position: 'bottom',
               axisLabelPadding: 10,
               axisLabelUseCanvas: true },
      yaxis: { position: 'left',
               axisLabelPadding: 10,
               axisLabelUseCanvas: true },
      lines: { show: true },
      selection: { mode: 'xy' },
      grid: { hoverable: true},
      legend: { backgroundOpacity: 0,
                container: legendContainer }
  };
  return genericSettings;
}

/**
 * Attach the click, select, hover, etc listeners to the plot
 *
 * @param plotProperties Assembly of various plot properties.
 * @param moreThanOneDataset True if more than one dataset being plotted.
 */
function setListeners(plotProperties, moreThanOneDataset) {
    var choicesContainer = plotProperties.choicesContainer;
    var flotPlotDivId = plotProperties.flotPlotDivId;

    /* someone's clicked on a dataset checkbox */
    choicesContainer.find("input").click(function() {
        var checkedCount = choicesContainer.find('input:checkbox:checked').length;
        if (checkedCount == 0) {
          /* should not happen! */
        }
        else
        {
          if (checkedCount == 1) {
            /* disable the input checkbox on whichever checked dataset remains */
            $('#' + choicesDivId + ' input:checkbox:checked').prop('disabled', true);
          }
          else
          {
            /* more than one dataset selected, remove any disabled */
            $('#' + choicesDivId + ' input:checkbox:disabled').prop('disabled', false);
          }
          /* re-plot using existing coordinates */
          plotAccordingToChoices(plotProperties, retrieveCurrentPlotCoords(plottedGraph));
        }
    });

    /* listen to user selecting an area of the plot to zoom into */
    $('#' + flotPlotDivId).bind('plotselected', function (event, ranges) {
        /* clamp the zooming to prevent eternal zoom */
        if (ranges.xaxis.to - ranges.xaxis.from < 0.00001)
          ranges.xaxis.to = ranges.xaxis.from + 0.00001;
        if (ranges.yaxis.to - ranges.yaxis.from < 0.00001)
          ranges.yaxis.to = ranges.yaxis.from + 0.00001;

        var coords = { 'x': [ranges.xaxis.from, ranges.xaxis.to],
                       'y': [ranges.yaxis.from, ranges.yaxis.to] };

        plottedGraph.setSelection(ranges, true);
        plotAccordingToChoices(plotProperties, coords);
    });

    /* listen to user hovering over plot */
    var previousPoint = null;
    $('#' + flotPlotDivId).bind('plothover', function (event, pos, item) {
      if (typeof pos.y != 'undefined') {
        if (item) {
          if (previousPoint != item.datapoint) {
            previousPoint = item.datapoint;

            $('#' + tooltipId).remove();
            var x = item.datapoint[0];
            var y = item.datapoint[1];

            var content = '[' + item.series.label + '] : ' +
                          plotProperties.x_label + ' \'' + x + '\' : ' +
                          plotProperties.y_label + ' \'' + y + '\'';
            show_tooltip(item.pageX, item.pageY, content);
          }
        } else {
          $('#' + tooltipId).remove();
          previousPoint = null;
        }
      }
    });


    /* reset graphical display according to ranges defined by current dataset selection */
    $('#' + resetButtonId).click(function() {
        plotAccordingToChoices(plotProperties);
    });

    if (moreThanOneDataset)
    {
        /* action when all datasets toggler is clicked */
        $('#' + selectTogglerId).click(function() {
          var toggler = $(this);
          setTogglerTitle(toggler);
          /* remove any disabled inputs */
          $('#' + choicesDivId + ' input:checkbox:disabled').prop('disabled', false);
          if (toggler.is(':checked'))
          {
            /* check all currently unchecked datasets */
            choicesContainer.find('input:checkbox:not(:checked)').each(function() {
              $(this).prop('checked', true);
            });
          }
          else
          {
            /* remove all the checked properties except on the first (and disabled that!) */
            choicesContainer.find('input:checkbox:not(:eq(0))').each(function() {
              $(this).prop('checked', false);
            });
            /* switch on the first (just in case it was already de-selected) and disable it */
            $('#' + choicesDivId + ' input:checkbox:eq(0)').prop({ 'disabled': true, 'checked': true });
          }
          plotAccordingToChoices(plotProperties, retrieveCurrentPlotCoords(plottedGraph));
      });
    }

    // mouse over for legend
    var legend = $("#" + choicesDivId);
    legend.append ($("<div></div>").addClass ("clearer"));
    if (legend.height () > 100)
    {
        legend.append ($("<div></div>").addClass ("fadings").append ($("<small></small>").append ($("<strong></strong>").text ("hover or click 'toggle legend' to show all"))));

    	legend.addClass ("legend-fade");
    	legend.mouseover (function ()
    	{
    		legend.removeClass ("legend-fade");
    	}).mouseout(function ()
    	{
    		legend.addClass ("legend-fade");
    	});
        // Toggle button implements persistent expand/collapse
        $('#' + legendHideButtonId).click (function ()
            {
                var legend = $('#' + choicesDivId);
                if (legend.hasClass("legend-fade"))
                {
                    // Show, and disable mouseout behaviour
                    legend.removeClass("legend-fade").off('mouseout');
                }
                else
                {
                    // Fade, and enable mouseout behaviour
                    legend.addClass("legend-fade").mouseout(function(){legend.addClass("legend-fade");});
                }
            });
    }
    else
    {
    	legend.removeClass ("legend-fade");
    	$('#' + legendHideButtonId).hide();
    }
}

/* provide dataset toggler title */
function setTogglerTitle(toggler) {
  toggler.attr('title', toggler.is(':checked') ? 'Select one (cannot select none!)' : 'Select all');
}

/**
 * Pop up a tooltip current x and y axis values.
 *
 * @param x X-axis coordinate.
 * @param y Y-axis coordinate.
 * @param content Content of tooltip.
 */
function show_tooltip(x, y, content) {
  jQuery('<div />').attr({ 'id' : tooltipId })
                   .css({ 'top': y + 5, 'left': x + 5 })
                   .addClass('flotTooltip')
                   .html(content)
                   .appendTo('body')
                   .fadeIn(200);
}

/* Transfer the colours placed into the legend div by flot's plotting, to the spans corresponding
to the dataset plot label. Once transfered the legend div serves no purpose. */
function transferLegendColours(datasets) {
 /* we don't want to see the legend data so hide immediately, only use it to pinch the colour! */
 $('#' + legendDivId).hide();
 $.each(datasets, function(key, val) {
     /* class legendColorBox defined in jquery.flot.js in function insertLegend() */
     var thisDatasetNumber = val.color;
     var legendColorBox = $('td.legendColorBox:eq(' + thisDatasetNumber + ') div div');
     /* moz wasn't happy using border-color, which IE didn't mind */
     var colour = legendColorBox.css('border-left-color');
     $('#' + colouredSpanIdPrefix + thisDatasetNumber).css('background-color', colour);
 });
 /* legend element is no longer required */
 $('#' + legendDivId).remove();
}

/**
 * Transform from flot formatted datasets to highcharts formatted, which is more convenient for exporting as CSV.
 * That is, an object whose values are {label:, data:} gets converted to an array with values {name:, data:}.
 * In both cases data is an array of [x,y] pairs.
 */
function transformForExport(datasets)
{
	return $.map(datasets, function (value, key) {
		return {'name': value.label, 'data': value.data};
	});
}

function contentFlotPlot (file, div)
{
    this.file = file;
    this.div = div;
    this.setUp = false;
    div.appendChild (document.createTextNode ("loading..."));
    div.setAttribute ("class", "flotDiv");
};

contentFlotPlot.prototype.getContentsCallback = function (succ)
{
    var thisFile = this.file;
    var thisFileId = thisFile.id;
    var thisDiv = this.div;

    $(thisDiv).empty();
    if (!succ)
        thisDiv.appendChild (document.createTextNode ("failed to load the contents"));
    else
    {
        if (thisFile.keyId && !thisFile.keyFile.contents)
        {
            // Load the key data and try again
            thisDiv.appendChild (document.createTextNode ("loading plot key data..."));
            thisFile.keyFile.getContents (this);
            return;
        }
        this.setUp = true;
        this.drawPlot();
    }
};

contentFlotPlot.prototype.drawPlot = function ()
{
    var thisFile = this.file, thisFileId = thisFile.id, thisDiv = this.div;
    $(thisDiv).empty();
        var styleLinespointsOrPoints = isStyleLinespointsOrPoints(thisFile.linestyle);
        var csvData = styleLinespointsOrPoints ? common.getCSVColumnsNonDownsampled (thisFile) :
                                                 common.getCSVColumnsDownsampled (thisFile);
        var keyVals = common.getKeyValues(thisFile, csvData.length);

        var data_file = $('#dataset-link').data('file');
        if (data_file)
        {
          // Overlay expt'l data
          var data_cols = styleLinespointsOrPoints ? common.getCSVColumnsNonDownsampled(data_file) :
                                                     common.getCSVColumnsDownsampled(data_file),
              data_key = common.getKeyValues(data_file, data_cols.length);
          data_cols.shift(); // Remove t
          data_key.shift();
          csvData = csvData.concat(data_cols);
          keyVals = keyVals.concat(data_key);
          console.log(keyVals);
        }

        var datasets = {};
        for (var i = 1; i < csvData.length; i++)
        {
            var curData = [];
            for (var j = 0; j < csvData[i].length; j++)
                curData.push ([csvData[i][j].x, csvData[i][j].y]);
            datasets["line" + i] = {label: keyVals[i], data: curData};
        }

        // Some of the plots won't come from specified plots, so these are missing.
        var x_label = thisFile.xAxes || "";
        var y_label = thisFile.yAxes || "";

        /* hard-coded colour indexes to prevent from shifting when turned off */
        var datasetNumber = 0;
        $.each(datasets, function(key, val)
        {
            val.color = datasetNumber++;
        });
        var lastDatasetNumber = datasetNumber - 1;

        var flotPlotDivId = 'flotplot-' + thisFileId.replace(/\W/g, '');
        createAppendFlotPlotDiv(thisDiv, flotPlotDivId);
        (datasetNumber > 1) && createAppendSelectToggler(thisDiv);
        createAppendResetButton(thisDiv);
        createAppendChoicesDiv(thisDiv);
        createAppendLegendDiv(thisDiv);

        var choicesContainer = $('#' + choicesDivId);
        var onlyOneDataset = (datasetNumber == 1);

        /* insert checkboxes - note that colours will be applied to spans after plotting */
        $.each(datasets, function(key, val) {
            var thisDatasetNumber = val.color;
            var colouredSpan = $('<span />').attr('id', colouredSpanIdPrefix + thisDatasetNumber)
                                            .addClass('flotColour')
                                            .html('&nbsp;&nbsp;');
            var inputId = 'id' + key;
            var newLabel = $('<label />').attr('for', inputId).html(val.label);
            var newInput = $('<input />').attr({ 'type': 'checkbox',
                                                 'name': key,
                                                 'checked': 'checked',
                                                 'id': inputId });
            if (onlyOneDataset)
            {
                newInput.attr('disabled', 'disabled');
            }
            choicesContainer.append ($("<div></div>").addClass ("flotLegendEntity").append(newInput).append(colouredSpan).append('&nbsp;').append(newLabel));
            /* if more than one dataset and it's not the last one to be processed.. */
            /*if (!onlyOneDataset && (thisDatasetNumber != lastDatasetNumber))
            {
                choicesContainer.append('<br />');
            }*/
        });

        var plotProperties = {
          'choicesContainer': choicesContainer,
          'datasets': datasets,
          'styleLinespointsOrPoints': styleLinespointsOrPoints,
          'histogram': thisFile.linestyle == 'hist',
          'flotPlotDivId': flotPlotDivId,
          'x_label': x_label,
          'y_label': y_label
        };

        plotAccordingToChoices(plotProperties, undefined);
        /* legend generated when graph plotted, so this must follow the plot creation! */
        transferLegendColours(datasets);
        setListeners(plotProperties, (datasetNumber > 1));

        // Save data for export if user requests it
        common.allowPlotExport(thisFile.name, transformForExport(datasets), {'x': x_label, 'y': y_label});
};

contentFlotPlot.prototype.show = function ()
{
    //console.log ("show");
    //console.log (this.div);
    if (!this.setUp)
        this.file.getContents (this);
};

contentFlotPlot.prototype.redraw = function ()
{
    if (this.setUp)
        this.drawPlot();
};

function contentFlotPlotComparer (file, div)
{
    this.file = file;
    this.div = div;
    this.setUp = false;
    div.appendChild (document.createTextNode ("loading..."));
    div.setAttribute ("class", "flotDiv");
    this.gotFileContents = 0;
    this.gotKeyContents = 0;
    this.expectedKeyContents = -1;
    this.ok = true;
};

contentFlotPlotComparer.prototype.getContentsCallback = function (succ)
{
    if (!succ)
        this.ok = false;
    this.div.appendChild(document.createTextNode("."));

    if (this.expectedKeyContents > 0)
    {
        // We've loaded the main data, and are now loading plot key data
        this.gotKeyContents++;
        if (this.gotKeyContents >= this.expectedKeyContents)
            this.showContents();
    }
    else
    {
        // We're loading the main plot data
        this.gotFileContents++;
        if (this.gotFileContents >= this.file.entities.length)
            this.showContents ();
    }
};

contentFlotPlotComparer.prototype.showContents = function ()
{
    var thisFile = this.file;
    var thisFileSig = thisFile.sig;
    var thisDiv = this.div;

    $(thisDiv).empty();
    if (!this.ok)
        thisDiv.appendChild (document.createTextNode ("failed to load the contents"));
    else
    {
        // Check whether we need to load plot key data
        if (this.expectedKeyContents == -1)
        {
            this.expectedKeyContents = 0;
            // First figure out how many keys we expect
            for (var i = 0; i < thisFile.entities.length; i++)
            {
                var f = thisFile.entities[i].entityFileLink;
                if (f.keyId && !f.keyFile.contents)
                {
                    this.expectedKeyContents++;
                }
            }
//            console.log("Expecting " + this.expectedKeyContents + " keys");
            // Then set them loading and wait!
            for (var i = 0; i < thisFile.entities.length; i++)
            {
                var f = thisFile.entities[i].entityFileLink;
                if (f.keyId && !f.keyFile.contents)
                {
                    utils.getFileContent(f.keyFile, this);
                }
            }
            if (this.expectedKeyContents > 0)
            {
                thisDiv.appendChild (document.createTextNode ("loading plot legend data..."));
                return;
            }
        }

        this.setUp = true;

        var styleLinespointsOrPoints = isStyleLinespointsOrPoints(thisFile.linestyle);

        var csvDatas = new Array ();
        for (var i = 0; i < thisFile.entities.length; i++)
        {
            csvDatas.push ({
                data: (styleLinespointsOrPoints) ? common.getCSVColumnsNonDownsampled (thisFile.entities[i].entityFileLink) :
                                                   common.getCSVColumnsDownsampled (thisFile.entities[i].entityFileLink),
                entity: thisFile.entities[i].entityLink,
                file: thisFile.entities[i].entityFileLink
            });
        }

        // Some of the plots won't come from specified plots, so these are missing.
        var x_label = thisFile.xAxes || "";
        var y_label = thisFile.yAxes || "";

        var flotPlotDivId = 'flotplot-' + thisFileSig;
        createAppendFlotPlotDiv(thisDiv, flotPlotDivId);
        createAppendSelectToggler(thisDiv);
        createAppendResetButton(thisDiv);
        createAppendChoicesDiv(thisDiv);
        createAppendLegendDiv(thisDiv);

        // insert checkboxes
        var choicesContainer = $('#' + choicesDivId);

        var datasets = {};
        var curColor = 0;

        for (var j = 0; j < csvDatas.length; j++)
        {
            var eachCSVData = csvDatas[j];
            var entityName = eachCSVData.entity.plotName ? eachCSVData.entity.plotName : eachCSVData.entity.name;
            var entityId = eachCSVData.entity.id;
            var fileSig = eachCSVData.file.sig;
            var csvData = eachCSVData.data;
            var keyVals = common.getKeyValues(eachCSVData.file, csvData.length);

            //var paragraph = $('<p />').html(eachCSVData.entity.name).css('font-weight', 'bold');
            //choicesContainer.append(paragraph);

            for (var i = 1; i < csvData.length; i++)
            {
                var curData = [];
                for (var k = 0; k < csvData[i].length; k++)
                    curData.push ([csvData[i][k].x, csvData[i][k].y]);

                var key = entityId + "-" + fileSig + "-" + i;
                var label = entityName;
                var plotLabelStripText = $.data(document.body, 'plotLabelStripText');
                if (plotLabelStripText)
                    label = label.replace(plotLabelStripText, "");
                if (csvData.length > 2 || keyVals[i].substr(0, 5) !== "line ")
                    label += ", " + keyVals[i];
                datasets[key] = {label: label, data: curData, color: curColor};

                var colouredSpan = $('<span />').attr('id', colouredSpanIdPrefix + curColor)
                                                .addClass('flotColour')
                                                .html('&nbsp;&nbsp;');
                var inputId = 'id' + key;
                var newLabel = $('<label />').attr('for', inputId).html(label);
                var newInput = $('<input />').attr({ 'type': 'checkbox',
                                                     'name': key,
                                                     'checked': 'checked',
                                                     'id': inputId });
                choicesContainer.append ($("<div></div>").addClass ("flotLegendEntity").append(newInput).append(colouredSpan).append('&nbsp;').append(newLabel));
                //choicesContainer.append(newInput).append(colouredSpan).append('&nbsp;').append(newLabel);
                curColor++;
                /*if (i!=csvData.length)
                {
                    choicesContainer.append('<br/>');
                }*/
            }
        }

        var plotProperties = {
            'choicesContainer': choicesContainer,
            'datasets': datasets,
            'styleLinespointsOrPoints': styleLinespointsOrPoints,
            'histogram': thisFile.linestyle == 'hist',
            'flotPlotDivId': flotPlotDivId,
            'x_label': x_label,
            'y_label': y_label
        };

        plotAccordingToChoices(plotProperties, undefined);
        /* legend generated when graph plotted, so this must follow the plot creation! */
        transferLegendColours(datasets);
        setListeners(plotProperties, true);

        // Save data for export if user requests it
        common.allowPlotExport(thisFile.name, transformForExport(datasets), {'x': x_label, 'y': y_label});
    }
};

contentFlotPlotComparer.prototype.show = function ()
{
    //console.log ("show");
    //console.log (this.div);
    if (!this.setUp)
    {
        this.file.getContents (this);
    }
    else
    {
        this.showContents ();
    }
};

contentFlotPlotComparer.prototype.redraw = function ()
{
    if (this.setUp)
        this.showContents();
};


function flotContent ()
{
    this.name = "displayPlotFlot";
    this.icon = "displayPlotFlot.png";
    this.description = "display graphs using flot library";

    utils.addScript(staticPath + "js/visualizers/displayPlotFlot/flot/jquery.flot.min.js");
    utils.addScript(staticPath + "js/visualizers/displayPlotFlot/flot/jquery.flot.navigate.min.js");
    utils.addScript(staticPath + "js/visualizers/displayPlotFlot/flot/jquery.flot.axislabels.js");
    utils.addScript(staticPath + "js/visualizers/displayPlotFlot/flot/jquery.flot.selection.js");
};

flotContent.prototype.canRead = function (file)
{
    return file.name.endsWith(".csv");
};

flotContent.prototype.getName = function ()
{
    return this.name;
};

flotContent.prototype.getIcon = function ()
{
    return this.icon;
};

flotContent.prototype.getDescription = function ()
{
    return this.description;
};

flotContent.prototype.setUp = function (file, div)
{
    return new contentFlotPlot (file, div);
};

flotContent.prototype.setUpComparision = function (files, div)
{
    return new contentFlotPlotComparer (files, div);
};

module.exports = {
  'name': 'displayPlotFlot',
  'get_visualizer': function() { return new flotContent(); }
}
