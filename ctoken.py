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
        self.factor = 1 / (1 - self.fraction)


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

    def sell(self, num, owner):
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

    def avg_price_at_reserve(self, reserve):
        return reserve / self.supply(reserve)

    def supply_at_avg_price(self, avg_price):
        return (avg_price - self.b) / self.f * 2

    def supply_at_avg_price_and_existing_supply(self, avg_price, s1):
        assert avg_price >= self.price(s1)
        return (avg_price - self.b - self.f / 2 * s1) / self.f * 2

    def avg_price_at_supply(self, supply):
        return self.b + self.f / 2 * supply

    def reserve_at_avg_price(self, avg_price):
        return self.reserve(self.supply_at_avg_price(avg_price))

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
    def supply_by_reserve(self):
        """"
        supply according to reserve
        """
        return self.curve.supply(self.reserve)

    # cost of selling, purchasing tokens

    def _sale_cost(self, num):  # cost
        assert num >= 0
        added = num * self.beneficiary.factor
        return self.curve.cost(self.supply_by_reserve, added)

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
        s = self.supply_by_reserve
        issued = self.curve.issued(s, value)
        return self._issue(issued, recipient)

    def _issue(self, num_issued, recipient):
        num_sold = num_issued * self.beneficiary.factor
        seigniorage = num_issued - num_sold
        self.token.issue(num_sold, recipient)
        self.token.issue(seigniorage, self.beneficiary)
        return num_sold

    def sell(self, num, owner=None):
        value = self._purchase_cost(num)
        self.token.sell(num, owner)  # can throw
        assert value < self.reserve or xassert(value, self.reserve)
        value = min(value, self.reserve)
        self.reserve -= value
        return value

    def burn(self, num, owner=None):
        "project might want to burn tokens, this increases the floor"
        self.token.sell(num, owner)  # can throw

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
        return self.curve.cost(self.supply_by_reserve, 1)

    @property
    def mktcap(self):
        return self.ask * self.token.supply

    @property
    def valuation(self):  # (ask - bid) * supply
        return max(0, self.mktcap - self.reserve)
