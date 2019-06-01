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

  /**
   * Raw parsing function for CSV files into columns of numerical/textual data
   * @param file  the loaded file to parse
   */
function parseCsvRaw(file) {
  var str = file.contents.replace(/\s*#.*\n/gm,"");
  var patterns = new RegExp(
      (
       // Delimiters.
       "(,|\\t|\\r?\\n|\\r|^)" +
       // Quoted fields.
       "(?:\"([^\"]*(?:\"\"[^\"]*)*)\"|" +
       // Standard fields.
       "([^\",\\t\\r\\n]*))"
      ),
      "gi"
      );
  var csv = [[]];
  var matches = null;
  while (matches = patterns.exec (str))
  {
    var value;
    var matchDel = matches[1];
    if (matchDel.length && matchDel != "," && matchDel != "\t")
      csv.push([]);
    if (matches[2])
      value = matches[2].replace (new RegExp ("\"\"", "g"), "\"");
    else
      value = matches[3];

    csv[csv.length - 1].push (value);
  }
  file.csv = csv;
}

function keys(obj) {
  var keys = [];

  for(var key in obj)
    if(obj.hasOwnProperty(key))
      keys.push(key);

  return keys;
}

function getPos(ele) {
  var x = 0;
  var y = 0;
  while (true) {
    if (!ele)
      break;
    x += ele.offsetLeft;
    y += ele.offsetTop;
    if (ele.offsetParent === null)
      break;
    ele = ele.offsetParent;
  }
  return {xPos:x, yPos:y};
}

function getFileContent (file, succ) {
  // TODO: loading indicator.. so the user knows that we are doing something
  $.get(file.url, function(data) {
      file.contents = data;
      succ.getContentsCallback (true);
  }).fail(function() {
    succ.getContentsCallback(false);
  });
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
  addLink: addLink,
  parseCsvRaw: parseCsvRaw,
  keys: keys,
  getPos: getPos,
  getFileContent: getFileContent,
}
