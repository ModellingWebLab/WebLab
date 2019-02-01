
var EntityVersionList = function() {};

EntityVersionList.prototype = {
  init: function() {
    // Comparing entity versions click events
    $("#compareVersionsSelectorsAll").click (function () {
      $(".comparisonCheckBox").prop('checked', true);
    });
    $("#compareVersionsSelectorsNone").click (function () {
      $(".comparisonCheckBox").prop('checked', false);
    });
    $("#compareVersions").click (function () {
      var url = $(this).data('base-href');
      var numToCompare = 0;
      $(".comparisonCheckBox").each (function () {
        if ($(this).prop('checked')) {
          url += '/' + $(this).val();
          numToCompare += 1;
        }
      });
      if (numToCompare < 2) {
        window.alert("You need to select at least 2 versions to compare.");
      } else {
        document.location = url;
      }
    });
  }	
};


$(document).ready(function() {
  if ($("#entityversionlist").length > 0) {
    var page = new EntityVersionList();
    page.init();
  }
});
