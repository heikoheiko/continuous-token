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
        # factor and const determin the initial price and its rate of reduction over time
        self.factor = factor
        self.const = const
        # the incoming funds go to the reserve
        self.reserve = 0
        # the prealloc if any
        self.prealloc = self.token.supply
        # the reserve collected when selling the prealloc
        self.pre_auction_reserve = pre_auction_reserve
        # the number of tokens that are auctioned
        self.offered_supply = self.supply - self.prealloc
        # track the amounts received
        self.value_by_buyer = dict()
        # the elapsed time
        self.elapsed = 0
        self.closing_price = 0

    @property
    def price(self):
        "price after elapsed time"
        return self.factor / (self.elapsed + self.const)

    @property
    def bid(self):
        "the price offered when destroying tokens"
        return (self.reserve + self.pre_auction_reserve) / self.supply

    @property
    def mktcap_at_price(self):
        return self.supply * self.price

    @property
    def valuation_at_price(self):
        "valuation is the difference between the marketcap and the reserve "
        return self.mktcap_at_price - self.reserve_at_price - self.pre_auction_reserve

    @property
    def reserve_at_price(self):
        "this is the required added reserve at the current price"
        return self.offered_supply * self.price

    @property
    def missing_reserve_to_end_auction(self):
        "the reserve amount necessary to end the auction at the current price"
        return max(0, self.reserve_at_price - self.reserve)

    def order(self, recipient, value):
        """
        a bid at the current price.
        it's guranteed, that tokens can be bought at current or a lower valuation.
        """
        assert not self.closing_price
        value = min(value, self.missing_reserve_to_end_auction)
        self.value_by_buyer[recipient] = self.value_by_buyer.get(recipient, 0) + value
        self.reserve += value
        if self.missing_reserve_to_end_auction == 0:  # this call ended the auction
            self.finalize_auction()

    def finalize_auction(self):
        "all bidders get tokens at the same current price"
        print 'finalizing auction at price:{}'.format(self.price)
        self.closing_price = self.price
        for recipient, value in self.value_by_buyer.items():
            num_issued = self.offered_supply * value / self.reserve
            self.token.issue(num_issued, recipient)
