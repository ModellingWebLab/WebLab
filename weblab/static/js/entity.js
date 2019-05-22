var showdown = require('showdown');
var notifications = require('./lib/notifications.js');
var utils = require('./lib/utils.js')
var expt_common = require('./expt_common.js');
var plugins = [
  require('./visualizers/displayContent/displayContent.js'),
  require('./visualizers/editMetadata/editMetadata.js'),
];


var versions = {},
	files = {},
	doc,
	basicurl,
	entityType,
	compareType, allComparisonsUrl,
	entityId,
	curVersion = null,
	converter = new showdown.Converter(),
	filesTable = {};

var visualizers = {};

function init() {

  function updateVisibility (url, jsonObject)
  {
    var $actionIndicator = $(doc.version.visibilityAction);
    $actionIndicator.html("<img src='"+staticPath+"img/loading2-new.gif' alt='loading' />");
    
    $.post(
        url,
        jsonObject,
        function(json) {
          if (json.updateVisibility) {
            var msg = json.updateVisibility.responseText;
            if (json.updateVisibility.response) {
              $actionIndicator.html(
                  "<img src='"+staticPath+"img/check.png' alt='valid' /> " + msg);
              var v = versions[jsonObject.version];
              $("#version-item-" + v.id)
                .removeClass("entityviz-" + v.visibility)
                .addClass("entityviz-" + jsonObject.visibility)
                .attr("title", function (index, oldTitle) {
                  return oldTitle.replace(/Visibility: (\w+)/, "Visibility: " + jsonObject.visibility);
                });
              v.visibility = jsonObject.visibility;
            } else {
              $actionIndicator.html("<img src='"+staticPath+"img/failed.png' alt='invalid' /> " + msg);
            }
          }
        }
    ).fail(function() {
        $actionIndicator.html("<img src='"+staticPath+"img/failed.png' alt='error' /> sorry, serverside error occurred.");
    }).done(function(json){
        notifications.display(json);
    })
      .fail(function(){
        notifications.add("sorry, server-side error occurred", "error");
      });
  }

  function deleteEntity (jsonObject)
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
      
      xmlhttp.open ("POST", document.location.href, true);
      xmlhttp.setRequestHeader ("Content-type", "application/json");

      xmlhttp.onreadystatechange = function()
      {
          if(xmlhttp.readyState != 4)
            return;
          
        var json = JSON.parse(xmlhttp.responseText);
        notifications.display (json);
        
          if (xmlhttp.status == 200)
          {
              var resp = json.deleteVersion || json.deleteEntity;
              if (resp)
              {
                  var msg = resp.responseText;
                  if (resp.response)
                  {
                      notifications.add(msg, "info");
                      if (resp.entityRemains)
                      {
                          // Go back to version table
                          versions[jsonObject.version] = null;
                          $("#version-item-" + jsonObject.version).remove();
                          nextPage(basicurl);
                      }
                      else
                      {
                          // Entity is gone, so we'd get an error if we tried to display it!
                          doc.entity.details.style.display = "none";
                          doc.entity.version.style.display = "none";
                          $(".suppl").hide();
                      }
                  }
                  else
                      alert(msg);
              }
          }
          else
          {
            alert("sorry, serverside error occurred.");
          }
      };
      xmlhttp.send (JSON.stringify (jsonObject));
  }


  function highlightPlots (version, showDefault)
  {
    //console.log (plotDescription);
    // Plot description has fields: Plot title,File name,Data file name,Line style,First variable id,Optional second variable id,Optional key variable id
    // Output contents has fields: Variable id,Variable name,Units,Number of dimensions,File name,Type,Dimensions
    var plotDescription = version.plotDescription;
    var outputContents = version.outputContents;
    var plots = new Array ();
    for (var i = 1; i < plotDescription.length; i++)
    {
      if (plotDescription[i].length < 2)
        continue;
      //console.log (plotDescription[i][2]);
      var row = document.getElementById ("filerow-" + plotDescription[i][2].hashCode ());
          // Show the first plot defined by the protocol using flot, if there is one available
      if (row && showDefault)
      {
        var viz = document.getElementById ("filerow-" + plotDescription[i][2] + "-viz-displayPlotFlot");
        if (viz)
        {
            showDefault = false;
          nextPage(viz.href, true); // 'Invisible' redirect
        }
      }

      //console.log ("files: ")
      //console.log (version.files);
      for (var f = 0; f < version.files.length; f++)
      {
        if (files[version.files[f]].name == plotDescription[i][2])
        {
          // Find the plot x and y object names and units from the output contents file.
          for (var output_idx = 0; output_idx < outputContents.length; output_idx++)
          {
            if (plotDescription[i][4] == outputContents[output_idx][0])
            {
              files[version.files[f]].xAxes = outputContents[output_idx][1] + ' (' + outputContents[output_idx][2] + ')';
              files[version.files[f]].xUnits = outputContents[output_idx][2];
            }
            if (plotDescription[i][5] == outputContents[output_idx][0])
            {
              files[version.files[f]].yAxes = outputContents[output_idx][1] + ' (' + outputContents[output_idx][2] + ')';
              files[version.files[f]].yUnits = outputContents[output_idx][2];
            }
            if (plotDescription[i].length > 6 && plotDescription[i][6] == outputContents[output_idx][0])
            {
              files[version.files[f]].keyId = outputContents[output_idx][0];
              files[version.files[f]].keyName = outputContents[output_idx][1];
              files[version.files[f]].keyUnits = outputContents[output_idx][2];
              for (var fkey=0; fkey < version.files.length; fkey++)
              {
                if (files[version.files[fkey]].name == outputContents[output_idx][4])
                {
                  files[version.files[f]].keyFile = files[version.files[fkey]];
                }
              }
            }
          }
          files[version.files[f]].title = plotDescription[i][0];
          files[version.files[f]].linestyle = plotDescription[i][3];
        }
        //console.log ("file: ")
        //console.log (files[version.files[f]]);
      }
      
      plots.push (plotDescription[i][2]);
    }
    expt_common.sortTable (plots);
    
    // If there were no graphs to show, but we do have an errors.txt file and want to show a default, then show the errors
    if (showDefault && version.errorsLink)
        nextPage(version.errorsLink, true); // 'Invisible' redirect
  }

  function parseOutputContents (file, version, showDefault)
  {
      version.outputContents = null; // Note that there is one to parse
    var goForIt = {
      getContentsCallback : function (succ)
      {
        if (succ)
        {
            utils.parseCsvRaw(file);
          version.outputContents = file.csv;
                  if (version.plotDescription)
                      highlightPlots (version, showDefault);
        }
      }
    };
    utils.getFileContent (file, goForIt);
    
    return null;
  }

  function parsePlotDescription (file, version, showDefault)
  {
    if (file.plotDescription) // TODO: Always false => remove?
      return converter.makeHtml (file.contents);
    
    version.plotDescription = null; // Note that there is one to parse
    var goForIt = {
      getContentsCallback : function (succ)
      {
        if (succ)
        {
            utils.parseCsvRaw(file);
          version.plotDescription = file.csv;
          if (version.outputContents)
              highlightPlots (version, showDefault);
          
        }
      }
    };
    utils.getFileContent (file, goForIt);
    
    return null;
  }

  function parseReadme (file, version)
  {
    if (file.contents)
      return converter.makeHtml (file.contents);
    
    var goForIt = {
        getContentsCallback : function (succ)
        {
          if (succ)
          {
            version.readme = converter.makeHtml (file.contents);
            doc.version.readme.innerHTML = version.readme;
            doc.version.readme.style.display = "block";
          }
        }
    };
    utils.getFileContent (file, goForIt);
    
    return null;
  }

  function displayVersion (id, showDefault)
  {
    var v = versions[id];
    if (!v)
    {
      notifications.add ("no such version", "error");
      return;
    }
    //console.log(v);
    var dv = doc.version;
    dv.name.innerHTML = "<small>Version: </small>" + v.name + " ";
    
    // If an experiment, show indication of status, perhaps including a note that we don't expect any results yet!
    if (entityType == 'experiment')
    {
        if (v.status == 'RUNNING' || v.status == 'QUEUED')
            dv.exptRunningNote.style.display = "block";
        else
            dv.exptRunningNote.style.display = "none";
          dv.exptStatus.innerHTML = "Status: " + v.status + ".";
    }

    if (dv.deleteBtn)
    {
      dv.deleteBtn = removeListeners (dv.deleteBtn);
      
      dv.deleteBtn.addEventListener("click", function () {
        if (confirm("Are you sure to delete this version? (including all files and experiments associated to it)"))
        {
          deleteEntity ({
            task: "deleteVersion",
              version: v.id
          });
        }
      });
    }
    
    /*
      if (entityType != "experiment" && ROLE.isAllowedToCreateNewExperiment)
      {
          // Specify links to create new experiments using this model/protocol
          $(".runExpts").each(function (){this.href = contextPath + "/batch/" + entityType + "/" + convertForURL (v.name) + "/" + v.id;});
      }
      */
      
    dv.author.innerHTML = v.author;
    dv.time.setAttribute ("datetime", v.created);
    dv.time.innerHTML = utils.beautifyTimeStamp (v.created);
    
    $(dv.filestable).empty();
    filesTable = {};
    filesTable.table = dv.filestable;
    filesTable.plots = {};
    filesTable.pngeps = {};
    filesTable.otherCSV = {};
    filesTable.defaults = {};
    filesTable.text = {};
    filesTable.other = {};
    filesTable.all = new Array ();

    var tr = document.createElement("tr");
    var td = document.createElement("th");
    td.appendChild(document.createTextNode ("Name"));
    tr.appendChild(td);
    td = document.createElement("th");
    td.appendChild(document.createTextNode ("Type"));
    tr.appendChild(td);
    td = document.createElement("th");
    //td.colSpan = 2;
    td.appendChild(document.createTextNode ("Size"));
    tr.appendChild(td);
    td = document.createElement("th");
    td.appendChild(document.createTextNode ("Actions"));
    tr.appendChild(td);
    dv.filestable.appendChild(tr);
    
    for (var i = 0; i < v.files.length; i++)
    {
      var file = files[v.files[i]];
      tr = document.createElement("tr");
      tr.setAttribute("id", "filerow-" + file.name.hashCode());
      if (file.masterFile)
        tr.setAttribute("class", "masterFile");
      td = document.createElement("td");
      td.appendChild(document.createTextNode (file.name));
      tr.appendChild(td);
      td = document.createElement("td");
      td.appendChild(document.createTextNode (file.type.replace (/^.*identifiers.org\/combine.specifications\//,"")));
      tr.appendChild(td);
      
      var fsize = utils.humanReadableBytes (file.size).split (" ");
      td = document.createElement("td");
      td.appendChild(document.createTextNode (fsize[0] + " " + fsize[1]));
  //		td.setAttribute("class", "right");
      tr.appendChild(td);
  //		td = document.createElement("td");
  //		td.appendChild(document.createTextNode (fsize[1]));
  //		tr.appendChild(td);
      td = document.createElement("td");
      
      if (!v.readme && file.name.toLowerCase () == "readme.md")
        v.readme = parseReadme (file, v);
      
      if (!v.plotDescription && file.name.toLowerCase () == "outputs-default-plots.csv")
        parsePlotDescription (file, v, showDefault);
      
      if (!v.outputContents && file.name.toLowerCase () == "outputs-contents.csv")
        parseOutputContents (file, v, showDefault);
      

      filesTable.all.push ({
        name: file.name,
        row: tr
      });
      
      
      
      for (var vi in visualizers)
      {
        var viz = visualizers[vi];
        if (!viz.canRead (file))
          continue;
        var a = document.createElement("a");
        a.setAttribute("id", "filerow-" + file.name + "-viz-" + viz.getName ());
        a.href = basicurl + "/" + encodeURIComponent(file.name) + "/" + vi;
        var img = document.createElement("img");
        img.src = staticPath + "js/visualizers/" + vi + "/" + viz.getIcon ();
        img.alt = viz.getDescription ();
        img.title = img.alt;
        a.appendChild(img);
        registerFileDisplayer (a);
        td.appendChild(a);
        td.appendChild(document.createTextNode (" "));
        // Note how to default-display the errors.txt file, if there is one; the actual displaying
        // will be done by highlightPlots if no graphs are available.
        if (vi == "displayContent" && file.name.toLowerCase() == "errors.txt")
            v.errorsLink = a.href;
      }
      
      
      
      var a = document.createElement("a");
      a.href = file.url;
      img = document.createElement("img");
      img.src = staticPath + "img/download.png";
      img.alt = "download document";
      img.title = "download document";
      a.appendChild(img);
      td.appendChild(a);
      tr.appendChild(td);
      dv.filestable.appendChild(tr);
      dv.archivelink.href = v.download_url;
    }
    
    if (!v.hasOwnProperty('outputContents') && !v.hasOwnProperty('plotDescription') && showDefault && v.errorsLink)
    {
      // If there are no output meta files, but there is an errors file, then we still want to display it.
      // So set an invisible redirect to happen once we're done here.
      window.setTimeout(function(){nextPage(v.errorsLink, true);}, 0);
    }
    
    $(dv.readme).empty();
    if (v.readme)
    {
      dv.readme.innerHTML = v.readme;
          dv.readme.style.display = "block";
    }
    else
        dv.readme.style.display = "none";
    if (v.plotDescription && v.outputContents)
      highlightPlots (v, showDefault);
    
    // Items related to a protocol's interface
    $('#parse_status').empty();
    if (v.parsedOk)
    {
      $('#parse_status').append('<small>All ' + entityType + ' files parsed successfully.</small>');
    }
    $('#updateInterface').off('click').click(function(){
      $.post(document.location.href, JSON.stringify({'task': 'updateInterface', 'version': v.id}))
      .done(function(json){
        notifications.display(json);
      })
      .fail(function(){
        notifications.add("sorry, server-side error occurred", "error");
      });
    });
    
    doc.entity.details.style.display = "none";
    doc.entity.version.style.display = "block";

    doc.version.files.style.display = "block";
  }

  function registerFileDisplayer (elem)
  {
    elem.addEventListener("click", function (ev) {
      if (ev.which == 1)
      {
        ev.preventDefault();
        nextPage (elem.href);
      }
        }, true);
  }

  function updateVersion (rv)
  {
    var v = versions[rv.id];
    if (!v)
    {
      v = new Array ();
      versions[rv.id] = v;
    }
    
    v.name = rv.version;
    v.author = rv.author;
    v.created = rv.created;
    v.visibility = rv.visibility;
    v.id = rv.id;
    v.status = rv.status;
    v.commitMessage = rv.commitMessage;
    v.readme = null;
    v.parsedOk = rv.parsedOk;
    v.download_url = rv.download_url;
    v.files = [];
    if (rv.files)
      {
        for (var i = 0; i < rv.files.length; i++)
        {
            updateFile (rv.files[i], v);
            v.files.push (rv.files[i].id);
        }
      }
    v.experiments = [];
    if (rv.experiments)
      for (var i = 0; i < rv.experiments.length; i++)
      {
        v.experiments.push ({
          model: rv.experiments[i].model,
          protocol: rv.experiments[i].protocol,
          id: rv.experiments[i].id
        });
      }
    versions[v.id] = v;
  }

  /**
  * Get the full information about a newly created entity version, and add it to the local list.
  * @param id  version id
  * @param url  url to page for this version
  */
  function addNewVersion(id, url)
  {
      requestInformation ({
        task: "getInfo",
        version: id
    }, function () {
      console.log("New info got"); console.log(versions); console.log(id);
      var v = versions[id],
        deleteLink = ' <a id="deleteVersion-' + v.id + '" class="deleteVersionLink"><img src="' + contextPath + '/res/img/delete.png" alt="delete version" title="delete this version of the ' + entityType + '" /></a>',
        classes = 'entityviz-' + v.visibility + (v.status ? ' experiment-' + v.status : '');
      $("#entityversionlist_content").prepend(
          '<p id="version-item-' + v.id + '" title="' + v.created + ' -- Visibility: ' + v.visibility + '" class="' + classes + '">\n'
          + '<input type="checkbox" value="' + v.id + '" class="comparisonCheckBox"/>\n'
          + '<strong><a class="entityversionlink" href="' + url + '">' + v.name + '</a></strong>\n'
          + ' by <em>' + v.author + deleteLink + '</em>'
          + (v.commitMessage ? ' &mdash; <small>' + v.commitMessage + '</small>' : '')
          + '<br/>\n'
          + '<span class="suppl"><small>created </small> <time>' + v.created + '</time> '
          + '<small>containing</small> ' + v.files.length + ' file' + (v.files.length != 1 ? 's': '') + '.</span>\n'
          + '</p>\n').find('.deleteVersionLink').click(deleteVersionCallback);
      beautifyTimeStamps();
    });
  }

  function updateFile (rf, v)
  {
    var f = files[rf.id];
    if (!f)
    {
      f = {};
      files[rf.id] = f;
    }
    
    f.id = rf.id;
    f.created = rf.created;
    f.type = rf.filetype;
    f.author = rf.author;
    f.name = rf.name;
    f.masterFile = rf.masterFile;
    f.size = rf.size;
    f.url = rf.url;
    f.div = {};
    f.viz = {};
    f.contents = null;
    f.getContents = function (callBack)
    {
      if (!f.contents)
      {
        //console.log ("missing file contents. calling for: " + f.id);
        utils.getFileContent (f, callBack);
      }
      else
        utils.getFileContent (f, callBack);
    };
  }

  zoom_property_names = ['position', 'top', 'left', 'border-style', 'border-width', 'background-color'];
  function zoomHandler()
  {
      var $div = $(doc.version.filedetails),
          $button = $('#zoomFile'),
          curr_width = $div.width(),
          curr_css = $div.css(zoom_property_names),
          last_width = $div.data('zoom_width'),
          last_css = $div.data('zoom_css');
      if (last_width !== undefined)
      {
          // Reset to normal
          $div.css(last_css).width(last_width).removeData(['zoom_width', 'zoom_css']);
      }
      else
      {
          // Zoom to full-window
          $div.css({'position': 'absolute', 'top': 5, 'left': 5, 'border-style': 'ridge', 'border-width': 5, 'background-color': '#ffffff'})
              .width($(window).width()-40)
              .data({'zoom_width': curr_width, 'zoom_css': curr_css});
      }
  }

  function displayFile (id, pluginName)
  {
    if (id && pluginName) {
      doc.file.close.href = basicurl;

      var f = files[id];
      if (!f)
      {
        notifications.add ("no such file", "error");
        return;
      }
      var df = doc.file;
      df.name.innerHTML = "<small>File: </small>" + f.name;
      df.time.setAttribute ("datetime", f.created);
      df.time.innerHTML = utils.beautifyTimeStamp (f.created);
      df.author.innerHTML = f.author;

      if (!f.div[pluginName])
      {
        f.div[pluginName] = document.createElement("div");
        f.viz[pluginName] = visualizers[pluginName].setUp (f, f.div[pluginName]);
      }
      $(df.display).empty();
      df.display.appendChild (f.div[pluginName]);
      f.viz[pluginName].show ();

      // Show parent div of the file display, and scroll there
      doc.version.filedetails.style.display = "block";
      var pos = utils.getPos (doc.version.filedetails);
      window.scrollTo(pos.xPos, pos.yPos);
    } else {
      doc.version.filedetails.style.display = "none";
    }
  }

  function requestInformation (jsonObject, onSuccess)
  {
    // TODO: loading indicator.. so the user knows that we are doing something
      
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
          
          //console.log (xmlhttp.responseText);
        var json = JSON.parse(xmlhttp.responseText);
        //console.log (json);
        notifications.display (json);
        
          if(xmlhttp.status == 200)
          {
            
            if (json.version)
            {
              var rv = json.version;
              
              updateVersion (rv);
              onSuccess ();
            }
          }
      };
      xmlhttp.send(JSON.stringify(jsonObject));
  }

  /*
  * Note that if the 'replace' argument is not supplied, it in effect defaults to false
  */
  function nextPage (url, replace)
  {
      if (replace)
          window.history.replaceState(document.location.href, "", url);
      else
          window.history.pushState(document.location.href, "", url);

      render ();
  }


  function render ()
  {
    var curVersionId, fileName, pluginName;

    var parts = document.location.pathname.split("/")
    parts.forEach((part, i) => {
      if (part == 'versions') {
        basicurl = parts.slice(0, i+2).join('/');
        curVersionId = parts[i+1];
        fileName = parts[i+2];
        pluginName = parts[i+3];
      }
    });

    console.log(curVersion, fileName, pluginName);

    if (curVersion) {
      displayFile(fileName, pluginName);
    } else {
      var jsonUrl = $('#entityversion').data('version-json-href');
      $.getJSON(jsonUrl, function(data) {
        notifications.display(data);
        if (data.version) {
          curVersion = data.version;
          $('#entityversion').data('version-json', curVersion);
          triggerExperimentSubmission(curVersion.planned_experiments, false);
          updateVersion(curVersion);
          displayVersion(curVersion.id, !(fileName && pluginName));
          displayFile(fileName, pluginName);
        }
      });
    }
  }

  /**
   * Asynchronously submit a list of experiments to the front-end for execution on the task queue.
   * Will register a callback every 0.2s to submit the next experiment until they're all done,
   * so the UI doesn't freeze.
   * @param plannedExperiments  array of objects with keys model, model_version, protocol, protocol_version
   *     specifying the experiments to launch. May be empty.
   * @param submitNow  whether to submit a job now, or just register the first callback.
   */
  function triggerExperimentSubmission(plannedExperiments, submitNow)
  {
    if (plannedExperiments.length > 0 && submitNow)
    {
      // Submit the first planned experiment to the queue
      var exptSpec = plannedExperiments.pop();
      exptSpec["rerun"] = true;
      $.post('/experiments/new', exptSpec, function(data) {
        var msg = data.newExperiment.responseText;
        if (data.newExperiment.response)
          notifications.add(msg, "info");
        else
          notifications.add(msg, "error");
      }).fail(function() {
        notifications.add("Server-side error occurred submitting experiment.", "error");
      }).always(function(data) {
        notifications.display(data);
      });
    }
    if (plannedExperiments)
    {
      // Call this function again after a delay
      window.setTimeout(function(){triggerExperimentSubmission(plannedExperiments, true);}, 200);
    }
  }

  function deleteVersionCallback()
  {
    if (confirm("Are you sure you want to delete this version? (including all files and experiments associated to it)"))
    {
      deleteEntity({
        task: "deleteVersion",
          version: $(this).attr("id").replace("deleteVersion-", "")
      });
    }
  }


	doc = {
			entity : {
				details : document.getElementById("entitydetails"),
				version : document.getElementById("entityversion"),
				deleteBtn : document.getElementById("deleteEntity")
			},
			version : {
				close : document.getElementById("entityversionclose"),
				name : document.getElementById("entityversionname"),
				time : document.getElementById("entityversiontime"),
				author : document.getElementById("entityversionauthor"),
				details : document.getElementById("entityversiondetails"),
				files : document.getElementById("entityversionfiles"),
				filestable : document.getElementById("entityversionfilestable"),
				readme : document.getElementById("entityversionfilesreadme"),
				archivelink : document.getElementById("downloadArchive"),
				filedetails : document.getElementById("entityversionfiledetails"),
				experimentlist: document.getElementById("entityexperimentlist"),
				experimentpartners: document.getElementById("entityexperimentlistpartners"),
				visibility: document.getElementById("versionVisibility"),
				visibilityAction : document.getElementById("versionVisibilityAction"),
				deleteBtn: document.getElementById("deleteVersion"),
				exptRunningNote: document.getElementById("running-experiment-note"),
				exptStatus: document.getElementById("exptStatus")
			},
			file: {
				close : document.getElementById("entityversionfileclose"),
				name : document.getElementById("entityversionfilename"),
				time : document.getElementById("entityversionfiletime"),
				author : document.getElementById("entityversionfileauthor"),
				display : document.getElementById("entityversionfiledisplay")
			}
	};

  entityType = $(doc.version).data('entity-type');
  compareType = entityType == 'model' ? 'protocol' : 'model';
	
  if (doc.version.details) {
    window.onpopstate = render;
    render ();
  }

  var $visibility = $(doc.version.visibility);
  $visibility.on(
      'change',
      '#id_visibility',
      function() {
        updateVisibility (
            $visibility.data('change-href'),
            {
              version: curVersion.id,
              visibility: $(this).val(),
            })
      });

  $(doc.file.close).click(function (ev) {
    if (ev.which == 1)
    {
      ev.preventDefault();
      doc.version.filedetails.style.display = "none";
      doc.version.files.style.display = "block";
      $(doc.version.visibilityAction).empty();
      nextPage (doc.file.close.href);
    }
  });
  $('#zoomFile').click(zoomHandler);

	var list = document.getElementById("entityversionlist");
	if (list)
		sortChildrenByAttribute (list, true, "title");
	
	
	var resubmit = document.getElementById("rerunExperiment");
	var resubmitAction = document.getElementById("rerunExperimentAction");
	if (resubmit && resubmitAction)
	{
		resubmit.addEventListener("click", function (ev) {
			batchProcessing ({
				batchTasks : [{
					experiment : entityId
				}],
				force: true
			}, resubmitAction, addNewVersion);
		});
	}
    
	if (doc.entity.deleteBtn)
	{
		doc.entity.deleteBtn.addEventListener("click", function () {
			if (confirm("Are you sure to delete this entity? (including all versions, files, and experiments associated to it)"))
			{
				deleteEntity ({
					task: "deleteEntity",
			    	entity: entityId
				});
			}
		});
	}
	
	$(".deleteVersionLink").click(deleteVersionCallback);

	// Comparing experiments click events
  var $exp_list = $(doc.version.experimentpartners).children("ul");
  $("#entityexperimentlistpartnersactall").click(function () {
    $exp_list.find("input").filter(":visible").prop('checked', true);
  });
  $("#entityexperimentlistpartnersactnone").click(function () {
    $exp_list.find("input").prop('checked', false);
  });
  $("#entityexperimentlistpartnersactlatest").click(function () {
    $exp_list.children("li").children("input").prop('checked', true);
  });
	$("#entityexperimentlist_showallversions").click(function () {
		$(this).toggleClass("selected");
		$exp_list.find("ul").toggle();
		$("#entityexperimentlist_span_latest").toggle();
    return false;
	});
  $("#entityexperimentlistpartnersactcompare").click(function () {
    var url = $(this).data('base-href');
    $exp_list.find("input:checked").filter(":visible").each(function () {
      url += '/' + this.value;
    });
    if (url)
      document.location = url; //contextPath + "/compare/e/" + url;
    else
      window.alert("You need to select some " + compareType + "s to compare.");
  });
	
  $("#entityexperimentlist_span_latest").hide();

  $(plugins).each(function(i, plugin) {
    visualizers[plugin.name] = plugin.get_visualizer()
  });
}

module.exports = {
  init: init,
}
