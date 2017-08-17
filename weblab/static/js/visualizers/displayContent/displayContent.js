highlightTypes = 
	{
		"xml":
			[
			 new RegExp("xmlprotocol", 'gi'),
			 new RegExp("xml", 'gi'),
			 new RegExp("cellml", 'gi')
			],
		"python":
			[
			 new RegExp("txtprotocol", 'gi')
			],
		"cpp":
			[
			 new RegExp("cpp", 'gi'),
			 new RegExp("hpp", 'gi')
			]/*,
		"plain":
			[
			 new RegExp("plain", 'gi'),
			 new RegExp("txt", 'gi'),
			 new RegExp("csv", 'gi')
			]*/
	};

function getHighlightingType (file)
{
	// match stored type
	for (var i in highlightTypes)
	{
		/*console.log ("trymatch");
		console.log (file.type);
		console.log (highlightTypes[i]);
		console.log (i);
		console.log (file.type.match (highlightTypes[i]));*/
		for (var j = 0; j < highlightTypes[i].length; j++)
			if (file.type.match (highlightTypes[i][j]))
				return i;
	}
	// match extension (user might have chosen unknown)
	var ext = file.name.split('.').pop();
	if (ext)
		for (var i in highlightTypes)
			for (var j = 0; j < highlightTypes[i].length; j++)
				if (ext.match (highlightTypes[i][j]))
					return i;
	// we don't know...
	return "unknown";
}


function contentDumper (file, div)
{
	this.file = file;
	this.div = div;
	this.setUp = false;
	div.appendChild (document.createTextNode ("loading"));
};

contentDumper.prototype.getContentsCallback = function (succ)
{
	removeChildren (this.div);
	if (!succ)
		this.div.appendChild (document.createTextNode ("failed to load the contents"));
	else
	{
		var pre = document.createElement("pre"),
			content = this.file.contents,
			type = getHighlightingType(this.file),
			ext = this.file.name.split('.').pop();
		if (ext == "csv") {
			// Change the array shape line to be comprehensible to humans who don't know the format!
			var lines = content.match(/^.*((\r\n|\n|\r)|$)/gm);
			for (var i=0; i<lines.length; i++)
				if (lines[i].charAt(0) != '#') {
					var dims = lines[i].split(','),
						ndims = dims.shift().trim();
					if (dims.length == ndims)
						lines[i] = lines[i].trim() + ' # This is a ' + ndims + 'd array with shape (' + dims.join().trim() + ')\r\n';
					else
						lines[i] = '# This is a 2d array\r\n' + lines[i];
					break;
				}
			content = lines.join('');
		}
		pre.appendChild(document.createTextNode(content));
		this.div.appendChild (pre);
		if (type != "unknown")
		{
			console.log ("setting class: " + type);
			pre.setAttribute ("class", type);
			hljs.highlightBlock(pre);
		}
	}
		
};

contentDumper.prototype.show = function ()
{
	if (!this.setUp)
		this.file.getContents (this);
};


function displayContent ()
{
	this.name = "displayContent";
	this.icon = "displayContent.png";
	this.description = "display raw contents of this file";
	
	addScript (contextPath + "/res/js/visualizers/displayContent/highlight.js/highlight.pack.js");
	addLink (contextPath + "/res/js/visualizers/displayContent/highlight.js/styles/tomorrow.css");
};

displayContent.prototype.canRead = function (file)
{
	return getHighlightingType (file);
};

displayContent.prototype.getName = function ()
{
	return this.name;
};

displayContent.prototype.getIcon = function ()
{
	return this.icon;
};

displayContent.prototype.getDescription = function ()
{
	return this.description;
};

displayContent.prototype.setUp = function (file, div)
{
	return new contentDumper (file, div);
};

function initDisplayContent ()
{
	visualizers["displayContent"] = new displayContent ();
}

document.addEventListener("DOMContentLoaded", initDisplayContent, false);