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
from ctoken import ContinuousToken, PriceSupplyCurve, Auction, Beneficiary
from draw import draw

Investment = namedtuple('Investment', 'value, valuation')


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
    curve = PriceSupplyCurve(factor=0.0001, base_price=5)
    auction = Auction(factor=10**6, const=10**3)
    beneficiary = Beneficiary(issuance_fraction=0.3)
    ct = ContinuousToken(curve, beneficiary, auction)
    return ct


class Simulation(object):

    def __init__(self, ct, investments):
        self.ct = ct
        self.investments = investments
        self.step = 10
        self.ticker = []

    def report(self):
        a = 'A' if self.ct.isauction else 'T'
        s = '{} ask:{:.2f} bid:{:.2f} mktcap:{:,.0f}  maxvaluation:{:,.0f} valuation:{:,.0f} reserve:{:,.0f} supply:{:,.0f}'
        print s.format(self.ct.auction.elapsed, self.ct.ask, self.ct.bid, self.ct.mktcap,
                       self.ct.max_valuation, self.ct.valuation, self.ct.reserve_value, self.ct.token.supply)

    def tick(self, **kargs):
        d = dict(time=self.ct.auction.elapsed,
                 CT_Sale_Price=self.ct.ask,
                 CT_Purchase_Price=self.ct.bid,
                 MktCap=self.ct.mktcap,
                 Valuation=self.ct.valuation,
                 Max_MktCap=self.ct.max_mktcap,
                 Max_Valuation=self.ct.max_valuation,
                 CT_Reserve=self.ct.reserve_value,
                 CT_Reserve_Based_Price=self.ct.curve_price,
                 CT_Supply=self.ct.token.supply,
                 CT_Arithmetic_Supply=self.ct._arithmetic_supply,
                 CT_Notional_Supply=self.ct._notional_supply,
                 CT_Simulated_Supply=self.ct._simulated_supply,
                 CT_Simulated_Price=self.ct.curve_price_auction,
                 CT_Spread=self.ct.ask - self.ct.bid
                 )
        d.update(kargs)
        self.ticker.append(d)

    def run_auction(self, max_elapsed):
        while self.ct.auction.elapsed < max_elapsed:
            self.ct.auction.elapsed += self.step
            # valuation = self.ct.valuation_after_create(i.value)
            while self.investments[0].valuation > self.ct.max_valuation:  # FIXME slippage
                i = self.investments.pop(0)
                # print self.ct.ask, valuation, i
                self.ct.create(i.value, i)
                self.report()
                if not self.investments:
                    break
            self.tick()
            if not self.ct.isauction:
                break
        self.report()
        assert self.ct.auction.ended
        assert self.ct.token.supply > 0

    def run_trading(self, max_elapsed, stddev, period_factor):
        ct = self.ct
        assert ct.token.supply > 0
        assert not ct.isauction
        ex_price = self.ct.ask
        steps = (max_elapsed - ct.auction.elapsed) / self.step
        median = period_factor ** (1 / steps)

        while ct.auction.elapsed < max_elapsed:
            ct.auction.elapsed += self.step
            # random walk on valuation
            ex_price *= random.normalvariate(median, stddev)
            if ex_price > ct.ask:
                added_reserve = ct.curve.reserve_at_price(ex_price) \
                    - ct.curve.reserve_at_price(ct.ask)
                ct.create(added_reserve, 'market buyer')
            self.tick(Market_Price=ex_price)


def main():
    random.seed(43)
    ct = gen_token()
    num_investors = 30
    total_investable = 100 * 10**6
    median_valuation = 50 * 10**6
    std_deviation = 0.5 * median_valuation
    investments = gen_investments(num_investors, total_investable, median_valuation, std_deviation)

    sim = Simulation(ct, investments[:])

    sim.run_auction(3600 * 48)
    sim.run_trading(ct.auction.elapsed * 2, stddev=0.01, period_factor=2.)

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

    # draw(sim.ticker)

if __name__ == '__main__':
    main()
