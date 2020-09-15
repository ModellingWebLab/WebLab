
function init() {
  var $model = $("#id_model");
  var $modelVersion = $("#id_model_version");
  var $protocol = $("#id_protocol");
  var $protocolVersion = $("#id_protocol_version");
  var $fittingSpec = $("#id_fittingspec");
  var $fittingSpecVersion = $("#id_fittingspec_version");
  var $dataset = $("#id_dataset");

  function updateDropdowns() {
    var modelId = parseInt($model.val(), 10);
    var protocolId = parseInt($protocol.val(), 10);
    var fittingSpecId = parseInt($fittingSpec.val(), 10);
    var datasetId = parseInt($dataset.val(), 10);

    console.log(modelId, protocolId, fittingSpecId, datasetId);

    // Clear selected version if no entity selected
    if (isNaN(modelId)) $modelVersion.val('');
    if (isNaN(protocolId)) $protocolVersion.val('');
    if (isNaN(fittingSpecId)) $fittingSpecVersion.val('');

    // Disable version dropdowns if entity not selected
    $modelVersion.prop('disabled', isNaN(modelId));
    $protocolVersion.prop('disabled', isNaN(protocolId));
    $fittingSpecVersion.prop('disabled', isNaN(fittingSpecId));
  }

  $("form select").change(updateDropdowns);

  updateDropdowns();
}


module.exports = {
  init: init,
};
