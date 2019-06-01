var common = require('../../expt_common.js');


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
	$(this.div).empty();
	if (!succ)
		this.div.appendChild (document.createTextNode ("failed to load the contents"));
	else
	{
		var data = common.getCSV (this.file), header = this.file.header, colmap = this.file.colmap;
		
		var table = document.createElement("table");
		table.setAttribute("class", "displayContentsTable");

		if (header)
		{
			var tr = document.createElement("tr");
			for (var j = 0; j < header.length; j++)
			{
				var th = document.createElement("th");
				th.appendChild (document.createTextNode(header[j]));
				tr.appendChild(th);
			}
			table.appendChild(tr);
		}
		
		for (var i = 0; i < data.length; i++)
		{
			var tr = document.createElement("tr");
			for (var j = 0; j < data[i].length; j++)
			{
				var td = document.createElement("td");
				td.appendChild (document.createTextNode(data[i][colmap[j]]));
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

module.exports = {
  'name': 'displayTable',
  'get_visualizer': function() { return new tabularizeContent(); }
}
