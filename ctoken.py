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


class Auction(object):

    def __init__(self, factor, const):
        self.factor = factor
        self.const = const
        self.elapsed = 0
        self.value_by_buyer = {}
        self.ended = False

    def order(self, recipient, value):
        self.value_by_buyer[recipient] = self.value_by_buyer.get(recipient, 0) + value

    @property
    def price(self):
        return self.factor / (self.elapsed + self.const)


class PriceSupplyCurve(object):

    def __init__(self, factor=1., base_price=0):
        self.f = factor
        self.b = base_price

    def price(self, supply):
        return self.b + self.f * supply

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


class ContinuousToken(object):

    def __init__(self, curve, beneficiary, auction):
        self.curve = curve
        self.auction = auction
        self.beneficiary = beneficiary
        self.auction = auction
        self.token = Token()
        self.reserve_value = 0

    # supplies

    @property
    def _notional_supply(self):
        """"
        supply according to reserve_value
        """
        return self.curve.supply(self.reserve_value)

    @property
    def _simulated_supply(self):
        """
        current auction price converted to additional supply
        note: this is virtual skipped supply,
        so we must not include the skipped supply
        """
        if not self.auction.ended and self.auction.price >= self.curve.b:
            return self.curve.supply_at_price(self.auction.price)
        return 0

    @property
    def _arithmetic_supply(self):
        if self.isauction:
            return self._simulated_supply
        return self._notional_supply

    # cost of selling, purchasing tokens

    def _sale_cost(self, num):  # cost
        assert num >= 0
        added = num / (1 - self.beneficiary.fraction)
        return self.curve.cost(self._arithmetic_supply, added)

    def _purchase_cost(self, num):
        "the value offered if tokens are bought back"
        if not self.token.supply:
            return 0
        assert num >= 0 and num <= self.token.supply
        c = self.reserve_value * num / self.token.supply
        return c

    # auction specific methods

    @property
    def isauction(self):
        return (not self.auction.ended) and self._simulated_supply >= self._notional_supply

    @property
    def missing_reserve_to_end_auction(self):
        return max(0, self.curve.reserve(self._simulated_supply) - self.reserve_value)

    def finalize_auction(self):
        assert self._notional_supply >= self._simulated_supply
        assert not self.auction.ended
        # all orders get tokens at the current price
        price = self.ask
        total_issuance = self.curve.supply(self.reserve_value)
        print 'finalizing auction at price:{}, issuing:{:,.0f}'.format(price, total_issuance)

        for recipient, value in self.auction.value_by_buyer.items():
            num_issued = total_issuance * value / self.reserve_value
            # print num_issued, value, price
            self._issue(num_issued, recipient)

        xassert(self.curve.reserve(self.token.supply), self.reserve_value)
        xassert(self.token.supply, self.curve.supply(self.reserve_value))
        # assert it is not used anymore, even if tokens would be destroyed
        self.auction.ended = True
        xassert(self.token.supply, total_issuance)
        assert self.token.supply > 0
        print 'supply', self.token.supply

    # public functions

    def create(self, value, recipient=None):
        if self.isauction:
            return self._create_during_auction(value, recipient)
        return self._create(value, recipient)

    def _create_during_auction(self, value, recipient=None):
        if value > self.missing_reserve_to_end_auction:
            print "buy ends auction, need to send some tokens back"
            value = max(value, self.missing_reserve_to_end_auction)
        self.reserve_value += value
        self.auction.order(recipient, value)
        if not self.isauction:  # this call ended the auction
            self.finalize_auction()

    def _create(self, value, recipient=None):
        self.reserve_value += value
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
        assert value < self.reserve_value or xassert(value, self.reserve_value)
        value = min(value, self.reserve_value)
        self.reserve_value -= value
        return value

    # public const functions

    @property
    def ask(self):
        return self._sale_cost(1)

    @property
    def bid(self):
        if not self.reserve_value:
            return 0
        bid = self._purchase_cost(1)
        assert bid <= self.ask, (bid, self.ask)
        return bid

    @property
    def curve_price_auction(self):
        return self.curve.cost(self._arithmetic_supply, 1)

    @property
    def curve_price(self):
        return self.curve.cost(self._notional_supply, 1)

    @property
    def mktcap(self):
        return self.ask * self.token.supply

    @property
    def valuation(self):  # (ask - bid) * supply
        return max(0, self.mktcap - self.reserve_value)

    @property
    def max_mktcap(self):
        vsupply = self.curve.supply_at_price(self.ask)
        return self.ask * vsupply

    @property
    def max_valuation(self):  # FIXME
        return self.max_mktcap * self.beneficiary.fraction
