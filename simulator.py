""""
ContinousToken with Auction
Exchange contract

Setup:
    - Continuous Token with Auction
    - Exchange
    - set of bidders with total purchase_amount
        - with different normal distributed limit prices
        - place buy orders at an exchange
    - auction starts
    - arbitrageur buys from auction and sells on the market if he can make a profit
    - auction ends
    - marketmaker generates random walk prices
    - arbitrageur buys or sells, between continuous token and exchange

Observables:
    - bid / floor
    - ask / ceiling
    - reserve based price
    - auction price
    - supply
    - mktcap
    - valuation

Parameters:
    - total purchase_amount
    - pareto distributon of order value per bidder
    - normal distribution of valuation, median
    - num bidders
"""
from __future__ import division
import random
from operator import attrgetter
from collections import namedtuple
from ctoken import Mint, PriceSupplyCurve, Beneficiary
from auction import Auction
from draw import draw

Bid = namedtuple('Bid', 'value, valuation')


class Simulation(object):

    def __init__(self, mint, bids):
        self.mint = mint
        self.auction = mint.auction
        self.bids = bids
        self.step = 10
        self.ticker = []

    def report(self):
        a = 'A' if self.mint.isauction else 'T'
        s = '{}{} ask:{:.2f} bid:{:.2f} maxmktcap:{:,.0f}  maxvaluation:{:,.0f} valuation:{:,.0f} ' +\
            'reserve:{:,.0f} supply:{:,.0f}'
        print s.format(a, self.auction.elapsed, self.ask, self.bid, self.maxmktcap,
                       self.maxvaluation, self.mint.valuation, self.reserve,
                       self.mint.token.supply)

    @property
    def maxvaluation(self):
        return self.mint.valuation if self.auction.ended else self.auction.max_valuation

    @property
    def maxmktcap(self):
        return self.mint.mktcap if self.auction.ended else self.auction.max_mktcap

    @property
    def ask(self):
        return self.mint.ask if self.auction.ended else self.auction.price

    @property
    def bid(self):
        return self.mint.bid if self.auction.ended else self.auction.bid

    @property
    def reserve(self):
        return self.mint.reserve + self.auction.reserve

    @property
    def reserve_based_price(self):
        return self.mint.curve.price_at_reserve(self.reserve) * self.mint.beneficiary.factor

    def tick(self, **kargs):

        d = dict(time=self.auction.elapsed,
                 Sale_Price=self.ask,
                 Purchase_Price=self.mint.bid,
                 MktCap=self.mint.mktcap,
                 Valuation=self.mint.valuation,
                 Max_MktCap=self.maxmktcap,
                 Max_Valuation=self.maxvaluation,
                 Reserve=self.reserve,
                 Reserve_Based_Price=self.reserve_based_price,
                 Supply=self.mint.token.supply,
                 Reserve_Based_Supply=self.mint.curve.supply(self.reserve),
                 Auction_Price=self.auction.price,
                 Spread=self.mint.ask - self.mint.bid
                 )
        d.update(kargs)
        self.ticker.append(d)

    def run_auction(self, factor, const):
        self.auction.start(factor, const)
        print 'starting price:{} starting mktcap:{}'.format(
            self.auction.price, self.auction.max_mktcap)
        while not self.auction.ended and self.bids:
            # self.report()
            self.auction.elapsed += self.step
            while self.bids and self.bids[0].valuation > self.auction.max_valuation:
                i = self.bids.pop(0)
                self.auction.order(i, i.value)
                if self.auction.ended:
                    self.report()
                    break
                self.report()
            self.tick()
            if not self.mint.isauction:
                break
        assert self.auction.ended, 'increase the total order amount'
        assert self.mint.token.supply > 0

    def run_trading(self, max_elapsed, stddev, final_price):
        mint = self.mint
        assert mint.token.supply > 0
        assert not mint.isauction
        ex_price = mint.auction.final_price
        print 'trading start price', ex_price
        start = mint.auction.elapsed
        steps = (max_elapsed - start) / self.step
        period_factor = final_price / mint.bid
        median = period_factor ** (1 / steps)
        final_price_reached = False
        while ex_price < final_price:  # or mint.auction.elapsed < max_elapsed:
            mint.auction.elapsed += self.step
            # random walk on valuation
            ex_price *= random.normalvariate(median, stddev)
            if ex_price > mint.ask:
                added_reserve = mint.curve.reserve_at_price(ex_price) \
                    - mint.curve.reserve_at_price(mint.ask)
                mint.buy(added_reserve, 'market buyer')
                self.report()
            self.tick(Market_Price=ex_price)
            # let it trade a bit longer
            # if ex_price > final_price and not final_price_reached:
            #     max_elapsed = (mint.auction.elapsed - start) * 1.2 + start
            #     final_price_reached = True
            #     print 'price target reached'


def gen_bids(num_bidders, total_purchase_amount, median_valuation, std_deviation):
    bids = []
    for i in range(num_bidders):
        i = Bid(value=random.paretovariate(2),
                valuation=random.normalvariate(median_valuation, std_deviation))
        bids.append(i)
    # norm
    f = total_purchase_amount / sum(i.value for i in bids)
    bids = [Bid(b.value * f, b.valuation) for b in bids]
    bids.sort(key=attrgetter('valuation'), reverse=True)
    assert bids[0].valuation > bids[-1].valuation
    return bids


def gen_token():
    curve = PriceSupplyCurve(factor=0.000001, base_price=1)
    auction = Auction()
    beneficiary = Beneficiary(issuance_fraction=.2)
    ct = Mint(curve, beneficiary, auction)
    return ct


def main():
    random.seed(42)
    mint = gen_token()
    num_bidders = 300
    total_purchase_amount = 20 * 10**6
    median_valuation = 5 * 10**6

    std_deviation = 0.25 * median_valuation
    bids = gen_bids(num_bidders, total_purchase_amount, median_valuation, std_deviation)

    sim = Simulation(mint, bids[:])

    print 'Running Auction'
    sim.run_auction(factor=10**12, const=10**3)

    print 'Running Trading'
    final_price = 1.2 * sim.mint.ask
    sim.run_trading(mint.auction.elapsed * 3, stddev=0.005, final_price=final_price)

    tstart = len(sim.ticker)

    if False:  # calc changes
        e = sim.ticker[-1]
        s = sim.ticker[tstart + 1]
        for i, t in enumerate(sim.ticker):
            for key in ['CT_Supply', 'CT_Sale_Price', 'CT_Purchase_Price', 'CT_Spread',
                        'MktCap', 'Valuation', 'CT_Reserve', 'Market_Price']:
                n = 'Change_' + key
                if i > tstart:
                    t[n] = t[key] / s[key]
                else:
                    t[n] = 1
        print e

    print 'max valuation', max(i.valuation for i in bids)
    print 'min valuation', min(i.valuation for i in bids)
    print 'avg valuation', sum(i.valuation for i in bids) / len(bids)
    print 'max order value', max(i.value for i in bids)
    print 'min order value', min(i.value for i in bids)
    print 'not ordered', len(sim.bids)

    print 'visualizing {} ticks'.format(len(sim.ticker))
    draw(sim.ticker)

if __name__ == '__main__':
    main()
