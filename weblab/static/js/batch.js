
function submitBatch (jsonObject, actionIndicator)
{
	actionIndicator.innerHTML = "<img src='"+contextPath+"/res/img/loading2-new.gif' alt='loading' />";
    
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
        	if (json.batchSubmit)
        	{
	        	var msg = json.batchSubmit.responseText;
	        	if (json.batchSubmit.response)
	        	{
	        		actionIndicator.innerHTML = "<img src='"+contextPath+"/res/img/check.png' alt='valid' /> " + msg;
	        	}
	        	else
	        		actionIndicator.innerHTML = "<img src='"+contextPath+"/res/img/failed.png' alt='invalid' /> " + msg;
        	}
        }
        else
        {
        	actionIndicator.innerHTML = "<img src='"+contextPath+"/res/img/failed.png' alt='error' /> sorry, serverside error occurred.";
        }
    };
    xmlhttp.send(JSON.stringify(jsonObject));
}


/* Factory function for creating event handlers for clicks on the 'create jobs' buttons.
 * The handler will figure out which experiments to start, and call submitBatch.
 * @param createButton  the button to add a handler to
 * @param actionIndicator  a span element for use in keeping the user informed
 */
function createListener(createButton, actionIndicator)
{
    createButton.addEventListener("click",
        function (event)
        {
            var toCreate = [];
            var toForce = false;
            var boxes = document.getElementsByTagName("input");
            for (var i = 0; i < boxes.length; i++)
            {
                if (boxes[i].type != "checkbox")
                    continue;
                if (boxes[i].checked)
                {
                    if (boxes[i].id == "forceoverwrite")
                        toForce = true;
                    else
                        toCreate.push(boxes[i].name);
                }
            }

            console.log(toCreate);
            console.log(toForce);
            submitBatch ({
                task: "batchSubmit",
                entities: toCreate,
                force: toForce
            }, actionIndicator);
        },
        false);
}

/**
 * Set whether each model/protocol selection checkbox is checked or unchecked.
 * @param checked  what to set as the state of each checkbox
 */
function setChecks(checked)
{
    var boxes = document.getElementsByTagName("input");
    for (var i = 0; i < boxes.length; i++)
    {
        if (boxes[i].type != "checkbox" || boxes[i].id == "forceoverwrite")
            continue;
        boxes[i].checked = checked;
    }
}

function initBatch ()
{
    // Add listeners for clicks on our various buttons
    var btn = document.getElementById("batchcreator1");
    if (btn)
        createListener(btn, document.getElementById("batchcreatoraction1"));
    btn = document.getElementById("batchcreator2");
    if (btn)
        createListener(btn, document.getElementById("batchcreatoraction2"));

	var checker = document.getElementById("checkAll");
	var checkerLatest = document.getElementById("checkLatest");
	var unchecker = document.getElementById("uncheckAll");
	checker.addEventListener("click", function () { setChecks(true); }, false);
	checkerLatest.addEventListener("click", function ()
	{
	    setChecks(false);
	    $( ".latestVersion" ).prop('checked', true);
	}, false);
	unchecker.addEventListener("click", function () { setChecks(false); }, false);
	
	// Start with just the latest versions checked
	$( ".latestVersion" ).prop('checked', true);
}

document.addEventListener("DOMContentLoaded", initBatch, false);