# Walkthrough: the Assistant page against a running ledger page

One full walk, sentence by sentence, from typing on this program's
Assistant page to pressing Save (or Reject) in the ledger page's pending
list, and then looking at the trade, the trades page and the change
history in the ledger. Everything was looked at and written down; nothing
in the program was changed for it.

- **When**: 2026-11-27, on a Windows computer (time zone Europe/Budapest).
- **Ledger**: the Local-First Trading Ledger at `dev@050e7dd`, the one with
  ten tools, among them the list of exchange rates; its page run with
  `next dev` on this computer, its assistant link started by this program.
- **Model**: `qwen2.5:7b` through the local Ollama, with every setting at
  its default: the table of common company names off, remembering the
  user's answers on. A last part turns the table on (see "With the table
  of company names on").
- **Browser**: a headless Chromium driven by a script (Playwright). The
  script typed every sentence on the Assistant page, read the reply, the
  cards and "How this was done", then read the ledger page's pending list
  and pressed Save or Reject there, as a person would. The token of the
  assistant link was read from the Assistant page and typed into the ledger
  page by the script only; it was never printed, written or shown in a
  screenshot.
- **Every figure is invented**, and so is the ledger: a new one made for
  this walk, kept in the browser's private storage.

## The invented ledger before the walk

Made on the ledger's own pages, by hand-typed forms. The euro was added as
a money, and MSFT and KO as US shares (BTC and ETH were already there).
AAPL and INTC were not added, on purpose.

| | When | What |
| --- | --- | --- |
| D1 | 2026-11-01 09:00 | 50000 USDT paid in |
| D2 | 2026-11-01 09:05 | 20000 USD paid in |
| D3 | 2026-11-01 09:10 | 2000 EUR paid in |
| B1 | 2026-11-03 09:30, Binance | bought 0.2 BTC at 60000 USDT, fee 6 USDT |
| B2 | 2026-11-05 14:00, Binance | bought 3 ETH at 2500 USDT, fee 3 USDT |
| B3 | 2026-11-06 15:30, IBKR | bought 5 MSFT at 400 USD, fee 1 USD |
| B4 | 2026-11-10 10:15, Binance | bought 0.05 BTC at 62000 USDT, fee 1.5 USDT |
| B5 | 2026-11-12 16:20, OKX | sold 1 ETH at 2700 USDT, fee 1 USDT |
| B6 | 2026-11-13 15:45, IBKR | bought 2 KO for 128 EUR (64 EUR a share), rate 1 EUR = 1.0859375 USD, fee 0.19 EUR |
| R | 2026-11-20 | exchange rate typed in: 1 EUR = 1.085 USD |

The ledger's share form starts a US share at New York time, and B3 and B6
were saved so (15:30 and 15:45 New York time); the days are the same
either way, and nothing below depended on the hour. Before the first
sentence the ledger was exported to a plain JSON backup, and once more
after the last one.

## How each sentence is judged

A sentence that sends a card, a change or a deletion is one of:

- **right**: every cell on the card and in the pending list is what was
  said, or carries a fitting mark; after Save the trade in the ledger is
  the card, plus the cells the walk was planned to fill in or put right;
- **marked wrong**: the model or the program got a cell wrong, but the cell
  was marked "assumed" or "suspicious", or the user was asked; a figure
  said but left empty on the card also counts here;
- **silently wrong**: a cell differs from what was said and carries no mark,
  or a change or deletion reaches another trade than the one meant;
- **not done**: nothing reached the pending list.

A question about the ledger is either **agrees** (the reply's figures are
the ledger's) or **wrong**.

A card whose figures differ from what was said was never saved, except for
the cells the walk planned to fill in or correct.

## Results

**Silently wrong: none.** 21 rounds, all walked; replies came in 3 to 7
seconds each.

| # | What was said | What happened | Judged |
| --- | --- | --- | --- |
| W01 | 2026年11月18号14点20分在OKX买了0.01个BTC，成交价63000 USDT，手续费0.5 USDT | Card as said; total 630 marked "worked out". Saved; the trade matches the card. | right |
| W02 | Bought 0.5 ETH at 2600 USDT on Binance on 19 November 2026 at 10:05, fee 0.4 USDT. | Card as said; the reply cautions that 10:05 was read on a 24-hour clock. Saved. | right |
| W03 | 2026年11月19号16点在Binance买了1个ETH，成交价2650 USDT | No fee said: the card went with the fee and its money empty, the reply naming them; the ledger would not save it until they were filled. Fee 0.6 USDT filled in on the ledger page, saved. | right |
| W04 | 2026年11月20号11点在Binance买了0.1个BTC，一个65000，一共花了6000 USDT，手续费1 USDT | 0.1 × 65000 is 6500, not 6000: all three figures sent as said and all three marked suspicious; the ledger's Save button was disabled. The total put right to 6500 on the ledger page, saved. | right |
| W05 | 2026年11月20号15点在OKX卖了5个ETH，一个2700，一共收了12000 USDT，手续费1 USDT | The ledger turned it down whole (figures disagree, and more sold than held); the reply quotes the ledger's reason. Nothing in the pending list. | not done (as meant) |
| W06 | 2026年11月21号15点30分在IBKR花了130欧元买了2股KO，一股70.5美元，换汇费0.2欧元 | Paid 130 EUR, price 65 EUR worked out, rate 1.0846153846 worked out as 2 × 70.5 ÷ 130 (by hand 141 ÷ 130 = 1.08461538...), compared with the ledger's rate of 2026-11-20 (1.085), 0.0% apart, not marked. Saved; the rate in the ledger is 1.0846153846. | right |
| W07 | 2026年11月21号16点在IBKR花了100欧元买了2股KO，一股70美元，换汇费0.2欧元 | Rate 1.4 (2 × 70 ÷ 100) marked suspicious: the ledger's rate (2026-11-20) is older than the euro trade of 2026-11-21 just saved, so it was compared with that one (1.0846153846). Rejected. | right |
| W08 | 2026年11月24号10点在IBKR买了1股KO，一股70美金，手续费1美金 | Priced in USD with the fee in USD, both marked "assumed" (KO's last trade was paid in EUR); not asked. Saved. | right |
| W09 | 2026年11月24号15点30分在IBKR买了1.5股微软，412.5美元一股，没有手续费 | With the table off, "微软" is not known: the user is asked which asset it is. | right (asked) |
| W09b | MSFT (the answer, same chat) | The card goes as MSFT, not marked "assumed"; the remembered names file gains "微软 → MSFT". "没有手续费" was not taken as a fee of 0: the fee went empty and was named; 0 USD filled in on the ledger page, saved. | marked wrong |
| W10 | 2026年11月25号10点在IBKR买了1股微软，410美元一股，手续费1美元 | Not asked again: asset MSFT marked "assumed", the reason naming the user's answer of 2026-11-27. Rejected. | right |
| W11 | 2026年11月25号14点在IBKR买了2股苹果，190美元一股，手续费1美元 | With the table off, "苹果" is not known: asked. | right (asked) |
| W11b | AAPL (the answer, same chat) | The ledger has no AAPL: asked again, saying to add it in the ledger first. Nothing sent. | not done (as meant) |
| W12 | 按北京时间算，2026年11月20号下午3点在OKX买了0.1个ETH，成交价2700 USDT，手续费0.1 USDT | Sent at 15:00 in Budapest time, the time cell marked suspicious with the zone said and "not converted". Rejected. | right |
| W13 | 我还有多少USDT | The ledger's cash balances: 19,006 USDT, 17,309.25 USD, 0 CNY, 1,741.61 EUR. Same as the ledger's home page. | agrees |
| W14 | What is my cash balance? | The same four balances. | agrees |
| W15 | 把11月10号那笔的平台改成OKX | B4 found; before and after side by side, only the platform changes (Binance to OKX). Saved; the change history shows the user's words. | right |
| W16 | 删掉11月12号那笔ETH卖出 | B5 found and shown. Saved; the trade is gone, the history says so. | right |
| W17 | 把11月6号那笔MSFT的手续费改成2美元 | Not done: the reply said "'美元' is not USD, what the fee is in now" and changed nothing. Said again as "把11月6号那笔MSFT的手续费改成2 USD": B3 found, only the fee changes (1 to 2 USD). Saved. | not done, then right on the second wording |
| W18 | 我现在持有什么？ | BTC 0.36 (cost 22,239 USDT), ETH 4.5 (11,454 USDT), MSFT 6.5 (2,620.75 USD), KO 5 (351.42325119992 USD). Same as the ledger's holdings (KO's cost shown there as 351.42 USD). | agrees |
| W19 | Delete the KO buy on 24 November 2026. | The W08 trade found. Saved; it is gone. | right |

The cash and holdings in W13, W14 and W18 were checked by hand against the
invented trades and the walk's own saves and deletions.

In the ledger's change history, every save made from a proposal reads
"助手自称：Ledger Hand 0.1.0 qwen2.5:7b" (the name the assistant gives
itself), with "保存前你改过" added when the card was changed on the ledger
page before Save (W03, W04, W09b).

## With the table of company names on

The program restarted with the table of company names on and an empty
folder for remembered names; each card rejected. Recorded only, not judged.

| # | What was said | What happened |
| --- | --- | --- |
| T1 | 2026年11月25号15点在IBKR买了1股微软，412美元一股，手续费1美元 | Not asked: MSFT, marked "assumed" from the program's table of common company names. |
| T2 | 2026年11月25号15点30分在IBKR买了2股苹果，190美元一股，手续费1美元 | Not asked, not sent: the ledger has no AAPL yet, add it first. |
| T3 | 2026年11月25号16点在IBKR买了1股微软，415美元一股，又买了2股英特尔，24美元一股，手续费都是1美元 | The MSFT trade sent, marked "assumed"; the INTC trade not sent, with "add it in the ledger first". Half of the passage went. |

No cell on these cards differed from what was said.

## Seen in this program, not changed

None of these sends a wrong figure unmarked; they are written down for
later.

- After "没有手续费" ("no fee") the fee is left empty rather than 0 (W09b).
- Changing a fee "to 2 美元" on a trade whose fee is in USD is refused as
  "'美元' is not USD" (W17).
- A card sent with empty cells names them by the ledger's field names ("fee,
  feeAssetId"), and its Fee line reads "none none" (W03, W09b).
- "Took "微软" as MSFT (MSFT)": the code is said twice when the ledger's
  name for the share is its code (W10, T1, T3).
- When "美金" is read as USD, the reply says "no currency was said" (W08).
- The reminder about numbers no trade used lists the "一" of "一个", "一共"
  and "一股" (W04 to W10, T1 to T3).
- The reason on suspicious figures says "6500.0 USDT" where the total said
  had no decimals (W04).
- A held amount is shown with all its decimals: KO's cost 351.42325119992
  USD (W18).
- A deletion saved in the ledger reads "saved in your ledger, as trade ..."
  on its card (W16, W19).
- A change is shown twice in the reply: as lines of text and as a table
  (W15, W17).

## Seen in the ledger, passed on to it

- After a card is changed in the pending list and saved, the line "已保存：..."
  describes the card as proposed, not as saved (W03 says "手续费 没有", W04
  says "成交金额 6 000.00"; the trades saved have 0.6 and 6500).
- For a change of platform alone, the summary "改一笔：把 ... 改成 ..." does
  not mention the platform, so its two halves read the same; the row for
  the raw text says it will change while showing the same words twice (W15).
- A trade's details do not show the rate of a trade paid in another money;
  only the edit form does (W06).
- The change history lists the exchange rate typed in (1.085) as "市场价 EUR
  1.09 USD".
- In the edit form of a card whose three figures disagree, the total's
  suspicious mark is listed twice (W04). Not seen again when the walk was
  checked afterwards: the screenshots show each mark once, and the text
  read off the page then repeated other labels of the form as well, so
  the page may have been drawing itself again while it was read.

## What this walk did not cover

- A ledger page left open overnight, a reload of the ledger page, and a
  proposal that times out were not tried.
- Only one model, `qwen2.5:7b`, and one run of each sentence (W17 twice).
- The screenshots taken during the walk are kept with the owner's notes,
  not in this repository.
