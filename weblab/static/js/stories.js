/* stories facilities */

var $ = require('jquery');
var compare = require('./compare.js')

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

//insert new graph form
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
                <label id="${currentGraphCount}-id_models" for="id_graph-${currentGraphCount}-id_models">Select model or model group: </label><br/>

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
                    <select class="selectList modelgroupselect" id="id_graph-${currentGraphCount}-availableModels" size="2" multiple>
                    </select>
                </div>
                <div class="modelgroup-model-selector-col div-table-buttons">
                   <input class="deselectModelFromGroup" id="id_graph-${currentGraphCount}-deselectModelFromGroup" type="button" value="◀" style="display: inline-block;" title="move left" alt="move left">
                   <input class="slectModelForGroup" id="id_graph-${currentGraphCount}-slectModelForGroup" type="button" value="▶" style="display: inline-block;" title="move right" alt="move right">
                </div>
                <div class="modelgroup-model-selector-col">
                    <select name="graph-${currentGraphCount}-id_models" class="selectList modelgroupselect selectedmodels" id="id_graph-${currentGraphCount}-id_models" size="2" multiple></select>
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

function get_models_str(id_prefix){
    models_str = ''
    $(`#${id_prefix}id_models`).children().each(function(){
        models_str += $(this).attr('value') + '_';
    });
    return models_str;
}

function backFillProtocol(){
    return $.ajax({url: `${getStoryBasePath()}/${get_models_str(this.id_prefix)}/protocols`,
                   context: this,
                   success: function (data) {
                       $(`#${this.id_prefix}protocol`).html(data);
                       $(`#${this.id_prefix}protocol`).val(this.protocol_selected);
                   }
           });
}

function backFillGraphFile(){
    return $.ajax({url: `${getStoryBasePath()}/${get_models_str(this.id_prefix)}/${this.protocol_selected}/graph`,
                   context: this,
                   success: function (data) {
                       $(`#${this.id_prefix}graphfiles`).html(data);
                       $(`#${this.id_prefix}graphfiles`).val(this.graph_file_selected);
                   }
    });
}

function backFillGroupToggles(){
    protocol_selected =  $(`#${this.id_prefix}protocol`).val();
    toggle_values = [];
    $(`#${this.id}groupToggleBox`).find('input').each(function(){
        if($(this).is(":checked")){
            toggle_values.push($(this).val());
        }
    });
    $.ajax({url: `${getStoryBasePath()}/${this.id}/${get_models_str(this.id_prefix)}/${protocol_selected}/toggles`,
            context: this,
            success: function (data) {
                $(`#${this.id}groupToggleBox`).html(data);
                $(`#${this.id}groupToggleBox`).find('input').each(function(){
                    $(this).prop('checked', toggle_values.includes($(this).val()));
                    $(this).change(); // show toggles as appropriate
                });
            }
    });
}

// backfil graph control
function backfilGraphControl(){
    this.protocol_selected =  $(`#${this.id_prefix}protocol`).val();
    this.graph_file_selected = $(`#${this.id_prefix}graphfiles`).val();
    $.when(backFillProtocol.bind(this)(), backFillGraphFile.bind(this)(), backFillGroupToggles.bind(this)()).done(function(){
        // link visibility change when update radio changes
        $(`#${this.id_prefix}update_0`).change(toggleEditVisibility.bind(this));
        $(`#${this.id_prefix}update_1`).change(toggleEditVisibility.bind(this));
        toggleEditVisibility.bind(this)();
    }.bind(this));
}

function toggleEditVisibility(){
    if($(`#id_graph-${this.id}-update_0`).is(':checked')){
        //make sure visability for toggles matches their selectedness
        $(`#${this.id}groupToggleBox`).find('input').each(function(){
            $(this).change();
        });

        $(`#id_graph-${this.id}-graph-selecttion-controls`).css({"visibility": "visible", "display": "block"});
    }else{
        //make sure all group toggles in original graph are visible
        groupToggles = $(`#id_graph-${this.id}-currentGroupToggles`).val();
        group_toggle_list = groupToggles.split('/');
        for (i = 0; i < group_toggle_list.length; i++) {
            $(`<style>#label_selectGroup-group-${this.id}-${group_toggle_list[i]} { visibility: visible; display: block;}</style>`).appendTo('body');
        }
        groupToggles = $(`#id_graph-${this.id}-currentGroupToggles-off`).val();
        group_toggle_list = groupToggles.split('/');
        for (i = 0; i < group_toggle_list.length; i++) {
            $(`<style>#label_selectGroup-group-${this.id}-${group_toggle_list[i]} { visibility: hidden; display: none;}</style>`).appendTo('body');
        }
        $(`#id_graph-${this.id}-graph-selecttion-controls`).css({"visibility": "hidden", "display": "none"});
    }
    $(`#id_graph-${this.id}-experimentVersionsUpdate`).change();
}

// hook up functionality when document has loaded
$(document).ready(function(){
    //busy cursor if appropriate
    var numGraphs = $('.graphPreviewBox').length - $('.graphPreviewButton').length;
    if(numGraphs >0){
        $('#fullwidthpage').css('cursor', 'wait');
    }
    $('body').on('graphDrawn', function(){
        numGraphs--;
        if(numGraphs <=0){
            $('#fullwidthpage').css('cursor', 'default');
        }
    });

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
                  $(`#${id}groupToggleBox`).html('');
                  protocol = $(`#${id_prefix}protocol`).val();
                  if(protocol != ''){
                      toggle_url = `${getStoryBasePath()}/${id}/${get_models_str(id_prefix)}/${protocol}/toggles`;
                      $.ajax({url: toggle_url,
                              success: function (data) {
                                  $(`#${id}groupToggleBox`).html(data);
                                  // show all toggles
                                  $(`#${id}groupToggleBox`).find('input').each(function(){
                                      id_pref = $(this).attr('name').replace('grouptoggles', '').replace('graph', '');
                                      $(`<style>#label_selectGroup-group${id_pref}${$(this).val()} { visibility: visible; display: block;}</style>`).appendTo('body');

                                  });
                                  $(`#${id_prefix}graphfiles`).prop('disabled', false);
                                  $(`#${id_prefix}graphfiles`).change();
                              }
                      });
                  }else{
                      $(`#${id_prefix}graphfiles`).change();
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
        $.ajax({url: url,
                success: function(data){
                    data = data.trim();
                    $(`#${id_prefix}experimentVersionsUpdate`).val(data);
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
      if($(this).is(':checked')){
          $(`<style>#label_selectGroup-group${id_prefix}${$(this).val()} { visibility: visible; display: block;}</style>`).appendTo('body');
      }else{
          $(`<style>#label_selectGroup-group${id_prefix}${$(this).val()} { visibility: hidden; display: none;}</style>`).appendTo('body');
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
  // back fill graph controls
  $(body).on('change', '.preview-graph-control', function() {
       var match = $(this).attr("id").match(/^id_graph-([0-9]*)-.*$/)
        graphId = match[1];
        //set relevant css class for preview box size
        $(`#${graphId}graphPreviewBox`).removeClass('displayPlotFlot-preview');
        $(`#${graphId}graphPreviewBox`).removeClass('displayPlotHC-preview');
        $(`#${graphId}graphPreviewBox`).addClass(`${$('#id_graphvisualizer').val()}-preview`);
        groupToggles = '';
        if ($(`#id_graph-${graphId}-update_1`).is(':checked')) {
            experimentVersions = $(`#id_graph-${graphId}-experimentVersions`).val();
            graphFile = $(`#id_graph-${graphId}-currentGraph`).val();
            groupToggles = $(`#id_graph-${graphId}-currentGroupToggles`).val();
        } else {
            experimentVersions = $(`#id_graph-${graphId}-experimentVersionsUpdate`).val();
            graphFile = $(`#id_graph-${graphId}-graphfiles`).val();
            // retreive selected groups
            $(`#${graphId}groupToggleBox`).find('input').each(function(){
                groupToggles += '/' + $(this).val();
            });
            //make sure vasability for toggles matches their selectedness

        }

        if (experimentVersions != '/') {
            basePath = $('#base_uri').val(); // may be running in subfolder, so the base path (without /stories) is passed form django
            // compse url for ids for preview graph
            graphPathIds = `/experiments/compare/${experimentVersions}/show/${graphFile}/${$('#id_graphvisualizer').val()}`;
            graphPathIds = basePath + graphPathIds.replace('//', '/');

            // compse url for entities for preview graph
            graphPathEntities = `/experiments/compare/${experimentVersions}/graph_for_story${groupToggles}`;

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
            if($(this).find('.graphPreviewButton').length == 0){
                $(this).html('Switching graph visualizer...');
                id = $(this).attr('id').replace('graphPreviewBox', '')
                $(`#id_graph-${id}-update_0`).change();
            }
        });
    });

    // if the selected model has a value fill it and use ajax to backfil the rest of the form so we can edit it.
    $('.selectedmodels').each(function(){
        if($(this).find('option').length){
            context = {id_prefix: $(this).attr('id').replace('id_models', ''),
                       id: $(this).attr('id').replace('id_models', '').replace('id_graph-', '').replace('-', '')};
                       if($(`#${context.id_prefix}update_0`).is('checked')){
                           backfilGraphControl.bind(context)();
                           $(`#${context.id_prefix}-0-update_0`).change(toggleEditVisibility.bind(context));
                           $(`#${context.id_prefix}-0-update_1`).change(toggleEditVisibility.bind(context));
                       }else{
                           $(`#${context.id_prefix}update_0`).one('change', backfilGraphControl.bind(context));
                       }
        }
    });

});



