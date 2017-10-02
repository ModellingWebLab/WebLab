/*
 * list is either `error` or `info`
 */

var notifications = {
  add: function(msg, list)
  {
    list = list || "error";
    var $errsList = $("#" + list + "list");
    var $errors = $("#" + list);
    var $item = $("<li>").html(msg).appendTo($errsList);

    $errors.removeClass("invisible");
  },

  display: function(json)
  {
    if (json && json.notifications)
    {
      if (json.notifications.errors)
      {
        var errs = json.notifications.errors;
        for(var i = 0; i < errs.length; i++)
          this.add(errs[i], "error");
      }
      if (json.notifications.notes)
      {
        var errs = json.notifications.notes;
        for(var i = 0; i < errs.length; i++)
          this.add(errs[i], "info");
      }
    }
  },

  clear: function(type) {
    $("#" + type + "list").empty();
    $("#" + type).addClass("invisible");
  }
};


module.exports = notifications;
