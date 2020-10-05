var showdown = require('showdown');
var notifications = require('./lib/notifications.js');
var utils = require('./lib/utils.js')
var expt_common = require('./expt_common.js');

var versions = {},
  files = {},
  doc,
  basicurl,
  compareType, allComparisonsUrl,
  entityId,
  curVersion = null,
  converter = new showdown.Converter(),
  filesTable = {};

function init() {
  var plugins = [
    //require('./visualizers/displayBivesDiff/displayBivesDiff.js'),
    require('./visualizers/displayContent/displayContent.js'),
    require('./visualizers/displayPlotFlot/displayPlotFlot.js'),
    require('./visualizers/displayPlotHC/displayPlotHC.js'),
    require('./visualizers/displayTable/displayTable.js'),
    //require('./visualizers/displayUnixDiff/displayUnixDiff.js'),
    //require('./visualizers/editMetadata/editMetadata.js'),
  ];

  var visualizers = {};

  // Handle selecting a linked dataset to overlay
  function load_linked_dataset(dataset_json_url) {
    if (dataset_json_url) {
      $.getJSON(dataset_json_url, function(json) {
        dataset_json = json.version;
        $('#dataset-link').data({json: dataset_json, file: null});
        for (var i=0; i<dataset_json.files.length; i++)
        {
          if (dataset_json.files[i].name.endsWith('.csv'))
          {
            $.get(dataset_json.files[i].url, function(data) {
              dataset_file = {contents: data};
              utils.parseCsvRaw(dataset_file);
              $('#dataset-link').data('file', dataset_file);
              var viz = $('#dataset-link').data("viz");
              console.log(viz);
              if (viz) viz.redraw();
            });
            break;
          }
        }
      });
    }
    else
    {
      $('#dataset-link').data({json: null, file: null});
      var viz = $('#dataset-link').data("viz");
      console.log(viz);
      if (viz) viz.redraw();
    }
  }
  // Load initial dataset, if any
  load_linked_dataset($('#dataset-link').val());
  // Load dataset on select change
  $('#dataset-link').on('change', function () {
    load_linked_dataset(this.value);
  });

  function updateVisibility (jsonObject, actionIndicator) {
    actionIndicator.innerHTML = "<img src='"+staticPath+"/res/img/loading2-new.gif' alt='loading' />";

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
      //console.log (json);
      notifications.display(json);

      if(xmlhttp.status == 200)
      {
        if (json.updateVisibility)
        {
          var msg = json.updateVisibility.responseText;
          if (json.updateVisibility.response)
          {
            actionIndicator.innerHTML = "<img src='"+staticPath+"/res/img/check.png' alt='valid' /> " + msg;
            var v = versions[jsonObject.version];
            $("#version-item-" + v.id)
              .removeClass("entityviz-" + v.visibility)
              .addClass("entityviz-" + jsonObject.visibility)
              .attr("title", function (index, oldTitle) {
                return oldTitle.replace(/Visibility: (\w+)/, "Visibility: " + jsonObject.visibility);
              });
            v.visibility = jsonObject.visibility;
          }
          else
            actionIndicator.innerHTML = "<img src='"+staticPath+"/res/img/failed.png' alt='invalid' /> " + msg;
        }
      }
      else
      {
        actionIndicator.innerHTML = "<img src='"+staticPath+"/res/img/failed.png' alt='error' /> sorry, serverside error occurred.";
      }
    };
    xmlhttp.send (JSON.stringify (jsonObject));
  }


  function deleteEntity (jsonObject) {
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
      notifications.display(json);

      if (xmlhttp.status == 200)
      {
        var resp = json.deleteVersion || json.deleteEntity;
        if (resp)
        {
          var msg = resp.responseText;
          if (resp.response)
          {
            addNotification(msg, "info");
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


  function highlightPlots (version, showDefault) {
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
    expt_common.sortTable (filesTable, plots);

    // If there were no graphs to show, but we do have an errors.txt file and want to show a default, then show the errors
    if (showDefault && version.errorsLink)
      nextPage(version.errorsLink, true); // 'Invisible' redirect
  }

  function parseOutputContents (file, version, showDefault) {
    version.outputContents = null; // Note that there is one to parse
    var goForIt = {
      getContentsCallback : function (succ) {
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

  function parsePlotDescription (file, version, showDefault) {
    if (file.plotDescription) // TODO: Always false => remove?
      return converter.makeHtml (file.contents);

    version.plotDescription = null; // Note that there is one to parse
    var goForIt = {
      getContentsCallback : function (succ) {
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

  function parseReadme (file, version) {
    if (file.contents)
      return converter.makeHtml (file.contents);

    var goForIt = {
      getContentsCallback : function (succ) {
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

  function displayVersion (versionId, showDefault) {
    var v = versions[versionId];

    //console.log(v);
    var dv = doc.version;
    dv.name.html("<small>Version: </small>" + v.name + " ");

    // If an experiment, show indication of status, perhaps including a note that we don't expect any results yet!
    //if (entityType == 'experiment')
    //{
    if (v.status == 'RUNNING' || v.status == 'QUEUED')
    {
      $('#running-experiment-note').show();
      $('#return-text').hide();
    }
    else
    {
      $('#running-experiment-note').hide();
      if (v.status == 'SUCCESS')
        $('#return-text').hide();
      else
        $('#return-text').show();
    }
    $('#exptStatus').text("Status: " + v.status + ".");
    //}

    if (dv.visibility)
    {
      // Show chooser for changing entity visibility
      dv.visibility = removeListeners (dv.visibility);

      document.getElementById("visibility-" + v.visibility).selected=true;

      dv.visibility.addEventListener("change", function () {
        /*console.log (v.id);
          console.log (dv.visibility.options[dv.visibility.selectedIndex].value);*/
        updateVisibility ({
          task: "updateVisibility",
          version: v.id,
          visibility: dv.visibility.options[dv.visibility.selectedIndex].value
        }, dv.visibilityAction);
      }, true);
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

    //if (entityType != "experiment" && ROLE.isAllowedToCreateNewExperiment)
    // {
    // Specify links to create new experiments using this model/protocol
    //   $(".runExpts").each(function (){this.href = staticPath + "/batch/" + entityType + "/" + utils.convertForURL (v.name) + "/" + v.id;});
    //}

    dv.author.innerHTML = v.author;
    dv.time.setAttribute ("datetime", v.created);
    dv.time.innerHTML = utils.beautifyTimeStamp(v.created);

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

    $(dv.details).toggle(v.files.length > 0);

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


      for (var vi in visualizers) {
        var viz = visualizers[vi];
        if (!viz.canRead (file))
          continue;
        var a = document.createElement("a");
        a.setAttribute("id", "filerow-" + file.name + "-viz-" + viz.getName ());
        a.href = basicurl + '/' + encodeURIComponent(file.name) + "/" + vi;
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

    if (!v.hasOwnProperty('outputContents') && !v.hasOwnProperty('plotDescription') && showDefault && v.errorsLink) {
      // If there are no output meta files, but there is an errors file, then we still want to display it.
      // So set an invisible redirect to happen once we're done here.
      window.setTimeout(function(){nextPage(v.errorsLink, true);}, 0);
    }

    /*
      if (v.experiments.length > 0)
      {
      var isProtocol = (entityType == "protocol"),
      $base_list = $(dv.experimentpartners).children("ul"),
      $parent_list = $base_list,
      $li = null;
      $base_list.contents().remove();
      allComparisonsUrl = "";
      for (var i = 0; i < v.experiments.length; i++)
      {
      var exp = v.experiments[i],
      href = staticPath + "/experiment/" + exp.model.id + exp.protocol.id + "/" + exp.id + "/latest",
      other = (isProtocol ? exp.model : exp.protocol),
      name = other.name + " @ " + other.version;
    // Figure out which list to add the next experiment to
    if ($li)
    {
    var lastOther = (isProtocol ? v.experiments[i-1].model : v.experiments[i-1].protocol)
    if (other.name == lastOther.name)
    {
    if ($parent_list == $base_list) // Nest a new sub-list within the last li
    $parent_list = $("<ul></ul>").appendTo($li);
    }
    else
    $parent_list = $base_list;
    }
    // Add a list item with checkbox & link for this experiment
    $li = $('<li><input type="checkbox" value="' + exp.id + '" /><a href="' + href + '">' + name + '</a></li>');
    $parent_list.append($li);
    if ($parent_list == $base_list)
    allComparisonsUrl += exp.id + "/";
    }
    // Show only latest versions by default
    $base_list.find("ul").hide();
    $("#entityexperimentlist_span_latest").hide();
    $("#entityexperimentlist_showallversions").removeClass("selected");

    dv.switcher.style.display = "block";
    if (dv.compareAll)
    dv.compareAll.style.display = "block";
    }
    else
    {
    dv.switcher.style.display = "none";
    dv.experimentpartners.style.display = "none";
    if (dv.compareAll)
    dv.compareAll.style.display = "none";
    dv.details.style.display = "block";
    }
    */

    $(dv.readme).empty();
    if (v.readme) {
      dv.readme.innerHTML = v.readme;
      dv.readme.style.display = "block";
    }
    else {
      dv.readme.style.display = "none";
    }
    if (v.plotDescription && v.outputContents) {
      highlightPlots (v, showDefault);
    }

    // Items related to a protocol's interface
    $('#parse_status').empty();
    if (v.parsedOk) {
      //$('#parse_status').append('<small>All ' + entityType + ' files parsed successfully.</small>');
    }

    $('#updateInterface').off('click').click(function(){
      $.post(document.location.href, JSON.stringify({'task': 'updateInterface', 'version': v.id}))
        .done(function(json){
          notifications.display(json);
        })
      .fail(function(){
        addNotification("sorry, server-side error occurred", "error");
      });
    });

    doc.entity.details.style.display = "none";
    doc.entity.version.style.display = "block";

    doc.version.files.style.display = "block";
    $("#experiment-files-switcher-files").addClass("selected");
    $("#experiment-files-switcher-exp").removeClass("selected");
  }

  function registerFileDisplayer (elem) {
    elem.addEventListener("click", function (ev) {
      if (ev.which == 1) {
        ev.preventDefault();
        nextPage (elem.href);
      }
    }, true);
  }

  function updateVersion (rv) {
    var v = versions[rv.id];
    if (!v)
    {
      v = new Array ();
      versions[rv.id] = v;
    }

    v.name = rv.name;
    v.author = rv.author;
    v.created = rv.created;
    v.visibility = rv.visibility;
    v.download_url = rv.download_url;
    v.id = rv.id;
    v.status = rv.status;
    v.commitMessage = rv.commitMessage;
    v.readme = null;
    v.parsedOk = rv.parsedOk;
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
  function addNewVersion(id, url) {
    requestInformation ({
      task: "getInfo",
      version: id
    }, function () {
      console.log("New info got"); console.log(versions); console.log(id);
      var v = versions[id],
      // deleteLink = ' <a id="deleteVersion-' + v.id + '" class="deleteVersionLink"><img src="' + staticPath + '/res/img/delete.png" alt="delete version" title="delete this version of the ' + entityType + '" /></a>',
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
      utils.beautifyTimeStamps();
    });
  }


  function updateFile (rf, v) {
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
    //	f.url = '/experiments/' + v.entity_id + "/" + v.id + "/" + f.id + "/" + utils.convertForURL (f.name);
    f.div = {};
    f.viz = {};
    f.contents = null;
    f.getContents = function (callBack)
    {
      if (!f.contents) {
        //console.log ("missing file contents. calling for: " + f.id);
        utils.getFileContent (f, callBack);
      } else {
        utils.getFileContent (f, callBack);
      }
    };
  }

  zoom_property_names = ['position', 'top', 'left', 'border-style', 'border-width', 'background-color'];
  function zoomHandler() {
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

  function displayFile (id, pluginName) {
    if (id && pluginName) {
      doc.file.close.href = basicurl;

      var f = files[id];
      if (!f) {
        addNotification ("no such file", "error");
        return;
      }
      var df = doc.file;
      df.name.innerHTML = "<small>File: </small>" + f.name;
      df.time.setAttribute ("datetime", f.created);
      df.time.innerHTML = utils.beautifyTimeStamp (f.created);
      df.author.innerHTML = f.author;

      if (!f.div[pluginName]) {
        f.div[pluginName] = document.createElement("div");
        f.viz[pluginName] = visualizers[pluginName].setUp (f, f.div[pluginName]);
      }
      $(df.display).empty();
      df.display.appendChild (f.div[pluginName]);
      f.viz[pluginName].show ();
      // Let dataset link know we've initialised a plot
      $('#dataset-link').data("viz", f.viz[pluginName]);

      // Show parent div of the file display, and scroll there
      doc.version.filedetails.style.display = "block";
      var pos = utils.getPos (doc.version.filedetails);
      window.scrollTo(pos.xPos, pos.yPos);
    }
    else {
      doc.version.filedetails.style.display = "none";
      $('#dataset-link').data("viz", null);
    }
  }

  function requestInformation (url, onSuccess) {
    // TODO: loading indicator.. so the user knows that we are doing something
    $.getJSON(url, function(data) {
      notifications.display (data);
      if (data.version) {
        var rv = data.version;
        updateVersion (rv);
        onSuccess();
      }
    });
  }

  /*
  * Note that if the 'replace' argument is not supplied, it in effect defaults to false
  */
  function nextPage (url, replace) {
      if (replace)
          window.history.replaceState(document.location.href, "", url);
      else
          window.history.pushState(document.location.href, "", url);

      render();
  }

  function render() {
    basicurl = $('#entityversion').data('version-href');
    var url = document.location.pathname.substr(basicurl.length + 1);
    var parts = url.split('/')
    var fileName = parts[0];
    var pluginName = parts[1];

    console.log ("fileName  " + fileName);
    console.log ("pluginName " + pluginName);

    basicurl = $('#entityversion').data('version-href');
    var jsonUrl = $('#entityversion').data('version-json-href');

    if (curVersion) {
      displayFile(fileName, pluginName);
    } else {
      $.getJSON(jsonUrl, function(data) {
        notifications.display (data);
        if (data.version) {
          curVersion = data.version;
          updateVersion (curVersion);
          displayVersion (curVersion.id, !(fileName && pluginName));
          displayFile(fileName, pluginName);
        }
      });
    }

    //}
    /*
      else
      {
      if (url.length > 0 && url[0] == "latest")
      {
    // The 'return false' means we only follow the first matching link
    $(".entityversionlink").each(function (){nextPage ($(this).attr('href'), true); return false;});
    }
    doc.entity.version.style.display = "none";
    doc.entity.details.style.display = "block";
    curVersion = null;
    }
    */
  }

  function deleteVersionCallback() {
    if (confirm("Are you sure to delete this version? (including all files and experiments associated to it)"))
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
      name : $("#entityversionname"),
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
    },
    file: {
      close : document.getElementById("entityversionfileclose"),
      name : document.getElementById("entityversionfilename"),
      time : document.getElementById("entityversionfiletime"),
      author : document.getElementById("entityversionfileauthor"),
      display : document.getElementById("entityversionfiledisplay")
    }
  };

  window.onpopstate = render;
  render ();

  $("#experiment-files-switcher-exp").click(function () {
    $("#experiment-files-switcher-exp").addClass("selected");
    $("#experiment-files-switcher-files").removeClass("selected");
    doc.version.details.style.display = "none";
    doc.version.experimentlist.style.display = "block";
  }, false);

  $("#experiment-files-switcher-files").click(function () {
    $("#experiment-files-switcher-files").addClass("selected");
    $("#experiment-files-switcher-exp").removeClass("selected");
    doc.version.experimentlist.style.display = "none";
    doc.version.details.style.display = "block";
  }, false);


  /*
     doc.version.close.href = basicurl;
     doc.version.close.addEventListener("click", function (ev) {
     if (ev.which == 1)
     {
     ev.preventDefault();
     curVersion = null;
     doc.entity.version.style.display = "none";
     doc.entity.details.style.display = "block";
     $(doc.version.visibilityAction).empty();
     nextPage (doc.version.close.href);
     }
     }, true);
     */

  doc.file.close.addEventListener("click", function (ev) {
    if (ev.which == 1)
    {
      ev.preventDefault();
      doc.version.filedetails.style.display = "none";
      doc.version.files.style.display = "block";
      $(doc.version.visibilityAction).empty();
      nextPage (doc.file.close.href);
    }
  }, true);
  $('#zoomFile').click(zoomHandler);

  var list = document.getElementById("entityversionlist");
  if (list)
    sortChildrenByAttribute (list, true, "title");


  var resubmit = document.getElementById("rerunExperiment");
  var resubmitAction = document.getElementById("rerunExperimentAction");
  if (resubmit && resubmitAction)
  {
    var resubmitHref = $(resubmit).data('href');
    resubmit.addEventListener("click", function (ev) {
      resubmitAction.innerHTML = "<img src='"+staticPath+"img/loading2-new.gif' alt='loading' />";
      var exp_ver = versions[curVersion.id],
          jsonObject = {
            rerun: exp_ver.id,
          };
      $.post(resubmitHref, jsonObject, function(data) {
        var msg = data.newExperiment.responseText;
        if (data.newExperiment.response)
        {
          notifications.add(msg, "info");
          resubmitAction.innerHTML = "<img src='"+staticPath+"img/check.png' alt='valid' /> " + msg;
        }
        else
        {
          notifications.add(msg, "error");
          resubmitAction.innerHTML = "<img src='"+staticPath+"img/failed.png' alt='invalid' /> " + msg;
        }
      }).fail(function() {
        notifications.add("Server-side error occurred submitting experiment.", "error");
      }).always(function(data) {
        notifications.display(data);
      });
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

  $(plugins).each(function(i, plugin) {
    visualizers[plugin.name] = plugin.get_visualizer()
  });
}

module.exports = {
  init: init,
}
