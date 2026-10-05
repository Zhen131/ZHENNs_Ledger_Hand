# Results

This file records what each run of the experiment kit in `evals/` measured.
It states numbers and examples only. Every number in the tables below is
worked out again from the run's results file by `evals.summarize`, and a
test (`tests/evals/test_results_record.py`) checks that the tables here are
exactly what the results file gives.

How to read the tables:

- **Scored sentences** are the passages a trade should be recorded from,
  and the passages with no trade at all (talk). The sentences of the
  `not_to_record` group (futures or leverage, a coin paid with another coin,
  an order not filled yet, a plan) are counted in **none** of the scores:
  the first prompt does not ask the model to leave them out, and leaving
  them out belongs to the check of a draft and to the later steps. They
  have a table of their own: how many drafts each gave, and what the check
  of a draft says of each.
- **Well-formed**: sentences whose reply was read as the table, of all
  sentences. **Whole trades right** (the main score): gold trades for which
  every one of the eleven scored fields of the paired draft is right (an
  empty gold field must be empty too), of all gold trades; a missed trade
  counts as wrong. **Missed / extra**: per sentence, gold trades minus
  drafts, and drafts minus gold trades, where above zero. **Made up**:
  fields in pairs where the gold value is empty and the draft holds one, of
  the fields in pairs where the gold value is empty. **No-trade sentences
  right**: talk that gave no draft, of all talk.
- Drafts are paired with gold trades so that as many pairs are made as
  there can be and the most fields agree; the order the model gave its rows
  in changes nothing (`evals/matching.py`).
- Every field of every pair falls into one kind: right; left empty by the
  program with its reason in the issues; left empty with no issue (the
  model gave nothing for it); a wrong value with an issue about the field; a
  wrong value with no issue about the field; a value made up. "Wrong values
  in drafts with no issue about them" lists every wrong value with no issue,
  made-up ones included.
- A **half copy** is a field where the model copied only part of the gold
  phrase (the piece of the passage the gold value comes from) and the field
  did not come out right.
- "Fields the program left empty" marks the ones where the model's phrase
  was exactly the gold phrase: the model copied what the gold answer says,
  and the program still left the field empty.

## 2026-10-05: baseline, debug set, prompt `first`, `qwen2.5:7b`

Results file: `evals/results/run-20261005T150537Z-debug-first.jsonl`, with
its summary in `run-20261005T150537Z-debug-first.summary.json`. The
conditions of the run are the first table below. The final set was not run.

This run was made twice on the same day, under the same conditions except
the commit; the earlier run is at the end of this section. The model's raw
replies, the drafts and the issues are the same in both runs for all 30
sentences.

**Several trades in one passage.** 8 sentences hold more than one trade,
with 19 gold trades between them: 16 whole trades right, 0 missed, 0 extra.
Of these, the 5 sentences with two trades hold 10 gold trades, 10 whole
right; the 3 sentences with three or more hold 9, 6 whole right. In every
one of the 8 sentences the model gave as many rows as there are trades.

**One trade in a passage.** 15 sentences, 15 gold trades: 13 whole trades
right, 0 missed, 0 extra.

**Talk.** 3 sentences, 3 gave no draft.

**The fields that came out wrong** (8 of 374 fields in 34 pairs):

- 5 left empty by the program, with the reason in the issues. 3 because the
  model's phrase is not a piece of the passage: the English times
  `yesterday` (d05) and `yesterday at 18:20` (d13) were written as `昨天` and
  `昨天 18:20`, and `TON 卖了 200 个` (d23) was written as `200 个 TON`. 2
  because the phrase was taken as cutting a number (d23): the model's
  phrases were exactly the gold phrases `63,000` and `1.5 ETH`; in the
  passage `0.1 BTC @ 63,000，1.5 ETH @ 2,410`, the full-width comma between
  `63,000` and `1.5` is read as a thousands separator, and the issue of
  numbers no trade used lists `63,000，1.5` as one number.
- 1 left empty with no issue: the total of the third trade in d23
  (`total 1,040 USDT`), which the model put under price instead.
- 2 made up, each with no issue about the field, both a total the model
  also or instead put under price: d05 (`64.80 USDT` under both price and
  total; price 64.80 in the draft) and d23, third trade (`1,040 USDT` under
  price; price 1040 in the draft). The check of a draft reports
  `AMOUNTS_DISAGREE` for the d05 draft (120 times 64.80 is not 64.80); the
  d23 draft holds only a price and is reported as missing one more of
  quantity, price and total.
- 0 wrong values with an issue, 0 wrong values with no issue among the
  fields whose gold value is not empty.

**Half copies.** 0. In the sentences with a number written so much a
piece, with a gap before the multiplier, with a space between thousands or
next to another number one space away, the model copied the whole phrase
each time: `100 万 SHIB` and `0.000012` out of `0.000012一个` (d09),
`94 900` (d10), `0.02` and `94900` (d11), `3 w DOGE` (d12), `1 万个 DOGE`
(d19). `94 900` and
`3 w DOGE` are numbers the core is unsure of, so the gold answer and the
draft both leave those fields empty.

**Passages not to record.** d27 (futures) gave one draft, with the margin
`200U` under total and the opening price under price; the check of a draft
stops it for a missing side and fee. d28 (a coin paid with another coin)
gave two drafts, one per coin. d29 (an order not filled yet) gave one
draft, stopped for a missing side, fee and time. d30 (a plan) gave none.
No draft of this group passes the check of a draft; none is stopped by a
rule about its kind, since the check has no such rule.

**Time.** The 30 sentences took 123.7 seconds in all (the sum of the
sentences; 123.7 seconds from the first to the end line). One-trade
sentences took 2.8 to 4.0 seconds, two-trade ones 5.7 to 6.6, three-trade
ones 8.8 to 9.7, talk under 0.6. The model was already loaded when the run
began, so the first sentence includes no loading. Every sentence needed
one call to the model; no reply was cut off; the prompt read 1,745 to 1,797
tokens per call.

**Typical errors**, as the results file records them:

| Sentence | What the passage says | What the model wrote | What went wrong |
| --- | --- | --- | --- |
| d05 | `Bought 120 ADA for 64.80 USDT total yesterday, fee 0.002 BNB` | price `64.80 USDT`, total `64.80 USDT`, time `昨天` | The total is also given as the price, so the draft holds price 64.80 with no issue; the time is written in Chinese, is not a piece of the passage and is left empty. |
| d13 | `Picked up 40 LINK at 13.85 yesterday at 18:20 while BTC sat near 61k, fee 0` | time `昨天 18:20` | The time is written in Chinese, is not a piece of the passage and is left empty. Every other field is right. |
| d23 | `刚才连着 sell 了三笔：0.1 BTC @ 63,000，1.5 ETH @ 2,410，还有 TON 卖了 200 个，total 1,040 USDT` | price `63,000` (first trade), quantity `1.5 ETH` (second), quantity `200 个 TON` and price `1,040 USDT` (third) | The first two phrases are the gold phrases, and the program leaves both fields empty as cutting a number. The third trade's quantity is rewritten and left empty; its total is given as the price. None of the three trades is whole. |

The generated tables of this run:

#### Run
| Condition | Value |
| --- | --- |
| set | debug |
| final_exam_switch | False |
| set_file | evals/sets/debug.json |
| set_sha256 | 4529d98323ad1df4d38f5a5b73cdf1082b6a1cd08a0604a454ecf7986104f4d8 |
| prompt | first |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | 7a510f4aaf16f7830ea5df2ec2071a276006565014e61bf295aa44a57a297112 |
| commit | 3c3095707bd995efc1350c2305436ec2af26e837 |
| worktree_clean | True |
| model | qwen2.5:7b |
| model_fingerprint | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e |
| server_version | 0.34.3 |
| base_url | http://127.0.0.1:11434 |
| parameter temperature | 0.0 |
| parameter top_p | 1.0 |
| parameter max_reply_tokens | 1024 |
| parameter context_tokens | 16384 |
| parameter timeout_seconds | 120.0 |
| parameter retries | 2 |
| parameter retry_wait_seconds | 1.0 |
| parameter asks_again | 1 |
| coin_table | built-in |
| started_at | 2026-10-05T15:05:37+00:00 |
| sentences | 30 |
| sum_of_sentence_seconds | 123.686 |
| first_sentence_seconds | 4.01 |
| longest_sentence_seconds | 9.686 |
| finished_at | 2026-10-05T15:07:41+00:00 |
| seconds_of_the_last_session | 123.728 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 26 | 26 / 26 (100.0%) | 29 / 34 (85.3%) | 0 | 0 | 2 / 140 (1.4%) | 3 / 3 (100.0%) |
| one trade | 15 | 15 / 15 (100.0%) | 13 / 15 (86.7%) | 0 | 0 | 1 / 60 (1.7%) | 0 / 0 (-) |
| several trades | 8 | 8 / 8 (100.0%) | 16 / 19 (84.2%) | 0 | 0 | 1 / 80 (1.2%) | 0 / 0 (-) |
| - two trades | 5 | 5 / 5 (100.0%) | 10 / 10 (100.0%) | 0 | 0 | 0 / 42 (0.0%) | 0 / 0 (-) |
| - three or more trades | 3 | 3 / 3 (100.0%) | 6 / 9 (66.7%) | 0 | 0 | 1 / 38 (2.6%) | 0 / 0 (-) |
| no trade (talk) | 3 | 3 / 3 (100.0%) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 3 / 3 (100.0%) |
| Chinese | 10 | 10 / 10 (100.0%) | 13 / 13 (100.0%) | 0 | 0 | 0 / 52 (0.0%) | 1 / 1 (100.0%) |
| English | 9 | 9 / 9 (100.0%) | 10 / 12 (83.3%) | 0 | 0 | 1 / 49 (2.0%) | 1 / 1 (100.0%) |
| mixed | 7 | 7 / 7 (100.0%) | 6 / 9 (66.7%) | 0 | 0 | 1 / 39 (2.6%) | 1 / 1 (100.0%) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 34 / 34 (100.0%) |
| coin | 34 / 34 (100.0%) |
| quantity | 32 / 34 (94.1%) |
| price | 31 / 34 (91.2%) |
| total | 33 / 34 (97.1%) |
| price_currency | 34 / 34 (100.0%) |
| fee | 34 / 34 (100.0%) |
| fee_currency | 34 / 34 (100.0%) |
| time | 32 / 34 (94.1%) |
| platform | 34 / 34 (100.0%) |
| opinion | 34 / 34 (100.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 366 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 5 |
| - because the model's phrase is not a piece of the passage | 3 |
| - because the model's phrase cuts a number of the passage | 2 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 1 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 2 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (2)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |
| d05: Bought 120 ADA for 64.80 USDT total yesterday, fee 0.002 BNB | 1 | price | 64.80 USDT | 64.80 | (empty) | MADE_UP |
| d23: 刚才连着 sell 了三笔：0.1 BTC @ 63,000，1.5 ETH @ 2,410，还有 TON 卖了 200 个，total 1,040 USDT | 3 | price | 1,040 USDT | 1040 | (empty) | MADE_UP |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (5; the model's phrase was exactly the gold phrase in 2)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| d05 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| d13 | 1 | time | 昨天 18:20 | yesterday at 18:20 | NOT_IN_PASSAGE | no |
| d23 | 1 | price | 63,000 | 63,000 | CUTS_A_NUMBER | yes |
| d23 | 2 | quantity | 1.5 ETH | 1.5 ETH | CUTS_A_NUMBER | yes |
| d23 | 3 | quantity | 200 个 TON | 200 个 | NOT_IN_PASSAGE | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |
| d27: 昨天开了 10 倍杠杆做多 BTC，开仓价 62,800，保证金 200U | futures_or_leverage | extracted | 1 | draft 1: stopped by SIDE, FEE |
| d28: Swapped 0.5 ETH for 0.019 BTC on Uniswap this morning | coin_for_coin | extracted | 2 | draft 1: stopped by SIDE, ONE_MORE_OF_QUANTITY_PRICE_TOTAL, FEE; draft 2: stopped by ONE_MORE_OF_QUANTITY_PRICE_TOTAL, FEE |
| d29: 挂了一个 limit buy，0.05 BTC @ 58,000，还没成交 | open_order | extracted | 1 | draft 1: stopped by SIDE, FEE, OCCURRED |
| d30: 打算明天下午 3 点买 1 个 ETH，价格到 2,300 就进 | plan | extracted | 0 | - |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| d01 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d02 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d03 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d04 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d05 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.price:MADE_UP, 1.time:LEFT_EMPTY_WITH_REASON |
| d06 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d07 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d08 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d09 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d10 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d11 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d12 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d13 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| d14 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d15 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d16 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d17 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d18 | mixed | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d19 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d20 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d21 | zh | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d22 | en | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d23 | mixed | extracted | 3 | 3 | 0 | 0 | 0 | 1.price:LEFT_EMPTY_WITH_REASON, 2.quantity:LEFT_EMPTY_WITH_REASON, 3.quantity:LEFT_EMPTY_WITH_REASON, 3.price:MADE_UP, 3.total:LEFT_EMPTY_BY_MODEL |
| d24 | zh | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d25 | en | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d26 | mixed | extracted | 0 | 0 | 0 | 0 | 0 | - |

### The earlier run of the same day

Results file: `evals/results/run-20261005T150041Z-debug-first.jsonl`, with
its summary in `run-20261005T150041Z-debug-first.summary.json`. Same set,
prompt, model, model fingerprint, Ollama version and parameters as the
baseline above; made at commit `a458392`, the commit before the baseline's.
The only difference between the two commits is in the summary: the
baseline's commit added the table of run conditions and timing, and the
list of the fields the program left empty. The scores are not touched by
that change.

Its raw replies, drafts and issues are the same as the baseline's for all 30
sentences, and so is every score. Its summary file was worked out again from
its unchanged results file with the summary code of the baseline's commit,
so that it has the same parts as the baseline's; every number in the summary
written during the run is the same in the one worked out again.

<details>
<summary>The generated tables of the earlier run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | debug |
| final_exam_switch | False |
| set_file | evals/sets/debug.json |
| set_sha256 | 4529d98323ad1df4d38f5a5b73cdf1082b6a1cd08a0604a454ecf7986104f4d8 |
| prompt | first |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | 7a510f4aaf16f7830ea5df2ec2071a276006565014e61bf295aa44a57a297112 |
| commit | a458392d7cfa8713c85f5e2d26fffbf00ca8c6ea |
| worktree_clean | True |
| model | qwen2.5:7b |
| model_fingerprint | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e |
| server_version | 0.34.3 |
| base_url | http://127.0.0.1:11434 |
| parameter temperature | 0.0 |
| parameter top_p | 1.0 |
| parameter max_reply_tokens | 1024 |
| parameter context_tokens | 16384 |
| parameter timeout_seconds | 120.0 |
| parameter retries | 2 |
| parameter retry_wait_seconds | 1.0 |
| parameter asks_again | 1 |
| coin_table | built-in |
| started_at | 2026-10-05T15:00:41+00:00 |
| sentences | 30 |
| sum_of_sentence_seconds | 122.433 |
| first_sentence_seconds | 3.98 |
| longest_sentence_seconds | 9.591 |
| finished_at | 2026-10-05T15:02:43+00:00 |
| seconds_of_the_last_session | 122.474 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 26 | 26 / 26 (100.0%) | 29 / 34 (85.3%) | 0 | 0 | 2 / 140 (1.4%) | 3 / 3 (100.0%) |
| one trade | 15 | 15 / 15 (100.0%) | 13 / 15 (86.7%) | 0 | 0 | 1 / 60 (1.7%) | 0 / 0 (-) |
| several trades | 8 | 8 / 8 (100.0%) | 16 / 19 (84.2%) | 0 | 0 | 1 / 80 (1.2%) | 0 / 0 (-) |
| - two trades | 5 | 5 / 5 (100.0%) | 10 / 10 (100.0%) | 0 | 0 | 0 / 42 (0.0%) | 0 / 0 (-) |
| - three or more trades | 3 | 3 / 3 (100.0%) | 6 / 9 (66.7%) | 0 | 0 | 1 / 38 (2.6%) | 0 / 0 (-) |
| no trade (talk) | 3 | 3 / 3 (100.0%) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 3 / 3 (100.0%) |
| Chinese | 10 | 10 / 10 (100.0%) | 13 / 13 (100.0%) | 0 | 0 | 0 / 52 (0.0%) | 1 / 1 (100.0%) |
| English | 9 | 9 / 9 (100.0%) | 10 / 12 (83.3%) | 0 | 0 | 1 / 49 (2.0%) | 1 / 1 (100.0%) |
| mixed | 7 | 7 / 7 (100.0%) | 6 / 9 (66.7%) | 0 | 0 | 1 / 39 (2.6%) | 1 / 1 (100.0%) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 34 / 34 (100.0%) |
| coin | 34 / 34 (100.0%) |
| quantity | 32 / 34 (94.1%) |
| price | 31 / 34 (91.2%) |
| total | 33 / 34 (97.1%) |
| price_currency | 34 / 34 (100.0%) |
| fee | 34 / 34 (100.0%) |
| fee_currency | 34 / 34 (100.0%) |
| time | 32 / 34 (94.1%) |
| platform | 34 / 34 (100.0%) |
| opinion | 34 / 34 (100.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 366 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 5 |
| - because the model's phrase is not a piece of the passage | 3 |
| - because the model's phrase cuts a number of the passage | 2 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 1 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 2 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (2)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |
| d05: Bought 120 ADA for 64.80 USDT total yesterday, fee 0.002 BNB | 1 | price | 64.80 USDT | 64.80 | (empty) | MADE_UP |
| d23: 刚才连着 sell 了三笔：0.1 BTC @ 63,000，1.5 ETH @ 2,410，还有 TON 卖了 200 个，total 1,040 USDT | 3 | price | 1,040 USDT | 1040 | (empty) | MADE_UP |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (5; the model's phrase was exactly the gold phrase in 2)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| d05 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| d13 | 1 | time | 昨天 18:20 | yesterday at 18:20 | NOT_IN_PASSAGE | no |
| d23 | 1 | price | 63,000 | 63,000 | CUTS_A_NUMBER | yes |
| d23 | 2 | quantity | 1.5 ETH | 1.5 ETH | CUTS_A_NUMBER | yes |
| d23 | 3 | quantity | 200 个 TON | 200 个 | NOT_IN_PASSAGE | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |
| d27: 昨天开了 10 倍杠杆做多 BTC，开仓价 62,800，保证金 200U | futures_or_leverage | extracted | 1 | draft 1: stopped by SIDE, FEE |
| d28: Swapped 0.5 ETH for 0.019 BTC on Uniswap this morning | coin_for_coin | extracted | 2 | draft 1: stopped by SIDE, ONE_MORE_OF_QUANTITY_PRICE_TOTAL, FEE; draft 2: stopped by ONE_MORE_OF_QUANTITY_PRICE_TOTAL, FEE |
| d29: 挂了一个 limit buy，0.05 BTC @ 58,000，还没成交 | open_order | extracted | 1 | draft 1: stopped by SIDE, FEE, OCCURRED |
| d30: 打算明天下午 3 点买 1 个 ETH，价格到 2,300 就进 | plan | extracted | 0 | - |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| d01 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d02 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d03 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d04 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d05 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.price:MADE_UP, 1.time:LEFT_EMPTY_WITH_REASON |
| d06 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d07 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d08 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d09 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d10 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d11 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d12 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d13 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| d14 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d15 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d16 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d17 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d18 | mixed | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d19 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d20 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d21 | zh | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d22 | en | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d23 | mixed | extracted | 3 | 3 | 0 | 0 | 0 | 1.price:LEFT_EMPTY_WITH_REASON, 2.quantity:LEFT_EMPTY_WITH_REASON, 3.quantity:LEFT_EMPTY_WITH_REASON, 3.price:MADE_UP, 3.total:LEFT_EMPTY_BY_MODEL |
| d24 | zh | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d25 | en | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d26 | mixed | extracted | 0 | 0 | 0 | 0 | 0 | - |

</details>
