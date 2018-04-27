var XDate = require('xdate');

function humanReadableBytes (bytes)
{
    var sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    if (bytes == 0)
      return '0 Bytes';
    var i = parseInt (Math.floor(Math.log(bytes) / Math.log(1024)));
    return Math.round (bytes / Math.pow(1024, i), 2) + ' ' + sizes[i];
};

function removeChildren (elem)
{
  $(elem).empty();
}

function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = jQuery.trim(cookies[i]);
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function beautifyTimeStamp (datestring)
{
  var date = new XDate(datestring, true);
  if (date && date.valid())
  {
    return date.toString ("MMM d'<sup>'S'</sup>', yyyy 'at' h:mm tt");
  }
  return datestring;
}

function beautifyTimeStamps()
{
  $("time").each(function () {
    var tm = this.innerHTML;
    if (tm)
    {
      this.setAttribute("datetime", tm);
      this.innerHTML = beautifyTimeStamp(tm);
    }
  });
}

function getYMDHMS (datestring)
{
  var date = new XDate(datestring, true);
  if (date && date.valid ())
  {
    return date.toString ("yyyy-MM-dd_HH-mm-ss");
  }
  return datestring;
}

function convertForURL (str)
{
  var url = str.replace(/\W/g, '');
  if (url.length >= 5)
    return url;
  while (url.length < 7)
    url += Math.random().toString(36).substring(7);
  return url.substring (0, 5);
}

function addScript (link)
{
  var el = document.createElement('script');
  el.async = false;
  el.src = link;
  el.type = 'text/javascript';
  (document.getElementsByTagName('head')[0]||document.body).appendChild(el);
}

function addLink (link)
{
  var el = document.createElement('link');
  el.rel = "stylesheet";
  el.href = link;
  el.type = 'text/css';
  (document.getElementsByTagName('head')[0]||document.body).appendChild(el);
}

module.exports = {
  humanReadableBytes: humanReadableBytes,
  removeChildren: removeChildren,
  getCookie: getCookie,
  beautifyTimeStamp: beautifyTimeStamp,
  beautifyTimeStamps: beautifyTimeStamps,
  getYMDHMS: getYMDHMS,
  convertForURL: convertForURL,
  addScript: addScript,
  addLink: addLink
}
