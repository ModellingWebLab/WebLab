
function contentTabularizer (file, div)
{
	this.file = file;
	this.div = div;
	this.setUp = false;
	div.appendChild (document.createTextNode ("loading"));
};

contentTabularizer.prototype.getContentsCallback = function (succ)
{
	//console.log ("insert content");
	//console.log (this.div);
	removeChildren (this.div);
	if (!succ)
		this.div.appendChild (document.createTextNode ("failed to load the contents"));
	else
	{
		var data = getCSV (this.file);
		
		var table = document.createElement("table");
		table.setAttribute("class", "displayContentsTable");
		
		for (var i = 0; i < data.length; i++)
		{
			var tr = document.createElement("tr");
			for (var j = 0; j < data[i].length; j++)
			{
				var td = document.createElement("td");
				td.appendChild (document.createTextNode(data[i][j]));
				tr.appendChild(td);
			}
			table.appendChild(tr);
		}
		
		
		this.div.appendChild (table);
	}
		
};

contentTabularizer.prototype.show = function ()
{
	console.log ("show");
	console.log (this.div);
	if (!this.setUp)
		this.file.getContents (this);
};


function tabularizeContent ()
{
	this.name = "displayTable";
	this.icon = "displayTable.png";
	this.description = "display contents in a table";
};

tabularizeContent.prototype.canRead = function (file)
{
	var ext = file.name.split('.').pop();
	
	return ext == "csv";
};

tabularizeContent.prototype.getName = function ()
{
	return this.name;
};

tabularizeContent.prototype.getIcon = function ()
{
	return this.icon;
};

tabularizeContent.prototype.getDescription = function ()
{
	return this.description;
};

tabularizeContent.prototype.setUp = function (file, div)
{
	return new contentTabularizer (file, div);
};

function initTabularizeContent ()
{
	visualizers["displayTable"] = new tabularizeContent ();
}

document.addEventListener("DOMContentLoaded", initTabularizeContent, false);