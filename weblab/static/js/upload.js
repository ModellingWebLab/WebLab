var $ = require('jquery');
require('blueimp-file-upload');
var utils = require('./lib/utils.js')
var notifications = require('./lib/notifications.js');


var Upload = function(){
  this.uploading = new Array();
  this.uploaded = new Array();

  // Names that aren't allowed to be uploaded
  this.reserved_names = ['errors.txt', 'manifest.xml', 'metadata.rdf'];

  this.$table = $("#entityversionfilestable");

  var self = this;
  this.$table.find("tbody tr").each(function(i, tr) {
    var $tr = $(tr);
    self.uploaded.push({
      'fileName': $tr.find(".filename").html(),
      'fileType': $tr.find(".type").html(),
    });
  });

  console.log(self.uploaded);
};


Upload.prototype = {

  init: function(types) {
    var self =  this;
    $("#fileupload").fileupload({
      dataType: 'json',
      dropZone: $("#dropbox"),
      add: function(e, data) {
        var name = data.files[0].name;
        console.log(name);
        if (self.validName(name)) {
          self.addRow(data);
          data.submit();
        }
      },
      submit: function(e, data) {
        self.uploading.push(data.files[0].name);
      },
      progress: function(e, data) {
        self.updateProgress(data);
      },
      done: function(e, data) {
        var file = data.result.files[0];
        self.showUpload(data, file, types);
      },
    });

    $('#dropbox a').click(function() {
      $("#fileupload").click();
    });

    $("form #entityversionfilestable").on('click', 'tr .action .delete-file', function() {
      var $tr = $(this).parents('tr');
      $td = $tr.find(".filename");
      if ($tr.hasClass('deleting')) {
        $tr.removeClass('deleting');
        $tr.find('input[name="delete_filename[]"]').remove();
      } else {
        $tr.addClass('deleting');
        $('<input type="hidden" name="delete_filename[]" value="' + $.trim($td.text()) + '" />').appendTo($td);
      }
      return false;
    });
  },

  validName: function(name) {
    var error;
    if (this.alreadyExists(name)) {
      error = "there is already a file with the name '" + name + "' - please remove that first.", "error";
    } else if (this.reserved_names.indexOf(name) != -1) {
      error = "the name '" + name + "' is reserved for system use; please choose another file name.", "error";
    } else if (!/^[a-zA-Z0-9._]+$/.test(name)) {
      error = "the name '" + name + "' contains reserved characters; only alpha-numeric characters, underscores and periods are allowed.", "error";
    }

    if (error) {
      notifications.add(error);
      return false;
    }
    return true;
  },

  updateProgress: function(data) {
    var $tr = data.context;
    var $type = $tr.find(".type small");
    $type.html((Math.floor(data.loaded/data.total*1000)/10) + "%");
  },

  alreadyExists: function(name) {
    for (var i = 0; i < this.uploading.length; i++) {
      if (this.uploading[i] == name) {
        return true;
      }
    }
    for (var i = 0; i < this.uploaded.length; i++) {
      if (this.uploaded[i].fileName == name) {
        return true;
      }
    }
    return false;
  },

  addRow: function(data) {
    var file = data.files[0];
    var $tr = $('<tr class="new-file">').appendTo(this.$table);
    data.context = $tr;
    var $td;

    $td = $('<td class="filename">').appendTo($tr);
    $("<code>" + file.name + '</code>').appendTo($td);
    $('<a class="rm"><img src="' + staticPath + 'img/failed.png" alt="remove from list" /></a>').appendTo($td);

    $('<td class="type"><small></small></td>').appendTo($tr);

    $td = $('<td class="size">').appendTo($tr);
    $('<small><code> ' + utils.humanReadableBytes(file.size) + ' </code></small>').appendTo($td);

    $('<td class="action"><a class="delete-file" title="delete this file"></td>').appendTo($tr);
  },

  showUpload: function(data, file, types) {
    var $tr = data.context;
    var $name = $tr.find(".filename code");
    var $type = $tr.find(".type small");
    var $rm = $tr.find(".rm");
    var self = this;

    var array = {
      fileName: file.name,
      fileType: "unknown"
    };

    // Set default fileType based on extension, where sensible
    if (file.name.endsWith(".cellml"))
        array.fileType = "CellML";
    else if (file.name.endsWith(".txt"))
        array.fileType = "TXTPROTOCOL";
    else if (file.name.endsWith(".xml"))
        array.fileType = "XMLPROTOCOL";
    else if (file.name.endsWith(".zip") || name.endsWith(".omex"))
        array.fileType = "COMBINE archive";

    var $typeSelect = $("<select>");
    for (var i = 0; i < types.length; i++)
    {
      var $opt = $("<option>").appendTo($typeSelect);
      $opt.value = types[i];
      $opt.append(types[i]);
    }
    $typeSelect.val(array.fileType);

    $typeSelect.click(function () {
      array.fileType = $opt.options[$opt.selectedIndex].value;
    });

    $name.addClass("success");
    $type.html($typeSelect);
    this.uploaded.push(array);

    $td = $tr.find(".filename");
    $('<input type="hidden" name="filename[]" value="' + file.stored_name + '" />').appendTo($td);

    $rm.click(function () {
      for (var i = 0; i < self.uploaded.length; i++) {
        if (self.uploaded[i].fileName == name)
          self.uploaded.splice(i, 1);
      }
      for (var i = 0; i < self.uploading.length; i++) {
        if (self.uploading[i] == name)
          self.uploading.splice(i, 1);
      }
      $tr.remove();
    });
  }
}


module.exports = Upload
