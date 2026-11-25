"""An asset table made only for tests: two moneys to price in, one that cannot, a share.

It is not the built-in table and no part of the program is handed it; it
is here so that what the program can do with another table is tested now.
USDT and USD are both money trades may be priced in, and "刀" names both.
EUR is money no trade may be priced in. The assets are Bitcoin, Ether and
one invented share; an asset the table does not know cannot be recorded;
"股", "share" and "shares" may stand after a number.

Names defined here: ``TWO_MONEYS``, ``USDT``, ``USD`` and ``EUR``.
"""

from __future__ import annotations

from ledger_hand.core.assets import AssetTable, Money, MoneyUse, UnknownAssets
from ledger_hand.core.coins import Coin, CoinTable

USDT = Money("USDT", ("U", "泰达币", "刀"), MoneyUse.CAN_PRICE)
USD = Money("USD", ("美元", "$", "刀"), MoneyUse.CAN_PRICE)
EUR = Money("EUR", ("欧元",), MoneyUse.CANNOT_PRICE)

TWO_MONEYS = AssetTable(
    coins=CoinTable(
        (
            Coin("BTC", "Bitcoin", None, ("比特币",)),
            Coin("ETH", "Ethereum", None, ("以太坊",)),
            Coin("MSFT", "Microsoft", None, ("微软",)),
        )
    ),
    moneys=(USDT, USD, EUR),
    unknown=UnknownAssets.REFUSE,
    extra_units=("股", "share", "shares"),
)
