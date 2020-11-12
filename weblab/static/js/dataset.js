function init() {

  $("#toggle-older-versions").click(function() {
    $(".older-version-mappings").toggle();
    if ($(".older-version-mappings").is(":visible")) {
      $(this).text("Hide older versions");
    } else {
      $(this).text("Show older versions");
    }
  });
}


module.exports = {
  init: init,
}
