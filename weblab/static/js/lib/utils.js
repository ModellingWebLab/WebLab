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

module.exports = {
  humanReadableBytes: humanReadableBytes,
  removeChildren: removeChildren,
  getCookie: getCookie,
  beautifyTimeStamp: beautifyTimeStamp,
  beautifyTimeStamps: beautifyTimeStamps,
  getYMDHMS: getYMDHMS
}
