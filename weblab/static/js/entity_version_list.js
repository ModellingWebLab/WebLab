
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
      $(".comparisonCheckBox").each (function () {
        if ($(this).prop('checked')) {
          url += '/' + $(this).val();
        }
      });
      console.log(url);
      if (url)
        document.location = url;
      else
        window.alert("You need to select some versions to compare.");
    });
  }	
};


$(document).ready(function() {
  if ($("#entityversionlist").length > 0) {
    var page = new EntityVersionList();
    page.init();
  }
});
