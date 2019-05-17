
var RunExperiment = function() {};

RunExperiment.prototype = {
  init: function() {
    // Comparing entity versions click events
    $("#checkallbutton").click (function () {
      $(".experimentCheckBox").each (function () {
        $(this).prop('checked', true)
      });
    });
    $("#uncheckallbutton").click (function () {
      $(".experimentCheckBox").prop('checked', false);
    });
  }	
};


$(document).ready(function() {
  if ($("#runexperiment").length > 0) {
    var page = new RunExperiment();
    page.init();
  }
});
