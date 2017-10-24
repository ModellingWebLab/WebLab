var Upload = require('./upload.js');

var uploadedFiles = new Array ();
var knownTypes = ["unknown", "CellML", "CSV", "HDF5", "EPS", "PNG", "XMLPROTOCOL", "TXTPROTOCOL", "COMBINE archive"];


function initNewEntity() {
  var $versionName = $("id_version");
  var commitMsg = $("id_commit_message");
  var visibilityElt = $("visibility");

  $("dateinserter").click(function(){
    if ($versionName.length)
    {
      $versionName.focus();
      $versionName.value = getYMDHMS(new Date());
      $versionName.blur();
    }
  });

  var upload = new Upload();
  upload.init(knownTypes);
}

$(document).ready(initNewEntity);
