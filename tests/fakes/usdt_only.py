"""The fake ledger's invented book with USDT as the one money trades are priced in.

The invented book prices trades in USDT and in USD. A test of recording
whose sentence gives a price with no money named was written when every
trade was priced in USDT; with both moneys the assistant would now ask
which. Such a test uses this book: the same assets and the same trades,
only USD is a money the ledger no longer prices trades in. Nothing is taken
out, so the count of trades and the stock bought with USD stay as they were.
"""

from __future__ import annotations

import dataclasses

from ledger_hand.core.ledger_records import Pricing
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_ASSETS

USDT_ONLY_ASSETS = tuple(
    dataclasses.replace(asset, pricing=Pricing.CANNOT_PRICE) if asset.code == "USD" else asset
    for asset in INVENTED_ASSETS
)


def usdt_only_ledger() -> FakeLedger:
    """A fake ledger with the invented book, USD made a money no trade is priced in."""
    return FakeLedger(assets=USDT_ONLY_ASSETS)
