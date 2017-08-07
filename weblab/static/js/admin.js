
function updateUser (jsonObject)
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
    
    xmlhttp.open("POST", document.location.href, true);
    xmlhttp.setRequestHeader("Content-type", "application/json");

    xmlhttp.onreadystatechange = function()
    {
        if(xmlhttp.readyState != 4)
        	return;
        
    	var json = JSON.parse(xmlhttp.responseText);
    	displayNotifications (json);
    	
        if(xmlhttp.status == 200)
        {
        	addNotification (json.updateUserRole.responseText, "info");
        }
    };
    xmlhttp.send(JSON.stringify(jsonObject));
}

function roleObserver (elem)
{
        	elem.addEventListener("change", function (ev) {
        		var id = elem.id.split ("-");
        		if (id.length != 3 || !id[2])
        		{
        			addNotification ("error identifying user", "error");
        			return;
        		}
        		
        		updateUser ({
    		    	task: "updateUserRole",
    		    	user: id[2],
        			role: elem.options[elem.selectedIndex].value
        		});
        	}, true);
	
}

function initAdmin ()
{
	var elems = document.getElementsByTagName('select');
    for (var i = 0; i < elems.length; i++)
    {
    	var classes = ' ' + elems[i].className + ' ';
        if(classes.indexOf(' role-chooser ') > -1)
        {
        	roleObserver (elems[i]);
        }
    }
    

	var resubmit = document.getElementById("rerunExperiments");
	var resubmitAction = document.getElementById("rerunExperimentsAction");
	if (resubmit && resubmitAction)
	{
		resubmit.addEventListener("click", function (ev) {
			batchProcessing ({
				batchTasks : [{
					experiment : "*"
				}],
				force: true
			},resubmitAction);
		});
	}
}

document.addEventListener("DOMContentLoaded", initAdmin, false);