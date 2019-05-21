
var RunExperiment = function() {};

RunExperiment.prototype = {
  init: function() {
    $("#checkallbutton").click (function () {
        $(".latestexperimentCheckBox").each (function () {
            $(this).prop('checked', true)
        });
        $(".experimentCheckBox").each (function () {
            $(this).prop('checked', true)
        });
    });
    $("#uncheckallbutton").click (function () {
        $(".latestexperimentCheckBox").each (function () {
            $(this).prop('checked', false)
        });
        $(".experimentCheckBox").each (function () {
            $(this).prop('checked', false)
        });
    });
    $("#checklatestbutton").click (function () {
        $(".latestexperimentCheckBox").each (function () {
            $(this).prop('checked', true)
        });
        $(".experimentCheckBox").each (function () {
            $(this).prop('checked', false)
        });
    });
  }
};


$(document).ready(function() {
  if ($("#runexperiment").length > 0) {
    var page = new RunExperiment();
    page.init();
  }
});
