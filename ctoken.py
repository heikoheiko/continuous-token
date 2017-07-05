from __future__ import division
from math import sqrt


def assert_almost_equal(a, b, threshold=0.0001):
    if min(a, b) > 0:
        assert abs(a - b) / min(a, b) <= threshold, (a, b)
    assert abs(a - b) <= threshold, (a, b)
    return True


xassert = assert_almost_equal


class InsufficientFundsError(Exception):
    pass


class Beneficiary(object):

    def __init__(self, issuance_fraction=0):
        self.fraction = issuance_fraction


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

    def destroy(self, num, owner):
        if self.accounts[owner] < num:
            raise InsufficientFundsError('{} < {}'.format(self.accounts[owner], num))
        self.accounts[owner] -= num

    def transfer(self, _from, _to, value):
        assert self.accounts[_from] >= value
        self.accounts[_from] -= value
        self.accounts[_to] += value

    def balanceOf(self, address):
        return self.accounts.get(address, 0)


class PriceSupplyCurve(object):

    def __init__(self, factor=1., base_price=0):
        self.f = factor
        self.b = base_price

    def price(self, supply):
        return self.b + self.f * supply

    def price_at_reserve(self, reserve):
        return self.price(self.supply(reserve))

    def supply(self, reserve):
        return (-self.b + sqrt(self.b**2 + 2 * self.f * reserve)) / self.f

    def supply_at_price(self, price):
        assert price >= self.b
        return (price - self.b) / self.f

    def reserve(self, supply):
        return self.b * supply + self.f / 2 * supply**2

    def reserve_at_price(self, price):
        assert price >= 0
        return self.reserve(self.supply_at_price(price))

    def cost(self, supply, num):
        return self.reserve(supply + num) - self.reserve(supply)

    def issued(self, supply, added_reserve):
        reserve = self.reserve(supply)
        return self.supply(reserve + added_reserve) - self.supply(reserve)

    def mktcap(self, supply):
        return self.price(supply) * supply

    def supply_at_mktcap(self, m, skipped=0):
        b, f = self.b, self.f
        f = self.f
        b = (self.b + skipped * self.f)
        s = (-b + sqrt(b**2 - 4 * f * -m)) / (2 * f)
        return s


class Mint(object):

    def __init__(self, curve, beneficiary, auction):
        self.curve = curve
        self.auction = auction
        self.auction.mint = self
        self.beneficiary = beneficiary
        self.auction = auction
        self.token = Token()
        self.reserve = 0

    # supplies

    @property
    def _notional_supply(self):
        """"
        supply according to reserve
        """
        return self.curve.supply(self.reserve)

    # cost of selling, purchasing tokens

    def _sale_cost(self, num):  # cost
        assert num >= 0
        added = num / (1 - self.beneficiary.fraction)
        return self.curve.cost(self._notional_supply, added)

    def _purchase_cost(self, num):
        "the value offered if tokens are bought back"
        if not self.token.supply:
            return 0
        assert num >= 0 and num <= self.token.supply
        c = self.reserve * num / self.token.supply
        return c

    # public functions

    def buy(self, value, recipient=None):
        self.reserve += value
        s = self._notional_supply
        issued = self.curve.issued(s, value)
        return self._issue(issued, recipient)

    def _issue(self, num_issued, recipient):
        num_sold = num_issued * (1 - self.beneficiary.fraction)
        seigniorage = num_issued - num_sold
        self.token.issue(num_sold, recipient)
        self.token.issue(seigniorage, self.beneficiary)
        return num_sold

    def destroy(self, num, owner=None):
        value = self._purchase_cost(num)
        self.token.destroy(num, owner)  # can throw
        assert value < self.reserve or xassert(value, self.reserve)
        value = min(value, self.reserve)
        self.reserve -= value
        return value

    # public const functions

    @property
    def isauction(self):
        return not self.auction.ended

    @property
    def ask(self):
        return self._sale_cost(1)

    @property
    def bid(self):
        # if not self.reserve:
        if self.isauction:
            return 0
        bid = self._purchase_cost(1)
        assert bid <= self.ask, (bid, self.ask)
        return bid

    @property
    def price(self):
        return self.curve.cost(self._notional_supply, 1)

    @property
    def mktcap(self):
        return self.ask * self.token.supply

    @property
    def valuation(self):  # (ask - bid) * supply
        return max(0, self.mktcap - self.reserve)


class Auction(object):

    def __init__(self, factor, const):
        self.factor = factor
        self.const = const
        self.elapsed = 0
        self.value_by_buyer = {}
        self.ended = False
        self.mint = None  # set by mint
        self.reserve = 0

    @property
    def price(self):
        return self.factor / (self.elapsed + self.const)

    @property
    def combined_reserve(self):
        return self.reserve + self.mint.reserve

    @property
    def missing_reserve_to_end_auction(self):
        ask_price = self.price
        curve_price = ask_price * (1 - self.mint.beneficiary.fraction)
        target = self.mint.curve.reserve_at_price(curve_price)
        return max(0, target - self.reserve)

    def order(self, recipient, value):
        value = min(value, self.missing_reserve_to_end_auction)  # FXIME refund
        self.value_by_buyer[recipient] = self.value_by_buyer.get(recipient, 0) + value
        self.reserve += value
        # print self.reserve, value, self.price
        if self.missing_reserve_to_end_auction == 0:  # this call ended the auction
            self.finalize_auction()

    def finalize_auction(self):
        mint_ask = self.mint.curve.price_at_reserve(
            self.combined_reserve) / (1 - self.mint.beneficiary.fraction)
        assert self.price <= mint_ask
        assert not self.ended  # call only once
        self.ended = True
        # all orders get tokens at the current price
        price = self.price
        total_issuance = self.mint.curve.supply(self.reserve) - self.mint.token.supply
        print 'finalizing auction at price:{}, issuing:{:,.0f}'.format(price, total_issuance)

        for recipient, value in self.value_by_buyer.items():
            num_issued = total_issuance * value / self.reserve
            # print num_issued, value, price
            self.mint._issue(num_issued, recipient)
        # transfer reserve
        self.mint.reserve = self.reserve
        xassert(self.mint.curve.reserve(self.mint.token.supply), self.reserve)
        xassert(self.mint.token.supply, self.mint.curve.supply(self.reserve))
        self.reserve = 0

        xassert(self.mint.token.supply, total_issuance)
        assert self.mint.token.supply > 0
        print 'supply', self.mint.token.supply

    @property
    def max_mktcap(self):
        vsupply = self.mint.curve.supply_at_price(self.price)
        return self.price * vsupply

    @property
    def max_valuation(self):  # FIXME
        return self.max_mktcap * self.mint.beneficiary.fraction
        # return self.max_mktcap - self.reserve
