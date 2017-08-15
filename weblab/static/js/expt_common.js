/*
 * Routines related to displaying the results of experiments, common to both
 * entity.js and compare.js.
 *
 */

/**
 * Sort the list of results files from this experiment, so similar files are grouped together,
 * with those defined as plot data appearing first.
 * 
 * Note that when comparing experiments this method gets called multiple times (once for each
 * of the compared experiments which has both metadata files) so the sorting has to be cumulative:
 * any one experiment might not list all the possible plots, if it didn't fully complete.
 */
function sortTable (plots)
{
    // What remains to be sorted?
    var to_be_sorted;
    if (filesTable.beenSorted)
    {
        to_be_sorted = new Array ();
        // Add in filesTable.other and filesTable.otherCSV
        var adder = function(key, idx, arr)
        {
            to_be_sorted.push(this[key]);
        }
        Object.keys(filesTable.otherCSV).forEach(adder, filesTable.otherCSV);
        Object.keys(filesTable.other).forEach(adder, filesTable.other);
        filesTable.otherCSV = {};
        filesTable.other = {};
    }
    else
    {
        to_be_sorted = filesTable.all;
    }

    // Split the file list into categories
    for (var i = 0; i < to_be_sorted.length; i++)
    {
        var f = to_be_sorted[i];
        var found = false;
        for (var j = 0; j < plots.length; j++)
            if (f.name == plots[j])
            {
                filesTable.plots[f.name] = f;
                found = true;
                break;
            }
        if (found)
            continue;
        if (f.name.endsWith ("png") || f.name.endsWith ("eps"))
            filesTable.pngeps[f.name] = f;
        else if (f.name == "outputs-default-plots.csv" || f.name == "outputs-contents.csv")
            filesTable.defaults[f.name] = f;
        else if (f.name.endsWith ("csv"))
            filesTable.otherCSV[f.name] = f;
        else if (f.name.endsWith ("txt"))
            filesTable.text[f.name] = f;
        else 
            filesTable.other[f.name] = f;
    }

    // Figure out how many columns the table has (could be 3 or 4, depending on whether comparing!)
    var colCount = $(filesTable.table).find('tr:first th').length;

    // Function to sort each category individually
    var resortPartially = function (arr, css, title, startHidden)
    {
        var cur = keys(arr).sort();
//        console.log("Resorting " + css + " " + cur.length);
        if (cur.length > 0)
        {
            // Create/find the header row for this section
            var header = $("#filesTable-header-" + css).get(0);
            if (filesTable.beenSorted && header !== undefined)
            {
                filesTable.table.removeChild(header);
            }
            else
            {
                header = document.createElement("tr");
                header.id = "filesTable-header-" + css;
                $(header).addClass("filesTable-" + css).addClass("filesTable-header");
                header.innerHTML = "<th colspan='" + colCount + "' class='filesTable-header-shown'>" + title + "</th>";
                // Make a click on the header toggle visibility of the rest of the section
                $(header).click(function() {
                    $(".filesTable-" + css).not(header).toggle("fast");
                    $(header).children().toggleClass("filesTable-header-shown filesTable-header-hidden");
                });
            }
            filesTable.table.appendChild(header);
            // Append the rows for this section, ordered by file name
            for (var i = 0; i < cur.length; i++)
            {
                $(arr[cur[i]].row).removeClass().addClass ("filesTable-" + css);
                filesTable.table.removeChild (arr[cur[i]].row);
                filesTable.table.appendChild (arr[cur[i]].row);
            }
            if (startHidden)
            {
                $(".filesTable-" + css).not(header).hide();
                $(header).children().removeClass("filesTable-header-shown").addClass("filesTable-header-hidden");
            }
            else
            {
                // Explicitly show rows in this section, since some of them may have been hidden by a previous call to sortTable
                $(".filesTable-" + css).not(header).show();
            }
        }
    };

    // Put the categories in order, and sort them
    resortPartially (filesTable.plots, "plots", "Plottable result data", false);
    resortPartially (filesTable.otherCSV, "otherCSV", "Other result data", true);
    resortPartially (filesTable.text, "text", "Experiment information", false);
    resortPartially (filesTable.defaults, "defaults", "Result metadata", false);
    resortPartially (filesTable.pngeps, "pngeps", "Pre-generated figures", true);
    resortPartially (filesTable.other, "other", "Files mainly of use for debugging", true);

    // Remember that we've been called!
    filesTable.beenSorted = true;
}

/**
 * Calculate the maximum distance between three successive values in a series.
 */
function maxDist (val1, val2, val3)
{
    var a = val1 > val2 ?
            (val1 > val3 ? val1 : val3) :
            (val2 > val3 ? val2 : val3); 
    var b = val1 < val2 ?
            (val1 < val3 ? val1 : val3) :
            (val2 < val3 ? val2 : val3);
    return a - b;
}

/**
 * Parse a CSV file with plotting data. Adds the following fields to the file object:
 * - csv: the raw parsed numeric data, an array of row arrays
 * - columns: the transpose of the raw data, an array of column arrays
 * - nonDownsampled: {x,y} data organised by column
 * - downsampled: downsampled {x,y} data, with 'close' points removed
 * 
 * The point data treats the first column as containing x values, and every other column
 * as a separate series of y values.  We thus get arrays of columns, each of which is an
 * array of objects with x and y properties.
 * 
 * The downsampling considers each column separately, and includes a point only if it is
 * at least 1/500th of the range of that column away from either of its neighbours.  The
 * first and last points are always included.
 */
function parseCSVContent (file)
{
    parseCsvRaw(file);
    var csv = file.csv;

    file.columns = [];
    var dropDist = [];
    for (var i = 0; i < csv[0].length; i++)
    {
        var min = Math.pow(2, 32);
        var max = -min;
        file.columns[i] = [];
        for (var j = 0; j < csv.length; j++)
            if (csv[j][i])
            {
                file.columns[i][j] = Number(csv[j][i]);
                if (i > 0)
                {
                    if (max < file.columns[i][j])
                        max = file.columns[i][j];
                    if (min > file.columns[i][j])
                        min = file.columns[i][j];
                }
            }
        dropDist.push ( (max - min) / 500.0 );
        //console.log( "scale for line " + i + ": " + min + ":" + dropDist[dropDist.length-1] + ":" + max);
    }
    file.nonDownsampled = [];
    file.downsampled = [];
    for (var i = 1; i < file.columns.length; i++)
    {
        file.downsampled[i] = [];
        file.nonDownsampled[i] = [];
        file.downsampled[i][0] = {x : file.columns[0][0], y : file.columns[i][0]};
        file.nonDownsampled[i][0] = {x : file.columns[0][0], y : file.columns[i][0]};
        var last_j = file.columns[i].length - 1;
        for (var j = 1; j <= last_j; j++)
        {
            file.nonDownsampled[i].push ({x : file.columns[0][j], y : file.columns[i][j]});
            var last = file.downsampled[i][file.downsampled[i].length - 1]['y'];
            var cur = file.columns[i][j];
            var next = file.columns[i][j + 1];
            if (j == last_j || maxDist (last, cur, next) > dropDist[i] || (cur < last && cur < next) || (cur > last && cur > next))
                file.downsampled[i].push ({x : file.columns[0][j], y : file.columns[i][j]});
        }
        //console.log ("column " + i + " prev: " + file.columns[i].length + " now: " + file.downsampled[i].length);
    }
}

/**
 * Ensures the CSV plotting data in the given file has been parsed, and returns the non-downsampled column point data.
 * @see parseCSVContent
 */
function getCSVColumnsNonDownsampled (file)
{
    if (!file.nonDownsampled)
    {
        parseCSVContent (file);
    }
    return file.nonDownsampled;
}

/**
 * Ensures the CSV plotting data in the given file has been parsed, and returns the downsampled column point data.
 * @see parseCSVContent
 */
function getCSVColumnsDownsampled (file)
{
    if (!file.downsampled)
    {
        parseCSVContent (file);
    }
    return file.downsampled;
}

/**
 * Ensures the CSV plotting data in the given file has been parsed, and returns the column-wise raw data.
 * @see parseCSVContent
 */
function getCSVColumns (file)
{
    if (!file.columns)
    {
        parseCSVContent (file);
    }
    return file.columns;
}

/**
 * Ensures the CSV plotting data in the given file has been parsed, and returns the row-wise raw data.
 * @see parseCSVContent
 */
function getCSV (file)
{
    if (!file.csv)
    {
        parseCSVContent (file);
    }
    return file.csv;
}


/**
 * Extract key data for a file if available.
 *
 * @param file  the file to get key data for
 * @param numTraces  the number of values to expect in a key vector
 */
function getKeyValues(file, numTraces)
{
    var keyVals = [];
    if (file.keyId)
    {
        var keyData = getCSVColumns(file.keyFile);
        if (keyData.length > 0)
            for (var i=0; i<keyData[0].length; i++)
                keyVals.push(keyData[0][i]);
        if (keyVals.length != numTraces)
        	console.log("Ignoring key data of wrong length (key length=" + keyVals.length + "; number of traces=" + numTraces + ")");
    }
    return keyVals;
}


/**
 * Set up a link to allow users to export the raw data behind a plot, in CSV column-oriented format.
 * @param filename  the file name to suggest saving as
 * @param datasets  an array of {name: String, data: [[x1,y1], ...]} objects
 * @param axisLabels  an object {x: String, y: String} giving the labels for the axes, if any
 */
function allowPlotExport(filename, datasets, axisLabels)
{
	$("#exportPlot").off().click(function () {
		// Determine the greatest number of points in a dataset, and hence the number of rows in the CSV
		var numRows = Math.max.apply(null, $.map(datasets, function (dataset, index) { return dataset.data.length; })),
			rows = new Array(numRows+2);
		// Header line
		rows[0] = $.map(datasets, function (dataset, index) { return axisLabels.x + "," + dataset.name; }).join() + "\n";
		// The data
		for (var i=0; i<numRows; i++)
		{
			rows[i+1] = $.map(datasets, function (dataset, index) {
				if (i < dataset.data.length)
					return dataset.data[i].join();
				else
					return ",";
			}).join() + "\n";
		}
		// Footer line
		rows[numRows+1] = "# x axis: " + axisLabels.x + "; y axis: " + axisLabels.y + "\n";
		// Construct file in memory and trigger save dialog
		var blob = new Blob(rows, {type: "text/csv;charset=utf-8", endings: "native"});
		saveAs(blob, filename);
	}).show();
}
