from __future__ import division


class Token(object):

    def __init__(self):
        self.accounts = dict()

    @property
    def supply(self):
        return sum(self.accounts.values())

    def issue(self, num, recipient):
        if recipient not in self.accounts:
            self.accounts[recipient] = 0
        self.accounts[recipient] += num


class Auction(object):
    """
    Basic Idea: Reverse Auction, funds go into reserve
    If the total supply and prealloc are fixed,
        the required reserve at any auction ending price can be calculated
    The auction ends once
        the collected ETH (reserve) equals the required reserve at the current price

    See: https://plot.ly/~heikoheiko2/43/reverse-auction/
    """
    supply = 10**6

    def __init__(self, token, factor, const, pre_auction_reserve=0):
        self.token = token
        self.factor = factor
        self.const = const
        self.pre_auction_reserve = pre_auction_reserve
        self.reserve = 0
        self.prealloc = self.token.supply
        self.sold_supply = self.supply - self.prealloc

        self.value_by_buyer = dict()
        self.elapsed = 0
        self.ended = False

    @property
    def price(self):
        "price after elapsed time"
        return self.factor / (self.elapsed + self.const)

    @property
    def bid(self):
        return (self.reserve + self.pre_auction_reserve) / self.supply

    @property
    def mktcap_at_price(self):
        return self.supply * self.price

    @property
    def valuation_at_price(self):
        return self.mktcap_at_price - self.reserve_at_price - self.pre_auction_reserve

    @property
    def reserve_at_price(self):
        "this is the required added reserve at the current price"
        return self.sold_supply * self.price

    @property
    def missing_reserve_to_end_auction(self):
        return max(0, self.reserve_at_price - self.reserve)

    def order(self, recipient, value):
        assert not self.ended
        value = min(value, self.missing_reserve_to_end_auction)  # FXIME refund
        self.value_by_buyer[recipient] = self.value_by_buyer.get(recipient, 0) + value
        self.reserve += value
        if self.missing_reserve_to_end_auction == 0:  # this call ended the auction
            self.finalize_auction()

    def finalize_auction(self):
        # all orders get tokens at the current price
        print 'finalizing auction at price:{}'.format(self.price)
        for recipient, value in self.value_by_buyer.items():
            num_issued = self.sold_supply * value / self.reserve
            self.token.issue(num_issued, recipient)
        self.ended = True
