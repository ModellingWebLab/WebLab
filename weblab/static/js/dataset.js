function init() {

  var $columnMappingForm = $("form.dataset-column-mapper");
  if ($columnMappingForm.length > 0) {
    initColumnMappingForm($columnMappingForm);
  }
}


function initColumnMappingForm($form) {
    var $versionDropdowns = $form.find(".protocol-version select");

    function restrictIoputs() {
      // Restrict protocol ioput dropdown to match protocol versions.
      var $ioputDropdown = $(this).siblings('select');
      var $ioputOptions = $ioputDropdown.find('option');
      var protoVersionId = $(this).val();

      $ioputOptions.each(function() { 
        var $opt = $(this);
        $opt.toggle($opt.val() == '' || $opt.data('protocol-version') == protoVersionId);
      });
    }

    $versionDropdowns.change(restrictIoputs);
    $versionDropdowns.each(restrictIoputs);
}

module.exports = {
  init: init,
}
