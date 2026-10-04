"""Tests of the check that turns a draft into a record or into two lists of problems.

Every trade below is invented. The current moment is always passed in, so
nothing here depends on the day the tests run.
"""

from __future__ import annotations

import dataclasses
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.coins import BUILT_IN_TABLE, CoinTable
from ledger_hand.core.trade import (
    Amount,
    OccurredTime,
    Side,
    TimePrecision,
    TradeDraft,
    TradeRecord,
)
from ledger_hand.core.validation import (
    DEFAULT_DERIVED_PLACES,
    DEFAULT_FUTURE_GRACE,
    DEFAULT_SETTINGS,
    CheckSettings,
    DraftProblems,
    Missing,
    Violation,
    check_draft,
)

BUDAPEST = "Europe/Budapest"
SHANGHAI = "Asia/Shanghai"
NOW = datetime(2026, 10, 4, 12, 0, tzinfo=ZoneInfo(BUDAPEST))
RAW_TEXT = "今天 9:40 买了 0.02 BTC，94900，手续费 2 USDT，我觉得要涨"
GRINNING_FACE = "\N{GRINNING FACE}"


def at(hour: int, minute: int, second: int = 0, *, zone: str = BUDAPEST) -> OccurredTime:
    """A moment on the invented "today", read off the wall clock of ``zone``."""
    precision = TimePrecision.SECOND if second else TimePrecision.MINUTE
    moment = datetime(2026, 10, 4, hour, minute, second, tzinfo=ZoneInfo(zone))
    return OccurredTime(moment, precision, zone)


def on(day: date, *, zone: str = BUDAPEST) -> OccurredTime:
    return OccurredTime(day, TimePrecision.DAY, zone)


def complete(**changes: object) -> TradeDraft:
    """A draft that passes every rule, with the given fields replaced."""
    draft = TradeDraft(
        side=Side.BUY,
        coin="BTC",
        quantity=Decimal("0.02"),
        price=Decimal("94900"),
        fee=Decimal("2"),
        fee_coin="USDT",
        occurred=at(9, 40),
        raw_text=RAW_TEXT,
    )
    return dataclasses.replace(draft, **changes)  # type: ignore[arg-type]


def amounts(
    quantity: str | None = None, price: str | None = None, total: str | None = None
) -> dict[str, Decimal | None]:
    """The three amounts as replacement fields; an amount left out is blank."""
    stated = {"quantity": quantity, "price": price, "total": total}
    return {name: None if text is None else Decimal(text) for name, text in stated.items()}


def written(value: Decimal) -> str:
    """The number written out in full, the way it goes into a ledger file."""
    return format(value, "f")


def record_of(outcome: TradeRecord | DraftProblems) -> TradeRecord:
    assert isinstance(outcome, TradeRecord), outcome
    return outcome


def problems_of(outcome: TradeRecord | DraftProblems) -> DraftProblems:
    assert isinstance(outcome, DraftProblems), outcome
    return outcome


def amount_of(built: TradeRecord, amount: Amount) -> Decimal:
    values = {
        Amount.QUANTITY: built.quantity,
        Amount.PRICE: built.price,
        Amount.TOTAL: built.total,
    }
    return values[amount]


def check(
    draft: TradeDraft,
    coins: CoinTable = BUILT_IN_TABLE,
    now: datetime = NOW,
    settings: CheckSettings = DEFAULT_SETTINGS,
) -> TradeRecord | DraftProblems:
    return check_draft(draft, coins, now, settings)


def missing(draft: TradeDraft, **options: object) -> tuple[Missing, ...]:
    return problems_of(check(draft, **options)).missing  # type: ignore[arg-type]


def violations(draft: TradeDraft, **options: object) -> tuple[Violation, ...]:
    return problems_of(check(draft, **options)).violations  # type: ignore[arg-type]


# --- a draft that is complete and sound becomes a record --------------------


def test_complete_sound_draft_becomes_a_record_with_the_same_values() -> None:
    draft = TradeDraft(
        side=Side.BUY,
        coin="BTC",
        quantity=Decimal("0.02"),
        price=Decimal("94900"),
        total=Decimal("1898"),
        quote="USDT",
        fee=Decimal("2"),
        fee_coin="USDT",
        occurred=at(9, 40),
        platform="OKX",
        note="我觉得要涨",
        raw_text=RAW_TEXT,
    )

    assert check(draft) == TradeRecord(
        side=Side.BUY,
        coin="BTC",
        quantity=Decimal("0.02"),
        price=Decimal("94900"),
        total=Decimal("1898"),
        derived=None,
        fee=Decimal("2"),
        fee_coin="USDT",
        occurred=at(9, 40),
        raw_text=RAW_TEXT,
        platform="OKX",
        note="我觉得要涨",
    )


def test_sell_known_to_the_day_with_platform_note_and_chinese_text_passes() -> None:
    raw_text = "昨天在币安卖了 0.5 个以太，3000 刀一个，手续费 1.5 刀，先落袋"
    draft = TradeDraft(
        side=Side.SELL,
        coin="以太",
        quantity=Decimal("0.5"),
        price=Decimal("3000"),
        quote="刀",
        fee=Decimal("1.5"),
        fee_coin="刀",
        occurred=on(date(2026, 10, 3)),
        platform="币安",
        note="先落袋",
        raw_text=raw_text,
    )

    assert check(draft) == TradeRecord(
        side=Side.SELL,
        coin="ETH",
        quantity=Decimal("0.5"),
        price=Decimal("3000"),
        total=Decimal("1500"),
        derived=Amount.TOTAL,
        fee=Decimal("1.5"),
        fee_coin="USDT",
        occurred=on(date(2026, 10, 3)),
        raw_text=raw_text,
        platform="币安",
        note="先落袋",
    )


@pytest.mark.parametrize("spoken", ["btc", " BTC ", "比特币", "大饼", "Bitcoin", "ＢＴＣ"])
def test_coin_is_recorded_under_its_symbol_however_it_was_said(spoken: str) -> None:
    assert record_of(check(complete(coin=spoken))).coin == "BTC"


def test_platform_and_note_are_optional() -> None:
    built = record_of(check(complete(platform=None, note=None)))

    assert built.platform is None
    assert built.note is None


def test_original_text_is_kept_character_for_character() -> None:
    raw_text = "  bought 0.02 BTC \n at 94900  "

    assert record_of(check(complete(raw_text=raw_text))).raw_text == raw_text


# --- what has to be there ---------------------------------------------------


@pytest.mark.parametrize(
    ("blank", "expected"),
    [
        ("side", Missing.SIDE),
        ("coin", Missing.COIN),
        ("fee", Missing.FEE),
        ("occurred", Missing.OCCURRED),
        ("raw_text", Missing.RAW_TEXT),
    ],
)
def test_blank_required_field_is_listed_as_missing(blank: str, expected: Missing) -> None:
    problems = problems_of(check(complete(**{blank: None})))

    assert problems == DraftProblems(missing=(expected,), violations=())


@pytest.mark.parametrize("spoken", ["", "   ", "\N{IDEOGRAPHIC SPACE}"])
def test_coin_made_of_whitespace_counts_as_blank(spoken: str) -> None:
    assert missing(complete(coin=spoken)) == (Missing.COIN,)


def test_empty_draft_lists_everything_that_is_missing_and_nothing_else() -> None:
    assert check(TradeDraft()) == DraftProblems(
        missing=(
            Missing.SIDE,
            Missing.COIN,
            Missing.TWO_OF_QUANTITY_PRICE_TOTAL,
            Missing.FEE,
            Missing.OCCURRED,
            Missing.RAW_TEXT,
        ),
        violations=(),
    )


# --- two of quantity, price and total give the third ------------------------


def test_quantity_and_price_give_the_total() -> None:
    built = record_of(check(complete(**amounts(quantity="0.02", price="94900"))))

    assert (built.quantity, built.price, built.total) == (
        Decimal("0.02"),
        Decimal("94900"),
        Decimal("1898"),
    )
    assert built.derived is Amount.TOTAL


def test_quantity_and_total_give_the_price() -> None:
    built = record_of(check(complete(**amounts(quantity="0.02", total="1898"))))

    assert built.price == Decimal("94900")
    assert built.derived is Amount.PRICE


def test_price_and_total_give_the_quantity() -> None:
    built = record_of(check(complete(**amounts(price="94900", total="1898"))))

    assert built.quantity == Decimal("0.02")
    assert built.derived is Amount.QUANTITY


@pytest.mark.parametrize(
    ("total", "price", "quantity"),
    [
        ("100", "3", "33.33333333"),
        ("2", "3", "0.66666667"),
        ("100", "94900", "0.00105374"),
    ],
)
def test_quotient_that_does_not_come_out_even_is_rounded_half_up_to_eight_places(
    total: str, price: str, quantity: str
) -> None:
    built = record_of(check(complete(**amounts(price=price, total=total))))

    assert written(built.quantity) == quantity
    assert built.derived is Amount.QUANTITY
    assert (built.price, built.total) == (Decimal(price), Decimal(total))


def test_price_that_does_not_come_out_even_is_rounded_the_same_way() -> None:
    built = record_of(check(complete(**amounts(quantity="3", total="100"))))

    assert written(built.price) == "33.33333333"
    assert built.derived is Amount.PRICE


def test_number_of_places_for_a_rounded_quotient_can_be_set() -> None:
    settings = CheckSettings(derived_places=4)

    built = record_of(check(complete(**amounts(price="3", total="100")), settings=settings))

    assert written(built.quantity) == "33.3333"


def test_quotient_that_comes_out_even_is_kept_whole_even_past_the_usual_places() -> None:
    built = record_of(check(complete(**amounts(price="1024", total="1"))))

    assert written(built.quantity) == "0.0009765625"


def test_quotient_that_comes_out_even_but_too_long_for_the_ledger_is_rounded() -> None:
    # One over two to the twentieth is exact at twenty decimal places, two
    # more than the ledger holds.
    built = record_of(check(complete(**amounts(price="1048576", total="1"))))

    assert written(built.quantity) == "0.00000095"


@pytest.mark.parametrize(
    ("quantity", "price", "total"),
    [
        ("0.000000001", "0.0000000005", "0.000000000000000001"),
        ("2.5", "0.000000000000000001", "0.000000000000000003"),
        ("1.123456789", "1.1234567891", "1.262155156862536200"),
    ],
)
def test_product_with_too_many_decimal_places_is_rounded_half_up_to_the_ledger_s_limit(
    quantity: str, price: str, total: str
) -> None:
    built = record_of(check(complete(**amounts(quantity=quantity, price=price))))

    assert built.total == Decimal(total)
    assert built.derived is Amount.TOTAL


@pytest.mark.parametrize(
    ("stated", "derived", "expected"),
    [
        (amounts(quantity="0.020", price="94900"), Amount.TOTAL, "1898"),
        (amounts(price="0.00000001", total="100"), Amount.QUANTITY, "10000000000"),
        (amounts(quantity="2.50", total="10.00"), Amount.PRICE, "4"),
    ],
)
def test_calculated_amount_is_written_plainly(
    stated: dict[str, Decimal | None], derived: Amount, expected: str
) -> None:
    built = record_of(check(complete(**stated)))

    assert built.derived is derived
    assert written(amount_of(built, derived)) == expected


def test_stated_amounts_are_kept_exactly_as_they_were_given() -> None:
    built = record_of(check(complete(**amounts(quantity="0.020", price="94900.0"))))

    assert (written(built.quantity), written(built.price)) == ("0.020", "94900.0")


@pytest.mark.parametrize(
    "stated",
    [amounts(quantity="0.02"), amounts(price="94900"), amounts(total="1898")],
)
def test_one_amount_alone_asks_for_one_more(stated: dict[str, Decimal | None]) -> None:
    problems = problems_of(check(complete(**stated)))

    assert problems == DraftProblems(
        missing=(Missing.ONE_MORE_OF_QUANTITY_PRICE_TOTAL,), violations=()
    )


def test_no_amount_at_all_asks_for_two() -> None:
    problems = problems_of(check(complete(**amounts())))

    assert problems == DraftProblems(missing=(Missing.TWO_OF_QUANTITY_PRICE_TOTAL,), violations=())


def test_amount_the_program_calculated_earlier_is_worked_out_again() -> None:
    stale = complete(**amounts(quantity="0.02", price="94900", total="5"))
    stale = dataclasses.replace(stale, derived=frozenset({Amount.TOTAL}))

    built = record_of(check(stale))

    assert built.total == Decimal("1898")
    assert built.derived is Amount.TOTAL


def test_amounts_the_program_calculated_do_not_count_as_stated() -> None:
    draft = complete(**amounts(quantity="0.02", price="94900", total="1898"))
    draft = dataclasses.replace(draft, derived=frozenset({Amount.PRICE, Amount.TOTAL}))

    assert missing(draft) == (Missing.ONE_MORE_OF_QUANTITY_PRICE_TOTAL,)


# --- all three stated: they must agree --------------------------------------


@pytest.mark.parametrize("total", ["1898", "1898.005", "1897.995", "1898.01", "1897.99"])
def test_three_amounts_within_the_tolerance_pass_and_are_kept_as_stated(total: str) -> None:
    built = record_of(check(complete(**amounts(quantity="0.02", price="94900", total=total))))

    assert (written(built.quantity), written(built.price), written(built.total)) == (
        "0.02",
        "94900",
        total,
    )
    assert built.derived is None


@pytest.mark.parametrize(
    "total", ["1900", "1898.02", "1897.98", "1898.010000000000000001", "18.98"]
)
def test_three_amounts_beyond_the_tolerance_disagree(total: str) -> None:
    problems = problems_of(check(complete(**amounts(quantity="0.02", price="94900", total=total))))

    assert problems == DraftProblems(missing=(), violations=(Violation.AMOUNTS_DISAGREE,))


def test_tolerance_can_be_tightened() -> None:
    exact_only = CheckSettings(total_tolerance=Decimal("0"))
    close = complete(**amounts(quantity="0.02", price="94900", total="1898.005"))
    exact = complete(**amounts(quantity="0.02", price="94900", total="1898"))

    assert violations(close, settings=exact_only) == (Violation.AMOUNTS_DISAGREE,)
    assert record_of(check(exact, settings=exact_only)).derived is None


def test_amounts_the_ledger_s_own_arithmetic_would_refuse_are_refused() -> None:
    # Exactly 0.01 apart when multiplied out in full. The ledger keeps only 40
    # significant digits of the product, which here rounds it a hair further
    # away from the total, so the ledger itself would turn this trade down.
    quantity = "5"
    price = "2000000000000000000000.001000000000000001"
    total = "9999999999999999999999.995000000000000005"
    assert Fraction(quantity) * Fraction(price) - Fraction(total) == Fraction(1, 100)

    stated = amounts(quantity=quantity, price=price, total=total)

    assert violations(complete(**stated)) == (Violation.AMOUNTS_DISAGREE,)


# --- a calculated amount must still make a sound trade ----------------------


def test_rounded_quotient_that_no_longer_matches_the_total_disagrees() -> None:
    stated = amounts(price="30000000", total="1")

    assert violations(complete(**stated)) == (Violation.AMOUNTS_DISAGREE,)


def test_more_places_for_the_quotient_can_make_it_match_again() -> None:
    settings = CheckSettings(derived_places=18)

    built = record_of(check(complete(**amounts(price="30000000", total="1")), settings=settings))

    assert written(built.quantity) == "0.000000033333333333"


def test_calculated_amount_that_rounds_to_nothing_is_not_positive() -> None:
    stated = amounts(price="94900", total="0.000000001")

    assert violations(complete(**stated)) == (Violation.QUANTITY_NOT_POSITIVE,)


def test_calculated_total_too_large_for_the_ledger_has_too_many_digits() -> None:
    stated = amounts(quantity="9" * 40, price="10")

    assert violations(complete(**stated)) == (Violation.TOTAL_TOO_MANY_DIGITS,)


# --- signs ------------------------------------------------------------------


@pytest.mark.parametrize("value", ["0", "-1", "-0.02", "0.000"])
@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("quantity", Violation.QUANTITY_NOT_POSITIVE),
        ("price", Violation.PRICE_NOT_POSITIVE),
        ("total", Violation.TOTAL_NOT_POSITIVE),
    ],
)
def test_amount_that_is_not_above_zero_is_a_violation(
    field: str, expected: Violation, value: str
) -> None:
    stated = {**amounts(quantity="0.02", price="94900", total="1898"), field: Decimal(value)}

    assert violations(complete(**stated)) == (expected,)


@pytest.mark.parametrize("fee", ["-0.01", "-2"])
def test_fee_below_zero_is_a_violation(fee: str) -> None:
    problems = problems_of(check(complete(fee=Decimal(fee))))

    assert problems == DraftProblems(missing=(), violations=(Violation.FEE_NEGATIVE,))


# --- digits: a stated number is never silently rounded ----------------------

NINETEEN_PLACES = "0.0200000000000000001"
FORTY_ONE_DIGITS = "1" * 41


@pytest.mark.parametrize("value", [NINETEEN_PLACES, FORTY_ONE_DIGITS, "1" * 23 + "." + "1" * 18])
@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("quantity", Violation.QUANTITY_TOO_MANY_DIGITS),
        ("price", Violation.PRICE_TOO_MANY_DIGITS),
        ("total", Violation.TOTAL_TOO_MANY_DIGITS),
    ],
)
def test_stated_amount_with_too_many_digits_is_a_violation_and_nothing_else(
    field: str, expected: Violation, value: str
) -> None:
    stated = {**amounts(quantity="0.02", price="94900", total="1898"), field: Decimal(value)}

    assert check(complete(**stated)) == DraftProblems(missing=(), violations=(expected,))


@pytest.mark.parametrize("fee", ["0.0000000000000000001", FORTY_ONE_DIGITS])
def test_fee_with_too_many_digits_is_a_violation(fee: str) -> None:
    assert violations(complete(fee=Decimal(fee))) == (Violation.FEE_TOO_MANY_DIGITS,)


def test_numbers_right_at_the_digit_limits_pass() -> None:
    quantity = "0.000000000000000001"
    price = "1" + "0" * 39

    built = record_of(
        check(
            complete(**amounts(quantity=quantity, price=price), fee=Decimal("0." + "0" * 17 + "1"))
        )
    )

    assert built.total == Decimal("1" + "0" * 21)


def test_amount_with_too_many_digits_is_not_used_to_calculate_another() -> None:
    stated = amounts(quantity=NINETEEN_PLACES, price="94900")

    assert check(complete(**stated)) == DraftProblems(
        missing=(), violations=(Violation.QUANTITY_TOO_MANY_DIGITS,)
    )


# --- the fee ----------------------------------------------------------------


def test_fee_that_was_never_stated_is_missing_even_when_its_coin_was() -> None:
    assert missing(complete(fee=None, fee_coin="USDT")) == (Missing.FEE,)


@pytest.mark.parametrize("fee", ["0", "0.00", "-0"])
@pytest.mark.parametrize("fee_coin", [None, "", "USDT", "BTC", "NOSUCHCOIN", "某某币"])
def test_fee_of_zero_passes_and_is_recorded_in_usdt_whatever_coin_was_said(
    fee: str, fee_coin: str | None
) -> None:
    built = record_of(check(complete(fee=Decimal(fee), fee_coin=fee_coin)))

    assert built.fee.is_zero()
    assert not built.fee.is_signed()
    assert built.fee_coin == "USDT"


@pytest.mark.parametrize("fee_coin", [None, "", "  "])
def test_fee_above_zero_without_its_coin_asks_for_the_coin(fee_coin: str | None) -> None:
    problems = problems_of(check(complete(fee=Decimal("2"), fee_coin=fee_coin)))

    assert problems == DraftProblems(missing=(Missing.FEE_COIN,), violations=())


@pytest.mark.parametrize("fee_coin", ["BTC", "btc", "比特币"])
def test_fee_paid_in_the_traded_coin_passes(fee_coin: str) -> None:
    built = record_of(check(complete(fee=Decimal("0.0001"), fee_coin=fee_coin)))

    assert (built.fee, built.fee_coin) == (Decimal("0.0001"), "BTC")


@pytest.mark.parametrize("fee_coin", ["USDT", "usdt", "U", "刀", "美元", "$"])
def test_fee_paid_in_any_word_for_usdt_is_recorded_in_usdt(fee_coin: str) -> None:
    assert record_of(check(complete(fee_coin=fee_coin))).fee_coin == "USDT"


def test_fee_paid_in_another_known_coin_passes() -> None:
    built = record_of(check(complete(fee=Decimal("0.003"), fee_coin="bnb")))

    assert built.fee_coin == "BNB"


def test_fee_paid_in_an_unseen_coin_needs_that_coin_confirmed() -> None:
    draft = complete(fee=Decimal("3"), fee_coin="feecoin")

    assert check(draft) == DraftProblems(missing=(Missing.FEE_COIN_CONFIRMATION,), violations=())
    assert record_of(check(draft, BUILT_IN_TABLE.with_confirmed("FEECOIN"))).fee_coin == "FEECOIN"


@pytest.mark.parametrize("fee_coin", ["某某币", "FEE-COIN", "X" * 33])
def test_fee_coin_that_cannot_be_a_symbol_is_a_violation(fee_coin: str) -> None:
    problems = problems_of(check(complete(fee_coin=fee_coin)))

    assert problems == DraftProblems(missing=(), violations=(Violation.FEE_COIN_NOT_A_SYMBOL,))


def test_fee_in_the_same_unseen_coin_as_the_trade_asks_for_one_confirmation() -> None:
    draft = complete(coin="newcoin", quantity=Decimal("500"), fee=Decimal("1"), fee_coin="NEWCOIN")

    assert check(draft) == DraftProblems(missing=(Missing.COIN_CONFIRMATION,), violations=())
    built = record_of(check(draft, BUILT_IN_TABLE.with_confirmed("newcoin")))
    assert (built.coin, built.fee_coin) == ("NEWCOIN", "NEWCOIN")


# --- a fee paid in the coin being bought ------------------------------------


@pytest.mark.parametrize("fee", ["0.02", "0.03", "5"])
def test_buy_fee_in_the_bought_coin_must_be_below_the_quantity(fee: str) -> None:
    draft = complete(quantity=Decimal("0.02"), fee=Decimal(fee), fee_coin="BTC")

    assert check(draft) == DraftProblems(missing=(), violations=(Violation.FEE_NOT_BELOW_QUANTITY,))


def test_buy_fee_in_the_bought_coin_just_below_the_quantity_passes() -> None:
    draft = complete(quantity=Decimal("0.02"), fee=Decimal("0.019999"), fee_coin="BTC")

    assert record_of(check(draft)).fee == Decimal("0.019999")


def test_fee_is_compared_with_a_quantity_the_program_calculated() -> None:
    stated = amounts(price="94900", total="1898")

    draft = complete(**stated, fee=Decimal("0.02"), fee_coin="BTC")

    assert violations(draft) == (Violation.FEE_NOT_BELOW_QUANTITY,)


def test_sell_fee_in_the_sold_coin_may_reach_the_quantity() -> None:
    draft = complete(side=Side.SELL, quantity=Decimal("0.02"), fee=Decimal("0.02"), fee_coin="BTC")

    assert record_of(check(draft)).fee_coin == "BTC"


@pytest.mark.parametrize("fee_coin", ["USDT", "BNB"])
def test_buy_fee_in_some_other_coin_may_exceed_the_quantity(fee_coin: str) -> None:
    draft = complete(quantity=Decimal("0.02"), fee=Decimal("5"), fee_coin=fee_coin)

    assert record_of(check(draft)).fee == Decimal("5")


# --- the coin ---------------------------------------------------------------


@pytest.mark.parametrize(("spoken", "symbol"), [("PEPE2", "PEPE2"), (" pepe2 ", "PEPE2")])
def test_unseen_coin_needs_confirming_and_passes_once_confirmed(spoken: str, symbol: str) -> None:
    draft = complete(coin=spoken)

    assert check(draft) == DraftProblems(missing=(Missing.COIN_CONFIRMATION,), violations=())
    assert record_of(check(draft, BUILT_IN_TABLE.with_confirmed(spoken))).coin == symbol


@pytest.mark.parametrize("spoken", ["USDT", "usdt", "U", "刀", "美元"])
def test_usdt_cannot_be_the_coin_that_is_traded(spoken: str) -> None:
    problems = problems_of(check(complete(coin=spoken)))

    assert problems == DraftProblems(missing=(), violations=(Violation.COIN_IS_USDT,))


@pytest.mark.parametrize("spoken", ["某某币", "BT-C", "BTC/USDT", "X" * 33])
def test_coin_that_cannot_be_a_ledger_symbol_is_a_violation(spoken: str) -> None:
    problems = problems_of(check(complete(coin=spoken)))

    assert problems == DraftProblems(missing=(), violations=(Violation.COIN_NOT_A_SYMBOL,))


# --- the pricing currency ---------------------------------------------------


@pytest.mark.parametrize("quote", [None, "", "USDT", "usdt", "U", "刀", "美元", "美金", "$", "USD"])
def test_no_quote_word_or_a_word_for_usdt_passes(quote: str | None) -> None:
    assert isinstance(check(complete(quote=quote)), TradeRecord)


@pytest.mark.parametrize("quote", ["BTC", "ETH", "USDC", "CNY", "EUR", "元", "块", "人民币"])
def test_any_other_quote_word_is_not_supported(quote: str) -> None:
    problems = problems_of(check(complete(quote=quote)))

    assert problems == DraftProblems(missing=(), violations=(Violation.UNSUPPORTED_QUOTE,))


# --- the time: nothing from the future --------------------------------------


@pytest.mark.parametrize("occurred", [at(9, 40), at(11, 59, 59), at(12, 0), at(0, 0)])
def test_moment_up_to_now_passes(occurred: OccurredTime) -> None:
    assert record_of(check(complete(occurred=occurred))).occurred == occurred


@pytest.mark.parametrize("occurred", [at(12, 0, 30), at(12, 1)])
def test_moment_within_the_grace_after_now_passes(occurred: OccurredTime) -> None:
    assert isinstance(check(complete(occurred=occurred)), TradeRecord)


@pytest.mark.parametrize("occurred", [at(12, 1, 1), at(12, 2), at(23, 59)])
def test_moment_beyond_the_grace_is_in_the_future(occurred: OccurredTime) -> None:
    problems = problems_of(check(complete(occurred=occurred)))

    assert problems == DraftProblems(missing=(), violations=(Violation.IN_THE_FUTURE,))


def test_grace_can_be_set() -> None:
    none_at_all = CheckSettings(future_grace=timedelta(0))
    ten_minutes = CheckSettings(future_grace=timedelta(minutes=10))

    assert violations(complete(occurred=at(12, 0, 1)), settings=none_at_all) == (
        Violation.IN_THE_FUTURE,
    )
    assert isinstance(check(complete(occurred=at(12, 0)), settings=none_at_all), TradeRecord)
    assert isinstance(check(complete(occurred=at(12, 10)), settings=ten_minutes), TradeRecord)
    assert violations(complete(occurred=at(12, 11)), settings=ten_minutes) == (
        Violation.IN_THE_FUTURE,
    )


@pytest.mark.parametrize("day", [date(2026, 10, 4), date(2026, 10, 3), date(2020, 1, 1)])
def test_day_up_to_today_passes(day: date) -> None:
    assert isinstance(check(complete(occurred=on(day))), TradeRecord)


def test_day_after_today_is_in_the_future_whatever_the_grace() -> None:
    generous = CheckSettings(future_grace=timedelta(days=3))
    tomorrow = complete(occurred=on(date(2026, 10, 5)))

    assert violations(tomorrow) == (Violation.IN_THE_FUTURE,)
    assert violations(tomorrow, settings=generous) == (Violation.IN_THE_FUTURE,)


def test_today_is_the_date_in_the_zone_of_the_trade() -> None:
    late_evening = datetime(2026, 10, 4, 23, 30, tzinfo=ZoneInfo(BUDAPEST))
    fifth = date(2026, 10, 5)

    assert violations(complete(occurred=on(fifth)), now=late_evening) == (Violation.IN_THE_FUTURE,)
    assert isinstance(
        check(complete(occurred=on(fifth, zone=SHANGHAI)), now=late_evening), TradeRecord
    )


def test_moments_are_compared_as_instants_not_as_wall_clock_readings() -> None:
    earlier_instant = at(17, 30, zone=SHANGHAI)
    later_instant = at(18, 30, zone=SHANGHAI)

    assert isinstance(check(complete(occurred=earlier_instant)), TradeRecord)
    assert violations(complete(occurred=later_instant)) == (Violation.IN_THE_FUTURE,)


def test_the_hour_that_repeats_is_told_apart_by_its_offset() -> None:
    zone = ZoneInfo(BUDAPEST)
    first_reading = datetime(2026, 10, 25, 2, 30, tzinfo=zone, fold=0)
    second_reading = datetime(2026, 10, 25, 2, 30, tzinfo=zone, fold=1)
    between = datetime(2026, 10, 25, 2, 45, tzinfo=zone, fold=0)

    past = complete(occurred=OccurredTime(first_reading, TimePrecision.MINUTE, BUDAPEST))
    ahead = complete(occurred=OccurredTime(second_reading, TimePrecision.MINUTE, BUDAPEST))

    assert isinstance(check(past, now=between), TradeRecord)
    assert violations(ahead, now=between) == (Violation.IN_THE_FUTURE,)


def test_now_given_in_utc_works_the_same() -> None:
    now_utc = NOW.astimezone(timezone.utc)

    assert isinstance(check(complete(occurred=at(12, 1)), now=now_utc), TradeRecord)
    assert violations(complete(occurred=at(12, 2)), now=now_utc) == (Violation.IN_THE_FUTURE,)


def test_now_without_an_offset_is_a_mistake_by_the_caller() -> None:
    with pytest.raises(ValueError, match="offset"):
        check(complete(), now=datetime(2026, 10, 4, 12, 0))


# --- free text --------------------------------------------------------------


@pytest.mark.parametrize("raw_text", ["", "   ", "\n\t", "\N{IDEOGRAPHIC SPACE}"])
def test_original_text_with_nothing_in_it_is_a_violation(raw_text: str) -> None:
    problems = problems_of(check(complete(raw_text=raw_text)))

    assert problems == DraftProblems(missing=(), violations=(Violation.RAW_TEXT_EMPTY,))


@pytest.mark.parametrize(
    ("field", "limit", "expected"),
    [
        ("raw_text", 16_384, Violation.RAW_TEXT_TOO_LONG),
        ("note", 4_096, Violation.NOTE_TOO_LONG),
        ("platform", 128, Violation.PLATFORM_TOO_LONG),
    ],
)
def test_text_may_reach_its_limit_but_not_pass_it(
    field: str, limit: int, expected: Violation
) -> None:
    at_limit = complete(**{field: "x" * limit})
    one_over = complete(**{field: "x" * (limit + 1)})

    assert getattr(record_of(check(at_limit)), field) == "x" * limit
    assert check(one_over) == DraftProblems(missing=(), violations=(expected,))


@pytest.mark.parametrize(
    ("field", "limit", "expected"),
    [
        ("raw_text", 16_384, Violation.RAW_TEXT_TOO_LONG),
        ("note", 4_096, Violation.NOTE_TOO_LONG),
        ("platform", 128, Violation.PLATFORM_TOO_LONG),
    ],
)
def test_emoji_counts_as_two_toward_the_limit_as_it_does_in_the_ledger(
    field: str, limit: int, expected: Violation
) -> None:
    fits = "x" * (limit - 2) + GRINNING_FACE
    one_over = "x" * (limit - 1) + GRINNING_FACE

    assert len(one_over) == limit
    assert getattr(record_of(check(complete(**{field: fits}))), field) == fits
    assert check(complete(**{field: one_over})) == DraftProblems(missing=(), violations=(expected,))


@pytest.mark.parametrize(
    ("platform", "recorded"),
    [
        ("  OKX ", "OKX"),
        ("\tBinance\n", "Binance"),
        ("\N{IDEOGRAPHIC SPACE}币安\N{IDEOGRAPHIC SPACE}", "币安"),
        ("Gate io", "Gate io"),
        (" " + "p" * 128 + " ", "p" * 128),
    ],
)
def test_platform_is_recorded_without_surrounding_whitespace(platform: str, recorded: str) -> None:
    assert record_of(check(complete(platform=platform))).platform == recorded


@pytest.mark.parametrize("platform", ["", "   ", "\t\n", "\N{IDEOGRAPHIC SPACE}"])
def test_platform_made_of_whitespace_counts_as_not_given(platform: str) -> None:
    assert record_of(check(complete(platform=platform))).platform is None


# --- several problems at once -----------------------------------------------


def test_two_violations_in_one_draft_are_both_reported() -> None:
    draft = complete(price=Decimal("-94900"), occurred=at(18, 0))

    assert check(draft) == DraftProblems(
        missing=(), violations=(Violation.PRICE_NOT_POSITIVE, Violation.IN_THE_FUTURE)
    )


def test_missing_fields_and_violations_are_reported_together() -> None:
    draft = complete(
        coin="pepe2", fee=None, price=Decimal("-94900"), occurred=at(18, 0), quote="CNY"
    )

    assert check(draft) == DraftProblems(
        missing=(Missing.COIN_CONFIRMATION, Missing.FEE),
        violations=(
            Violation.UNSUPPORTED_QUOTE,
            Violation.PRICE_NOT_POSITIVE,
            Violation.IN_THE_FUTURE,
        ),
    )


def test_draft_wrong_in_every_way_reports_every_problem_in_the_fixed_order() -> None:
    draft = TradeDraft(
        coin="某某币",
        quantity=Decimal("-1"),
        quote="块",
        fee=Decimal("-0.0000000000000000001"),
        occurred=on(date(2026, 10, 5)),
        platform="p" * 129,
        note="n" * 4097,
        raw_text="",
    )

    assert check(draft) == DraftProblems(
        missing=(Missing.SIDE, Missing.ONE_MORE_OF_QUANTITY_PRICE_TOTAL),
        violations=(
            Violation.COIN_NOT_A_SYMBOL,
            Violation.UNSUPPORTED_QUOTE,
            Violation.QUANTITY_NOT_POSITIVE,
            Violation.FEE_NEGATIVE,
            Violation.FEE_TOO_MANY_DIGITS,
            Violation.IN_THE_FUTURE,
            Violation.PLATFORM_TOO_LONG,
            Violation.NOTE_TOO_LONG,
            Violation.RAW_TEXT_EMPTY,
        ),
    )


def test_order_of_the_lists_does_not_depend_on_the_order_problems_were_found_in() -> None:
    # The quantity is looked at before the price, yet the price's problem is
    # written earlier in the enumeration and so comes first.
    stated = amounts(quantity=NINETEEN_PLACES, price="-94900")

    assert violations(complete(**stated)) == (
        Violation.PRICE_NOT_POSITIVE,
        Violation.QUANTITY_TOO_MANY_DIGITS,
    )


def test_problems_are_listed_in_the_order_the_enumerations_are_written() -> None:
    assert [item.name for item in Missing] == [
        "SIDE",
        "COIN",
        "COIN_CONFIRMATION",
        "TWO_OF_QUANTITY_PRICE_TOTAL",
        "ONE_MORE_OF_QUANTITY_PRICE_TOTAL",
        "FEE",
        "FEE_COIN",
        "FEE_COIN_CONFIRMATION",
        "OCCURRED",
        "RAW_TEXT",
    ]
    assert [item.name for item in Violation] == [
        "COIN_IS_USDT",
        "COIN_NOT_A_SYMBOL",
        "UNSUPPORTED_QUOTE",
        "QUANTITY_NOT_POSITIVE",
        "PRICE_NOT_POSITIVE",
        "TOTAL_NOT_POSITIVE",
        "QUANTITY_TOO_MANY_DIGITS",
        "PRICE_TOO_MANY_DIGITS",
        "TOTAL_TOO_MANY_DIGITS",
        "AMOUNTS_DISAGREE",
        "FEE_NEGATIVE",
        "FEE_TOO_MANY_DIGITS",
        "FEE_COIN_NOT_A_SYMBOL",
        "FEE_NOT_BELOW_QUANTITY",
        "IN_THE_FUTURE",
        "PLATFORM_TOO_LONG",
        "NOTE_TOO_LONG",
        "RAW_TEXT_EMPTY",
        "RAW_TEXT_TOO_LONG",
    ]


def test_checking_a_draft_leaves_it_as_it_was() -> None:
    draft = complete(platform="  OKX ")
    before = dataclasses.asdict(draft)

    check(draft)

    assert dataclasses.asdict(draft) == before


# --- the adjustable settings ------------------------------------------------


def test_default_settings_are_the_named_defaults() -> None:
    assert DEFAULT_DERIVED_PLACES == 8
    assert timedelta(minutes=1) == DEFAULT_FUTURE_GRACE
    assert CheckSettings() == DEFAULT_SETTINGS
    assert (
        DEFAULT_SETTINGS.derived_places,
        DEFAULT_SETTINGS.total_tolerance,
        DEFAULT_SETTINGS.future_grace,
    ) == (8, Decimal("0.01"), timedelta(minutes=1))


@pytest.mark.parametrize("places", [-1, 19, 100])
def test_places_outside_what_the_ledger_can_hold_are_refused(places: int) -> None:
    with pytest.raises(ValueError, match="derived_places"):
        CheckSettings(derived_places=places)


@pytest.mark.parametrize("places", [0, 18])
def test_places_at_either_end_of_the_range_are_accepted(places: int) -> None:
    assert CheckSettings(derived_places=places).derived_places == places


@pytest.mark.parametrize("tolerance", ["-0.01", "0.02", "1", "NaN", "Infinity"])
def test_tolerance_looser_than_the_ledger_s_or_not_a_number_is_refused(tolerance: str) -> None:
    with pytest.raises(ValueError, match="total_tolerance"):
        CheckSettings(total_tolerance=Decimal(tolerance))


def test_grace_below_zero_is_refused() -> None:
    with pytest.raises(ValueError, match="future_grace"):
        CheckSettings(future_grace=timedelta(seconds=-1))
