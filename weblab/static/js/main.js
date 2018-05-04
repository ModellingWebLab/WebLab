var $ = require('jquery');
require('jquery-migrate');
$.migrateMute = true;
require('jquery-ui-browserify');
var utils = require('./lib/utils.js')
require('./entitynew.js');
require('./db.js');
var experiment =require('./experiment.js');
var notifications = require('./lib/notifications.js');


function removeListeners (element)
{
  var new_element = element.cloneNode(true);
  element.parentNode.replaceChild (new_element, element);
  return new_element;
}

function batchProcessing (jsonObject, actionIndicator, callback)
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

    xmlhttp.open("POST", contextPath + '/batch/batch', true);
    xmlhttp.setRequestHeader("Content-type", "application/json");

    xmlhttp.onreadystatechange = function()
    {
        if(xmlhttp.readyState != 4)
          return;

        console.log (xmlhttp.responseText);
      var json = JSON.parse(xmlhttp.responseText);
      console.log (json);
      notifications.display(json);

        if(xmlhttp.status == 200)
        {
          if (json.batchTasks)
          {
            var msg = json.batchTasks.responseText;
            if (json.batchTasks.response)
            {
              actionIndicator.innerHTML = "<img src='"+contextPath+"/res/img/check.png' alt='valid' /> " + msg;
              if (callback && json.batchTasks.createdExps)
              {
                var exps = json.batchTasks.createdExps;
                for (var i=0; i<exps.length; i++)
                  callback(exps[i].versId, exps[i].url);
              }
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

function sortChildrenByAttribute (elem, reverse, attr)
{
  //console.log (elem);
  var children = elem.childNodes;
  //console.log (children);
  var items = [];

  var ret = reverse ? -1 : 1;

  for (var i = 0; i < children.length; i++)
  {
    //console.log (children[i]);
    //console.log (children[i].nodeType);
    //console.log (children[i].attr);
    //console.log (children[i][attr]);
    if (children[i].nodeType == 1 && children[i][attr])
      items.push(children[i]);
  }
  //console.log ("sorting");
  //console.log (items);

  items.sort(function (a, b)
      {
        return a[attr] == b[attr] ? 0 : (a[attr] > b[attr] ? ret : -1 * ret);
      });

  //console.log (items);
  //console.log ("sorted");

  for (var i = 0; i < items.length; i++)
    elem.appendChild (items[i]);

}

function initPage ()
{
  // java's implementation of string's hashcode
  String.prototype.hashCode = function()
  {
      var hash = 0, i, char, l;
      if (this.length == 0)
        return hash;
      for (i = 0, l = this.length; i < l; i++)
      {
          char  = this.charCodeAt(i);
          hash  = ((hash<<5)-hash)+char;
          hash |= 0; // Convert to 32bit integer
      }
      return hash;
  };


  String.prototype.endsWith = function(suffix) {
      return this.indexOf(suffix, this.length - suffix.length) !== -1;
  };

  $("#dismisserrors").click(function() {
    notifications.clear("error");
  });

  $("#dismissnotes").click(function() {
    notifications.clear("info");
  });

  utils.beautifyTimeStamps();

  var csrftoken = utils.getCookie('csrftoken');
  function csrfSafeMethod(method) {
    // these HTTP methods do not require CSRF protection
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
  }
  $.ajaxSetup({
    beforeSend: function(xhr, settings) {
      if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
        xhr.setRequestHeader("X-CSRFToken", csrftoken);
      }
    }
  });

  if ($('#experiment-version').length > 0) {
    experiment.init()
  }
}

document.addEventListener("DOMContentLoaded", initPage, false);
