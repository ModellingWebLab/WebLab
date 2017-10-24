var $ = require('jquery');
require('blueimp-file-upload');
var utils = require('./lib/utils.js')
var notifications = require('./lib/notifications.js');


var Upload = function(){
  this.uploading = new Array();
  this.uploaded = new Array();

  // Names that aren't allowed to be uploaded
  this.reserved_names = ['errors.txt', 'manifest.xml', 'metadata.rdf'];

  this.$table = $("#uploadedfiles");
};


Upload.prototype = {

  init: function(uploaded, types) {
    var self =  this;
    $("#fileupload").fileupload({
      dataType: 'json',
      dropZone: $("#dropbox"),
      add: function(e, data) {
        self.addRow(data);
        data.submit();
      },
      submit: function(e, data) {
        var name = data.files[0].name;

        if (self.alreadyExists(uploaded, name))
        {
          notifications.add("there is already a file with the name '" + name + "' - please remove that first.", "error");
          return false;
        }
        if (self.reserved_names.indexOf(name) != -1)
        {
          notifications.add("the name '" + name + "' is reserved for system use; please choose another file name.", "error");
          return false;
        }
        if (!/^[a-zA-Z0-9._]+$/.test(name))
        {
          notifications.add("the name '" + name + "' contains reserved characters; only alpha-numeric characters, underscores and periods are allowed.", "error");
          return false;
        }
        self.uploading.push(name);

        console.log('submit', e, data);
      },
      progress: function(e, data) {
        self.updateProgress(data);
      },
      done: function(e, data) {
        var file = data.result.files[0];
        self.showUpload(data, uploaded, file, types);
      },
    }
    );

    $('#dropbox a').click(function() {
      $("#fileupload").click();
    });
  },

  updateProgress: function(data) {
    var $tr = data.context;
    var $action = $tr.find(".action small");
    $action.html((Math.floor(data.loaded/data.total*1000)/10) + "%");
  },

  alreadyExists: function(uploaded, name) {
    for (var i = 0; i < this.uploading.length; i++) {
      if (this.uploading[i] == name) {
        console.log('already uploading', name);
        return true;
      }
    }
    for (var i = 0; i < uploaded.length; i++) {
      if (uploaded[i].fileName == name) {
        console.log('already uploaded', name);
        return true;
      }
    }
    return false;
  },

  addRow: function(data) {
    var file = data.files[0];
    var $tr = $("<tr>").appendTo(this.$table);
    data.context = $tr;

    var $td = $("<td>").appendTo($tr);
    $('<input type="radio" name="mainEntry" value="' + file.name + '" />').appendTo($td);
    $('<input type="hidden" name="filename[]" value="' + file.stored_name + '" />').appendTo($td);

    $td = $('<td class="filename">').appendTo($tr);
    $("<code>" + file.name + '</code>').appendTo($td);
    $('<a class="rm"><img src="' + staticPath + 'img/failed.png" alt="remove from list" /></a>').appendTo($td);

    $td = $('<td class="size">').appendTo($tr);
    $('<small><code> ' + utils.humanReadableBytes(file.size) + ' </code></small>').appendTo($td);

    $('<td class="action"><small></small></td>').appendTo($tr);
  },

  showUpload: function(data, uploaded, file, types) {
    var $tr = data.context;
    var $name = $tr.find(".filename code");
    var $action = $tr.find(".action small");
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
    $action.html($typeSelect);
    uploaded.push(array);

    $rm.click(function () {
      for (var i = 0; i < uploaded.length; i++) {
        if (uploaded[i].fileName == name)
          uploaded.splice(i, 1);
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
