
function unixDiffer (file, div)
{
	this.file = file;
	this.div = div;
	this.setUp = false;
	
	this.formerFile = null;
	this.laterFile = null;
	this.diffs = new Array ();
	
	var jqDiv = $(div);

	var table = $("<table></table>").append ("<thead>" +
			"<tr><th>Available versions</th><th>Select as predecessor</th><th>Select as successor</th>" +
			"</thead>");
	var tableBody = $("<tbody></tbody>");
	table.append (tableBody);
	
	this.displayer = $("<div></div>").addClass ("unixDiffDisplayer");
	jqDiv.append (table).append (this.displayer);

	var autoDiff = (file.entities.length == 2); // If there are only 2 versions available, diff them automatically
	for (var i = 0; i < file.entities.length; i++)
	{
		var tr = $("<tr></tr>").addClass ("unixDiffFileVersionTableRow");
		
		var name = $("<td></td>").text (file.entities[i].entityLink.name + " - " + file.entities[i].entityLink.version);
		var prev = $("<input type='radio' name='former'/>");
		var succ = $("<input type='radio' name='later'/>");
		
		tr.append (name).append ($("<td></td>").append (prev)).append ($("<td></td>").append (succ));
		tableBody.append (tr);
		
		this.formerClickListener (prev, file.entities[i], tr);
		this.laterClickListener (succ, file.entities[i], tr);
		
        if (autoDiff)
        {
            if (i == 0)
                succ.prop('checked', true).click();
            else
                prev.prop('checked', true).click();
        }
	}
};

unixDiffer.prototype.formerClickListener = function (former, file, tr)
{
	var outer = this;
	former.click (function ()
	{
		$(".unixDiffFileVersionTableRow").each (function () {$(this).removeClass ("unixDiffDel");});
		outer.formerFile = file;
		tr.addClass ("unixDiffDel");
		outer.showDiff ();
	});
};

unixDiffer.prototype.laterClickListener = function (later, file, tr)
{
	var outer = this;
	later.click (function () 
	{
		$(".unixDiffFileVersionTableRow").each (function () {$(this).removeClass ("unixDiffIns");});
		outer.laterFile = file;
		tr.addClass ("unixDiffIns");
		outer.showDiff ();
	});
};

unixDiffer.prototype.computeDifferences = function (former, later, matrixKey)
{
	var request = {
			task: "getUnixDiff",
			entity1: former.entityLink.id,
			file1: former.entityFileLink.id,
			entity2: later.entityLink.id,
			file2: later.entityFileLink.id
	};
	
	var diffs = this.diffs;
	
	$.post (document.location.href, JSON.stringify(request)).done (function (data)
	{
		console.log (data);
		if (data && data.getUnixDiff && data.getUnixDiff.response)
		{
			var diff = data.getUnixDiff.unixDiff;
			
			diff = diff
			// stop thinking these are tags
			.replace (/</g, "&lt;")
			.replace (/>/g, "&gt;")
			// highlight line numbers
			.replace (/^(\d.*)$/gm, "<strong>$1</strong>")
			// highlight inserted/deleted stuff
			.replace (/^(&lt;.*)$/gm, "<span class='unixDiffDel'>$1</span>")
			.replace (/^(&gt;.*)$/gm, "<span class='unixDiffIns'>$1</span>")
			;

			diffs[matrixKey].empty ().append (
					"<strong>Differences</strong> between <strong>" + former.entityLink.name + "</strong> - <strong>" + former.entityLink.version + "</strong> and <strong>" + later.entityLink.name + "</strong> - <strong>" + later.entityLink.version + "</strong>")
					.append ("<pre>"+diff+"</pre>");
		}
		else
			diffs[matrixKey].empty ().append ("failed to compute the differences");
	}).fail (function () 
	{
		diffs[matrixKey].empty ().append ("failed to compute the differences");
	});
};

unixDiffer.prototype.showDiff = function ()
{
	if (this.laterFile && this.formerFile)
	{
		var matrixKey = this.formerFile.entityLink.name + "--" + this.formerFile.entityLink.version + "--" + this.laterFile.entityLink.name + "--" + this.laterFile.entityLink.version;
		if (!this.diffs[matrixKey])
		{
			// compute the diff and show it afterwards
			this.diffs[matrixKey] = $("<div></div>").text ("computing differences");
			this.computeDifferences (this.formerFile, this.laterFile, matrixKey);
		}

		// show diff
		this.displayer.empty ().append (this.diffs[matrixKey]);
	}
};

unixDiffer.prototype.getContentsCallback = function (succ)
{
	
};

unixDiffer.prototype.show = function ()
{
	
};


function unixDiffContent ()
{
    this.name = "displayUnixDiff";
    this.icon = "displayUnixDiff.png";
    this.description = "use unix diff tool to compare versions";
};

unixDiffContent.prototype.canRead = function (file)
{
	var allowedExt = [
	                  "xmlprotocol",
	                  "xml",
	                  "cellml",
	                  "cpp",
	                  "hpp",
	                  "txt",
	                  "gp"
	                  // to be extended?
	                  ];
	
	for (var i = 0; i < allowedExt.length; i++)
		if (file.name.endsWith(allowedExt[i]))
			return true;
	
	return false;
};

unixDiffContent.prototype.getName = function ()
{
    return this.name;
};

unixDiffContent.prototype.getIcon = function ()
{
    return this.icon;
};

unixDiffContent.prototype.getDescription = function ()
{
    return this.description;
};

unixDiffContent.prototype.setUpComparision = function (files, div)
{
    return new unixDiffer (files, div);
};


function initUnixDiffContent ()
{
    visualizers["displayUnixDiff"] = new unixDiffContent ();
}

document.addEventListener("DOMContentLoaded", initUnixDiffContent, false);