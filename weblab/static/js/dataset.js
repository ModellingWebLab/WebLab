function init() {

    $("#toggle-older-versions").click(function () {
        $(".older-version-mappings").toggle();
        if ($(".older-version-mappings").is(":visible")) {
            $(this).text("Hide older versions");
        } else {
            $(this).text("Show older versions");
        }
    });

    var $visibility = $("#versionVisibility");
    $visibility.on(
        'change',
        '#id_visibility',
        function () {
            updateVisibility(
                $visibility.data('change-href'),
                {
                    visibility: $(this).val(),
                })
        });


}

function updateVisibility(url, jsonObject) {
    var $actionIndicator = $("#versionVisibilityAction");
    $actionIndicator.html("<img src='" + staticPath + "img/loading2-new.gif' alt='loading' />");

    $.post(
        url,
        jsonObject,
        function (json) {
            if (json.updateVisibility) {
                var msg = json.updateVisibility.responseText;
                if (json.updateVisibility.response) {
                    $actionIndicator.html(
                        "<img src='" + staticPath + "img/check.png' alt='valid' /> " + msg);
                } else {
                    $actionIndicator.html("<img src='" + staticPath + "img/failed.png' alt='invalid' /> " + msg);
                }
            }
        }
    ).fail(function () {
        $actionIndicator.html("<img src='" + staticPath + "img/failed.png' alt='error' /> sorry, serverside error occurred.");
    }).done(function (json) {
        notifications.display(json);
    })
        .fail(function () {
            notifications.add("sorry, server-side error occurred", "error");
        });
}


module.exports = {
    init: init,
}
