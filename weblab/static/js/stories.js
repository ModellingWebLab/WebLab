/* stories facilities */

var $ = require('jquery');
var compare = require('./compare.js')

//spinner to indicate page is loading
var loadingSpinner = null;
class jQuerySpinner {
  constructor(options) {
    const opt = Object.assign({
      duration: 300,
      created: true
                }, options);
                this.parentId_ = opt.parentId;
                this.appendId_ = '_spinner_wrap';
                this.overlayId_ = `${this.parentId_}${this.appendId_}`;
    this.duration_ = opt.duration;
    if (opt.created) {
      this.createElement();
    }
  }

  createElement() {
      try {
          const $el = $(`#${this.parentId_}`);
          const str = `<div id="${this.overlayId_}" class="jquery-spinner-wrap"><div class="jquery-spinner-circle"><span class="jquery-spinner-bar"></span></div></div>`;
          const html = $.parseHTML(str);
          $el.append(html);
      } catch (err) {
          console.error(err);
      }
  }

  removeElement() {
    try {
      const $el = $(`#${this.overlayId_}`);
      $el.remove();
    } catch (err) {
      console.error(err);
    }
  }

  show() {
    $(`#${this.overlayId_}`).fadeIn(this.duration_);
  }

  hide() {
    $(`#${this.overlayId_}`).fadeOut(this.duration_);
  }
}


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
                <label id="${currentGraphCount}-models_or_group-label" for="id_graph-${currentGraphCount}-models_or_group">Select model or model group: </label><br/>
                
                
                
      <div class="modelgroup-model-selector">
             <div class="modelgroup-model-selector-row">
                <div class="modelgroup-model-selector-col left"><h5>Available models</h5></div>
                <div class="modelgroup-model-selector-col"><h5>Selected models & groups</h5></div>
             </div>
             <div class="modelgroup-model-selector-row">
                <div class="modelgroup-model-selector-col left"><label>Filter search: </label><input class="searchModel" id="${currentGraphCount}-searchAvailableModel" autocomplete="off"><br/></div>
                <div class="modelgroup-model-selector-colt"><ul class="errorlist"><li></li></ul></div>
             </div>

             <div class="modelgroup-model-selector-row">
                <div class="modelgroup-model-selector-col">
                    <select class="selectList modelgroupselect" id="id_graph-${currentGraphCount}-availableModels" size="2">
                        {% for model in part.models_or_group%}{{model}}{% endfor %}                      
                    </select>
                </div>
                <div class="modelgroup-model-selector-col div-table-buttons">
                   <input class="deselectModelFromGroup" id="id_graph-${currentGraphCount}-deselectModelFromGroup" type="button" value="◀" style="display: inline-block;" title="move left" alt="move left">
                   <input class="slectModelForGroup" id="id_graph-${currentGraphCount}-slectModelForGroup" type="button" value="▶" style="display: inline-block;" title="move right" alt="move right">
                </div>
                <div class="modelgroup-model-selector-col">
                    <select name="graph-${currentGraphCount}-id_models" class="selectList modelgroupselect selectedmodels" id="id_graph-${currentGraphCount}-id_models" size="2"></select>
                </div>
           </div><br/>
                
                <label id="${currentGraphCount}-protocol" for="id_graph-${currentGraphCount}-protocol">Select protocol: </label><select class="graphprotocol" name="graph-${currentGraphCount}-protocol" id="id_graph-${currentGraphCount}-protocol" disabled></select><br/>

                    Select which groups can be switched on and off in the graph: 
                    <div id="${currentGraphCount}groupToggleBox" class="groupToggleBox"></div>                
                
                
                <label id="${currentGraphCount}-graphfiles" for="id_graph-${currentGraphCount}-graphfiles">Select graph: </label><select class="graphfiles" name="graph-${currentGraphCount}-graphfiles" id="id_graph-${currentGraphCount}-graphfiles" disabled></select><br/><br/>
                <div id="${currentGraphCount}graphPreviewBox" class="graphPreviewBox">Please select a graph...</div>
                <br/>
              </td>
          </tr>`;

    // add new form
    $('#storyparts  > tbody').append(html);

    // Fill dropdowns
    // get graph selection elements
    modelorgroup = $(`#id_graph-${currentGraphCount}-availableModels`);
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

function updateLoadingSpinner(){
    num_not_loading = 0;
    $('.graphPreviewBox').each(function(){
        txt = $(this).text().trim();
        if(txt == 'Please select a graph...' || txt == 'failed to load the contents'){
            num_not_loading ++;
        }
    });

    if ((num_not_loading +  ($('.graphPreviewBox').find('canvas').length /2) + $('.graphPreviewBox').find('svg').length) <  $('.graphPreviewBox').length){
        if(loadingSpinner == null){
            loadingSpinner = new jQuerySpinner({parentId: 'fullwidthpage'});
        }
        loadingSpinner.show();
        setTimeout(updateLoadingSpinner, 1000);
    }else if(loadingSpinner != null){
        loadingSpinner.hide();
    }
}

// hook up functionality when document has loaded
$(document).ready(function(){

    // start loading spinner if needed
    updateLoadingSpinner();

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

  function get_models_str(id_prefix){
      models_str = ''
      $(`#${id_prefix}id_models`).children().each(function(){
          models_str += $(this).attr('value') + '_';
      });
      return models_str;
  }

  // update protocols when model changes
  $(document).on('modelsChanged', '.modelgroupselect', function(){
      id_prefix = $(this).attr('id').replace('id_models', '');
      url = `${getStoryBasePath()}/${get_models_str(id_prefix)}/protocols`;
      $(`#${id_prefix}protocol`).prop('disabled', true);
      $.ajax({url: url,
              success: function (data) {
                  $(`#${id_prefix}protocol`).html(data);
                  if($(`#${id_prefix}protocol`).find('option').length > 1){
                      $(`#${id_prefix}protocol`).prop('disabled', false);
                  }
                  $(`#${id_prefix}protocol`).change();
              }
      });
  });

  // update graphs when protocol changes
  $(document).on('change', '.graphprotocol', function(){
      id_prefix = $(this).attr('id').replace('protocol', '');
      id = id_prefix.replace('id_graph-', '').replace('-', '');
      $(`#${id_prefix}graphfiles`).prop('disabled', true);
      url = `${getStoryBasePath()}/${get_models_str(id_prefix)}/${$(this).val()}/graph`;
      $.ajax({url: url,
              success: function (data) {
                  $(`#${id_prefix}graphfiles`).html(data);
                  $(`#${id}groupToggleBox`).prop('disabled', true);
                  protocol = $(`#${id_prefix}protocol`).val();
                  if(protocol != ''){
                      toggle_url = `${getStoryBasePath()}/${id}/${get_models_str(id_prefix)}/${protocol}/toggles`;
                      $.ajax({url: toggle_url,
                              success: function (data) {
                                  $(`#${id}groupToggleBox`).html(data);
                                  // show all toggles
                                  $(`#${id}groupToggleBox`).find('input').each(function(){
                                      id_pref = $(this).attr('name').replace('grouptoggles', '').replace('graph', '');
                                      $(`<style>#label_selectGroup-group${id_pref}${$(this).val()} { visibility: visible; display: block;}</style>`).appendTo('head');
                                  });
                                  $(`#${id}groupToggleBox`).prop('disabled', false);
                                  $(`#${id_prefix}graphfiles`).prop('disabled', false);
                                  $(`#${id_prefix}graphfiles`).change();
                              }
                      });
                  }
             }
      });
  });

  // update graph preview when file changes
  $(document).on('change', '.graphfiles', function(){
      id_prefix = $(this).attr('id').replace('graphfiles', '');
      protocol = $(`#${id_prefix}protocol`).val();
      graphfile = $(this).val();

      if(graphfile != ''){
        // retreive experiment versions
        url = `${getStoryBasePath()}/${get_models_str(id_prefix)}/${protocol}/experimentversions`;
        $(`#${id_prefix}experimentVersionsUpdate`).prop('disabled', true);
        $.ajax({url: url,
                success: function(data){
                    data = data.trim();
                    $(`#${id_prefix}experimentVersionsUpdate`).val(data);
                    $(`#${id_prefix}experimentVersionsUpdate`).prop('disabled', false);
                    $(`#${id_prefix}experimentVersionsUpdate`).change();
                }
        });
      }else{
          if($(`#${id_prefix}experimentVersionsUpdate`).val().trim() != '/'){
              $(`#${id_prefix}experimentVersionsUpdate`).val('/');
              $(`#${id_prefix}experimentVersionsUpdate`).change();
          }
      }
  });

  // update graph preview when selected model groups change

  $(document).on('change', '.groupToggleSelect', function(){
      id_prefix = $(this).attr('name').replace('grouptoggles', '').replace('graph', '');
      if($(`#label_selectGroup-group${id_prefix}${$(this).val()}`).css('visibility') == 'hidden'){
          $(`<style>#label_selectGroup-group${id_prefix}${$(this).val()} { visibility: visible; display: block;}</style>`).appendTo('head');
      }else{
          $(`<style>#label_selectGroup-group${id_prefix}${$(this).val()} { visibility: hidden; display: none;}</style>`).appendTo('head');
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
        $(`#${graphId}graphPreviewBox`).removeClass('displayPlotFlot-preview');
        $(`#${graphId}graphPreviewBox`).removeClass('displayPlotHC-preview');
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
            graphPathEntities = `/experiments/compare/${experimentVersions}/graph_for_story`;

            // retreive selected groups
            $(`#${graphId}groupToggleBox`).find('input').each(function(){
                graphPathEntities += '/' + $(this).val();
            });

            graphPathEntities = basePath + graphPathEntities.replace('//', '/');
            $(`#${graphId}graphPreviewBox`).html(`<div class="graphPreviewDialog"><input type="hidden" id="${graphId}entityIdsToCompare" class="entityIdsToCompare" value="${graphPathIds}"><div class="entitiesToCompare" id="${graphId}entitiesToCompare" data-comparison-href="${graphPathEntities}">loading...</div><div id="${graphId}filedetails" class="filedetails"><div id="${graphId}filedisplay"></div></div></div>`);
            compare.initCompare(graphId, false);
        } else {
            $(`#${graphId}graphPreviewBox`).html('Please select a graph...');
        }
    });

    // update all graph previews if graph type changes
    $('#id_graphvisualizer').change(function() {
        $('.graphPreviewBox').each(function(){
            $(this).html('Switching graph visualizer...');
        });
        updateLoadingSpinner();
        $('.update_1').change();

    });
});


