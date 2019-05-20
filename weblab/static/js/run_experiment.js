
var RunExperiment = function() {};

RunExperiment.prototype = {
  init: function() {
    $("#checkallbutton").click (function () {
       $(".latestexperimentCheckBox").prop('checked', true);
       $(".experimentCheckBox").prop('checked', true);
      });
    $("#uncheckallbutton").click (function () {
       $(".latestexperimentCheckBox").prop('checked', false);
       $(".experimentCheckBox").prop('checked', false);
    });
    $("#checklatestbutton").click (function () {
       $(".latestexperimentCheckBox").prop('checked', true);
       $(".experimentCheckBox").prop('checked', false);
      });
    $("#runexperimentsbutton").click (function () {
      // do something
      });
  }
};


$(document).ready(function() {
  if ($("#runexperiment").length > 0) {
    var page = new RunExperiment();
    page.init();
  }
});
