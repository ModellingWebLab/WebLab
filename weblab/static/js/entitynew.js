
var uploadedFiles = new Array ();
var knownTypes = ["unknown", "CellML", "CSV", "HDF5", "EPS", "PNG", "XMLPROTOCOL", "TXTPROTOCOL", "COMBINE archive"];

function verifyNewEntity (jsonObject, elem, entityNameAction, versionNameAction, storeAction, visibilityAction)
{
    elem.innerHTML = "<img src='"+contextPath+"/res/img/loading2-new.gif' alt='loading' />";
    
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
        if (xmlhttp.readyState != 4)
        	return;
        
    	var json = JSON.parse(xmlhttp.responseText);
    	console.log (json);
    	displayNotifications (json);
    	
        if (xmlhttp.status == 200)
        {
        	
        	if (json.entityName && entityNameAction)
        	{
	        	var msg = json.entityName.responseText;
	        	if (json.entityName.response)
	        		entityNameAction.innerHTML = "<img src='"+contextPath+"/res/img/check.png' alt='valid' /> " + msg;
	        	else
	        		entityNameAction.innerHTML = "<img src='"+contextPath+"/res/img/failed.png' alt='invalid' /> " + msg;
	        	// Decide whether to show the 're-run'
	        	if (json.isNewVersion)
	        	    $("#reRunPara").show();
	        	else
	        	    $("#reRunPara").hide();
        	}
        	if (json.versionName)
        	{
	        	var msg = json.versionName.responseText;
	        	if (json.versionName.response)
	        		versionNameAction.innerHTML = "<img src='"+contextPath+"/res/img/check.png' alt='valid' /> " + msg;
	        	else
	        		versionNameAction.innerHTML = "<img src='"+contextPath+"/res/img/failed.png' alt='invalid' /> " + msg;
        	}
        	if (json.visibility && visibilityAction)
        	{
        	    document.getElementById("visibility-" + json.visibility).selected = true;
        	    visibilityAction.innerHTML = "";
        	}
        	if (json.createNewEntity)
        	{
	        	var msg = json.createNewEntity.responseText;
	        	if (json.createNewEntity.response)
	        	{
	        	    clearNotifications("error"); // Get rid of any leftover errors from failed creation attempts
	        		var form = document.getElementById ("newentityform");
	        		removeChildren (form);
	        		var h1 = document.createElement("h1");
	        		var img = document.createElement("img");
	        		img.src = contextPath + "/res/img/check.png";
	        		img.alt = "created entity successfully";
	        		h1.appendChild(img);
	        		h1.appendChild(document.createTextNode (" Congratulations"));

	        		form.appendChild(h1);
	        		
	        		var p = document.createElement("p");
	        		p.appendChild(document.createTextNode ("You've just created a "));
                    var a = document.createElement("a");
                    a.href = contextPath + "/" + json.createNewEntity.versionType + "/id/" + json.createNewEntity.entityId + "/version/" + json.createNewEntity.versionId;
                    a.appendChild(document.createTextNode ("new " + json.createNewEntity.versionType));
                    p.appendChild(a);
	        		p.appendChild(document.createTextNode ("!"));
	        		form.appendChild(p);
	        		
	        		if (json.createNewEntity.expCreation)
	        		{
		        		p = document.createElement("p");
		        		p.appendChild(document.createTextNode ("Also, " + json.createNewEntity.expCreation + "."));
		        		form.appendChild(p);
	        		}
	        		
	        		p = document.createElement("p");
	        		a = document.createElement("a");
	        		a.href = contextPath + "/batch/" + json.createNewEntity.versionType + "/newVersion/" + json.createNewEntity.versionId;
	        		a.appendChild(document.createTextNode ("Run experiments"));
	        		p.appendChild(a);
	        		p.appendChild(document.createTextNode (" using this " + json.createNewEntity.versionType + "."));
	        		form.appendChild(p);
	        	}
	        	else
	        		storeAction.innerHTML = "<img src='"+contextPath+"/res/img/failed.png' alt='invalid' /> " + msg;
        	}
        }
        else
        {
        	elem.innerHTML = "<img src='"+contextPath+"/res/img/failed.png' alt='error' /> sorry, serverside error occurred.";
        }
    };
    xmlhttp.send(JSON.stringify(jsonObject));
}


function initNewEntity ()
{
	var entityName = document.getElementById("entityname");
	var versionName = document.getElementById("versionname");
	var commitMsg = document.getElementById("commitMsg");
	var visibilityElt = document.getElementById("visibility");
	var visibilityAction = document.getElementById("visibilityaction");
	var entityNameAction = document.getElementById("entityaction");
	var versionNameAction = document.getElementById("versionaction");
	var storeAction = document.getElementById("saveaction");
	var svbtn = document.getElementById('savebutton');
	
	entityName.addEventListener("blur", function( event )
	{
		verifyNewEntity ({
	    	task: "verifyNewEntity",
	    	entityName: entityName.value
	    }, entityNameAction, entityNameAction, versionNameAction, storeAction, visibilityAction);
	  }, true);
	
	versionName.addEventListener("blur", function( event ) {
		verifyNewEntity ({
	    	task: "verifyNewEntity",
	    	entityName: entityName.value,
	    	versionName: versionName.value
	    }, versionNameAction, entityNameAction, versionNameAction, storeAction, visibilityAction);
	  }, true);
	
	
	var insertDate = document.getElementById('dateinserter');
	insertDate.addEventListener("click", function (ev) {
		if (versionName)
		{
			versionName.focus ();
			versionName.value = getYMDHMS (new Date());
			versionName.blur ();
		}
	}, true);
	
	// Get initial visibility, if any
	if (entityName.value)
	{
    	verifyNewEntity({
    	        task: "verifyNewEntity",
    	        entityName: entityName.value
    	    }, visibilityAction, entityNameAction, versionNameAction, storeAction, visibilityAction);
    	// Show the 're-run experiments' checkbox & label
    	$("#reRunPara").show();
    }
	
	initUpload (uploadedFiles, knownTypes);
	
	svbtn.addEventListener("click", function (ev) {
		verifyNewEntity(
		{
	    	task: "createNewEntity",
	    	entityName: entityName.value,
	    	commitMsg: commitMsg.value,
	    	versionName: versionName.value,
	    	visibility: visibilityElt.options[visibilityElt.selectedIndex].value,
	    	files: uploadedFiles,
	    	mainFile: $('input[name="mainEntry"]:checked').val (),
	    	rerunExperiments: document.getElementById('reRunExperiments').checked
	    }, storeAction, entityNameAction, versionNameAction, storeAction, visibilityAction);
	}, true);
	
}


document.addEventListener("DOMContentLoaded", initNewEntity, false);