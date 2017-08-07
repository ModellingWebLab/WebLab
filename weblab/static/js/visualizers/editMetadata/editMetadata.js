
/**
 * Create the 'visualiser' portion of the plugin, responsible for displaying content within the div for this file.
 */
function metadataEditor(file, div)
{
    this.file = file;
    this.div = div;
    div.id = 'editmeta_main_div';
    this.loadedModel = false;
    this.loadedOntology = false;
    this.loadedFilters = false;
    // Set up main divs
    this.modelDiv = $('<div></div>', {id: 'editmeta_modelvars_div'}).text('loading model...');
    this.ontoDiv = $('<div></div>', {id: 'editmeta_ontoterms_div'});
    otherContent = '<div class="clearer">\n'
        + '<p><label for="versionname">Version:</label>\n'
        + '<input type="text" name="versionname" id="versionname" placeholder="Version Identifier"/>\n'
        + '<a class="pointer" id="dateinserter"><small>use current date</small></a>\n'
        + '<span id="versionaction"></span></p>\n'
        + '<p><label for="commitMsg">Commit Message:</label><br/>\n'
        + '<textarea cols="70" rows="3" name="commitMsg" id="commitMsg" placeholder="optional message to describe this commit"></textarea>\n'
        + '<span id="commitmsgaction"></span></p>\n'
        + '<p><input type="checkbox" name="reRunExperiments" id="reRunExperiments"/>\n'
        + '<label for="reRunExperiments">rerun experiments involving previous versions of this model</label>\n'
        + '<small>(this might take some time)</small></p>\n'
        + '<p><button id="savebutton">Save model annotations</button><span id="saveaction"></span></p>';
    this.dragDiv = $('<div></div>', {'class': 'editmeta_annotation', 'style': 'position: fixed;'});
    // Set up annotation filtering divs
	this.filterDiv = $('<div></div>', {id: 'editmeta_filter_div'}).text('loading filters...');
	this.mainAnnotDiv = $('<div></div>').text('loading available annotations...');
	this.filtAnnotDiv = $('<div></div>').hide();
	this.ontoDiv.append(this.filterDiv, this.mainAnnotDiv, this.filtAnnotDiv);
	// Add everything to the page
	$(div).append(this.modelDiv, this.ontoDiv, otherContent, this.dragDiv);
	this.initRdf();
};

/**
 * Check with the server whether properties of the new model version are OK.
 */
metadataEditor.prototype.verifyNewEntity = function (jsonObject, actionElem)
{
    actionElem.html("<img src='"+contextPath+"/res/img/loading2-new.gif' alt='loading' />");
    $.post(contextPath + '/model/createnew', JSON.stringify(jsonObject))
        .done(function (json) {
            displayNotifications(json);
            if (json.versionName)
            {
                var msg = json.versionName.responseText;
                if (json.versionName.response)
                    actionElem.html("<img src='"+contextPath+"/res/img/check.png' alt='valid' /> " + msg);
                else
                    actionElem.html("<img src='"+contextPath+"/res/img/failed.png' alt='invalid' /> " + msg);
            }
        })
        .fail (function () {
            actionElem.html("<img src='"+contextPath+"/res/img/failed.png' alt='error' /> sorry, serverside error occurred.");
        });
}

/**
 * If our required libraries are not yet present, wait until they are then call the callback.
 * Returns true iff a wait is needed.
 */
function waitForLibraries (self, callback, timeout)
{
    timeout = timeout || 150;
    if (self.rdf === undefined || $.ui === undefined)
    {
        console.log("Waiting for libraries to load.");
        window.setTimeout(callback, timeout);
        return true;
    }
    return false;
}

/**
 * Initialisation that depends on rdfQuery being available; waits until it is before proceeding.
 */
metadataEditor.prototype.initRdf = function ()
{
    if ($.rdf === undefined)
    {
        var self = this;
        /// Wait 0.1s for rdfquery to load and try again
        console.log("Waiting for rdfquery to load.");
        window.setTimeout(function(){self.initRdf();}, 100);
        return;
    }
    this.modelBaseUri = $.uri.absolute(window.location.protocol + '//' + window.location.host + this.file.url);
    this.modelRdf = $.rdf({base: this.modelBaseUri})
                     .prefix('bqbiol', 'http://biomodels.net/biology-qualifiers/')
                     .prefix('oxmeta', 'https://chaste.comlab.ox.ac.uk/cellml/ns/oxford-metadata#')
                     .prefix('rdfs', 'http://www.w3.org/2000/01/rdf-schema#');
    this.ontoRdf = $.rdf()
                    .prefix('bqbiol', 'http://biomodels.net/biology-qualifiers/')
                    .prefix('oxmeta', 'https://chaste.comlab.ox.ac.uk/cellml/ns/oxford-metadata#')
                    .prefix('rdfs', 'http://www.w3.org/2000/01/rdf-schema#');
    this.rdf = $.rdf()
                .prefix('bqbiol', 'http://biomodels.net/biology-qualifiers/')
                .prefix('oxmeta', 'https://chaste.comlab.ox.ac.uk/cellml/ns/oxford-metadata#')
                .prefix('rdfs', 'http://www.w3.org/2000/01/rdf-schema#')
                .add(this.modelRdf)
                .add(this.ontoRdf);
}

/**
 * This is called when the file to be edited has been fetched from the server,
 * and parses it and sets up the editing UI.
 */
metadataEditor.prototype.getContentsCallback = function (succ)
{
    var self = this;
    if (!succ)
        this.modelDiv.text("failed to load the contents");
    else
    {
        if (waitForLibraries(self, function(){self.getContentsCallback(true);}))
            return;
        console.log("Model loaded");
        this.loadedModel = true;
        this.model = $.parseXML(this.file.contents);
        var $model = $(this.model);
        this.modelDiv.empty();

        // Find the variables that can be annotated, and display as a nested list in their components
        var components = $model.find("component"),
            var_list = document.createElement("ul");
        this.components = {};
        this.vars_by_name = {};
        this.vars_by_uri = {};
        components.each(function() {
            // Store component info and create display items
            var li = document.createElement("li"),
                clist = document.createElement("ul"),
                c = {li: li, ul: clist, elt: this, name: this.getAttribute('name'), vars: []};
            self.components[c.name] = c;
            li.innerHTML = '<span class="editmeta_cname editmeta_content_hidden">' + c.name + '</span>';
            li.appendChild(clist);
            var_list.appendChild(li);
            // Toggle display of this component's variables on click of the component name
            $('span', li).click(function (ev) {
                $(clist).toggle();
                $(this).toggleClass("editmeta_content_shown editmeta_content_hidden");
            });
            $(clist).hide();
            // Find variables in this component
            $(this).children('variable[public_interface != "in"][private_interface != "in"]').each(function() {
                var li = $('<li></li>'),
                    v = {li: li, elt: this, name: this.getAttribute('name'), cname: c.name,
                         metaid: this.getAttributeNS("http://www.cellml.org/metadata/1.0#", "id"),
                         annotations: {}};
                c.vars.push(v);
                v.fullname = c.name + ':' + v.name;
                self.vars_by_name[v.fullname] = v;
                if (v.metaid)
                {
                    v.uri = self.modelBaseUri.toString() + '#' + v.metaid;
                    self.vars_by_uri[v.uri] = v;
                }
                li.html('<span class="editmeta_vname">' + v.name + '</span>');
                clist.appendChild(li.get(0));
                li.droppable({
                    drop: function (event, ui) {
                        console.log("Adding annotation " + ui.helper.data('bindings').ann + " on " + v.fullname);
                        self.addAnnotation(v, ui.helper.data('bindings'));
                    }
                });
            });
        });
        console.log("Found " + keys(this.vars_by_name).length + " variables");
        this.modelDiv.append("<h4>Model variables</h4>", var_list);

        // Find the existing annotations
        var rdf_nodes = this.model.getElementsByTagNameNS("http://www.w3.org/1999/02/22-rdf-syntax-ns#", "RDF"),
            rdf = this.modelRdf;
        console.log("Found " + rdf_nodes.length + " RDF nodes");
        $(rdf_nodes).each(function () {
            var doc_type = document.implementation.createDocumentType("RDF", "", ""),
                new_doc = document.implementation.createDocument("http://www.w3.org/1999/02/22-rdf-syntax-ns#", "RDF", doc_type);
            $(this).children().each(function(){
                var new_elt = new_doc.adoptNode(this);
                new_doc.documentElement.appendChild(new_elt);
                new_doc.documentElement.setAttributeNS('http://www.w3.org/XML/1998/namespace', 'base', rdf.base());
            });
            rdf.load(new_doc, {});
        });
        console.log("Found " + rdf.databank.size() + " triples");
//        console.log(rdf);
        
        // If ontology is available too, set up linking functionality
        if (this.loadedOntology)
            this.ready();
    }
};

/**
 * Add a new annotation to a variable.
 * The bindings object should contain at least 'ann', and optionally 'label' and 'comment'.
 * Duplicate annotations will be ignored.
 */
metadataEditor.prototype.addAnnotation = function (v, bindings)
{
	var term = bindings.ann.value.toString();
    if (v.annotations[term] !== undefined)
    {
        console.log("Ignoring duplicate annotation " + bindings.ann + " on " + v.fullname);
        return;
    }
    var self = this,
        s = $('<span></span>', {'class': 'editmeta_annotation editmeta_spaced'}),
        title = 'Use oxmeta:' + bindings.ann.value.fragment + ' to refer to this variable in a protocol.',
        del = $('<img>', {src: contextPath + '/res/img/delete.png',
                          alt: 'remove this annotation',
                          title: 'remove this annotation',
                          'class': 'editmeta_spaced pointer'});
    s.text(bindings.label === undefined ? bindings.ann.value.fragment : bindings.label.value);
    s.data('term', term);
    s.append(del);
    if (bindings.comment !== undefined)
    	title = bindings.comment.value + " \n" + title;
    s.attr('title', title);
    v.annotations[term] = {ann: bindings.ann, span: s};
    v.li.append(s);
    // Add to the RDF store, creating a unique cmeta:id for the variable if needed
    if (v.uri === undefined)
    {
        v.metaid = v.cname + '_' + v.name;
        while (self.vars_by_uri[self.modelBaseUri.toString() + '#' + v.metaid] !== undefined)
            v.metaid += '_';
        v.elt.setAttributeNS("http://www.cellml.org/metadata/1.0#", "id", v.metaid);
        v.uri = self.modelBaseUri.toString() + '#' + v.metaid;
        self.vars_by_uri[v.uri] = v;
    }
    var triple = '<' + v.uri + '> bqbiol:is ' + bindings.ann;
    self.modelRdf.add(triple);
    // Add the handler for deleting this annotation
    del.click(function (ev) {
//        console.log("Removing annotation: <" + v.uri + '> bqbiol:is ' + bindings.ann);
        delete v.annotations[term];
        self.modelRdf.remove('<' + v.uri + '> bqbiol:is ' + bindings.ann);
        s.remove();
        $('li.editmeta_annotation').each(function() {
        	var $this = $(this);
        	if ($this.data('term') == term)
        	{
        		$this.removeClass('editmeta_annotation_used');
        		$this.removeAttr('title');
        		if (bindings.comment !== undefined)
        	        $this.attr('title', bindings.comment.value);
        	}
        });
    });
    // Show in the annotations pane that this term has been used
    $('li.editmeta_annotation').each(function() {
    	var $this = $(this);
    	if ($this.data('term') == term)
    	{
    		$this.addClass('editmeta_annotation_used');
    		$this.attr('title', 'This term has been used');
    	}
    });
}

/**
 * Called when both the model and Oxford metadata ontology have been loaded and parsed.
 * Adds details of the existing variable annotations to the UI.
 */
metadataEditor.prototype.ready = function ()
{
    var self = this;
    console.log("Ready!");
    this.rdf.where('?v bqbiol:is ?ann')
            .optional('?ann rdfs:label ?label')
            .optional('?ann rdfs:comment ?comment')
            .each(function(i, bindings, triples) {
                 var v = self.vars_by_uri[bindings.v.value.toString()];
                 if (v === undefined)
                     console.log("Annotation of non-existent id! " + bindings.v + " is " + bindings.ann);
                 else
                     self.addAnnotation(v, bindings);
            });
}

/**
 * Helper function for ontologyLoaded().
 * Given a parent HTML element (as a jQuery object) and an rdfQuery collection representing the members of a Category
 * in our ontology, create an unordered list representation of these members (if there are any) and append it to the parent.
 * We recurse for any members that are not Annotations, since these represent sub-categories.
 * 
 * @param acceptableUris  a 'set' of URIs that are allowed to appear in the list, used to filter the annotations displayed so only
 *     those used by particular protocols appear.  (It's actually an object with the terms as keys.)
 * @return  the ul element containing the list of annotations (as a jQuery object)
 */
metadataEditor.prototype.fillCategoryList = function (parent, rdf_, acceptableUris)
{
	if (rdf_.length > 0)
	{
		var self = this,
			ul = $('<ul></ul>'),
			rdf = rdf_.optional('?ann rdfs:label ?label').optional('?ann rdfs:comment ?comment'),
			annotations = rdf.where('?ann a oxmeta:Annotation');
		parent.append(ul);
//		console.log("Number of annotations: " + annotations.length);
//		console.log("Number of categories: " + rdf.except(annotations).length);
		// First, process sub-categories
		rdf.except(annotations).each(function (i, bindings, triples) {
			var li = $('<li></li>').addClass("editmeta_category"),
				span = $('<span></span>').addClass("editmeta_category_name editmeta_content_hidden");
			span.text(bindings.label === undefined ? bindings.ann.value.fragment : bindings.label.value);
			if (bindings.comment !== undefined)
				span.attr('title', bindings.comment.value);
			li.append(span);
			ul.append(li);
			// Process the sub-category's members
			self.fillCategoryList(li, self.rdf.where('?ann a ' + bindings.ann.toString()), acceptableUris);
			// If there were no members, don't show the category
			if (li.find("li").length == 0)
			{
				li.remove();
			}
			else
			{
				// Toggle display of the sub-category's members on click of the category name
				span.click(function (ev) {
					var $this = $(this);
					$this.toggleClass("editmeta_content_shown editmeta_content_hidden");
					$this.next().toggle();
				});
				span.next().hide();
			}
		});
		// Second, process annotations
		annotations.each(function (i, bindings, triples) {
			if (acceptableUris !== undefined && acceptableUris.indexOf(bindings.ann.value.toString()) == -1)
				return; // Skip this annotation; it does not appear in the filter
			var li = $('<li></li>').addClass("editmeta_annotation");
			li.text(bindings.label === undefined ? bindings.ann.value.fragment : bindings.label.value);
			li.data('term', bindings.ann.value.toString());
			if (bindings.comment !== undefined)
				li.attr('title', bindings.comment.value);
			self.terms.push({uri: bindings.ann.value, li: li});
			ul.append(li);
			li.draggable({
				containment: self.div,
				cursor: 'move',
				helper: function (event) {
					self.dragDiv.text(li.text())
								.data('bindings', bindings);
					return self.dragDiv;
				},
				scroll: false
			});
		});
		// Finally, sort the list
		var items = ul.children('li').get();
		items.sort(function(a,b) { return $(a).text().localeCompare($(b).text()); });
		$.each(items, function(i, li) { ul.append(li); });
	}
}

/**
 * Callback function for when the Oxford metadata ontology has been fetched from the server.
 */
metadataEditor.prototype.ontologyLoaded = function (data, status, jqXHR)
{
    var self = this;
    if (waitForLibraries(self, function(){self.ontologyLoaded(data, status, jqXHR);}))
        return;
    console.log("Ontology loaded");
    this.loadedOntology = true;
    this.mainAnnotDiv.empty();

    // Parse XML
    this.ontoRdf.load(data, {});

    // Show available terms
    this.mainAnnotDiv.append("<h4>Available annotations</h4>");
    this.terms = [];
    this.fillCategoryList(this.mainAnnotDiv, this.rdf.where('?ann a oxmeta:Category'));

    // If model is available too, set up linking functionality
    if (this.loadedModel)
        this.ready();
}

/**
 * Callback function for when the filter data has been fetched from the server.
 */
metadataEditor.prototype.filtersLoaded = function (data, status, jqXHR)
{
    console.log("Interfaces loaded");
	this.filterDiv.empty();
	// Extract required & optional terms for each (visible) protocol.
	// This is an array of {name: string, optional: array, required: array}.
	if (data.interfaces === undefined)
	{
		this.filterDiv.append('Error loading filters');
		return;
	}
	this.protocolInterfaces = data.interfaces;
	this.protocolInterfaces.sort(function(p1,p2){ return p1.name.localeCompare(p2.name); });

	// Create the filter controls
	this.filterDiv.append('<h4 class="editmeta_content_hidden" id="editmeta_filter_header">Filter visible annotations</h4>\n'
			+ '<div id="editmeta_filter_content">\n'
			+ 'Show only terms used by:<br/>\n'
			+ '<input type="checkbox" name="all" id="editmeta_input_all" value="1"/><label for="editmeta_input_all"> any protocol</label><br/>\n'
			+ '</div>\n');
	var self = this,
		content_div = $('#editmeta_filter_content');
	for (var i=0; i<this.protocolInterfaces.length; i++)
	{
		var name = this.protocolInterfaces[i].name;
		content_div.append('<label><input type="checkbox" name="' + i + '" class="editmeta_input" value="1"/> "' + name + '" protocol</label><br/>\n');
	}
	content_div.append('<button style="float:left;" id="editmeta_filter_set">Filter annotations</button>\n'
			+ '<button style="margin-left:5px; float:left;" id="editmeta_filter_clear">Clear filters</button>\n'
			+ '<br style="clear:left;"/>');

	// Visibility toggle handler
	$('#editmeta_filter_header').click(function() {
		$(this).toggleClass("editmeta_content_shown editmeta_content_hidden");
		$('#editmeta_filter_content').toggle();
	});
	$('#editmeta_filter_content').hide();
	// Update selections if the 'all protocols' checkbox changes
	$('#editmeta_input_all').change(function() {
		$('.editmeta_input').prop('checked', $(this).prop('checked'));
	});

	// Handler that applies filters when requested
	$('#editmeta_filter_set').click(function() {
		// Figure out which terms are required/optional
		var required_terms = [], optional_terms = [];
		$('.editmeta_input:checked').each(function() {
			var iface = self.protocolInterfaces[this.name];
//			console.log(iface);
			for (var i=0; i<iface.required.length; i++)
			{
				term = iface.required[i];
				if (required_terms.indexOf(term) == -1)
					required_terms.push(term);
			}
			for (var i=0; i<iface.optional.length; i++)
			{
				term = iface.optional[i];
				if (optional_terms.indexOf(term) == -1)
					optional_terms.push(term);
			}
		});
//		console.log(required_terms);
//		console.log(optional_terms);
		// Create annotation lists accordingly
		self.mainAnnotDiv.hide();
		self.filtAnnotDiv.empty();
		self.filtAnnotDiv.append('<h4>Required annotations</h4>')
		self.fillCategoryList(self.filtAnnotDiv, self.rdf.where('?ann a oxmeta:Category'), required_terms);
		self.filtAnnotDiv.append('<h4>Optional annotations</h4>')
		self.fillCategoryList(self.filtAnnotDiv, self.rdf.where('?ann a oxmeta:Category'), optional_terms);
		self.filtAnnotDiv.show();
		// Shade those annotations that are already used
		$('span.editmeta_annotation').each(function() {
			var $span = $(this);
			$('li.editmeta_annotation').each(function() {
				var $li = $(this);
				if ($span.data('term') == $li.data('term'))
				{
					$li.addClass('editmeta_annotation_used');
					$li.attr('title', 'This term has been used');
				}
			});
		});
	});

	// Clear filters handler
	$('#editmeta_filter_clear').click(function() {
		self.filtAnnotDiv.hide();
		self.filtAnnotDiv.empty(); // No need to keep it around - will be recreated afresh if needed
		self.mainAnnotDiv.show();
	});
}

/**
 * Submit a new version of the model containing the metadata modifications.
 */
metadataEditor.prototype.saveNewVersion = function ()
{
    console.log('Save new version named "' + $('#versionname').val() + '"');
    var self = this,
        $div = $(this.div),
        actionElem = $('#saveaction');
    actionElem.html("<img src='"+contextPath+"/res/img/loading2-new.gif' alt='loading' />");

    // Remove original RDF from model
    $(this.model.getElementsByTagNameNS("http://www.w3.org/1999/02/22-rdf-syntax-ns#", "RDF")).remove();
    // Dump updated RDF back into the model, and serialize (with base URI omitted)
    var rdf_doc = this.modelRdf.databank.dump({format: 'application/rdf+xml', serialize: false});
    this.model.documentElement.appendChild(this.model.adoptNode(rdf_doc.documentElement));
    var model_str = new XMLSerializer().serializeToString(this.model.documentElement)
                                       .replace(new RegExp(this.modelBaseUri.toString(), 'g'), '');

    // Post the updated model file to the server; any other files comprising the model will be added
    // to the new version at that end.
    var data = {task: "updateEntityFile",
                entityId: entityId,
                entityName: $('#entityname span').text(),
                baseVersionId: curVersion.id,
                versionName: $('#versionname').val(),
                commitMsg: document.getElementById('commitMsg').value,
                rerunExperiments: document.getElementById('reRunExperiments').checked,
                fileName: this.file.name,
                fileContents: model_str
               };
//    console.log(data);
    $.post(contextPath + '/model/createnew', JSON.stringify(data))
        .done(function (json) {
            displayNotifications(json);
            var resp = json.updateEntityFile,
                msg = resp.responseText;
            if (resp.response)
            {
                clearNotifications("error"); // Get rid of any leftover errors from failed creation attempts
                $div.empty();
                var vers_href = contextPath + "/model/id/" + resp.entityId + "/version/" + resp.versionId,
                    expt_href = contextPath + "/batch/model/newVersion/" + resp.versionId;
                $div.append('<h1><img src="' + contextPath + '/res/img/check.png" alt="created version successfully" /> Congratulations</h1>'
                           +'<p>You\'ve just created a <a href="' + vers_href + '">new version of this model</a>!'
                           +(resp.expCreation ? '<p>Also, ' + resp.expCreation + '.</p>' : '')
                           +'<p><a href="' + expt_href + '">Run experiments</a> using this model.</p>'
                           );
                // Update the list of available versions with the newly created one, but don't change the display
				addNewVersion(resp.versionId, vers_href);
            }
            else
            {
                actionElem.html("<img src='"+contextPath+"/res/img/failed.png' alt='invalid' /> " + msg);
            }
        })
        .fail (function () {
            actionElem.html("<img src='"+contextPath+"/res/img/failed.png' alt='error' /> sorry, serverside error occurred.");
        });
}

/**
 * Called to generate the content for this visualiser plugin.
 * Mainly triggers a fetch of the file contents, with our getContentsCallback method doing the work when this completes.
 * But we also set up event handlers here, since our div's content isn't in the DOM until now.
 */
metadataEditor.prototype.show = function ()
{
    var self = this;
    if (!this.loadedModel)
        this.file.getContents(this);
    if (!this.loadedOntology)
        $.ajax(contextPath + '/res/js/visualizers/editMetadata/oxford-metadata.rdf',
               {dataType: 'xml',
                success: function(d,s,j) {self.ontologyLoaded(d,s,j);}
               });
	if (!this.loadedFilters)
		$.ajax(contextPath + '/protocol/get_interfaces',
				{method: 'post',
				 contentType : 'application/json; charset=utf-8',
				 data: JSON.stringify({task: 'getInterface'}),
				 dataType: 'json',
				 success: function(d,s,j) {self.filtersLoaded(d,s,j);}
				});

    // Initialise some event handlers
    $('#versionname').blur(function() {
        self.verifyNewEntity({
            task: "verifyNewEntity",
            entityName: $('#entityname span').text(),
            versionName: this.value
        }, $('#versionaction'));
    });
    $('#dateinserter').click(function() {
        $('#versionname').focus().val("Annotated on " + getYMDHMS(new Date())).blur();
    });
    $('#savebutton').click(function() {
        if (!$('#versionname').val())
            alert("You need to give the new model version a name.");
        else
            self.saveNewVersion();
    });
};



/**
 * A 'visualiser' plugin for editing the metadata in a CellML model.
 */
function editMetadata()
{
    this.name = "editMetadata";
    this.icon = "editMetadata.png";
    this.description = "edit the metadata annotations in this model";

    addScript(contextPath + "/res/js/3rd/jquery.rdfquery.core.min-1.0.js");
};

/**
 * Determine whether this plugin can be applied to the given file.
 * Checks whether the file is marked as CellML, or has a .cellml extension.
 */
editMetadata.prototype.canRead = function (file)
{
    if (file.type == 'CellML')
        return true;
    var ext = file.name.split('.').pop();
    return (ext == 'cellml');
};

/** Get the name of this plugin. */
editMetadata.prototype.getName = function ()
{
    return this.name;
};

/** Get the icon filename for displaying this plugin. */
editMetadata.prototype.getIcon = function ()
{
    return this.icon;
};

/** Get the brief description of this plugin. */
editMetadata.prototype.getDescription = function ()
{
    return this.description;
};

/**
 * Create the visualiser UI for a specific file, to display within the given div.
 * This must provide a show() method which will be called to generate the content.
 */
editMetadata.prototype.setUp = function (file, div)
{
    return new metadataEditor(file, div);
};

/**
 * Add ourselves to the available plugins for 'visualising' entities.
 */
function initEditMetadata ()
{
    visualizers["editMetadata"] = new editMetadata();
}

document.addEventListener("DOMContentLoaded", initEditMetadata, false);
