# Learn about API authentication here: https://plot.ly/python/getting-started
# Find your api_key here: https://plot.ly/settings/api
import collections
import plotly.plotly as py
import plotly.graph_objs as go
from plotly import tools


def draw(ticks):

    if False:  # remove most of initial auction
        max_mkt_cap = max([t['MktCap'] for t in ticks])
        ticks = [t for t in ticks if t['Max_Valuation'] < max_mkt_cap]
    else:
        ticks_r = [t for t in ticks if t['Reserve'] > 0]
        ticks = ticks[-int(len(ticks_r) * 1.1):]

    def tdata(key):
        return [(t['time'], t[key]) for t in ticks if key in t]

    traces1 = []
    traces2 = []
    traces3 = []
    traces4 = []

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
    chart('Reserve_Based_Price')
    chart('Sale_Price')
    chart('Market_Price')

    # Valuations
    chart2('MktCap')
    chart2('Reserve')
    chart2('Max_Valuation')
    chart2('Valuation')

    # Supplies
    chart('Reserve_Based_Supply', traces3)
    chart('Supply', traces3)

    # Changes
    if False and MARKETSIM:
        for key in ['Supply', 'Sale_Price', 'Purchase_Price', 'Spread',
                    'MktCap', 'Valuation', 'Reserve']:
            chart('Change_' + key, traces4)

    ######
    SHOW = collections.OrderedDict(
        Prices=traces1,
        Valuation=traces2,
        Supply=traces3,
        # Changes=traces4
    )

    fig = tools.make_subplots(rows=len(SHOW), cols=1,
                              subplot_titles=SHOW.keys())

    for i, traces in enumerate(SHOW.values()):
        for t in traces:
            fig.append_trace(t, i + 1, 1)

    fig['layout'].update(title='Continuous Token')
    plot_url = py.plot(fig, filename='continuoustoken4')
