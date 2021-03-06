
function init() {
  var $model = $("#id_model");
  var $modelVersion = $("#id_model_version");
  var $protocol = $("#id_protocol");
  var $protocolVersion = $("#id_protocol_version");
  var $fittingSpec = $("#id_fittingspec");
  var $fittingSpecVersion = $("#id_fittingspec_version");
  var $dataset = $("#id_dataset");

  function restrictIds(idList, $dropdown) {
    $dropdown.find("option").each(function(i, opt) {
      if (opt.value.length > 0) {
        $(opt).toggle(
            idList.includes(parseInt(opt.value, 10))
        );
      }
    });
  }

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

    $.getJSON("/fitting/results/new/filter",
        {
          'model': modelId,
          'protocol': protocolId,
          'fittingspec': fittingSpecId,
          'dataset': datasetId,
        },
        function(json) {
          if (json.fittingResultOptions) {
            var results = json.fittingResultOptions;

            restrictIds(results.models, $model);
            restrictIds(results.model_versions, $modelVersion);
            restrictIds(results.protocols, $protocol);
            restrictIds(results.protocol_versions, $protocolVersion);
            restrictIds(results.fittingspecs, $fittingSpec);
            restrictIds(results.fittingspec_versions, $fittingSpecVersion);
            restrictIds(results.datasets, $dataset);
          }
        }
    );
  }

  $('#resetbutton').click(function() {
    $('form select:enabled').val('');
  });

  $("form select").change(updateDropdowns);

  // Disabled form fields will not be submitted - re-enable before the form is posted
  $('form').submit(function() {
    $(':disabled').each(function() {
      $(this).removeAttr('disabled');
    })
  });

  updateDropdowns();
}


module.exports = {
  init: init,
};
