# Python 3
#
# Natalie Popescu (Adapted from Ziyang Xu)
# Jan 22, 2021
#
# Present results in HTML

import argparse
import os
import json
import numpy as np
import dash
from dash import dcc
from dash import html
import plotly
import plotly.graph_objects as go
import math
from subprocess import call

# some setting for plot
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
app.config.suppress_callback_exceptions = True

data = dict()

graph_styles = {
    2: {
        "bar_name": "Speedup",
        "bar_color": "#14D085" #58D68D"
    }
}

# geometric mean helper
def geomean_overflow(iterable):
    locarr = []
    for i in iterable:
        if i == 0:
            locarr.append(10**-100)
        else:
            locarr.append(i)
    # convert all elements to positive numbers
    a = np.log(locarr)
    return np.exp(a.sum() / len(a))

# helper for checking if a datafile has no data
def is_empty_datafile(filepath):
    handle = open(filepath, 'r')
    for line in handle: 
        if line[:1] == '#':
            continue
        else:
            return False
    return True

class ResultProvider:

    # complete object has the following fields: 
    # - root
    # - datafile
    # - options (for dropdown menu)
    # - data (dictionary with all crate/benchmark/perf info)
    # - better
    # - worse
    # - neither
    # - better_ (outliers removed)
    # - worse_ (outliers removed)

    def __init__(self, root):
        self.root = root
        self.datafile = "crunched.data"

        # populate list of crates
        loc_data = dict()
        for name in os.listdir(self.root):
            if os.path.isdir(os.path.join(self.root, name)):            
                loc_data[name] = None

        # sort for the purpose of displaying later
        global data
        for crate in sorted(loc_data): 
            data[crate] = None

        # populate options array for dropdown menu
        self.options = []
        for crate in list(data.keys()):
            self.options.append({'label': crate, 'value': crate})

    def get_speedups(self):
        # clearly categorized benchmark results
        self.better = dict()
        self.worse = dict()
        self.neither = dict()
        self.better_ = dict()
        self.worse_ = dict()
        global data
        for c in list(data.keys()):
            filepath = os.path.join(self.root, c, self.datafile)
            if not os.path.exists(filepath) or is_empty_datafile(filepath):
                continue
            # open data file for reading
            handle = open(filepath)
            bmarks = dict()

            for line in handle: 
                if line[:1] == '#':
                    continue
                cols = line.split()
                # <crate_name>::<benchmark_name>
                name = c + "::" + cols[0]

                if not len(cols) == 5: 
                    exit("file at <" + filepath + "> is improperly formatted; "\
                    "expected 5 columns but got " + len(cols))

                unmod_time = cols[1]
                unmod_error = cols[2]
                regex_time = cols[3]
                regex_error = cols[4]

                # get speedup
                if math.isclose(float(unmod_time), float(regex_time), rel_tol=1e-6): 
                    speedup = 1
                elif math.isclose(float(regex_time), float(0), rel_tol=1e-6):
                    speedup = -1 # FIXME how does this show up?
                else: 
                    speedup = float(regex_time) / float(unmod_time)

                bmarks[cols[0]] = speedup

                # categorize speedup: better, worse, neither
                if speedup < 0.97: 
                    self.worse[name] = speedup
                    # exlcude outliers
                    if speedup > 0.4:
                        self.worse_[name] = speedup
                elif speedup > 1.03: 
                    self.better[name] = speedup
                    # exclude outliers
                    if speedup < 1.6:
                        self.better_[name] = speedup
                else:
                    self.neither[name] = speedup

            # populate data dictionary w bmarks
            data[c] = bmarks

def make_graph(d, title):
    trace = {'x': list(d.keys()), 'y': list(d.values()), 'type': 'bar', 
            'name': graph_styles.get(2).get('bar_name'), 
            'marker_color': graph_styles.get(2).get('bar_color')}
    fig = go.Figure({
        'data': trace,
        'layout': {
            'title': title,
            'xaxis': {
                'linecolor': 'black',
                'showline': True, 
                'linewidth': 2,
                'mirror': 'all',
                'nticks': 10,
                'showticklabels': True,
                'title': {'text': 'Benchmarks'},
            },
            'yaxis': {
                'showline': True, 
                'linewidth': 2,
                'ticks': 'outside',
                'mirror': 'all',
                'linecolor': 'black',
                'gridcolor': 'rgb(200,200,200)', 
                'nticks': 20,
                'title': {'text': 'Speedup'},
            },
            'font': {'family': 'Helvetica', 'color': 'black', 'size': 16},
            'plot_bgcolor': 'white',
            'autosize': False,
            'width': 2000, 
            'height': 700}
        })

    # add horizontal lines @ 1
    fig.add_shape(type="line", 
        xref="paper",
        yref="y",
        x0=0,
        x1=1,
        y0=1, 
        y1=1,
        line=dict(color="#D00D56"), #D81B60"),
    )

    return fig

def get_overview_layout(rp):
    # for counting + average calc
    all_bmarks = {**rp.better, **rp.worse, **rp.neither}
    trimmed_bmarks = {**rp.better_, **rp.worse_, **rp.neither}
    # for maximum/potential speedup calc
    mock_all = list(rp.better.values()) + [1] * len(rp.worse) + list(rp.neither.values())
    mock_trimmed = list(rp.better_.values()) + [1] * len(rp.worse_) + list(rp.neither.values())

    trace = go.Histogram(x=list(all_bmarks.values()), nbinsx=100, autobinx=False, 
            marker=dict(color='#14D085'))
    fig_hist = go.Figure({
        'data': trace,
        'layout': {
            'title': 'Histogram of all speedups',
            'xaxis': {
                'linecolor': 'black',
                'ticks': 'outside',
                'mirror': 'all',
                'showline': True, 
                'nticks': 44,
                'title': {'text': 'Speedup'},
            },
            'yaxis': {
                'linecolor': 'black',
                'ticks': 'outside',
                'mirror': 'all',
                'showline': True, 
                'gridcolor':'rgb(200,200,200)', 
                'nticks': 14,
                'title': {'text': 'Number of Benchmarks'},
            },
            'font': {'family': 'Helvetica', 'color': 'black', 'size': 16},
            'plot_bgcolor': 'white',
            'autosize': False,
            'bargap': 0.2,
            'width': 2000, 
            'height': 700}
        })
    # add vertical line @ 1
    fig_hist.add_shape(type="line", 
        xref="x",
        yref="paper",
        x0=1, 
        x1=1, 
        y0=0,
        y1=1,
        line=dict(color="#D00D56"), #D81B60"),
        #line=dict(color="#D0620D"), #D00D56"), #D81B60"),
    )

    fig_all = make_graph(all_bmarks, 'Bar chart of all benchmarks')
    fig_better = make_graph(rp.better, 'Bar chart of improved benchmarks')
    fig_worse = make_graph(rp.worse, 'Bar chart of worsened benchmarks')
    fig_neither = make_graph(rp.neither, 'Bar chart of everything else')

    layout = html.Div([
        # to calculate: 
        # - overall average speedup
        #   - with and without outliers
        # - max potential speedup
        #   - with and without outliers
        # - average speedup within selected category
        #   - with and without outliers
        # to visualize: 
        # - histogram
        # - bar chart per category
        html.Br(),
        html.H3('All benchmarks (histogram)'),
        html.H5('Total number of benchmarks: {}'.format(len(all_bmarks))),
        html.H5('Total number of benchmarks (- outliers): {}'.format(len(trimmed_bmarks))),
        html.H5('Average speedup across all benchmarks: {}'.format(geomean_overflow(list(all_bmarks.values())))),
        html.H5('Average speedup across all benchmarks (- outliers): {}'.format(geomean_overflow(list(trimmed_bmarks.values())))),
        html.H5('Potential speedup across all benchmarks: {}'.format(geomean_overflow(mock_all))),
        html.H5('Potential speedup across all benchmarks (- outliers): {}'.format(geomean_overflow(mock_trimmed))),
        html.Br(),
        dcc.Graph(
            id='histogram',
            figure=fig_hist
        ),
        html.Br(),

        html.H3('All benchmarks (bar chart: see above for stats)'),
        html.Br(),
        dcc.Graph(
            id='all_graph',
            figure=fig_all
        ),
        html.Br(),

        html.H3('Benchmarks where removing bounds checks IMPROVES performance'),
        html.H5('Total number of benchmarks in this category: {} (or {}%)'.format(len(rp.better), float(100*len(rp.better)/len(all_bmarks)))),
        html.H5('Total number of benchmarks in this category (- outliers): {} (or {}%)'.format(len(rp.better_), float(100*len(rp.better_)/len(trimmed_bmarks)))),
        html.H5('Average speedup across benchmarks in this category: {}'.format(geomean_overflow(list(rp.better.values())))),
        html.H5('Average speedup across benchmarks in this category (- outliers): {}'.format(geomean_overflow(list(rp.better_.values())))),
        html.Br(),
        dcc.Graph(
            id='better_graph',
            figure=fig_better
        ),
        html.Br(),

        html.H3('Benchmarks where removing bounds checks HURTS performance'),
        html.H5('Total number of benchmarks in this category: {} (or {}%)'.format(len(rp.worse), float(100*len(rp.worse)/len(all_bmarks)))),
        html.H5('Total number of benchmarks in this category (- outliers): {} (or {}%)'.format(len(rp.worse_), float(100*len(rp.worse_)/len(trimmed_bmarks)))),
        html.H5('Average speedup across benchmarks in this category: {}'.format(geomean_overflow(list(rp.worse.values())))),
        html.H5('Average speedup across benchmarks in this category (- outliers): {}'.format(geomean_overflow(list(rp.worse_.values())))),
        html.Br(),
        dcc.Graph(
            id='worse_graph',
            figure=fig_worse
        ),
        html.Br(),

        html.H3('Benchmarks where removing bounds checks trivially affects performance'),
        html.H5('Total number of benchmarks in this category: {} (or {}%)'.format(len(rp.neither), float(100*len(rp.neither)/len(all_bmarks)))),
        html.H5('Average speedup across benchmarks in this category: {}'.format(geomean_overflow(list(rp.neither.values())))),
        html.Br(),
        dcc.Graph(
            id='neither_graph',
            figure=fig_neither
        ),
        html.Br(),
    ])

    return layout

def gen_figure1(root):
    app._result_provider = ResultProvider(root)
    app._result_provider.get_speedups()
    rp = app._result_provider

    # for counting + average calc
    all_bmarks = {**rp.better, **rp.worse, **rp.neither}
    trimmed_bmarks = {**rp.better_, **rp.worse_, **rp.neither}
    # for maximum/potential speedup calc
    mock_all = list(rp.better.values()) + [1] * len(rp.worse) + list(rp.neither.values())
    mock_trimmed = list(rp.better_.values()) + [1] * len(rp.worse_) + list(rp.neither.values())

    trace = go.Histogram(x=list(all_bmarks.values()), nbinsx=100, autobinx=False, 
            marker=dict(color='#14D085'))
    fig_hist = go.Figure({
        'data': trace,
        'layout': {
            'title': 'Histogram of all speedups',
            'xaxis': {
                'linecolor': 'black',
                'ticks': 'outside',
                'mirror': 'all',
                'showline': True, 
                'nticks': 44,
                'title': {'text': 'Speedup'},
            },
            'yaxis': {
                'linecolor': 'black',
                'ticks': 'outside',
                'mirror': 'all',
                'showline': True, 
                'gridcolor':'rgb(200,200,200)', 
                'nticks': 14,
                'title': {'text': 'Number of Benchmarks'},
            },
            'font': {'family': 'Helvetica', 'color': 'black', 'size': 16},
            'plot_bgcolor': 'white',
            'autosize': False,
            'bargap': 0.2,
            'width': 2000, 
            'height': 700}
        })
    # add vertical line @ 1
    fig_hist.add_shape(type="line", 
        xref="x",
        yref="paper",
        x0=1, 
        x1=1, 
        y0=0,
        y1=1,
        line=dict(color="#D00D56"), #D81B60"),
        #line=dict(color="#D0620D"), #D00D56"), #D81B60"),
    )
    call(['orca', 'graph', 
        '-o', 'figure1_histogram',
        '-f', 'pdf', 
        '--width', '1500', 
        '--height', '600',
        json.dumps(fig_hist, cls=plotly.utils.PlotlyJSONEncoder)])

    fig_all = make_graph(all_bmarks, 'Bar chart of all benchmarks')
    call(['orca', 'graph', 
        '-o', 'figure1_all',
        '-f', 'pdf', 
        '--width', '1500', 
        '--height', '600',
        json.dumps(fig_all, cls=plotly.utils.PlotlyJSONEncoder)])

    fig_better = make_graph(rp.better, 'Bar chart of improved benchmarks')
    call(['orca', 'graph', 
        '-o', 'figure1_improved',
        '-f', 'pdf', 
        '--width', '1500', 
        '--height', '600',
        json.dumps(fig_better, cls=plotly.utils.PlotlyJSONEncoder)])

    fig_worse = make_graph(rp.worse, 'Bar chart of worsened benchmarks')
    call(['orca', 'graph', 
        '-o', 'figure1_hurt',
        '-f', 'pdf', 
        '--width', '1500', 
        '--height', '600',
        json.dumps(fig_worse, cls=plotly.utils.PlotlyJSONEncoder)])

    fig_neither = make_graph(rp.neither, 'Bar chart of everything else')
    call(['orca', 'graph', 
        '-o', 'figure1_insignificantly_affected',
        '-f', 'pdf', 
        '--width', '1500', 
        '--height', '600',
        json.dumps(fig_neither, cls=plotly.utils.PlotlyJSONEncoder)])

def get_crates_layout(rp):
    layout = html.Div([
        html.Br(),
        html.H6('Pick a crate:'),
        dcc.Dropdown(id='crate_name',
            options=rp.options,
            value='actix-service-1.0.6',
            style={'width': '50%'}
        ),
        html.Br(),
        html.Div(id='crate_graph'),
        html.Br(),
    ])

    return layout

@app.callback(dash.dependencies.Output('crate_graph', 'children'),
        [dash.dependencies.Input('crate_name', 'value')])
def display_pipe(crate_name):
    return display_crate(crate_name)

def display_crate(crate_name):
    # TODO add error bars
    global data 
    if crate_name and data[crate_name]: 
        fig = make_graph(data[crate_name], 'Bar Chart of Crate Benchmarks')
        geo = geomean_overflow(list(data[crate_name].values()))

        return html.Div([
            html.Br(),
            html.H6('Average Speedup for [{}] Crate: {}'.format(crate_name, str(geo))),
            html.H6('Number of Benchmarks in [{}] Crate: {}'.format(crate_name, str(len(data[crate_name])))),
            dcc.Graph(
                id='crate_fig',
                figure=fig
            )
        ])
    else: 
        return html.Div([
            html.Br(),
            html.H6('Crate [{}] has no benchmarks'.format(crate_name)),
            html.Br()
        ])

def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", "-r",
            metavar="path",
            type=str,
            required=False,
            default="./results/",
            help="root path of scraped crates directory with benchmark results; "\
            "default is ./results/")
    parser.add_argument("-p", "--port",
            metavar="num",
            type=str,
            required=False,
            default="8050",
            help="port for Dash server to run; 8050 or 8060 on AWS")
    args = parser.parse_args()
    return args.root, args.port

@app.callback(dash.dependencies.Output('page_content', 'children'),
              [dash.dependencies.Input('url', 'pathname')])
def display_page(pathname):
    if not pathname:
        return 404
    if pathname == '/':
        pathname = '/passOverview'
    if pathname == '/passOverview':
        layout = get_overview_layout(app._result_provider)
        return layout
    elif pathname == '/passCrates':
        layout = get_crates_layout(app._result_provider)
        return layout
    else:
        return 404

if __name__ == '__main__':
    root, port = parseArgs()
    app._result_provider = ResultProvider(root)
    app._result_provider.get_speedups()

    app.layout = html.Div([
        dcc.Location(id='url', refresh=False),
        dcc.Link('Results Overview', href='/passOverview'),
        html.Br(),
        dcc.Link('Results per Crate', href='/passCrates'),
        html.Br(),
        html.Div(id='page_content')
    ])
    print(dash.__version__)
    print(plotly.__version__)

    app.run_server(debug=False, host='0.0.0.0', port=port)

