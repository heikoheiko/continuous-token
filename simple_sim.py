from __future__ import division
import random
from operator import attrgetter
from collections import namedtuple
from simple_auction import Auction, Token
from simple_draw import draw

Bid = namedtuple('Bid', 'value, valuation')


class Simulation(object):

    def __init__(self, auction, bids):
        self.auction = auction
        self.bids = bids
        self.step = 5 * 60  # 5 minutes
        self.ticker = []

    def report(self):
        s = '{} ask:{:.2f} bid:{:.2f} mktcap:{:,.0f} valuation:{:,.0f} reserve:{:,.0f}'
        print s.format(self.auction.elapsed,
                       self.auction.price,
                       self.auction.bid,
                       self.auction.mktcap_at_price,
                       self.auction.valuation_at_price,
                       self.auction.reserve)

    def tick(self, **kargs):
        d = dict(time=self.auction.elapsed,
                 Auction_Price=self.auction.price,
                 Purchase_Price=self.auction.bid,
                 MktCap_At_Price=self.auction.mktcap_at_price,
                 Valuation_At_Price=self.auction.valuation_at_price,
                 Raised_Reserve=self.auction.reserve,
                 Max_Reserve_At_Price=self.auction.reserve_at_price
                 )
        d.update(kargs)
        self.ticker.append(d)

    def run_auction(self):
        print 'starting price:{:,.0f} starting mktcap:{:,.0f}'.format(
            self.auction.price, self.auction.mktcap_at_price)
        while not self.auction.ended and self.bids:
            # self.report()
            self.auction.elapsed += self.step
            while self.bids and self.bids[0].valuation > self.auction.valuation_at_price:
                i = self.bids.pop(0)
                self.auction.order(i, i.value)
                if self.auction.ended:
                    self.report()
                    break
                self.report()
            self.tick()
            if self.auction.ended:
                break
        assert self.auction.ended, 'increase the total order amount'
        assert self.auction.token.supply > 0


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


def main():
    random.seed(42)

    num_bidders = 3000
    total_purchase_amount = 20 * 10**6
    median_valuation = 5 * 10**6

    std_deviation = 0.25 * median_valuation
    bids = gen_bids(num_bidders, total_purchase_amount, median_valuation, std_deviation)

    token = Token()
    token.issue(0.25 * Auction.supply, 'prealloc')  # 25% prealloc
    auction = Auction(token, factor=30 * 10**6, const=10**3, pre_auction_reserve=0)
    sim = Simulation(auction, bids[:])

    print 'Running Auction'
    sim.run_auction()

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
