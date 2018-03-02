
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
    if (elem)
        while (elem.firstChild)
            elem.removeChild(elem.firstChild);
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

module.exports = {
  humanReadableBytes: humanReadableBytes,
  removeChildren: removeChildren,
  getCookie: getCookie
}
