
function verifyReg (jsonObject, elem, mailAction, nickAction, submitAction)
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
        	
        	if (json.mail)
        	{
	        	var msg = json.mail.responseText;
	        	if (json.mail.response)
	        		mailAction.innerHTML = "<img src='"+contextPath+"/res/img/check.png' alt='valid' /> " + msg;
	        	else
	        		mailAction.innerHTML = "<img src='"+contextPath+"/res/img/failed.png' alt='invalid' /> " + msg;
        	}
        	if (json.nick)
        	{
	        	var msg = json.nick.responseText;
	        	if (json.nick.response)
	        		nickAction.innerHTML = "<img src='"+contextPath+"/res/img/check.png' alt='valid' /> " + msg;
	        	else
	        		nickAction.innerHTML = "<img src='"+contextPath+"/res/img/failed.png' alt='invalid' /> " + msg;
        	}
        	if (json.register)
        	{
	        	var msg = json.register.responseText;
	        	if (json.register.response)
	        	{
	        		var form = document.getElementById ("registerform");
	        		removeChildren (form);
	        		var h1 = document.createElement("h1");
	        		var img = document.createElement("img");
	        		img.src = contextPath + "/res/img/check.png";
	        		img.alt = "registered successfully";
	        		h1.appendChild(img);
	        		h1.appendChild(document.createTextNode (" Congratulations"));
	        		var p = document.createElement("p");
	        		p.appendChild(document.createTextNode ("You've just registered for Functional Curation. Now, have a look at your mailbox. We've just sent you an email with a password."));

	        		form.appendChild(h1);
	        		form.appendChild(p);
	        	}
	        	else
	        		submitAction.innerHTML = "<img src='"+contextPath+"/res/img/failed.png' alt='invalid' /> " + msg;
        	}
        }
        else
        {
        	elem.innerHTML = "<img src='"+contextPath+"/res/img/failed.png' alt='error' /> sorry, serverside error occurred.";
        }
    };
    xmlhttp.send(JSON.stringify(jsonObject));
}


function initRegForm ()
{
	var mailAction = document.getElementById("mailaction");
	var nickAction = document.getElementById("nickaction");
	var submitAction = document.getElementById("submitaction");
	
	var mailInput = document.getElementById("mail");
	var nickInput = document.getElementById("nick");
	var instInput = document.getElementById("institution");
	var famInput = document.getElementById("familyName");
	var givInput = document.getElementById("givenName");
	
	
	mailInput.addEventListener("blur", function( event ) {
		verifyReg ({
	    	task: "verify",
	    	mail: mailInput.value
	    }, mailAction, mailAction, nickAction, submitAction);
	  }, true);
	nickInput.addEventListener("blur", function( event ) {
		verifyReg ({
	    	task: "verify",
	    	nick: nickInput.value
	    }, nickAction, mailAction, nickAction, submitAction);
	  }, true);
	
	var btn = document.getElementById("registersubmit");
	if (btn)
		btn.addEventListener("click", 
        function (event)
        {
			verifyReg ({
		    	task: "register",
		    	nick: nickInput.value,
		    	mail: mailInput.value,
		    	givenName: givInput.value,
		    	familyName: famInput.value,
		    	inst: instInput.value
		    }, submitAction, mailAction, nickAction, submitAction);
        }, 
        false);
}

document.addEventListener("DOMContentLoaded", initRegForm, false);