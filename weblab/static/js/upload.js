
/// Keep track of files sent to the server but not fully uploaded yet
var uploading = new Array();

// Names that aren't allowed to be uploaded
var reserved_names = ['errors.txt', 'manifest.xml', 'metadata.rdf'];

function alreadyExists (uploaded, name)
{
    for (var i = 0; i < uploading.length; i++)
        if (uploading[i] == name)
            return true;
	for (var i = 0; i < uploaded.length; i++)
		if (uploaded[i].fileName == name)
			return true;
	return false;
}


function sendFile (uploaded, file, name, types)
{
//    console.log("Send " + name);
	if (alreadyExists (uploaded, name))
	{
		addNotification ("there is already a file with the name '" + name + "' - please remove that first.", "error");
		return;
	}
	if (reserved_names.indexOf(name) != -1)
	{
		addNotification("the name '" + name + "' is reserved for system use; please choose another file name.", "error");
		return;
	}
	if (!/^[a-zA-Z0-9._]+$/.test(name))
	{
		addNotification("the name '" + name + "' contains reserved characters; only alpha-numeric characters, underscores and periods are allowed.", "error");
		return;
	}
	uploading.push(name);
	
	var table = document.getElementById("uploadedfiles");
	var neu = document.createElement("tr");
	table.appendChild(neu);
	
	var td = document.createElement("td");
	neu.appendChild(td);
	var mainEntry = document.createElement("input");
	mainEntry.type = "radio";
	mainEntry.name = "mainEntry";
	mainEntry.value = name;
	td.appendChild(mainEntry);
	

	td = document.createElement("td");
	neu.appendChild(td);
	var neuName = document.createElement("code");
	var neuRm = document.createElement("a");
	var neuRmPic = document.createElement("img");
	neuName.appendChild(document.createTextNode(name));
	neuRmPic.src = contextPath+"/res/img/failed.png";
	neuRmPic.alt = "remove from list";
	neuRm.appendChild (neuRmPic);
	td.appendChild (neuName);
	td.appendChild (neuRm);
	
	
	td = document.createElement("td");
	neu.appendChild(td);
	var neuSize = document.createElement("small");
	var neuSizeCode = document.createElement("code");
	neuSizeCode.appendChild (document.createTextNode(" "+humanReadableBytes(file.size)+" "));
	neuSize.appendChild (neuSizeCode);
	td.appendChild(neuSize);
	
	td = document.createElement("td");
	neu.appendChild(td);
	var neuAction = document.createElement("small");
	td.appendChild(neuAction);
	
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
    		displayNotifications (json);
        if (xmlhttp.status == 200 && json.upload && json.upload.response)
        {
        	var array = {
        		fileName: name,
        		tmpName: json.upload.tmpName,
        		fileType: "unknown"
        	};
        	
        	// Set default fileType based on extension, where sensible
        	if (name.endsWith(".cellml"))
        	    array.fileType = "CellML";
        	else if (name.endsWith(".txt"))
        	    array.fileType = "TXTPROTOCOL";
        	else if (name.endsWith(".xml"))
        	    array.fileType = "XMLPROTOCOL";
            else if (name.endsWith(".zip") || name.endsWith(".omex"))
                array.fileType = "COMBINE archive";
        	
        	var type = document.createElement("select");
        	for (var i = 0; i < types.length; i++)
        	{
        		var opt = document.createElement("option");
        		opt.value = types[i];
        		opt.appendChild (document.createTextNode(types[i]));
        		if (opt.value == array.fileType)
        		    opt.selected = true;
        		type.appendChild(opt);
        	}
        	type.addEventListener("click", function () {
        		array.fileType = type.options[type.selectedIndex].value;
        	}, true);

        	neuName.setAttribute("class", "success");
        	removeChildren (neuAction);
        	neuAction.appendChild (type);
        	uploaded.push (array);
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

	var fd = new FormData;
	fd.append('file', file);
	
	neuAction.innerHTML = "uploading";
	xmlhttp.open('post', contextPath + "/upload.html", true);
	xmlhttp.send(fd);
	
	neuRm.addEventListener("click", function () {
//        console.log("Remove " + name);
        for (var i = 0; i < uploaded.length; i++)
            if (uploaded[i].fileName == name)
                uploaded.splice(i, 1);
        for (var i = 0; i < uploading.length; i++)
            if (uploading[i] == name)
                uploading.splice(i, 1);
		if (xmlhttp)
		{
			xmlhttp.onreadystatechange = function ()
			    {/* need this cause some browsers will throw a 'done' which we cannot interpret otherwise */};
			xmlhttp.abort();
		}
		table.removeChild(neu);
	}, true);
}


function handleDragOver(evt) {
    evt.stopPropagation();
    evt.preventDefault();
    evt.dataTransfer.dropEffect = 'copy';
}


function initUpload(uploaded, types)
{
    /// Handler for file(s) being dropped on the upload pane
    function handleFileSelect(evt) {
        evt.stopPropagation();
        evt.preventDefault();
        evt.dataTransfer.dropEffect = 'copy';

        var files = evt.dataTransfer.files;
        for (var i = 0, f; f = files[i]; i++) {
            sendFile (uploaded, f, f.name, types);
        }
    }

    var inp = document.getElementById('fileupload');
	var dropZone = document.getElementById('dropbox');
	dropZone.addEventListener('dragenter', handleDragOver, false);
	dropZone.addEventListener('dragover', handleDragOver, false);
	dropZone.addEventListener('drop', handleFileSelect, false);
	dropZone.addEventListener("click", function (event) { inp.click (); }, false);
	inp.addEventListener('change', function(e) {
			var file = this.files[0];
			var fullPath = inp.value;
			var startIndex = (fullPath.indexOf('\\') >= 0 ? fullPath.lastIndexOf('\\') : fullPath.lastIndexOf('/'));
			var filename = fullPath.substring(startIndex+1);
			sendFile (uploaded, file, filename, types);
		}, false);
}

