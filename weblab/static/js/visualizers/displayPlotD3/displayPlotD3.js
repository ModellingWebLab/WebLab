
function D3Plotter (file, div)
{
	this.file = file;
	this.div = div;
	this.setUp = false;
	div.appendChild (document.createTextNode ("loading"));
};

D3Plotter.prototype.getContentsCallback = function (succ)
{
	//console.log ("insert content");
	//console.log (this.div);
	removeChildren (this.div);
	if (!succ)
		this.div.appendChild (document.createTextNode ("failed to load the contents"));
	else
	{
		var csvData = getCSVColumnsDownsampled (this.file);
		
		var div = document.createElement("div");
		var id = "D3Plot-" + this.file.id;
		div.id = id;
		div.style.width = "780px";
		div.style.height = "780px";
		this.div.appendChild (div);
		
		// don't know whats the point in doing so, but looks like i have to invalidate this document...
		div.setAttribute ("data-d3-plot", "chart");
		
		var plot = D3.asPlot(div);
		
		var colorPalette = D3.ColorPalette.parse("red,green,blue");
		
		for (var i = 1; i < csvData.length; i++)
		{
			var col = (i-1)/(csvData.length-1);
			var xkoord = [];
			var ykoord = [];
			for (var j = 0; j < csvData[i].length; j++)
			{
				xkoord.push (csvData[i][j].x);
				ykoord.push (csvData[i][j].y);
			}
			plot.polyline("line " + i, { x: xkoord, y: ykoord, stroke:  colorPalette.getRgba (col), thickness: 1 });
		}
	}		
};

D3Plotter.prototype.show = function ()
{
	console.log ("show");
	console.log (this.div);
	if (!this.setUp)
		this.file.getContents (this);
};

function D3Plot ()
{
	this.name = "displayPlotD3";
	this.icon = "displayPlotD3.png";
	this.description = "display graphs using D3JS library";
		
	addLink (contextPath + "/res/js/visualizers/displayPlotD3/d3js-1.0.1/css/d3.css");

	addScript (contextPath + "/res/js/visualizers/displayPlotD3/d3js-1.0.1/script/rx.js");
	addScript (contextPath + "/res/js/visualizers/displayPlotD3/d3js-1.0.1/script/rx.jQuery.js");
	addScript (contextPath + "/res/js/visualizers/displayPlotD3/d3js-1.0.1/script/d3-1.0.1.min.js");
};

D3Plot.prototype.canRead = function (file)
{
    return file.name.endsWith("plot_data.csv");
};

D3Plot.prototype.getName = function ()
{
	return this.name;
};

D3Plot.prototype.getIcon = function ()
{
	return this.icon;
};

D3Plot.prototype.getDescription = function ()
{
	return this.description;
};

D3Plot.prototype.setUp = function (file, div)
{
	return new D3Plotter (file, div);
};

function initD3PlotContent ()
{
	visualizers["displayPlotD3"] = new D3Plot ();
}

document.addEventListener("DOMContentLoaded", initD3PlotContent, false);