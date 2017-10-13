var $ = require('jquery');
require('blueimp-file-upload');
var utils = require('./lib/utils.js')
var notifications = require('./lib/notifications.js');


/// Keep track of files sent to the server but not fully uploaded yet
var uploading = new Array();

// Names that aren't allowed to be uploaded
var reserved_names = ['errors.txt', 'manifest.xml', 'metadata.rdf'];

function alreadyExists (uploaded, name)
{
  for (var i = 0; i < uploading.length; i++) {
    if (uploading[i] == name) {
      console.log('already uploading', name);
      return true;
    }
  }
  for (var i = 0; i < uploaded.length; i++) {
    if (uploaded[i].fileName == name) {
      console.log('already uploaded', name);
      return true;
    }
  }
  return false;
}

function showUpload(uploaded, file, types) {
  var $table = $("#uploadedfiles");
  var $tr = $("<tr>").appendTo($table);

  var $td = $("<td>").appendTo($tr);
  $('<input type="radio" name="mainEntry" value="' + file.name + '" />').appendTo($td);
  $('<input type="hidden" name="filename[]" value="' + file.stored_name + '" />').appendTo($td);

  $td = $("<td>").appendTo($tr);
  var $name = $("<code>" + file.name + '</code>').appendTo($td);
  var $rm = $('<a><img src="' + staticPath + 'img/failed.png" alt="remove from list" /></a>').appendTo($td);

  $td = $("<td>").appendTo($tr);
  $('<small><code> ' + utils.humanReadableBytes(file.size) + ' </code></small>').appendTo($td);

  $td = $("<td>").appendTo($tr);
  var $action = $('<small></small>').appendTo($td);

  var array = {
    fileName: file.name,
    fileType: "unknown"
  };

  // Set default fileType based on extension, where sensible
  if (file.name.endsWith(".cellml"))
      array.fileType = "CellML";
  else if (file.name.endsWith(".txt"))
      array.fileType = "TXTPROTOCOL";
  else if (file.name.endsWith(".xml"))
      array.fileType = "XMLPROTOCOL";
  else if (file.name.endsWith(".zip") || name.endsWith(".omex"))
      array.fileType = "COMBINE archive";

  var $typeSelect = $("<select>");
  for (var i = 0; i < types.length; i++)
  {
    var $opt = $("<option>").appendTo($typeSelect);
    $opt.value = types[i];
    $opt.append(types[i]);
  }
  $typeSelect.val(array.fileType);

  $typeSelect.click(function () {
    array.fileType = $opt.options[$opt.selectedIndex].value;
  });

  $name.addClass("success");
  $action.html($typeSelect);
  uploaded.push(array);

  $rm.click(function () {
    for (var i = 0; i < uploaded.length; i++) {
      if (uploaded[i].fileName == name)
        uploaded.splice(i, 1);
    }
    for (var i = 0; i < uploading.length; i++) {
      if (uploading[i] == name)
        uploading.splice(i, 1);
    }
    /*
    if (xmlhttp) {
      xmlhttp.onreadystatechange = function ()
      {// need this cause some browsers will throw a 'done' which we cannot interpret otherwise };
      xmlhttp.abort();
    }
    */
    $tr.remove();
  });
}

	
/*
	var xmlhttp = null;
    progress_monitor = function(e)
    {
        var done = e.position || e.loaded;
        var total = e.totalSize || e.total;
        neuAction.innerHTML = (Math.floor(done/total*1000)/10) + "%";
    };
    xmlhttp.addEventListener('progress', progress_monitor, false);
    if ( xmlhttp.upload )
    {
        xmlhttp.upload.onprogress = progress_monitor;
    }
    
    xmlhttp.onreadystatechange = function(e)
    {
        if (xmlhttp.readyState != 4)
        	return;
    	var json = JSON.parse(xmlhttp.responseText);
    	if (json)
    		notifications.display (json);
        if (xmlhttp.status == 200 && json.upload && json.upload.response)
        {
        }
        else
        {
        	neuName.setAttribute("class", "failed");
        	neuAction.innerHTML = "failed, try again";
        }
        // Note that this file is no longer uploading
        for (var i = 0; i < uploading.length; i++)
            if (uploading[i] == name)
                uploading.splice(i, 1);
    };

}
    */



function initUpload(uploaded, types)
{
  $("#fileupload").fileupload({
    dataType: 'json',
    dropZone: $("#dropbox"),
    done: function(e, data) {
      $.each(data.result.files, function(index, file) {
        showUpload(uploaded, file, types);
      });
    },
    submit: function(e, data) {
      var name = data.files[0].name;

      if (alreadyExists(uploaded, name))
      {
        notifications.add("there is already a file with the name '" + name + "' - please remove that first.", "error");
        return false;
      }
      if (reserved_names.indexOf(name) != -1)
      {
        notifications.add("the name '" + name + "' is reserved for system use; please choose another file name.", "error");
        return false;
      }
      if (!/^[a-zA-Z0-9._]+$/.test(name))
      {
        notifications.add("the name '" + name + "' contains reserved characters; only alpha-numeric characters, underscores and periods are allowed.", "error");
        return false;
      }
      uploading.push(name);

      console.log('submit', e, data);
    }
  });

	$('#dropbox a').click(function() {
    $("#fileupload").click();
  });
}



module.exports = initUpload
