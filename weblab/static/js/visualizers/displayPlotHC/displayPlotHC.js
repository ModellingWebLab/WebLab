
/**
 * Actually create a plot using the HighCharts library.
 * 
 * @param id  id of the element that should contain the plot
 * @param datasets  the data to plot
 * @param thisFile  the 'file' object providing axes labels etc.
 */
function doHcPlot(id, datasets, thisFile)
{
    if ($("#"+id).highcharts === undefined)
    {
        // Wait for the library to finish loading!
        console.log("Waiting for highcharts to load...");
        window.setTimeout(function(){doHcPlot(id, datasets, thisFile)}, 100);
        return;
    }

    var options = {
        title: {
            text: ''
        },
        chart: {
            zoomType: "xy"
        },
        plotOptions: {
            series: {
                allowPointSelect: true
            },
            line: {
                marker: {
                    enabled: thisFile.linestyle == "linespoints"
                }
            }
        },
        series: datasets,
        tooltip: {
            headerFormat: "",
            pointFormat: '<span style="color:{series.color}">{series.name}</span>: <b>{point.x}{point.y}</b><br/>',
            valuePrefix: ", ", // This is a hack to allow putting units on the x value!
            valueSuffix: ""
        }
    };
    
    if (thisFile.xAxes)
    {
        options.xAxis = {title : { text : thisFile.xAxes}};
        options.tooltip.valuePrefix = " " + thisFile.xUnits + ", ";
    }
    if (thisFile.yAxes)
    {
        options.yAxis = {title : { text : thisFile.yAxes}};
        options.tooltip.valueSuffix = " " + thisFile.yUnits;
    }
    if (thisFile.title)
        options.title = {text : thisFile.title};
    
    $("#"+id).highcharts(options);
    
    // Save data for export if user requests it
    allowPlotExport(thisFile.name, datasets, {'x': thisFile.xAxes || '', 'y': thisFile.yAxes || ''});
}


function HCPlotter (file, div)
{
	this.file = file;
	this.div = div;
	this.setUp = false;
	div.appendChild (document.createTextNode ("loading"));
};

HCPlotter.prototype.getContentsCallback = function (succ)
{
    removeChildren (this.div);
	if (!succ)
		this.div.appendChild (document.createTextNode ("failed to load the contents"));
	else
	{
	    var thisFile = this.file;

	    if (thisFile.keyId && !thisFile.keyFile.contents)
        {
            // Load the key data and try again
            this.div.appendChild (document.createTextNode ("loading plot key data..."));
            thisFile.keyFile.getContents (this);
            return;
        }

		var csvData = (thisFile.linestyle == "linespoints" || thisFile.linestyle == "points") ? getCSVColumnsNonDownsampled (thisFile) : getCSVColumnsDownsampled (thisFile);
		var keyVals = getKeyValues(thisFile, csvData.length);
		
		var div = document.createElement("div");
		var id = "hcplot-" + thisFile.id;
		div.id = id;
		div.style.width = "780px";
		div.style.height = "450px";
		this.div.appendChild (div);

        var datasets = [];
        for (var i = 1; i < csvData.length; i++)
        {
                var curData = [];
                for (var j = 0; j < csvData[i].length; j++)
                        curData.push ([csvData[i][j].x, csvData[i][j].y]);
                var label;
                if (keyVals.length == csvData.length)
                    label = thisFile.keyName + " = " + keyVals[i] + " " + thisFile.keyUnits;
                else
                    label = "line " + i;
                datasets.push ({name : label, data: curData});
        }
        
        doHcPlot(id, datasets, thisFile);
	}
		
};

HCPlotter.prototype.show = function ()
{
	if (!this.setUp)
		this.file.getContents (this);
};

function HCPlotterComparer (file, div)
{
	this.file = file;
	this.div = div;
	this.setUp = false;
	div.appendChild (document.createTextNode ("loading..."));
	div.setAttribute ("class", "HighChartDiv");
	this.gotFileContents = 0;
    this.gotKeyContents = 0;
    this.expectedKeyContents = -1;
	this.ok = true;
};

HCPlotterComparer.prototype.getContentsCallback = function (succ)
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

HCPlotterComparer.prototype.showContents = function ()
{
    var thisDiv = this.div;
    var thisFile = this.file;
    if ($(thisDiv).highcharts === undefined)
    {
        // Wait for the library to finish loading!
        var t = this;
        window.setTimeout(function(){t.showContents()}, 100);
        return;
    }
	removeChildren (thisDiv);
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
//                    console.log("Found key " + f.keyId);
                }
            }
//            console.log("Expecting " + this.expectedKeyContents + " keys");
            // Then set them loading and wait!
            for (var i = 0; i < thisFile.entities.length; i++)
            {
                var f = thisFile.entities[i].entityFileLink;
                if (f.keyId && !f.keyFile.contents)
                {
                    getFileContent(f.keyFile, this);
                }
            }
            if (this.expectedKeyContents > 0)
            {
                thisDiv.appendChild (document.createTextNode ("loading plot legend data..."));
                return;
            }
        }
        
        this.setUp = true;
		
		var lineStyle = thisFile.linestyle;
		
		var csvDatas = new Array ();
		
		for (var i = 0; i < thisFile.entities.length; i++)
		{
			csvDatas.push ({
					data: (lineStyle == "linespoints" || lineStyle == "points") ?
							getCSVColumnsNonDownsampled (thisFile.entities[i].entityFileLink) : getCSVColumnsDownsampled (thisFile.entities[i].entityFileLink),
					entity: thisFile.entities[i].entityLink,
					file: thisFile.entities[i].entityFileLink
			});
		}
		
		var div = document.createElement("div");
		var id = "hcplot-" + thisFile.id;
		div.id = id;
		div.style.width = "780px";
		div.style.height = "450px";
		thisDiv.appendChild (div);
		
        var datasets = [];

        for (var j = 0; j < csvDatas.length; j++)
        {
            var eachCSVData = csvDatas[j];
            var entityName = eachCSVData.entity.plotName ? eachCSVData.entity.plotName : eachCSVData.entity.name;
        	var csvData = eachCSVData.data;
        	var csvFile = eachCSVData.file;
            var keyVals = getKeyValues(csvFile, csvData.length);
        	for (var i = 1; i < csvData.length; i++)
        	{
        		var curData = [];
	            for (var k = 0; k < csvData[i].length; k++)
	                curData.push ([csvData[i][k].x, csvData[i][k].y]);

                var label = entityName;
                if (plotLabelStripText)
                    label = label.replace(plotLabelStripText, "");
                if (keyVals.length == csvData.length)
                    label += ", " + csvFile.keyName + " = " + keyVals[i] + " " + csvFile.keyUnits
                else if (csvData.length > 2)
                    label += " line " + i;

                datasets.push ({name : label, data: curData});
        	}
        }
        
        doHcPlot(id, datasets, thisFile);
	}
		
};

HCPlotterComparer.prototype.show = function ()
{
	if (!this.setUp)
	{
		this.file.getContents (this);
	}
	else
		this.showContents ();
};

function HCPlot ()
{
	this.name = "displayPlotHC";
	this.icon = "displayPlotHC.png";
	this.description = "display graphs using HighChart library";
	
	var el = document.createElement('script');
	el.async = false;
	el.src = contextPath + "/res/js/visualizers/displayPlotHC/js/highcharts.js";//excanvas.min.js";
	el.type = 'text/javascript';

	(document.getElementsByTagName('head')[0]||document.body).appendChild(el);
};

HCPlot.prototype.canRead = function (file)
{
    return file.name.endsWith("plot_data.csv");
};

HCPlot.prototype.getName = function ()
{
	return this.name;
};

HCPlot.prototype.getIcon = function ()
{
	return this.icon;
};

HCPlot.prototype.getDescription = function ()
{
	return this.description;
};

HCPlot.prototype.setUp = function (file, div)
{
	return new HCPlotter (file, div);
};

HCPlot.prototype.setUpComparision = function (files, div)
{
	return new HCPlotterComparer (files, div);
};

function initHCPlotContent ()
{
	visualizers["displayPlotHC"] = new HCPlot ();
}

document.addEventListener("DOMContentLoaded", initHCPlotContent, false);