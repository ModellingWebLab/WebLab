function fetchCategories($ul) {
  $("#pmr-category").hide();
  $("#pmr-model").hide();
  $ul.empty();
    $.getJSON($ul.data('categories-href'), function(data) {
      $.each(data.categories, function(i, cat) {
        $ul.append('<li><a href="javascript:;" data-href="' + cat.url + '">' + cat.name + '</a></li>');
      });
    }).fail(function() {
      console.log('failed to fetch category list');
    });
}

function fetchModels($a) {
  $("#pmr-model").hide();

  var $div = $("#pmr-models").hide();
  $.getJSON($a.data('href'), function(data) {
    $div.find('h2').text('Models in ' + data.name);
    var $ul = $div.show().find('ul').empty();
    $.each(data.links, function(i, link) {
      $ul.append('<li><a href="javascript:;" data-href="' + link.url + '">' + link.prompt + '</a></li>');
    });
  }).fail(function() {
    console.log('failed to fetch model list for ' + $a.text());
  });
}

function fetchModel($a) {
  var $div = $("#pmr-model").hide();
  $.getJSON($a.data('href'), function(data) {
    $div.show();
    $div.find('h3').text(data.title);
    $div.find('#git-url').attr('href', data.git_url).text(data.git_url);
    //$div.find('h2').text('Models in ' + data.name);
    //$div.find(".git_url')
    
  }).fail(function() {
    console.log('failed to fetch model data');
  });
}

function categoryClick() {
  fetchModels($(this));
}

function modelClick() {
  fetchModel($(this));
}


$(document).ready(function() {
  var $div = $("#pmr-browse");
  if ($div.length > 0) {
    fetchCategories($div.find("#pmr-categories"));

    $('#pmr-categories').on('click', 'li a', categoryClick);
    $('#pmr-models').on('click', 'li a', modelClick);
  }
});

