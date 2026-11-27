"""Tests of a vague word for money ("美金", "刀") taken as the asset's own currency in the ledger.

The product owner's decision of 2026-11-27 on "美金": when the
asset's last trade in the ledger used a money that is neither USDT nor the
US dollar, a vague word is taken as the asset's own currency in the ledger,
marked as a guess, when that is USDT or the US dollar and the ledger prices
in it; in every other case nothing changes. One test for each line of the
table of examples, numbered B1 to B14 as there, and one walk through every
pair of the last trade's money and the asset's own. A scripted model
stands in for every call; "now" is 2026-11-27 18:00 in Budapest. Every
sentence, reply and number is invented.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.card_record import Doubt
from ledger_hand.core.ledger_records import (
    Asset,
    AssetKind,
    Pricing,
    TradeFacts,
    TradeFilter,
    TradeList,
)
from ledger_hand.core.marks import Field, MarkKind
from ledger_hand.core.trade import Side
from ledger_hand.flows.conversation import AssistantChat, Said, say
from ledger_hand.flows.recorded import RecordEnding
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ports import LedgerError, LedgerErrorKind, ToolCall, ToolReply
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import scripted_record
from tests.flows.scripted_flow import row, screened, table

ZONE = "Europe/Budapest"
_BUDAPEST = ZoneInfo(ZONE)
NOW = datetime(2026, 11, 27, 18, 0, tzinfo=_BUDAPEST)
RECORD = ToolReply(
    text="", calls=(ToolCall(name="propose_trade_add", arguments={}),), record=scripted_record()
)
GUESS = "This is a guess"
OWN = "own currency"
ASKS_QUOTE = "[Trade 1 of 1: pricing currency]"


def _money(code: str, pricing: Pricing = Pricing.CAN_PRICE) -> Asset:
    return Asset(
        id=f"asset-{code.lower()}", code=code, name=code, kind=AssetKind.CASH, pricing=pricing
    )


def _held(code: str, kind: AssetKind, own: str | None) -> Asset:
    return Asset(
        id=f"asset-{code.lower()}",
        code=code,
        name=code,
        kind=kind,
        pricing=Pricing.CANNOT_PRICE,
        price_currency=own,
    )


def _bought(
    asset: str, quote: str, when: tuple[int, int, int, int, int], rate: str | None = None
) -> TradeFacts:
    return TradeFacts(
        occurred=datetime(*when, tzinfo=_BUDAPEST),
        side=Side.BUY,
        asset=asset,
        quantity=Decimal(1),
        price=Decimal(60),
        total=Decimal(60),
        quote=quote,
        fee=Decimal(0),
        fee_asset=quote,
        platform="",
        note="",
        raw_text=None,
        zone=ZONE,
        date_only=False,
        cost_rate=Decimal(rate) if rate is not None else None,
    )


ASSETS = (
    _money("USDT"),
    _money("USD"),
    _money("EUR"),
    _held("KO", AssetKind.STOCK, "USD"),
    _held("SOL", AssetKind.CRYPTO, "USDT"),
    _held("INTC", AssetKind.STOCK, "USD"),
    _held("PEP", AssetKind.STOCK, "USD"),
    _held("DOT", AssetKind.CRYPTO, "EUR"),
    _held("ADA", AssetKind.CRYPTO, None),
    _held("NVDA", AssetKind.STOCK, "USD"),
    _held("AAPL", AssetKind.STOCK, "USD"),
)
KO_EUR = ("t-ko", _bought("KO", "EUR", (2026, 11, 20, 16, 0), rate="1.08"))
TRADES = (
    KO_EUR,
    ("t-sol", _bought("SOL", "EUR", (2026, 11, 20, 10, 0), rate="1.05")),
    ("t-intc", _bought("INTC", "USD", (2026, 11, 20, 16, 0))),
    ("t-dot", _bought("DOT", "EUR", (2026, 11, 20, 10, 0))),
    ("t-ada", _bought("ADA", "EUR", (2026, 11, 20, 10, 0))),
    ("t-nvda-eur", _bought("NVDA", "EUR", (2026, 11, 20, 10, 0), rate="1.08")),
    ("t-nvda-usd", _bought("NVDA", "USD", (2026, 11, 20, 16, 0))),
    ("t-aapl", _bought("AAPL", "EUR", (2026, 11, 20, 16, 0), rate="1.08")),
)


def ledger(
    *, cards: bool = True, assets: Sequence[Asset] = ASSETS, trades: Sequence = TRADES
) -> FakeLedger:
    return FakeLedger(assets=assets, trades=trades, prices={}, takes_unfinished=cards)


def talk(said: str, cells: dict[str, str], book: FakeLedger | None = None) -> Said:
    model = RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", said[:6]))],
        extraction=[table(row(**cells))],
    )
    return say(
        AssistantChat(),
        said,
        model=model,
        ledger=book if book is not None else ledger(),
        now=NOW,
        zone=ZONE,
        max_steps=6,
    )


def sent(said: Said):
    assert said.recorded is not None and said.recorded.ending is RecordEnding.SENT, said.reply
    (card,) = said.recorded.trades
    return card


def mark_on(said: Said, field: Field):
    assert said.recorded is not None
    return said.recorded.marked[0].marks.on(field)


def assumed_from_own(said: Said, field: Field, own: str, asset: str, last: str) -> None:
    mark = mark_on(said, field)
    assert mark is not None and mark.kind is MarkKind.INFERRED, mark
    assert f"{asset}'s own currency in the ledger, {own}" in (mark.reason or "")
    assert f"used {last}, not USDT or USD" in (mark.reason or "")


def asked_quote(said: Said) -> None:
    assert said.recorded is not None and said.recorded.ending is RecordEnding.ASKING, said.reply
    assert said.reply.startswith(ASKS_QUOTE), said.reply
    assert said.sent is None


def money_left_empty_for(said: Said, doubt: Doubt) -> None:
    card = sent(said)
    assert card.quote is None
    mark = mark_on(said, Field.QUOTE_ASSET_ID)
    assert mark is not None and mark.kind is MarkKind.SUSPICIOUS
    assert Doubt.of(mark.reason or "") is doubt
    assert OWN not in said.reply


KO = {"side": "buy", "coin": "KO", "quantity": "3股", "time": "今天15:30"}


def test_b1_meijin_after_a_euro_trade_is_the_shares_own_dollars() -> None:
    said = talk("今天15:30买了3股KO，一股70美金，手续费0", KO | {"price": "70美金", "fee": "0"})

    card = sent(said)
    assert (card.quote, card.price) == ("USD", Decimal(70))
    assumed_from_own(said, Field.QUOTE_ASSET_ID, "USD", "KO", "EUR")
    assert GUESS in said.reply and OWN in said.reply
    assert "its last trade used EUR" in said.reply


def test_b2_paid_in_euros_the_price_said_in_meijin_is_the_shares_own_dollars() -> None:
    said = talk(
        "今天15:30花了210欧元买了3股KO，一股70美金，换汇费0.3欧元",
        KO | {"price": "70美金", "total": "210欧元", "fee": "0.3欧元"},
    )

    card = sent(said)
    assert (card.quote, card.total, card.cost_rate) == ("EUR", Decimal(210), Decimal(1))
    rate = mark_on(said, Field.COST_RATE)
    assert rate is not None and rate.kind is MarkKind.INFERRED
    assert "KO's own currency in the ledger, USD" in (rate.reason or "")
    assert OWN in said.reply and GUESS in said.reply


def test_b3_a_coin_whose_own_currency_is_usdt() -> None:
    said = talk(
        "今天10点买了10个SOL，价格150刀，手续费0",
        {"side": "buy", "coin": "SOL", "quantity": "10个SOL", "time": "今天10点"}
        | {"price": "150刀", "fee": "0"},
    )

    card = sent(said)
    assert card.quote == "USDT"
    assumed_from_own(said, Field.QUOTE_ASSET_ID, "USDT", "SOL", "EUR")


def test_b4_the_fee_follows_the_same_rule() -> None:
    said = talk("今天15:30买了3股KO，一股70美金，手续费1刀", KO | {"price": "70美金", "fee": "1刀"})

    card = sent(said)
    assert (card.quote, card.fee_asset) == ("USD", "USD")
    assumed_from_own(said, Field.QUOTE_ASSET_ID, "USD", "KO", "EUR")
    assumed_from_own(said, Field.FEE_ASSET_ID, "USD", "KO", "EUR")
    assert "priced in USD and its fee is taken in USD, KO's own currency" in said.reply


def test_b5_a_last_trade_in_dollars_is_followed_as_before() -> None:
    said = talk(
        "今天15:30买了3股INTC，一股30美金，手续费0",
        {"side": "buy", "coin": "INTC", "quantity": "3股", "time": "今天15:30"}
        | {"price": "30美金", "fee": "0"},
    )

    card = sent(said)
    assert card.quote == "USD"
    mark = mark_on(said, Field.QUOTE_ASSET_ID)
    assert mark is not None and mark.kind is MarkKind.INFERRED
    assert (
        mark.reason
        == "assumed from the last INTC trade in the ledger (t-intc, 2026-11-20), which used USD"
    )
    assert OWN not in said.reply and GUESS in said.reply


def test_b6_a_share_never_traded_is_asked_as_before() -> None:
    said = talk(
        "今天15:30买了1股PEP，一股150美金，手续费0",
        {"side": "buy", "coin": "PEP", "quantity": "1股", "time": "今天15:30"}
        | {"price": "150美金", "fee": "0"},
    )

    asked_quote(said)


def test_b7_an_own_currency_in_euros_is_not_taken() -> None:
    said = talk(
        "今天10点买了2个DOT，价格5美金，手续费0",
        {"side": "buy", "coin": "DOT", "quantity": "2个DOT", "time": "今天10点"}
        | {"price": "5美金", "fee": "0"},
    )

    money_left_empty_for(said, Doubt.MONEY_OTHER_USED)


def test_b8_no_own_currency_named_is_as_before() -> None:
    said = talk(
        "今天10点买了100个ADA，价格0.5刀，手续费0",
        {"side": "buy", "coin": "ADA", "quantity": "100个ADA", "time": "今天10点"}
        | {"price": "0.5刀", "fee": "0"},
    )

    money_left_empty_for(said, Doubt.MONEY_OTHER_USED)


def test_b9_two_moneys_on_the_last_day_is_as_before() -> None:
    said = talk(
        "今天15:30买了1股NVDA，一股180美金，手续费0",
        {"side": "buy", "coin": "NVDA", "quantity": "1股", "time": "今天15:30"}
        | {"price": "180美金", "fee": "0"},
    )

    money_left_empty_for(said, Doubt.MONEY_TWO_USED)


def test_b10_dollars_said_are_no_guess() -> None:
    said = talk("今天15:30买了3股KO，一股70美元，手续费0", KO | {"price": "70美元", "fee": "0"})

    card = sent(said)
    assert card.quote == "USD"
    assert mark_on(said, Field.QUOTE_ASSET_ID) is None
    assert OWN not in said.reply and GUESS not in said.reply


def test_b11_usdt_said_stays_usdt() -> None:
    said = talk("今天15:30买了3股KO，一股70 USDT，手续费0", KO | {"price": "70 USDT", "fee": "0"})

    # Proposed in USDT as said; the ledger itself may turn down KO in USDT
    # (the fake ledger does, KO being priced in USD), which is no matter here.
    assert said.recorded is not None
    (card,) = said.recorded.trades
    assert card.quote == "USDT"
    assert mark_on(said, Field.QUOTE_ASSET_ID) is None
    assert OWN not in said.reply and GUESS not in said.reply


def test_b12_a_ledger_that_takes_no_cards_is_guessed_the_same() -> None:
    book = ledger(cards=False)
    said = talk(
        "今天15:30买了3股KO，一股70美金，手续费0", KO | {"price": "70美金", "fee": "0"}, book
    )

    card = sent(said)
    assert card.quote == "USD"
    assumed_from_own(said, Field.QUOTE_ASSET_ID, "USD", "KO", "EUR")
    assert "propose_add" in book.calls and OWN in said.reply


def test_b13_an_own_currency_the_ledger_cannot_price_in_is_not_taken() -> None:
    assets = tuple(
        dataclasses.replace(one, pricing=Pricing.CANNOT_PRICE) if one.code == "USD" else one
        for one in ASSETS
    )
    said = talk(
        "今天15:30买了3股KO，一股70美金，手续费0",
        KO | {"price": "70美金", "fee": "0"},
        ledger(assets=assets),
    )

    money_left_empty_for(said, Doubt.MONEY_OTHER_USED)
    assert sent(said).quote != "USDT"


def test_b14_the_old_e4_sentence() -> None:
    said = talk(
        "今天15:30花了210欧元买了1股AAPL，一股230美金，换汇费0.3欧元",
        {"side": "buy", "coin": "AAPL", "quantity": "1股", "time": "今天15:30"}
        | {"price": "230美金", "total": "210欧元", "fee": "0.3欧元"},
    )

    card = sent(said)
    assert (card.quote, card.total) == ("EUR", Decimal(210))
    rate = mark_on(said, Field.COST_RATE)
    assert rate is not None and rate.kind is MarkKind.INFERRED
    assert "AAPL's own currency in the ledger, USD" in (rate.reason or "")


# --- every pair of the last trade's money and the asset's own ----------------------------


class _FailingTrades(FakeLedger):
    def list_trades(self, conditions: TradeFilter) -> TradeList:
        raise LedgerError(LedgerErrorKind.UNREACHABLE, "UNREACHABLE", "not reached")


LASTS = ("USDT", "USD", "EUR", "none", "two", "failed")
OWNS = ("USDT", "USD", "EUR", None, "USD not pricing")


def _book(last: str, own: str | None) -> FakeLedger:
    code = own.split()[0] if own is not None else None
    assets: list[Asset] = [
        _money("USDT"),
        _money("USD", Pricing.CANNOT_PRICE if own == "USD not pricing" else Pricing.CAN_PRICE),
        _money("EUR"),
        _held("XYZ", AssetKind.CRYPTO, code),
    ]
    trades: list[tuple[str, TradeFacts]] = []
    if last in ("USDT", "USD", "EUR"):
        trades.append(("t-xyz", _bought("XYZ", last, (2026, 11, 20, 10, 0))))
    elif last == "two":
        trades.append(("t-xyz-a", _bought("XYZ", "USDT", (2026, 11, 20, 9, 0))))
        trades.append(("t-xyz-b", _bought("XYZ", "USD", (2026, 11, 20, 10, 0))))
    if last == "failed":
        return _FailingTrades(assets=assets, trades=(), prices={}, takes_unfinished=True)
    return FakeLedger(assets=assets, trades=trades, prices={}, takes_unfinished=True)


def _expected(last: str, own: str | None) -> str | None:
    """The money guessed for "刀", by the rule; ``None``: nothing guessed."""
    if last in ("USDT", "USD"):
        return last if not (last == "USD" and own == "USD not pricing") else None
    if last == "EUR" and own in ("USDT", "USD"):
        return own
    return None


@pytest.mark.parametrize("own", OWNS)
@pytest.mark.parametrize("last", LASTS)
def test_only_a_last_trade_in_another_money_looks_at_the_assets_own(
    last: str, own: str | None
) -> None:
    said = talk(
        "今天10点买了1个XYZ，价格5刀，手续费0",
        {"side": "buy", "coin": "XYZ", "quantity": "1个XYZ", "time": "今天10点"}
        | {"price": "5刀", "fee": "0"},
        _book(last, own),
    )

    expected = _expected(last, own)
    assert said.recorded is not None
    trades = said.recorded.progress.trades
    record = trades[0].record if trades and trades[0].record is not None else None
    record = record if record is not None else (trades[0].card if trades else None)
    source = record.inferred_from if record is not None else None
    if expected is None:
        assert source is None, (last, own, said.reply)
        assert OWN not in said.reply
        return
    assert source is not None, (last, own, said.reply)
    assert source.guessed == expected
    assert record is not None and record.quote == expected
    assert (source.own_money is not None) == (last == "EUR")
    # USDT and the US dollar never stand for each other.
    assert expected in ("USDT", "USD")
    if last in ("USDT", "USD"):
        assert expected == last
