"""The table of examples for tidying the words said: each said, and as tidied.

Rows may be added. No row is taken out, and what a row is tidied to is not
changed: the table is the rule.
"""

from __future__ import annotations

import pytest

from ledger_hand.core.spoken_text import tidy_spoken

BUDAPEST = "Europe/Budapest"
SHANGHAI = "Asia/Shanghai"

# (said, tidied, the zone trades are recorded in). A tidied of None is the said itself.
EXAMPLES: tuple[tuple[str, str | None, str], ...] = (
    ("我花了三十五 USDT买的", "我花了35 USDT买的", BUDAPEST),
    ("成交价是两千五百八十 USDT", "成交价是2580 USDT", BUDAPEST),
    ("均价六万四千五百三十点二USDT", "均价64530.2USDT", BUDAPEST),
    ("买了零点零零零八一八零九个BTC", "买了0.00081809个BTC", BUDAPEST),
    ("卖了七百四十七点二七个ADA", "卖了747.27个ADA", BUDAPEST),
    ("一共花了一千零五U", "一共花了1005U", BUDAPEST),
    ("卖了二十五万个PEPE", "卖了250000个PEPE", BUDAPEST),
    ("总共一亿两千万 SHIB", "总共120000000 SHIB", BUDAPEST),
    ("成交额三百零二点五 USDT", "成交额302.5 USDT", BUDAPEST),
    ("手续费零点一二个USDT", "手续费0.12个USDT", BUDAPEST),
    ("均价是十点五", "均价是10.5", BUDAPEST),
    ("买了0.0000五四二三八个BTC", "买了0.000054238个BTC", BUDAPEST),
    ("数量是0.0九四三二六个SOL", "数量是0.094326个SOL", BUDAPEST),
    ("手续费呢是0.七五，收的ADA", "手续费呢是0.75，收的ADA", BUDAPEST),
    ("手续费0.000000八二个BTC", "手续费0.00000082个BTC", BUDAPEST),
    ("二六年十一月二十号下午十四点十二分买的", "2026年11月20号下午14点12分买的", BUDAPEST),
    ("26年10月9号买的ETH", "2026年10月9号买的ETH", BUDAPEST),
    ("二〇二六年三月五号上午十点买的", "2026年3月5号上午10点买的", BUDAPEST),
    ("十月零九号下午十六点二十一分", "10月9号下午16点21分", BUDAPEST),
    ("二六年的九月零七号的下午的十五点三十八分", "2026年9月7号下午15点38分", BUDAPEST),
    ("晚上的二十点零七分卖的", "晚上20点07分卖的", BUDAPEST),
    ("上午八点五分买的", "上午8点05分买的", BUDAPEST),
    ("下午三点半买的", "下午3点半买的", BUDAPEST),
    ("下午十四点十二买的", "下午14点12买的", BUDAPEST),
    ("十四点十二分三十一秒买的", "14点12分买的", BUDAPEST),
    ("2026年11月20号14:12:31买的", "2026年11月20号14:12买的", BUDAPEST),
    ("二六年这个十月三号下午呢三点十分", "2026年10月3号下午3点10分", BUDAPEST),
    ("在匈牙利时间的二六年十一月二十号下午两点买的", "在2026年11月20号下午2点买的", BUDAPEST),
    (
        "2026年11月6号15点30分，布达佩斯时间，买了1.5股",
        "2026年11月6号15点30分，买了1.5股",
        BUDAPEST,
    ),
    ("北京时间二六年十一月二十号下午三点买的", None, BUDAPEST),
    ("匈牙利时间十四点十二分", None, SHANGHAI),
    ("然后成交的均价是在六万三千五百点五USDT", "然后成交的均价是在63500.5USDT", BUDAPEST),
    ("我买了微软的股票", None, BUDAPEST),
    ("手续费是以BTC计价的", None, BUDAPEST),
    ("那天八点二五买的", None, BUDAPEST),
    ("下午三十点二", None, BUDAPEST),
    ("那天十四点十二买的", None, BUDAPEST),
    ("三十点二USDT", "30.2USDT", BUDAPEST),
    ("3000一个", None, BUDAPEST),
    ("三十万一个", None, BUDAPEST),
    ("零点零一五二六三九一个BTC", None, BUDAPEST),
    ("两三千U", None, BUDAPEST),
    ("两万多U", None, BUDAPEST),
    ("委托价值大概五十九点九六USDT", None, BUDAPEST),
    ("买一些ETH试一下，十分划算，千万别卖", None, BUDAPEST),
    ("买了一点ETH", None, BUDAPEST),
    ("买了两个BTC", None, BUDAPEST),
    ("跌了百分之三十", None, BUDAPEST),
    ("9万4900买的", None, BUDAPEST),
    ("这个币拿了十六年", "这个币拿了16年", BUDAPEST),
    ("手续费呢是零", None, BUDAPEST),
    ("Bought 0.02 BTC at 94900 at 9:40:15, fee 2 USDT", None, BUDAPEST),
    ("2026年11月20号下午14点12分花了35 USDT买了0.000054238个BTC", None, BUDAPEST),
    ("今天上午11点在币安0.01个BTC 花了950U，手续费0", None, BUDAPEST),
    ("我10月一共买了多少钱的币", None, BUDAPEST),
    ("二六年十月一共买了多少", "2026年10月一共买了多少", BUDAPEST),
    ("晚上20点7分卖的", None, BUDAPEST),
    ("手续费零点零三个USDT", "手续费0.03个USDT", BUDAPEST),
    ("二六年十一月二十号下午三点五买的", None, BUDAPEST),
    ("下午三点五", None, BUDAPEST),
    ("下午三点五分买的", "下午3点05分买的", BUDAPEST),
    ("价格是四百一股", None, BUDAPEST),
    ("均价三千一共花了六千", "均价三千一共花了6000", BUDAPEST),
    ("手续费0.0五一个BTC", None, BUDAPEST),
    ("买了二十一个BTC", None, BUDAPEST),
    ("美东时间二六年十一月二十号下午三点买的", None, BUDAPEST),
    ("二六年十一月二十号下午三点UTC买的", None, BUDAPEST),
    ("二六年十一月二十号下午三点，东八区", None, BUDAPEST),
    ("手续费二十块五", None, BUDAPEST),
    ("买了十二个半SOL", None, BUDAPEST),
    ("手续费三十五块八毛", None, BUDAPEST),
    ("均价一点二三四USDT", None, BUDAPEST),
    ("买了1.二三四个ETH", None, BUDAPEST),
    ("这个月八号下午三点买的", "这个月8号下午3点买的", BUDAPEST),
    ("九九年十月三号上午十点买的", "2099年10月3号上午10点买的", BUDAPEST),
    # Another zone said anywhere in the sentence: no time of it is tidied, numbers are.
    (
        "按北京时间算，二六年十一月二十号下午三点买了0.01个BTC，均价九万五千U，手续费0",
        "按北京时间算，二六年十一月二十号下午三点买了0.01个BTC，均价95000U，手续费0",
        BUDAPEST,
    ),
    (
        "北京时间是二六年十一月二十号下午三点，买了两千U的ETH",
        "北京时间是二六年十一月二十号下午三点，买了2000U的ETH",
        BUDAPEST,
    ),
    ("二六年十一月二十号下午三点买的，这是UTC", None, BUDAPEST),
    ("二六年十一月二十号下午三点买的，用的是东京时间", None, BUDAPEST),
    # The ledger's own zone said apart from the time: the time is tidied, the words stay.
    (
        "按匈牙利时间算，二六年十一月二十号下午三点买的",
        "按匈牙利时间算，2026年11月20号下午3点买的",
        BUDAPEST,
    ),
    # Any other 时间, a zone or not, leaves every time of the sentence as said.
    ("成交时间是二六年十一月二十号下午三点", None, BUDAPEST),
    ("这段时间二六年十月买了三千U的币", "这段时间二六年十月买了3000U的币", BUDAPEST),
    ("下午时间三点十分买的", None, BUDAPEST),
    # A minute after a filler, money in 分, a while: not sure, left as said.
    ("二六年十一月二十号的下午三点的五十分买的", None, BUDAPEST),
    ("手续费零点五分", None, BUDAPEST),
    ("花了二十点五分钟", None, BUDAPEST),
    # More of the amount after a unit, with a gap or after letters.
    ("手续费二十块 五", None, BUDAPEST),
    ("手续费二十U五", None, BUDAPEST),
    # 时间 after anything not on the list of released words may be a zone: times left.
    (
        "按北京的时间，二六年十一月二十号下午三点买了0.01个BTC，均价九万五千U",
        "按北京的时间，二六年十一月二十号下午三点买了0.01个BTC，均价95000U",
        BUDAPEST,
    ),
    ("按北京那边的时间算，二六年十一月二十号下午三点买的", None, BUDAPEST),
    (
        "国内的时间是二六年十一月二十号下午三点，买了两千U的ETH",
        "国内的时间是二六年十一月二十号下午三点，买了2000U的ETH",
        BUDAPEST,
    ),
    ("我老家的时间二六年十一月二十号下午三点买的", None, BUDAPEST),
    ("公司那边的时间是二六年十一月二十号下午三点", None, BUDAPEST),
    ("按北京下午时间三点十分买的", None, BUDAPEST),
    ("二六年十一月二十号下午三点买的，JST", None, BUDAPEST),
    # The ledger's own zone with 的 between: tidied.
    (
        "按匈牙利的时间，二六年十一月二十号下午三点买的",
        "按匈牙利的时间，2026年11月20号下午3点买的",
        BUDAPEST,
    ),
    ("成交的时间是二六年十一月二十号下午三点", None, BUDAPEST),
    ("下单时间：二六年十一月二十号下午三点", None, BUDAPEST),
    ("具体时间是二六年十一月二十号下午三点", None, BUDAPEST),
    ("时间是二六年十一月二十号下午三点", None, BUDAPEST),
    # Missed at the third check: each 时间 here may be a zone, so the times stay.
    (
        "时间是美东二六年十一月二十号下午三点，买了0.01个BTC，均价九万五千U，手续费0",
        "时间是美东二六年十一月二十号下午三点，买了0.01个BTC，均价95000U，手续费0",
        BUDAPEST,
    ),
    ("成交时间是美东二六年十一月二十号下午三点买的", None, BUDAPEST),
    (
        "按纽约那个时间，二六年十一月二十号下午三点买了0.01个BTC，均价九万五千U，手续费0",
        "按纽约那个时间，二六年十一月二十号下午三点买了0.01个BTC，均价95000U，手续费0",
        BUDAPEST,
    ),
    ("北京这个时间二六年十一月二十号下午三点买的", None, BUDAPEST),
    (
        "美股交易时间二六年十一月二十号下午三点买了0.01个BTC，均价九万五千U，手续费0",
        "美股交易时间二六年十一月二十号下午三点买了0.01个BTC，均价95000U，手续费0",
        BUDAPEST,
    ),
    ("北京的成交时间是二六年十一月二十号下午三点", None, BUDAPEST),
)


@pytest.mark.parametrize(("said", "tidied", "zone"), EXAMPLES)
def test_each_example_is_tidied_as_the_table_says(said: str, tidied: str | None, zone: str) -> None:
    assert tidy_spoken(said, zone).text == (said if tidied is None else tidied)


def test_the_table_keeps_its_seventy_five_rows() -> None:
    assert len(EXAMPLES) >= 75
