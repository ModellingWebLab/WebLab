
var ExperimentVersionList = function() {};

ExperimentVersionList.prototype = {
  init: function() {

    $("#cancelRunningExperimentsAll").click (function () {
      $(".taskCancelCheckBox").prop('checked', true);
    });
    $("#cancelRunningExperimentsNone").click (function () {
      $(".taskCancelCheckBox").prop('checked', false);
    });

    $("#taskRefreshPage").click (function () {
      window.location.reload()
    });


  }	
};

$(document).ready(function() {

  if ($("#experimentversionlist").length > 0) {
    var page = new ExperimentVersionList();
    page.init();
  }
});
