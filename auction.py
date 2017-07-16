from ctoken import xassert


class Auction(object):

    def __init__(self):
        self.mint = None  # set by mint

    def start(self, factor, const):
        self.factor = factor
        self.const = const
        self.elapsed = 0
        self.value_by_buyer = {}
        self.ended = False
        self.reserve = 0
        self.final_price = 0

    @property
    def auctioned_supply(self):
        """
        The current available (additional) supply
        which can be bought at the same price by all eligibile bidders
        includes the seniorage tokens
        """
        return self.factor / (self.elapsed + self.const)

    @property
    def _total_supply(self):
        return self.mint.token.supply + self.auctioned_supply

    @property
    def price(self):
        """
        the price all eligible bidders would pay.
        it's the average price for the additional supply minus the seniorage
        """
        auctioned_supply = self.auctioned_supply
        total_supply = self.mint.token.supply + auctioned_supply
        added_reserve = self.mint.curve.reserve(total_supply) - self.mint.reserve
        seniorage = auctioned_supply * self.mint.beneficiary.fraction
        sold_supply = auctioned_supply - seniorage
        avg_price = added_reserve / sold_supply  # need to pay for seniorage tokens
        # print auctioned_supply, avg_price
        return avg_price

    avg_price = price

    @property
    def missing_reserve_to_end_auction(self):
        target = self.mint.curve.reserve(self._total_supply)
        missing = target - self.mint.reserve - self.reserve
        return max(0, missing)

    @property
    def combined_reserve(self):
        return self.reserve + self.mint.reserve

    def order(self, recipient, value):
        value = min(value, self.missing_reserve_to_end_auction)  # FXIME refund
        self.value_by_buyer[recipient] = self.value_by_buyer.get(recipient, 0) + value
        self.reserve += value
        # print self.reserve, value, self.price
        if self.missing_reserve_to_end_auction == 0:  # this call ended the auction
            self.finalize_auction()

    # @property
    # def _mint_ask(self):
    #     return self.mint.curve.price_at_reserve(self.combined_reserve) \
    #         * self.mint.beneficiary.factor

    def finalize_auction(self):
        # xassert(self.price, self._mint_ask)
        assert not self.ended  # call only once
        assert self.reserve
        self.ended = True
        self.final_price = self.price
        # all orders get tokens at the current price
        # price = self.price
        new_issuance = self.mint.curve.supply(self.combined_reserve) - self.mint.token.supply
        seniorage = new_issuance * self.mint.beneficiary.fraction
        assert seniorage < new_issuance
        avg_price = self.reserve / (new_issuance - seniorage)
        print 'finalizing auction at price:{} avg price:{:,.2f}'.format(self.price, avg_price)

        for recipient, value in self.value_by_buyer.items():
            num_issued = new_issuance * value / self.reserve
            # print num_issued, value, price
            self.mint._issue(num_issued, recipient)
        # transfer reserve
        self.mint.reserve = self.reserve
        xassert(self.mint.curve.reserve(self.mint.token.supply), self.reserve)
        xassert(self.mint.token.supply, self.mint.curve.supply(self.reserve))
        # self.reserve = 0

        xassert(self.mint.token.supply, new_issuance)
        assert self.mint.token.supply > 0
        print 'supply', self.mint.token.supply

    @property
    def bid(self):
        s = self._total_supply
        r = self.mint.curve.reserve(s)
        return r / s

    @property
    def max_mktcap(self):
        return self._total_supply * self.avg_price

    @property
    def max_valuation(self):
        # return self.max_mktcap * self.mint.beneficiary.fraction
        return self._total_supply * (self.avg_price - self.bid)
