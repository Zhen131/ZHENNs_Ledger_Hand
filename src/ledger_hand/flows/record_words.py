"""The program's own words to the user once the assistant has recorded what was said.

When the assistant records a trade, the program, not the model, tells the
user how it went: one sentence for every way it can end
(``ENDING_WORDS``, one for each ``RecordEnding``) and one for every reason
a trade was not sent (``LEFT_OUT_WORDS``, one for each ``LeftOut``). A test
walks both enumerations, so a new ending or reason cannot go without a
sentence. They live here, not in the interface, because the try-out script
says them too.

``reply_for`` puts the words together: for a question, the flow's whole
question (its label and sentence, why it is asked again when it is, the
answers to choose from and its notes, one to a line); for an
ending, its sentence, filled in with what the flow or the ledger gave as
the reason, then one line for each trade not sent, for each that waits in
the ledger when only part was taken, and for each turned down. When a
proposal was sent, turned down by the ledger or nothing was sent, one line
follows for each reminder of extraction whose kind is on
``SPOKEN_REMINDERS``, in the Record page's words (``reminder_words``); no
other ending says them. The reminder that held a trade back is not said
again: the line about that trade says it. The figures of a trade are
never in these words, the table of what was sent carries them, laid out
by the caller from the proposal itself; the one exception is a quantity
said in another unit, said back as the number read and its unit.

``spoken_reminders`` gives the reminders said, as they are, so that a
caller that keeps them (the assistant's record) keeps the same ones.

Each asset the model picked from the ledger's list for a name the program
did not know is said in one line (``PICKED_WORDS``): the words said, the
code, the ledger's name for it, and that the model matched it. It is said
in the reply that begins the recording (``begun``) and in the one that
ends it, once when they are the same reply; not in the replies between.

Each trade sent whose money the program guessed from the ledger's last
trade of its asset (``TradeRecord.inferred``) gets one line right after
the ending's sentence (``GUESSED_WORDS``): which money, from which asset's
last trade, and that it is a guess to check. The words are fixed here,
never the model's. (Decided on 2026-11-25.)

Each trade sent whose price was compared with the ledger's market price
and found far from it, or could not be compared, gets one line after
those (``PRICE_WORDS``, one for each ``PriceVerdict``, ``None`` where
nothing is said): far says the price, the market price with its day, how
many times apart and which way, and that it is marked suspicious; not
compared says why. A price within reach, or an asset with no market
price, is not spoken of. (Decided on 2026-11-25.)

A trade sent as a card with cells left empty (the ledger takes such a
card since 2026-11-25) gets one line saying which cells are empty and to
fill them in on the ledger's page before saving (``EMPTY_WORDS``). When
the ledger found a problem in the cells given, its own sentence is said
as it came (``LEDGER_PROBLEM_WORDS``); when it found none while the day,
an amount or the money used is empty, it is never said to have found
nothing: it could not check those (``NOT_CHECKED_YET_WORDS``), and of a
sell, whether enough was held (``SELL_NOT_CHECKED_WORDS``). Three
amounts that do not agree are said with the three figures, the total
left empty, and that the program does not guess which is wrong
(``DISAGREE_WORDS``); each other cell left empty for being wrong, or
marked suspicious for it, is said with its reason (``DOUBT_WORDS``).
(The product owner's rule, 81A section 2 item 1; decided 2026-11-25.)

``price_check_words`` says what came of the comparison in a few words,
for every outcome, and ``not_checked_words`` why a price was not compared
at all, for the try-out script and the line under a trade's card: a card
carries no mark when nothing was compared, and the user should not take
it as checked.

Names defined here: ``ENDING_WORDS``, ``LEFT_OUT_WORDS``,
``SPOKEN_REMINDERS``, ``PICKED_WORDS``, ``GUESSED_WORDS``, ``PRICE_WORDS``,
``NOT_CHECKED_WORDS``, ``EMPTY_WORDS``, ``LEDGER_PROBLEM_WORDS``,
``NOT_CHECKED_YET_WORDS``, ``SELL_NOT_CHECKED_WORDS``, ``DISAGREE_WORDS``,
``DOUBT_WORDS``, ``reply_for``, ``price_line``, ``price_check_words``,
``not_checked_words`` and ``spoken_reminders``.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType

from ledger_hand.core.card_record import Doubt
from ledger_hand.core.marks import FAR_REASON_START
from ledger_hand.core.price_check import PriceCheck, PriceVerdict
from ledger_hand.core.proposals import CheckOutcome, TradeCheck
from ledger_hand.core.trade import Inferred, Side
from ledger_hand.core.trade_card import TradeCard
from ledger_hand.extraction.issues import Issue, IssueKind
from ledger_hand.flows.progress import REMINDER_KINDS
from ledger_hand.flows.recorded import LeftOut, LeftOutTrade, Recorded, RecordEnding
from ledger_hand.flows.reminder_words import reminder_text

ENDING_WORDS: Mapping[RecordEnding, str] = MappingProxyType(
    {
        RecordEnding.ASKING: "{question}",
        RecordEnding.SENT: (
            "Sent to the ledger. It waits there for you to confirm it on the ledger's own page."
        ),
        RecordEnding.PARTLY_SENT: (
            "Only part of this was sent: the ledger took some trades and turned the others "
            "down. Those it took wait there for you to confirm on the ledger's own page."
        ),
        RecordEnding.LEDGER_REFUSED: (
            "The ledger turned this down, so nothing waits there for you to confirm."
        ),
        RecordEnding.MAYBE_SENT: (
            "The ledger did not answer in time, so this may already be waiting there. "
            "Nothing was sent again. Please look at the ledger's pending list first."
        ),
        RecordEnding.NOTHING_TO_SEND: "Nothing was sent to the ledger.",
        RecordEnding.NO_PRICING_MONEY: (
            "Nothing was sent to the ledger: it has no currency that trades can be priced in. "
            "Please add one in the ledger first."
        ),
        RecordEnding.CANCELLED: "Dropped, as you said: nothing was sent to the ledger.",
        RecordEnding.STOPPED: (
            "Nothing was sent to the ledger: what you said reports only things the ledger "
            "does not record ({reason})."
        ),
        RecordEnding.NO_TRADE: (
            "Nothing was sent to the ledger: no trade was found in what you said."
        ),
        RecordEnding.REFUSED: (
            "Nothing was sent to the ledger: what you said was not read, because {reason}."
        ),
        RecordEnding.MODEL_FAILED: (
            "Nothing was sent to the ledger: the model failed while reading what you said "
            "({reason}). Please try again."
        ),
        RecordEnding.LEDGER_FAILED: (
            "Nothing was sent to the ledger: it could not be asked ({reason}). Please try again."
        ),
    }
)

LEFT_OUT_WORDS: Mapping[LeftOut, str] = MappingProxyType(
    {
        LeftOut.SKIPPED: "Trade {number} was left out, as you said.",
        LeftOut.CANNOT_RECORD: "Trade {number} was not sent: it cannot be recorded ({reason}).",
        LeftOut.DAY_ONLY: (
            "Trade {number} ({code}) was not sent: it has no time of day. Please say this "
            "trade again, with the time it was made."
        ),
        LeftOut.NOT_IN_LEDGER: (
            "Trade {number} was not sent: the ledger has no asset {code} yet. "
            "Please add it in the ledger first."
        ),
        LeftOut.MONEY_TRADED: (
            "Trade {number} was not sent: {code} is a currency in the ledger, and the "
            "assistant does not record an exchange of currencies. Please record it in the "
            "ledger itself."
        ),
        LeftOut.QUOTE_CANNOT_PRICE: (
            "Trade {number} was not sent: the ledger does not price trades in {code}."
        ),
        LeftOut.MONEY_NOT_IN_LEDGER: (
            "Trade {number} was not sent: the ledger has no currency {code} yet, so this "
            "trade cannot be recorded. Please add it in the ledger first."
        ),
        LeftOut.FEE_MONEY_NOT_IN_LEDGER: (
            "Trade {number} was not sent: its fee was taken in {code}, and the ledger has no "
            "currency {code} yet, so this trade cannot be recorded. Please add it in the "
            "ledger first."
        ),
        LeftOut.SAME_CODE: "Trade {number} was not sent: {reason}",
        LeftOut.QUANTITY_IN_OTHER_UNIT: (
            "Trade {number} was not sent: its quantity was said as {quantity} {unit}, and "
            "{unit} is not {asset}. If {quantity} {unit} is what you paid or got in all, "
            "please say the trade again with it as the total, for example "
            "'... for {quantity} {unit} in total'."
        ),
    }
)

# The line for an asset the model picked from the ledger's list: the user's
# words, the code and the ledger's name; the model matched it, so it is said.
PICKED_WORDS = (
    'Took "{said}" as {code} ({name}) from the ledger\'s list of assets. '
    "The model matched it, not the program, so please check it before you confirm."
)

# The line for a trade sent whose money was guessed from the ledger's last
# trade of its asset: one for the pricing money alone, one for it and the
# fee's, one for the fee's alone. "This is a guess" is in each.
GUESSED_WORDS: Mapping[frozenset[Inferred], str] = MappingProxyType(
    {
        frozenset({Inferred.QUOTE}): (
            "Trade {number}: no currency was said, so it is priced in {money}, the currency "
            "of the last {asset} trade in the ledger. This is a guess; check it before you "
            "confirm."
        ),
        frozenset({Inferred.QUOTE, Inferred.FEE_COIN}): (
            "Trade {number}: no currency was said, so it is priced in {money} and its fee is "
            "taken in {money}, the currency of the last {asset} trade in the ledger. This is a "
            "guess; check it before you confirm."
        ),
        frozenset({Inferred.FEE_COIN}): (
            "Trade {number}: no currency was said for the fee, so it is taken in {money}, the "
            "currency of the last {asset} trade in the ledger. This is a guess; check it "
            "before you confirm."
        ),
    }
)

# The line for a trade sent whose price was compared with the ledger's market
# price, or could not be; None where nothing is said. "far from the market
# price" and "not compared with the market price" are the words to look for.
PRICE_WORDS: Mapping[PriceVerdict, str | None] = MappingProxyType(
    {
        PriceVerdict.FAR: (
            "Trade {number}: the price {price} {money} is far from the market price of "
            "{asset} in the ledger, {market} {market_money}{day} (about {times} times "
            "{way}). It is marked suspicious; check it before you confirm."
        ),
        PriceVerdict.WITHIN: None,
        PriceVerdict.NO_MARKET_PRICE: None,
        PriceVerdict.OTHER_MONEY: (
            "Trade {number}: the price was not compared with the market price: the trade is "
            "in {money}, the ledger's market price of {asset} is in {market_money}, and the "
            "two are never taken as one money."
        ),
        PriceVerdict.NO_MONEY: (
            "Trade {number}: the price was not compared with the market price: the money "
            "it was paid in is not settled yet."
        ),
        PriceVerdict.NO_PRICE: None,
        PriceVerdict.NOT_ASKED: (
            "Trade {number}: the price was not compared with the market price: the ledger "
            "could not be asked for it ({failure})."
        ),
    }
)

# Why a price was not compared with the market price, in a few words; None
# for the two outcomes that were compared.
NOT_CHECKED_WORDS: Mapping[PriceVerdict, str | None] = MappingProxyType(
    {
        PriceVerdict.FAR: None,
        PriceVerdict.WITHIN: None,
        PriceVerdict.NO_MARKET_PRICE: "no market price in the ledger",
        PriceVerdict.OTHER_MONEY: (
            "the market price is in {market_money} and the trade in {money}, never taken as "
            "one money"
        ),
        PriceVerdict.NO_MONEY: "the money the trade used is not settled yet",
        PriceVerdict.NO_PRICE: None,
        PriceVerdict.NOT_ASKED: "the ledger could not be asked for its market prices ({failure})",
    }
)

# The line for a card sent with cells left empty; "with empty fields" is the
# word to look for. The cells are the ledger's own names for them.
EMPTY_WORDS = (
    "Trade {number} was sent with empty fields: {fields}. It waits on the ledger's pending "
    "list; fill them in on the ledger's own page before you save it."
)

# The line for what the ledger found in the cells given of a card, its own words.
LEDGER_PROBLEM_WORDS = "Trade {number}: the ledger says: {message}"

# The line for a card the ledger found nothing wrong with while some cell it
# would check is empty: never said as nothing found (72C1, 2026-11-25).
NOT_CHECKED_YET_WORDS = (
    "Trade {number}: the ledger cannot check it in full while {fields} are empty; it checks "
    "again when you save."
)

# Added for a sell: whether enough was held is checked only once it is filled in.
SELL_NOT_CHECKED_WORDS = (
    " Whether you held enough to sell can be checked only once they are filled in."
)

# The line for three amounts that do not agree: the three figures, what was left
# empty, and that the program does not guess which is wrong.
DISAGREE_WORDS = (
    "Trade {number}: you said {quantity} at {price} for a total of {total}, but quantity × "
    "price is {product}. The total was left empty and all three are marked suspicious; the "
    "program does not guess which is wrong."
)

# The line for any other cell marked suspicious for being wrong, with its reason.
DOUBT_WORDS = "Trade {number}: {field} is marked suspicious: {reason}."

# The cells whose emptiness keeps the ledger from checking a card in full:
# the day, the amounts and the money used (72C1, "the holdings cannot be checked").
_CHECKED_ONLY_WHEN_GIVEN = ("occurredDate", "quantity", "price", "totalValue", "quoteAssetId")

# The endings after which a guessed money is said: a trade waits, or may.
_SAYS_GUESSES = frozenset({RecordEnding.SENT, RecordEnding.PARTLY_SENT, RecordEnding.MAYBE_SENT})

# The kinds of reminder the assistant says once recording ends: every kind
# the Record page says, for now. Take a kind off this list to stop saying
# it, for example the numbers no trade used, which a share's "一股" raises.
SPOKEN_REMINDERS: frozenset[IssueKind] = REMINDER_KINDS

# The endings after which the reminders are said: a proposal was sent,
# the ledger turned it down, or nothing was sent.
_SAYS_REMINDERS = frozenset(
    {
        RecordEnding.SENT,
        RecordEnding.PARTLY_SENT,
        RecordEnding.LEDGER_REFUSED,
        RecordEnding.MAYBE_SENT,
        RecordEnding.NOTHING_TO_SEND,
    }
)


def reply_for(recorded: Recorded, *, begun: bool = False) -> str:
    """What the program tells the user about ``recorded``.

    ``begun`` says this is the reply that begins the recording; the assets
    picked from the ledger's list are said then, and once it ends.
    """
    first = ENDING_WORDS[recorded.ending].format(
        question=_question(recorded), code=recorded.missing_money or "", reason=_reason(recorded)
    )
    lines = [first, *_guessed(recorded), *_priced(recorded), *_cards(recorded)]
    if begun or recorded.ending is not RecordEnding.ASKING:
        lines.extend(_picked(recorded))
    lines.extend(_left_out(trade) for trade in recorded.left_out)
    lines.extend(_waiting(recorded))
    lines.extend(_turned_down(recorded))
    lines.extend(_reminders(recorded))
    return "\n".join(lines)


def _guessed(recorded: Recorded) -> list[str]:
    """One line for each trade sent whose money was guessed; none for a trade turned down."""
    if recorded.ending not in _SAYS_GUESSES:
        return []
    passed = (
        [check.outcome is CheckOutcome.PASSED for check in recorded.checks]
        if recorded.checks
        else [True] * len(recorded.numbers)
    )
    trades = recorded.progress.trades
    lines: list[str] = []
    for number, waits in zip(recorded.numbers, passed, strict=True):
        state = trades[number - 1]
        record = state.record if state.record is not None else state.card
        if not waits or record is None or record.inferred_from is None:
            continue
        source = record.inferred_from
        inferred = record.inferred
        if state.card is not None:
            # A guessed money sent empty is not said as used.
            sent = recorded.trades[recorded.numbers.index(number)]
            inferred = frozenset(
                one
                for one in inferred
                if (sent.quote if one is Inferred.QUOTE else sent.fee_asset) is not None
            )
        if inferred not in GUESSED_WORDS:
            continue
        lines.append(
            GUESSED_WORDS[inferred].format(number=number, money=source.money, asset=source.asset)
        )
    return lines


def _cards(recorded: Recorded) -> list[str]:
    """The lines for each card waiting: its empty cells, what the ledger found, its doubts."""
    lines: list[str] = []
    for place, number in _waiting_trades(recorded):
        card = recorded.trades[place]
        check = recorded.checks[place] if len(recorded.checks) == len(recorded.trades) else None
        lines.extend(_card_lines(recorded, number, card, check))
    return lines


def _card_lines(
    recorded: Recorded, number: int, card: TradeCard, check: TradeCheck | None
) -> list[str]:
    lines: list[str] = []
    state = recorded.progress.trades[number - 1]
    found = state.card
    if found is not None:
        doubts = [(mark, Doubt.of(mark.reason or "")) for mark in found.doubts]
        if any(doubt is Doubt.DISAGREE for _, doubt in doubts):
            draft = state.draft
            lines.append(
                _disagree_line(number, draft.quantity, draft.price, draft.total, found.quote)
            )
        for mark, doubt in doubts:
            reason = mark.reason or ""
            if doubt is Doubt.DISAGREE or reason.startswith(FAR_REASON_START):
                continue
            lines.append(DOUBT_WORDS.format(number=number, field=mark.field.value, reason=reason))
    if card.complete:
        return lines
    lines.append(EMPTY_WORDS.format(number=number, fields=", ".join(card.missing)))
    problem = check.problem if check is not None else None
    if problem is not None:
        lines.append(LEDGER_PROBLEM_WORDS.format(number=number, message=problem.message))
        return lines
    unchecked = [name for name in card.missing if name in _CHECKED_ONLY_WHEN_GIVEN]
    if unchecked:
        words = NOT_CHECKED_YET_WORDS.format(number=number, fields=", ".join(unchecked))
        if card.side is Side.SELL:
            words += SELL_NOT_CHECKED_WORDS
        lines.append(words)
    return lines


def _disagree_line(
    number: int,
    quantity: Decimal | None,
    price: Decimal | None,
    total: Decimal | None,
    quote: str | None,
) -> str:
    """The three figures said that do not agree, and quantity times price."""
    money = f" {quote}" if quote else ""

    def shown(value: Decimal | None, unit: str = "") -> str:
        return format(value, "f") + unit if value is not None else "none"

    product = quantity * price if quantity is not None and price is not None else None
    return DISAGREE_WORDS.format(
        number=number,
        quantity=shown(quantity),
        price=shown(price, money),
        total=shown(total, money),
        product=shown(product, money),
    )


def _waiting_trades(recorded: Recorded) -> list[tuple[int, int]]:
    """Each trade sent that waits in the ledger, or may: its place among those sent, its number."""
    if recorded.ending not in _SAYS_GUESSES:
        return []
    passed = (
        [check.outcome is CheckOutcome.PASSED for check in recorded.checks]
        if recorded.checks
        else [True] * len(recorded.numbers)
    )
    return [
        (place, number)
        for place, (number, waits) in enumerate(zip(recorded.numbers, passed, strict=True))
        if waits
    ]


def _priced(recorded: Recorded) -> list[str]:
    """One line for each trade waiting whose price was far, or was not compared."""
    if len(recorded.marked) != len(recorded.numbers):
        return []
    lines: list[str] = []
    for place, number in _waiting_trades(recorded):
        trade = recorded.trades[place]
        line = price_line(number, trade.asset, recorded.marked[place].price)
        if line is not None:
            lines.append(line)
    return lines


def price_line(number: int, asset: str, check: PriceCheck) -> str | None:
    """The line about trade ``number``'s price against the market price; ``None`` for none."""
    words = PRICE_WORDS[check.verdict]
    return None if words is None else words.format(**_price_fields(number, asset, check))


def _price_fields(number: int, asset: str, check: PriceCheck) -> dict[str, object]:
    """What the words about ``check`` are filled in with."""
    market = check.market
    return {
        "number": number,
        "asset": asset,
        "price": format(check.price, "f") if check.price is not None else "",
        "money": check.money or "",
        "market": format(market.price.amount, "f") if market is not None else "",
        "market_money": market.price.currency if market is not None else "",
        "day": f" on {market.day.isoformat()}" if market is not None and market.day else "",
        "times": format(check.times, "f") if check.times is not None else "",
        "way": "higher" if check.higher else "lower",
        "failure": check.failure or "",
    }


def not_checked_words(check: PriceCheck) -> str | None:
    """Why the price was not compared, in a few words; ``None`` when it was."""
    words = NOT_CHECKED_WORDS[check.verdict]
    return None if words is None else words.format(**_price_fields(0, "", check))


def price_check_words(check: PriceCheck) -> str:
    """What came of comparing the price, in a few words.

    Example: "far from the market price: 64880 USDT on 2026-11-24, about 68
    times lower"; "not compared: the ledger could not be asked ...".
    """
    if check.verdict.compared:
        start = "far from" if check.verdict is PriceVerdict.FAR else "within reach of"
        fields = _price_fields(0, "", check)
        return (
            f"{start} the market price: {fields['market']} {fields['market_money']}"
            f"{fields['day']}, about {fields['times']} times {fields['way']}"
        )
    if check.verdict is PriceVerdict.NO_MARKET_PRICE:
        return NOT_CHECKED_WORDS[check.verdict] or ""
    return f"not compared: {not_checked_words(check)}"


def _picked(recorded: Recorded) -> list[str]:
    """One line for each asset the model picked from the ledger's list."""
    progress = recorded.progress
    lines: list[str] = []
    for found in progress.picks:
        if found.code is None:
            continue
        coin = progress.setting.assets.find(found.code)
        name = coin.name if coin is not None else found.code
        said = (found.said or found.word).strip()
        lines.append(PICKED_WORDS.format(said=said, code=found.code, name=name))
    return lines


def _question(recorded: Recorded) -> str:
    question = recorded.question
    if question is None:
        return ""
    again = f"(Asked again: {question.again}) " if question.again is not None else ""
    return "\n".join((again + question.text, *question.choices, *question.notes))


def _reason(recorded: Recorded) -> str:
    progress = recorded.progress
    if recorded.failure is not None:
        return recorded.failure.message
    if recorded.ending is RecordEnding.STOPPED:
        return "; ".join(
            report.kind.value + (f": {report.evidence}" if report.evidence else "")
            for report in progress.stopped
        )
    if recorded.ending is RecordEnding.REFUSED and progress.refused is not None:
        return progress.refused.value
    failure = progress.failure
    if recorded.ending is RecordEnding.MODEL_FAILED and failure is not None:
        detail = str(failure.error) if failure.error is not None else ", ".join(failure.problems)
        return f"{failure.step.value}: {detail}"
    return ""


def _left_out(trade: LeftOutTrade) -> str:
    quantity = format(trade.quantity, "f") if trade.quantity is not None else ""
    return LEFT_OUT_WORDS[trade.why].format(
        number=trade.number,
        code=trade.code or "",
        reason=trade.reason or "",
        quantity=quantity,
        unit=trade.unit or "",
        asset=trade.code or "the asset traded",
    )


def _reminders(recorded: Recorded) -> list[str]:
    """One line for each reminder to say, once recording ended with a proposal or none."""
    ledger = recorded.progress.setting.assets.from_ledger
    return [
        f"Reminder: {reminder_text(issue, ledger=ledger)}" for issue in spoken_reminders(recorded)
    ]


def spoken_reminders(recorded: Recorded) -> tuple[Issue, ...]:
    """The reminders the reply for ``recorded`` says, in the order said; none for most endings."""
    if recorded.ending not in _SAYS_REMINDERS:
        return ()
    return tuple(
        issue
        for issue in recorded.progress.reminders
        if issue.kind in SPOKEN_REMINDERS and not _held_by(issue, recorded.left_out)
    )


def _held_by(issue: Issue, left_out: tuple[LeftOutTrade, ...]) -> bool:
    """Whether ``issue`` is the reminder that held a trade back, said in that trade's line."""
    return issue.kind is IssueKind.UNIT_NOT_THE_COIN and any(
        trade.why is LeftOut.QUANTITY_IN_OTHER_UNIT and issue.draft == trade.number - 1
        for trade in left_out
    )


def _waiting(recorded: Recorded) -> list[str]:
    """When only part was taken, one line for each trade that waits in the ledger."""
    if recorded.ending is not RecordEnding.PARTLY_SENT:
        return []
    return [
        f"Trade {number} waits in the ledger to be confirmed ({check.proposal_id})."
        for number, check in zip(recorded.numbers, recorded.checks, strict=True)
        if check.outcome is CheckOutcome.PASSED
    ]


def _turned_down(recorded: Recorded) -> list[str]:
    """One line for each trade the ledger's check turned down, with the ledger's sentence."""
    if not recorded.checks:
        return []
    return [
        f"Trade {number}: {check.message}"
        for number, check in zip(recorded.numbers, recorded.checks, strict=True)
        if check.outcome is CheckOutcome.FAILED
    ]
