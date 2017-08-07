
// Sub-pages of myfiles.html, and which we're currently viewing
var pages = [ "model", "protocol", "experiment" ];
var curPage = null;


function updateUser (jsonObject, elem)
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
        if(xmlhttp.readyState != 4)
        	return;
        
    	var json = JSON.parse(xmlhttp.responseText);
    	console.log (json);
    	displayNotifications (json);
    	
        if(xmlhttp.status == 200)
        {
        	
        	if (json.updatePassword)
        	{
        		if (json.updatePassword.response)
        			elem.innerHTML = "<img src='"+contextPath+"/res/img/check.png' alt='valid' /> " + json.updatePassword.responseText;
        		else
        			elem.innerHTML = "<img src='"+contextPath+"/res/img/failed.png' alt='invalid' /> " + json.updatePassword.responseText;
        	}
        	
        	if (json.updateInstitute)
        	{
        		if (json.updateInstitute.response)
        			elem.innerHTML = "<img src='"+contextPath+"/res/img/check.png' alt='valid' /> " + json.updateInstitute.responseText;
        		else
        			elem.innerHTML = "<img src='"+contextPath+"/res/img/failed.png' alt='invalid' /> " + json.updateInstitute.responseText;
        	}
        	
        	if (json.updateSendMails)
        	{
        		if (json.updateSendMails.response)
        			elem.innerHTML = "<img src='"+contextPath+"/res/img/check.png' alt='valid' /> " + json.updateSendMails.responseText;
        		else
        			elem.innerHTML = "<img src='"+contextPath+"/res/img/failed.png' alt='invalid' /> " + json.updateSendMails.responseText;
        	}
        	
        }
        else
        	elem.innerHTML = "<img src='"+contextPath+"/res/img/failed.png' alt='error' /> sorry, serverside error occurred.";
    };
    xmlhttp.send(JSON.stringify(jsonObject));
}

function initMe ()
{
	if (document.getElementById ("myaccounttable"))
	{
		// account page
		var btn = document.getElementById("pwchanger");
		btn.addEventListener("click", function (ev) {
			if (ev.which == 1)
			{
				var old = document.getElementById("oldpassword").value;
				var new1 = document.getElementById("newpassword1").value;
				var new2 = document.getElementById("newpassword2").value;
				
				if (!old || !new1 || !new2)
				{
					addNotification ("please fill in all fields.", "error");
					return;
				}
				
				if (new1 != new2)
				{
					addNotification ("the new passwords are different.", "error");
					return;
				}
				
				updateUser ({
					task: "updatePassword",
					prev: old,
					next: new1
				}, document.getElementById("changeaction"));
			}
	    	}, true);
		
		var instituteChanger = document.getElementById("instituteChanger");
		if (instituteChanger)
			instituteChanger.addEventListener("blur", function (ev) {
				updateUser ({
					task: "updateInstitute",
					institute: instituteChanger.value
				}, document.getElementById("instituteChangeaction"));
			}, true);
		
		var sendMailsChanger = document.getElementById("sendMailsCheckbox");
		if (sendMailsChanger)
			sendMailsChanger.addEventListener("click", function (ev) {
				updateUser ({
					task: "updateSendMails",
					sendMail: sendMailsChanger.checked
				}, document.getElementById("sendMailsChangeaction"));
			}, true);
	}
	else
	{
		// files page
	    window.onpopstate = initMe;
        var hash_index = document.location.href.lastIndexOf("#");
        var page = document.location.href.substr(hash_index + 1);
		for (var i = 0; i < pages.length; i++)
		{
			var btn = document.getElementById(pages[i] + "chooser");
			registerSwitchPagesListener (btn, pages[i]);
			if (page == pages[i])
			    curPage = page;
		}
		if (curPage === null || hash_index == -1)
		    curPage = "model";
		switchPage (curPage);
		
		var modellist = document.getElementById("modellist");
		var protocollist = document.getElementById("protocollist");
		var experimentlist = document.getElementById("experimentlist");
		
		var uls = experimentlist.getElementsByTagName("ul");
		for (var i = 0; i < uls.length; i++)
			sortChildrenByAttribute (uls[i], false, "title");
		uls = protocollist.getElementsByTagName("ul");
		for (var i = 0; i < uls.length; i++)
			sortChildrenByAttribute (uls[i], false, "title");
		uls = modellist.getElementsByTagName("ul");
		for (var i = 0; i < uls.length; i++)
			sortChildrenByAttribute (uls[i], false, "title");
	}
}
function switchPage (page)
{
    if (page != curPage)
    {
        window.history.pushState(document.location.href, "", contextPath + "/myfiles.html#" + page);
    }
    
	for (var i = 0; i < pages.length; i++)
	{
	    var div = document.getElementById(pages[i] + "list");
	    var btn = $(document.getElementById(pages[i] + "chooser"));
		if (pages[i] == page)
		{
			div.style.display = "block";
			btn.addClass("selected");
		}
		else
	    {
			div.style.display = "none";
			btn.removeClass("selected");
	    }
	}
}
function registerSwitchPagesListener (btn, page)
{
	btn.addEventListener("click", function () {
		console.log ("switch listener triggered " + page);
		switchPage (page);
	}, true);
}

document.addEventListener("DOMContentLoaded", initMe, false);