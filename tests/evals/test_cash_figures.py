"""Tests of how the cash balances ruler judges a figure in the model's own words.

No real model is called. The six replies the independent check of
2026-11-26 wrote are each a figure made up (a cash balance, a holding
said as cash, one money's balance said as another's, money put in) and
must each be caught, whatever was looked up. The seventeen replies the
model really wrote in the first run, each after looking up the holdings
or the sums, say only the tables' figures and must each pass. Each
replay scripts the tool the model really asked for, against the demo
ledger with cash. Every figure is invented.
"""

from __future__ import annotations

import pytest

from evals.cash_balances_run import Sentence, judge
from evals.cash_figures import unfound
from ledger_hand.core.ledger_records import PeriodRequest, TradeFilter
from ledger_hand.flows.conversation import AssistantChat, Said, say
from ledger_hand.ledger.demo_cash import demo_ledger_with_cash
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import ToolCall, ToolReply
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import scripted_record


def calls(name: str, **arguments: str) -> ToolReply:
    return ToolReply(
        text="", calls=(ToolCall(name=name, arguments=arguments),), record=scripted_record()
    )


def words(text: str) -> ToolReply:
    return ToolReply(text=text, calls=(), record=scripted_record())


def replayed(text: str, call: ToolReply | None, reply: str) -> Said:
    tools = [call, words(reply)] if call is not None else [words(reply)]
    return say(
        AssistantChat(),
        text,
        model=RoutedModel(tools=tools),
        ledger=demo_ledger_with_cash().taking_cards(),
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
    )


def tables() -> list[object]:
    ledger = demo_ledger_with_cash()
    return [
        ledger.positions(),
        ledger.period_summary(PeriodRequest()),
        ledger.list_trades(TradeFilter()),
    ]


# The six replies of the check: (what was asked, the reply, the tables it had).
SIX = [
    ("我还有多少钱", "你账上还有 5000 USDT 现金。"),
    ("帮我看看账户", "你现在持有 1.0174765 个 BTC。你的现金余额是 5000 USDT。"),
    ("我还有多少钱", "你还有 1.0174765 USDT 的现金可用。"),
    ("我还剩多少美元", "你还剩 140080.19 美元现金。"),
    ("我这个月入了多少金", "你这个月入金了 3000 USDT。"),
    ("how much cash", "You have 2500 USD in cash."),
]


@pytest.mark.parametrize(("text", "reply"), SIX)
@pytest.mark.parametrize("cash_read", ["no", "yes"])
def test_each_made_up_figure_of_the_check_is_caught_whatever_was_looked_up(
    text: str, reply: str, cash_read: str
) -> None:
    cash = demo_ledger_with_cash().cash_balances() if cash_read == "yes" else None

    found = unfound(reply, tables=tables(), cash=cash, user_said=[text])

    assert found is not None


def test_a_cash_balance_of_the_money_named_passes_and_rounded_too() -> None:
    cash = demo_ledger_with_cash().cash_balances()

    assert unfound("你还剩 140080.19 USDT 现金。", tables=(), cash=cash, user_said=[]) is None
    assert unfound("You have 17093.94 USD in cash.", tables=(), cash=cash, user_said=[]) is None
    assert unfound("你还剩 17093.94 USDT 现金。", tables=(), cash=cash, user_said=[]) is not None


# The seventeen replies of the first run, with the tool the model asked for.
SUMMARY_OCTOBER = calls("get_period_summary", period="10月")
SUMMARY_ETH = calls("get_period_summary", period="今年", asset="ETH")
POSITIONS = calls("get_positions")
SEVENTEEN = [
    (
        "X5",
        "10月卖币一共收回了多少美元",
        SUMMARY_OCTOBER,
        "根据记录，您在10月卖出所有币共收回了920.32 USDT。其他币种的交易没有涉及卖出操作。",
    ),
    (
        "X6",
        "我现在还有多少BTC",
        POSITIONS,
        "您目前持有大约1.0174765个BTC。未实现利润为6919.59984044 USDT。",
    ),
    (
        "X7",
        "今年在ETH上赚了多少钱",
        SUMMARY_ETH,
        "根据提供的信息，在2026年您在ETH上的交易中，您总共花费了27,464.14 USDT购买ETH，"
        "从出售ETH中获得了523.6 USDT。您的手续费为0.00005 ETH和27.85104 USDT。计算下来，"
        "您在ETH上的净收益为5.48382781 USDT。\n\n"
        "因此，您在2026年通过ETH交易赚得了5.48382781 USDT。",
    ),
    (
        "X18",
        "What's my BTC balance?",
        POSITIONS,
        "You currently hold 1.0174765 BTC. The cost of this holding was 59,094.27547956 USDT, "
        "and as of now, it has an unrealized profit of 6,919.59984044 USDT.",
    ),
    (
        "X19",
        "比特币余额是多少",
        POSITIONS,
        "您目前持有的比特币（BTC）数量为1.0174765个。未实现利润为6919.59984044美元。",
    ),
    (
        "X21",
        "以太坊余额多少",
        POSITIONS,
        "根据最新的记录，您持有的以太坊（ETH）数量为10.41995个。请注意，这可能不是实时余额，"
        "因为这些数据是基于历史交易记录的。如果您需要最新的余额，请通过交易平台查询。",
    ),
    (
        "X22",
        "Show me the balance of ETH",
        POSITIONS,
        "You currently hold 10.41995 ETH, which has an unrealized profit of 1170.41008219 USD.",
    ),
    (
        "X23",
        "What is my ETH's balance?",
        POSITIONS,
        "You currently hold 10.41995 ETH. The total cost of your ETH purchases was "
        "26,973.87486781 USDT, and as of now, you have an unrealized profit of "
        "1,170.41008219 USDT.",
    ),
    (
        "X24",
        "my ADA balance please",
        POSITIONS,
        "You currently hold 20,939.06 ADA, which was bought with USDT. However, the current "
        "market price for ADA in USDT is not available to calculate the unrealized profit.",
    ),
    (
        "X25",
        "我的 BTC 余额是多少",
        POSITIONS,
        "您目前持有 1.0174765 BTC。它的未实现利润为 6919.59984044 USDT。",
    ),
    ("X27", "英伟达的余额还剩多少股", POSITIONS, "英伟达（NVDA）的余额还剩下50股。"),
    (
        "X28",
        "微软股票的余额还有多少",
        POSITIONS,
        "微软股票（MSFT）的余额为52股。成本总计为21083.70415094美元，未实现利润为1880.53584906美元。",
    ),
    (
        "X31",
        "What's my eth balance?",
        POSITIONS,
        "You currently hold 10.41995 ETH, which has an unrealized profit of 1170.41008219 USDT.",
    ),
    (
        "X32",
        "balance of BTC please",
        POSITIONS,
        "You currently hold 1.0174765 BTC. The cost of this holding was 59094.27547956 USDT, "
        "and the unrealized profit is 6919.59984044 USDT.",
    ),
    (
        "X33",
        "How much ADA do I have left?",
        POSITIONS,
        "You currently hold 20,939.06 ADA. As of now, there is no market price for ADA in "
        "USDT, so the unrealized profit cannot be calculated.",
    ),
    (
        "X35",
        "what is the balance on my bitcoin",
        POSITIONS,
        "You currently hold 1.0174765 Bitcoin (BTC). The cost of your BTC holdings is "
        "59,094.27547956 USDT, and your unrealized profit is 6,919.59984044 USDT.",
    ),
    (
        "X36",
        "比特币余额",
        POSITIONS,
        "您目前持有的比特币（BTC）数量为1.0174765 BTC。未实现盈利为6919.59984044 USDT。",
    ),
]


@pytest.mark.parametrize(
    ("number", "text", "call", "reply"), SEVENTEEN, ids=[one[0] for one in SEVENTEEN]
)
def test_the_seventeen_replies_of_the_tables_are_not_caught(
    number: str, text: str, call: ToolReply, reply: str
) -> None:
    said = replayed(text, call, reply)
    assert said.reply == reply, number

    verdict = judge(Sentence(id=number, group="must_pass", text=text), said)

    assert verdict.trouble == "", verdict.trouble


@pytest.mark.parametrize(
    ("text", "reply"),
    [
        ("帮我看看账户", "你现在持有 1.0174765 个 BTC。你的现金余额是 5000 USDT。"),
        ("我还有多少钱", "你还有 1.0174765 USDT 的现金可用。"),
        ("我还剩多少美元", "你还剩 140080.19 美元现金。"),
        ("我这个月入了多少金", "你这个月入金了 3000 USDT。"),
    ],
)
def test_the_four_let_through_before_are_never_shown_unjudged_after_a_lookup(
    text: str, reply: str
) -> None:
    said = replayed(text, POSITIONS, reply)
    verdict = judge(Sentence(id="x", group="must_pass", text=text), said)

    # Either the program's own check held the model's words back (none of
    # them is shown), or the ruler counts them as trouble.
    assert said.reply != reply or verdict.trouble != ""
