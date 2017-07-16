# Learn about API authentication here: https://plot.ly/python/getting-started
# Find your api_key here: https://plot.ly/settings/api
import collections
import plotly.plotly as py
import plotly.graph_objs as go
from plotly import tools


def draw(ticks):

    ticks_r = [t for t in ticks if t['Raised_Reserve'] > 0]
    ticks = ticks[-int(len(ticks_r) * 1.1):]

    def tdata(key):
        return [(t['time'], t[key]) for t in ticks if key in t]

    traces1 = []
    traces2 = []

    def chart(key, t=traces1):
        d = tdata(key)
        assert d
        name = key.replace('_', ' ')
        s = go.Scatter(x=[_[0] for _ in d], y=[_[1] for _ in d], name=name)
        t.append(s)

    def chart2(key):
        chart(key, traces2)

    # PRICES
    chart('Auction_Price')
    chart('Purchase_Price')

    # Valuations
    chart2('MktCap_At_Price')
    chart2('Raised_Reserve')
    chart2('Max_Reserve_At_Price')
    chart2('Valuation_At_Price')

    ######
    SHOW = collections.OrderedDict(
        Prices=traces1,
        Valuation=traces2,
    )

    fig = tools.make_subplots(rows=len(SHOW), cols=1,
                              subplot_titles=SHOW.keys())

    for i, traces in enumerate(SHOW.values()):
        for t in traces:
            fig.append_trace(t, i + 1, 1)

    fig['layout'].update(title='Reverse Auction')
    plot_url = py.plot(fig, filename='continuoustoken6')
