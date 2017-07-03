from ctoken import PriceSupplyCurve, xassert
from math import sqrt

bf = 0.3
M = 1000**2
c = PriceSupplyCurve(factor=0.0001, base_price=0)

reserve = 50 * M  # the total proceeds
s = c.supply(reserve)
xassert(c.reserve(s), reserve)
p = c.price(s)  # all bought at this price
issued = reserve / p
skipped = s - issued
print 'issued', issued, s, skipped
mktcap = issued * p

fmt = 'ceil:{:,.0f}\tprice:{:,.0f}\tfloor:{:,.0f}\tmktcap:{:,.0f}\treserve:{:,.0f}'
fmt += '\tpval:{:,.0f}\tsupply:{:,.0f}\tbval:{:,.0f}'

mktcap /= 2
for i in range(7):
    mktcap *= 2
    s = c.supply_at_mktcap(mktcap, skipped)
    price = c.price(s + skipped)
    xassert(mktcap, s * price)
    r = c.reserve_at_price(price)
    f = r / s
    ceil = price / (1 - bf)
    bval = bf * mktcap
    pval = mktcap - r
    print fmt.format(ceil, price, f, mktcap, r, pval, s, bval)
