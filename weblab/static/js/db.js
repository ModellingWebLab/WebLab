var $ = require('jquery');
var notifications = require('./lib/notifications.js')
var utils = require('./lib/utils.js')

var pages = ["matrix"],
    comparisonMode = false,
    experimentsToCompare = {},
    linesToCompare = {},
    baseUrls = {}; // These are filled in if we are viewing a sub-matrix

/**
 * Submit a request to create an experiment.
 * @param jsonObject  the data to send;
 *    an object with fields { task: "newExperiment", model, model_version, protocol, protocol_version }
 * @param $td  the table cell to contain this experiment
 * @param entry  the entry for this experiment in the data matrix
 */
function submitNewExperiment(jsonObject, $td, entry, tablePrefix)
{

    div = $("#" + tablePrefix + "matrixdiv");
    $td.append("<img src='" + staticPath + "img/loading2-new.gif' alt='loading' />");

    $.post(div.data('new-href'), jsonObject, function(data)
    {
        var msg = data.newExperiment.responseText;
        $td.removeClass("experiment-QUEUED experiment-RUNNING experiment-INAPPLICABLE experiment-FAILED experiment-PARTIAL experiment-SUCCESS");
        $td.unbind("click");

        if (data.newExperiment.response) {
            notifications.add(msg, "info");
        } else {
            notifications.add(msg, "error");
        }
        entry.experiment = {
            name: data.newExperiment.expName,
            id: data.newExperiment.expId,
            latestResult: data.newExperiment.status,
            url: data.newExperiment.url,
        };
        $td.addClass("experiment-" + data.newExperiment.status);
        setExpListeners($td, entry, tablePrefix);
    }).fail(function()
    {
        notifications.add("Server-side error occurred submitting experiment.", "error");
        $td.addClass("experiment-FAILED");
    }).always(function(data)
    {
        notifications.display(data);
        $td.contents().remove();
    });
}


function drawMatrix(matrix, tablePrefix)
{
    div = $("#" + tablePrefix + "matrixdiv");
    var rows = [],
        columns = [],
        rowMapper = {},
        columnMapper = {},
        mat = [];

    for (var key in matrix.rows)
        if (matrix.rows.hasOwnProperty(key)) {
            var rowId = matrix.rows[key].id;
            rowMapper[rowId] = matrix.rows[key];
            rows.push(rowId);
        }

    for (var key in matrix.columns)
        if (matrix.columns.hasOwnProperty(key)) {
            var columnId = matrix.columns[key].id;
            columnMapper[columnId] = matrix.columns[key];
            columns.push(columnId);
        }

    // Sort rows & columns alphabetically (case insensitive)
    rows.sort(function(a, b)
    {
        return (rowMapper[a].name.toLocaleLowerCase() > rowMapper[b].name.toLocaleLowerCase()) ? 1 : ((rowMapper[b].name.toLocaleLowerCase() > rowMapper[a].name.toLocaleLowerCase()) ? -1 : 0);
    });
    columns.sort(function(a, b)
    {
        return (columnMapper[a].name.toLocaleLowerCase() > columnMapper[b].name.toLocaleLowerCase()) ? 1 : ((columnMapper[b].name.toLocaleLowerCase() > columnMapper[a].name.toLocaleLowerCase()) ? -1 : 0);
    });

    for (var i = 0; i < rows.length; i++) {
        mat[i] = [];
        for (var j = 0; j < columns.length; j++) {
            mat[i][j] = {
                rowData: rowMapper[rows[i]],
                columnData: columnMapper[columns[j]]
            };
            rowMapper[rows[i]].row = i;
            columnMapper[columns[j]].col = j;
        }
    }

    for (var key in matrix.experiments) {
        if (matrix.experiments.hasOwnProperty(key)) {
            var exp = matrix.experiments[key],
                row = rowMapper[exp.model.id].row,
                colEntity = exp.dataset || exp.protocol,
                col = columnMapper[colEntity.id].col;
            exp.name = exp.model.name + " @ " + exp.model.version + " & " + colEntity.name + " @ " + colEntity.version;
            mat[row][col].experiment = exp;
        }
    }

    table = document.createElement("table");
    div.empty();
    table.setAttribute("class", "matrixTable");
    div.append(table);

    if (mat.length == 0) {
        table.innerHTML = "<p class='failed'>No experiments found matching the selected view criteria.</p>";
        return;
    }

    for (var row = -1; row < mat.length; row++) {
        var tr = document.createElement("tr");
        table.appendChild(tr);
        for (var col = -1; col < mat[0].length; col++) {
            var td = document.createElement("td"),
                $td = $(td);
            tr.appendChild(td);
            td.setAttribute("id", tablePrefix + "matrix-entry-" + row + "-" + col);

            if (row == -1 && col == -1)
                continue;

            // Top row: column names
            if (row == -1) {
                var d1 = document.createElement("div"),
                    d2 = document.createElement("div"),
                    a = document.createElement("a"),
                    column = mat[0][col].columnData;
                a.href = column.url;
                d2.setAttribute("class", "vertical-text");
                d1.setAttribute("class", "vertical-text__inner");
                d2.appendChild(d1);
                a.appendChild(document.createTextNode(column.name));
                d1.appendChild(a);
                td.appendChild(d2);
                $td.addClass("matrixTableCol")
                    .data({
                        col: col,
                        columnId: column.entityId,
                        columnVersion: column.id
                    })
                    .click(function(ev)
                    {
                        if (comparisonMode) {
                            ev.preventDefault();
                            addToComparison($(this), 'col', tablePrefix);
                        }
                    });
                continue;
            }

            // Left column: model names
            if (col == -1) {
                var a = document.createElement("a"),
                    model = mat[row][0].rowData;
                a.href = model.url;
                a.appendChild(document.createTextNode(model.name));
                td.appendChild(a);
                $td.addClass("matrixTableRow")
                    .data({
                        row: row,
                        modelId: model.entityId,
                        modelVersion: model.id
                    })
                    .click(function(ev)
                    {
                        if (comparisonMode) {
                            ev.preventDefault();
                            addToComparison($(this), 'row', tablePrefix);
                        }
                    });
                continue;
            }

            // Normal case
            var entry = mat[row][col];
            entry.row = row;
            entry.col = col;
            $td.data("entry", entry).addClass(tablePrefix + "matrix-row-" + row).addClass(tablePrefix + "matrix-col-" + col);
            if (entry.experiment)
                $td.addClass("experiment experiment-" + entry.experiment.latestResult);
            else
                $td.addClass("experiment experiment-NONE");

            setExpListeners($td, entry, tablePrefix);
        }
    }

    // Fix the matrix layout, so it doesn't jump on hovers
    var rowWidth = 0,
        rowHeight = 0,
        colWidth = 0,
        colHeight = 0;
    $(table).find("td.matrixTableRow").addClass("matrixHover").each(function()
    {
        rowWidth = Math.max(rowWidth, this.offsetWidth);
        rowHeight = Math.max(rowHeight, this.offsetHeight);
    });
    $(table).find("td.matrixTableCol").addClass("matrixHover").each(function()
    {
        colWidth = Math.max(colWidth, this.offsetWidth);
        colHeight = Math.max(colHeight, this.offsetHeight);
    });
    $(table).find("td.matrixTableRow").removeClass("matrixHover").each(function()
    {
        $(this).height(rowHeight).width(rowWidth);
    });
    $(table).find("td.matrixTableCol").removeClass("matrixHover").each(function()
    {
        $(this).height(colHeight).width(colWidth);
    });
}


/**
 * Set up the click/hover listeners for the given matrix entry
 * @param $td  the table cell
 * @param entry  mat[row][col] for this table cell
 */
function setExpListeners($td, entry, tablePrefix)
{
    $div = $("#" + tablePrefix + "matrixdiv");
    // Click listener
    if (entry.experiment) {
        addMatrixClickListener($td, entry.experiment.url, entry.experiment.id, entry.experiment.latestResult, tablePrefix);
    } else {
        var experimentType = $div.data('experiment-type');
        if (experimentType == 'fitting') {
            // Link through to fitting submission form
            $td.click(function()
            {
                var link = $div.data('new-fitting-href') + '?';
                var params = {
                    'model': entry.rowData.entityId,
                    'model_version': entry.rowData.id,
                    'dataset': entry.columnData.id,
                    'protocol': entry.columnData.protocolId,
                    'protocol_version': entry.columnData.protocolLatestVersion,
                    'fittingspec': $div.data('fittingspec-id'),
                    'fittingspec_version': $div.data('fittingspec-version'),
                }
                location.href = link + $.param(params);
            });
        } else {
            // Submit new experiment directly
            $td.click(function()
            {
                submitNewExperiment({
                    task: "newExperiment",
                    model: entry.rowData.entityId,
                    model_version: entry.rowData.id,
                    protocol: entry.columnData.entityId,
                    protocol_version: entry.columnData.id,
                }, $td, entry, tablePrefix);
            });
        }
    }

    // Highlight the relevant row & column labels when the mouse is over this cell
    $td.mouseenter(function(ev)
    {
        $("#" + tablePrefix + "matrix-entry--1-" + entry.col).addClass("matrixHover");
        $("#" + tablePrefix + "matrix-entry-" + entry.row + "--1").addClass("matrixHover");
    }).mouseleave(function(ev)
    {
        $("#" + tablePrefix + "matrix-entry--1-" + entry.col).removeClass("matrixHover");
        $("#" + tablePrefix + "matrix-entry-" + entry.row + "--1").removeClass("matrixHover");
    });
}

/**
 * Handle a click on a row or column header when in comparison mode.
 *
 * Toggles the selected state of this row/column.  If only one ends up selected, then all cells in that row/column are
 * included in the comparison.  If at least one row and column are selected, then we only compare experiments that
 * feature both a selected row and column.
 *
 * Note that users MAY select extra experiments not in a selected row/column.  Such choices should not be affected by
 * this method.  Clicking on individual experiments selected via this mechanism will also toggle their state, but may
 * be overridden by a subsequent selection via this method.
 *
 * @param $td  the header clicked on
 * @param rowOrCol  either 'row' or 'col'
 */
function addToComparison($td, rowOrCol, tablePrefix)
{
    var index = $td.data(rowOrCol),
        lineIndex = linesToCompare[tablePrefix][rowOrCol].indexOf(index),
        cells = $("." + tablePrefix + "matrix-" + rowOrCol + "-" + index),
        colOrRow = (rowOrCol == 'row' ? 'col' : 'row'),
        otherTypeSelected = (linesToCompare[tablePrefix][colOrRow].length > 0);
    if (lineIndex != -1) {
        // Was selected already -> unselect
        linesToCompare[tablePrefix][rowOrCol].splice(lineIndex, 1);
        $td.removeClass("patternized");
        // Clear any selected experiments in this line
        cells.filter(".patternized").each(function()
        {
            var $cell = $(this),
                cellIndex = experimentsToCompare[tablePrefix].indexOf($cell.data("entry").experiment.id);
            if (cellIndex != -1) {
                experimentsToCompare[tablePrefix].splice(cellIndex, 1);
                $cell.removeClass("patternized");
            }
        });
        // If this was the only line of this type selected, select all experiments in any selected colOrRow
        if (linesToCompare[tablePrefix][rowOrCol].length == 0) {
            $.each(linesToCompare[tablePrefix][colOrRow], function(i, otherLineIndex)
            {
                $("." + tablePrefix + "matrix-" + colOrRow + "-" + otherLineIndex).not(".patternized").each(function(i, elt)
                {
                    var $cell = $(elt),
                        exp = $cell.data("entry").experiment;
                    if (exp && isSelectableResult(exp.latestResult)) {
                        experimentsToCompare[tablePrefix].push(exp.id);
                        $cell.addClass("patternized");
                    }
                });
            });
        }
    } else {
        // Select this row/col
        linesToCompare[tablePrefix][rowOrCol].push(index);
        $td.addClass("patternized");
        $("#" + tablePrefix + "comparisonMatrix").show();
        // If this is the first line of this type, clear lines of the other type
        if (linesToCompare[tablePrefix][rowOrCol].length == 1) {
            $.each(linesToCompare[tablePrefix][colOrRow], function(i, otherLineIndex)
            {
                $("." + tablePrefix + "matrix-" + colOrRow + "-" + otherLineIndex).filter(".patternized").each(function(i, elt)
                {
                    var $cell = $(elt),
                        cellIndex = experimentsToCompare[tablePrefix].indexOf($cell.data("entry").experiment.id);
                    experimentsToCompare[tablePrefix].splice(cellIndex, 1);
                    $cell.removeClass("patternized");
                });
            });
        }
        // Select experiments in this line
        cells.not(".patternized").each(function()
        {
            var $cell = $(this),
                entry = $cell.data("entry"),
                exp = entry.experiment;
            if (exp && isSelectableResult(exp.latestResult) &&
                (!otherTypeSelected || linesToCompare[tablePrefix][colOrRow].indexOf(entry[colOrRow]) != -1)) {
                experimentsToCompare[tablePrefix].push(exp.id);
                $cell.addClass("patternized");
            }
        });
    }
    computeComparisonLink(tablePrefix);
}

/**
 * Toggle whether the given experiment is selected in comparison mode.
 * @param $td  the table cell
 * @param expId  the experiment id
 * @returns whether the experiment is now selected
 */
function toggleSelected($td, expId, tablePrefix)
{
    var index = experimentsToCompare[tablePrefix].indexOf(expId);
    if (index != -1) {
        // was selected -> unselect
        experimentsToCompare[tablePrefix].splice(index, 1);
        $td.removeClass("patternized");
    } else {
        // add a new element to the list
        experimentsToCompare[tablePrefix].push(expId);
        $td.addClass("patternized");
    }
    return (index == -1);
}

/**
 * Compute the 'compare experiments' link in comparison mode,
 * and show the button iff there are experiments to compare.
 */
function computeComparisonLink(tablePrefix)
{
    var $comparisonLink = $("#" + tablePrefix + "comparisonLink");
    if (experimentsToCompare[tablePrefix].length > 0) {
        var newHref = $comparisonLink.data('comparison-href');
        for (var i = 0; i < experimentsToCompare[tablePrefix].length; i++)
            newHref += '/' + experimentsToCompare[tablePrefix][i];
        $("#" + tablePrefix + "comparisonLink").show().data("href", newHref);
    } else {
        $("#" + tablePrefix + "comparisonMatrix").hide();
        $("#" + tablePrefix + "comparisonLink").hide();
    }
}

/**
 * Determine whether an experiment with the given result status can be selected for comparison.
 */
function isSelectableResult(result)
{
    return (result == "SUCCESS" || result == "PARTIAL");
}

function addMatrixClickListener($td, link, expId, result, tablePrefix)
{
    $td.click(function(ev)
    {
        if (comparisonMode) {
            if (!isSelectableResult(result))
                return;
            toggleSelected($td, expId, tablePrefix);
            computeComparisonLink(tablePrefix);
        } else {
            document.location.href = link;
        }
    });
}


function getMatrix(params, tablePrefix)
{
    div = $("#" + tablePrefix + "matrixdiv");
    var baseUrl = $(div).data('base-json-href');
    $.getJSON(baseUrl, params, function(data)
    {
        if (data.getMatrix) {
            drawMatrix(data.getMatrix, tablePrefix);
        }
    }).always(function(data)
    {
        notifications.display(data);
    });
}


/**
 * Parse the current location URL to determine what part of the matrix to show.
 * The URL pathname should look like: {contextPath}/db/models/id1/id2/protocols/id3/id4
 * or {contextPath}/db/models/id1/id2/datasets/id3/id4
 * If no models or protocols/datasets are given, we show everything.
 * The URL can also be {contextPath}/db/public to show only what anonymous users can view.
 * Returns a JSON object to be passed to getMatrix();
 */
function parseLocation(tablePrefix)
{
    div = $("#" + tablePrefix + "matrixdiv");
    base = div.data('base-href'),
        rowType = div.data('row-type'),
        columnType = div.data('column-type'),
        rest = "",
        ret = {},
        queryParams = (new URL(document.location)).searchParams;

    if (document.location.pathname.substr(0, base.length) == base) {
        rest = document.location.pathname.substr(base.length);
    }

    $("." + tablePrefix + "showButton").removeClass("selected");
    $("." + tablePrefix + "showMyButton").hide();
    if (rest.length > 0) {
        var rowUrlFragment = rowType + 's',
            columnUrlFragment = columnType + 's',
            items = rest.replace(/^\//, "").split("/"),
            rowIndex = items.indexOf(rowUrlFragment);
        colIndex = items.indexOf(columnUrlFragment);
        if (colIndex != -1) {
            if (rowIndex != -1) {
                // /models/1/2/protocols/3/4
                // /models/1/2/datasets/3/4
                ret.rowIds = parts = items.slice(rowIndex + 1, colIndex);
                versionIndex = parts.indexOf('versions')
                if (versionIndex != -1) {
                    // /models/1/2/protocols/3/versions/abc/def
                    ret.rowIds = parts.slice(0, versionIndex);
                    ret.rowVersions = parts.slice(versionIndex + 1);
                }
            }
            // /protocols/3/4
            // /datasets/3/4
            parts = ret.columnIds = items.slice(colIndex + 1);
            versionIndex = parts.indexOf('versions')
            if (versionIndex != -1) {
                // /protocols/3/versions/abc/def
                ret.columnIds = parts.slice(0, versionIndex);
                ret.columnVersions = parts.slice(versionIndex + 1);
            }
        } else if (rowIndex != -1) {
            // /models/1/2
            ret.rowIds = parts = items.slice(rowIndex + 1);
            versionIndex = parts.indexOf('versions')
            if (versionIndex != -1) {
                // /models/1/versions/xyz
                ret.rowIds = parts.slice(0, versionIndex);
                ret.rowVersions = parts.slice(versionIndex + 1);
            }
        }

        if (rowIndex != -1) {
            baseUrls[tablePrefix].row = "/" + rowUrlFragment + "/" + ret.rowIds.join("/");
        }
        if (colIndex != -1) {
            baseUrls[tablePrefix].col = "/" + columnUrlFragment + "/" + ret.columnIds.join("/");
        }

        if (rowIndex == -1 && colIndex == -1) {
            if (items[0] == "public") {
                $("#" + tablePrefix + "showPublicExpts").addClass("selected");
                ret.subset = "public";
            } else if (items[0] == "mine") {
                $("#" + tablePrefix + "showMyExpts").addClass("selected");
                $("." + tablePrefix + "showMyButton").show();
                ret.subset = "mine";

                $("#" + tablePrefix + "showMyExptsModels").text("Hide moderated models");
                $("#" + tablePrefix + "showMyExptsProtocols").text("Hide moderated protocols");
                $("#" + tablePrefix + "showMyExptsDatasets").text("Hide moderated datasets");

                var query = location.search.substr(1);
                var result = {};
                query.split("&").forEach(function(part)
                {
                    var item = part.split("=");
                    if (item[0] == 'moderated-models' && item[1] == 'false') {
                        ret["moderated-models"] = "false";
                        $("#" + tablePrefix + "showMyExptsModels").text("Show moderated models");
                    }
                    if (item[0] == 'moderated-protocols' && item[1] == 'false') {
                        ret["moderated-protocols"] = "false";
                        $("#" + tablePrefix + "showMyExptsProtocols").text("Show moderated protocols");
                    }
                    if (item[0] == 'moderated-datasets' && item[1] == 'false') {
                        ret["moderated-datasets"] = "false";
                        $("#" + tablePrefix + "showMyExptsDatasets").text("Show moderated datasets");
                    }
                    result[item[0]] = decodeURIComponent(item[1]);
                });
            } else if (items[0] == "all") {
                $("#" + tablePrefix + "showAllExpts").addClass("selected");
                ret.subset = "all";
            } else {
                $("#" + tablePrefix + "showModeratedExpts").addClass("selected");
                ret.subset = "moderated";
            }
        }
    } else {
        $("#" + tablePrefix + "showModeratedExpts").addClass("selected");
        ret.subset = "moderated";
    }
    return ret;
}

function prepareMatrix(tablePrefix)
{
    div = $("#" + tablePrefix + "matrixdiv");
    div.append($("<img src='" + staticPath + "/img/loading2-new.gif' alt='loading'>"));
    div.append(document.createTextNode("Preparing experiment matrix; please be patient."));

    var components = parseLocation(tablePrefix);
    getMatrix(components, tablePrefix);

    $("#" + tablePrefix + "comparisonModeButton").text(comparisonMode ? "Disable" : "Enable")
        .click(function()
        {
            comparisonMode = !comparisonMode;
            $("#" + tablePrefix + "comparisonModeButton").text(comparisonMode ? "Disable" : "Enable");
            if (!comparisonMode) {
                // Clear all selections
                experimentsToCompare[tablePrefix].splice(0, experimentsToCompare[tablePrefix].length);
                linesToCompare[tablePrefix].row.splice(0, linesToCompare[tablePrefix].row.length);
                linesToCompare[tablePrefix].col.splice(0, linesToCompare[tablePrefix].col.length);
                $("." + tablePrefix + "patternized").removeClass("patternized");
                $("#" + tablePrefix + "comparisonLink").hide();
                $("#" + tablePrefix + "comparisonMatrix").hide();
            }
        });
    $("#" + tablePrefix + "comparisonLink").click(function()
    {
        document.location = $(this).data("href");
    });
    $("#" + tablePrefix + "comparisonMatrix").click(function()
    {
        var url = $(div).data('base-href');
        if (url.substr(-1) === '/') {
            url = url.slice(0, -1);
        }

        if (linesToCompare[tablePrefix].row.length > 0) {
            var rows = linesToCompare[tablePrefix].row.map(i => $("#" + tablePrefix + "matrix-entry-" + i + "--1"));
            var rowIds = rows.map($row => $row.data('modelId'));
            var rowVersions = rows.map($row => $row.data('modelVersion'));
            if (components.rowVersions) {
                url += '/models/' + rowIds[0] + '/versions/' + rowVersions.join('/');
            } else {
                url += '/models/' + rowIds.join('/');
            }
        } else {
            url += baseUrls[tablePrefix].row;
            if (components.rowVersions) {
                url += '/versions/' + components.rowVersions.join('/');
            }
        }

        if (linesToCompare[tablePrefix].col.length > 0) {
            var colType = $(div).data('column-type');
            var cols = linesToCompare[tablePrefix].col.map(i => $("#" + tablePrefix + "matrix-entry--1-" + i));

            var colIds = cols.map($col => $col.data('columnId'));
            var colVersions = cols.map($col => $col.data('columnVersion'));
            var colUrlPrefix = '/' + colType + 's/';
            if (components.columnVersions) {
                url += colUrlPrefix + colIds[0] + '/versions/' + colVersions.join('/');
            } else {
                url += colUrlPrefix + colIds.join('/');
            }
        } else {
            url += baseUrls[tablePrefix].col;
            if (components.columnVersions) {
                url += '/versions/' + components.columnVersions.join('/');
            }
        }
        document.location.href = url; // TODO: use history API instead?
    });
    $("#" + tablePrefix + "comparisonLink").hide();
    $("#" + tablePrefix + "comparisonMatrix").hide();

    function getBaseUrl()
    {
        var url = $(div).data('base-href'),
            suffix = $("." + tablePrefix + "showButton.selected").data('suffix');
        if (url.substr(-1) === '/') {
            url = url.slice(0, -1);
        }
        if (suffix) {
            url = url + '/' + suffix;
        }
        return url + '?';
    }

    function hideModeratedParams(hideModels, hideProtocols, hideDatasets)
    {
        var params = {};
        if (hideModels) params['moderated-models'] = false;
        if (hideProtocols) params['moderated-protocols'] = false;
        if (hideDatasets) params['moderated-datasets'] = false;
        return params;
    }

    // The my/public/moderated view buttons
    $("#" + tablePrefix + "showModeratedExpts").click(function()
    {
        if (!$(this).hasClass("selected")) {
            $("." + tablePrefix + "showButton").removeClass("selected");
            $(this).addClass("selected");
            document.location.href = getBaseUrl();
        }
    });
    $("#" + tablePrefix + "showPublicExpts").click(function()
    {
        if (!$(this).hasClass("selected")) {
            $("." + tablePrefix + "showButton").removeClass("selected");
            $(this).addClass("selected");
            document.location.href = getBaseUrl();
        }
    });
    $("#" + tablePrefix + "showAllExpts").click(function()
    {
        if (!$(this).hasClass("selected")) {
            $("." + tablePrefix + "showButton").removeClass("selected");
            $(this).addClass("selected");
            document.location.href = getBaseUrl();
        }
    });
    $("#" + tablePrefix + "showMyExpts").click(function()
    {
        if (!$(this).hasClass("selected")) {
            $("." + tablePrefix + "showButton").removeClass("selected");
            $(this).addClass("selected");
            document.location.href = getBaseUrl();
        }
    });
    $("#" + tablePrefix + "showMyExptsModels").click(function()
    {
        var hideModels = hiddenToggle($(this)),
            hideProtocols = $("#" + tablePrefix + "showMyExptsProtocols").text().substr(0, 4) == 'Show';
        hideDatasets = $("#" + tablePrefix + "showMyExptsDatasets").text().substr(0, 4) == 'Show';
        document.location.href = getBaseUrl() + $.param(hideModeratedParams(hideModels, hideProtocols, hideDatasets));
    });
    $("#" + tablePrefix + "showMyExptsProtocols").click(function()
    {
        var hideProtocols = hiddenToggle($(this)),
            hideModels = $("#" + tablePrefix + "showMyExptsModels").text().substr(0, 4) == 'Show';
        hideDatasets = $("#" + tablePrefix + "showMyExptsDatasets").text().substr(0, 4) == 'Show';
        document.location.href = getBaseUrl() + $.param(hideModeratedParams(hideModels, hideProtocols, hideDatasets));
    });
    $("#" + tablePrefix + "showMyExptsDatasets").click(function()
    {
        var hideDatasets = hiddenToggle($(this)),
            hideModels = $("#" + tablePrefix + "showMyExptsModels").text().substr(0, 4) == 'Show';
        hideProtocols = $("#" + tablePrefix + "showMyExptsProtocols").text().substr(0, 4) == 'Show';
        document.location.href = getBaseUrl() + $.param(hideModeratedParams(hideModels, hideProtocols, hideDatasets));
    });
}

/**
 * Toggle whether a button's text starts 'Hide' or 'Show'.
 * @param $button  the button to check
 * @returns true iff the text previously started 'Hide' (so the state was shown, now hidden)
 */
function hiddenToggle($button)
{
    var oldText = $button.text(),
        hide;
    if (oldText.substr(0, 4) == 'Show') {
        hide = false;
        $button.text('Hide' + oldText.substr(4));
    } else {
        hide = true;
        $button.text('Show' + oldText.substr(4));
    }
    return hide;
}

function switchPage(page, tablePrefix)
{
    for (var i = 0; i < pages.length; i++) {
        if (pages[i] == page) {
            document.getElementById(tablePrefix + pages[i] + "Tab").style.display = "block";
            $("#" + tablePrefix + pages[i] + "chooser").addClass("selected");
        } else {
            document.getElementById(tablePrefix + pages[i] + "Tab").style.display = "none";
            $("#" + tablePrefix + pages[i] + "chooser").removeClass("selected");
        }
    }
}

function registerSwitchPagesListener(btn, page, tablePrefix = '')
{
    btn.addEventListener("click", function()
    {
        switchPage(page, tablePrefix);
    }, true);
}

function initDb(tablePrefix)
{
    if ($("#" + tablePrefix + "matrixdiv").length > 0) {

        experimentsToCompare[tablePrefix] = [];
        linesToCompare[tablePrefix] = {
            row: [],
            col: []
        };
        baseUrls[tablePrefix] = {
            row: "",
            col: ""
        }; // These are filled in if we are viewing a sub-matrix

        switchPage(pages[0], tablePrefix);
        prepareMatrix(tablePrefix);
    }
}

$(document).ready(function()
{
    $("div[id$='matrixdiv']").each(function(i, el)
    {
        prefix = $(el).attr('id').replace('matrixdiv', '');
        comparisonMode = prefix.startsWith("story");  // for experiment selector in story parts use comparisson mode
        initDb(prefix);
    });
})
