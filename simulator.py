""""
ContinousToken with Auction
Exchange contract

Setup:
    - Continuous Token with Auction
    - Exchange
    - set of investors with total investable amount
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
    - total investable amount
    - pareto distributon of investment per investor
    - normal distribution of valuation, median
    - num investors
"""
from __future__ import division
import random
from operator import attrgetter
from collections import namedtuple
from ctoken import Mint, PriceSupplyCurve, Auction, Beneficiary
from draw import draw

Investment = namedtuple('Investment', 'value, valuation')


class Simulation(object):

    def __init__(self, mint, investments):
        self.mint = mint
        self.auction = mint.auction
        self.investments = investments
        self.step = 10
        self.ticker = []

    def report(self):
        a = 'A' if self.mint.isauction else 'T'
        s = '{}{} ask:{:.2f} bid:{:.2f} mktcap:{:,.0f}  maxvaluation:{:,.0f} valuation:{:,.0f} ' +\
            'reserve:{:,.0f} supply:{:,.0f}'
        print s.format(a, self.auction.elapsed, self.ask, self.mint.bid, self.mint.mktcap,
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
    def reserve(self):
        return self.mint.reserve + self.auction.reserve

    @property
    def reserve_based_price(self):
        return self.mint.curve.price_at_reserve(self.reserve) / (1 - self.mint.beneficiary.fraction)

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

    def run_auction(self, max_elapsed):
        while not self.auction.ended:
            self.auction.elapsed += self.step
            # valuation = self.mint.valuation_after_create(i.value)
            while self.investments[0].valuation > self.auction.max_valuation:  # FIXME slippage
                i = self.investments.pop(0)
                self.auction.order(i, i.value)
                if self.auction.ended:
                    assert self.investments, 'increase the invstable amount'
                    self.report()
                    break
                self.report()
            self.tick()
            if not self.mint.isauction:
                break
        assert self.auction.ended, 'increase the invstable amount'
        assert self.mint.token.supply > 0

    def run_trading(self, max_elapsed, stddev, final_price):
        mint = self.mint
        assert mint.token.supply > 0
        assert not mint.isauction
        ex_price = mint.ask
        steps = (max_elapsed - mint.auction.elapsed) / self.step
        period_factor = final_price / mint.ask
        median = period_factor ** (1 / steps)

        # while mint.auction.elapsed < max_elapsed:
        while ex_price < final_price:
            mint.auction.elapsed += self.step
            # random walk on valuation
            ex_price *= random.normalvariate(median, stddev)
            if ex_price > mint.ask:
                added_reserve = mint.curve.reserve_at_price(ex_price) \
                    - mint.curve.reserve_at_price(mint.ask)
                mint.buy(added_reserve, 'market buyer')
                self.report()
            self.tick(Market_Price=ex_price)


def gen_investments(num_investors, total_investable, median_valuation, std_deviation):
    investments = []
    for i in range(num_investors):
        i = Investment(value=random.paretovariate(2),
                       valuation=random.normalvariate(median_valuation, std_deviation))
        investments.append(i)
    # norm
    f = total_investable / sum(i.value for i in investments)
    investments = [Investment(i.value * f, i.valuation) for i in investments]
    investments.sort(key=attrgetter('valuation'), reverse=True)
    assert investments[0].valuation > investments[-1].valuation
    return investments


def gen_token():
    curve = PriceSupplyCurve(factor=0.000001, base_price=1)
    auction = Auction(factor=10**7, const=10**3)
    beneficiary = Beneficiary(issuance_fraction=0.2)
    ct = Mint(curve, beneficiary, auction)
    return ct


def main():
    random.seed(43)
    mint = gen_token()
    num_investors = 3000
    total_investable = 400 * 10**6
    median_valuation = 50 * 10**6

    std_deviation = 0.25 * median_valuation
    investments = gen_investments(num_investors, total_investable, median_valuation, std_deviation)

    sim = Simulation(mint, investments[:])

    print 'Running Auction'
    sim.run_auction(3600 * 48)

    print 'Running Trading'
    final_mktcap = 4 * mint.mktcap
    price_at_mktcap = mint.curve.price(mint.curve.supply_at_mktcap(final_mktcap))
    price_at_mktcap /= (1 - mint.beneficiary.fraction)
    sim.run_trading(mint.auction.elapsed * 2, stddev=0.005, final_price=price_at_mktcap)

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

    print 'max valuation', max(i.valuation for i in investments)
    print 'min valuation', min(i.valuation for i in investments)
    print 'avg valuation', sum(i.valuation for i in investments) / len(investments)
    print 'max investment', max(i.value for i in investments)
    print 'min investment', min(i.value for i in investments)
    print 'not invested', len(sim.investments)
    print len(sim.ticker)

    draw(sim.ticker)

if __name__ == '__main__':
    main()
