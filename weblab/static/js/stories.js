var $ = require('jquery');
var compare = require('./compare.js')

/* stories facilities */
// Code to facilitate stories with text and graph parts
const SimpleMDE = require('./lib/simplemde.js');

function moveUp(id)
{
    me = $(id.closest('tr'));
    moveDown(me.prev());
}

function moveDown(id)
{
    me = $(id.closest('tr'));
    next = me.next();
    if (me.length && next.length){  // check we're not going off the start / end
        me.insertAfter(next);  // move
        // swap value of order for processing on server side
        order = me.find('.order');
        next_order = next.find('.order');
        current_order_val = order.val();
        order.val(next_order.val());
        next_order.val(current_order_val);
    }
}

function remove(clicked)
{
    id = $(clicked.closest('tr')).find('.order').attr('id');
    name =  $(clicked.closest('tr')).find('.order').attr('name');
    order = $(clicked.closest('tr')).find('.order').val();
    number = $(clicked.closest('tr')).find('.number').val();
    $("#storyform").append(`<input class="order" type="hidden" name="${name}" id="${id}" value="${order}">`);

    id = id.replace("ORDER", "DELETE");
    name = name.replace("ORDER", "DELETE");
    $("#storyform").append(`<input type="hidden" name="${name}" id="${id}" value="true">`);

    id = id.replace("DELETE", "number");
    name = name.replace("DELETE", "number");
    $("#storyform").append(`<input type="hidden" name="${name}" id="${id}" value="${number}">`);
    $(clicked.closest('tr')).remove();
}

function renderMde(id) // render text editor
{
    element = document.getElementById(id);
    // initialise editor
    var simplemde = new SimpleMDE({hideIcons:['guide', 'quote', 'heading'], showIcons: ['strikethrough', 'heading-1', 'heading-2', 'heading-3', 'code', 'table', 'horizontal-rule', 'undo', 'redo'], element:element});
    simplemde.render();
}

function insertDescriptionForm()
{
    currentTextCount = parseInt($('#id_text-TOTAL_FORMS').val());
    currentGraphCount = parseInt($('#id_graph-TOTAL_FORMS').val())
    order = currentGraphCount + currentTextCount;
    html=`
          <tr class="storypart description">
              <td>
                  <div class="storypart-controls">
                      <input class="uppart" type="button" value="▲" style="font-size:15px;margin:0;padding:0;width:20px;" title="move up" alt="move up">
                      <input class="downpart" type="button" value="▼" style="font-size:15px;margin:0;padding:0;width:20px;" title="move down" alt="move down">
                      <img class="deletepart" alt="remove story part" title="remove story part"/>
                      <input class="order" type="hidden" name="text-${currentTextCount}-ORDER" id="id_text-${currentTextCount}-ORDER" value="${order}">
                      <input class="number" type="hidden" name="text-${currentTextCount}-number" id="id_text-${currentTextCount}-number" value="${currentTextCount}">
                  </div>
              </td>
              <td class="storypart-content">
                 <textarea name="text-${currentTextCount}-description" cols="40" rows="10" id="id_text-${currentTextCount}-description"></textarea>
              </td>
          </tr>`;
    // add new form
    $('#storyparts  > tbody').append(html);
    renderMde(`id_text-${currentTextCount}-description`);
    currentTextCount++;
    $('#id_text-TOTAL_FORMS').val(currentTextCount);
}

// we may be running in a subfolder so we can't just assume /stories is the base path
function getStoryBasePath(){
    var url = $(location).attr('pathname');
    return url.replace(/stories.*/i, 'stories');
}

//checkbox toggels dropdown enabled
function insertGraphForm(){
    currentTextCount = parseInt($('#id_text-TOTAL_FORMS').val());
    currentGraphCount = parseInt($('#id_graph-TOTAL_FORMS').val())
    order = currentGraphCount + currentTextCount;

    html=`
          <tr class="storypart graph">
             <td>
                <div class="storypart-controls">
                  <input class="uppart" type="button" value="▲" style="font-size:15px;margin:0;padding:0;width:20px;" title="move up" alt="move up">
                  <input class="downpart" type="button" value="▼" style="font-size:15px;margin:0;padding:0;width:20px;" title="move down" alt="move down">
                  <img class="deletepart" alt="remove story part" title="remove story part"/>
                  <input class="order" type="hidden" name="graph-${currentGraphCount}-ORDER" id="id_graph-${currentGraphCount}-ORDER" value="${order}">
                  <input type="hidden" name="graph-${currentGraphCount}-currentGraph" class="currentGraph" id="id_graph-${currentGraphCount}-currentGraph" value="/">
                  <input class="number" type="hidden" name="graph-${currentGraphCount}-number" id="id_graph-${currentGraphCount}-number" value="${currentGraphCount}">
                </div>
              </td>
              <td class="storypart-content">
                <div class="StoryGraphRadio" style="Display:none">
                  <input type="radio" name="graph-${currentGraphCount}-update" value="True" id="id_graph-${currentGraphCount}-update_1" class="update_1 preview-graph-control" name="graph-${currentGraphCount}-update">
                  <input type="radio" name="graph-${currentGraphCount}-update" value="True" id="id_graph-${currentGraphCount}-update_0" class="update_0 preview-graph-control" name="graph-${currentGraphCount}-update" checked>
                  <input type="hidden" id="id_graph-${currentGraphCount}-experimentVersionsUpdate" class="experimentVersionsUpdate preview-graph-control" value="/">
                </div>
                <label id="${currentGraphCount}-models_or_group-label" for="id_graph-${currentGraphCount}-models_or_group">Select model or model group: </label><select class="modelgroupselect" name="graph-${currentGraphCount}-models_or_group" id="id_graph-${currentGraphCount}-models_or_group"></select><br/>
                <label id="${currentGraphCount}-protocol" for="id_graph-${currentGraphCount}-protocol">Select protocol: </label><select class="graphprotocol" name="graph-${currentGraphCount}-protocol" id="id_graph-${currentGraphCount}-protocol"></select><br/>
                <label id="${currentGraphCount}-graphfiles" for="id_graph-${currentGraphCount}-graphfiles">Select graph: </label><select class="graphfiles" name="graph-${currentGraphCount}-graphfiles" id="id_graph-${currentGraphCount}-graphfiles"></select><br/><br/>
                <div id="${currentGraphCount}graphPreviewBox" class="graphPreviewBox"></div>
                <br/>
              </td>
          </tr>`;

    // add new form
    $('#storyparts  > tbody').append(html);

    // Fill dropdowns
    // get graph selection elements
    modelorgroup = $(`#id_graph-${currentGraphCount}-models_or_group`);
    protocol = $(`#id_graph-${currentGraphCount}-protocol`);
    filename = $(`#id_graph-${currentGraphCount}-graphfiles`);
    // fill models or groups
    $.ajax({
      url: getStoryBasePath() + "/modelorgroup",
      success: function (data) {
          modelorgroup.html(data);
          // fill protocols
          url = getStoryBasePath() + "/protocols";
          $.ajax({
            url: url,
            success: function (data) {
              protocol.html(data);
              // file graph file names
              url2 = getStoryBasePath() + "/graph";
              $.ajax({
                url: url2,
                success: function (data) {
                  filename.html(data);
                }
              });
            }
          })
      }
    });

    // update number of graphs on page
    currentGraphCount++;
    $("#id_graph-TOTAL_FORMS").val(currentGraphCount);  // update number of forms
}

// hook up functionality when document has loaded
$(document ).ready(function(){
    // disable graph legend when submitting
    $('#newstoryform').submit(function(e) {
        $('.graphPreviewDialog').find('input').each(function(){
            $(this).prop('disabled', true);
        });
        $('.modelgroupselect').prop('disabled', false);
        $('.graphprotocol').prop('disabled', false);
        $('.graphfiles').prop('disabled', false);
    });

  // render markdown editors if editing
  $(".storypart").each(function(){
    if($(this).hasClass('description')){
        renderMde($(this).find('textarea').attr('id'));
    }
  });
  //checkbox toggels dropdown enabled
  $(document).on('click', '.preview-graph-control', function graphMenuVisibility(){
      id = $(this).attr('id');
      id = id.replace('id_graph-', '');
      id = id.replace('-update_0', '');
      id = id.replace('-update_1', '');
      update = $(`#id_graph-${id}-update_0`).is(':checked');
      $(`#id_graph-${id}-models_or_group`).prop("disabled", !update);
      $(`#id_graph-${id}-protocol`).prop("disabled", !update);
      $(`#id_graph-${id}-graphfiles`).prop("disabled", !update);
      $(`#${id}-models_or_group-label`).css('opacity', update ? '1.0' : '0.5');
      $(`#${id}-protocol`).css('opacity', update ? '1.0' : '0.5');
      $(`#${id}-graphfiles`).css('opacity', update ? '1.0' : '0.5');
  });

  // update protocols when model changes
  $(document).on('change', '.modelgroupselect', function(){
      id = $(this).attr('id').replace('-models_or_group', '');
      model = $(this).val();
      protocol = $(`#${id}-protocol`);
      filename = $(`#${id}-graphfiles`);
      // empty protocol & file while waiting
      protocol.html('');
      filename.html('');
      url = `${getStoryBasePath()}/${model}/protocols`;
      $.ajax({url: url,
              success: function (data) {
                  protocol.html(data);
                  protocol.change();
             }
      });
  });

  // update graphs when protocol changes
  $(document).on('change', '.graphprotocol', function(){
      id = $(this).attr('id').replace('-protocol', '');
      model = $(`#${id}-models_or_group`).val();
      protocol = $(this).val();
      filename = $(`#${id}-graphfiles`);
      filename.html('');
      url = `${getStoryBasePath()}/${model}/${protocol}/graph`;
      $.ajax({url: url,
              success: function (data) {
                  filename.html(data);
                  filename.change();
             }
      });
  });

  // update graph preview when file changes
  $(document).on('change', '.graphfiles', function(){
      id = $(this).attr('id').replace('-graphfiles', '');
      model = $(`#${id}-models_or_group`).val();
      protocol = $(`#${id}-protocol`).val();
      graphfile = $(this).val();
      experimentVersionsUpdate = $(`#${id}-experimentVersionsUpdate`);

      if(graphfile != ''){
        // retreive experiment versions
        url = `${getStoryBasePath()}/${model}/${protocol}/experimentversions`;
        $.ajax({url: url,
                success: function(data){
                    data = data.trim();
                    experimentVersionsUpdate.val(data);
                    experimentVersionsUpdate.change();
                }
        });
      }else{
          if(experimentVersionsUpdate.val().trim() != '/'){
            experimentVersionsUpdate.val('/');
            experimentVersionsUpdate.change();
          }
      }
  });

  //link add, delete and up/down button clicks
  $("#add-description").click(insertDescriptionForm);
  $("#add-graph").click(insertGraphForm);

  $("#storyparts").on("click", ".deletepart", function(){
      remove($(this));
  });

  $("#storyparts").on("click", ".uppart", function(){
      moveUp($(this));
  });

  $("#storyparts").on("click", ".downpart", function(){
      moveDown($(this));
  });

  // render markdown in story view
  const marked = require("./lib/marked.min.js");
  marked.setOptions({breaks: true,});

  $(".markdowrenderview").each(function(){
        source = $(this).find(".markdownsource").val();
        $(this).html(marked(source));
    });

  /* Graph Preview functionality */
  // update graph preview if any of the controls change
  $(body).on('change', '.preview-graph-control', function() {
        // get prefix graph Id
        var match = $(this).attr("id").match(/^id_graph-([0-9]*)-.*$/)
        graphId = match[1];

        //set relevant css class for preview box size
        $(`#${graphId}graphPreviewBox`).removeClass();
        $(`#${graphId}graphPreviewBox`).addClass(`${$('#id_graphvisualizer').val()}-preview`);
        if ($(`#id_graph-${graphId}-update_1`).is(':checked')) {
            experimentVersions = $(`#id_graph-${graphId}-experimentVersions`).val();
            currentGraph = $(`#id_graph-${graphId}-currentGraph`).val();
            currentGraphParts = currentGraph.split(' / ');
            graphFile = currentGraphParts[currentGraphParts.length - 1];
        } else {
            experimentVersions = $(`#id_graph-${graphId}-experimentVersionsUpdate`).val();
            graphFile = $(`#id_graph-${graphId}-graphfiles`).val();
        }
        if (experimentVersions != '/') {
            basePath = $('#base_uri').val(); // may be running in subfolder, so the base path (without /stories) is passed form django
            // compse url for ids for preview graph
            graphPathIds = `/experiments/compare/${experimentVersions}/show/${graphFile}/${$('#id_graphvisualizer').val()}`;
            graphPathIds = basePath + graphPathIds.replace('//', '/');

            // compse url for entities for preview graph
            graphPathEntities = `/experiments/compare/${experimentVersions}/info`;
            graphPathEntities = basePath + graphPathEntities.replace('//', '/');
            $(`#${graphId}graphPreviewBox`).html(`<div class="graphPreviewDialog"><input type="hidden" id="${graphId}entityIdsToCompare" value="${graphPathIds}"><div class="entitiesToCompare" id="${graphId}entitiesToCompare" data-comparison-href="${graphPathEntities}">loading...</div><div id="${graphId}filedetails" class="filedetails"><div id="${graphId}filedisplay"></div></div></div>`);
            compare.initCompare(graphId, false);
        } else {
            $(`#${graphId}graphPreviewBox`).html('Please select a graph...');
        }


    });

    // update all graph previews if graph type changes
    $('#id_graphvisualizer').change(function() {
        $('.experimentVersionsUpdate').change();
    });
});

