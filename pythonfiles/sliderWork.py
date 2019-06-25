from bokeh.models import HoverTool, DatetimeTickFormatter, CrosshairTool, CustomJS, Slider, NumberFormatter
from bokeh.models import Row, Column
from bokeh.layouts import layout, Spacer, widgetbox
from bokeh.embed import components
from bokeh.plotting import figure, ColumnDataSource
from datetime import datetime
from bokeh.models.widgets import Toggle, CheckboxGroup, DateFormatter, Div, Button
from bokeh.palettes import Viridis256  # Up to 256 different colors available
from random import shuffle
import json
import logging
import base64
import bokeh
import numpy as np
from jinja2 import Template
from bokeh.io import export_png

from pprint import pprint

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

def standard_dev(tf, xs, ys):
    sd = []
    sddate = []
    x = tf
    while x <= len(ys):
        array2consider = ys[x - tf:x]
        standev = array2consider.std()
        sd.append(standev)
        sddate.append(xs[x])
        x += 1
    return sddate, sd


def movingaverage(values, window):
    weigths = np.repeat(1.0, window) / window
    smas = np.convolve(values, weigths, 'valid')
    return smas  # as a numpy array


def bollinger_bands(multiplier, xss, yss, tff):
    bdate = []
    topBand = []
    botBand = []
    midBand = []
    np_xss = np.array(xss)
    np_yss = np.array(yss)

    x = tff

    while x < len(xss):
        curSMA = movingaverage(np_yss[x - tff:x], tff)[-1]

        d, curSD = standard_dev(tff, np_xss, np_yss[0:tff])
        curSD = curSD[-1]

        TB = curSMA + (curSD * multiplier)
        BB = curSMA - (curSD * multiplier)
        D = np_xss[x]

        bdate.append(D)
        topBand.append(TB)
        botBand.append(BB)
        midBand.append(curSMA)
        x += 1

    noData = "NaN"
    if len(xss) > tff:
        for i in range(tff):
            bdate.insert(0, noData)
            topBand.insert(0, noData)
            botBand.insert(0, noData)
            midBand.insert(0, noData)
    else:
        for i in range(len(xss)):
            bdate.insert(0, noData)
            topBand.insert(0, noData)
            botBand.insert(0, noData)
            midBand.insert(0, noData)

    return bdate, topBand, botBand, midBand


def basic_TS_plot(fullDataset):
    # Init values
    ticker = ""
    yLabel = ""
    descLine = ""
    plotX = []
    plotXLabel = []
    plotY = []
    legendList = []

    # BollingerBands
    all_top_bollingers = []
    all_bot_bollingers = []
    all_mid_bollingers = []
    all_bollinger_dates = []

    # Quartiles
    firstQuartiles = []
    medians = []
    thirdQuartiles = []

    # SETUP DATA
    for element in fullDataset:

        try:
            elementX = []
            elementXLabel = []
            elementY = []

            # Extract x and y's from the pairs provided in each element of the dataset
            if element["dataset"]["data"]:
                for e in range(0, len(element["dataset"]["data"])):
                    elementX.append(datetime.strptime(element["dataset"]["data"][e][0], '%Y-%m-%d').date())
                    elementXLabel.append(str(element["dataset"]["data"][e][0]))
                    elementY.append(element["dataset"]["data"][e][1])

            databaseCode = "[" + element["dataset"]["database_code"] + "] "
            name = element["dataset"]["name"]

            if len(elementX) > 0:
                # Reverse the incoming data if it starts with the closest-to-present data. We want it list to start with the oldest data
                if len(elementX) > 1:
                    if elementX[0] > elementX[1]:
                        elementX.reverse()
                        elementY.reverse()
                plotX.append(elementX)
                plotXLabel.append(elementXLabel)
                plotY.append(elementY)

                # Bollinger Band Info prepare
                date_b, top_b, bot_b, mid_b = bollinger_bands(2, elementX, elementY, 20)
                all_top_bollingers.append(top_b)
                all_mid_bollingers.append(mid_b)
                all_bot_bollingers.append(bot_b)
                # all_bollinger_dates.append(date_b)
                all_bollinger_dates.append(elementX)

            if element["dataset"]["data"]:
                if len(name) > 15:
                    legendList.append("Show/Hide: " + name[:30] + "...")
                else:
                    legendList.append(name)

            if element["dataset"]["data"]:
                # Prepare Quartiles
                numpyY = np.array(elementY)
                first_q = np.percentile(numpyY, 25)
                medi = np.percentile(numpyY, 50)
                third_q = np.percentile(numpyY, 75)

                firstQuartiles.append(first_q)
                medians.append(medi)
                thirdQuartiles.append(third_q)
        except Exception as e:
            logger.debug("ERROR: element in fullDataset could not be added")
            logger.debug(element)
            logger.debug(e)

    all_quartiles = [[]] * len(plotX)
    quartiles_names = [["First Quartile", "Median", "Third Quartile"]] * len(plotX)

    for i in range(len(plotX)):
        all_quartiles[i] = [firstQuartiles[i], medians[i], thirdQuartiles[i]]

    # If only one item is available from the fullDataset, the report can be tailored to that time-series only
    if len(fullDataset) == 1:

        titleLong = fullDataset[0]["dataset"]["name"]

        if len(titleLong) > 20:
            titleShort = titleLong[:10] + "..."
        else:
            titleShort = titleLong

        descLong = "Long description placeholder."
        descLine = '<abbr title="' + descLong + '">' + ticker + '</abbr>'
        yLabel = fullDataset[0]["dataset"]["column_names"][1]

    # generic title for multiple data sets
    else:
        titleShort = "Time-series for: " + fullDataset[0]["dataset"]["start_date"] + " to " + fullDataset[0]["dataset"][
            "end_date"]
        descLine = ticker
        yLabel = "Value(s)"  # The table below will be used to show the units. Ideally it should also figure in the legend

    # Prepare column data sources for the graphs. This is also where hover tool and other widgets get their information
    source = []

    # 'color' is created specifically for lasso tool - for the invisible, but selectable circle glyphs
    for i in range(len(plotX)):
        color = ["navy"] * len(plotX[i])
        source.append(ColumnDataSource(data=dict(x=plotX[i], y=plotY[i], color=color,
                                                 topx=all_bollinger_dates[i], topy=all_top_bollingers[i],
                                                 midx=all_bollinger_dates[i], midy=all_mid_bollingers[i],
                                                 botx=all_bollinger_dates[i], boty=all_bot_bollingers[i])))

    PLOT_OPTIONS = dict(plot_width=400, plot_height=170)

    crosshair = CrosshairTool(
        dimensions="height"
    )

    TOOLS = ['pan,wheel_zoom,box_zoom,reset,save,lasso_select'] + [crosshair]

    plot = figure(title=titleShort,
                  x_axis_type="datetime",
                  tools=TOOLS,
                  toolbar_location="above",
                  sizing_mode='scale_width',
                  **PLOT_OPTIONS
                  )

    plot.xaxis.formatter = DatetimeTickFormatter(
        hours=["%d %B %Y"],
        days=["%d %B %Y"],
        months=["%d %B %Y"],
        years=["%d %B %Y"],
    )

    plot.xaxis.axis_label = 'Date(s)'
    plot.yaxis.axis_label = yLabel

    # Magma color palette is: black - purple - orange - tan - light tan
    # Viridis is a color paledtte: dark blue - greenblue - green - yellow
    # More palettes @
    # http://bokeh.pydata.org/en/latest/docs/reference/palettes.html
    colors_list = Viridis256
    shuffle(colors_list)

    # visible lines on graph creation
    plot_line_list = []

    bollinger_band_list = []

    for i in range(len(plotX)):
        # circles created for lasso average finding tool
        plot.circle("x", "y", color='color', size=1, source=source[i], alpha=0)
        # visible graph:
        plot_line_list.append(
            plot.line("x", "y", color=colors_list[i], line_width=4, name='standard', source=source[i]))
        shuffle(colors_list)
        bollinger_band_list.append(
            plot.line("topx", "topy", color=colors_list[i], line_width=1, name='top', source=source[i]))
        bollinger_band_list.append(
            plot.line("midx", "midy", color=colors_list[i], line_width=1, line_dash="dashed", name='mid',
                      source=source[i]))
        bollinger_band_list.append(
            plot.line("botx", "boty", color=colors_list[i], line_width=1, name='bot', source=source[i]))

    # Bollinger bands are initially off
    for i in range(len(bollinger_band_list)):
        bollinger_band_list[i].visible = True

    # A hover tool for each line (standard, top, mid, lower)
    hover = HoverTool(names=['standard'], tooltips=[
        ("Value", "@y{0,0.0000}"),  # FRED REMOVED comma HERE
        ("Date", "@x{%F}")
    ],
                      formatters={"x": "datetime"},
                      mode='vline'
                      )

    hover2 = HoverTool(names=['top'], tooltips=[
        ("Upper Band", "@topy{0,0.0000}"),
        ("Date", "@x{%F}")
    ],
                       formatters={"x": "datetime"},
                       mode='vline'
                       )
    hover3 = HoverTool(names=['mid'], tooltips=[
        ("SMA", "@midy{0,0.0000}"),
        ("Date", "@x{%F}")
    ],
                       formatters={"x": "datetime"},
                       mode='vline'
                       )
    hover4 = HoverTool(names=['bot'], tooltips=[
        ("Lower Band", "@boty{0,0.0000}"),
        ("Date", "@x{%F}")
    ],
                       formatters={"x": "datetime"},
                       mode='vline'
                       )

    plot.add_tools(hover, hover2, hover3, hover4)

    # Set-up the multi-line representation (not using bokeh's multi-line) and the checkboxes
    list_active = []
    dictArgs = {}

    button_titles = []
    for i in range(0, len(plotX)):
        button_titles.append("Graph " + str(i + 1) + ": " + legendList[i])

    # Generate the JS code for checkbox group - show/hide graphs
    dynamicJS = '//console.log(cb_obj.active);'

    for line in range(0, len(plot_line_list)):
        dynamicJS += '\nline' + str(line * 4) + '.visible = false; '
        for i in range(3):
            dynamicJS += '\nline' + str(line * 4 + i + 1) + '.visible = false; '

    dynamicJS += """
    for (i in cb_obj.active)
    {
    //console.log(cb_obj.active[i]);
    if (cb_obj.active[i] == 0)
    {
        line0.visible = true;
        if (bollToggle.active == true)\n"""
    dynamicJS += "{\n"
    for i in range(3):
        dynamicJS += 'line' + str(i + 1) + '.visible = true;\n'
    dynamicJS += '}}'

    for line in range(1, len(plot_line_list)):
        dynamicJS += '\nelse if (cb_obj.active[i] == ' + str(line) + ') {\n'
        dynamicJS += 'line' + str(line * 4) + '.visible = true;\n'
        dynamicJS += 'if (bollToggle.active == true) {\n'
        for i in range(3):
            dynamicJS += 'line' + str(line * 4 + i + 1) + '.visible = true;\n'
        dynamicJS += '\n}}'
    dynamicJS += '\nelse if (cb_obj.active[i] == ' + str(len(plot_line_list)) + ') {\n'
    for t in range(0, len(plot_line_list)):
        dynamicJS += 'if (bollToggle.active == true) {\n'
        for i in range(3):
            dynamicJS += 'line' + str(t * 4 + i + 1) + '.visible = true;\n'
        dynamicJS += '}\n'
    dynamicJS += '\n}'
    dynamicJS += '\n}'

    logger.debug("DEBUG: DynamicJS")
    logger.debug(dynamicJS)

    # list_active means the buttons initially ON at page load
    for line in range(0, len(plot_line_list)):
        list_active.append(line)
        key = "line" + str(line * 4)
        dictArgs.update({key: plot_line_list[line]})
        for i in range(3):
            key = "line" + str(line * 4 + i + 1)
            dictArgs.update({key: bollinger_band_list[line * 3 + i]})

    bollButton = Toggle(label='Bollinger On/Off', button_type='success')

    key = "bollToggle"
    dictArgs.update({key: bollButton})

    checkboxColor = ''
    if len(plotY) > 9:
        checkboxColor += '#E4E4E4;'
    else:
        checkboxColor += 'white;'

    checkbox = CheckboxGroup(labels=button_titles, active=list_active, width=450, height=210)

    checkbox.callback = CustomJS(args=dictArgs, code=dynamicJS)
    # checkbox is 210 pixels high(max), with a vertical scrollbar and grey background color
    checkbox.css_classes = ["checkbox-scrollbar"]

    key = "checkbox"
    dictArgs.update({key: checkbox})

    selectAllJS = ''
    selectAllJS += "checkbox.active = ["
    for i in range(len(plotY)):
        if i != len(plotY) - 1:
            selectAllJS += str(i) + ', '
        else:
            selectAllJS += str(i)

    selectAllJS += "];\n"

    for i in range(len(plotY)):
        selectAllJS += 'line' + str(i * 4) + '.visible = true;\n'

    selectAllJS += 'if (bollToggle.active == true) {\n'

    for i in range(len(plotY)):
        for t in range(3):
            selectAllJS += 'line' + str(i * 4 + t + 1) + '.visible = true;\n'

    selectAllJS += '}'

    selectAllCallback = CustomJS(args=dictArgs, code=selectAllJS)
    selectAllButton = Button(label='Select All', button_type='warning', callback=selectAllCallback)

    deselectAllJS = "checkbox.active = [];\n"

    for i in range(len(plotY) * 4):
        deselectAllJS += 'line' + str(i) + '.visible = false;\n'

    deselectAllCallback = CustomJS(args=dictArgs, code=deselectAllJS)
    deselectAllButton = Button(label='Deselect All', button_type='warning', callback=deselectAllCallback)

    plotScript, plotDiv = components(plot)

    # printPlotJS = """
    #         var div = plot;
    #         console.log(plot);
    #         var data=divID.innerHTML;
    #         var myWindow = window.open('', 'my div', 'height=400,width=600');
    #         myWindow.document.write(div);
    #         myWindow.document.close(); // necessary for IE >= 10
    #
    #         myWindow.onload=function(){ // necessary if the div contain images
    #
    #             myWindow.focus(); // necessary for IE >= 10
    #             myWindow.print();
    #             myWindow.close();
    #         };
    # """


    # logger.debug("DEBUG: DynamicJS")
    # logger.debug(dynamicJS)

    sliderJS = """
        var window = cb_obj.value
        var sources = ["""

    for i in range(len(source)):
        if i != len(source) - 1:
            sliderJS += 'source' + str(i) + ', '
        else:
            sliderJS += 'source' + str(i)

    sliderJS += '];'

    sliderJS += """

        for (var i = 0, len=sources.length; i < len; i++) {
            var data = sources[i].data;
            var y = data['y']
            topy = data['topy']
            midy = data['midy']
            boty = data['boty']


            function StandardDeviation(numbersArr) {
                //--CALCULATE AVERAGE--
                var total = 0;
                for(var key in numbersArr)
                   total += numbersArr[key];
                var meanVal = total / numbersArr.length;
                //--CALCULATE AVERAGE--

                //--CALCULATE STANDARD DEVIATION--
                var SDprep = 0;
                for(var key in numbersArr)
                   SDprep += Math.pow((parseFloat(numbersArr[key]) - meanVal),2);
                var SDresult = Math.sqrt(SDprep/numbersArr.length);
                //--CALCULATE STANDARD DEVIATION--
                return SDresult;
            }

            function standardDev(window, y) {
                var sd = [];
                var x = window;
                while (x <= y.length) {
                    var a2c = y.slice(x - window, x);
                    var standev = StandardDeviation(a2c);
                    sd.push(standev);
                    x += 1;
                }
                return sd;
            }

            //moving average calc
            function movingAvg(array, count, qualifier){

                // calculate average for subarray
                var avg = function(array, qualifier){

                    var sum = 0, count = 0, val;
                    for (var i in array){
                        val = array[i];
                        if (!qualifier || qualifier(val)){
                            sum += val;
                            count++;
                        }
                    }

                    return sum / count;
                };

                var result = [], val;

                // pad beginning of result with null values
                for (var i=0; i < count-1; i++)
                    result.push(NaN);

                // calculate average for each subarray and add to result
                for (var i=0, len=array.length - count; i <= len; i++){

                    val = avg(array.slice(i, i + count), qualifier);
                    if (isNaN(val))
                        result.push(NaN);
                    else
                        result.push(val);
                }

                return result;
            }
            //end moving avg


            var top_band = [];
            var mid_band = [];
            var bot_band = [];

            var x = window;
            while (x < y.length) {
                var sma_array = movingAvg(y.slice(x - window, x), window);
                var sma_last = sma_array[sma_array.length - 1];

                var curSD = standardDev(window, y.slice(0, window));
                var curSD_last = curSD[curSD.length - 1];

                var tb = sma_last + curSD_last * 2;
                var bb = sma_last - curSD_last * 2;

                top_band.push(tb);
                mid_band.push(sma_last);
                bot_band.push(bb);
                x+=1;
                }

            if (top_band < topy) {
                shift_amt = topy.length - top_band.length;
                for (var q=0; q < shift_amt; q++) {
                    top_band.unshift(NaN);
                    mid_band.unshift(NaN);
                    bot_band.unshift(NaN);
                }
            }


            //for (var t=0; t < y.length; t++) {
            //   if (isNaN(top_band[0]) == true) {
            //        topy[t] = top_band[t + 1];
            //        boty[t] = bot_band[t + 1];
            //        midy[t] = mid_band[t + 1];
            //    }
            //    else {
            //        topy[t] = top_band[t];
            //        boty[t] = bot_band[t];
            //        midy[t] = mid_band[t];
            //    }
            //}
            for (var t=0; t < y.length; t++) {
                    topy[t] = top_band[t];
                    boty[t] = bot_band[t];
                    midy[t] = mid_band[t];
            }
            console.log(sources[i]);
            sources[i].change.emit();
        }
            """

    sourceArgs = {}
    for i in range(0, len(plot_line_list)):
        key = "source" + str(i)
        sourceArgs.update({key: source[i]})

    print(sourceArgs)

    SMAcallback = CustomJS(args=sourceArgs, code=sliderJS)

    SMAwindow_slider = Slider(start=1, end=100, value=20, step=1,
                              title="SMA Window(period)", callback=SMAcallback)

    # for space between checkboxes and buttons
    spacer = Spacer(height=100, width=50)

    # for temporary space when slider is invisible
    no_slider = Spacer(height=75, width=100)
    SMAwindow_slider.height = 65

    bollColumn = Column()
    bollColumn.width = 175
    bollColumn.children = [bollButton, no_slider, selectAllButton, deselectAllButton]

    bollRow = Row(checkbox, spacer, bollColumn)

    # --------------------------------------------------------------
    # Allow bollinger button to turn on/off the slider

    # dynamicJSboll = '\ncolumn.children = [no_slider];'
    #
    # dynamicJSboll += """
    #                 if (cb_obj.active == true)
    #                 {
    #                     column.children = [boll_button, slider, select_all, deselect_all]
    #                 }
    #                 else if (cb_obj.active == false)
    #                 {
    #                     column.children = [boll_button, no_slider, select_all, deselect_all];
    #                 }"""

    key = "column"
    dictArgs.update({key: bollColumn})
    key = "boll_button"
    dictArgs.update({key: bollButton})
    key = "slider"
    dictArgs.update({key: SMAwindow_slider})
    key = "no_slider"
    dictArgs.update({key: no_slider})
    key = "select_all"
    dictArgs.update({key: selectAllButton})
    key = "deselect_all"
    dictArgs.update({key: deselectAllButton})

    # javascript for bollinger toggle button
    dynamicJSboll = """
    //console.log(cb_obj.active);
    if (cb_obj.active == true) {\n"""

    # slider is made visible
    dynamicJSboll += 'column.children = [boll_button, slider, select_all, deselect_all];\n'

    for t in range(0, len(plot_line_list)):
        dynamicJSboll += 'if (line' + str(t * 4) + '.visible == true) {\n'
        for i in range(3):
            dynamicJSboll += 'line' + str(t * 4 + i + 1) + '.visible = true;\n'
        dynamicJSboll += "}\n"

    dynamicJSboll += "}\n"
    dynamicJSboll += "else if (cb_obj.active == false) {\n"

    # slider is turned invisible
    dynamicJSboll += 'column.children = [boll_button, no_slider, select_all, deselect_all];\n'

    for t in range(0, len(plot_line_list)):
        for i in range(3):
            dynamicJSboll += 'line' + str(t * 4 + i + 1) + '.visible = false;\n'
    dynamicJSboll += "}\n"

    bollButton.callback = CustomJS(args=dictArgs, code=dynamicJSboll)

    # --------------------------------------------------------------

    '''
    # display data tables only if there are 10 or less data sets
    if len(plotY) < 11:
        doc_layout = layout([
            [Column((plot), sizing_mode='scale_width')],
            [bollRow],
            [Row(children=data_table, sizing_mode='scale_width')],
        ], sizing_mode='scale_width')
    '''
    doc_layout = layout([
        [Column(plot)],
        [bollRow]],
        sizing_mode='scale_width')

    plots = [plot, [bollRow]]

    scripts, div = components(plot)

    cssCode = """
             <style type="text/css">

               svg {
                   font-family: 'Helvetica Neue', Helvetica;
               }

               .line {
                   fill: none;
                   stroke: #000;
                   stroke-width: 2px;
               }

               body {
                   height: 100%;
                   overflow: hidden;
                   margin: 0px;
                   display: flex;
                   box-sizing: border-box;
                   }

               h1 {
                   font-family: 'Helvetica Neue', Helvetica;
                   color: #ffc800;
                   text-align: center;
               }

               h2 {
                   font-family: 'Helvetica Neue', Helvetica;
                   color: grey;
                   text-align: center;
               }
               p {
                   font-family: 'Helvetica Neue', Helvetica;
                   font-size: 14px;
                   color: dark-grey;
                   text-align: justify;
               }
               metric {
                   font-family: 'Helvetica Neue', Helvetica;
                   font-size: 20px;
                   color: dark-grey;
                   text-decoration: underline;
                   text-align: center;
               }
               cop {
                   font-family: 'Helvetica Neue', Helvetica;
                   font-size: 10px;
                   color: black;
                   text-align: center;
               }

#main {
    transition: margin-left .5s;
    padding: 16px;
    margin-top: 70px;
    flex-grow: 1;
    display: flex;
    overflow-y: auto;  /*adds scroll to this container*/
    max-width: 100%;
}

.navbar {
  overflow: hidden;
  background-color: #ffc800;
  position: fixed;
  top: 0;
  width: 100%;
}

.navbar a {
  float: left;
  display: block;
  color: black;
  text-align: center;
  padding: 14px 16px;
  text-decoration: none;
  font-size: 15px;
}

.sidenav {
    max-height: 82%;
    width: 0;
    position: fixed;
    z-index: 1;
    top: 0;
    left: 0;
    background-color: #DCDCDC;
    overflow-x: hidden;
    overflow-y: auto;
    transition: 0.5s;
    padding-top: 30px;
    margin-top: 68px;
}

.sidenav a {
    padding: 8px 8px 8px 32px;
    text-decoration: none;
    font-size: 25px;
    color: white;
    display: block;
    transition: 0.3s;
}

.sidenav a:hover, .offcanvas a:focus{
    color: #ffc800;
}

.sidenav .closebtn {
    color: black;
    position: absolute;
    top: 0;
    right: 25px;
    color: black;
    font-size: 36px;
    margin-left: 50px;
}

                .table-custom {
                   border:1px;
                   border-style: solid;
                   border-color:#ffc800;
                   padding: 3em;
                   border-radius: 6px;
                   text-align:center;
                   margin: auto;
                   max-width: 100%;
                   max-height: 100%;
                   display: block;
               }
               .checkbox-scrollbar {
                   overflow: auto;
                   background-color: """ + str(checkboxColor) + """
               }

               @media screen and (max-height: 450px) {
  .sidenav {padding-top: 15px;}
  .sidenav a {font-size: 18px;}

           </style>
           """

    metrics_shown = ""
    reportId = fullDataset[0]["reportId"]
    counter = 1

    for element in fullDataset:
        if counter == 1:
            metrics_shown += "<b>Graph " + str(counter) + "</b><br>" + element["dataset"]["name"] + "<br>"
        else:
            metrics_shown += "<b><br>Graph " + str(counter) + "</b><br>" + element["dataset"]["name"] + "<br>"
        counter += 1

    redirect_head_script = """
        <script type="text/javascript">
          <!--
          if (screen.width <= 1200) {"""
    redirect_head_script += 'window.location = "https://s3.amazonaws.com/reports.tools.neonrisk.com/' + reportId + '/mobile_bokeh_report.html";'
    redirect_head_script += """}
          //-->
        </script>
        """

    toolbar_scripts = """
        <script>
    window.onload = function(){
          var pr = document.getElementById('print');
          pr.onclick = printReport;

          function printReport() {

            window.print();

          return false;
            }};

        </script>
        <script>
    window.onload = function(){
          var el = document.getElementById('email');
          el.onclick = createEmail;

          function createEmail() {

            var subject = "See the enclosed report"
            var link = "http://www.neonrisk.com"
            var body = "Please click here to access the report: " + link


            window.open('mailto:?subject=' + subject + '&body=' + body);

          return false;
            }};

        </script>
        <script>
    window.onload = function(){
          var sa = document.getElementById('saveAs');
          sa.onclick = saveAs;

          function saveAs() {

            alert("Please use the SaveAs function of your browser to save the document locally. Note however, that viewing the document always requires a connection.")

          return false;
            }};

        </script>
      <script>
        jQuery(function($) {
              $('#bookmark-this').click(function(e) {
                var bookmarkURL = window.location.href;
                var bookmarkTitle = document.title;

                if ('addToHomescreen' in window && addToHomescreen.isCompatible) {
                  // Mobile browsers
                  addToHomescreen({ autostart: false, startDelay: 0 }).show(true);
                } else if (window.sidebar && window.sidebar.addPanel) {
                  // Firefox <=22
                  window.sidebar.addPanel(bookmarkTitle, bookmarkURL, '');
                } else if ((window.sidebar && /Firefox/i.test(navigator.userAgent)) || (window.opera && window.print)) {
                  // Firefox 23+ and Opera <=14
                  $(this).attr({
                    href: bookmarkURL,
                    title: bookmarkTitle,
                    rel: 'sidebar'
                  }).off(e);
                  return true;
                } else if (window.external && ('AddFavorite' in window.external)) {
                  // IE Favorites
                  window.external.AddFavorite(bookmarkURL, bookmarkTitle);
                } else {
                  // Other browsers (mainly WebKit & Blink - Safari, Chrome, Opera 15+)
                  alert('Press ' + (/Mac/i.test(navigator.userAgent) ? 'Cmd' : 'Ctrl') + '+D to bookmark this page.');
                }

                return false;
              });
            });
        </script>
        """

    infoCol = """
               </head>

              <body>
                    <div class="navbar">
                    <a style="font-size:30px;cursor:pointer" onclick="openNav()">&#9776;</a>
          <a id="bookmark-this" href="#"><img src="https://s3.amazonaws.com/www.neonrisk.com/icons/bookmark.png" alt="Bookmark" width=30 height=30></a>
          <a href="#" title="Save this report as .pdf" id="saveAs">
          <img src="https://s3.amazonaws.com/www.neonrisk.com/icons/save.png" alt="Save this report as pdf" width=30 height=30></a>
          <a href="#" title="Print this report" id="print">
          <img src="https://s3.amazonaws.com/www.neonrisk.com/icons/print.png" alt="Print" width=30 height=30></a>"""

    linkToReport = 'https://s3.amazonaws.com/reports.tools.neonrisk.com/' + reportId + '/bokeh_report.html'

    infoCol += '<a href="mailto:?subject=Please%20see%20the%20enclosed%20report&body=Link%20to%20the%20report' + linkToReport + '">'

    infoCol += """<img src="https://s3.amazonaws.com/www.neonrisk.com/icons/email.png" alt="Email a link" width=30 height=30></a>

                    <a href="http://www.neonrisk.com"><img src="https://s3.amazonaws.com/www.neonrisk.com/icons/help.png" alt="Open Online Help" width=30 height=30></a>
                    <a href="https://www.linkedin.com/company/neon-risk"><img src="https://s3.amazonaws.com/www.neonrisk.com/icons/linkedin.png" alt="Find us on LinkedIn" width=30 height=30></a>
                    <a href="https://twitter.com/NeonRisk"><img src="https://s3.amazonaws.com/www.neonrisk.com/icons/twitter.png" alt="Find us on Twitter" width=30 height=30></a>
          </div>

                <div id="mySidenav" class="sidenav">
                       <a href="javascript:void(0)" class="closebtn" onclick="closeNav()">&times;</a>
                       <p><img src="http://www.neonrisk.com/uploads/6/9/5/2/69527361/hi-res-fpe-phat-flat-x4.png" alt="logo" align="left"></p>
                       <metric>Metrics shown</metric>"""

    infoCol += '<p>' + metrics_shown + '</p><br>'
    infoCol += '<p>Report # ' + reportId + '</p>'
    infoCol += """<p>Thank you for using Neon Risk Tools.
                       For support, please contact <a href="mailto:info@neonrisk.com">info@neonrisk.com</a></p>
                       <cop>copyright Neon Risk, Inc. 2017</cop>
                </div>
                <div id="main">
               """

    closeTableHTML = """
           </div>
                      <script>
function openNav() {
    document.getElementById("mySidenav").style.width = "250px";
    document.getElementById("main").style.marginLeft = "250px";
    document.getElementById("main").style.maxWidth = "87%";
}

function closeNav() {
    document.getElementById("mySidenav").style.width = "0";
    document.getElementById("main").style.marginLeft= "0";
    document.getElementById("main").style.maxWidth = "100%";
}
</script>
           </body>
           </html>
           """

    bokehCode = '<link href="https://cdnjs.cloudflare.com/ajax/libs/bokeh/1.0.2/bokeh.min.css" rel="stylesheet" type="text/css">'
    bokehCode += '<link href="https://cdnjs.cloudflare.com/ajax/libs/bokeh/1.0.2/bokeh-widgets.min.css" rel="stylesheet" type="text/css">'
    bokehCode += '<script src="https://cdnjs.cloudflare.com/ajax/libs/bokeh/1.0.2/bokeh.min.js"></script>'
    bokehCode += '<script src="https://cdnjs.cloudflare.com/ajax/libs/bokeh/1.0.2/bokeh-widgets.min.js"></script>'

    # -- NOW generate page

    reportBodyDataHTML_bokeh = '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'
    reportBodyDataHTML_bokeh += '<html xmlns="http://www.w3.org/1999/xhtml" style="height:100%;width:100%;font-size:100%">'
    reportBodyDataHTML_bokeh += '<head><meta content="text/html; charset=US-ASCII" http-equiv="Content-Type">'

    reportBodyDataHTML_bokeh += cssCode

    reportBodyDataHTML_bokeh += redirect_head_script + bokehCode + scripts + toolbar_scripts

    reportBodyDataHTML_bokeh += infoCol

    reportBodyDataHTML_bokeh += div

    reportBodyDataHTML_bokeh += closeTableHTML

    html_file = open("testing.html", "w")
    html_file.write(reportBodyDataHTML_bokeh)
    html_file.close()
    print(reportBodyDataHTML_bokeh)
    # reportBodyDataHTMLb64us_bokeh = base64.urlsafe_b64encode(reportBodyDataHTML_bokeh)
    #
    # return reportBodyDataHTMLb64us_bokeh

'''
json_file = '8J3RY7AIXFNM_MW0_2017719_172.json'
data = json.loads(json_file).decode('utf-8')
print(data['dataset'])
#basic_TS_plot(data)
'''


'''
    # Lasso Tool for average:
    # Compute y value average of [lasso tool-selected points] and show as horizontal line
    minY = min(min(plotY))
    maxY = max(max(plotY))
    minX = min(min(plotX))
    maxX = max(max(plotX))
    middleY = float(maxY + minY) / 2.0
    s2 = ColumnDataSource(data=dict(ym=[middleY, middleY]))
    plot.line(x=[minX, maxX], y='ym', color="#ffc800", line_width=5, alpha=0.6, source=s2)

    for i in range(len(source)):
        source[i].callback = CustomJS(args=dict(s2=s2), code="""
                var inds = cb_obj.get('selected')['1d'].indices;
                var d = cb_obj.get('data');
                var ym = 0

                if (inds.length == 0) { return; }

                for (i = 0; i < d['color'].length; i++) {
                    d['color'][i] = "navy"
                }
                for (i = 0; i < inds.length; i++) {
                    d['color'][inds[i]] = "firebrick"
                    ym += d['y'][inds[i]]
                }

                ym /= inds.length
                s2.get('data')['ym'] = [ym, ym]

                cb_obj.trigger('change');
                s2.trigger('change');
            """)
            
            # Data table creation - standard and quartile
    data_table = []

    def create_data_table(i):
        columns = [
            bokeh.models.TableColumn(field="x", title="Date", formatter=DateFormatter(), width=125),
            bokeh.models.TableColumn(field="y", title="Value", formatter=NumberFormatter(format='0,0.0000'), width=150)]
        datatable = bokeh.models.DataTable(source=source[i], columns=columns, width=275, height=250,
                                           editable=True, row_headers=False)
        return datatable

    def create_quartile_data_table(x, y):
        quartile_table_source = ColumnDataSource(data=dict())
        quartile_table_source.data = {'name': y, 'value': x}
        quartile_columns = [
            bokeh.models.TableColumn(field="name", title="Quartile", width=125),
            bokeh.models.TableColumn(field="value", title="Value", formatter=NumberFormatter(format='0,0.0000'),
                                     width=150)]
        quartiledatatable = bokeh.models.DataTable(source=quartile_table_source, columns=quartile_columns,
                                                   width=275, height=120, row_headers=False)
        return quartiledatatable

    # 'data_table' holds the title div, and both data tables (standard + quartile)
    for i in range(len(plotX)):
        data_table.append(Column(Div(
            text='<p style="border:0px; border-style:solid; border-color:#ffc800; padding: 10px; margin: 2px 2px 2px; border-radius: 5px; text-align:center;">Graph ' + str(
                i + 1) + '</p>'),
            (create_data_table(i)),
            (create_quartile_data_table(all_quartiles[i], quartiles_names[i])), width=285, height=450))
        # data_table[i].css_classes = ['table-custom']
    '''