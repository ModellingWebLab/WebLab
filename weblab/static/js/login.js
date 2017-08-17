
function verifyLogin (jsonObject, elem)
{
    elem.innerHTML = "<img src='res/img/loading2-new.gif' alt='loading' />";
    
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
        if(xmlhttp.readyState != 4) {
        	return;
        }
        
        if(xmlhttp.status == 200) {
        	var json = JSON.parse(xmlhttp.responseText);
        	console.log (json);
        	
        	if (json.login)
        	{
	        	var msg = json.login.responseText;
	        	if (json.login.response)
	        	{
	        		elem.innerHTML = "<img src='res/img/check.png' alt='valid' /> " + msg;
	        		// lets switch to the internal side, by while keeping the cache.
	        		location.reload (false);
	        	}
	        	else
	        		elem.innerHTML = "<img src='res/img/failed.png' alt='invalid' /> " + msg;
        	}
        }
        else
        {
        	elem.innerHTML = "<img src='res/img/failed.png' alt='error' /> sorry, serverside error occurred.";
        }
    };
    
    xmlhttp.send(JSON.stringify(jsonObject));
}

function initRegForm ()
{
	var mailInput = document.getElementById("mail");
	var pwInput = document.getElementById("password");
	var rememberInput = document.getElementById("remember");
	
	var action = document.getElementById("submitaction");
	
	var btn = document.getElementById("loginsubmit");
	btn.addEventListener("click", 
			function (event)
			{
		verifyLogin ({
			task: "logmein",
			password: pwInput.value,
			mail: mailInput.value,
			remember: rememberInput.checked
		}, action);
	}, false);
	$('#loginform').keydown(function(e) {
		if (e.keyCode == 13) {
			$(btn).click();
		}
	});
}


document.addEventListener("DOMContentLoaded", initRegForm, false);