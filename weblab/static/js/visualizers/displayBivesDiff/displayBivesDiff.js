
function bivesDiffer (file, div)
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
	
	this.displayer = $("<div></div>").addClass ("bivesDiffDisplayer");
	jqDiv.append (table).append (this.displayer);

	var autoDiff = (file.entities.length == 2); // If there are only 2 versions available, diff them automatically
	for (var i = 0; i < file.entities.length; i++)
	{
		var tr = $("<tr></tr>").addClass ("bivesDiffFileVersionTableRow");
		
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

bivesDiffer.prototype.formerClickListener = function (former, file, tr)
{
	var outer = this;
	former.click (function () 
	{
		$(".bivesDiffFileVersionTableRow").each (function () {$(this).removeClass ("bivesDiffDel");});
		outer.formerFile = file;
		tr.addClass ("bivesDiffDel");
		outer.showDiff ();
	});
};

bivesDiffer.prototype.laterClickListener = function (later, file, tr)
{
	var outer = this;
	later.click (function () 
	{
		$(".bivesDiffFileVersionTableRow").each (function () {$(this).removeClass ("bivesDiffIns");});
		outer.laterFile = file;
		tr.addClass ("bivesDiffIns");
		outer.showDiff ();
	});
};

bivesDiffer.prototype.computeDifferences = function (former, later, matrixKey)
{
	var request = {
			task: "getBivesDiff",
			entity1: former.entityLink.id,
			file1: former.entityFileLink.id,
			entity2: later.entityLink.id,
			file2: later.entityFileLink.id
	};
	
	var diffs = this.diffs;
	
	$.post (document.location.href, JSON.stringify(request)).done (function (data)
	{
		//console.log (data);
		if (data && data.getBivesDiff && data.getBivesDiff.response)
		{
			var diff = data.getBivesDiff.bivesDiff;

			var diffDiv = $("<div></div>");
			var legendDiv = $("<div></div>").addClass ("bivesLegend");

			diffs[matrixKey].empty ().append (
					"<strong>Differences</strong> between <strong>" + former.entityLink.name + "</strong> - <strong>" + former.entityLink.version + "</strong> and <strong>" + later.entityLink.name + "</strong> - <strong>" + later.entityLink.version + "</strong>")
					.append (diffDiv).append (legendDiv);
			
			legendDiv.append ("<span class='bivesDiffIns bivesLegendItem'>inserted</span> &mdash; " +
					"<span class='bivesDiffDel bivesLegendItem'>deleted</span> &mdash; " +
					"<span class='bivesDiffMove bivesLegendItem'>moved</span> &mdash; " +
					"<span class='bivesDiffUpdate bivesLegendItem'>updated</span>");
			
			var head = $("<div></div>").addClass ("bivesTabLine");
			var reportDiv = $("<div></div>").hide ();
			var chDiv = $("<div></div>").hide ();
			var crnDiv = $("<div></div>").hide ();
			var xmlDiv = $("<div></div>").hide ();
			diffDiv.append (head);
			
			var shown = false;
			
			if (diff.reactionsJson)
			{
				var rnLink = $("<span></span>").addClass ("bivesTab").text ("Reaction Network");
				var reactionsDiffId = "bivesGrapheneAppRn-" + diff.id;
				crnDiv.append ("<div id='" + reactionsDiffId + "' ng-controller='MainCtrl'><sg-graphene imports='exports' template='"+contextPath + "/res/js/visualizers/displayBivesDiff/graphene-sems/template.html'></sg-graphene></div>");
				head.append (rnLink);
				diffDiv.append (crnDiv);
				rnLink.click (function ()
				{
					reportDiv.hide ();
					chDiv.hide ();
					crnDiv.show ();
					xmlDiv.hide ();
					
					$(".bivesTab").each (function () {$(this).removeClass ("bivesTabSelected");});
					rnLink.addClass ("bivesTabSelected");
				});
				if (!shown)
					rnLink.click ();
				shown = true;
				
				// add stanley's graphene library
				angular.element(document).ready(function() {
					angular.bootstrap(document.querySelector("div#" + reactionsDiffId),
							['grapheneSemsApp']);
				  var scope = angular.element(document.querySelector("div#" + reactionsDiffId)).scope();
				  scope.data = angular.fromJson(diff.reactionsJson);
				  scope.zoom = true; // enables scroll to zoom
				  scope.width = 780;  // this is the width of the node force layout system, which is independent of the SVG size, which is defined in the template, but you can and probably make them the same.
				  scope.height = 500; // this is the height, I suggest you probably change both of these to match the width and height in the template file.
				  scope.charge = -2500; // I think you can make this more negative, maybe -1500, I noticed the nodes are very close.
				  // Alternatively you could also play with increasing scope.linkDistance
				  scope.gravity = 0.0; // set gravity to 0.1 or 0.2, so the outer disconnected nodes aren't quite so far away.
				  scope.linkDistance = 5;
				  scope.renderFps = 20; // makes the layout more choppy, but saves CPU
				  scope.$apply();
				});
				
			}
			
			if (diff.reportHtml)
			{
				var reportLink = $("<span></span>").addClass ("bivesTab").text ("Report");
				reportDiv.append (diff.reportHtml);
				head.append (reportLink);
				diffDiv.append (reportDiv);
				reportLink.click (function ()
				{
					reportDiv.show ();
					chDiv.hide ();
					crnDiv.hide ();
					xmlDiv.hide ();
					
					$(".bivesTab").each (function () {$(this).removeClass ("bivesTabSelected");});
					reportLink.addClass ("bivesTabSelected");
				});
				if (!shown)
					reportLink.click ();
				shown = true;
				
				// uff, these equations are quite long...
				// lets append some line breaks..
				reportDiv.find ("mo").each (function () { 
                    if ($(this).html ().match (/\s*=\s*/))
					{
						var neu = $("<mo></mo>").attr ("linebreak", "newline");
						$(this).parent ().append (neu);
					}
                });
				MathJax.Hub.Queue(["Typeset",MathJax.Hub])
			}
			
			if (false) //diff.compHierarchyJson)
			{
				var chLink = $("<span></span>").addClass ("bivesTab").text ("Component Hierarchy");
				var hierarchyDiffId = "bivesGrapheneAppCh-" + diff.id;
				chDiv.append ("<div id='" + hierarchyDiffId+ "' ng-controller='MainCtrl'><sg-graphene imports='exports' template='"+contextPath + "/res/js/visualizers/displayBivesDiff/graphene-sems/template.html'></sg-graphene></div>");
				head.append (chLink);
				diffDiv.append (chDiv);
				chLink.click (function ()
				{
					reportDiv.hide ();
					chDiv.show ();
					crnDiv.hide ();
					xmlDiv.hide ();
					
					$(".bivesTab").each (function () {$(this).removeClass ("bivesTabSelected");});
					chLink.addClass ("bivesTabSelected");
				});
				if (!shown)
					chLink.click ();
				shown = true;
				
				// add stanley's graphene library
				angular.element(document).ready(function() {
					angular.bootstrap(document.querySelector("div#" + hierarchyDiffId),
							['grapheneSemsApp']);
				  var scope = angular.element(document.querySelector("div#" + hierarchyDiffId)).scope();
				  scope.data = angular.fromJson(diff.compHierarchyJson);
				  scope.zoom = true; // enables scroll to zoom
				  scope.width = 1560;  // this is the width of the node force layout system, which is independent of the SVG size, which is defined in the template, but you can and probably make them the same.
				  scope.height = 1000; // this is the height, I suggest you probably change both of these to match the width and height in the template file.
				  scope.charge = -400; // I think you can make this more negative, maybe -1500, I noticed the nodes are very close.
				  // Alternatively you could also play with increasing scope.linkDistance
				  scope.gravity = 0.2; // set gravity to 0.1 or 0.2, so the outer disconnected nodes aren't quite so far away.
				  scope.linkDistance = 5;
				  scope.renderFps = 10; // makes the layout more choppy, but saves CPU
				  scope.$apply();
				});
			}
			
			// fallback if neither sbml/cellml/pharmml etc.
			if (diff.xmlDiff)
			{
				var xmlLink = $("<span></span>").addClass ("bivesTab").text ("XML Patch");
				var xml = diff.xmlDiff;
				

				xml = xml
				// stop assuming these are tags
				.replace (/</g, "&lt;")
				.replace (/>/g, "&gt;")
				// highlight inserted/deleted stuff
				.replace (/(&lt;delete&gt;((.|[\r\n])*)&lt;\/delete&gt;|&lt;delete \/&gt;)/m, "<span class='bivesDiffDel'>$1</span>")
				.replace (/(&lt;insert&gt;((.|[\r\n])*)&lt;\/insert&gt;|&lt;insert \/&gt;)/m, "<span class='bivesDiffIns'>$1</span>")
				.replace (/(&lt;move&gt;((.|[\r\n])*)&lt;\/move&gt;|&lt;move \/&gt;)/m, "<span class='bivesDiffMove'>$1</span>")
				.replace (/(&lt;update&gt;((.|[\r\n])*)&lt;\/update&gt;|&lt;update \/&gt;)/m, "<span class='bivesDiffUpdate'>$1</span>")
				// highlight arguments
				.replace (/(oldParent="[^"]*")/g, "<span class='bivesDiffDel'>$1</span>")
				.replace (/(oldChildNo="[^"]*")/g, "<span class='bivesDiffDel'>$1</span>")
				.replace (/(oldPath="[^"]*")/g, "<span class='bivesDiffDel'>$1</span>")
				//
				.replace (/(newParent="[^"]*")/g, "<span class='bivesDiffIns'>$1</span>")
				.replace (/(newChildNo="[^"]*")/g, "<span class='bivesDiffIns'>$1</span>")
				.replace (/(newPath="[^"]*")/g, "<span class='bivesDiffIns'>$1</span>")
				;
				
				xmlDiv.append ($("<pre></pre>").append (xml));
				head.append (xmlLink);
				diffDiv.append (xmlDiv);
				xmlLink.click (function ()
				{
					reportDiv.hide ();
					chDiv.hide ();
					crnDiv.hide ();
					xmlDiv.show ();
					
					$(".bivesTab").each (function () {$(this).removeClass ("bivesTabSelected");});
					xmlLink.addClass ("bivesTabSelected");
				});
				if (!shown)
					xmlLink.click ();
				shown = true;
			}
			
			if (!shown)
				diffDiv.append ("server didn't return any diff");
			
			
		}
		else
			diffs[matrixKey].empty ().append ("failed to compute the differences");
	}).fail (function () 
	{
		diffs[matrixKey].empty ().append ("failed to compute the differences");
	});
};

bivesDiffer.prototype.showDiff = function ()
{
	if (this.laterFile && this.formerFile)
	{
		var matrixKey = this.formerFile.entityLink.name + "--" + this.formerFile.entityLink.version + "--" + this.laterFile.entityLink.name + "--" + this.laterFile.entityLink.version;
		if (!this.diffs[matrixKey])
		{
			// compute the diff and show it afterwards
			this.diffs[matrixKey] = $("<div></div>").html ("<img src='"+contextPath+"/res/img/loading2-new.gif' alt='loading' /> calling BiVeS to compute the differences");
			this.computeDifferences (this.formerFile, this.laterFile, matrixKey);
		}

		// show diff
		this.displayer.empty ().append (this.diffs[matrixKey]);
	}
};

bivesDiffer.prototype.getContentsCallback = function (succ)
{
	
};

bivesDiffer.prototype.show = function ()
{
	
};


function bivesDiffContent ()
{
    this.name = "displayBivesDiff";
    this.icon = "displayBivesDiff.png";
    this.description = "use BiVeS to compare versions";

	addLink (contextPath + "/res/js/visualizers/displayBivesDiff/graphene-sems/graphene.css");
  	addScript (contextPath + "/res/js/visualizers/displayBivesDiff/graphene-sems/fda44d5a.vendor.js");
  	addScript (contextPath + "/res/js/visualizers/displayBivesDiff/graphene-sems/11726d3b.scripts.js");
};

bivesDiffContent.prototype.canRead = function (file)
{
	var allowedExt = [
	                  "xml",
	                  "cellml",
	                  "sbml"
	                  // to be extended?
	                  ];
	
	for (var i = 0; i < allowedExt.length; i++)
		if (file.name.endsWith(allowedExt[i]))
			return true;
	
	return false;
};

bivesDiffContent.prototype.getName = function ()
{
    return this.name;
};

bivesDiffContent.prototype.getIcon = function ()
{
    return this.icon;
};

bivesDiffContent.prototype.getDescription = function ()
{
    return this.description;
};

bivesDiffContent.prototype.setUpComparision = function (files, div)
{
    return new bivesDiffer (files, div);
};


function initbivesDiffContent ()
{
    visualizers["displayBivesDiff"] = new bivesDiffContent ();
}

document.addEventListener("DOMContentLoaded", initbivesDiffContent, false);