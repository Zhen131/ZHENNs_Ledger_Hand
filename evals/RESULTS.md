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

## 2026-10-09: prompt experiment one, five prompt versions, `qwen2.5:7b`

Five versions of the extraction prompt, each one technique away from the
first, measured with the same 30 debug sentences, the same scoring and the
same model as the baseline above. Then the same five on a small set of
sentences written for the numbers the number reader finds hard (the
writings set), scored apart. Then two runs that each change one parameter.
The final set is run once, after all of this is recorded, with the version
that a rule fixed before the runs picks; its section is at the end.

These are versions of the extraction prompt only. The prompts for judging a
passage (`screen-1`, zero-shot), reading an answer (`answer-1`, zero-shot)
and wording a question (`bookkeeper-1`, persona) do other jobs and are not
measured here.

| Version | File | Technique | The one thing it changes from `first` |
| --- | --- | --- | --- |
| `first` | `extraction/prompts/first.py` | few-shot | nothing: the baseline, instructions and ten examples |
| `zero_shot` | `extraction/prompts/zero_shot.py` | zero-shot | no example; the instructions are the same |
| `persona` | `extraction/prompts/persona.py` | persona | a paragraph before the instructions: the model is a meticulous bookkeeper |
| `stepwise` | `extraction/prompts/stepwise.py` | chain of thought | a paragraph after the instructions asking for a step-by-step analysis, written in a field `steps` that its reply table has before the rows; its examples are `first`'s and show no analysis |
| `price_total` | `extraction/prompts/price_total.py` | content iteration | a sixth rule after the instructions: an amount said as a total goes into total, never into price |

The words for asking again are the same in all five. A test checks that
each version is `first` with only its declared change
(`tests/extraction/test_prompt_versions.py`).

**Conditions.** Every run used `qwen2.5:7b` (fingerprint
`845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`),
Ollama 0.34.3 and the settings' defaults: temperature 0.0, top_p 1.0,
longest reply 1,024 tokens, context 16,384 tokens, 120 seconds per call, 2
retries 1 second apart, and asking again once after a reply that misses the
table. Only the two parameter comparisons change one of these each. The
model was loaded before the first run. The runs were made one after
another on 2026-10-09 between 02:32 and 02:59 UTC, each at the commit that
recorded the run before it; between those commits only the results files
and this record changed. Each run line also records the fingerprint of the
reply table the version sends: it is the same for every version but
`stepwise`.

**How to read the new tables.** The first table of each comparison holds
the scores of the summary (see the top of this file), one row per run. The
second holds: the wrong values with no issue (the summary's list of that
name: wrong values and made-up values with no issue about the field); the
three more counts; the sentences in which a reply was cut off at the
longest reply; the calls to the model; and the seconds the sentences took,
added up. Calls, cut-off replies and seconds count every sentence of the
set, the passages not to record included. The three more counts are listed
case by case in each run's subsection:

- **A total put as the price**: in a pair whose gold trade says a total,
  the model's phrase for the price is the gold total's phrase, or the
  draft's price is the gold total while the gold price is another number.
- **Half copies (any)**: the model's phrase for a field is part of the gold
  phrase but not all of it, whether the field came out right or not: `100
  万` for `100 万 SHIB` counts, and so does `0.05` for `0.05 个 BTC`. **Half
  copies (not right)** is the summary's count, which takes only the fields
  that did not come out right.
- **A time in another language**: the time was left empty because the
  model's phrase is not a piece of the passage, and one of the model's
  phrase and the gold phrase holds a Chinese character and the other none.

### The five versions on the debug set

| Version | Technique | Differs from `first` in | Well-formed | Whole trades right | One trade | Several trades | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | few-shot | the baseline: instructions and ten examples | 26 / 26 (100.0%) | 31 / 34 (91.2%) | 13 / 15 (86.7%) | 18 / 19 (94.7%) | 0 | 0 | 2 / 140 (1.4%) | 3 / 3 (100.0%) |
| `zero_shot` | zero-shot | no example | 26 / 26 (100.0%) | 19 / 34 (55.9%) | 8 / 15 (53.3%) | 11 / 19 (57.9%) | 0 | 0 | 5 / 140 (3.6%) | 3 / 3 (100.0%) |
| `persona` | persona | a role said before the instructions | 26 / 26 (100.0%) | 29 / 34 (85.3%) | 12 / 15 (80.0%) | 17 / 19 (89.5%) | 0 | 0 | 3 / 140 (2.1%) | 3 / 3 (100.0%) |
| `stepwise` | chain of thought | a step-by-step analysis written before the table | 26 / 26 (100.0%) | 25 / 34 (73.5%) | 10 / 15 (66.7%) | 15 / 19 (78.9%) | 0 | 0 | 1 / 140 (0.7%) | 3 / 3 (100.0%) |
| `price_total` | content iteration | one more rule: a total is never the price | 26 / 26 (100.0%) | 29 / 34 (85.3%) | 12 / 15 (80.0%) | 17 / 19 (89.5%) | 0 | 0 | 0 / 140 (0.0%) | 3 / 3 (100.0%) |

| Version | Wrong values with no issue | A total put as the price | Half copies (any) | Half copies (not right) | A time in another language | Sentences with a reply cut off | Calls | Seconds | Results file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | 2 | 2 | 0 | 0 | 2 | 0 | 30 | 115.9 | `evals/results/run-20261009T023225Z-debug-first.jsonl` |
| `zero_shot` | 5 | 0 | 42 | 0 | 2 | 0 | 30 | 116.2 | `evals/results/run-20261009T023459Z-debug-zero_shot.jsonl` |
| `persona` | 3 | 2 | 0 | 0 | 2 | 0 | 30 | 119.3 | `evals/results/run-20261009T023708Z-debug-persona.jsonl` |
| `stepwise` | 0 | 0 | 0 | 0 | 1 | 0 | 30 | 177.8 | `evals/results/run-20261009T023913Z-debug-stepwise.jsonl` |
| `price_total` | 0 | 0 | 0 | 0 | 2 | 0 | 30 | 127.6 | `evals/results/run-20261009T024223Z-debug-price_total.jsonl` |

The rule, written down before any version was run: the most whole trades
right; then the fewest wrong values with no issue; then the fewest trades
missed and extra, added up; then the first in the order `first`,
`price_total`, `persona`, `zero_shot`, `stepwise`. So a new version is
picked only if it does strictly better than `first`. The parameter
comparisons below take no part.

Picked by the rule: `first`, settled at step 1.

- Step 1, most whole trades right: `first`.

The fields that did not come out right, run by run (each is in the run's
subsection below):

- `first`, 3 trades not whole: d05 and d13, the English time written in
  Chinese (left empty); d05 and d23 (third trade), the total put as the
  price as well or instead (a made-up price with no issue); d23 (third
  trade), `TON 卖了 200 个` written as `200 个 TON` (left empty).
- `zero_shot`, 15 trades not whole: 10 fields left empty with no issue (9
  times and 1 fee); 4 prices copied with `一个` after the number
  (`13.6 一个`), which the number reader does not read (left empty); 2
  times in another language (d05 `yesterday` as `昨天`, d15 `9:40` as
  `昨天晚上 9 点 40`); 5 made-up values with no issue (a
  pricing currency in d02 and twice in d23, the coin `3` in d08, the
  quantity `500` in d14, which is the total).
- `persona`, 5 trades not whole: d05, the total put as the price instead
  (a made-up price with no issue, the total left empty) and the English
  time written in Chinese; d13, the English time written in Chinese; d23
  (third trade), as in `first`; d08, the coin `3` (made up, no issue); d19,
  the price `两千四百五` written as `2,450` (left empty).
- `stepwise`, 9 trades not whole: the side left empty with no issue in d06,
  d07 and d14; the time left empty with no issue in d07 and in the three
  trades of d21; the Chinese prices of d04 and d19 written in digits (left
  empty); the English time of d13 written in Chinese (left empty); and in
  d14 the total as the quantity, with an issue about it. No wrong value
  with no issue.
- `price_total`, 5 trades not whole: d05 and d13, the English time written
  in Chinese; d11, `0.02 94900` copied whole as the quantity (the number
  reader is unsure of it, left empty) and no price; d19, the Chinese price
  written in digits; d23 (third trade), `200 个 TON` again. No total put as
  the price and no made-up value.

### The writings set

20 invented sentences, each made for one hard way of writing a number, in
Chinese or mixed passages and in English ones (`evals/sets/writings.json`,
read by `evals/writings.py`). Their gold answers follow the same rules as
the 50 sentences: a number the core is unsure of (`3 w`, `1.5 k`, `94 900`)
leaves its field empty, and each gold trade goes through the check of a
draft. These runs are not part of the scores above.

| Way of writing | Chinese or mixed passages | English passages |
| --- | --- | --- |
| a gap before a letter multiplier (3 w, 1.5 k) | 2 | 2 |
| a gap before a Chinese multiplier (100 万) | 2 | 2 |
| a space between thousands (94 900) | 2 | 2 |
| two numbers one space apart (0.02 94900) | 2 | 2 |
| a full-width comma between digits (94，900; 63,000，1.5) | 2 | 2 |

| Version | Technique | Differs from `first` in | Well-formed | Whole trades right | One trade | Several trades | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | few-shot | the baseline: instructions and ten examples | 20 / 20 (100.0%) | 15 / 22 (68.2%) | 13 / 18 (72.2%) | 2 / 4 (50.0%) | 0 | 0 | 0 / 93 (0.0%) | 0 / 0 (-) |
| `zero_shot` | zero-shot | no example | 20 / 20 (100.0%) | 14 / 22 (63.6%) | 14 / 18 (77.8%) | 0 / 4 (0.0%) | 0 | 0 | 1 / 93 (1.1%) | 0 / 0 (-) |
| `persona` | persona | a role said before the instructions | 20 / 20 (100.0%) | 15 / 22 (68.2%) | 13 / 18 (72.2%) | 2 / 4 (50.0%) | 0 | 0 | 0 / 93 (0.0%) | 0 / 0 (-) |
| `stepwise` | chain of thought | a step-by-step analysis written before the table | 20 / 20 (100.0%) | 12 / 22 (54.5%) | 10 / 18 (55.6%) | 2 / 4 (50.0%) | 0 | 1 | 0 / 93 (0.0%) | 0 / 0 (-) |
| `price_total` | content iteration | one more rule: a total is never the price | 20 / 20 (100.0%) | 15 / 22 (68.2%) | 13 / 18 (72.2%) | 2 / 4 (50.0%) | 0 | 0 | 0 / 93 (0.0%) | 0 / 0 (-) |

| Version | Wrong values with no issue | A total put as the price | Half copies (any) | Half copies (not right) | A time in another language | Sentences with a reply cut off | Calls | Seconds | Results file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | 0 | 0 | 1 | 0 | 7 | 0 | 20 | 68.2 | `evals/results/run-20261009T024502Z-writings-first.jsonl` |
| `zero_shot` | 1 | 1 | 29 | 0 | 5 | 0 | 20 | 79.2 | `evals/results/run-20261009T024611Z-writings-zero_shot.jsonl` |
| `persona` | 0 | 0 | 1 | 0 | 7 | 0 | 20 | 79.4 | `evals/results/run-20261009T024737Z-writings-persona.jsonl` |
| `stepwise` | 0 | 0 | 1 | 0 | 6 | 0 | 20 | 124.6 | `evals/results/run-20261009T024858Z-writings-stepwise.jsonl` |
| `price_total` | 0 | 0 | 1 | 0 | 7 | 0 | 20 | 81.4 | `evals/results/run-20261009T025103Z-writings-price_total.jsonl` |

Whole trades right for each way of writing:

| Way of writing | `first` | `zero_shot` | `persona` | `stepwise` | `price_total` |
| --- | --- | --- | --- | --- | --- |
| a gap before a letter multiplier (3 w, 1.5 k) | 3 / 4 (75.0%) | 4 / 4 (100.0%) | 3 / 4 (75.0%) | 2 / 4 (50.0%) | 3 / 4 (75.0%) |
| a gap before a Chinese multiplier (100 万) | 3 / 4 (75.0%) | 2 / 4 (50.0%) | 3 / 4 (75.0%) | 1 / 4 (25.0%) | 3 / 4 (75.0%) |
| a space between thousands (94 900) | 3 / 4 (75.0%) | 3 / 4 (75.0%) | 3 / 4 (75.0%) | 3 / 4 (75.0%) | 3 / 4 (75.0%) |
| two numbers one space apart (0.02 94900) | 3 / 4 (75.0%) | 3 / 4 (75.0%) | 3 / 4 (75.0%) | 2 / 4 (50.0%) | 3 / 4 (75.0%) |
| a full-width comma between digits (94，900; 63,000，1.5) | 3 / 6 (50.0%) | 2 / 6 (33.3%) | 3 / 6 (50.0%) | 4 / 6 (66.7%) | 3 / 6 (50.0%) |

In these 100 sentence runs no model copied only part of a hard number:
not `3` of `3 w`, `900` of `94 900`, nor one number of `0.02 94900`
together with the other. Wherever the gold answer has a phrase for a
number field and the model wrote one, the model's phrase was the gold
phrase (after the scoring's tidying), or the gold phrase without its unit
(`zero_shot` only: `2 w` for `2 w 个 DOGE`, `200 万` for `200 万 SHIB`, 28
such fields, all of them right), except two rewrites in `stepwise`: `5 万
个 DOGE` written as `5 万个 DOGE` in w06 and `6 900` as `6,900` in w12,
neither a piece of the passage, both left empty. The half copy that
`first`, `persona`, `stepwise` and `price_total` each have is the time
`Monday` for `on Monday` (w07), which is right.

The trades not whole, besides the English times written in Chinese (7
fields in `first`, `persona` and `price_total`, 6 in `stepwise`, 5 in
`zero_shot`): in `zero_shot`, the fee left out in w07 and in both trades of
w18, and `1.2 万` put under price as well as under total in w08 (a made-up
price with no issue); in `stepwise`, the time left out in w01 and w05, the
quantity of w06 left empty (above), and in w14 the time put in a second
row of its own.

### `first` against the baseline, sentence by sentence

This run of `first` and the baseline's (2026-10-05) under the same prompt,
model and parameters; the code that reads a reply changed between them (a
full-width comma between two numbers no longer joins them).

| Sentences in both runs | Same raw replies | Other raw replies | Same raw replies, other drafts or issues |
| --- | --- | --- | --- |
| 30 | 30 | 0 | 1 |

| Sentence | Same raw replies | Same drafts and issues | Whole trades right, earlier | Whole trades right, later |
| --- | --- | --- | --- | --- |
| d23 | yes | no | 0 | 2 |

d23 is the passage with `63,000，1.5`: the model wrote the same reply; the
program now takes `63,000` and `1.5 ETH` as they are, and two of its three
trades are whole.

### Parameter comparisons

Each changes one parameter of one version and is not part of the rule.
Each table shows the main run first and the comparison second.

**1. `first`, temperature 0.7** (instead of 0.0): how far the version the
rule picked moves when the model samples more freely.

| Version | Technique | Differs from `first` in | Well-formed | Whole trades right | One trade | Several trades | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | few-shot | the baseline: instructions and ten examples | 26 / 26 (100.0%) | 31 / 34 (91.2%) | 13 / 15 (86.7%) | 18 / 19 (94.7%) | 0 | 0 | 2 / 140 (1.4%) | 3 / 3 (100.0%) |
| `first` | few-shot | the baseline: instructions and ten examples | 26 / 26 (100.0%) | 30 / 34 (88.2%) | 13 / 15 (86.7%) | 17 / 19 (89.5%) | 0 | 0 | 1 / 140 (0.7%) | 3 / 3 (100.0%) |

| Version | Wrong values with no issue | A total put as the price | Half copies (any) | Half copies (not right) | A time in another language | Sentences with a reply cut off | Calls | Seconds | Results file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | 2 | 2 | 0 | 0 | 2 | 0 | 30 | 115.9 | `evals/results/run-20261009T023225Z-debug-first.jsonl` |
| `first` | 1 | 1 | 0 | 0 | 2 | 0 | 30 | 130.6 | `evals/results/run-20261009T025243Z-debug-first.jsonl` |

**2. `stepwise`, longest reply 256 tokens** (instead of 1,024): `stepwise`
writes the longest replies, its analysis coming before the table; its
longest reply in the main run was 297 tokens. This shows what the limit
does when a reply reaches it: the three-trade passages d21, d22 and d23
were cut off, asked again, cut off again, and gave no draft.

| Version | Technique | Differs from `first` in | Well-formed | Whole trades right | One trade | Several trades | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `stepwise` | chain of thought | a step-by-step analysis written before the table | 26 / 26 (100.0%) | 25 / 34 (73.5%) | 10 / 15 (66.7%) | 15 / 19 (78.9%) | 0 | 0 | 1 / 140 (0.7%) | 3 / 3 (100.0%) |
| `stepwise` | chain of thought | a step-by-step analysis written before the table | 23 / 26 (88.5%) | 19 / 34 (55.9%) | 10 / 15 (66.7%) | 9 / 19 (47.4%) | 9 | 0 | 1 / 102 (1.0%) | 3 / 3 (100.0%) |

| Version | Wrong values with no issue | A total put as the price | Half copies (any) | Half copies (not right) | A time in another language | Sentences with a reply cut off | Calls | Seconds | Results file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `stepwise` | 0 | 0 | 0 | 0 | 1 | 0 | 30 | 177.8 | `evals/results/run-20261009T023913Z-debug-stepwise.jsonl` |
| `stepwise` | 0 | 0 | 0 | 0 | 1 | 3 | 33 | 228.6 | `evals/results/run-20261009T025506Z-debug-stepwise.jsonl` |

### The runs

Each run has its own subsection with the tables its results file gives and
its three more counts (`evals/extra_counts.py`).

### Run: debug set, prompt `first`

Results file: `evals/results/run-20261009T023225Z-debug-first.jsonl`, with its summary in `run-20261009T023225Z-debug-first.summary.json`.

<details>
<summary>The generated tables of this run</summary>

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
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| commit | da3aa2c4e54c00f3b2b80862c9ca0bf471962325 |
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
| started_at | 2026-10-09T02:32:25+00:00 |
| sentences | 30 |
| sum_of_sentence_seconds | 115.858 |
| first_sentence_seconds | 6.76 |
| longest_sentence_seconds | 8.71 |
| finished_at | 2026-10-09T02:34:21+00:00 |
| seconds_of_the_last_session | 115.904 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 26 | 26 / 26 (100.0%) | 31 / 34 (91.2%) | 0 | 0 | 2 / 140 (1.4%) | 3 / 3 (100.0%) |
| one trade | 15 | 15 / 15 (100.0%) | 13 / 15 (86.7%) | 0 | 0 | 1 / 60 (1.7%) | 0 / 0 (-) |
| several trades | 8 | 8 / 8 (100.0%) | 18 / 19 (94.7%) | 0 | 0 | 1 / 80 (1.2%) | 0 / 0 (-) |
| - two trades | 5 | 5 / 5 (100.0%) | 10 / 10 (100.0%) | 0 | 0 | 0 / 42 (0.0%) | 0 / 0 (-) |
| - three or more trades | 3 | 3 / 3 (100.0%) | 8 / 9 (88.9%) | 0 | 0 | 1 / 38 (2.6%) | 0 / 0 (-) |
| no trade (talk) | 3 | 3 / 3 (100.0%) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 3 / 3 (100.0%) |
| Chinese | 10 | 10 / 10 (100.0%) | 13 / 13 (100.0%) | 0 | 0 | 0 / 52 (0.0%) | 1 / 1 (100.0%) |
| English | 9 | 9 / 9 (100.0%) | 10 / 12 (83.3%) | 0 | 0 | 1 / 49 (2.0%) | 1 / 1 (100.0%) |
| mixed | 7 | 7 / 7 (100.0%) | 8 / 9 (88.9%) | 0 | 0 | 1 / 39 (2.6%) | 1 / 1 (100.0%) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 34 / 34 (100.0%) |
| coin | 34 / 34 (100.0%) |
| quantity | 33 / 34 (97.1%) |
| price | 32 / 34 (94.1%) |
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
| RIGHT: right | 368 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 3 |
| - because the model's phrase is not a piece of the passage | 3 |
| - because the model's phrase cuts a number of the passage | 0 |
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

#### Fields the program left empty (3; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| d05 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| d13 | 1 | time | 昨天 18:20 | yesterday at 18:20 | NOT_IN_PASSAGE | no |
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
| d23 | mixed | extracted | 3 | 3 | 2 | 0 | 0 | 3.quantity:LEFT_EMPTY_WITH_REASON, 3.price:MADE_UP, 3.total:LEFT_EMPTY_BY_MODEL |
| d24 | zh | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d25 | en | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d26 | mixed | extracted | 0 | 0 | 0 | 0 | 0 | - |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 2 |
| Half copies, any field whose phrase is part of the gold phrase | 0 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 2 |

#### A total put as the price (2; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| d05: Bought 120 ADA for 64.80 USDT total yesterday, fee 0.002 BNB | 1 | price | 64.80 USDT | 64.80 | 64.80 USDT | 64.80 |
| d23: 刚才连着 sell 了三笔：0.1 BTC @ 63,000，1.5 ETH @ 2,410，还有 TON 卖了 200 个，total 1,040 USDT | 3 | price | 1,040 USDT | 1040 | 1,040 USDT | 1040 |

#### Half copies, counted the second way (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |

#### A time written in another language (2)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| d05: Bought 120 ADA for 64.80 USDT total yesterday, fee 0.002 BNB | 1 | time | 昨天 | (empty) | yesterday | 2026-10-04 (day) |
| d13: Picked up 40 LINK at 13.85 yesterday at 18:20 while BTC sat near 61k, fee 0 | 1 | time | 昨天 18:20 | (empty) | yesterday at 18:20 | 2026-10-04T18:20:00+02:00 (minute) |

</details>

### Run: debug set, prompt `zero_shot`

Results file: `evals/results/run-20261009T023459Z-debug-zero_shot.jsonl`, with its summary in `run-20261009T023459Z-debug-zero_shot.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | debug |
| final_exam_switch | False |
| set_file | evals/sets/debug.json |
| set_sha256 | 4529d98323ad1df4d38f5a5b73cdf1082b6a1cd08a0604a454ecf7986104f4d8 |
| prompt | zero_shot |
| prompt file src/ledger_hand/extraction/prompts/zero_shot.py | sha256 b5f309ca198e98cef953f38cd62cbffafe65cb6e7fc036371e5deaf1392b54a5 |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt_content_sha256 | f2d6c2b077e3a8a7d6bee5c2aeb7bb6eaf1588f73a1c93d21668c6f4f9569c88 |
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| commit | 5907cf0f722e1bde124a0b78dd6f3460c875a784 |
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
| started_at | 2026-10-09T02:34:59+00:00 |
| sentences | 30 |
| sum_of_sentence_seconds | 116.209 |
| first_sentence_seconds | 3.708 |
| longest_sentence_seconds | 10.257 |
| finished_at | 2026-10-09T02:36:55+00:00 |
| seconds_of_the_last_session | 116.261 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 26 | 26 / 26 (100.0%) | 19 / 34 (55.9%) | 0 | 0 | 5 / 140 (3.6%) | 3 / 3 (100.0%) |
| one trade | 15 | 15 / 15 (100.0%) | 8 / 15 (53.3%) | 0 | 0 | 3 / 60 (5.0%) | 0 / 0 (-) |
| several trades | 8 | 8 / 8 (100.0%) | 11 / 19 (57.9%) | 0 | 0 | 2 / 80 (2.5%) | 0 / 0 (-) |
| - two trades | 5 | 5 / 5 (100.0%) | 8 / 10 (80.0%) | 0 | 0 | 0 / 42 (0.0%) | 0 / 0 (-) |
| - three or more trades | 3 | 3 / 3 (100.0%) | 3 / 9 (33.3%) | 0 | 0 | 2 / 38 (5.3%) | 0 / 0 (-) |
| no trade (talk) | 3 | 3 / 3 (100.0%) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 3 / 3 (100.0%) |
| Chinese | 10 | 10 / 10 (100.0%) | 9 / 13 (69.2%) | 0 | 0 | 1 / 52 (1.9%) | 1 / 1 (100.0%) |
| English | 9 | 9 / 9 (100.0%) | 6 / 12 (50.0%) | 0 | 0 | 2 / 49 (4.1%) | 1 / 1 (100.0%) |
| mixed | 7 | 7 / 7 (100.0%) | 4 / 9 (44.4%) | 0 | 0 | 2 / 39 (5.1%) | 1 / 1 (100.0%) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 34 / 34 (100.0%) |
| coin | 33 / 34 (97.1%) |
| quantity | 33 / 34 (97.1%) |
| price | 30 / 34 (88.2%) |
| total | 34 / 34 (100.0%) |
| price_currency | 31 / 34 (91.2%) |
| fee | 33 / 34 (97.1%) |
| fee_currency | 34 / 34 (100.0%) |
| time | 23 / 34 (67.6%) |
| platform | 34 / 34 (100.0%) |
| opinion | 34 / 34 (100.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 353 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 6 |
| - because the model's phrase is not a piece of the passage | 2 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 4 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 10 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 5 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (5)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |
| d02: Sold 2.5 ETH at 2,415.30 on Coinbase 3 hours ago, paid 1.21 USDT in fees | 1 | price_currency | USDT | USDT | (empty) | MADE_UP |
| d08: Sold 3 at 4,120 this morning, fee 0.9 USDT | 1 | coin | 3 | 3 | (empty) | MADE_UP |
| d14: 昨天花了 500 刀买大饼，手续费 0.5 刀 | 1 | quantity | 500 | 500 | (empty) | MADE_UP |
| d23: 刚才连着 sell 了三笔：0.1 BTC @ 63,000，1.5 ETH @ 2,410，还有 TON 卖了 200 个，total 1,040 USDT | 1 | price_currency | USD | USD | (empty) | MADE_UP |
| d23: 刚才连着 sell 了三笔：0.1 BTC @ 63,000，1.5 ETH @ 2,410，还有 TON 卖了 200 个，total 1,040 USDT | 2 | price_currency | USD | USD | (empty) | MADE_UP |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (6; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| d05 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| d09 | 1 | price | 0.000012一个 | 0.000012 | NUMBER_NOT_READ | no |
| d15 | 1 | time | 昨天晚上 9 点 40 | 9:40 | NOT_IN_PASSAGE | no |
| d21 | 1 | price | 13.6 一个 | 13.6 | NUMBER_NOT_READ | no |
| d21 | 2 | price | 26.1 一个 | 26.1 | NUMBER_NOT_READ | no |
| d21 | 3 | price | 1.73 一个 | 1.73 | NUMBER_NOT_READ | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |
| d27: 昨天开了 10 倍杠杆做多 BTC，开仓价 62,800，保证金 200U | futures_or_leverage | extracted | 1 | draft 1: stopped by ONE_MORE_OF_QUANTITY_PRICE_TOTAL, FEE |
| d28: Swapped 0.5 ETH for 0.019 BTC on Uniswap this morning | coin_for_coin | extracted | 1 | draft 1: stopped by FEE, UNSUPPORTED_QUOTE |
| d29: 挂了一个 limit buy，0.05 BTC @ 58,000，还没成交 | open_order | extracted | 0 | - |
| d30: 打算明天下午 3 点买 1 个 ETH，价格到 2,300 就进 | plan | extracted | 0 | - |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| d01 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d02 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.price_currency:MADE_UP |
| d03 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d04 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d05 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| d06 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d07 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d08 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.coin:MADE_UP |
| d09 | mixed | extracted | 1 | 1 | 0 | 0 | 0 | 1.price:LEFT_EMPTY_WITH_REASON, 1.time:LEFT_EMPTY_BY_MODEL |
| d10 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d11 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d12 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d13 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.fee:LEFT_EMPTY_BY_MODEL |
| d14 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.quantity:MADE_UP |
| d15 | mixed | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| d16 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d17 | en | extracted | 2 | 2 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_BY_MODEL, 2.time:LEFT_EMPTY_BY_MODEL |
| d18 | mixed | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d19 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d20 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d21 | zh | extracted | 3 | 3 | 0 | 0 | 0 | 1.price:LEFT_EMPTY_WITH_REASON, 1.time:LEFT_EMPTY_BY_MODEL, 2.price:LEFT_EMPTY_WITH_REASON, 2.time:LEFT_EMPTY_BY_MODEL, 3.price:LEFT_EMPTY_WITH_REASON, 3.time:LEFT_EMPTY_BY_MODEL |
| d22 | en | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d23 | mixed | extracted | 3 | 3 | 0 | 0 | 0 | 1.price_currency:MADE_UP, 1.time:LEFT_EMPTY_BY_MODEL, 2.price_currency:MADE_UP, 2.time:LEFT_EMPTY_BY_MODEL, 3.time:LEFT_EMPTY_BY_MODEL |
| d24 | zh | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d25 | en | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d26 | mixed | extracted | 0 | 0 | 0 | 0 | 0 | - |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 42 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 2 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (42)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| d01: 昨晚 8 点 15 分在币安入了 0.05 个 BTC，成交价 63,480，手续费 1.6 USDT，这个位置我觉得不亏 | 1 | quantity | 0.05 个 | 0.05 | 0.05 个 BTC | 0.05 | yes |
| d02: Sold 2.5 ETH at 2,415.30 on Coinbase 3 hours ago, paid 1.21 USDT in fees | 1 | quantity | 2.5 | 2.5 | 2.5 ETH | 2.5 | yes |
| d02: Sold 2.5 ETH at 2,415.30 on Coinbase 3 hours ago, paid 1.21 USDT in fees | 1 | fee | 1.21 | 1.21 | 1.21 USDT | 1.21 | yes |
| d03: 今天下午 4 点 buy 了 0.1 BTC，单价 6.2万，手续费 0 | 1 | quantity | 0.1 | 0.1 | 0.1 BTC | 0.1 | yes |
| d04: 在 OKX 把 0.3 个比特币卖了，价格六万三千五，手续费 2.4U | 1 | quantity | 0.3 | 0.3 | 0.3 个比特币 | 0.3 | yes |
| d05: Bought 120 ADA for 64.80 USDT total yesterday, fee 0.002 BNB | 1 | quantity | 120 | 120 | 120 ADA | 120 | yes |
| d05: Bought 120 ADA for 64.80 USDT total yesterday, fee 0.002 BNB | 1 | fee | 0.002 | 0.002 | 0.002 BNB | 0.002 | yes |
| d06: 10 月 2 号 14:05 在 Bybit 花 1,500 USDT 买了 SOL，price 150，fee 0.01 SOL | 1 | fee | 0.01 | 0.01 | 0.01 SOL | 0.01 | yes |
| d08: Sold 3 at 4,120 this morning, fee 0.9 USDT | 1 | fee | 0.9 | 0.9 | 0.9 USDT | 0.9 | yes |
| d09: 刚刚 bought 100 万 SHIB，0.000012一个，fee 0.5 U | 1 | quantity | 100 万 | 1000000 | 100 万 SHIB | 1000000 | yes |
| d09: 刚刚 bought 100 万 SHIB，0.000012一个，fee 0.5 U | 1 | fee | 0.5 | 0.5 | 0.5 U | 0.5 | yes |
| d10: 上周五下午三点买了 0.01 BTC，价格 94 900，手续费 0.95 USDT | 1 | fee | 0.95 | 0.95 | 0.95 USDT | 0.95 | yes |
| d11: bought BTC 0.02 94900 on Kraken Oct 3, fee 1.9 USDT | 1 | fee | 1.9 | 1.9 | 1.9 USDT | 1.9 | yes |
| d12: 今天上午卖了 3 w DOGE，单价 0.21，手续费 1.3U | 1 | quantity | 3 w | (empty) | 3 w DOGE | (empty) | yes |
| d13: Picked up 40 LINK at 13.85 yesterday at 18:20 while BTC sat near 61k, fee 0 | 1 | quantity | 40 | 40 | 40 LINK | 40 | yes |
| d15: 9:40 卖了 15 SOL @ 152.6，fee 0.8 USDT，先落袋为安 | 1 | quantity | 15 | 15 | 15 SOL | 15 | yes |
| d15: 9:40 卖了 15 SOL @ 152.6，fee 0.8 USDT，先落袋为安 | 1 | fee | 0.8 | 0.8 | 0.8 USDT | 0.8 | yes |
| d16: 今天中午在币安先后买了两次：0.4 个 BNB 单价 585，还有 20 个 DOT 单价 4.2，手续费都按 0.1 USDT 算 | 1 | quantity | 0.4 个 | 0.4 | 0.4 个 BNB | 0.4 | yes |
| d16: 今天中午在币安先后买了两次：0.4 个 BNB 单价 585，还有 20 个 DOT 单价 4.2，手续费都按 0.1 USDT 算 | 2 | quantity | 20 个 | 20 | 20 个 DOT | 20 | yes |
| d17: Today on Binance I sold 0.8 ETH at 2,402 and bought 150 XRP at 0.588, fee 0.5 USDT each | 1 | quantity | 0.8 | 0.8 | 0.8 ETH | 0.8 | yes |
| d17: Today on Binance I sold 0.8 ETH at 2,402 and bought 150 XRP at 0.588, fee 0.5 USDT each | 1 | fee | 0.5 | 0.5 | 0.5 USDT | 0.5 | yes |
| d17: Today on Binance I sold 0.8 ETH at 2,402 and bought 150 XRP at 0.588, fee 0.5 USDT each | 2 | quantity | 150 | 150 | 150 XRP | 150 | yes |
| d17: Today on Binance I sold 0.8 ETH at 2,402 and bought 150 XRP at 0.588, fee 0.5 USDT each | 2 | fee | 0.5 | 0.5 | 0.5 USDT | 0.5 | yes |
| d18: 昨天下午 3 点 sold 0.02 BTC at 63,900，今天早上 9 点又 buy back 0.025 BTC at 62,750，fee 都是 1.2U | 1 | quantity | 0.02 | 0.02 | 0.02 BTC | 0.02 | yes |
| d18: 昨天下午 3 点 sold 0.02 BTC at 63,900，今天早上 9 点又 buy back 0.025 BTC at 62,750，fee 都是 1.2U | 2 | quantity | 0.025 | 0.025 | 0.025 BTC | 0.025 | yes |
| d19: 9 月 30 号在 Kraken 卖了两样：2 个 ETH，价格两千四百五；1 万个 DOGE，单价 0.2 | 1 | quantity | 2 个 | 2 | 2 个 ETH | 2 | yes |
| d19: 9 月 30 号在 Kraken 卖了两样：2 个 ETH，价格两千四百五；1 万个 DOGE，单价 0.2 | 2 | quantity | 1 万个 | 10000 | 1 万个 DOGE | 10000 | yes |
| d20: Bought 0.3 BTC at 61,200 and 5 ETH at 2,390 last Saturday | 1 | quantity | 0.3 | 0.3 | 0.3 BTC | 0.3 | yes |
| d20: Bought 0.3 BTC at 61,200 and 5 ETH at 2,390 last Saturday | 2 | quantity | 5 | 5 | 5 ETH | 5 | yes |
| d21: 今天在 Bitget 调仓：卖了 50 个 LINK，13.6 一个；买了 2 个 AVAX，26.1 一个；又买了 100 个 OP，1.73 一个。每笔手续费 0.1U | 1 | quantity | 50 个 | 50 | 50 个 LINK | 50 | yes |
| d21: 今天在 Bitget 调仓：卖了 50 个 LINK，13.6 一个；买了 2 个 AVAX，26.1 一个；又买了 100 个 OP，1.73 一个。每笔手续费 0.1U | 2 | quantity | 2 个 | 2 | 2 个 AVAX | 2 | yes |
| d21: 今天在 Bitget 调仓：卖了 50 个 LINK，13.6 一个；买了 2 个 AVAX，26.1 一个；又买了 100 个 OP，1.73 一个。每笔手续费 0.1U | 3 | quantity | 100 个 | 100 | 100 个 OP | 100 | yes |
| d22: Yesterday at 10:30 I bought 1 ETH at 2,350, 0.05 BTC at 62,100 and 20 SOL at 149.5, paying a flat 1 USDT fee on each | 1 | quantity | 1 | 1 | 1 ETH | 1 | yes |
| d22: Yesterday at 10:30 I bought 1 ETH at 2,350, 0.05 BTC at 62,100 and 20 SOL at 149.5, paying a flat 1 USDT fee on each | 1 | fee | 1 | 1 | 1 USDT | 1 | yes |
| d22: Yesterday at 10:30 I bought 1 ETH at 2,350, 0.05 BTC at 62,100 and 20 SOL at 149.5, paying a flat 1 USDT fee on each | 2 | quantity | 0.05 | 0.05 | 0.05 BTC | 0.05 | yes |
| d22: Yesterday at 10:30 I bought 1 ETH at 2,350, 0.05 BTC at 62,100 and 20 SOL at 149.5, paying a flat 1 USDT fee on each | 2 | fee | 1 | 1 | 1 USDT | 1 | yes |
| d22: Yesterday at 10:30 I bought 1 ETH at 2,350, 0.05 BTC at 62,100 and 20 SOL at 149.5, paying a flat 1 USDT fee on each | 3 | quantity | 20 | 20 | 20 SOL | 20 | yes |
| d22: Yesterday at 10:30 I bought 1 ETH at 2,350, 0.05 BTC at 62,100 and 20 SOL at 149.5, paying a flat 1 USDT fee on each | 3 | fee | 1 | 1 | 1 USDT | 1 | yes |
| d23: 刚才连着 sell 了三笔：0.1 BTC @ 63,000，1.5 ETH @ 2,410，还有 TON 卖了 200 个，total 1,040 USDT | 1 | quantity | 0.1 | 0.1 | 0.1 BTC | 0.1 | yes |
| d23: 刚才连着 sell 了三笔：0.1 BTC @ 63,000，1.5 ETH @ 2,410，还有 TON 卖了 200 个，total 1,040 USDT | 2 | quantity | 1.5 | 1.5 | 1.5 ETH | 1.5 | yes |
| d23: 刚才连着 sell 了三笔：0.1 BTC @ 63,000，1.5 ETH @ 2,410，还有 TON 卖了 200 个，total 1,040 USDT | 3 | quantity | 200 | 200 | 200 个 | 200 | yes |
| d23: 刚才连着 sell 了三笔：0.1 BTC @ 63,000，1.5 ETH @ 2,410，还有 TON 卖了 200 个，total 1,040 USDT | 3 | price_currency | USD | USD | USDT | USDT | yes |

#### A time written in another language (2)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| d05: Bought 120 ADA for 64.80 USDT total yesterday, fee 0.002 BNB | 1 | time | 昨天 | (empty) | yesterday | 2026-10-04 (day) |
| d15: 9:40 卖了 15 SOL @ 152.6，fee 0.8 USDT，先落袋为安 | 1 | time | 昨天晚上 9 点 40 | (empty) | 9:40 | 2026-10-05T09:40:00+02:00 (minute) |

</details>

### Run: debug set, prompt `persona`

Results file: `evals/results/run-20261009T023708Z-debug-persona.jsonl`, with its summary in `run-20261009T023708Z-debug-persona.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | debug |
| final_exam_switch | False |
| set_file | evals/sets/debug.json |
| set_sha256 | 4529d98323ad1df4d38f5a5b73cdf1082b6a1cd08a0604a454ecf7986104f4d8 |
| prompt | persona |
| prompt file src/ledger_hand/extraction/prompts/persona.py | sha256 5d43341346f6e0a6e298640144807ded0f9e93797ebbac094e70ec1458086940 |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | 0e33c465f66b25dec176b39404a451ee5bffc8f35751a275ee8753564335fb42 |
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| commit | 1cf4ad691c3394f273752f21d00d80349c8ac3ac |
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
| started_at | 2026-10-09T02:37:08+00:00 |
| sentences | 30 |
| sum_of_sentence_seconds | 119.329 |
| first_sentence_seconds | 7.046 |
| longest_sentence_seconds | 9.018 |
| finished_at | 2026-10-09T02:39:07+00:00 |
| seconds_of_the_last_session | 119.377 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 26 | 26 / 26 (100.0%) | 29 / 34 (85.3%) | 0 | 0 | 3 / 140 (2.1%) | 3 / 3 (100.0%) |
| one trade | 15 | 15 / 15 (100.0%) | 12 / 15 (80.0%) | 0 | 0 | 2 / 60 (3.3%) | 0 / 0 (-) |
| several trades | 8 | 8 / 8 (100.0%) | 17 / 19 (89.5%) | 0 | 0 | 1 / 80 (1.2%) | 0 / 0 (-) |
| - two trades | 5 | 5 / 5 (100.0%) | 9 / 10 (90.0%) | 0 | 0 | 0 / 42 (0.0%) | 0 / 0 (-) |
| - three or more trades | 3 | 3 / 3 (100.0%) | 8 / 9 (88.9%) | 0 | 0 | 1 / 38 (2.6%) | 0 / 0 (-) |
| no trade (talk) | 3 | 3 / 3 (100.0%) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 3 / 3 (100.0%) |
| Chinese | 10 | 10 / 10 (100.0%) | 12 / 13 (92.3%) | 0 | 0 | 0 / 52 (0.0%) | 1 / 1 (100.0%) |
| English | 9 | 9 / 9 (100.0%) | 9 / 12 (75.0%) | 0 | 0 | 2 / 49 (4.1%) | 1 / 1 (100.0%) |
| mixed | 7 | 7 / 7 (100.0%) | 8 / 9 (88.9%) | 0 | 0 | 1 / 39 (2.6%) | 1 / 1 (100.0%) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 34 / 34 (100.0%) |
| coin | 33 / 34 (97.1%) |
| quantity | 33 / 34 (97.1%) |
| price | 31 / 34 (91.2%) |
| total | 32 / 34 (94.1%) |
| price_currency | 34 / 34 (100.0%) |
| fee | 34 / 34 (100.0%) |
| fee_currency | 34 / 34 (100.0%) |
| time | 32 / 34 (94.1%) |
| platform | 34 / 34 (100.0%) |
| opinion | 34 / 34 (100.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 365 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 4 |
| - because the model's phrase is not a piece of the passage | 4 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 2 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 3 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (3)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |
| d05: Bought 120 ADA for 64.80 USDT total yesterday, fee 0.002 BNB | 1 | price | 64.80 USDT | 64.80 | (empty) | MADE_UP |
| d08: Sold 3 at 4,120 this morning, fee 0.9 USDT | 1 | coin | 3 | 3 | (empty) | MADE_UP |
| d23: 刚才连着 sell 了三笔：0.1 BTC @ 63,000，1.5 ETH @ 2,410，还有 TON 卖了 200 个，total 1,040 USDT | 3 | price | 1,040 USDT | 1040 | (empty) | MADE_UP |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (4; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| d05 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| d13 | 1 | time | 昨天 18:20 | yesterday at 18:20 | NOT_IN_PASSAGE | no |
| d19 | 1 | price | 2,450 | 两千四百五 | NOT_IN_PASSAGE | no |
| d23 | 3 | quantity | 200 个 TON | 200 个 | NOT_IN_PASSAGE | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |
| d27: 昨天开了 10 倍杠杆做多 BTC，开仓价 62,800，保证金 200U | futures_or_leverage | extracted | 1 | draft 1: stopped by SIDE, ONE_MORE_OF_QUANTITY_PRICE_TOTAL, FEE |
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
| d05 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.price:MADE_UP, 1.total:LEFT_EMPTY_BY_MODEL, 1.time:LEFT_EMPTY_WITH_REASON |
| d06 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d07 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d08 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.coin:MADE_UP |
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
| d19 | zh | extracted | 2 | 2 | 1 | 0 | 0 | 1.price:LEFT_EMPTY_WITH_REASON |
| d20 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d21 | zh | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d22 | en | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d23 | mixed | extracted | 3 | 3 | 2 | 0 | 0 | 3.quantity:LEFT_EMPTY_WITH_REASON, 3.price:MADE_UP, 3.total:LEFT_EMPTY_BY_MODEL |
| d24 | zh | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d25 | en | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d26 | mixed | extracted | 0 | 0 | 0 | 0 | 0 | - |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 2 |
| Half copies, any field whose phrase is part of the gold phrase | 0 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 2 |

#### A total put as the price (2; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| d05: Bought 120 ADA for 64.80 USDT total yesterday, fee 0.002 BNB | 1 | price | 64.80 USDT | 64.80 | 64.80 USDT | 64.80 |
| d23: 刚才连着 sell 了三笔：0.1 BTC @ 63,000，1.5 ETH @ 2,410，还有 TON 卖了 200 个，total 1,040 USDT | 3 | price | 1,040 USDT | 1040 | 1,040 USDT | 1040 |

#### Half copies, counted the second way (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |

#### A time written in another language (2)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| d05: Bought 120 ADA for 64.80 USDT total yesterday, fee 0.002 BNB | 1 | time | 昨天 | (empty) | yesterday | 2026-10-04 (day) |
| d13: Picked up 40 LINK at 13.85 yesterday at 18:20 while BTC sat near 61k, fee 0 | 1 | time | 昨天 18:20 | (empty) | yesterday at 18:20 | 2026-10-04T18:20:00+02:00 (minute) |

</details>

### Run: debug set, prompt `stepwise`

Results file: `evals/results/run-20261009T023913Z-debug-stepwise.jsonl`, with its summary in `run-20261009T023913Z-debug-stepwise.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | debug |
| final_exam_switch | False |
| set_file | evals/sets/debug.json |
| set_sha256 | 4529d98323ad1df4d38f5a5b73cdf1082b6a1cd08a0604a454ecf7986104f4d8 |
| prompt | stepwise |
| prompt file src/ledger_hand/extraction/prompts/stepwise.py | sha256 ade615b5113708fa8356a35b6e21fbc40bfd1c0666bb22b8eaaf6cbfcf49ca99 |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | 2f47a7ac7368b04d5dbbf112ceebf83cdc0963e6996c464c21ef836096380768 |
| reply_table_sha256 | c822392c150e388a3bef711e3af1c43e4dd73329b118145b1e8a1308f4dfae89 |
| commit | 899e9fb9a3429739ad775e025a94911206021fd9 |
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
| started_at | 2026-10-09T02:39:13+00:00 |
| sentences | 30 |
| sum_of_sentence_seconds | 177.819 |
| first_sentence_seconds | 8.061 |
| longest_sentence_seconds | 12.574 |
| finished_at | 2026-10-09T02:42:10+00:00 |
| seconds_of_the_last_session | 177.873 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 26 | 26 / 26 (100.0%) | 25 / 34 (73.5%) | 0 | 0 | 1 / 140 (0.7%) | 3 / 3 (100.0%) |
| one trade | 15 | 15 / 15 (100.0%) | 10 / 15 (66.7%) | 0 | 0 | 1 / 60 (1.7%) | 0 / 0 (-) |
| several trades | 8 | 8 / 8 (100.0%) | 15 / 19 (78.9%) | 0 | 0 | 0 / 80 (0.0%) | 0 / 0 (-) |
| - two trades | 5 | 5 / 5 (100.0%) | 9 / 10 (90.0%) | 0 | 0 | 0 / 42 (0.0%) | 0 / 0 (-) |
| - three or more trades | 3 | 3 / 3 (100.0%) | 6 / 9 (66.7%) | 0 | 0 | 0 / 38 (0.0%) | 0 / 0 (-) |
| no trade (talk) | 3 | 3 / 3 (100.0%) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 3 / 3 (100.0%) |
| Chinese | 10 | 10 / 10 (100.0%) | 6 / 13 (46.2%) | 0 | 0 | 1 / 52 (1.9%) | 1 / 1 (100.0%) |
| English | 9 | 9 / 9 (100.0%) | 11 / 12 (91.7%) | 0 | 0 | 0 / 49 (0.0%) | 1 / 1 (100.0%) |
| mixed | 7 | 7 / 7 (100.0%) | 8 / 9 (88.9%) | 0 | 0 | 0 / 39 (0.0%) | 1 / 1 (100.0%) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 31 / 34 (91.2%) |
| coin | 34 / 34 (100.0%) |
| quantity | 33 / 34 (97.1%) |
| price | 32 / 34 (94.1%) |
| total | 34 / 34 (100.0%) |
| price_currency | 34 / 34 (100.0%) |
| fee | 34 / 34 (100.0%) |
| fee_currency | 34 / 34 (100.0%) |
| time | 29 / 34 (85.3%) |
| platform | 34 / 34 (100.0%) |
| opinion | 34 / 34 (100.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 363 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 3 |
| - because the model's phrase is not a piece of the passage | 3 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 7 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 1 |
| - of them with an issue about the field | 1 |

#### Wrong values in drafts with no issue about them (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (3; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| d04 | 1 | price | 63,500 | 六万三千五 | NOT_IN_PASSAGE | no |
| d13 | 1 | time | 昨天 18:20 | yesterday at 18:20 | NOT_IN_PASSAGE | no |
| d19 | 1 | price | 2,450 | 两千四百五 | NOT_IN_PASSAGE | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |
| d27: 昨天开了 10 倍杠杆做多 BTC，开仓价 62,800，保证金 200U | futures_or_leverage | extracted | 1 | draft 1: stopped by ONE_MORE_OF_QUANTITY_PRICE_TOTAL, FEE |
| d28: Swapped 0.5 ETH for 0.019 BTC on Uniswap this morning | coin_for_coin | extracted | 1 | draft 1: stopped by ONE_MORE_OF_QUANTITY_PRICE_TOTAL, FEE |
| d29: 挂了一个 limit buy，0.05 BTC @ 58,000，还没成交 | open_order | extracted | 1 | draft 1: stopped by SIDE, FEE, OCCURRED |
| d30: 打算明天下午 3 点买 1 个 ETH，价格到 2,300 就进 | plan | extracted | 0 | - |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| d01 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d02 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d03 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d04 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.price:LEFT_EMPTY_WITH_REASON |
| d05 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d06 | mixed | extracted | 1 | 1 | 0 | 0 | 0 | 1.side:LEFT_EMPTY_BY_MODEL |
| d07 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.side:LEFT_EMPTY_BY_MODEL, 1.time:LEFT_EMPTY_BY_MODEL |
| d08 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d09 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d10 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d11 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d12 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d13 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| d14 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.side:LEFT_EMPTY_BY_MODEL, 1.quantity:MADE_UP |
| d15 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d16 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d17 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d18 | mixed | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d19 | zh | extracted | 2 | 2 | 1 | 0 | 0 | 1.price:LEFT_EMPTY_WITH_REASON |
| d20 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d21 | zh | extracted | 3 | 3 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_BY_MODEL, 2.time:LEFT_EMPTY_BY_MODEL, 3.time:LEFT_EMPTY_BY_MODEL |
| d22 | en | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d23 | mixed | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d24 | zh | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d25 | en | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d26 | mixed | extracted | 0 | 0 | 0 | 0 | 0 | - |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 0 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 1 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |

#### A time written in another language (1)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| d13: Picked up 40 LINK at 13.85 yesterday at 18:20 while BTC sat near 61k, fee 0 | 1 | time | 昨天 18:20 | (empty) | yesterday at 18:20 | 2026-10-04T18:20:00+02:00 (minute) |

</details>

### Run: debug set, prompt `price_total`

Results file: `evals/results/run-20261009T024223Z-debug-price_total.jsonl`, with its summary in `run-20261009T024223Z-debug-price_total.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | debug |
| final_exam_switch | False |
| set_file | evals/sets/debug.json |
| set_sha256 | 4529d98323ad1df4d38f5a5b73cdf1082b6a1cd08a0604a454ecf7986104f4d8 |
| prompt | price_total |
| prompt file src/ledger_hand/extraction/prompts/price_total.py | sha256 1fe1993962a398131dc6c02f26c4c33dd772ea9750ab5aa73c10b686061ec745 |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | cfc0d1a883062284a83ad8e25962d1e4a5634b17320388ee47da920821da9ec8 |
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| commit | 60ace80a5c1903c87c40e0ca25a7029afab88d80 |
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
| started_at | 2026-10-09T02:42:23+00:00 |
| sentences | 30 |
| sum_of_sentence_seconds | 127.598 |
| first_sentence_seconds | 6.558 |
| longest_sentence_seconds | 10.007 |
| finished_at | 2026-10-09T02:44:30+00:00 |
| seconds_of_the_last_session | 127.65 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 26 | 26 / 26 (100.0%) | 29 / 34 (85.3%) | 0 | 0 | 0 / 140 (0.0%) | 3 / 3 (100.0%) |
| one trade | 15 | 15 / 15 (100.0%) | 12 / 15 (80.0%) | 0 | 0 | 0 / 60 (0.0%) | 0 / 0 (-) |
| several trades | 8 | 8 / 8 (100.0%) | 17 / 19 (89.5%) | 0 | 0 | 0 / 80 (0.0%) | 0 / 0 (-) |
| - two trades | 5 | 5 / 5 (100.0%) | 9 / 10 (90.0%) | 0 | 0 | 0 / 42 (0.0%) | 0 / 0 (-) |
| - three or more trades | 3 | 3 / 3 (100.0%) | 8 / 9 (88.9%) | 0 | 0 | 0 / 38 (0.0%) | 0 / 0 (-) |
| no trade (talk) | 3 | 3 / 3 (100.0%) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 3 / 3 (100.0%) |
| Chinese | 10 | 10 / 10 (100.0%) | 12 / 13 (92.3%) | 0 | 0 | 0 / 52 (0.0%) | 1 / 1 (100.0%) |
| English | 9 | 9 / 9 (100.0%) | 9 / 12 (75.0%) | 0 | 0 | 0 / 49 (0.0%) | 1 / 1 (100.0%) |
| mixed | 7 | 7 / 7 (100.0%) | 8 / 9 (88.9%) | 0 | 0 | 0 / 39 (0.0%) | 1 / 1 (100.0%) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 34 / 34 (100.0%) |
| coin | 34 / 34 (100.0%) |
| quantity | 32 / 34 (94.1%) |
| price | 32 / 34 (94.1%) |
| total | 34 / 34 (100.0%) |
| price_currency | 34 / 34 (100.0%) |
| fee | 34 / 34 (100.0%) |
| fee_currency | 34 / 34 (100.0%) |
| time | 32 / 34 (94.1%) |
| platform | 34 / 34 (100.0%) |
| opinion | 34 / 34 (100.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 368 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 5 |
| - because the model's phrase is not a piece of the passage | 4 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 1 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 1 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 0 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (5; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| d05 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| d11 | 1 | quantity | 0.02 94900 | 0.02 | NUMBER_NOT_READ | no |
| d13 | 1 | time | 昨天 18:20 | yesterday at 18:20 | NOT_IN_PASSAGE | no |
| d19 | 1 | price | 2,450 | 两千四百五 | NOT_IN_PASSAGE | no |
| d23 | 3 | quantity | 200 个 TON | 200 个 | NOT_IN_PASSAGE | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |
| d27: 昨天开了 10 倍杠杆做多 BTC，开仓价 62,800，保证金 200U | futures_or_leverage | extracted | 1 | draft 1: stopped by SIDE, ONE_MORE_OF_QUANTITY_PRICE_TOTAL, FEE |
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
| d05 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| d06 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d07 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d08 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d09 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d10 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d11 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.quantity:LEFT_EMPTY_WITH_REASON, 1.price:LEFT_EMPTY_BY_MODEL |
| d12 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d13 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| d14 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d15 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d16 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d17 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d18 | mixed | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d19 | zh | extracted | 2 | 2 | 1 | 0 | 0 | 1.price:LEFT_EMPTY_WITH_REASON |
| d20 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d21 | zh | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d22 | en | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d23 | mixed | extracted | 3 | 3 | 2 | 0 | 0 | 3.quantity:LEFT_EMPTY_WITH_REASON |
| d24 | zh | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d25 | en | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d26 | mixed | extracted | 0 | 0 | 0 | 0 | 0 | - |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 0 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 2 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |

#### A time written in another language (2)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| d05: Bought 120 ADA for 64.80 USDT total yesterday, fee 0.002 BNB | 1 | time | 昨天 | (empty) | yesterday | 2026-10-04 (day) |
| d13: Picked up 40 LINK at 13.85 yesterday at 18:20 while BTC sat near 61k, fee 0 | 1 | time | 昨天 18:20 | (empty) | yesterday at 18:20 | 2026-10-04T18:20:00+02:00 (minute) |

</details>

### Run: writings set, prompt `first`

Results file: `evals/results/run-20261009T024502Z-writings-first.jsonl`, with its summary in `run-20261009T024502Z-writings-first.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | writings |
| final_exam_switch | False |
| set_file | evals/sets/writings.json |
| set_sha256 | 7ac6a2027ec4434f140db02e51a3a46ca27da7dc89da06b3088866351f38ffce |
| prompt | first |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | 7a510f4aaf16f7830ea5df2ec2071a276006565014e61bf295aa44a57a297112 |
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| commit | fb1f927a42b83b9c39df66273d092567bf3830a8 |
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
| started_at | 2026-10-09T02:45:02+00:00 |
| sentences | 20 |
| sum_of_sentence_seconds | 68.166 |
| first_sentence_seconds | 5.213 |
| longest_sentence_seconds | 5.749 |
| finished_at | 2026-10-09T02:46:10+00:00 |
| seconds_of_the_last_session | 68.198 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 20 | 20 / 20 (100.0%) | 15 / 22 (68.2%) | 0 | 0 | 0 / 93 (0.0%) | 0 / 0 (-) |
| one trade | 18 | 18 / 18 (100.0%) | 13 / 18 (72.2%) | 0 | 0 | 0 / 77 (0.0%) | 0 / 0 (-) |
| several trades | 2 | 2 / 2 (100.0%) | 2 / 4 (50.0%) | 0 | 0 | 0 / 16 (0.0%) | 0 / 0 (-) |
| - two trades | 2 | 2 / 2 (100.0%) | 2 / 4 (50.0%) | 0 | 0 | 0 / 16 (0.0%) | 0 / 0 (-) |
| - three or more trades | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| no trade (talk) | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| Chinese | 8 | 8 / 8 (100.0%) | 9 / 9 (100.0%) | 0 | 0 | 0 / 38 (0.0%) | 0 / 0 (-) |
| English | 10 | 10 / 10 (100.0%) | 4 / 11 (36.4%) | 0 | 0 | 0 / 46 (0.0%) | 0 / 0 (-) |
| mixed | 2 | 2 / 2 (100.0%) | 2 / 2 (100.0%) | 0 | 0 | 0 / 9 (0.0%) | 0 / 0 (-) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 22 / 22 (100.0%) |
| coin | 22 / 22 (100.0%) |
| quantity | 22 / 22 (100.0%) |
| price | 22 / 22 (100.0%) |
| total | 22 / 22 (100.0%) |
| price_currency | 22 / 22 (100.0%) |
| fee | 22 / 22 (100.0%) |
| fee_currency | 22 / 22 (100.0%) |
| time | 15 / 22 (68.2%) |
| platform | 22 / 22 (100.0%) |
| opinion | 22 / 22 (100.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 235 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 7 |
| - because the model's phrase is not a piece of the passage | 7 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 0 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 0 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (7; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| w04 | 1 | time | 昨天 15:20 | yesterday at 15:20 | NOT_IN_PASSAGE | no |
| w08 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| w12 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| w16 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| w19 | 1 | time | 今天 | today | NOT_IN_PASSAGE | no |
| w20 | 1 | time | 今天 | today | NOT_IN_PASSAGE | no |
| w20 | 2 | time | 今天 | today | NOT_IN_PASSAGE | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| w01 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w02 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w03 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w04 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w05 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w06 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w07 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w08 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w09 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w10 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w11 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w12 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w13 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w14 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w15 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w16 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w17 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w18 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| w19 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w20 | en | extracted | 2 | 2 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON, 2.time:LEFT_EMPTY_WITH_REASON |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 1 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 7 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (1)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| w07: Picked up 50 万 PEPE at 0.0000098 on Monday, fee 0 | 1 | time | Monday | 2026-10-05 (day) | on Monday | 2026-10-05 (day) | yes |

#### A time written in another language (7)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| w04: Sold 0.2 BTC at 97.5 k yesterday at 15:20, fee 0 | 1 | time | 昨天 15:20 | (empty) | yesterday at 15:20 | 2026-10-07T15:20:00+02:00 (minute) |
| w08: Sold 80 SOL for 1.2 万 USDT in total yesterday, fee 6 USDT | 1 | time | 昨天 | (empty) | yesterday | 2026-10-07 (day) |
| w12: Sold 2 ETH for 6 900 in total on Bybit yesterday, fee 3 USDT | 1 | time | 昨天 | (empty) | yesterday | 2026-10-07 (day) |
| w16: Sold LINK 25 14.2 yesterday, fee 0.1 LINK | 1 | time | 昨天 | (empty) | yesterday | 2026-10-07 (day) |
| w19: Sold 0.5 ETH at 3，510 today, fee 0.6 USDT | 1 | time | 今天 | (empty) | today | 2026-10-08 (day) |
| w20: Bought 0.1 BTC at 95,400，2 SOL at 150, both on OKX today, fee 0 | 1 | time | 今天 | (empty) | today | 2026-10-08 (day) |
| w20: Bought 0.1 BTC at 95,400，2 SOL at 150, both on OKX today, fee 0 | 2 | time | 今天 | (empty) | today | 2026-10-08 (day) |

</details>

### Run: writings set, prompt `zero_shot`

Results file: `evals/results/run-20261009T024611Z-writings-zero_shot.jsonl`, with its summary in `run-20261009T024611Z-writings-zero_shot.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | writings |
| final_exam_switch | False |
| set_file | evals/sets/writings.json |
| set_sha256 | 7ac6a2027ec4434f140db02e51a3a46ca27da7dc89da06b3088866351f38ffce |
| prompt | zero_shot |
| prompt file src/ledger_hand/extraction/prompts/zero_shot.py | sha256 b5f309ca198e98cef953f38cd62cbffafe65cb6e7fc036371e5deaf1392b54a5 |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt_content_sha256 | f2d6c2b077e3a8a7d6bee5c2aeb7bb6eaf1588f73a1c93d21668c6f4f9569c88 |
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| commit | e63dc184168241d5fb5ed2c14c1c98e8adbfd5d4 |
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
| started_at | 2026-10-09T02:46:11+00:00 |
| sentences | 20 |
| sum_of_sentence_seconds | 79.201 |
| first_sentence_seconds | 2.938 |
| longest_sentence_seconds | 7.579 |
| finished_at | 2026-10-09T02:47:30+00:00 |
| seconds_of_the_last_session | 79.237 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 20 | 20 / 20 (100.0%) | 14 / 22 (63.6%) | 0 | 0 | 1 / 93 (1.1%) | 0 / 0 (-) |
| one trade | 18 | 18 / 18 (100.0%) | 14 / 18 (77.8%) | 0 | 0 | 1 / 77 (1.3%) | 0 / 0 (-) |
| several trades | 2 | 2 / 2 (100.0%) | 0 / 4 (0.0%) | 0 | 0 | 0 / 16 (0.0%) | 0 / 0 (-) |
| - two trades | 2 | 2 / 2 (100.0%) | 0 / 4 (0.0%) | 0 | 0 | 0 / 16 (0.0%) | 0 / 0 (-) |
| - three or more trades | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| no trade (talk) | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| Chinese | 8 | 8 / 8 (100.0%) | 7 / 9 (77.8%) | 0 | 0 | 0 / 38 (0.0%) | 0 / 0 (-) |
| English | 10 | 10 / 10 (100.0%) | 5 / 11 (45.5%) | 0 | 0 | 1 / 46 (2.2%) | 0 / 0 (-) |
| mixed | 2 | 2 / 2 (100.0%) | 2 / 2 (100.0%) | 0 | 0 | 0 / 9 (0.0%) | 0 / 0 (-) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 22 / 22 (100.0%) |
| coin | 22 / 22 (100.0%) |
| quantity | 22 / 22 (100.0%) |
| price | 21 / 22 (95.5%) |
| total | 22 / 22 (100.0%) |
| price_currency | 22 / 22 (100.0%) |
| fee | 19 / 22 (86.4%) |
| fee_currency | 20 / 22 (90.9%) |
| time | 15 / 22 (68.2%) |
| platform | 22 / 22 (100.0%) |
| opinion | 22 / 22 (100.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 229 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 5 |
| - because the model's phrase is not a piece of the passage | 5 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 7 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 1 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (1)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |
| w08: Sold 80 SOL for 1.2 万 USDT in total yesterday, fee 6 USDT | 1 | price | 1.2 万 | 12000 | (empty) | MADE_UP |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (5; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| w08 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| w12 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| w16 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| w20 | 1 | time | 今天 | today | NOT_IN_PASSAGE | no |
| w20 | 2 | time | 今天 | today | NOT_IN_PASSAGE | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| w01 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w02 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w03 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w04 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w05 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w06 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w07 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.fee:LEFT_EMPTY_BY_MODEL |
| w08 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.price:MADE_UP, 1.time:LEFT_EMPTY_WITH_REASON |
| w09 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w10 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w11 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w12 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w13 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w14 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w15 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w16 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w17 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w18 | zh | extracted | 2 | 2 | 0 | 0 | 0 | 1.fee:LEFT_EMPTY_BY_MODEL, 1.fee_currency:LEFT_EMPTY_BY_MODEL, 1.time:LEFT_EMPTY_BY_MODEL, 2.fee:LEFT_EMPTY_BY_MODEL, 2.fee_currency:LEFT_EMPTY_BY_MODEL, 2.time:LEFT_EMPTY_BY_MODEL |
| w19 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w20 | en | extracted | 2 | 2 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON, 2.time:LEFT_EMPTY_WITH_REASON |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 1 |
| Half copies, any field whose phrase is part of the gold phrase | 29 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 5 |

#### A total put as the price (1; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| w08: Sold 80 SOL for 1.2 万 USDT in total yesterday, fee 6 USDT | 1 | price | 1.2 万 | 12000 | 1.2 万 USDT | 12000 |

#### Half copies, counted the second way (29)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| w01: 前天在币安买了 2 w 个 DOGE，0.16 一个，手续费 1U | 1 | quantity | 2 w | (empty) | 2 w 个 DOGE | (empty) | yes |
| w02: 昨天 sold 了 4.5 k 个 XRP at 0.52，fee 0.3 USDT | 1 | quantity | 4.5 k | (empty) | 4.5 k 个 XRP | (empty) | yes |
| w02: 昨天 sold 了 4.5 k 个 XRP at 0.52，fee 0.3 USDT | 1 | fee | 0.3 | 0.3 | 0.3 USDT | 0.3 | yes |
| w03: Bought 3 k ADA at 0.38 on Kraken this morning, fee 1 USDT | 1 | quantity | 3 k | (empty) | 3 k ADA | (empty) | yes |
| w03: Bought 3 k ADA at 0.38 on Kraken this morning, fee 1 USDT | 1 | fee | 1 | 1 | 1 USDT | 1 | yes |
| w04: Sold 0.2 BTC at 97.5 k yesterday at 15:20, fee 0 | 1 | quantity | 0.2 | 0.2 | 0.2 BTC | 0.2 | yes |
| w05: 上周五买了 200 万 SHIB，一共花了 30 U，手续费 0 | 1 | quantity | 200 万 | 2000000 | 200 万 SHIB | 2000000 | yes |
| w06: 今天下午 4 点在 OKX 卖了 5 万 个 DOGE，价格 0.17，手续费 2 U | 1 | quantity | 5 万 | 50000 | 5 万 个 DOGE | 50000 | yes |
| w06: 今天下午 4 点在 OKX 卖了 5 万 个 DOGE，价格 0.17，手续费 2 U | 1 | fee | 2 | 2 | 2 U | 2 | yes |
| w07: Picked up 50 万 PEPE at 0.0000098 on Monday, fee 0 | 1 | quantity | 50 万 | 500000 | 50 万 PEPE | 500000 | yes |
| w07: Picked up 50 万 PEPE at 0.0000098 on Monday, fee 0 | 1 | time | Monday | 2026-10-05 (day) | on Monday | 2026-10-05 (day) | yes |
| w08: Sold 80 SOL for 1.2 万 USDT in total yesterday, fee 6 USDT | 1 | quantity | 80 | 80 | 80 SOL | 80 | yes |
| w08: Sold 80 SOL for 1.2 万 USDT in total yesterday, fee 6 USDT | 1 | fee | 6 | 6 | 6 USDT | 6 | yes |
| w09: 昨天晚上 8 点入了 0.03 个 BTC，单价 95 800，手续费 2.9 USDT | 1 | quantity | 0.03 个 | 0.03 | 0.03 个 BTC | 0.03 | yes |
| w09: 昨天晚上 8 点入了 0.03 个 BTC，单价 95 800，手续费 2.9 USDT | 1 | fee | 2.9 | 2.9 | 2.9 USDT | 2.9 | yes |
| w10: 今天在 OKX 卖了 1.2 个 ETH，成交价 3 450 | 1 | quantity | 1.2 个 | 1.2 | 1.2 个 ETH | 1.2 | yes |
| w11: Bought 0.05 BTC at 96 300 this afternoon, fee 2 USDT | 1 | fee | 2 | 2 | 2 USDT | 2 | yes |
| w12: Sold 2 ETH for 6 900 in total on Bybit yesterday, fee 3 USDT | 1 | quantity | 2 | 2 | 2 ETH | 2 | yes |
| w12: Sold 2 ETH for 6 900 in total on Bybit yesterday, fee 3 USDT | 1 | fee | 3 | 3 | 3 USDT | 3 | yes |
| w14: ETH 卖出 0.8 3520，前天下午 2 点半，手续费 0.9 U | 1 | fee | 0.9 | 0.9 | 0.9 U | 0.9 | yes |
| w15: Bought SOL 12 148.5 this morning on Binance, fee 0.2 USDT | 1 | fee | 0.2 | 0.2 | 0.2 USDT | 0.2 | yes |
| w16: Sold LINK 25 14.2 yesterday, fee 0.1 LINK | 1 | fee | 0.1 | 0.1 | 0.1 LINK | 0.1 | yes |
| w17: 昨天买了 0.02 个 BTC，价格 95，200，手续费 1U | 1 | quantity | 0.02 个 | 0.02 | 0.02 个 BTC | 0.02 | yes |
| w18: 今天连着卖了两笔：0.2 BTC @ 96,000，3 ETH @ 3,480，手续费都是 1U | 1 | quantity | 0.2 | 0.2 | 0.2 BTC | 0.2 | yes |
| w18: 今天连着卖了两笔：0.2 BTC @ 96,000，3 ETH @ 3,480，手续费都是 1U | 2 | quantity | 3 | 3 | 3 ETH | 3 | yes |
| w19: Sold 0.5 ETH at 3，510 today, fee 0.6 USDT | 1 | quantity | 0.5 | 0.5 | 0.5 ETH | 0.5 | yes |
| w19: Sold 0.5 ETH at 3，510 today, fee 0.6 USDT | 1 | fee | 0.6 | 0.6 | 0.6 USDT | 0.6 | yes |
| w20: Bought 0.1 BTC at 95,400，2 SOL at 150, both on OKX today, fee 0 | 1 | quantity | 0.1 | 0.1 | 0.1 BTC | 0.1 | yes |
| w20: Bought 0.1 BTC at 95,400，2 SOL at 150, both on OKX today, fee 0 | 2 | quantity | 2 | 2 | 2 SOL | 2 | yes |

#### A time written in another language (5)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| w08: Sold 80 SOL for 1.2 万 USDT in total yesterday, fee 6 USDT | 1 | time | 昨天 | (empty) | yesterday | 2026-10-07 (day) |
| w12: Sold 2 ETH for 6 900 in total on Bybit yesterday, fee 3 USDT | 1 | time | 昨天 | (empty) | yesterday | 2026-10-07 (day) |
| w16: Sold LINK 25 14.2 yesterday, fee 0.1 LINK | 1 | time | 昨天 | (empty) | yesterday | 2026-10-07 (day) |
| w20: Bought 0.1 BTC at 95,400，2 SOL at 150, both on OKX today, fee 0 | 1 | time | 今天 | (empty) | today | 2026-10-08 (day) |
| w20: Bought 0.1 BTC at 95,400，2 SOL at 150, both on OKX today, fee 0 | 2 | time | 今天 | (empty) | today | 2026-10-08 (day) |

</details>

### Run: writings set, prompt `persona`

Results file: `evals/results/run-20261009T024737Z-writings-persona.jsonl`, with its summary in `run-20261009T024737Z-writings-persona.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | writings |
| final_exam_switch | False |
| set_file | evals/sets/writings.json |
| set_sha256 | 7ac6a2027ec4434f140db02e51a3a46ca27da7dc89da06b3088866351f38ffce |
| prompt | persona |
| prompt file src/ledger_hand/extraction/prompts/persona.py | sha256 5d43341346f6e0a6e298640144807ded0f9e93797ebbac094e70ec1458086940 |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | 0e33c465f66b25dec176b39404a451ee5bffc8f35751a275ee8753564335fb42 |
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| commit | 939dba3fd16be7cf57daaf832a8583ba07cf385d |
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
| started_at | 2026-10-09T02:47:37+00:00 |
| sentences | 20 |
| sum_of_sentence_seconds | 79.443 |
| first_sentence_seconds | 3.654 |
| longest_sentence_seconds | 6.593 |
| finished_at | 2026-10-09T02:48:57+00:00 |
| seconds_of_the_last_session | 79.478 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 20 | 20 / 20 (100.0%) | 15 / 22 (68.2%) | 0 | 0 | 0 / 93 (0.0%) | 0 / 0 (-) |
| one trade | 18 | 18 / 18 (100.0%) | 13 / 18 (72.2%) | 0 | 0 | 0 / 77 (0.0%) | 0 / 0 (-) |
| several trades | 2 | 2 / 2 (100.0%) | 2 / 4 (50.0%) | 0 | 0 | 0 / 16 (0.0%) | 0 / 0 (-) |
| - two trades | 2 | 2 / 2 (100.0%) | 2 / 4 (50.0%) | 0 | 0 | 0 / 16 (0.0%) | 0 / 0 (-) |
| - three or more trades | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| no trade (talk) | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| Chinese | 8 | 8 / 8 (100.0%) | 9 / 9 (100.0%) | 0 | 0 | 0 / 38 (0.0%) | 0 / 0 (-) |
| English | 10 | 10 / 10 (100.0%) | 4 / 11 (36.4%) | 0 | 0 | 0 / 46 (0.0%) | 0 / 0 (-) |
| mixed | 2 | 2 / 2 (100.0%) | 2 / 2 (100.0%) | 0 | 0 | 0 / 9 (0.0%) | 0 / 0 (-) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 22 / 22 (100.0%) |
| coin | 22 / 22 (100.0%) |
| quantity | 22 / 22 (100.0%) |
| price | 22 / 22 (100.0%) |
| total | 22 / 22 (100.0%) |
| price_currency | 22 / 22 (100.0%) |
| fee | 22 / 22 (100.0%) |
| fee_currency | 22 / 22 (100.0%) |
| time | 15 / 22 (68.2%) |
| platform | 22 / 22 (100.0%) |
| opinion | 22 / 22 (100.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 235 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 7 |
| - because the model's phrase is not a piece of the passage | 7 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 0 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 0 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (7; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| w04 | 1 | time | 昨天 15:20 | yesterday at 15:20 | NOT_IN_PASSAGE | no |
| w08 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| w12 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| w16 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| w19 | 1 | time | 今天 | today | NOT_IN_PASSAGE | no |
| w20 | 1 | time | 今天 | today | NOT_IN_PASSAGE | no |
| w20 | 2 | time | 今天 | today | NOT_IN_PASSAGE | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| w01 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w02 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w03 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w04 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w05 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w06 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w07 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w08 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w09 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w10 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w11 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w12 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w13 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w14 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w15 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w16 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w17 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w18 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| w19 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w20 | en | extracted | 2 | 2 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON, 2.time:LEFT_EMPTY_WITH_REASON |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 1 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 7 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (1)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| w07: Picked up 50 万 PEPE at 0.0000098 on Monday, fee 0 | 1 | time | Monday | 2026-10-05 (day) | on Monday | 2026-10-05 (day) | yes |

#### A time written in another language (7)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| w04: Sold 0.2 BTC at 97.5 k yesterday at 15:20, fee 0 | 1 | time | 昨天 15:20 | (empty) | yesterday at 15:20 | 2026-10-07T15:20:00+02:00 (minute) |
| w08: Sold 80 SOL for 1.2 万 USDT in total yesterday, fee 6 USDT | 1 | time | 昨天 | (empty) | yesterday | 2026-10-07 (day) |
| w12: Sold 2 ETH for 6 900 in total on Bybit yesterday, fee 3 USDT | 1 | time | 昨天 | (empty) | yesterday | 2026-10-07 (day) |
| w16: Sold LINK 25 14.2 yesterday, fee 0.1 LINK | 1 | time | 昨天 | (empty) | yesterday | 2026-10-07 (day) |
| w19: Sold 0.5 ETH at 3，510 today, fee 0.6 USDT | 1 | time | 今天 | (empty) | today | 2026-10-08 (day) |
| w20: Bought 0.1 BTC at 95,400，2 SOL at 150, both on OKX today, fee 0 | 1 | time | 今天 | (empty) | today | 2026-10-08 (day) |
| w20: Bought 0.1 BTC at 95,400，2 SOL at 150, both on OKX today, fee 0 | 2 | time | 今天 | (empty) | today | 2026-10-08 (day) |

</details>

### Run: writings set, prompt `stepwise`

Results file: `evals/results/run-20261009T024858Z-writings-stepwise.jsonl`, with its summary in `run-20261009T024858Z-writings-stepwise.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | writings |
| final_exam_switch | False |
| set_file | evals/sets/writings.json |
| set_sha256 | 7ac6a2027ec4434f140db02e51a3a46ca27da7dc89da06b3088866351f38ffce |
| prompt | stepwise |
| prompt file src/ledger_hand/extraction/prompts/stepwise.py | sha256 ade615b5113708fa8356a35b6e21fbc40bfd1c0666bb22b8eaaf6cbfcf49ca99 |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | 2f47a7ac7368b04d5dbbf112ceebf83cdc0963e6996c464c21ef836096380768 |
| reply_table_sha256 | c822392c150e388a3bef711e3af1c43e4dd73329b118145b1e8a1308f4dfae89 |
| commit | dfcf3405b5bca0074a3a9a32286c0e6db23def60 |
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
| started_at | 2026-10-09T02:48:58+00:00 |
| sentences | 20 |
| sum_of_sentence_seconds | 124.561 |
| first_sentence_seconds | 5.55 |
| longest_sentence_seconds | 8.853 |
| finished_at | 2026-10-09T02:51:02+00:00 |
| seconds_of_the_last_session | 124.593 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 20 | 20 / 20 (100.0%) | 12 / 22 (54.5%) | 0 | 1 | 0 / 93 (0.0%) | 0 / 0 (-) |
| one trade | 18 | 18 / 18 (100.0%) | 10 / 18 (55.6%) | 0 | 1 | 0 / 77 (0.0%) | 0 / 0 (-) |
| several trades | 2 | 2 / 2 (100.0%) | 2 / 4 (50.0%) | 0 | 0 | 0 / 16 (0.0%) | 0 / 0 (-) |
| - two trades | 2 | 2 / 2 (100.0%) | 2 / 4 (50.0%) | 0 | 0 | 0 / 16 (0.0%) | 0 / 0 (-) |
| - three or more trades | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| no trade (talk) | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| Chinese | 8 | 8 / 8 (100.0%) | 5 / 9 (55.6%) | 0 | 1 | 0 / 38 (0.0%) | 0 / 0 (-) |
| English | 10 | 10 / 10 (100.0%) | 5 / 11 (45.5%) | 0 | 0 | 0 / 46 (0.0%) | 0 / 0 (-) |
| mixed | 2 | 2 / 2 (100.0%) | 2 / 2 (100.0%) | 0 | 0 | 0 / 9 (0.0%) | 0 / 0 (-) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 22 / 22 (100.0%) |
| coin | 22 / 22 (100.0%) |
| quantity | 21 / 22 (95.5%) |
| price | 22 / 22 (100.0%) |
| total | 22 / 22 (100.0%) |
| price_currency | 22 / 22 (100.0%) |
| fee | 22 / 22 (100.0%) |
| fee_currency | 22 / 22 (100.0%) |
| time | 13 / 22 (59.1%) |
| platform | 22 / 22 (100.0%) |
| opinion | 22 / 22 (100.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 232 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 7 |
| - because the model's phrase is not a piece of the passage | 7 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 3 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 0 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (7; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| w04 | 1 | time | 昨天 15:20 | yesterday at 15:20 | NOT_IN_PASSAGE | no |
| w06 | 1 | quantity | 5 万个 DOGE | 5 万 个 DOGE | NOT_IN_PASSAGE | no |
| w08 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| w12 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| w16 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| w20 | 1 | time | 今天 | today | NOT_IN_PASSAGE | no |
| w20 | 2 | time | 今天 | today | NOT_IN_PASSAGE | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| w01 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_BY_MODEL |
| w02 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w03 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w04 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w05 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_BY_MODEL |
| w06 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.quantity:LEFT_EMPTY_WITH_REASON |
| w07 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w08 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w09 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w10 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w11 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w12 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w13 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w14 | zh | extracted | 1 | 2 | 0 | 0 | 1 | 1.time:LEFT_EMPTY_BY_MODEL |
| w15 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w16 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w17 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w18 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| w19 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w20 | en | extracted | 2 | 2 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON, 2.time:LEFT_EMPTY_WITH_REASON |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 1 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 6 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (1)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| w07: Picked up 50 万 PEPE at 0.0000098 on Monday, fee 0 | 1 | time | Monday | 2026-10-05 (day) | on Monday | 2026-10-05 (day) | yes |

#### A time written in another language (6)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| w04: Sold 0.2 BTC at 97.5 k yesterday at 15:20, fee 0 | 1 | time | 昨天 15:20 | (empty) | yesterday at 15:20 | 2026-10-07T15:20:00+02:00 (minute) |
| w08: Sold 80 SOL for 1.2 万 USDT in total yesterday, fee 6 USDT | 1 | time | 昨天 | (empty) | yesterday | 2026-10-07 (day) |
| w12: Sold 2 ETH for 6 900 in total on Bybit yesterday, fee 3 USDT | 1 | time | 昨天 | (empty) | yesterday | 2026-10-07 (day) |
| w16: Sold LINK 25 14.2 yesterday, fee 0.1 LINK | 1 | time | 昨天 | (empty) | yesterday | 2026-10-07 (day) |
| w20: Bought 0.1 BTC at 95,400，2 SOL at 150, both on OKX today, fee 0 | 1 | time | 今天 | (empty) | today | 2026-10-08 (day) |
| w20: Bought 0.1 BTC at 95,400，2 SOL at 150, both on OKX today, fee 0 | 2 | time | 今天 | (empty) | today | 2026-10-08 (day) |

</details>

### Run: writings set, prompt `price_total`

Results file: `evals/results/run-20261009T025103Z-writings-price_total.jsonl`, with its summary in `run-20261009T025103Z-writings-price_total.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | writings |
| final_exam_switch | False |
| set_file | evals/sets/writings.json |
| set_sha256 | 7ac6a2027ec4434f140db02e51a3a46ca27da7dc89da06b3088866351f38ffce |
| prompt | price_total |
| prompt file src/ledger_hand/extraction/prompts/price_total.py | sha256 1fe1993962a398131dc6c02f26c4c33dd772ea9750ab5aa73c10b686061ec745 |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | cfc0d1a883062284a83ad8e25962d1e4a5634b17320388ee47da920821da9ec8 |
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| commit | 91b962e9f91d3fb6b68494249c8ade1ff751b54b |
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
| started_at | 2026-10-09T02:51:03+00:00 |
| sentences | 20 |
| sum_of_sentence_seconds | 81.439 |
| first_sentence_seconds | 3.728 |
| longest_sentence_seconds | 6.776 |
| finished_at | 2026-10-09T02:52:24+00:00 |
| seconds_of_the_last_session | 81.473 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 20 | 20 / 20 (100.0%) | 15 / 22 (68.2%) | 0 | 0 | 0 / 93 (0.0%) | 0 / 0 (-) |
| one trade | 18 | 18 / 18 (100.0%) | 13 / 18 (72.2%) | 0 | 0 | 0 / 77 (0.0%) | 0 / 0 (-) |
| several trades | 2 | 2 / 2 (100.0%) | 2 / 4 (50.0%) | 0 | 0 | 0 / 16 (0.0%) | 0 / 0 (-) |
| - two trades | 2 | 2 / 2 (100.0%) | 2 / 4 (50.0%) | 0 | 0 | 0 / 16 (0.0%) | 0 / 0 (-) |
| - three or more trades | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| no trade (talk) | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| Chinese | 8 | 8 / 8 (100.0%) | 9 / 9 (100.0%) | 0 | 0 | 0 / 38 (0.0%) | 0 / 0 (-) |
| English | 10 | 10 / 10 (100.0%) | 4 / 11 (36.4%) | 0 | 0 | 0 / 46 (0.0%) | 0 / 0 (-) |
| mixed | 2 | 2 / 2 (100.0%) | 2 / 2 (100.0%) | 0 | 0 | 0 / 9 (0.0%) | 0 / 0 (-) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 22 / 22 (100.0%) |
| coin | 22 / 22 (100.0%) |
| quantity | 22 / 22 (100.0%) |
| price | 22 / 22 (100.0%) |
| total | 22 / 22 (100.0%) |
| price_currency | 22 / 22 (100.0%) |
| fee | 22 / 22 (100.0%) |
| fee_currency | 22 / 22 (100.0%) |
| time | 15 / 22 (68.2%) |
| platform | 22 / 22 (100.0%) |
| opinion | 22 / 22 (100.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 235 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 7 |
| - because the model's phrase is not a piece of the passage | 7 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 0 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 0 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (7; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| w04 | 1 | time | 昨天 15:20 | yesterday at 15:20 | NOT_IN_PASSAGE | no |
| w08 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| w12 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| w16 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| w19 | 1 | time | 今天 | today | NOT_IN_PASSAGE | no |
| w20 | 1 | time | 今天 | today | NOT_IN_PASSAGE | no |
| w20 | 2 | time | 今天 | today | NOT_IN_PASSAGE | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| w01 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w02 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w03 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w04 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w05 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w06 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w07 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w08 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w09 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w10 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w11 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w12 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w13 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w14 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w15 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w16 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w17 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w18 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| w19 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w20 | en | extracted | 2 | 2 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON, 2.time:LEFT_EMPTY_WITH_REASON |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 1 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 7 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (1)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| w07: Picked up 50 万 PEPE at 0.0000098 on Monday, fee 0 | 1 | time | Monday | 2026-10-05 (day) | on Monday | 2026-10-05 (day) | yes |

#### A time written in another language (7)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| w04: Sold 0.2 BTC at 97.5 k yesterday at 15:20, fee 0 | 1 | time | 昨天 15:20 | (empty) | yesterday at 15:20 | 2026-10-07T15:20:00+02:00 (minute) |
| w08: Sold 80 SOL for 1.2 万 USDT in total yesterday, fee 6 USDT | 1 | time | 昨天 | (empty) | yesterday | 2026-10-07 (day) |
| w12: Sold 2 ETH for 6 900 in total on Bybit yesterday, fee 3 USDT | 1 | time | 昨天 | (empty) | yesterday | 2026-10-07 (day) |
| w16: Sold LINK 25 14.2 yesterday, fee 0.1 LINK | 1 | time | 昨天 | (empty) | yesterday | 2026-10-07 (day) |
| w19: Sold 0.5 ETH at 3，510 today, fee 0.6 USDT | 1 | time | 今天 | (empty) | today | 2026-10-08 (day) |
| w20: Bought 0.1 BTC at 95,400，2 SOL at 150, both on OKX today, fee 0 | 1 | time | 今天 | (empty) | today | 2026-10-08 (day) |
| w20: Bought 0.1 BTC at 95,400，2 SOL at 150, both on OKX today, fee 0 | 2 | time | 今天 | (empty) | today | 2026-10-08 (day) |

</details>

### Parameter comparison 1: debug set, prompt `first`, temperature 0.7

Results file: `evals/results/run-20261009T025243Z-debug-first.jsonl`, with its summary in `run-20261009T025243Z-debug-first.summary.json`.

One parameter changed from the runs above: the temperature, 0.0 there and 0.7 here (set with `LEDGER_HAND_MODEL_TEMPERATURE=0.7`). It measures how much the version the rule picked moves when the model samples more freely. This run is not one of the five the rule compares.

<details>
<summary>The generated tables of this run</summary>

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
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| commit | 35f00a6dfd8d70df73e04c68a77c4007ab03f651 |
| worktree_clean | True |
| model | qwen2.5:7b |
| model_fingerprint | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e |
| server_version | 0.34.3 |
| base_url | http://127.0.0.1:11434 |
| parameter temperature | 0.7 |
| parameter top_p | 1.0 |
| parameter max_reply_tokens | 1024 |
| parameter context_tokens | 16384 |
| parameter timeout_seconds | 120.0 |
| parameter retries | 2 |
| parameter retry_wait_seconds | 1.0 |
| parameter asks_again | 1 |
| coin_table | built-in |
| started_at | 2026-10-09T02:52:43+00:00 |
| sentences | 30 |
| sum_of_sentence_seconds | 130.607 |
| first_sentence_seconds | 4.006 |
| longest_sentence_seconds | 10.46 |
| finished_at | 2026-10-09T02:54:54+00:00 |
| seconds_of_the_last_session | 130.655 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 26 | 26 / 26 (100.0%) | 30 / 34 (88.2%) | 0 | 0 | 1 / 140 (0.7%) | 3 / 3 (100.0%) |
| one trade | 15 | 15 / 15 (100.0%) | 13 / 15 (86.7%) | 0 | 0 | 0 / 60 (0.0%) | 0 / 0 (-) |
| several trades | 8 | 8 / 8 (100.0%) | 17 / 19 (89.5%) | 0 | 0 | 1 / 80 (1.2%) | 0 / 0 (-) |
| - two trades | 5 | 5 / 5 (100.0%) | 9 / 10 (90.0%) | 0 | 0 | 0 / 42 (0.0%) | 0 / 0 (-) |
| - three or more trades | 3 | 3 / 3 (100.0%) | 8 / 9 (88.9%) | 0 | 0 | 1 / 38 (2.6%) | 0 / 0 (-) |
| no trade (talk) | 3 | 3 / 3 (100.0%) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 3 / 3 (100.0%) |
| Chinese | 10 | 10 / 10 (100.0%) | 12 / 13 (92.3%) | 0 | 0 | 0 / 52 (0.0%) | 1 / 1 (100.0%) |
| English | 9 | 9 / 9 (100.0%) | 10 / 12 (83.3%) | 0 | 0 | 0 / 49 (0.0%) | 1 / 1 (100.0%) |
| mixed | 7 | 7 / 7 (100.0%) | 8 / 9 (88.9%) | 0 | 0 | 1 / 39 (2.6%) | 1 / 1 (100.0%) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 34 / 34 (100.0%) |
| coin | 34 / 34 (100.0%) |
| quantity | 33 / 34 (97.1%) |
| price | 32 / 34 (94.1%) |
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
| RIGHT: right | 368 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 4 |
| - because the model's phrase is not a piece of the passage | 4 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 1 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 1 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (1)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |
| d23: 刚才连着 sell 了三笔：0.1 BTC @ 63,000，1.5 ETH @ 2,410，还有 TON 卖了 200 个，total 1,040 USDT | 3 | price | 1,040 USDT | 1040 | (empty) | MADE_UP |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (4; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| d05 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| d13 | 1 | time | 昨天 18:20 | yesterday at 18:20 | NOT_IN_PASSAGE | no |
| d19 | 1 | price | 2,450 | 两千四百五 | NOT_IN_PASSAGE | no |
| d23 | 3 | quantity | 200 个 TON | 200 个 | NOT_IN_PASSAGE | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |
| d27: 昨天开了 10 倍杠杆做多 BTC，开仓价 62,800，保证金 200U | futures_or_leverage | extracted | 1 | draft 1: stopped by SIDE, FEE |
| d28: Swapped 0.5 ETH for 0.019 BTC on Uniswap this morning | coin_for_coin | extracted | 2 | draft 1: stopped by SIDE, ONE_MORE_OF_QUANTITY_PRICE_TOTAL, FEE; draft 2: stopped by ONE_MORE_OF_QUANTITY_PRICE_TOTAL, FEE |
| d29: 挂了一个 limit buy，0.05 BTC @ 58,000，还没成交 | open_order | extracted | 1 | draft 1: stopped by SIDE, FEE, OCCURRED |
| d30: 打算明天下午 3 点买 1 个 ETH，价格到 2,300 就进 | plan | extracted | 1 | draft 1: stopped by SIDE, ONE_MORE_OF_QUANTITY_PRICE_TOTAL, FEE, OCCURRED |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| d01 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d02 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d03 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d04 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d05 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
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
| d19 | zh | extracted | 2 | 2 | 1 | 0 | 0 | 1.price:LEFT_EMPTY_WITH_REASON |
| d20 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d21 | zh | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d22 | en | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d23 | mixed | extracted | 3 | 3 | 2 | 0 | 0 | 3.quantity:LEFT_EMPTY_WITH_REASON, 3.price:MADE_UP, 3.total:LEFT_EMPTY_BY_MODEL |
| d24 | zh | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d25 | en | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d26 | mixed | extracted | 0 | 0 | 0 | 0 | 0 | - |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 1 |
| Half copies, any field whose phrase is part of the gold phrase | 0 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 2 |

#### A total put as the price (1; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| d23: 刚才连着 sell 了三笔：0.1 BTC @ 63,000，1.5 ETH @ 2,410，还有 TON 卖了 200 个，total 1,040 USDT | 3 | price | 1,040 USDT | 1040 | 1,040 USDT | 1040 |

#### Half copies, counted the second way (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |

#### A time written in another language (2)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| d05: Bought 120 ADA for 64.80 USDT total yesterday, fee 0.002 BNB | 1 | time | 昨天 | (empty) | yesterday | 2026-10-04 (day) |
| d13: Picked up 40 LINK at 13.85 yesterday at 18:20 while BTC sat near 61k, fee 0 | 1 | time | 昨天 18:20 | (empty) | yesterday at 18:20 | 2026-10-04T18:20:00+02:00 (minute) |

</details>

### Parameter comparison 2: debug set, prompt `stepwise`, longest reply 256 tokens

Results file: `evals/results/run-20261009T025506Z-debug-stepwise.jsonl`, with its summary in `run-20261009T025506Z-debug-stepwise.summary.json`.

One parameter changed from the runs above: the longest reply, 1,024 tokens there and 256 here (set with `LEDGER_HAND_MODEL_MAX_REPLY_TOKENS=256`). The `stepwise` version writes the longest replies, as it writes its analysis before the table; its longest reply in its run above was 297 tokens, so 256 is below it. It measures what the limit does when it is reached. This run is not one of the five the rule compares.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | debug |
| final_exam_switch | False |
| set_file | evals/sets/debug.json |
| set_sha256 | 4529d98323ad1df4d38f5a5b73cdf1082b6a1cd08a0604a454ecf7986104f4d8 |
| prompt | stepwise |
| prompt file src/ledger_hand/extraction/prompts/stepwise.py | sha256 ade615b5113708fa8356a35b6e21fbc40bfd1c0666bb22b8eaaf6cbfcf49ca99 |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | 2f47a7ac7368b04d5dbbf112ceebf83cdc0963e6996c464c21ef836096380768 |
| reply_table_sha256 | c822392c150e388a3bef711e3af1c43e4dd73329b118145b1e8a1308f4dfae89 |
| commit | 30ef9b44f86a3d42c5e54a4a4a73e3cba727de72 |
| worktree_clean | True |
| model | qwen2.5:7b |
| model_fingerprint | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e |
| server_version | 0.34.3 |
| base_url | http://127.0.0.1:11434 |
| parameter temperature | 0.0 |
| parameter top_p | 1.0 |
| parameter max_reply_tokens | 256 |
| parameter context_tokens | 16384 |
| parameter timeout_seconds | 120.0 |
| parameter retries | 2 |
| parameter retry_wait_seconds | 1.0 |
| parameter asks_again | 1 |
| coin_table | built-in |
| started_at | 2026-10-09T02:55:06+00:00 |
| sentences | 30 |
| sum_of_sentence_seconds | 228.606 |
| first_sentence_seconds | 6.445 |
| longest_sentence_seconds | 24.683 |
| finished_at | 2026-10-09T02:58:55+00:00 |
| seconds_of_the_last_session | 228.654 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 26 | 23 / 26 (88.5%) | 19 / 34 (55.9%) | 9 | 0 | 1 / 102 (1.0%) | 3 / 3 (100.0%) |
| one trade | 15 | 15 / 15 (100.0%) | 10 / 15 (66.7%) | 0 | 0 | 1 / 60 (1.7%) | 0 / 0 (-) |
| several trades | 8 | 5 / 8 (62.5%) | 9 / 19 (47.4%) | 9 | 0 | 0 / 42 (0.0%) | 0 / 0 (-) |
| - two trades | 5 | 5 / 5 (100.0%) | 9 / 10 (90.0%) | 0 | 0 | 0 / 42 (0.0%) | 0 / 0 (-) |
| - three or more trades | 3 | 0 / 3 (0.0%) | 0 / 9 (0.0%) | 9 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| no trade (talk) | 3 | 3 / 3 (100.0%) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 3 / 3 (100.0%) |
| Chinese | 10 | 9 / 10 (90.0%) | 6 / 13 (46.2%) | 3 | 0 | 1 / 43 (2.3%) | 1 / 1 (100.0%) |
| English | 9 | 8 / 9 (88.9%) | 8 / 12 (66.7%) | 3 | 0 | 0 / 37 (0.0%) | 1 / 1 (100.0%) |
| mixed | 7 | 6 / 7 (85.7%) | 5 / 9 (55.6%) | 3 | 0 | 0 / 22 (0.0%) | 1 / 1 (100.0%) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 22 / 25 (88.0%) |
| coin | 25 / 25 (100.0%) |
| quantity | 24 / 25 (96.0%) |
| price | 23 / 25 (92.0%) |
| total | 25 / 25 (100.0%) |
| price_currency | 25 / 25 (100.0%) |
| fee | 25 / 25 (100.0%) |
| fee_currency | 25 / 25 (100.0%) |
| time | 23 / 25 (92.0%) |
| platform | 25 / 25 (100.0%) |
| opinion | 25 / 25 (100.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 267 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 3 |
| - because the model's phrase is not a piece of the passage | 3 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 4 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 1 |
| - of them with an issue about the field | 1 |

#### Wrong values in drafts with no issue about them (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (3; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| d04 | 1 | price | 63,500 | 六万三千五 | NOT_IN_PASSAGE | no |
| d13 | 1 | time | 昨天 18:20 | yesterday at 18:20 | NOT_IN_PASSAGE | no |
| d19 | 1 | price | 2,450 | 两千四百五 | NOT_IN_PASSAGE | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |
| d27: 昨天开了 10 倍杠杆做多 BTC，开仓价 62,800，保证金 200U | futures_or_leverage | extracted | 1 | draft 1: stopped by ONE_MORE_OF_QUANTITY_PRICE_TOTAL, FEE |
| d28: Swapped 0.5 ETH for 0.019 BTC on Uniswap this morning | coin_for_coin | extracted | 1 | draft 1: stopped by ONE_MORE_OF_QUANTITY_PRICE_TOTAL, FEE |
| d29: 挂了一个 limit buy，0.05 BTC @ 58,000，还没成交 | open_order | extracted | 1 | draft 1: stopped by SIDE, FEE, OCCURRED |
| d30: 打算明天下午 3 点买 1 个 ETH，价格到 2,300 就进 | plan | extracted | 0 | - |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| d01 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d02 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d03 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d04 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.price:LEFT_EMPTY_WITH_REASON |
| d05 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d06 | mixed | extracted | 1 | 1 | 0 | 0 | 0 | 1.side:LEFT_EMPTY_BY_MODEL |
| d07 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.side:LEFT_EMPTY_BY_MODEL, 1.time:LEFT_EMPTY_BY_MODEL |
| d08 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d09 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d10 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d11 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d12 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d13 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| d14 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.side:LEFT_EMPTY_BY_MODEL, 1.quantity:MADE_UP |
| d15 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d16 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d17 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d18 | mixed | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d19 | zh | extracted | 2 | 2 | 1 | 0 | 0 | 1.price:LEFT_EMPTY_WITH_REASON |
| d20 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d21 | zh | reply_unreadable | 3 | 0 | 0 | 3 | 0 | - |
| d22 | en | reply_unreadable | 3 | 0 | 0 | 3 | 0 | - |
| d23 | mixed | reply_unreadable | 3 | 0 | 0 | 3 | 0 | - |
| d24 | zh | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d25 | en | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d26 | mixed | extracted | 0 | 0 | 0 | 0 | 0 | - |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 0 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 1 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |

#### A time written in another language (1)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| d13: Picked up 40 LINK at 13.85 yesterday at 18:20 while BTC sat near 61k, fee 0 | 1 | time | 昨天 18:20 | (empty) | yesterday at 18:20 | 2026-10-04T18:20:00+02:00 (minute) |

</details>

### Final exam: final set, prompt `first`

Run once, with `--final-exam`, with the version the rule picked (`first`),
at commit `dcc6e11`, after every run above and the sections of this record
on them were committed; it is not run again. Same model, fingerprint,
Ollama version and parameters as the five runs compared above.

| Version | Technique | Differs from `first` in | Well-formed | Whole trades right | One trade | Several trades | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | few-shot | the baseline: instructions and ten examples | 16 / 16 (100.0%) | 22 / 22 (100.0%) | 9 / 9 (100.0%) | 13 / 13 (100.0%) | 0 | 0 | 0 / 89 (0.0%) | 2 / 2 (100.0%) |

| Version | Wrong values with no issue | A total put as the price | Half copies (any) | Half copies (not right) | A time in another language | Sentences with a reply cut off | Calls | Seconds | Results file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | 0 | 0 | 0 | 0 | 0 | 0 | 20 | 79.7 | `evals/results/run-20261009T030436Z-final-first.jsonl` |

All 22 gold trades of the 16 scored sentences came out whole: 9 of 9 in
one-trade passages, 13 of 13 in passages with several (6 of 6 with two, 7
of 7 with three or more); no trade missed or extra; no field left empty,
wrong or made up; the 2 passages of talk gave no draft. Of the 4 passages
not to record, f17 (futures), f18 (a coin paid with another coin) and f19
(an order not filled yet) gave one draft each, which the check of a draft
stops; f20 (a plan) gave none. The 20 sentences took 79.7 seconds, one
call each.

### Run: final set, prompt `first`

Results file: `evals/results/run-20261009T030436Z-final-first.jsonl`, with its summary in `run-20261009T030436Z-final-first.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | final |
| final_exam_switch | True |
| set_file | evals/sets/final.json |
| set_sha256 | 34afdeb36b787d7e62a6a1a0149838c2dfde8c186a1bb89ea6b3de1205090406 |
| prompt | first |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | 7a510f4aaf16f7830ea5df2ec2071a276006565014e61bf295aa44a57a297112 |
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| commit | dcc6e116d7f793647562c60c9b0b0f98975a2b03 |
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
| started_at | 2026-10-09T03:04:36+00:00 |
| sentences | 20 |
| sum_of_sentence_seconds | 79.685 |
| first_sentence_seconds | 7.888 |
| longest_sentence_seconds | 9.701 |
| finished_at | 2026-10-09T03:05:55+00:00 |
| seconds_of_the_last_session | 79.72 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 16 | 16 / 16 (100.0%) | 22 / 22 (100.0%) | 0 | 0 | 0 / 89 (0.0%) | 2 / 2 (100.0%) |
| one trade | 9 | 9 / 9 (100.0%) | 9 / 9 (100.0%) | 0 | 0 | 0 / 35 (0.0%) | 0 / 0 (-) |
| several trades | 5 | 5 / 5 (100.0%) | 13 / 13 (100.0%) | 0 | 0 | 0 / 54 (0.0%) | 0 / 0 (-) |
| - two trades | 3 | 3 / 3 (100.0%) | 6 / 6 (100.0%) | 0 | 0 | 0 / 21 (0.0%) | 0 / 0 (-) |
| - three or more trades | 2 | 2 / 2 (100.0%) | 7 / 7 (100.0%) | 0 | 0 | 0 / 33 (0.0%) | 0 / 0 (-) |
| no trade (talk) | 2 | 2 / 2 (100.0%) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 2 / 2 (100.0%) |
| Chinese | 6 | 6 / 6 (100.0%) | 8 / 8 (100.0%) | 0 | 0 | 0 / 26 (0.0%) | 1 / 1 (100.0%) |
| English | 6 | 6 / 6 (100.0%) | 9 / 9 (100.0%) | 0 | 0 | 0 / 41 (0.0%) | 1 / 1 (100.0%) |
| mixed | 4 | 4 / 4 (100.0%) | 5 / 5 (100.0%) | 0 | 0 | 0 / 22 (0.0%) | 0 / 0 (-) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 22 / 22 (100.0%) |
| coin | 22 / 22 (100.0%) |
| quantity | 22 / 22 (100.0%) |
| price | 22 / 22 (100.0%) |
| total | 22 / 22 (100.0%) |
| price_currency | 22 / 22 (100.0%) |
| fee | 22 / 22 (100.0%) |
| fee_currency | 22 / 22 (100.0%) |
| time | 22 / 22 (100.0%) |
| platform | 22 / 22 (100.0%) |
| opinion | 22 / 22 (100.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 242 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 0 |
| - because the model's phrase is not a piece of the passage | 0 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 0 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 0 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (0; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |
| f17: Opened a 5x long on ETH at 2,380 with 100 USDT margin last night | futures_or_leverage | extracted | 1 | draft 1: stopped by SIDE, FEE |
| f18: 用 0.05 BTC 换了 1.3 个 ETH，在 Uniswap 上换的 | coin_for_coin | extracted | 1 | draft 1: stopped by SIDE, FEE, OCCURRED, UNSUPPORTED_QUOTE |
| f19: Placed a limit sell for 2 SOL at 165, still waiting for it to fill | open_order | extracted | 1 | draft 1: stopped by SIDE, ONE_MORE_OF_QUANTITY_PRICE_TOTAL, FEE, OCCURRED |
| f20: 下周想 buy 一点 DOT，大概 4 刀左右就进 | plan | extracted | 0 | - |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| f01 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| f02 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| f03 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| f04 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| f05 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| f06 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| f07 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| f08 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| f09 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| f10 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| f11 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| f12 | mixed | extracted | 2 | 2 | 2 | 0 | 0 | - |
| f13 | zh | extracted | 3 | 3 | 3 | 0 | 0 | - |
| f14 | en | extracted | 4 | 4 | 4 | 0 | 0 | - |
| f15 | zh | extracted | 0 | 0 | 0 | 0 | 0 | - |
| f16 | en | extracted | 0 | 0 | 0 | 0 | 0 | - |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 0 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 0 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |

#### A time written in another language (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

</details>

## 2026-10-09: prompt experiment two, one list or split first, `qwen2.5:7b`

The first prompt experiment read every passage in one call: the model hands
back one list of rows for the whole passage (**one list**). This one
measures the other way to read a passage that reports several trades
(**split first**): the model is first asked to cut the passage into one
segment per trade, and each segment then goes through the same extraction
on its own. Both ways use `first`, the version the rule of the first
experiment picked, with the same 30 debug sentences, the same scoring, the
same model and the same parameters.

How split first goes (`extraction/splitting.py`):

- The split prompt `split-1` (`extraction/prompts/split.py`; few-shot:
  instructions and five invented examples) asks the model to copy out, for
  each trade, the pieces of the passage that trade needs, a detail said once
  for several trades (the day, the exchange, a shared fee) going into each
  of them.
- The program finds every piece in the passage the way extraction finds a
  phrase, and builds each trade's segment from the passage's own text:
  pieces that overlap, touch, or stand apart by nothing but spacing and
  punctuation become one run, and runs that stand apart are joined by a
  full-width comma (`extraction/segments.py`).
- When the split lists fewer than two trades (or gives fewer than two
  segments), the whole passage goes through extraction once, exactly as one
  list. When the split goes wrong (its reply cannot be read after asking
  again, the model fails on it, or a piece is not a piece of the passage),
  the whole passage goes the same way and the line says why: the split
  "fell back".
- With two segments or more, each is extracted on its own; then the rows
  the model wrote for all the segments are read once more against the whole
  passage by extraction's own program side. So every draft's original text
  is the whole passage, a phrase that is not a piece of the whole passage is
  left empty with an issue, and the positions in the issues count among all
  the drafts.

Every sentence line of these two runs also holds the record of every reply
read (`reads`): which call was the split and which extracted a segment, the
rows each reply gave and the draft each row became. The scores take each
draft's phrases from that record (`evals/reads.py`), so that a passage read
in several calls is scored with the phrases of every call; the earlier
runs, which have no such record, are read exactly as before
(`tests/evals/test_earlier_runs_pinned.py`).

**Conditions.** Both runs used `qwen2.5:7b` (fingerprint
`845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`),
Ollama 0.34.3 and the settings' defaults: temperature 0.0, top_p 1.0,
longest reply 1,024 tokens, context 16,384 tokens, 120 seconds per call, 2
retries 1 second apart, and asking again once after a reply that misses its
table (the split's table too). The model was loaded before the first run.
Both runs were made at the same commit, `3a66d50`, one after the other on
2026-10-09 between 05:52 and 05:58 UTC, the one-list run first.

### The two ways on the debug set

The first table holds the scores of the summary (see the top of this file),
with the whole trades right of the passages of one trade, of two and of
three or more apart. The second holds the wrong values with no issue, the
three more counts (see the first experiment), the sentences in which a
reply was cut off, the calls to the model (of them, the calls to split)
and the seconds the sentences took, added up; calls, cut-off replies and
seconds count every sentence of the set, the passages not to record
included.

| Way | Well-formed | Whole trades right | One trade | Two trades | Three or more | No-trade sentences right | Missed | Extra | Made up |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| one list | 26 / 26 (100.0%) | 31 / 34 (91.2%) | 13 / 15 (86.7%) | 10 / 10 (100.0%) | 8 / 9 (88.9%) | 3 / 3 (100.0%) | 0 | 0 | 2 / 140 (1.4%) |
| split first | 26 / 26 (100.0%) | 31 / 34 (91.2%) | 13 / 15 (86.7%) | 10 / 10 (100.0%) | 8 / 9 (88.9%) | 3 / 3 (100.0%) | 0 | 2 | 2 / 140 (1.4%) |

| Way | Wrong values with no issue | A total put as the price | Half copies (any) | Half copies (not right) | A time in another language | Sentences with a reply cut off | Calls | Calls to split | Seconds | Results file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| one list | 2 | 2 | 0 | 0 | 2 | 0 | 30 | 0 | 115.8 | `evals/results/run-20261009T055241Z-debug-first.jsonl` |
| split first | 2 | 2 | 0 | 0 | 2 | 0 | 64 | 30 | 182.8 | `evals/results/run-20261009T055442Z-debug-first-split_first.jsonl` |

The rule, fixed before the two runs (`evals/compare_methods.py`): the most
whole trades right; then the fewest wrong values with no issue; then the
fewest trades missed and extra; then one list. So splitting first is
picked only when it does strictly better.

Picked by the rule: one list, settled at step 3.

- Step 1, most whole trades right: one list, split first.
- Step 2, fewest wrong values with no issue: one list, split first.
- Step 3, fewest trades missed and extra: one list.

Both ways have 31 of 34 trades whole. The two extra trades of split first
are both in d16: each of its two segments starts with the passage's
opening words, which say the coins were bought twice, and the extraction of
each segment gave two rows. In the first segment the two rows are the same,
and the second is marked as given twice; in the second segment, the second
row holds only the shared fee, time and platform. Split first made 64
calls (30 to split, 34 to extract) against 30, and its sentences took
182.8 seconds against 115.8.

### How each passage was split

For every sentence of the split-first run: the trades the split listed,
whether that is the number of gold trades, how many segments were
extracted one by one, the route the passage took (`WHOLE`: fewer than
two trades or segments, the whole passage extracted once;
`PIECE_NOT_IN_PASSAGE`: the split fell back because a piece is not a
piece of the passage), and the whole trades right of each way. The
passages not to record count no score; the split listed one trade for
each of d27, d28 and d29.

| Sentence | Gold trades | Trades the split listed | Same number as gold | Segments extracted | Route | Whole right, one list | Whole right, split first |
| --- | --- | --- | --- | --- | --- | --- | --- |
| d01 | 1 | 1 | yes | 0 | WHOLE | 1 | 1 |
| d02 | 1 | 1 | yes | 0 | WHOLE | 1 | 1 |
| d03 | 1 | 1 | yes | 0 | WHOLE | 1 | 1 |
| d04 | 1 | 1 | yes | 0 | WHOLE | 1 | 1 |
| d05 | 1 | 1 | yes | 0 | WHOLE | 0 | 0 |
| d06 | 1 | 1 | yes | 0 | WHOLE | 1 | 1 |
| d07 | 1 | 1 | yes | 0 | WHOLE | 1 | 1 |
| d08 | 1 | 1 | yes | 0 | WHOLE | 1 | 1 |
| d09 | 1 | 1 | yes | 0 | WHOLE | 1 | 1 |
| d10 | 1 | 1 | yes | 0 | WHOLE | 1 | 1 |
| d11 | 1 | 1 | yes | 0 | WHOLE | 1 | 1 |
| d12 | 1 | 1 | yes | 0 | WHOLE | 1 | 1 |
| d13 | 1 | 1 | yes | 0 | WHOLE | 0 | 0 |
| d14 | 1 | 1 | yes | 0 | WHOLE | 1 | 1 |
| d15 | 1 | 1 | yes | 0 | WHOLE | 1 | 1 |
| d16 | 2 | 2 | yes | 2 | SEGMENTS | 2 | 2 |
| d17 | 2 | 2 | yes | 2 | SEGMENTS | 2 | 2 |
| d18 | 2 | 2 | yes | 0 | PIECE_NOT_IN_PASSAGE | 2 | 2 |
| d19 | 2 | 1 | no | 0 | WHOLE | 2 | 2 |
| d20 | 2 | 2 | yes | 0 | PIECE_NOT_IN_PASSAGE | 2 | 2 |
| d21 | 3 | 3 | yes | 3 | SEGMENTS | 3 | 3 |
| d22 | 3 | 3 | yes | 0 | PIECE_NOT_IN_PASSAGE | 3 | 3 |
| d23 | 3 | 3 | yes | 0 | PIECE_NOT_IN_PASSAGE | 2 | 2 |
| d24 | 0 | 0 | yes | 0 | WHOLE | 0 | 0 |
| d25 | 0 | 0 | yes | 0 | WHOLE | 0 | 0 |
| d26 | 0 | 0 | yes | 0 | WHOLE | 0 | 0 |
| d27 | 0 | 1 | no | 0 | WHOLE | - | - |
| d28 | 0 | 1 | no | 0 | WHOLE | - | - |
| d29 | 0 | 1 | no | 0 | WHOLE | - | - |
| d30 | 0 | 0 | yes | 0 | WHOLE | - | - |

Of the 8 passages with several trades, 3 were extracted segment by
segment (d16, d17, d21); in 4 the split fell back, each over a piece that
joins words standing apart in the passage or leaves a word out of it
(below); in d19 the split listed one trade. A passage that falls back, or
goes whole, is read by the same call as one list.

| Sentence | First piece that is not a piece of the passage | Why |
| --- | --- | --- |
| d18: 昨天下午 3 点 sold 0.02 BTC at 63,900，今天早上 9 点又 buy back 0.025 BTC at 62,750，fee 都是 1.2U | fee 1.2U | the phrase is not a piece of the passage |
| d20: Bought 0.3 BTC at 61,200 and 5 ETH at 2,390 last Saturday | Bought 5 ETH at 2,390 | the phrase is not a piece of the passage |
| d22: Yesterday at 10:30 I bought 1 ETH at 2,350, 0.05 BTC at 62,100 and 20 SOL at 149.5, paying a flat 1 USDT fee on each | bought 0.05 BTC at 62,100 | the phrase is not a piece of the passage |
| d23: 刚才连着 sell 了三笔：0.1 BTC @ 63,000，1.5 ETH @ 2,410，还有 TON 卖了 200 个，total 1,040 USDT | 刚才连着 sell 了三笔：1.5 ETH @ 2,410 | the phrase is not a piece of the passage |

### The one-list run against the first experiment's run of `first`

The same prompt, way, model and parameters, at another commit; between the
two commits nothing changed in extraction but the files added for splitting.

| Sentences in both runs | Same raw replies | Other raw replies | Same raw replies, other drafts or issues |
| --- | --- | --- | --- |
| 30 | 30 | 0 | 0 |

| Sentence | Same raw replies | Same drafts and issues | Whole trades right, earlier | Whole trades right, later |
| --- | --- | --- | --- | --- |

### The final set

Not run in this experiment. The rule picked one list; with it, the prompt
(`first`), the way of reading a passage (one list) and the model
(`qwen2.5:7b`, the same fingerprint) are those of the final-set run of
the first experiment, at temperature 0, so that run stands for this
experiment too (see "Final exam" above):

| Version | Technique | Differs from `first` in | Well-formed | Whole trades right | One trade | Several trades | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | few-shot | the baseline: instructions and ten examples | 16 / 16 (100.0%) | 22 / 22 (100.0%) | 9 / 9 (100.0%) | 13 / 13 (100.0%) | 0 | 0 | 0 / 89 (0.0%) | 2 / 2 (100.0%) |

| Version | Wrong values with no issue | A total put as the price | Half copies (any) | Half copies (not right) | A time in another language | Sentences with a reply cut off | Calls | Seconds | Results file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | 0 | 0 | 0 | 0 | 0 | 0 | 20 | 79.7 | `evals/results/run-20261009T030436Z-final-first.jsonl` |

### A second model

Not obtained: this machine has one model, `qwen2.5:7b`, and no other is
downloaded for this experiment; the second model waits until one is
named. The runner takes another model by name (`--model <name>`) and
records its name and fingerprint in the run line; a name the model server
does not have stops the run before any results file is written, with exit
status 2 (`tests/evals/test_run_second_model.py`; and against the model
server itself, in the live tier, `tests/live/test_live_second_model.py`,
which also reads the server's list of models before and after and finds it
the same).

### The runs of the second experiment

Each run has its own subsection with the tables its results file gives and
its three more counts (`evals/extra_counts.py`).

### Run: debug set, prompt `first`, one list

Results file: `evals/results/run-20261009T055241Z-debug-first.jsonl`, with its summary in `run-20261009T055241Z-debug-first.summary.json`.

<details>
<summary>The generated tables of this run</summary>

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
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| method | one_list |
| commit | 3a66d50db989436f7b724f5c17c0a27bab791acf |
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
| started_at | 2026-10-09T05:52:41+00:00 |
| sentences | 30 |
| sum_of_sentence_seconds | 115.761 |
| first_sentence_seconds | 7.434 |
| longest_sentence_seconds | 8.7 |
| finished_at | 2026-10-09T05:54:37+00:00 |
| seconds_of_the_last_session | 115.809 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 26 | 26 / 26 (100.0%) | 31 / 34 (91.2%) | 0 | 0 | 2 / 140 (1.4%) | 3 / 3 (100.0%) |
| one trade | 15 | 15 / 15 (100.0%) | 13 / 15 (86.7%) | 0 | 0 | 1 / 60 (1.7%) | 0 / 0 (-) |
| several trades | 8 | 8 / 8 (100.0%) | 18 / 19 (94.7%) | 0 | 0 | 1 / 80 (1.2%) | 0 / 0 (-) |
| - two trades | 5 | 5 / 5 (100.0%) | 10 / 10 (100.0%) | 0 | 0 | 0 / 42 (0.0%) | 0 / 0 (-) |
| - three or more trades | 3 | 3 / 3 (100.0%) | 8 / 9 (88.9%) | 0 | 0 | 1 / 38 (2.6%) | 0 / 0 (-) |
| no trade (talk) | 3 | 3 / 3 (100.0%) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 3 / 3 (100.0%) |
| Chinese | 10 | 10 / 10 (100.0%) | 13 / 13 (100.0%) | 0 | 0 | 0 / 52 (0.0%) | 1 / 1 (100.0%) |
| English | 9 | 9 / 9 (100.0%) | 10 / 12 (83.3%) | 0 | 0 | 1 / 49 (2.0%) | 1 / 1 (100.0%) |
| mixed | 7 | 7 / 7 (100.0%) | 8 / 9 (88.9%) | 0 | 0 | 1 / 39 (2.6%) | 1 / 1 (100.0%) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 34 / 34 (100.0%) |
| coin | 34 / 34 (100.0%) |
| quantity | 33 / 34 (97.1%) |
| price | 32 / 34 (94.1%) |
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
| RIGHT: right | 368 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 3 |
| - because the model's phrase is not a piece of the passage | 3 |
| - because the model's phrase cuts a number of the passage | 0 |
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

#### Fields the program left empty (3; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| d05 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| d13 | 1 | time | 昨天 18:20 | yesterday at 18:20 | NOT_IN_PASSAGE | no |
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
| d23 | mixed | extracted | 3 | 3 | 2 | 0 | 0 | 3.quantity:LEFT_EMPTY_WITH_REASON, 3.price:MADE_UP, 3.total:LEFT_EMPTY_BY_MODEL |
| d24 | zh | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d25 | en | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d26 | mixed | extracted | 0 | 0 | 0 | 0 | 0 | - |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 2 |
| Half copies, any field whose phrase is part of the gold phrase | 0 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 2 |

#### A total put as the price (2; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| d05: Bought 120 ADA for 64.80 USDT total yesterday, fee 0.002 BNB | 1 | price | 64.80 USDT | 64.80 | 64.80 USDT | 64.80 |
| d23: 刚才连着 sell 了三笔：0.1 BTC @ 63,000，1.5 ETH @ 2,410，还有 TON 卖了 200 个，total 1,040 USDT | 3 | price | 1,040 USDT | 1040 | 1,040 USDT | 1040 |

#### Half copies, counted the second way (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |

#### A time written in another language (2)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| d05: Bought 120 ADA for 64.80 USDT total yesterday, fee 0.002 BNB | 1 | time | 昨天 | (empty) | yesterday | 2026-10-04 (day) |
| d13: Picked up 40 LINK at 13.85 yesterday at 18:20 while BTC sat near 61k, fee 0 | 1 | time | 昨天 18:20 | (empty) | yesterday at 18:20 | 2026-10-04T18:20:00+02:00 (minute) |

</details>

### Run: debug set, prompt `first`, split first

Results file: `evals/results/run-20261009T055442Z-debug-first-split_first.jsonl`, with its summary in `run-20261009T055442Z-debug-first-split_first.summary.json`.

<details>
<summary>The generated tables of this run</summary>

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
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| method | split_first |
| split_prompt | split-1 |
| split_prompt_files | [{'path': 'src/ledger_hand/extraction/prompts/split.py', 'sha256': 'da420d6d6b38f1ca4942635abc2ee318121d6283a114428c979ff74824caa89b'}] |
| split_prompt_content_sha256 | 12da8704c870064555b00c32d374f08c76bf2d103648030f0f2e43485ad01f7e |
| split_table_sha256 | 9a77d679d7f5e3b671bdb7467492d207cb243837bd7a0c7fd7a8e5a6b08e9eed |
| commit | 3a66d50db989436f7b724f5c17c0a27bab791acf |
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
| started_at | 2026-10-09T05:54:42+00:00 |
| sentences | 30 |
| sum_of_sentence_seconds | 182.76 |
| first_sentence_seconds | 8.128 |
| longest_sentence_seconds | 15.257 |
| finished_at | 2026-10-09T05:57:45+00:00 |
| seconds_of_the_last_session | 182.829 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 26 | 26 / 26 (100.0%) | 31 / 34 (91.2%) | 0 | 2 | 2 / 140 (1.4%) | 3 / 3 (100.0%) |
| one trade | 15 | 15 / 15 (100.0%) | 13 / 15 (86.7%) | 0 | 0 | 1 / 60 (1.7%) | 0 / 0 (-) |
| several trades | 8 | 8 / 8 (100.0%) | 18 / 19 (94.7%) | 0 | 2 | 1 / 80 (1.2%) | 0 / 0 (-) |
| - two trades | 5 | 5 / 5 (100.0%) | 10 / 10 (100.0%) | 0 | 2 | 0 / 42 (0.0%) | 0 / 0 (-) |
| - three or more trades | 3 | 3 / 3 (100.0%) | 8 / 9 (88.9%) | 0 | 0 | 1 / 38 (2.6%) | 0 / 0 (-) |
| no trade (talk) | 3 | 3 / 3 (100.0%) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 3 / 3 (100.0%) |
| Chinese | 10 | 10 / 10 (100.0%) | 13 / 13 (100.0%) | 0 | 2 | 0 / 52 (0.0%) | 1 / 1 (100.0%) |
| English | 9 | 9 / 9 (100.0%) | 10 / 12 (83.3%) | 0 | 0 | 1 / 49 (2.0%) | 1 / 1 (100.0%) |
| mixed | 7 | 7 / 7 (100.0%) | 8 / 9 (88.9%) | 0 | 0 | 1 / 39 (2.6%) | 1 / 1 (100.0%) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 34 / 34 (100.0%) |
| coin | 34 / 34 (100.0%) |
| quantity | 33 / 34 (97.1%) |
| price | 32 / 34 (94.1%) |
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
| RIGHT: right | 368 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 3 |
| - because the model's phrase is not a piece of the passage | 3 |
| - because the model's phrase cuts a number of the passage | 0 |
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

#### Fields the program left empty (3; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| d05 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| d13 | 1 | time | 昨天 18:20 | yesterday at 18:20 | NOT_IN_PASSAGE | no |
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
| d16 | zh | extracted | 2 | 4 | 2 | 0 | 2 | - |
| d17 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d18 | mixed | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d19 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d20 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d21 | zh | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d22 | en | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d23 | mixed | extracted | 3 | 3 | 2 | 0 | 0 | 3.quantity:LEFT_EMPTY_WITH_REASON, 3.price:MADE_UP, 3.total:LEFT_EMPTY_BY_MODEL |
| d24 | zh | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d25 | en | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d26 | mixed | extracted | 0 | 0 | 0 | 0 | 0 | - |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 2 |
| Half copies, any field whose phrase is part of the gold phrase | 0 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 2 |

#### A total put as the price (2; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| d05: Bought 120 ADA for 64.80 USDT total yesterday, fee 0.002 BNB | 1 | price | 64.80 USDT | 64.80 | 64.80 USDT | 64.80 |
| d23: 刚才连着 sell 了三笔：0.1 BTC @ 63,000，1.5 ETH @ 2,410，还有 TON 卖了 200 个，total 1,040 USDT | 3 | price | 1,040 USDT | 1040 | 1,040 USDT | 1040 |

#### Half copies, counted the second way (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |

#### A time written in another language (2)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| d05: Bought 120 ADA for 64.80 USDT total yesterday, fee 0.002 BNB | 1 | time | 昨天 | (empty) | yesterday | 2026-10-04 (day) |
| d13: Picked up 40 LINK at 13.85 yesterday at 18:20 while BTC sat near 61k, fee 0 | 1 | time | 昨天 18:20 | (empty) | yesterday at 18:20 | 2026-10-04T18:20:00+02:00 (minute) |

</details>

## 2026-10-13: second model, `qwen2.5:7b` and `qwen3-vl:8b`

This is the second model that "A second model" in "2026-10-09: prompt
experiment two" says was not obtained then. Two models on this machine,
`qwen2.5:7b` (the one the settings name by default) and `qwen3-vl:8b`, each
ran the debug set, the final set and a fourth set, the voice set, under the
same conditions: the same prompt version, `first`, the same way of reading a
passage, one list, and the same parameters. Only the model differs.

The voice set (`evals/sets/voice.json`, described in `evals/voice.py`) holds
ten passages in the owner's own voice, with invented numbers; voice here
means the owner's own way of writing, not speech. 9 of the 10 passages are
to be recorded, with 10 gold trades between them (8 passages of one trade,
1 of two), and 1 is not to record (u08, an order not filled yet); none is
talk. The set is scored apart and never merged into the debug set, so the
scores of the debug and the final set stay comparable with the sections
above.

**Conditions.** `qwen2.5:7b` (fingerprint
`845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`) and
`qwen3-vl:8b` (fingerprint
`901cae73216286ea8c5aba8b46d307ff7188f737285ec500c795a12f05225d28`),
Ollama 0.34.3, and the settings' defaults in all six runs: temperature 0.0,
top_p 1.0, longest reply 1,024 tokens, context 16,384 tokens, 120 seconds
per call, 2 retries 1 second apart, and asking again once after a reply
that misses its table. No variable starting with `LEDGER_HAND_MODEL_` was
set; each run named its model with `--model`. The plug sends the same
parameters for both models (temperature, top_p, the longest reply and the
context); what it does not send, such as top_k and whether the model thinks
before it replies, is each model's own default. `ollama show qwen3-vl:8b`,
read before the runs, lists its capabilities as completion, vision, tools
and thinking (levels false and true, true by default), and its own
parameters as top_p 0.95, temperature 1 and top_k 20: temperature and top_p
are overridden by the settings, while top_k and thinking are the model's
own. Neither model was loaded on purpose before a run, so the first
sentence of a run may include loading the model into memory. The six runs
were made one after the other on 2026-10-13, at commits that differ only by
the results files of the runs before them:

| Run | Commit | Began (UTC) | Finished (UTC) |
| --- | --- | --- | --- |
| debug set, `qwen2.5:7b` | `f96a60e` | 09:27:24 | 09:29:25 |
| voice set, `qwen2.5:7b` | `511c849` | 09:29:41 | 09:30:26 |
| final set, `qwen2.5:7b` | `6db98b3` | 09:30:36 | 09:31:54 |
| debug set, `qwen3-vl:8b` | `c2daf5c` | 09:32:06 | 09:53:28 |
| voice set, `qwen3-vl:8b` | `4235809` | 09:53:44 | 10:01:24 |
| final set, `qwen3-vl:8b` | `2e80aee` | 10:01:36 | 10:14:52 |

How to read the subsections below. Each is printed by
`evals/compare_models.py` from the two results files. The first two tables
hold the scores (see the top of this file) and the three more counts, the
sentences in which a reply was cut off, the calls to the model, the
sentences and their seconds: added up, per sentence (added up, divided by
the sentences), the first sentence's and the longest sentence's, with the
sentence it was. The third counts what each sentence gave, with the model
failures sorted by kind and, among the malformed replies, the empty replies
apart. A reply is counted as cut off only where the record of its call says
it reached the longest reply (`length_limit`). An empty reply is a failure
of the call: the plug reads the server's answer as malformed, "has an
empty reply" (`src/ledger_hand/llm/ollama_reply.py`), a failure of that
kind is not tried again, and the call leaves no record, so an empty reply
is counted neither as a call nor as cut off. The fourth table is each
field, right of the pairs, for both models; the last lists the sentences
where the two models differ in result, drafts, whole trades right or the
fields not right, and for the voice set every sentence.

### The two models on the debug set

The two runs share the set, the prompt, the way of reading a passage and every parameter; only the model differs: `qwen2.5:7b` and `qwen3-vl:8b`.

| Model | Well-formed | Whole trades right | One trade | Several trades | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `qwen2.5:7b` | 26 / 26 (100.0%) | 31 / 34 (91.2%) | 13 / 15 (86.7%) | 18 / 19 (94.7%) | 0 | 0 | 2 / 140 (1.4%) | 3 / 3 (100.0%) |
| `qwen3-vl:8b` | 5 / 26 (19.2%) | 3 / 34 (8.8%) | 1 / 15 (6.7%) | 2 / 19 (10.5%) | 31 | 0 | 0 / 15 (0.0%) | 3 / 3 (100.0%) |

| Model | Wrong values with no issue | A total put as the price | Half copies (any) | Half copies (not right) | A time in another language | Sentences with a reply cut off | Calls | Sentences | Seconds | Seconds per sentence | First sentence, seconds | Longest sentence, seconds | Results file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `qwen2.5:7b` | 2 | 2 | 0 | 0 | 2 | 0 | 30 | 30 | 121.3 | 4.04 | 8.879 | 8.894 (d22) | `evals/results/run-20261013T092724Z-debug-first.jsonl` |
| `qwen3-vl:8b` | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 30 | 1282.1 | 42.74 | 50.881 | 52.573 (d30) | `evals/results/run-20261013T093206Z-debug-first.jsonl` |

| Result | `qwen2.5:7b` | `qwen3-vl:8b` |
| --- | --- | --- |
| all sentences | 30 | 30 |
| extracted | 30 | 5 |
| reply_unreadable | 0 | 0 |
| model_failed | 0 | 25 |
| - unreachable | 0 | 0 |
| - timed_out | 0 | 0 |
| - model_not_found | 0 | 0 |
| - rate_limited | 0 | 0 |
| - server_error | 0 | 0 |
| - malformed_reply | 0 | 25 |
| - malformed_reply, of them an empty reply | 0 | 25 |
| passage_refused | 0 | 0 |

| Field | `qwen2.5:7b`, right / pairs | `qwen3-vl:8b`, right / pairs |
| --- | --- | --- |
| side | 34 / 34 (100.0%) | 3 / 3 (100.0%) |
| coin | 34 / 34 (100.0%) | 3 / 3 (100.0%) |
| quantity | 33 / 34 (97.1%) | 3 / 3 (100.0%) |
| price | 32 / 34 (94.1%) | 3 / 3 (100.0%) |
| total | 33 / 34 (97.1%) | 3 / 3 (100.0%) |
| price_currency | 34 / 34 (100.0%) | 3 / 3 (100.0%) |
| fee | 34 / 34 (100.0%) | 3 / 3 (100.0%) |
| fee_currency | 34 / 34 (100.0%) | 3 / 3 (100.0%) |
| time | 32 / 34 (94.1%) | 3 / 3 (100.0%) |
| platform | 34 / 34 (100.0%) | 3 / 3 (100.0%) |
| opinion | 34 / 34 (100.0%) | 3 / 3 (100.0%) |

The sentences where the two models differ in result, drafts, whole trades right or the fields not right (25 of 30):

| Sentence | Group | Result, `qwen2.5:7b` | Result, `qwen3-vl:8b` | Drafts, `qwen2.5:7b` | Drafts, `qwen3-vl:8b` | Whole right, `qwen2.5:7b` | Whole right, `qwen3-vl:8b` | Fields not right, `qwen2.5:7b` | Fields not right, `qwen3-vl:8b` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| d01 | scored | extracted | model_failed | 1 | 0 | 1 | 0 | - | - |
| d03 | scored | extracted | model_failed | 1 | 0 | 1 | 0 | - | - |
| d04 | scored | extracted | model_failed | 1 | 0 | 1 | 0 | - | - |
| d05 | scored | extracted | model_failed | 1 | 0 | 0 | 0 | 1.price:MADE_UP, 1.time:LEFT_EMPTY_WITH_REASON | - |
| d06 | scored | extracted | model_failed | 1 | 0 | 1 | 0 | - | - |
| d07 | scored | extracted | model_failed | 1 | 0 | 1 | 0 | - | - |
| d08 | scored | extracted | model_failed | 1 | 0 | 1 | 0 | - | - |
| d09 | scored | extracted | model_failed | 1 | 0 | 1 | 0 | - | - |
| d10 | scored | extracted | model_failed | 1 | 0 | 1 | 0 | - | - |
| d11 | scored | extracted | model_failed | 1 | 0 | 1 | 0 | - | - |
| d12 | scored | extracted | model_failed | 1 | 0 | 1 | 0 | - | - |
| d13 | scored | extracted | model_failed | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON | - |
| d14 | scored | extracted | model_failed | 1 | 0 | 1 | 0 | - | - |
| d15 | scored | extracted | model_failed | 1 | 0 | 1 | 0 | - | - |
| d16 | scored | extracted | model_failed | 2 | 0 | 2 | 0 | - | - |
| d17 | scored | extracted | model_failed | 2 | 0 | 2 | 0 | - | - |
| d18 | scored | extracted | model_failed | 2 | 0 | 2 | 0 | - | - |
| d19 | scored | extracted | model_failed | 2 | 0 | 2 | 0 | - | - |
| d21 | scored | extracted | model_failed | 3 | 0 | 3 | 0 | - | - |
| d22 | scored | extracted | model_failed | 3 | 0 | 3 | 0 | - | - |
| d23 | scored | extracted | model_failed | 3 | 0 | 2 | 0 | 3.quantity:LEFT_EMPTY_WITH_REASON, 3.price:MADE_UP, 3.total:LEFT_EMPTY_BY_MODEL | - |
| d27 | not_to_record | extracted | model_failed | 1 | 0 | - | - | - | - |
| d28 | not_to_record | extracted | model_failed | 2 | 0 | - | - | - | - |
| d29 | not_to_record | extracted | model_failed | 1 | 0 | - | - | - | - |
| d30 | not_to_record | extracted | model_failed | 0 | 0 | - | - | - | - |

Every failure of `qwen3-vl:8b` in its three runs above is of one kind: the
model server's answer held an empty reply, with the start of the model's
thinking beside it. The first, d01, as the results file records it:

```text
malformed_reply: the model server's answer has an empty reply (status 200); the reply began '{"model":"qwen3-vl:8b","created_at":"2026-10-13T09:32:56.94114Z","message":{"role":"assistant","content":"","thinking":"Okay, let\'s tackle this query. The user provided a passage about a trade they ma...'
```

### The two models on the final set

The two runs share the set, the prompt, the way of reading a passage and every parameter; only the model differs: `qwen2.5:7b` and `qwen3-vl:8b`.

| Model | Well-formed | Whole trades right | One trade | Several trades | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `qwen2.5:7b` | 16 / 16 (100.0%) | 22 / 22 (100.0%) | 9 / 9 (100.0%) | 13 / 13 (100.0%) | 0 | 0 | 0 / 89 (0.0%) | 2 / 2 (100.0%) |
| `qwen3-vl:8b` | 4 / 16 (25.0%) | 5 / 22 (22.7%) | 1 / 9 (11.1%) | 4 / 13 (30.8%) | 17 | 0 | 0 / 26 (0.0%) | 2 / 2 (100.0%) |

| Model | Wrong values with no issue | A total put as the price | Half copies (any) | Half copies (not right) | A time in another language | Sentences with a reply cut off | Calls | Sentences | Seconds | Seconds per sentence | First sentence, seconds | Longest sentence, seconds | Results file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `qwen2.5:7b` | 0 | 0 | 0 | 0 | 0 | 0 | 20 | 20 | 77.3 | 3.86 | 3.494 | 10.111 (f14) | `evals/results/run-20261013T093036Z-final-first.jsonl` |
| `qwen3-vl:8b` | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 20 | 794.9 | 39.75 | 44.161 | 48.593 (f06) | `evals/results/run-20261013T100136Z-final-first.jsonl` |

| Result | `qwen2.5:7b` | `qwen3-vl:8b` |
| --- | --- | --- |
| all sentences | 20 | 20 |
| extracted | 20 | 5 |
| reply_unreadable | 0 | 0 |
| model_failed | 0 | 15 |
| - unreachable | 0 | 0 |
| - timed_out | 0 | 0 |
| - model_not_found | 0 | 0 |
| - rate_limited | 0 | 0 |
| - server_error | 0 | 0 |
| - malformed_reply | 0 | 15 |
| - malformed_reply, of them an empty reply | 0 | 15 |
| passage_refused | 0 | 0 |

| Field | `qwen2.5:7b`, right / pairs | `qwen3-vl:8b`, right / pairs |
| --- | --- | --- |
| side | 22 / 22 (100.0%) | 5 / 5 (100.0%) |
| coin | 22 / 22 (100.0%) | 5 / 5 (100.0%) |
| quantity | 22 / 22 (100.0%) | 5 / 5 (100.0%) |
| price | 22 / 22 (100.0%) | 5 / 5 (100.0%) |
| total | 22 / 22 (100.0%) | 5 / 5 (100.0%) |
| price_currency | 22 / 22 (100.0%) | 5 / 5 (100.0%) |
| fee | 22 / 22 (100.0%) | 5 / 5 (100.0%) |
| fee_currency | 22 / 22 (100.0%) | 5 / 5 (100.0%) |
| time | 22 / 22 (100.0%) | 5 / 5 (100.0%) |
| platform | 22 / 22 (100.0%) | 5 / 5 (100.0%) |
| opinion | 22 / 22 (100.0%) | 5 / 5 (100.0%) |

The sentences where the two models differ in result, drafts, whole trades right or the fields not right (15 of 20):

| Sentence | Group | Result, `qwen2.5:7b` | Result, `qwen3-vl:8b` | Drafts, `qwen2.5:7b` | Drafts, `qwen3-vl:8b` | Whole right, `qwen2.5:7b` | Whole right, `qwen3-vl:8b` | Fields not right, `qwen2.5:7b` | Fields not right, `qwen3-vl:8b` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| f01 | scored | extracted | model_failed | 1 | 0 | 1 | 0 | - | - |
| f03 | scored | extracted | model_failed | 1 | 0 | 1 | 0 | - | - |
| f04 | scored | extracted | model_failed | 1 | 0 | 1 | 0 | - | - |
| f05 | scored | extracted | model_failed | 1 | 0 | 1 | 0 | - | - |
| f06 | scored | extracted | model_failed | 1 | 0 | 1 | 0 | - | - |
| f07 | scored | extracted | model_failed | 1 | 0 | 1 | 0 | - | - |
| f08 | scored | extracted | model_failed | 1 | 0 | 1 | 0 | - | - |
| f09 | scored | extracted | model_failed | 1 | 0 | 1 | 0 | - | - |
| f10 | scored | extracted | model_failed | 2 | 0 | 2 | 0 | - | - |
| f11 | scored | extracted | model_failed | 2 | 0 | 2 | 0 | - | - |
| f12 | scored | extracted | model_failed | 2 | 0 | 2 | 0 | - | - |
| f13 | scored | extracted | model_failed | 3 | 0 | 3 | 0 | - | - |
| f17 | not_to_record | extracted | model_failed | 1 | 0 | - | - | - | - |
| f18 | not_to_record | extracted | model_failed | 1 | 0 | - | - | - | - |
| f19 | not_to_record | extracted | model_failed | 1 | 0 | - | - | - | - |

### The two models on the voice set

The two runs share the set, the prompt, the way of reading a passage and every parameter; only the model differs: `qwen2.5:7b` and `qwen3-vl:8b`.

| Model | Well-formed | Whole trades right | One trade | Several trades | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `qwen2.5:7b` | 9 / 9 (100.0%) | 1 / 10 (10.0%) | 1 / 8 (12.5%) | 0 / 2 (0.0%) | 0 | 0 | 4 / 12 (33.3%) | 0 / 0 (-) |
| `qwen3-vl:8b` | 1 / 9 (11.1%) | 0 / 10 (0.0%) | 0 / 8 (0.0%) | 0 / 2 (0.0%) | 9 | 0 | 1 / 3 (33.3%) | 0 / 0 (-) |

| Model | Wrong values with no issue | A total put as the price | Half copies (any) | Half copies (not right) | A time in another language | Sentences with a reply cut off | Calls | Sentences | Seconds | Seconds per sentence | First sentence, seconds | Longest sentence, seconds | Results file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `qwen2.5:7b` | 6 | 0 | 2 | 2 | 0 | 0 | 10 | 10 | 45.0 | 4.50 | 4.458 | 8.731 (u09) | `evals/results/run-20261013T092941Z-voice-first.jsonl` |
| `qwen3-vl:8b` | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 10 | 460.3 | 46.03 | 45.316 | 54.74 (u04) | `evals/results/run-20261013T095344Z-voice-first.jsonl` |

| Result | `qwen2.5:7b` | `qwen3-vl:8b` |
| --- | --- | --- |
| all sentences | 10 | 10 |
| extracted | 10 | 1 |
| reply_unreadable | 0 | 0 |
| model_failed | 0 | 9 |
| - unreachable | 0 | 0 |
| - timed_out | 0 | 0 |
| - model_not_found | 0 | 0 |
| - rate_limited | 0 | 0 |
| - server_error | 0 | 0 |
| - malformed_reply | 0 | 9 |
| - malformed_reply, of them an empty reply | 0 | 9 |
| passage_refused | 0 | 0 |

| Field | `qwen2.5:7b`, right / pairs | `qwen3-vl:8b`, right / pairs |
| --- | --- | --- |
| side | 8 / 10 (80.0%) | 1 / 1 (100.0%) |
| coin | 10 / 10 (100.0%) | 1 / 1 (100.0%) |
| quantity | 7 / 10 (70.0%) | 0 / 1 (0.0%) |
| price | 10 / 10 (100.0%) | 0 / 1 (0.0%) |
| total | 7 / 10 (70.0%) | 0 / 1 (0.0%) |
| price_currency | 7 / 10 (70.0%) | 0 / 1 (0.0%) |
| fee | 9 / 10 (90.0%) | 1 / 1 (100.0%) |
| fee_currency | 9 / 10 (90.0%) | 1 / 1 (100.0%) |
| time | 10 / 10 (100.0%) | 1 / 1 (100.0%) |
| platform | 10 / 10 (100.0%) | 1 / 1 (100.0%) |
| opinion | 5 / 10 (50.0%) | 1 / 1 (100.0%) |

Every sentence (10 of 10):

| Sentence | Group | Result, `qwen2.5:7b` | Result, `qwen3-vl:8b` | Drafts, `qwen2.5:7b` | Drafts, `qwen3-vl:8b` | Whole right, `qwen2.5:7b` | Whole right, `qwen3-vl:8b` | Fields not right, `qwen2.5:7b` | Fields not right, `qwen3-vl:8b` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| u01 | scored | extracted | model_failed | 1 | 0 | 0 | 0 | 1.quantity:LEFT_EMPTY_WITH_REASON, 1.opinion:WRONG_SILENT | - |
| u02 | scored | extracted | model_failed | 1 | 0 | 0 | 0 | 1.quantity:MADE_UP, 1.total:LEFT_EMPTY_BY_MODEL, 1.price_currency:LEFT_EMPTY_BY_MODEL | - |
| u03 | scored | extracted | model_failed | 1 | 0 | 0 | 0 | 1.opinion:WRONG_SILENT | - |
| u04 | scored | extracted | model_failed | 1 | 0 | 1 | 0 | - | - |
| u05 | scored | extracted | model_failed | 1 | 0 | 0 | 0 | 1.opinion:WRONG_SILENT | - |
| u06 | scored | extracted | model_failed | 1 | 0 | 0 | 0 | 1.total:LEFT_EMPTY_BY_MODEL, 1.price_currency:LEFT_EMPTY_BY_MODEL, 1.fee:MADE_UP, 1.fee_currency:MADE_UP | - |
| u07 | scored | extracted | model_failed | 1 | 0 | 0 | 0 | 1.side:LEFT_EMPTY_BY_MODEL | - |
| u08 | not_to_record | extracted | model_failed | 1 | 0 | - | - | - | - |
| u09 | scored | extracted | model_failed | 2 | 0 | 0 | 0 | 1.opinion:WRONG_SILENT, 2.opinion:LEFT_EMPTY_BY_MODEL | - |
| u10 | scored | extracted | extracted | 1 | 1 | 0 | 0 | 1.side:LEFT_EMPTY_BY_MODEL, 1.quantity:MADE_UP, 1.total:LEFT_EMPTY_BY_MODEL, 1.price_currency:LEFT_EMPTY_BY_MODEL | 1.quantity:MADE_UP, 1.price:LEFT_EMPTY_WITH_REASON, 1.total:LEFT_EMPTY_BY_MODEL, 1.price_currency:LEFT_EMPTY_WITH_REASON |

### `qwen2.5:7b` against its earlier runs

`qwen2.5:7b` ran the final set once before, in the first prompt
experiment, and the debug set with one list in the second. Its two runs
here are compared with those, sentence by sentence (`evals/same_replies.py`,
the earlier run first): the same prompt, way, model, fingerprint and
parameters, at other commits. This is reported, not judged.

The debug set, against `evals/results/run-20261009T055241Z-debug-first.jsonl`:

| Sentences in both runs | Same raw replies | Other raw replies | Same raw replies, other drafts or issues |
| --- | --- | --- | --- |
| 30 | 30 | 0 | 0 |

| Sentence | Same raw replies | Same drafts and issues | Whole trades right, earlier | Whole trades right, later |
| --- | --- | --- | --- | --- |

The final set, against `evals/results/run-20261009T030436Z-final-first.jsonl`:

| Sentences in both runs | Same raw replies | Other raw replies | Same raw replies, other drafts or issues |
| --- | --- | --- | --- |
| 20 | 20 | 0 | 0 |

| Sentence | Same raw replies | Same drafts and issues | Whole trades right, earlier | Whole trades right, later |
| --- | --- | --- | --- | --- |

### The numbers in short

On the debug set `qwen2.5:7b` got 31 of 34 trades whole and `qwen3-vl:8b`
3 of 34; on the final set 22 of 22 and 5 of 22; on the voice set 1 of 10
and 0 of 10. `qwen3-vl:8b` gave no draft in 25 of the 30 debug sentences,
15 of the 20 final ones and 9 of the 10 voice ones: each of these ended in
an empty reply. In the pairs it did make, every field was right on the
debug set (3 pairs) and on the final set (5 pairs); on the voice set its
one pair (u10) had the quantity, the price, the total and the price
currency not right. On the voice set the fields `qwen2.5:7b` got right
least often were the opinion (5 of 10), the quantity, the total and the
price currency (7 of 10 each) and the side (8 of 10); four of its opinions
(u01, u03, u05 and the first trade of u09) are wrong values with no issue
about them. Per sentence `qwen2.5:7b` took 4.04 seconds on the debug set,
3.86 on the final set and 4.50 on the voice set, its longest sentence
8.894 (d22), 10.111 (f14) and 8.731 (u09) seconds; `qwen3-vl:8b` took
42.74, 39.75 and 46.03, its longest 52.573 (d30), 48.593 (f06) and 54.74
(u04) seconds.

### Parameter comparisons of `qwen3-vl:8b`

Each changes one setting of the `qwen3-vl:8b` run of the debug set above,
with its environment variable, and was made after the six runs; neither is
in the tables above, and neither stands for any of their numbers. Each
table shows the run with the settings' defaults first and the comparison
second.

**1. Longest reply 2,048 tokens** (instead of 1,024; set with
`LEDGER_HAND_MODEL_MAX_REPLY_TOKENS=2048`), at commit `aeb0378`, from
10:15:12 to 10:53:15 UTC. With the defaults, 25 of the 30 sentences ended
in an empty reply after 43.619 to 52.573 seconds each, the model's thinking
beside it; this shows what twice the room for the reply does. 2,048 was
chosen so that a reply of that length can still come back within the 120
seconds a call is given.

| Version | Technique | Differs from `first` in | Well-formed | Whole trades right | One trade | Several trades | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | few-shot | the baseline: instructions and ten examples | 5 / 26 (19.2%) | 3 / 34 (8.8%) | 1 / 15 (6.7%) | 2 / 19 (10.5%) | 31 | 0 | 0 / 15 (0.0%) | 3 / 3 (100.0%) |
| `first` | few-shot | the baseline: instructions and ten examples | 12 / 26 (46.2%) | 15 / 34 (44.1%) | 4 / 15 (26.7%) | 11 / 19 (57.9%) | 18 | 0 | 0 / 69 (0.0%) | 3 / 3 (100.0%) |

| Version | Wrong values with no issue | A total put as the price | Half copies (any) | Half copies (not right) | A time in another language | Sentences with a reply cut off | Calls | Seconds | Results file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 1282.1 | `evals/results/run-20261013T093206Z-debug-first.jsonl` |
| `first` | 0 | 0 | 0 | 0 | 0 | 0 | 14 | 2283.0 | `evals/results/run-20261013T101512Z-debug-first.jsonl` |

With 2,048 tokens, 14 of the 30 sentences were answered, the longest reply
2,004 tokens (d06), and 16 ended in an empty reply, after 89.528 to 100.182
seconds each.

**2. Longest reply 4,096 tokens** (instead of 1,024; set with
`LEDGER_HAND_MODEL_MAX_REPLY_TOKENS=4096`), at commit `d49e730`, from
10:53:45 to 12:32:49 UTC. With 2,048 tokens 16 sentences still ended in an
empty reply; this gives the reply four times the room of the defaults, so
that the 120 seconds a call is given are what limits it instead.

| Version | Technique | Differs from `first` in | Well-formed | Whole trades right | One trade | Several trades | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | few-shot | the baseline: instructions and ten examples | 5 / 26 (19.2%) | 3 / 34 (8.8%) | 1 / 15 (6.7%) | 2 / 19 (10.5%) | 31 | 0 | 0 / 15 (0.0%) | 3 / 3 (100.0%) |
| `first` | few-shot | the baseline: instructions and ten examples | 14 / 26 (53.8%) | 18 / 34 (52.9%) | 4 / 15 (26.7%) | 14 / 19 (73.7%) | 14 | 0 | 1 / 83 (1.2%) | 3 / 3 (100.0%) |

| Version | Wrong values with no issue | A total put as the price | Half copies (any) | Half copies (not right) | A time in another language | Sentences with a reply cut off | Calls | Seconds | Results file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 1282.1 | `evals/results/run-20261013T093206Z-debug-first.jsonl` |
| `first` | 1 | 0 | 0 | 0 | 0 | 0 | 17 | 5944.0 | `evals/results/run-20261013T105345Z-debug-first.jsonl` |

With 4,096 tokens, 17 of the 30 sentences were answered, the longest reply
2,402 tokens (d21, in 118.8 seconds), and 13 got no complete answer within
120 seconds (`timed_out`): each such call was tried three times (two
retries), 363.106 to 363.159 seconds a sentence. The first, d04, as the
results file records it:

```text
timed_out: no complete answer from the model server at http://127.0.0.1:11434 within 120 seconds
```

No third comparison was made.

### The runs of the second-model comparison

Each run has its own subsection with the tables its results file gives and
its three more counts (`evals/extra_counts.py`).

### Run: debug set, `qwen2.5:7b`

Results file: `evals/results/run-20261013T092724Z-debug-first.jsonl`, with its summary in `run-20261013T092724Z-debug-first.summary.json`.

<details>
<summary>The generated tables of this run</summary>

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
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| method | one_list |
| commit | f96a60e46a8d82314191f59d13fd1a47687e9795 |
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
| started_at | 2026-10-13T09:27:24+00:00 |
| sentences | 30 |
| sum_of_sentence_seconds | 121.291 |
| first_sentence_seconds | 8.879 |
| longest_sentence_seconds | 8.894 |
| finished_at | 2026-10-13T09:29:25+00:00 |
| seconds_of_the_last_session | 121.333 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 26 | 26 / 26 (100.0%) | 31 / 34 (91.2%) | 0 | 0 | 2 / 140 (1.4%) | 3 / 3 (100.0%) |
| one trade | 15 | 15 / 15 (100.0%) | 13 / 15 (86.7%) | 0 | 0 | 1 / 60 (1.7%) | 0 / 0 (-) |
| several trades | 8 | 8 / 8 (100.0%) | 18 / 19 (94.7%) | 0 | 0 | 1 / 80 (1.2%) | 0 / 0 (-) |
| - two trades | 5 | 5 / 5 (100.0%) | 10 / 10 (100.0%) | 0 | 0 | 0 / 42 (0.0%) | 0 / 0 (-) |
| - three or more trades | 3 | 3 / 3 (100.0%) | 8 / 9 (88.9%) | 0 | 0 | 1 / 38 (2.6%) | 0 / 0 (-) |
| no trade (talk) | 3 | 3 / 3 (100.0%) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 3 / 3 (100.0%) |
| Chinese | 10 | 10 / 10 (100.0%) | 13 / 13 (100.0%) | 0 | 0 | 0 / 52 (0.0%) | 1 / 1 (100.0%) |
| English | 9 | 9 / 9 (100.0%) | 10 / 12 (83.3%) | 0 | 0 | 1 / 49 (2.0%) | 1 / 1 (100.0%) |
| mixed | 7 | 7 / 7 (100.0%) | 8 / 9 (88.9%) | 0 | 0 | 1 / 39 (2.6%) | 1 / 1 (100.0%) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 34 / 34 (100.0%) |
| coin | 34 / 34 (100.0%) |
| quantity | 33 / 34 (97.1%) |
| price | 32 / 34 (94.1%) |
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
| RIGHT: right | 368 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 3 |
| - because the model's phrase is not a piece of the passage | 3 |
| - because the model's phrase cuts a number of the passage | 0 |
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

#### Fields the program left empty (3; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| d05 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| d13 | 1 | time | 昨天 18:20 | yesterday at 18:20 | NOT_IN_PASSAGE | no |
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
| d23 | mixed | extracted | 3 | 3 | 2 | 0 | 0 | 3.quantity:LEFT_EMPTY_WITH_REASON, 3.price:MADE_UP, 3.total:LEFT_EMPTY_BY_MODEL |
| d24 | zh | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d25 | en | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d26 | mixed | extracted | 0 | 0 | 0 | 0 | 0 | - |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 2 |
| Half copies, any field whose phrase is part of the gold phrase | 0 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 2 |

#### A total put as the price (2; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| d05: Bought 120 ADA for 64.80 USDT total yesterday, fee 0.002 BNB | 1 | price | 64.80 USDT | 64.80 | 64.80 USDT | 64.80 |
| d23: 刚才连着 sell 了三笔：0.1 BTC @ 63,000，1.5 ETH @ 2,410，还有 TON 卖了 200 个，total 1,040 USDT | 3 | price | 1,040 USDT | 1040 | 1,040 USDT | 1040 |

#### Half copies, counted the second way (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |

#### A time written in another language (2)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| d05: Bought 120 ADA for 64.80 USDT total yesterday, fee 0.002 BNB | 1 | time | 昨天 | (empty) | yesterday | 2026-10-04 (day) |
| d13: Picked up 40 LINK at 13.85 yesterday at 18:20 while BTC sat near 61k, fee 0 | 1 | time | 昨天 18:20 | (empty) | yesterday at 18:20 | 2026-10-04T18:20:00+02:00 (minute) |

</details>

### Run: final set, `qwen2.5:7b`

Results file: `evals/results/run-20261013T093036Z-final-first.jsonl`, with its summary in `run-20261013T093036Z-final-first.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | final |
| final_exam_switch | True |
| set_file | evals/sets/final.json |
| set_sha256 | 34afdeb36b787d7e62a6a1a0149838c2dfde8c186a1bb89ea6b3de1205090406 |
| prompt | first |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | 7a510f4aaf16f7830ea5df2ec2071a276006565014e61bf295aa44a57a297112 |
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| method | one_list |
| commit | 6db98b31c55e26b4aaadae2a84a81dbc131facc7 |
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
| started_at | 2026-10-13T09:30:36+00:00 |
| sentences | 20 |
| sum_of_sentence_seconds | 77.291 |
| first_sentence_seconds | 3.494 |
| longest_sentence_seconds | 10.111 |
| finished_at | 2026-10-13T09:31:54+00:00 |
| seconds_of_the_last_session | 77.318 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 16 | 16 / 16 (100.0%) | 22 / 22 (100.0%) | 0 | 0 | 0 / 89 (0.0%) | 2 / 2 (100.0%) |
| one trade | 9 | 9 / 9 (100.0%) | 9 / 9 (100.0%) | 0 | 0 | 0 / 35 (0.0%) | 0 / 0 (-) |
| several trades | 5 | 5 / 5 (100.0%) | 13 / 13 (100.0%) | 0 | 0 | 0 / 54 (0.0%) | 0 / 0 (-) |
| - two trades | 3 | 3 / 3 (100.0%) | 6 / 6 (100.0%) | 0 | 0 | 0 / 21 (0.0%) | 0 / 0 (-) |
| - three or more trades | 2 | 2 / 2 (100.0%) | 7 / 7 (100.0%) | 0 | 0 | 0 / 33 (0.0%) | 0 / 0 (-) |
| no trade (talk) | 2 | 2 / 2 (100.0%) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 2 / 2 (100.0%) |
| Chinese | 6 | 6 / 6 (100.0%) | 8 / 8 (100.0%) | 0 | 0 | 0 / 26 (0.0%) | 1 / 1 (100.0%) |
| English | 6 | 6 / 6 (100.0%) | 9 / 9 (100.0%) | 0 | 0 | 0 / 41 (0.0%) | 1 / 1 (100.0%) |
| mixed | 4 | 4 / 4 (100.0%) | 5 / 5 (100.0%) | 0 | 0 | 0 / 22 (0.0%) | 0 / 0 (-) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 22 / 22 (100.0%) |
| coin | 22 / 22 (100.0%) |
| quantity | 22 / 22 (100.0%) |
| price | 22 / 22 (100.0%) |
| total | 22 / 22 (100.0%) |
| price_currency | 22 / 22 (100.0%) |
| fee | 22 / 22 (100.0%) |
| fee_currency | 22 / 22 (100.0%) |
| time | 22 / 22 (100.0%) |
| platform | 22 / 22 (100.0%) |
| opinion | 22 / 22 (100.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 242 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 0 |
| - because the model's phrase is not a piece of the passage | 0 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 0 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 0 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (0; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |
| f17: Opened a 5x long on ETH at 2,380 with 100 USDT margin last night | futures_or_leverage | extracted | 1 | draft 1: stopped by SIDE, FEE |
| f18: 用 0.05 BTC 换了 1.3 个 ETH，在 Uniswap 上换的 | coin_for_coin | extracted | 1 | draft 1: stopped by SIDE, FEE, OCCURRED, UNSUPPORTED_QUOTE |
| f19: Placed a limit sell for 2 SOL at 165, still waiting for it to fill | open_order | extracted | 1 | draft 1: stopped by SIDE, ONE_MORE_OF_QUANTITY_PRICE_TOTAL, FEE, OCCURRED |
| f20: 下周想 buy 一点 DOT，大概 4 刀左右就进 | plan | extracted | 0 | - |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| f01 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| f02 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| f03 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| f04 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| f05 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| f06 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| f07 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| f08 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| f09 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| f10 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| f11 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| f12 | mixed | extracted | 2 | 2 | 2 | 0 | 0 | - |
| f13 | zh | extracted | 3 | 3 | 3 | 0 | 0 | - |
| f14 | en | extracted | 4 | 4 | 4 | 0 | 0 | - |
| f15 | zh | extracted | 0 | 0 | 0 | 0 | 0 | - |
| f16 | en | extracted | 0 | 0 | 0 | 0 | 0 | - |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 0 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 0 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |

#### A time written in another language (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

</details>

### Run: voice set, `qwen2.5:7b`

Results file: `evals/results/run-20261013T092941Z-voice-first.jsonl`, with its summary in `run-20261013T092941Z-voice-first.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | voice |
| final_exam_switch | False |
| set_file | evals/sets/voice.json |
| set_sha256 | 884e678672d4fcedc2d36da18e96e7e70261785936b4fc48cd2a3259d2b35196 |
| prompt | first |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | 7a510f4aaf16f7830ea5df2ec2071a276006565014e61bf295aa44a57a297112 |
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| method | one_list |
| commit | 511c84966843d33ef8c1c9753edfc02e42e0d9d2 |
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
| started_at | 2026-10-13T09:29:41+00:00 |
| sentences | 10 |
| sum_of_sentence_seconds | 45.039 |
| first_sentence_seconds | 4.458 |
| longest_sentence_seconds | 8.731 |
| finished_at | 2026-10-13T09:30:26+00:00 |
| seconds_of_the_last_session | 45.052 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 9 | 9 / 9 (100.0%) | 1 / 10 (10.0%) | 0 | 0 | 4 / 12 (33.3%) | 0 / 0 (-) |
| one trade | 8 | 8 / 8 (100.0%) | 1 / 8 (12.5%) | 0 | 0 | 4 / 12 (33.3%) | 0 / 0 (-) |
| several trades | 1 | 1 / 1 (100.0%) | 0 / 2 (0.0%) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| - two trades | 1 | 1 / 1 (100.0%) | 0 / 2 (0.0%) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| - three or more trades | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| no trade (talk) | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| Chinese | 9 | 9 / 9 (100.0%) | 1 / 10 (10.0%) | 0 | 0 | 4 / 12 (33.3%) | 0 / 0 (-) |
| English | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| mixed | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 8 / 10 (80.0%) |
| coin | 10 / 10 (100.0%) |
| quantity | 7 / 10 (70.0%) |
| price | 10 / 10 (100.0%) |
| total | 7 / 10 (70.0%) |
| price_currency | 7 / 10 (70.0%) |
| fee | 9 / 10 (90.0%) |
| fee_currency | 9 / 10 (90.0%) |
| time | 10 / 10 (100.0%) |
| platform | 10 / 10 (100.0%) |
| opinion | 5 / 10 (50.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 92 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 1 |
| - because the model's phrase is not a piece of the passage | 1 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 9 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 4 |
| MADE_UP: a value in the draft where the gold answer is empty | 4 |
| - of them with an issue about the field | 2 |

#### Wrong values in drafts with no issue about them (6)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |
| u01: 今晚23:41在OKX买入ADA，花了30USDT，成交96.6494个，均价0.3104，手续费0.0966494ADA。ADA是我目前亏损最多的币种-45%，现在低位购买目的是拉低ADA平均持仓成本 | 1 | opinion | 低位购买目的是拉低ADA平均持仓成本 | 低位购买目的是拉低ADA平均持仓成本 | ADA是我目前亏损最多的币种-45%，现在低位购买目的是拉低ADA平均持仓成本 | WRONG_SILENT |
| u03: 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的。10:18在OKX买的，50USDT，均价0.3218，手续费0.1553ADA | 1 | opinion | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | WRONG_SILENT |
| u05: BTC 60000有支撑，买点，毕竟在牛市初期，无论是60,000还是62,000或是等到突破66,000之后回调的60,000都是一样的。今早8点05分OKX买入0.00040811BTC，花了25USDT，均价61,258.60，手续费0.0000004BTC | 1 | opinion | BTC 60000有支撑，买点，毕竟在牛市初期，无论是60,000还是62,000或是等到突破66,000之后回调的60,000都是一样的。 | BTC 60000有支撑，买点，毕竟在牛市初期，无论是60,000还是62,000或是等到突破66,000之后回调的60,000都是一样的。 | BTC 60000有支撑，买点，毕竟在牛市初期，无论是60,000还是62,000或是等到突破66,000之后回调的60,000都是一样的 | WRONG_SILENT |
| u06: BTC又回到6万附近了，OKX补了30U，成交价60,412，牛市初期不怕 | 1 | fee | 30U | 30 | (empty) | MADE_UP |
| u06: BTC又回到6万附近了，OKX补了30U，成交价60,412，牛市初期不怕 | 1 | fee_currency | (empty) | U | (empty) | MADE_UP |
| u09: BTC跌破60000了，今天下午3点50在OKX补仓BTC，100USDT买到0.00167785BTC，均价59,600，手续费0.00000168BTC；好久没买ETH了，顺手20USDT买了0.008291ETH，均价2,412.25，手续费0.00000829ETH | 1 | opinion | 均价59,600，手续费0.00000168BTC | 均价59,600，手续费0.00000168BTC | BTC跌破60000了 | WRONG_SILENT |

#### Half copies: the model copied part of the gold phrase (2)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |
| u01 | 1 | opinion | 低位购买目的是拉低ADA平均持仓成本 | 低位购买目的是拉低ADA平均持仓成本 | ADA是我目前亏损最多的币种-45%，现在低位购买目的是拉低ADA平均持仓成本 | WRONG_SILENT |
| u03 | 1 | opinion | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | WRONG_SILENT |

#### Fields the program left empty (1; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| u01 | 1 | quantity | 96.6494 个 | 96.6494个 | NOT_IN_PASSAGE | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |
| u08: 在OKX挂了个BTC限价单，59,500买100U，觉得这里是强支撑，等它触发 | open_order | extracted | 1 | draft 1: stopped by SIDE, ONE_MORE_OF_QUANTITY_PRICE_TOTAL, FEE, OCCURRED |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| u01 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.quantity:LEFT_EMPTY_WITH_REASON, 1.opinion:WRONG_SILENT |
| u02 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.quantity:MADE_UP, 1.total:LEFT_EMPTY_BY_MODEL, 1.price_currency:LEFT_EMPTY_BY_MODEL |
| u03 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.opinion:WRONG_SILENT |
| u04 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| u05 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.opinion:WRONG_SILENT |
| u06 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.total:LEFT_EMPTY_BY_MODEL, 1.price_currency:LEFT_EMPTY_BY_MODEL, 1.fee:MADE_UP, 1.fee_currency:MADE_UP |
| u07 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.side:LEFT_EMPTY_BY_MODEL |
| u09 | zh | extracted | 2 | 2 | 0 | 0 | 0 | 1.opinion:WRONG_SILENT, 2.opinion:LEFT_EMPTY_BY_MODEL |
| u10 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.side:LEFT_EMPTY_BY_MODEL, 1.quantity:MADE_UP, 1.total:LEFT_EMPTY_BY_MODEL, 1.price_currency:LEFT_EMPTY_BY_MODEL |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 2 |
| Half copies, only fields not right (as in the summary) | 2 |
| A time written in another language | 0 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (2)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| u01: 今晚23:41在OKX买入ADA，花了30USDT，成交96.6494个，均价0.3104，手续费0.0966494ADA。ADA是我目前亏损最多的币种-45%，现在低位购买目的是拉低ADA平均持仓成本 | 1 | opinion | 低位购买目的是拉低ADA平均持仓成本 | 低位购买目的是拉低ADA平均持仓成本 | ADA是我目前亏损最多的币种-45%，现在低位购买目的是拉低ADA平均持仓成本 | ADA是我目前亏损最多的币种-45%，现在低位购买目的是拉低ADA平均持仓成本 | no |
| u03: 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的。10:18在OKX买的，50USDT，均价0.3218，手续费0.1553ADA | 1 | opinion | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | no |

#### A time written in another language (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

</details>

### Run: debug set, `qwen3-vl:8b`

Results file: `evals/results/run-20261013T093206Z-debug-first.jsonl`, with its summary in `run-20261013T093206Z-debug-first.summary.json`.

<details>
<summary>The generated tables of this run</summary>

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
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| method | one_list |
| commit | c2daf5c5923af851e53dfead182617da651e83e3 |
| worktree_clean | True |
| model | qwen3-vl:8b |
| model_fingerprint | 901cae73216286ea8c5aba8b46d307ff7188f737285ec500c795a12f05225d28 |
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
| started_at | 2026-10-13T09:32:06+00:00 |
| sentences | 30 |
| sum_of_sentence_seconds | 1282.061 |
| first_sentence_seconds | 50.881 |
| longest_sentence_seconds | 52.573 |
| finished_at | 2026-10-13T09:53:28+00:00 |
| seconds_of_the_last_session | 1282.16 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 26 | 5 / 26 (19.2%) | 3 / 34 (8.8%) | 31 | 0 | 0 / 15 (0.0%) | 3 / 3 (100.0%) |
| one trade | 15 | 1 / 15 (6.7%) | 1 / 15 (6.7%) | 14 | 0 | 0 / 3 (0.0%) | 0 / 0 (-) |
| several trades | 8 | 1 / 8 (12.5%) | 2 / 19 (10.5%) | 17 | 0 | 0 / 12 (0.0%) | 0 / 0 (-) |
| - two trades | 5 | 1 / 5 (20.0%) | 2 / 10 (20.0%) | 8 | 0 | 0 / 12 (0.0%) | 0 / 0 (-) |
| - three or more trades | 3 | 0 / 3 (0.0%) | 0 / 9 (0.0%) | 9 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| no trade (talk) | 3 | 3 / 3 (100.0%) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 3 / 3 (100.0%) |
| Chinese | 10 | 1 / 10 (10.0%) | 0 / 13 (0.0%) | 13 | 0 | 0 / 0 (-) | 1 / 1 (100.0%) |
| English | 9 | 3 / 9 (33.3%) | 3 / 12 (25.0%) | 9 | 0 | 0 / 15 (0.0%) | 1 / 1 (100.0%) |
| mixed | 7 | 1 / 7 (14.3%) | 0 / 9 (0.0%) | 9 | 0 | 0 / 0 (-) | 1 / 1 (100.0%) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 3 / 3 (100.0%) |
| coin | 3 / 3 (100.0%) |
| quantity | 3 / 3 (100.0%) |
| price | 3 / 3 (100.0%) |
| total | 3 / 3 (100.0%) |
| price_currency | 3 / 3 (100.0%) |
| fee | 3 / 3 (100.0%) |
| fee_currency | 3 / 3 (100.0%) |
| time | 3 / 3 (100.0%) |
| platform | 3 / 3 (100.0%) |
| opinion | 3 / 3 (100.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 33 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 0 |
| - because the model's phrase is not a piece of the passage | 0 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 0 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 0 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (0; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |
| d27: 昨天开了 10 倍杠杆做多 BTC，开仓价 62,800，保证金 200U | futures_or_leverage | model_failed | 0 | - |
| d28: Swapped 0.5 ETH for 0.019 BTC on Uniswap this morning | coin_for_coin | model_failed | 0 | - |
| d29: 挂了一个 limit buy，0.05 BTC @ 58,000，还没成交 | open_order | model_failed | 0 | - |
| d30: 打算明天下午 3 点买 1 个 ETH，价格到 2,300 就进 | plan | model_failed | 0 | - |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| d01 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d02 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d03 | mixed | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d04 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d05 | en | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d06 | mixed | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d07 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d08 | en | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d09 | mixed | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d10 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d11 | en | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d12 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d13 | en | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d14 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d15 | mixed | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d16 | zh | model_failed | 2 | 0 | 0 | 2 | 0 | - |
| d17 | en | model_failed | 2 | 0 | 0 | 2 | 0 | - |
| d18 | mixed | model_failed | 2 | 0 | 0 | 2 | 0 | - |
| d19 | zh | model_failed | 2 | 0 | 0 | 2 | 0 | - |
| d20 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d21 | zh | model_failed | 3 | 0 | 0 | 3 | 0 | - |
| d22 | en | model_failed | 3 | 0 | 0 | 3 | 0 | - |
| d23 | mixed | model_failed | 3 | 0 | 0 | 3 | 0 | - |
| d24 | zh | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d25 | en | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d26 | mixed | extracted | 0 | 0 | 0 | 0 | 0 | - |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 0 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 0 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |

#### A time written in another language (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

</details>

### Run: final set, `qwen3-vl:8b`

Results file: `evals/results/run-20261013T100136Z-final-first.jsonl`, with its summary in `run-20261013T100136Z-final-first.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | final |
| final_exam_switch | True |
| set_file | evals/sets/final.json |
| set_sha256 | 34afdeb36b787d7e62a6a1a0149838c2dfde8c186a1bb89ea6b3de1205090406 |
| prompt | first |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | 7a510f4aaf16f7830ea5df2ec2071a276006565014e61bf295aa44a57a297112 |
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| method | one_list |
| commit | 2e80aee8e29a013cd8d9ad76ec762ff1fae995c0 |
| worktree_clean | True |
| model | qwen3-vl:8b |
| model_fingerprint | 901cae73216286ea8c5aba8b46d307ff7188f737285ec500c795a12f05225d28 |
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
| started_at | 2026-10-13T10:01:36+00:00 |
| sentences | 20 |
| sum_of_sentence_seconds | 794.945 |
| first_sentence_seconds | 44.161 |
| longest_sentence_seconds | 48.593 |
| finished_at | 2026-10-13T10:14:52+00:00 |
| seconds_of_the_last_session | 795.013 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 16 | 4 / 16 (25.0%) | 5 / 22 (22.7%) | 17 | 0 | 0 / 26 (0.0%) | 2 / 2 (100.0%) |
| one trade | 9 | 1 / 9 (11.1%) | 1 / 9 (11.1%) | 8 | 0 | 0 / 2 (0.0%) | 0 / 0 (-) |
| several trades | 5 | 1 / 5 (20.0%) | 4 / 13 (30.8%) | 9 | 0 | 0 / 24 (0.0%) | 0 / 0 (-) |
| - two trades | 3 | 0 / 3 (0.0%) | 0 / 6 (0.0%) | 6 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| - three or more trades | 2 | 1 / 2 (50.0%) | 4 / 7 (57.1%) | 3 | 0 | 0 / 24 (0.0%) | 0 / 0 (-) |
| no trade (talk) | 2 | 2 / 2 (100.0%) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 2 / 2 (100.0%) |
| Chinese | 6 | 1 / 6 (16.7%) | 0 / 8 (0.0%) | 8 | 0 | 0 / 0 (-) | 1 / 1 (100.0%) |
| English | 6 | 3 / 6 (50.0%) | 5 / 9 (55.6%) | 4 | 0 | 0 / 26 (0.0%) | 1 / 1 (100.0%) |
| mixed | 4 | 0 / 4 (0.0%) | 0 / 5 (0.0%) | 5 | 0 | 0 / 0 (-) | 0 / 0 (-) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 5 / 5 (100.0%) |
| coin | 5 / 5 (100.0%) |
| quantity | 5 / 5 (100.0%) |
| price | 5 / 5 (100.0%) |
| total | 5 / 5 (100.0%) |
| price_currency | 5 / 5 (100.0%) |
| fee | 5 / 5 (100.0%) |
| fee_currency | 5 / 5 (100.0%) |
| time | 5 / 5 (100.0%) |
| platform | 5 / 5 (100.0%) |
| opinion | 5 / 5 (100.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 55 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 0 |
| - because the model's phrase is not a piece of the passage | 0 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 0 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 0 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (0; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |
| f17: Opened a 5x long on ETH at 2,380 with 100 USDT margin last night | futures_or_leverage | model_failed | 0 | - |
| f18: 用 0.05 BTC 换了 1.3 个 ETH，在 Uniswap 上换的 | coin_for_coin | model_failed | 0 | - |
| f19: Placed a limit sell for 2 SOL at 165, still waiting for it to fill | open_order | model_failed | 0 | - |
| f20: 下周想 buy 一点 DOT，大概 4 刀左右就进 | plan | extracted | 0 | - |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| f01 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| f02 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| f03 | mixed | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| f04 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| f05 | en | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| f06 | mixed | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| f07 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| f08 | en | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| f09 | mixed | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| f10 | zh | model_failed | 2 | 0 | 0 | 2 | 0 | - |
| f11 | en | model_failed | 2 | 0 | 0 | 2 | 0 | - |
| f12 | mixed | model_failed | 2 | 0 | 0 | 2 | 0 | - |
| f13 | zh | model_failed | 3 | 0 | 0 | 3 | 0 | - |
| f14 | en | extracted | 4 | 4 | 4 | 0 | 0 | - |
| f15 | zh | extracted | 0 | 0 | 0 | 0 | 0 | - |
| f16 | en | extracted | 0 | 0 | 0 | 0 | 0 | - |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 0 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 0 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |

#### A time written in another language (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

</details>

### Run: voice set, `qwen3-vl:8b`

Results file: `evals/results/run-20261013T095344Z-voice-first.jsonl`, with its summary in `run-20261013T095344Z-voice-first.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | voice |
| final_exam_switch | False |
| set_file | evals/sets/voice.json |
| set_sha256 | 884e678672d4fcedc2d36da18e96e7e70261785936b4fc48cd2a3259d2b35196 |
| prompt | first |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | 7a510f4aaf16f7830ea5df2ec2071a276006565014e61bf295aa44a57a297112 |
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| method | one_list |
| commit | 4235809224ccfd2d3454765b74c6a05f3d83691c |
| worktree_clean | True |
| model | qwen3-vl:8b |
| model_fingerprint | 901cae73216286ea8c5aba8b46d307ff7188f737285ec500c795a12f05225d28 |
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
| started_at | 2026-10-13T09:53:44+00:00 |
| sentences | 10 |
| sum_of_sentence_seconds | 460.341 |
| first_sentence_seconds | 45.316 |
| longest_sentence_seconds | 54.74 |
| finished_at | 2026-10-13T10:01:24+00:00 |
| seconds_of_the_last_session | 460.432 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 9 | 1 / 9 (11.1%) | 0 / 10 (0.0%) | 9 | 0 | 1 / 3 (33.3%) | 0 / 0 (-) |
| one trade | 8 | 1 / 8 (12.5%) | 0 / 8 (0.0%) | 7 | 0 | 1 / 3 (33.3%) | 0 / 0 (-) |
| several trades | 1 | 0 / 1 (0.0%) | 0 / 2 (0.0%) | 2 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| - two trades | 1 | 0 / 1 (0.0%) | 0 / 2 (0.0%) | 2 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| - three or more trades | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| no trade (talk) | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| Chinese | 9 | 1 / 9 (11.1%) | 0 / 10 (0.0%) | 9 | 0 | 1 / 3 (33.3%) | 0 / 0 (-) |
| English | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| mixed | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 1 / 1 (100.0%) |
| coin | 1 / 1 (100.0%) |
| quantity | 0 / 1 (0.0%) |
| price | 0 / 1 (0.0%) |
| total | 0 / 1 (0.0%) |
| price_currency | 0 / 1 (0.0%) |
| fee | 1 / 1 (100.0%) |
| fee_currency | 1 / 1 (100.0%) |
| time | 1 / 1 (100.0%) |
| platform | 1 / 1 (100.0%) |
| opinion | 1 / 1 (100.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 7 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 2 |
| - because the model's phrase is not a piece of the passage | 0 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 2 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 1 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 1 |
| - of them with an issue about the field | 1 |

#### Wrong values in drafts with no issue about them (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (2; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| u10 | 1 | price | 2,388一个 | 2,388 | NUMBER_NOT_READ | no |
| u10 | 1 | price_currency | (empty) | U | NUMBER_NOT_READ | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |
| u08: 在OKX挂了个BTC限价单，59,500买100U，觉得这里是强支撑，等它触发 | open_order | model_failed | 0 | - |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| u01 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| u02 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| u03 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| u04 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| u05 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| u06 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| u07 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| u09 | zh | model_failed | 2 | 0 | 0 | 2 | 0 | - |
| u10 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.quantity:MADE_UP, 1.price:LEFT_EMPTY_WITH_REASON, 1.total:LEFT_EMPTY_BY_MODEL, 1.price_currency:LEFT_EMPTY_WITH_REASON |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 0 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 0 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |

#### A time written in another language (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

</details>

### Run: parameter comparison 1, debug set, `qwen3-vl:8b`, longest reply 2,048 tokens

Results file: `evals/results/run-20261013T101512Z-debug-first.jsonl`, with its summary in `run-20261013T101512Z-debug-first.summary.json`.

One parameter changed from the run of `qwen3-vl:8b` on the debug set above: the longest reply, 1,024 tokens there and 2,048 here (set with `LEDGER_HAND_MODEL_MAX_REPLY_TOKENS=2048`). Not one of the runs compared side by side.

<details>
<summary>The generated tables of this run</summary>

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
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| method | one_list |
| commit | aeb03789e4531ff8e90683834b5355dbf57cc849 |
| worktree_clean | True |
| model | qwen3-vl:8b |
| model_fingerprint | 901cae73216286ea8c5aba8b46d307ff7188f737285ec500c795a12f05225d28 |
| server_version | 0.34.3 |
| base_url | http://127.0.0.1:11434 |
| parameter temperature | 0.0 |
| parameter top_p | 1.0 |
| parameter max_reply_tokens | 2048 |
| parameter context_tokens | 16384 |
| parameter timeout_seconds | 120.0 |
| parameter retries | 2 |
| parameter retry_wait_seconds | 1.0 |
| parameter asks_again | 1 |
| coin_table | built-in |
| started_at | 2026-10-13T10:15:12+00:00 |
| sentences | 30 |
| sum_of_sentence_seconds | 2282.954 |
| first_sentence_seconds | 75.59 |
| longest_sentence_seconds | 100.182 |
| finished_at | 2026-10-13T10:53:15+00:00 |
| seconds_of_the_last_session | 2283.052 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 26 | 12 / 26 (46.2%) | 15 / 34 (44.1%) | 18 | 0 | 0 / 69 (0.0%) | 3 / 3 (100.0%) |
| one trade | 15 | 4 / 15 (26.7%) | 4 / 15 (26.7%) | 11 | 0 | 0 / 12 (0.0%) | 0 / 0 (-) |
| several trades | 8 | 5 / 8 (62.5%) | 11 / 19 (57.9%) | 7 | 0 | 0 / 57 (0.0%) | 0 / 0 (-) |
| - two trades | 5 | 3 / 5 (60.0%) | 6 / 10 (60.0%) | 4 | 0 | 0 / 28 (0.0%) | 0 / 0 (-) |
| - three or more trades | 3 | 2 / 3 (66.7%) | 5 / 9 (55.6%) | 3 | 0 | 0 / 29 (0.0%) | 0 / 0 (-) |
| no trade (talk) | 3 | 3 / 3 (100.0%) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 3 / 3 (100.0%) |
| Chinese | 10 | 3 / 10 (30.0%) | 3 / 13 (23.1%) | 10 | 0 | 0 / 12 (0.0%) | 1 / 1 (100.0%) |
| English | 9 | 5 / 9 (55.6%) | 8 / 12 (66.7%) | 4 | 0 | 0 / 33 (0.0%) | 1 / 1 (100.0%) |
| mixed | 7 | 4 / 7 (57.1%) | 4 / 9 (44.4%) | 4 | 0 | 0 / 24 (0.0%) | 1 / 1 (100.0%) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 16 / 16 (100.0%) |
| coin | 16 / 16 (100.0%) |
| quantity | 15 / 16 (93.8%) |
| price | 16 / 16 (100.0%) |
| total | 16 / 16 (100.0%) |
| price_currency | 16 / 16 (100.0%) |
| fee | 16 / 16 (100.0%) |
| fee_currency | 16 / 16 (100.0%) |
| time | 16 / 16 (100.0%) |
| platform | 16 / 16 (100.0%) |
| opinion | 16 / 16 (100.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 175 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 1 |
| - because the model's phrase is not a piece of the passage | 1 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 0 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 0 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (1; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| d23 | 3 | quantity | 200 个 TON | 200 个 | NOT_IN_PASSAGE | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |
| d27: 昨天开了 10 倍杠杆做多 BTC，开仓价 62,800，保证金 200U | futures_or_leverage | model_failed | 0 | - |
| d28: Swapped 0.5 ETH for 0.019 BTC on Uniswap this morning | coin_for_coin | model_failed | 0 | - |
| d29: 挂了一个 limit buy，0.05 BTC @ 58,000，还没成交 | open_order | extracted | 1 | draft 1: stopped by FEE, OCCURRED |
| d30: 打算明天下午 3 点买 1 个 ETH，价格到 2,300 就进 | plan | extracted | 1 | draft 1: stopped by FEE, OCCURRED |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| d01 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d02 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d03 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d04 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d05 | en | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d06 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d07 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d08 | en | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d09 | mixed | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d10 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d11 | en | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d12 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d13 | en | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d14 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d15 | mixed | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d16 | zh | model_failed | 2 | 0 | 0 | 2 | 0 | - |
| d17 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d18 | mixed | model_failed | 2 | 0 | 0 | 2 | 0 | - |
| d19 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d20 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d21 | zh | model_failed | 3 | 0 | 0 | 3 | 0 | - |
| d22 | en | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d23 | mixed | extracted | 3 | 3 | 2 | 0 | 0 | 3.quantity:LEFT_EMPTY_WITH_REASON |
| d24 | zh | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d25 | en | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d26 | mixed | extracted | 0 | 0 | 0 | 0 | 0 | - |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 0 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 0 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |

#### A time written in another language (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

</details>

### Run: parameter comparison 2, debug set, `qwen3-vl:8b`, longest reply 4,096 tokens

Results file: `evals/results/run-20261013T105345Z-debug-first.jsonl`, with its summary in `run-20261013T105345Z-debug-first.summary.json`.

One parameter changed from the run of `qwen3-vl:8b` on the debug set above: the longest reply, 1,024 tokens there and 4,096 here (set with `LEDGER_HAND_MODEL_MAX_REPLY_TOKENS=4096`). Not one of the runs compared side by side.

<details>
<summary>The generated tables of this run</summary>

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
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| method | one_list |
| commit | d49e73099eb69c9d72b2119da7675f2fa9277499 |
| worktree_clean | True |
| model | qwen3-vl:8b |
| model_fingerprint | 901cae73216286ea8c5aba8b46d307ff7188f737285ec500c795a12f05225d28 |
| server_version | 0.34.3 |
| base_url | http://127.0.0.1:11434 |
| parameter temperature | 0.0 |
| parameter top_p | 1.0 |
| parameter max_reply_tokens | 4096 |
| parameter context_tokens | 16384 |
| parameter timeout_seconds | 120.0 |
| parameter retries | 2 |
| parameter retry_wait_seconds | 1.0 |
| parameter asks_again | 1 |
| coin_table | built-in |
| started_at | 2026-10-13T10:53:45+00:00 |
| sentences | 30 |
| sum_of_sentence_seconds | 5944.04 |
| first_sentence_seconds | 76.787 |
| longest_sentence_seconds | 363.159 |
| finished_at | 2026-10-13T12:32:49+00:00 |
| seconds_of_the_last_session | 5944.195 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 26 | 14 / 26 (53.8%) | 18 / 34 (52.9%) | 14 | 0 | 1 / 83 (1.2%) | 3 / 3 (100.0%) |
| one trade | 15 | 5 / 15 (33.3%) | 4 / 15 (26.7%) | 10 | 0 | 1 / 17 (5.9%) | 0 / 0 (-) |
| several trades | 8 | 6 / 8 (75.0%) | 14 / 19 (73.7%) | 4 | 0 | 0 / 66 (0.0%) | 0 / 0 (-) |
| - two trades | 5 | 3 / 5 (60.0%) | 6 / 10 (60.0%) | 4 | 0 | 0 / 28 (0.0%) | 0 / 0 (-) |
| - three or more trades | 3 | 3 / 3 (100.0%) | 8 / 9 (88.9%) | 0 | 0 | 0 / 38 (0.0%) | 0 / 0 (-) |
| no trade (talk) | 3 | 3 / 3 (100.0%) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 3 / 3 (100.0%) |
| Chinese | 10 | 4 / 10 (40.0%) | 6 / 13 (46.2%) | 7 | 0 | 0 / 21 (0.0%) | 1 / 1 (100.0%) |
| English | 9 | 6 / 9 (66.7%) | 8 / 12 (66.7%) | 3 | 0 | 1 / 38 (2.6%) | 1 / 1 (100.0%) |
| mixed | 7 | 4 / 7 (57.1%) | 4 / 9 (44.4%) | 4 | 0 | 0 / 24 (0.0%) | 1 / 1 (100.0%) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 20 / 20 (100.0%) |
| coin | 20 / 20 (100.0%) |
| quantity | 19 / 20 (95.0%) |
| price | 20 / 20 (100.0%) |
| total | 20 / 20 (100.0%) |
| price_currency | 20 / 20 (100.0%) |
| fee | 20 / 20 (100.0%) |
| fee_currency | 20 / 20 (100.0%) |
| time | 20 / 20 (100.0%) |
| platform | 20 / 20 (100.0%) |
| opinion | 19 / 20 (95.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 218 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 1 |
| - because the model's phrase is not a piece of the passage | 1 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 0 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 1 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (1)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |
| d13: Picked up 40 LINK at 13.85 yesterday at 18:20 while BTC sat near 61k, fee 0 | 1 | opinion | while BTC sat near 61k | while BTC sat near 61k | (empty) | MADE_UP |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (1; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| d23 | 3 | quantity | 200 个 TON | 200 个 | NOT_IN_PASSAGE | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |
| d27: 昨天开了 10 倍杠杆做多 BTC，开仓价 62,800，保证金 200U | futures_or_leverage | model_failed | 0 | - |
| d28: Swapped 0.5 ETH for 0.019 BTC on Uniswap this morning | coin_for_coin | extracted | 2 | draft 1: stopped by ONE_MORE_OF_QUANTITY_PRICE_TOTAL, FEE; draft 2: stopped by ONE_MORE_OF_QUANTITY_PRICE_TOTAL, FEE |
| d29: 挂了一个 limit buy，0.05 BTC @ 58,000，还没成交 | open_order | extracted | 1 | draft 1: stopped by FEE, OCCURRED |
| d30: 打算明天下午 3 点买 1 个 ETH，价格到 2,300 就进 | plan | extracted | 1 | draft 1: stopped by FEE, OCCURRED |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| d01 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d02 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d03 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d04 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d05 | en | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d06 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d07 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d08 | en | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d09 | mixed | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d10 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d11 | en | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d12 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d13 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.opinion:MADE_UP |
| d14 | zh | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d15 | mixed | model_failed | 1 | 0 | 0 | 1 | 0 | - |
| d16 | zh | model_failed | 2 | 0 | 0 | 2 | 0 | - |
| d17 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d18 | mixed | model_failed | 2 | 0 | 0 | 2 | 0 | - |
| d19 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d20 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d21 | zh | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d22 | en | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d23 | mixed | extracted | 3 | 3 | 2 | 0 | 0 | 3.quantity:LEFT_EMPTY_WITH_REASON |
| d24 | zh | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d25 | en | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d26 | mixed | extracted | 0 | 0 | 0 | 0 | 0 | - |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 0 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 0 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |

#### A time written in another language (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

</details>

## 2026-10-18: prompt experiment three, more examples for the owner's way of writing, `qwen2.5:7b`

On the ten passages of the voice set, `qwen2.5:7b` with the prompt `first`
got 1 of 10 trades whole ("The two models on the voice set" in "2026-10-13:
second model, `qwen2.5:7b` and `qwen3-vl:8b`"). Its errors there were of
five kinds: an amount with U right after it, which is the total, copied as
the quantity or the fee ("再补20U", "补了30U", "25U买了点ETH"); a long
opinion copied in part, or with the mark that sets it apart from the trade;
a quantity written right against the Chinese copied with a space added; a
buy said with 买到, 买了点 or as a limit order filled, left with no side; and
the opinions of the two trades of one passage. This experiment measures a
prompt version written for those kinds: `second`
(`src/ledger_hand/extraction/prompts/second.py`, its examples in
`src/ledger_hand/extraction/prompts/second_examples.py`).

`second` changes two things from `first` at once, so its runs cannot tell
which of the two made a difference. Its instructions are those of `first`,
unchanged, followed by two rules: the owner's words for a buy (补, 补了, 再补,
补仓, 买到, 买了点), and that an amount with U or USDT right after it, with no
个 and no coin name beside it, said neither as the fee nor as the price of
one coin, is the total and never the quantity or the fee. Its examples are
the ten of `first`, unchanged and in their order, followed by six more,
invented and written the way the owner writes (no space between Chinese and
a number, buys only, on OKX, the fee paid in the coin bought): three show an
amount in U that is the total, said with 补了, 再补 and 买了点; four a long
opinion with a price or a percentage in it that is not the trade's price,
before the trade or after it, copied whole and without the mark that sets
it apart; every one a quantity, a price or a fee written right against the
Chinese; between them 买到, 买了点, 补仓 and a limit order filled, each a buy;
and two show two trades in one passage that share the time and the
exchange, each with an opinion of its own. Its words for asking again and
its reply table are those of `first`.

`third` (`src/ledger_hand/extraction/prompts/third.py`) was written after
the runs of `second`, and after reading its errors on the debug, the voice
and the writings set: on English passages of the debug and the writings set
`second` copied some times in Chinese ("今天早上" for "this morning", which
one of its six examples writes) and in d11 a quantity as "0.02 个比特币", the
words of an example of `first`. `third` is `first` with the two rules of
`second` and none of its six examples: its instructions are those of
`second`, its examples the ten of `first`, unchanged. Set beside `second`, it
shows what the two rules do without the six examples.

Two facts bear on every number below. The new examples were written after
the errors of `first` on the voice set, so the scores of a candidate on the
voice set are not scores on passages it has not seen; the only passages it
has not seen are those of the final set and of the owner's later use.
`third` was written after `second`'s errors on the debug and the writings
set as well, so its scores on those two sets are not scores on passages it
has not seen either. And
`first` already gets every trade of the final set whole, so the final set
can show only whether a candidate falls behind `first`, not whether it does
better.

### The rule

The rule below picks a candidate over `first`, and the final-set line after
it says when a candidate passes the final set. Both were written into the
module description of `evals/compare_sets.py` and committed in `48250bf`,
the commit the first run of this experiment was made at, before any run of
it; `--choose` and `--final` print them as they stand here. The rule:

A candidate is picked when, and only when, all five of these hold, each
against the run of `first` made in the same experiment:

1. on the voice set, more whole trades right than `first`;
2. on the debug set, no fewer whole trades right than `first`;
3. on the debug set, no more wrong values with no issue about them than
   `first` (the list "Wrong values in drafts with no issue about them" of
   the summary, the made-up values with no issue included);
4. on the debug set, no more trades missed and extra, added up over all
   scored sentences, than `first`;
5. on the voice set, no more wrong values with no issue about them than
   `first`.

The writings set is shown beside the debug and the voice set, with the same
counts, and judged by none of the five. The seconds are shown only. A later
candidate is held to the same rule against `first`, never against an
earlier candidate.

The final-set line:

The final set is run once, with the candidate the rule picked, and only
then. Its run is compared with an earlier run of `first` on the final set,
of the same model with the same parameters, and passes when all three of
these hold:

1. no fewer whole trades right than `first`;
2. no more trades missed and extra, added up over all scored sentences,
   than `first`;
3. no more wrong values with no issue about them than `first`.

### Conditions

`qwen2.5:7b` (fingerprint
`845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`), Ollama
0.34.3, and the settings' defaults in every run: temperature 0.0, top_p 1.0,
longest reply 1,024 tokens, context 16,384 tokens, 120 seconds per call, 2
retries 1 second apart, and asking again once after a reply that misses its
table; every passage read in one list. No variable starting with
`LEDGER_HAND_MODEL_` was set; each run named its model with `--model`. The
model was not loaded on purpose before a run, so the first sentence of a run
may include loading it into memory. `first` has the content fingerprint of
its earlier runs (`7a510f4aaf16f7830ea5df2ec2071a276006565014e61bf295aa44a57a297112`),
`second` has `8b20aa9f69064c8bf6fb87d7db9b526d3befec4c769d3a9d2ed4611e3ed2cc68`
and `third` `facabbe239e4ab100df1bb517ff25160711508d206f30f15d6185ac5d0001a65`.
The six runs of `first` and `second` were made one after the other on
2026-10-18, at commits that differ only by the results files of the runs
before them. The three runs of `third` were made on 2026-10-19, once this
section up to the rule applied to `second` and the file of `third` were
committed, again one after the other at commits that differ only by the
results files of the runs before them:

| Run | Commit | Began (UTC) | Finished (UTC) |
| --- | --- | --- | --- |
| debug set, `first` | `48250bf` | 2026-10-18 17:37:52 | 2026-10-18 17:39:50 |
| voice set, `first` | `3459426` | 2026-10-18 17:40:17 | 2026-10-18 17:41:02 |
| writings set, `first` | `fd326a0` | 2026-10-18 17:41:14 | 2026-10-18 17:42:21 |
| debug set, `second` | `1975b55` | 2026-10-18 17:42:35 | 2026-10-18 17:44:38 |
| voice set, `second` | `0bbd9e7` | 2026-10-18 17:44:49 | 2026-10-18 17:45:33 |
| writings set, `second` | `b17e746` | 2026-10-18 17:45:42 | 2026-10-18 17:46:53 |
| debug set, `third` | `5aba53f` | 2026-10-19 07:48:47 | 2026-10-19 07:50:54 |
| voice set, `third` | `8a62e97` | 2026-10-19 07:51:07 | 2026-10-19 07:51:54 |
| writings set, `third` | `f847fd0` | 2026-10-19 07:52:08 | 2026-10-19 07:53:17 |

How to read the subsections below. Each is printed by `evals/compare_sets.py`
from the results files of one set, `first` first. The first two tables hold
the scores (see the top of this file) and the three more counts, the
sentences in which a reply was cut off, the calls to the model, the
sentences and their seconds: added up, per sentence (added up, divided by
the sentences), the first sentence's and the longest sentence's, with the
sentence it was. The third is each field, right of the pairs, for each
version (all scored sentences). The last lists, for the voice set, every
sentence, and for the other two sets every sentence not to record and the
sentences where the versions differ in result, drafts, whole trades right or
the fields not right. A sentence not to record shows its drafts and, for
each, whether it passes the check of a draft (`stopped` or `passes`); it is
counted in no score. The last column names a candidate that gets fewer
trades of a scored sentence whole right than `first`.

### The versions on the debug set

The runs share the set, the model, the way of reading a passage and every parameter; only the prompt version differs: `first`, `second`, `third`.

| Version | Well-formed | Whole trades right | One trade | Several trades | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | 26 / 26 (100.0%) | 31 / 34 (91.2%) | 13 / 15 (86.7%) | 18 / 19 (94.7%) | 0 | 0 | 2 / 140 (1.4%) | 3 / 3 (100.0%) |
| `second` | 26 / 26 (100.0%) | 29 / 34 (85.3%) | 10 / 15 (66.7%) | 19 / 19 (100.0%) | 0 | 0 | 2 / 140 (1.4%) | 3 / 3 (100.0%) |
| `third` | 26 / 26 (100.0%) | 30 / 34 (88.2%) | 13 / 15 (86.7%) | 17 / 19 (89.5%) | 0 | 0 | 1 / 140 (0.7%) | 3 / 3 (100.0%) |

| Version | Wrong values with no issue | A total put as the price | Half copies (any) | Half copies (not right) | A time in another language | Sentences with a reply cut off | Calls | Sentences | Seconds | Seconds per sentence | First sentence, seconds | Longest sentence, seconds | Results file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | 2 | 2 | 0 | 0 | 2 | 0 | 30 | 30 | 118.6 | 3.95 | 8.841 | 8.841 (d01) | `evals/results/run-20261018T173752Z-debug-first.jsonl` |
| `second` | 2 | 0 | 2 | 0 | 3 | 0 | 30 | 30 | 122.4 | 4.08 | 9.002 | 9.327 (d22) | `evals/results/run-20261018T174235Z-debug-second.jsonl` |
| `third` | 1 | 1 | 0 | 0 | 2 | 0 | 30 | 30 | 126.6 | 4.22 | 9.9 | 9.9 (d01) | `evals/results/run-20261019T074847Z-debug-third.jsonl` |

| Field | `first`, right / pairs | `second`, right / pairs | `third`, right / pairs |
| --- | --- | --- | --- |
| side | 34 / 34 (100.0%) | 34 / 34 (100.0%) | 34 / 34 (100.0%) |
| coin | 34 / 34 (100.0%) | 34 / 34 (100.0%) | 34 / 34 (100.0%) |
| quantity | 33 / 34 (97.1%) | 32 / 34 (94.1%) | 33 / 34 (97.1%) |
| price | 32 / 34 (94.1%) | 33 / 34 (97.1%) | 32 / 34 (94.1%) |
| total | 33 / 34 (97.1%) | 33 / 34 (97.1%) | 33 / 34 (97.1%) |
| price_currency | 34 / 34 (100.0%) | 33 / 34 (97.1%) | 34 / 34 (100.0%) |
| fee | 34 / 34 (100.0%) | 34 / 34 (100.0%) | 34 / 34 (100.0%) |
| fee_currency | 34 / 34 (100.0%) | 34 / 34 (100.0%) | 34 / 34 (100.0%) |
| time | 32 / 34 (94.1%) | 31 / 34 (91.2%) | 32 / 34 (94.1%) |
| platform | 34 / 34 (100.0%) | 34 / 34 (100.0%) | 34 / 34 (100.0%) |
| opinion | 34 / 34 (100.0%) | 34 / 34 (100.0%) | 34 / 34 (100.0%) |

The sentences where the versions differ in result, drafts, whole trades right or the fields not right, and every sentence not to record (11 of 30):

| Sentence | Group | Result, `first` | Result, `second` | Result, `third` | Drafts, `first` | Drafts, `second` | Drafts, `third` | Whole right, `first` | Whole right, `second` | Whole right, `third` | Fields not right, `first` | Fields not right, `second` | Fields not right, `third` | Checks of the drafts, `first` | Checks of the drafts, `second` | Checks of the drafts, `third` | Fewer whole right than `first` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| d04 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 1 | 0 | 1 | - | 1.price:LEFT_EMPTY_WITH_REASON | - | - | - | - | `second` |
| d05 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 0 | 0 | 0 | 1.price:MADE_UP, 1.time:LEFT_EMPTY_WITH_REASON | 1.time:LEFT_EMPTY_WITH_REASON | 1.time:LEFT_EMPTY_WITH_REASON | - | - | - | - |
| d08 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 1 | 0 | 1 | - | 1.time:LEFT_EMPTY_WITH_REASON | - | - | - | - | `second` |
| d11 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 1 | 0 | 1 | - | 1.quantity:LEFT_EMPTY_WITH_REASON | - | - | - | - | `second` |
| d13 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON | 1.quantity:LEFT_EMPTY_BY_MODEL, 1.total:MADE_UP, 1.price_currency:MADE_UP, 1.time:LEFT_EMPTY_WITH_REASON | 1.time:LEFT_EMPTY_WITH_REASON | - | - | - | - |
| d19 | scored | extracted | extracted | extracted | 2 | 2 | 2 | 2 | 2 | 1 | - | - | 1.price:LEFT_EMPTY_WITH_REASON | - | - | - | `third` |
| d23 | scored | extracted | extracted | extracted | 3 | 3 | 3 | 2 | 3 | 2 | 3.quantity:LEFT_EMPTY_WITH_REASON, 3.price:MADE_UP, 3.total:LEFT_EMPTY_BY_MODEL | - | 3.quantity:LEFT_EMPTY_WITH_REASON, 3.price:MADE_UP, 3.total:LEFT_EMPTY_BY_MODEL | - | - | - | - |
| d27 | not_to_record | extracted | extracted | extracted | 1 | 1 | 1 | - | - | - | - | - | - | stopped | stopped | stopped | - |
| d28 | not_to_record | extracted | extracted | extracted | 2 | 2 | 2 | - | - | - | - | - | - | stopped, stopped | stopped, stopped | stopped, stopped | - |
| d29 | not_to_record | extracted | extracted | extracted | 1 | 0 | 1 | - | - | - | - | - | - | stopped | - | stopped | - |
| d30 | not_to_record | extracted | extracted | extracted | 0 | 0 | 0 | - | - | - | - | - | - | - | - | - | - |

In the three sentences of the debug set in which `second` got fewer trades
whole than `first`, its raw reply held: for d04, the price "6万35", where the
passage writes "六万三千五"; for d08, the time "今天早上", where the passage
writes "this morning"; for d11, the quantity "0.02 个比特币", where the passage
writes "0.02". None of the three is a piece of its passage, and the program
left each field empty, saying so in the issues. For d29, a passage not to
record, `second` gave no draft. In d19, the one sentence of the debug set in
which `third` got fewer trades whole than `first`, its raw reply held the
price "2,450", where the passage writes "两千四百五"; the program left it
empty, saying so in the issues.

### The versions on the voice set

The runs share the set, the model, the way of reading a passage and every parameter; only the prompt version differs: `first`, `second`, `third`.

| Version | Well-formed | Whole trades right | One trade | Several trades | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | 9 / 9 (100.0%) | 1 / 10 (10.0%) | 1 / 8 (12.5%) | 0 / 2 (0.0%) | 0 | 0 | 4 / 12 (33.3%) | 0 / 0 (-) |
| `second` | 9 / 9 (100.0%) | 6 / 10 (60.0%) | 6 / 8 (75.0%) | 0 / 2 (0.0%) | 0 | 0 | 0 / 12 (0.0%) | 0 / 0 (-) |
| `third` | 9 / 9 (100.0%) | 2 / 10 (20.0%) | 2 / 8 (25.0%) | 0 / 2 (0.0%) | 0 | 0 | 2 / 12 (16.7%) | 0 / 0 (-) |

| Version | Wrong values with no issue | A total put as the price | Half copies (any) | Half copies (not right) | A time in another language | Sentences with a reply cut off | Calls | Sentences | Seconds | Seconds per sentence | First sentence, seconds | Longest sentence, seconds | Results file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | 6 | 0 | 2 | 2 | 0 | 0 | 10 | 10 | 45.3 | 4.53 | 4.442 | 8.8 (u09) | `evals/results/run-20261018T174017Z-voice-first.jsonl` |
| `second` | 1 | 0 | 2 | 1 | 0 | 0 | 10 | 10 | 44.1 | 4.41 | 4.861 | 8.128 (u09) | `evals/results/run-20261018T174449Z-voice-second.jsonl` |
| `third` | 5 | 0 | 3 | 3 | 0 | 0 | 10 | 10 | 47.1 | 4.71 | 4.705 | 9.111 (u09) | `evals/results/run-20261019T075107Z-voice-third.jsonl` |

| Field | `first`, right / pairs | `second`, right / pairs | `third`, right / pairs |
| --- | --- | --- | --- |
| side | 8 / 10 (80.0%) | 10 / 10 (100.0%) | 10 / 10 (100.0%) |
| coin | 10 / 10 (100.0%) | 10 / 10 (100.0%) | 10 / 10 (100.0%) |
| quantity | 7 / 10 (70.0%) | 10 / 10 (100.0%) | 7 / 10 (70.0%) |
| price | 10 / 10 (100.0%) | 10 / 10 (100.0%) | 10 / 10 (100.0%) |
| total | 7 / 10 (70.0%) | 10 / 10 (100.0%) | 8 / 10 (80.0%) |
| price_currency | 7 / 10 (70.0%) | 10 / 10 (100.0%) | 8 / 10 (80.0%) |
| fee | 9 / 10 (90.0%) | 10 / 10 (100.0%) | 10 / 10 (100.0%) |
| fee_currency | 9 / 10 (90.0%) | 10 / 10 (100.0%) | 10 / 10 (100.0%) |
| time | 10 / 10 (100.0%) | 10 / 10 (100.0%) | 10 / 10 (100.0%) |
| platform | 10 / 10 (100.0%) | 10 / 10 (100.0%) | 10 / 10 (100.0%) |
| opinion | 5 / 10 (50.0%) | 6 / 10 (60.0%) | 4 / 10 (40.0%) |

Every sentence (10 of 10):

| Sentence | Group | Result, `first` | Result, `second` | Result, `third` | Drafts, `first` | Drafts, `second` | Drafts, `third` | Whole right, `first` | Whole right, `second` | Whole right, `third` | Fields not right, `first` | Fields not right, `second` | Fields not right, `third` | Checks of the drafts, `first` | Checks of the drafts, `second` | Checks of the drafts, `third` | Fewer whole right than `first` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| u01 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 0 | 1 | 0 | 1.quantity:LEFT_EMPTY_WITH_REASON, 1.opinion:WRONG_SILENT | - | 1.quantity:LEFT_EMPTY_WITH_REASON, 1.opinion:WRONG_SILENT | - | - | - | - |
| u02 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 0 | 1 | 0 | 1.quantity:MADE_UP, 1.total:LEFT_EMPTY_BY_MODEL, 1.price_currency:LEFT_EMPTY_BY_MODEL | - | 1.quantity:MADE_UP, 1.total:LEFT_EMPTY_BY_MODEL, 1.price_currency:LEFT_EMPTY_BY_MODEL | - | - | - | - |
| u03 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 0 | 0 | 0 | 1.opinion:WRONG_SILENT | 1.opinion:WRONG_SILENT | 1.opinion:WRONG_SILENT | - | - | - | - |
| u04 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 1 | 1 | 1 | - | - | - | - | - | - | - |
| u05 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 0 | 1 | 0 | 1.opinion:WRONG_SILENT | - | 1.opinion:WRONG_SILENT | - | - | - | - |
| u06 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 0 | 0 | 0 | 1.total:LEFT_EMPTY_BY_MODEL, 1.price_currency:LEFT_EMPTY_BY_MODEL, 1.fee:MADE_UP, 1.fee_currency:MADE_UP | 1.opinion:LEFT_EMPTY_WITH_REASON | 1.quantity:MADE_UP, 1.total:LEFT_EMPTY_BY_MODEL, 1.price_currency:LEFT_EMPTY_BY_MODEL | - | - | - | - |
| u07 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 0 | 1 | 0 | 1.side:LEFT_EMPTY_BY_MODEL | - | 1.opinion:WRONG_SILENT | - | - | - | - |
| u08 | not_to_record | extracted | extracted | extracted | 1 | 0 | 1 | - | - | - | - | - | - | stopped | - | stopped | - |
| u09 | scored | extracted | extracted | extracted | 2 | 2 | 2 | 0 | 0 | 0 | 1.opinion:WRONG_SILENT, 2.opinion:LEFT_EMPTY_BY_MODEL | 1.opinion:LEFT_EMPTY_BY_MODEL, 2.opinion:LEFT_EMPTY_BY_MODEL | 1.opinion:WRONG_SILENT, 2.opinion:LEFT_EMPTY_BY_MODEL | - | - | - | - |
| u10 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 0 | 1 | 1 | 1.side:LEFT_EMPTY_BY_MODEL, 1.quantity:MADE_UP, 1.total:LEFT_EMPTY_BY_MODEL, 1.price_currency:LEFT_EMPTY_BY_MODEL | - | - | - | - | - | - |

In the three scored sentences of the voice set that `second` did not get
whole (four trades): u03's opinion leaves out its first clause, as with
`first`; for u06 the reply joins two parts of the passage into one opinion,
which is not a piece of the passage, and the program left it empty; for u09
both opinions are empty. For u08, the passage not to record, `second` gave
no draft, where `first` gave one. With `third`, u04 and u10 are whole; u02
and u06 have their amount in U as the quantity ("20U", "30U"), with an issue
about it; u07 has the side buy, and as its opinion only the second clause of
the passage's first sentence, with no issue about it.

### The versions on the writings set

The runs share the set, the model, the way of reading a passage and every parameter; only the prompt version differs: `first`, `second`, `third`.

| Version | Well-formed | Whole trades right | One trade | Several trades | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | 20 / 20 (100.0%) | 15 / 22 (68.2%) | 13 / 18 (72.2%) | 2 / 4 (50.0%) | 0 | 0 | 0 / 93 (0.0%) | 0 / 0 (-) |
| `second` | 20 / 20 (100.0%) | 13 / 22 (59.1%) | 11 / 18 (61.1%) | 2 / 4 (50.0%) | 0 | 0 | 0 / 93 (0.0%) | 0 / 0 (-) |
| `third` | 20 / 20 (100.0%) | 15 / 22 (68.2%) | 13 / 18 (72.2%) | 2 / 4 (50.0%) | 0 | 0 | 0 / 93 (0.0%) | 0 / 0 (-) |

| Version | Wrong values with no issue | A total put as the price | Half copies (any) | Half copies (not right) | A time in another language | Sentences with a reply cut off | Calls | Sentences | Seconds | Seconds per sentence | First sentence, seconds | Longest sentence, seconds | Results file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | 0 | 0 | 1 | 0 | 7 | 0 | 20 | 20 | 67.1 | 3.36 | 3.131 | 5.564 (w20) | `evals/results/run-20261018T174114Z-writings-first.jsonl` |
| `second` | 0 | 0 | 2 | 0 | 9 | 0 | 20 | 20 | 70.7 | 3.54 | 3.156 | 6.079 (w20) | `evals/results/run-20261018T174542Z-writings-second.jsonl` |
| `third` | 0 | 0 | 1 | 0 | 7 | 0 | 20 | 20 | 69.0 | 3.45 | 3.221 | 5.961 (w20) | `evals/results/run-20261019T075208Z-writings-third.jsonl` |

| Field | `first`, right / pairs | `second`, right / pairs | `third`, right / pairs |
| --- | --- | --- | --- |
| side | 22 / 22 (100.0%) | 22 / 22 (100.0%) | 22 / 22 (100.0%) |
| coin | 22 / 22 (100.0%) | 22 / 22 (100.0%) | 22 / 22 (100.0%) |
| quantity | 22 / 22 (100.0%) | 22 / 22 (100.0%) | 22 / 22 (100.0%) |
| price | 22 / 22 (100.0%) | 22 / 22 (100.0%) | 22 / 22 (100.0%) |
| total | 22 / 22 (100.0%) | 22 / 22 (100.0%) | 22 / 22 (100.0%) |
| price_currency | 22 / 22 (100.0%) | 22 / 22 (100.0%) | 22 / 22 (100.0%) |
| fee | 22 / 22 (100.0%) | 22 / 22 (100.0%) | 22 / 22 (100.0%) |
| fee_currency | 22 / 22 (100.0%) | 22 / 22 (100.0%) | 22 / 22 (100.0%) |
| time | 15 / 22 (68.2%) | 13 / 22 (59.1%) | 15 / 22 (68.2%) |
| platform | 22 / 22 (100.0%) | 22 / 22 (100.0%) | 22 / 22 (100.0%) |
| opinion | 22 / 22 (100.0%) | 22 / 22 (100.0%) | 22 / 22 (100.0%) |

The sentences where the versions differ in result, drafts, whole trades right or the fields not right, and every sentence not to record (2 of 20):

| Sentence | Group | Result, `first` | Result, `second` | Result, `third` | Drafts, `first` | Drafts, `second` | Drafts, `third` | Whole right, `first` | Whole right, `second` | Whole right, `third` | Fields not right, `first` | Fields not right, `second` | Fields not right, `third` | Checks of the drafts, `first` | Checks of the drafts, `second` | Checks of the drafts, `third` | Fewer whole right than `first` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| w11 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 1 | 0 | 1 | - | 1.time:LEFT_EMPTY_WITH_REASON | - | - | - | - | `second` |
| w15 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 1 | 0 | 1 | - | 1.time:LEFT_EMPTY_WITH_REASON | - | - | - | - | `second` |

In w11 and w15, the two sentences of the writings set in which `second` got
fewer trades whole than `first`, its raw reply held the time in Chinese,
"今天下午" and "今天早上", where the passages write "this afternoon" and "this
morning"; the program left the time empty, saying so in the issues.

### `first` in this experiment against its earlier runs

`first` ran each of the three sets before, with the same model, fingerprint,
Ollama version and parameters, at other commits: the debug and the voice set
in the comparison of two models, the writings set in the first prompt
experiment. Its three runs here are compared with those, sentence by
sentence (`evals/same_replies.py`, the earlier run first). This is reported,
not judged.

The debug set, against `evals/results/run-20261013T092724Z-debug-first.jsonl`:

| Sentences in both runs | Same raw replies | Other raw replies | Same raw replies, other drafts or issues |
| --- | --- | --- | --- |
| 30 | 30 | 0 | 0 |

| Sentence | Same raw replies | Same drafts and issues | Whole trades right, earlier | Whole trades right, later |
| --- | --- | --- | --- | --- |

The voice set, against `evals/results/run-20261013T092941Z-voice-first.jsonl`:

| Sentences in both runs | Same raw replies | Other raw replies | Same raw replies, other drafts or issues |
| --- | --- | --- | --- |
| 10 | 10 | 0 | 0 |

| Sentence | Same raw replies | Same drafts and issues | Whole trades right, earlier | Whole trades right, later |
| --- | --- | --- | --- | --- |

The writings set, against `evals/results/run-20261009T024502Z-writings-first.jsonl`:

| Sentences in both runs | Same raw replies | Other raw replies | Same raw replies, other drafts or issues |
| --- | --- | --- | --- |
| 20 | 20 | 0 | 0 |

| Sentence | Same raw replies | Same drafts and issues | Whole trades right, earlier | Whole trades right, later |
| --- | --- | --- | --- | --- |

### The rule applied to `second`

`evals/compare_sets.py --choose`, given the six runs above, prints:

The rule, fixed before the first run it judges:

A candidate is picked when, and only when, all five of these hold, each
against the run of `first` made in the same experiment:

1. on the voice set, more whole trades right than `first`;
2. on the debug set, no fewer whole trades right than `first`;
3. on the debug set, no more wrong values with no issue about them than
   `first` (the list "Wrong values in drafts with no issue about them" of
   the summary, the made-up values with no issue included);
4. on the debug set, no more trades missed and extra, added up over all
   scored sentences, than `first`;
5. on the voice set, no more wrong values with no issue about them than
   `first`.

The writings set is shown beside the debug and the voice set, with the same
counts, and judged by none of the five. The seconds are shown only. A later
candidate is held to the same rule against `first`, never against an
earlier candidate.

`second` against `first`:

| Condition | Set | `first` | `second` | Holds |
| --- | --- | --- | --- | --- |
| 1. more whole trades right | voice | 1 | 6 | yes |
| 2. no fewer whole trades right | debug | 31 | 29 | no |
| 3. no more wrong values with no issue | debug | 2 | 2 | yes |
| 4. no more trades missed and extra | debug | 0 | 0 | yes |
| 5. no more wrong values with no issue | voice | 6 | 1 | yes |

The same counts on the writings set, judged by none of the conditions:

| Count | `first` | `second` |
| --- | --- | --- |
| Whole trades right | 15 | 13 |
| Wrong values with no issue | 0 | 0 |
| Trades missed and extra | 0 | 0 |

Not picked: `second`; condition 2 does not hold.

### The rule applied to `third`

`evals/compare_sets.py --choose`, given the three runs of `first` above and
the three of `third`, prints:

The rule, fixed before the first run it judges:

A candidate is picked when, and only when, all five of these hold, each
against the run of `first` made in the same experiment:

1. on the voice set, more whole trades right than `first`;
2. on the debug set, no fewer whole trades right than `first`;
3. on the debug set, no more wrong values with no issue about them than
   `first` (the list "Wrong values in drafts with no issue about them" of
   the summary, the made-up values with no issue included);
4. on the debug set, no more trades missed and extra, added up over all
   scored sentences, than `first`;
5. on the voice set, no more wrong values with no issue about them than
   `first`.

The writings set is shown beside the debug and the voice set, with the same
counts, and judged by none of the five. The seconds are shown only. A later
candidate is held to the same rule against `first`, never against an
earlier candidate.

`third` against `first`:

| Condition | Set | `first` | `third` | Holds |
| --- | --- | --- | --- | --- |
| 1. more whole trades right | voice | 1 | 2 | yes |
| 2. no fewer whole trades right | debug | 31 | 30 | no |
| 3. no more wrong values with no issue | debug | 2 | 1 | yes |
| 4. no more trades missed and extra | debug | 0 | 0 | yes |
| 5. no more wrong values with no issue | voice | 6 | 5 | yes |

The same counts on the writings set, judged by none of the conditions:

| Count | `first` | `third` |
| --- | --- | --- |
| Whole trades right | 15 | 15 |
| Wrong values with no issue | 0 | 0 |
| Trades missed and extra | 0 | 0 |

Not picked: `third`; condition 2 does not hold.

### The final set

Not run: the rule picked no candidate. For `second`, condition 2 does not
hold (debug set, 29 whole trades right against 31 for `first`); for `third`,
condition 2 does not hold (debug set, 30 against 31). So no final-set line
applies, and the product's version is unchanged.

### The numbers in short

- Debug set: `first` 31 of 34 trades whole, `second` 29 and `third` 30.
  Wrong values with no issue 2, 2 and 1; trades missed and extra 0, 0 and 0.
  `second` got fewer trades whole than `first` in d04, d08 and d11, and more
  in d23; `third` fewer in d19.
- Voice set: `first` 1 of 10 trades whole, `second` 6 and `third` 2. Wrong
  values with no issue 6, 1 and 5.
- Writings set: `first` 15 of 22 trades whole, `second` 13 and `third` 15.
  Wrong values with no issue 0, 0 and 0. `second` got fewer trades whole in
  w11 and w15.
- Seconds per sentence, `first`, `second` and `third`: debug set 3.95, 4.08
  and 4.22; voice set 4.53, 4.41 and 4.71; writings set 3.36, 3.54 and 3.45.
  The model read 1,745 tokens for d07 with `first`, 3,199 with `second` and
  1,890 with `third`.
- `first` gave the same raw replies as in its earlier runs on all three sets:
  30 of 30, 10 of 10 and 20 of 20 sentences.
- The rule: neither `second` nor `third` is picked; for each, condition 2
  does not hold. The final set was not run, and the product still records
  passages with `first`.
- The new examples were written after the errors of `first` on the voice
  set, so the voice set's scores of a candidate are not scores on passages
  it has not seen; `third` was written after `second`'s errors on the debug
  and the writings set, so its scores there are not either. `first` gets
  every trade of the final set whole, so the final set can show only whether
  a candidate falls behind.

### The runs of prompt experiment three

Each run has its own subsection with the tables its results file gives and
its three more counts (`evals/extra_counts.py`).

### Run: debug set, prompt `first`, prompt experiment three

Results file: `evals/results/run-20261018T173752Z-debug-first.jsonl`, with its summary in `run-20261018T173752Z-debug-first.summary.json`.

<details>
<summary>The generated tables of this run</summary>

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
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| method | one_list |
| commit | 48250bf195be9924cb88892fa97cf380d526df66 |
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
| started_at | 2026-10-18T17:37:52+00:00 |
| sentences | 30 |
| sum_of_sentence_seconds | 118.62 |
| first_sentence_seconds | 8.841 |
| longest_sentence_seconds | 8.841 |
| finished_at | 2026-10-18T17:39:50+00:00 |
| seconds_of_the_last_session | 118.672 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 26 | 26 / 26 (100.0%) | 31 / 34 (91.2%) | 0 | 0 | 2 / 140 (1.4%) | 3 / 3 (100.0%) |
| one trade | 15 | 15 / 15 (100.0%) | 13 / 15 (86.7%) | 0 | 0 | 1 / 60 (1.7%) | 0 / 0 (-) |
| several trades | 8 | 8 / 8 (100.0%) | 18 / 19 (94.7%) | 0 | 0 | 1 / 80 (1.2%) | 0 / 0 (-) |
| - two trades | 5 | 5 / 5 (100.0%) | 10 / 10 (100.0%) | 0 | 0 | 0 / 42 (0.0%) | 0 / 0 (-) |
| - three or more trades | 3 | 3 / 3 (100.0%) | 8 / 9 (88.9%) | 0 | 0 | 1 / 38 (2.6%) | 0 / 0 (-) |
| no trade (talk) | 3 | 3 / 3 (100.0%) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 3 / 3 (100.0%) |
| Chinese | 10 | 10 / 10 (100.0%) | 13 / 13 (100.0%) | 0 | 0 | 0 / 52 (0.0%) | 1 / 1 (100.0%) |
| English | 9 | 9 / 9 (100.0%) | 10 / 12 (83.3%) | 0 | 0 | 1 / 49 (2.0%) | 1 / 1 (100.0%) |
| mixed | 7 | 7 / 7 (100.0%) | 8 / 9 (88.9%) | 0 | 0 | 1 / 39 (2.6%) | 1 / 1 (100.0%) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 34 / 34 (100.0%) |
| coin | 34 / 34 (100.0%) |
| quantity | 33 / 34 (97.1%) |
| price | 32 / 34 (94.1%) |
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
| RIGHT: right | 368 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 3 |
| - because the model's phrase is not a piece of the passage | 3 |
| - because the model's phrase cuts a number of the passage | 0 |
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

#### Fields the program left empty (3; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| d05 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| d13 | 1 | time | 昨天 18:20 | yesterday at 18:20 | NOT_IN_PASSAGE | no |
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
| d23 | mixed | extracted | 3 | 3 | 2 | 0 | 0 | 3.quantity:LEFT_EMPTY_WITH_REASON, 3.price:MADE_UP, 3.total:LEFT_EMPTY_BY_MODEL |
| d24 | zh | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d25 | en | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d26 | mixed | extracted | 0 | 0 | 0 | 0 | 0 | - |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 2 |
| Half copies, any field whose phrase is part of the gold phrase | 0 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 2 |

#### A total put as the price (2; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| d05: Bought 120 ADA for 64.80 USDT total yesterday, fee 0.002 BNB | 1 | price | 64.80 USDT | 64.80 | 64.80 USDT | 64.80 |
| d23: 刚才连着 sell 了三笔：0.1 BTC @ 63,000，1.5 ETH @ 2,410，还有 TON 卖了 200 个，total 1,040 USDT | 3 | price | 1,040 USDT | 1040 | 1,040 USDT | 1040 |

#### Half copies, counted the second way (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |

#### A time written in another language (2)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| d05: Bought 120 ADA for 64.80 USDT total yesterday, fee 0.002 BNB | 1 | time | 昨天 | (empty) | yesterday | 2026-10-04 (day) |
| d13: Picked up 40 LINK at 13.85 yesterday at 18:20 while BTC sat near 61k, fee 0 | 1 | time | 昨天 18:20 | (empty) | yesterday at 18:20 | 2026-10-04T18:20:00+02:00 (minute) |

</details>

### Run: voice set, prompt `first`, prompt experiment three

Results file: `evals/results/run-20261018T174017Z-voice-first.jsonl`, with its summary in `run-20261018T174017Z-voice-first.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | voice |
| final_exam_switch | False |
| set_file | evals/sets/voice.json |
| set_sha256 | 884e678672d4fcedc2d36da18e96e7e70261785936b4fc48cd2a3259d2b35196 |
| prompt | first |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | 7a510f4aaf16f7830ea5df2ec2071a276006565014e61bf295aa44a57a297112 |
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| method | one_list |
| commit | 345942615f2eea426d52bb771c19ea5842a72f6a |
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
| started_at | 2026-10-18T17:40:17+00:00 |
| sentences | 10 |
| sum_of_sentence_seconds | 45.258 |
| first_sentence_seconds | 4.442 |
| longest_sentence_seconds | 8.8 |
| finished_at | 2026-10-18T17:41:02+00:00 |
| seconds_of_the_last_session | 45.273 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 9 | 9 / 9 (100.0%) | 1 / 10 (10.0%) | 0 | 0 | 4 / 12 (33.3%) | 0 / 0 (-) |
| one trade | 8 | 8 / 8 (100.0%) | 1 / 8 (12.5%) | 0 | 0 | 4 / 12 (33.3%) | 0 / 0 (-) |
| several trades | 1 | 1 / 1 (100.0%) | 0 / 2 (0.0%) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| - two trades | 1 | 1 / 1 (100.0%) | 0 / 2 (0.0%) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| - three or more trades | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| no trade (talk) | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| Chinese | 9 | 9 / 9 (100.0%) | 1 / 10 (10.0%) | 0 | 0 | 4 / 12 (33.3%) | 0 / 0 (-) |
| English | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| mixed | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 8 / 10 (80.0%) |
| coin | 10 / 10 (100.0%) |
| quantity | 7 / 10 (70.0%) |
| price | 10 / 10 (100.0%) |
| total | 7 / 10 (70.0%) |
| price_currency | 7 / 10 (70.0%) |
| fee | 9 / 10 (90.0%) |
| fee_currency | 9 / 10 (90.0%) |
| time | 10 / 10 (100.0%) |
| platform | 10 / 10 (100.0%) |
| opinion | 5 / 10 (50.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 92 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 1 |
| - because the model's phrase is not a piece of the passage | 1 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 9 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 4 |
| MADE_UP: a value in the draft where the gold answer is empty | 4 |
| - of them with an issue about the field | 2 |

#### Wrong values in drafts with no issue about them (6)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |
| u01: 今晚23:41在OKX买入ADA，花了30USDT，成交96.6494个，均价0.3104，手续费0.0966494ADA。ADA是我目前亏损最多的币种-45%，现在低位购买目的是拉低ADA平均持仓成本 | 1 | opinion | 低位购买目的是拉低ADA平均持仓成本 | 低位购买目的是拉低ADA平均持仓成本 | ADA是我目前亏损最多的币种-45%，现在低位购买目的是拉低ADA平均持仓成本 | WRONG_SILENT |
| u03: 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的。10:18在OKX买的，50USDT，均价0.3218，手续费0.1553ADA | 1 | opinion | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | WRONG_SILENT |
| u05: BTC 60000有支撑，买点，毕竟在牛市初期，无论是60,000还是62,000或是等到突破66,000之后回调的60,000都是一样的。今早8点05分OKX买入0.00040811BTC，花了25USDT，均价61,258.60，手续费0.0000004BTC | 1 | opinion | BTC 60000有支撑，买点，毕竟在牛市初期，无论是60,000还是62,000或是等到突破66,000之后回调的60,000都是一样的。 | BTC 60000有支撑，买点，毕竟在牛市初期，无论是60,000还是62,000或是等到突破66,000之后回调的60,000都是一样的。 | BTC 60000有支撑，买点，毕竟在牛市初期，无论是60,000还是62,000或是等到突破66,000之后回调的60,000都是一样的 | WRONG_SILENT |
| u06: BTC又回到6万附近了，OKX补了30U，成交价60,412，牛市初期不怕 | 1 | fee | 30U | 30 | (empty) | MADE_UP |
| u06: BTC又回到6万附近了，OKX补了30U，成交价60,412，牛市初期不怕 | 1 | fee_currency | (empty) | U | (empty) | MADE_UP |
| u09: BTC跌破60000了，今天下午3点50在OKX补仓BTC，100USDT买到0.00167785BTC，均价59,600，手续费0.00000168BTC；好久没买ETH了，顺手20USDT买了0.008291ETH，均价2,412.25，手续费0.00000829ETH | 1 | opinion | 均价59,600，手续费0.00000168BTC | 均价59,600，手续费0.00000168BTC | BTC跌破60000了 | WRONG_SILENT |

#### Half copies: the model copied part of the gold phrase (2)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |
| u01 | 1 | opinion | 低位购买目的是拉低ADA平均持仓成本 | 低位购买目的是拉低ADA平均持仓成本 | ADA是我目前亏损最多的币种-45%，现在低位购买目的是拉低ADA平均持仓成本 | WRONG_SILENT |
| u03 | 1 | opinion | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | WRONG_SILENT |

#### Fields the program left empty (1; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| u01 | 1 | quantity | 96.6494 个 | 96.6494个 | NOT_IN_PASSAGE | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |
| u08: 在OKX挂了个BTC限价单，59,500买100U，觉得这里是强支撑，等它触发 | open_order | extracted | 1 | draft 1: stopped by SIDE, ONE_MORE_OF_QUANTITY_PRICE_TOTAL, FEE, OCCURRED |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| u01 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.quantity:LEFT_EMPTY_WITH_REASON, 1.opinion:WRONG_SILENT |
| u02 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.quantity:MADE_UP, 1.total:LEFT_EMPTY_BY_MODEL, 1.price_currency:LEFT_EMPTY_BY_MODEL |
| u03 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.opinion:WRONG_SILENT |
| u04 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| u05 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.opinion:WRONG_SILENT |
| u06 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.total:LEFT_EMPTY_BY_MODEL, 1.price_currency:LEFT_EMPTY_BY_MODEL, 1.fee:MADE_UP, 1.fee_currency:MADE_UP |
| u07 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.side:LEFT_EMPTY_BY_MODEL |
| u09 | zh | extracted | 2 | 2 | 0 | 0 | 0 | 1.opinion:WRONG_SILENT, 2.opinion:LEFT_EMPTY_BY_MODEL |
| u10 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.side:LEFT_EMPTY_BY_MODEL, 1.quantity:MADE_UP, 1.total:LEFT_EMPTY_BY_MODEL, 1.price_currency:LEFT_EMPTY_BY_MODEL |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 2 |
| Half copies, only fields not right (as in the summary) | 2 |
| A time written in another language | 0 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (2)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| u01: 今晚23:41在OKX买入ADA，花了30USDT，成交96.6494个，均价0.3104，手续费0.0966494ADA。ADA是我目前亏损最多的币种-45%，现在低位购买目的是拉低ADA平均持仓成本 | 1 | opinion | 低位购买目的是拉低ADA平均持仓成本 | 低位购买目的是拉低ADA平均持仓成本 | ADA是我目前亏损最多的币种-45%，现在低位购买目的是拉低ADA平均持仓成本 | ADA是我目前亏损最多的币种-45%，现在低位购买目的是拉低ADA平均持仓成本 | no |
| u03: 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的。10:18在OKX买的，50USDT，均价0.3218，手续费0.1553ADA | 1 | opinion | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | no |

#### A time written in another language (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

</details>

### Run: writings set, prompt `first`, prompt experiment three

Results file: `evals/results/run-20261018T174114Z-writings-first.jsonl`, with its summary in `run-20261018T174114Z-writings-first.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | writings |
| final_exam_switch | False |
| set_file | evals/sets/writings.json |
| set_sha256 | 7ac6a2027ec4434f140db02e51a3a46ca27da7dc89da06b3088866351f38ffce |
| prompt | first |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | 7a510f4aaf16f7830ea5df2ec2071a276006565014e61bf295aa44a57a297112 |
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| method | one_list |
| commit | fd326a073c36c9735b12125d1689743c4b818033 |
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
| started_at | 2026-10-18T17:41:14+00:00 |
| sentences | 20 |
| sum_of_sentence_seconds | 67.134 |
| first_sentence_seconds | 3.131 |
| longest_sentence_seconds | 5.564 |
| finished_at | 2026-10-18T17:42:21+00:00 |
| seconds_of_the_last_session | 67.168 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 20 | 20 / 20 (100.0%) | 15 / 22 (68.2%) | 0 | 0 | 0 / 93 (0.0%) | 0 / 0 (-) |
| one trade | 18 | 18 / 18 (100.0%) | 13 / 18 (72.2%) | 0 | 0 | 0 / 77 (0.0%) | 0 / 0 (-) |
| several trades | 2 | 2 / 2 (100.0%) | 2 / 4 (50.0%) | 0 | 0 | 0 / 16 (0.0%) | 0 / 0 (-) |
| - two trades | 2 | 2 / 2 (100.0%) | 2 / 4 (50.0%) | 0 | 0 | 0 / 16 (0.0%) | 0 / 0 (-) |
| - three or more trades | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| no trade (talk) | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| Chinese | 8 | 8 / 8 (100.0%) | 9 / 9 (100.0%) | 0 | 0 | 0 / 38 (0.0%) | 0 / 0 (-) |
| English | 10 | 10 / 10 (100.0%) | 4 / 11 (36.4%) | 0 | 0 | 0 / 46 (0.0%) | 0 / 0 (-) |
| mixed | 2 | 2 / 2 (100.0%) | 2 / 2 (100.0%) | 0 | 0 | 0 / 9 (0.0%) | 0 / 0 (-) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 22 / 22 (100.0%) |
| coin | 22 / 22 (100.0%) |
| quantity | 22 / 22 (100.0%) |
| price | 22 / 22 (100.0%) |
| total | 22 / 22 (100.0%) |
| price_currency | 22 / 22 (100.0%) |
| fee | 22 / 22 (100.0%) |
| fee_currency | 22 / 22 (100.0%) |
| time | 15 / 22 (68.2%) |
| platform | 22 / 22 (100.0%) |
| opinion | 22 / 22 (100.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 235 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 7 |
| - because the model's phrase is not a piece of the passage | 7 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 0 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 0 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (7; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| w04 | 1 | time | 昨天 15:20 | yesterday at 15:20 | NOT_IN_PASSAGE | no |
| w08 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| w12 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| w16 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| w19 | 1 | time | 今天 | today | NOT_IN_PASSAGE | no |
| w20 | 1 | time | 今天 | today | NOT_IN_PASSAGE | no |
| w20 | 2 | time | 今天 | today | NOT_IN_PASSAGE | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| w01 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w02 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w03 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w04 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w05 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w06 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w07 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w08 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w09 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w10 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w11 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w12 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w13 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w14 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w15 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w16 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w17 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w18 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| w19 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w20 | en | extracted | 2 | 2 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON, 2.time:LEFT_EMPTY_WITH_REASON |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 1 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 7 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (1)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| w07: Picked up 50 万 PEPE at 0.0000098 on Monday, fee 0 | 1 | time | Monday | 2026-10-05 (day) | on Monday | 2026-10-05 (day) | yes |

#### A time written in another language (7)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| w04: Sold 0.2 BTC at 97.5 k yesterday at 15:20, fee 0 | 1 | time | 昨天 15:20 | (empty) | yesterday at 15:20 | 2026-10-07T15:20:00+02:00 (minute) |
| w08: Sold 80 SOL for 1.2 万 USDT in total yesterday, fee 6 USDT | 1 | time | 昨天 | (empty) | yesterday | 2026-10-07 (day) |
| w12: Sold 2 ETH for 6 900 in total on Bybit yesterday, fee 3 USDT | 1 | time | 昨天 | (empty) | yesterday | 2026-10-07 (day) |
| w16: Sold LINK 25 14.2 yesterday, fee 0.1 LINK | 1 | time | 昨天 | (empty) | yesterday | 2026-10-07 (day) |
| w19: Sold 0.5 ETH at 3，510 today, fee 0.6 USDT | 1 | time | 今天 | (empty) | today | 2026-10-08 (day) |
| w20: Bought 0.1 BTC at 95,400，2 SOL at 150, both on OKX today, fee 0 | 1 | time | 今天 | (empty) | today | 2026-10-08 (day) |
| w20: Bought 0.1 BTC at 95,400，2 SOL at 150, both on OKX today, fee 0 | 2 | time | 今天 | (empty) | today | 2026-10-08 (day) |

</details>

### Run: debug set, prompt `second`, prompt experiment three

Results file: `evals/results/run-20261018T174235Z-debug-second.jsonl`, with its summary in `run-20261018T174235Z-debug-second.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | debug |
| final_exam_switch | False |
| set_file | evals/sets/debug.json |
| set_sha256 | 4529d98323ad1df4d38f5a5b73cdf1082b6a1cd08a0604a454ecf7986104f4d8 |
| prompt | second |
| prompt file src/ledger_hand/extraction/prompts/second.py | sha256 6066b189cbf96fde8d7fb00a752ef125aa50afe061298858c291518d07ca0191 |
| prompt file src/ledger_hand/extraction/prompts/second_examples.py | sha256 c5080b438bd1412d7ad04b94edb50713a861be1343fb032589359a559dae6cd0 |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | 8b20aa9f69064c8bf6fb87d7db9b526d3befec4c769d3a9d2ed4611e3ed2cc68 |
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| method | one_list |
| commit | 1975b55f14b1bee5cd2589e78f2606b12ed25156 |
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
| started_at | 2026-10-18T17:42:35+00:00 |
| sentences | 30 |
| sum_of_sentence_seconds | 122.368 |
| first_sentence_seconds | 9.002 |
| longest_sentence_seconds | 9.327 |
| finished_at | 2026-10-18T17:44:38+00:00 |
| seconds_of_the_last_session | 122.42 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 26 | 26 / 26 (100.0%) | 29 / 34 (85.3%) | 0 | 0 | 2 / 140 (1.4%) | 3 / 3 (100.0%) |
| one trade | 15 | 15 / 15 (100.0%) | 10 / 15 (66.7%) | 0 | 0 | 2 / 60 (3.3%) | 0 / 0 (-) |
| several trades | 8 | 8 / 8 (100.0%) | 19 / 19 (100.0%) | 0 | 0 | 0 / 80 (0.0%) | 0 / 0 (-) |
| - two trades | 5 | 5 / 5 (100.0%) | 10 / 10 (100.0%) | 0 | 0 | 0 / 42 (0.0%) | 0 / 0 (-) |
| - three or more trades | 3 | 3 / 3 (100.0%) | 9 / 9 (100.0%) | 0 | 0 | 0 / 38 (0.0%) | 0 / 0 (-) |
| no trade (talk) | 3 | 3 / 3 (100.0%) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 3 / 3 (100.0%) |
| Chinese | 10 | 10 / 10 (100.0%) | 12 / 13 (92.3%) | 0 | 0 | 0 / 52 (0.0%) | 1 / 1 (100.0%) |
| English | 9 | 9 / 9 (100.0%) | 8 / 12 (66.7%) | 0 | 0 | 2 / 49 (4.1%) | 1 / 1 (100.0%) |
| mixed | 7 | 7 / 7 (100.0%) | 9 / 9 (100.0%) | 0 | 0 | 0 / 39 (0.0%) | 1 / 1 (100.0%) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 34 / 34 (100.0%) |
| coin | 34 / 34 (100.0%) |
| quantity | 32 / 34 (94.1%) |
| price | 33 / 34 (97.1%) |
| total | 33 / 34 (97.1%) |
| price_currency | 33 / 34 (97.1%) |
| fee | 34 / 34 (100.0%) |
| fee_currency | 34 / 34 (100.0%) |
| time | 31 / 34 (91.2%) |
| platform | 34 / 34 (100.0%) |
| opinion | 34 / 34 (100.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 366 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 5 |
| - because the model's phrase is not a piece of the passage | 5 |
| - because the model's phrase cuts a number of the passage | 0 |
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
| d13: Picked up 40 LINK at 13.85 yesterday at 18:20 while BTC sat near 61k, fee 0 | 1 | total | 40 LINK | 40 | (empty) | MADE_UP |
| d13: Picked up 40 LINK at 13.85 yesterday at 18:20 while BTC sat near 61k, fee 0 | 1 | price_currency | (empty) | LINK | (empty) | MADE_UP |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (5; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| d04 | 1 | price | 6万35 | 六万三千五 | NOT_IN_PASSAGE | no |
| d05 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| d08 | 1 | time | 今天早上 | this morning | NOT_IN_PASSAGE | no |
| d11 | 1 | quantity | 0.02 个比特币 | 0.02 | NOT_IN_PASSAGE | no |
| d13 | 1 | time | 昨天18:20 | yesterday at 18:20 | NOT_IN_PASSAGE | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |
| d27: 昨天开了 10 倍杠杆做多 BTC，开仓价 62,800，保证金 200U | futures_or_leverage | extracted | 1 | draft 1: stopped by SIDE, FEE |
| d28: Swapped 0.5 ETH for 0.019 BTC on Uniswap this morning | coin_for_coin | extracted | 2 | draft 1: stopped by SIDE, ONE_MORE_OF_QUANTITY_PRICE_TOTAL, FEE; draft 2: stopped by SIDE, ONE_MORE_OF_QUANTITY_PRICE_TOTAL, FEE |
| d29: 挂了一个 limit buy，0.05 BTC @ 58,000，还没成交 | open_order | extracted | 0 | - |
| d30: 打算明天下午 3 点买 1 个 ETH，价格到 2,300 就进 | plan | extracted | 0 | - |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| d01 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d02 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d03 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d04 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.price:LEFT_EMPTY_WITH_REASON |
| d05 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| d06 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d07 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d08 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| d09 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d10 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d11 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.quantity:LEFT_EMPTY_WITH_REASON |
| d12 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d13 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.quantity:LEFT_EMPTY_BY_MODEL, 1.total:MADE_UP, 1.price_currency:MADE_UP, 1.time:LEFT_EMPTY_WITH_REASON |
| d14 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d15 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d16 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d17 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d18 | mixed | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d19 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d20 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d21 | zh | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d22 | en | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d23 | mixed | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d24 | zh | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d25 | en | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d26 | mixed | extracted | 0 | 0 | 0 | 0 | 0 | - |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 2 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 3 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (2)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| d21: 今天在 Bitget 调仓：卖了 50 个 LINK，13.6 一个；买了 2 个 AVAX，26.1 一个；又买了 100 个 OP，1.73 一个。每笔手续费 0.1U | 2 | quantity | 2 个 | 2 | 2 个 AVAX | 2 | yes |
| d21: 今天在 Bitget 调仓：卖了 50 个 LINK，13.6 一个；买了 2 个 AVAX，26.1 一个；又买了 100 个 OP，1.73 一个。每笔手续费 0.1U | 3 | quantity | 100 个 | 100 | 100 个 OP | 100 | yes |

#### A time written in another language (3)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| d05: Bought 120 ADA for 64.80 USDT total yesterday, fee 0.002 BNB | 1 | time | 昨天 | (empty) | yesterday | 2026-10-04 (day) |
| d08: Sold 3 at 4,120 this morning, fee 0.9 USDT | 1 | time | 今天早上 | (empty) | this morning | 2026-10-05 (day) |
| d13: Picked up 40 LINK at 13.85 yesterday at 18:20 while BTC sat near 61k, fee 0 | 1 | time | 昨天18:20 | (empty) | yesterday at 18:20 | 2026-10-04T18:20:00+02:00 (minute) |

</details>

### Run: voice set, prompt `second`, prompt experiment three

Results file: `evals/results/run-20261018T174449Z-voice-second.jsonl`, with its summary in `run-20261018T174449Z-voice-second.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | voice |
| final_exam_switch | False |
| set_file | evals/sets/voice.json |
| set_sha256 | 884e678672d4fcedc2d36da18e96e7e70261785936b4fc48cd2a3259d2b35196 |
| prompt | second |
| prompt file src/ledger_hand/extraction/prompts/second.py | sha256 6066b189cbf96fde8d7fb00a752ef125aa50afe061298858c291518d07ca0191 |
| prompt file src/ledger_hand/extraction/prompts/second_examples.py | sha256 c5080b438bd1412d7ad04b94edb50713a861be1343fb032589359a559dae6cd0 |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | 8b20aa9f69064c8bf6fb87d7db9b526d3befec4c769d3a9d2ed4611e3ed2cc68 |
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| method | one_list |
| commit | 0bbd9e7879798c864587ebe05a1f9fed4802f8ef |
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
| started_at | 2026-10-18T17:44:49+00:00 |
| sentences | 10 |
| sum_of_sentence_seconds | 44.092 |
| first_sentence_seconds | 4.861 |
| longest_sentence_seconds | 8.128 |
| finished_at | 2026-10-18T17:45:33+00:00 |
| seconds_of_the_last_session | 44.112 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 9 | 9 / 9 (100.0%) | 6 / 10 (60.0%) | 0 | 0 | 0 / 12 (0.0%) | 0 / 0 (-) |
| one trade | 8 | 8 / 8 (100.0%) | 6 / 8 (75.0%) | 0 | 0 | 0 / 12 (0.0%) | 0 / 0 (-) |
| several trades | 1 | 1 / 1 (100.0%) | 0 / 2 (0.0%) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| - two trades | 1 | 1 / 1 (100.0%) | 0 / 2 (0.0%) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| - three or more trades | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| no trade (talk) | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| Chinese | 9 | 9 / 9 (100.0%) | 6 / 10 (60.0%) | 0 | 0 | 0 / 12 (0.0%) | 0 / 0 (-) |
| English | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| mixed | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 10 / 10 (100.0%) |
| coin | 10 / 10 (100.0%) |
| quantity | 10 / 10 (100.0%) |
| price | 10 / 10 (100.0%) |
| total | 10 / 10 (100.0%) |
| price_currency | 10 / 10 (100.0%) |
| fee | 10 / 10 (100.0%) |
| fee_currency | 10 / 10 (100.0%) |
| time | 10 / 10 (100.0%) |
| platform | 10 / 10 (100.0%) |
| opinion | 6 / 10 (60.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 106 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 1 |
| - because the model's phrase is not a piece of the passage | 1 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 2 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 1 |
| MADE_UP: a value in the draft where the gold answer is empty | 0 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (1)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |
| u03: 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的。10:18在OKX买的，50USDT，均价0.3218，手续费0.1553ADA | 1 | opinion | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | WRONG_SILENT |

#### Half copies: the model copied part of the gold phrase (1)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |
| u03 | 1 | opinion | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | WRONG_SILENT |

#### Fields the program left empty (1; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| u06 | 1 | opinion | BTC又回到6万附近了，OKX补了30U，牛市初期不怕 | 牛市初期不怕 | NOT_IN_PASSAGE | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |
| u08: 在OKX挂了个BTC限价单，59,500买100U，觉得这里是强支撑，等它触发 | open_order | extracted | 0 | - |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| u01 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| u02 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| u03 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.opinion:WRONG_SILENT |
| u04 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| u05 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| u06 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.opinion:LEFT_EMPTY_WITH_REASON |
| u07 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| u09 | zh | extracted | 2 | 2 | 0 | 0 | 0 | 1.opinion:LEFT_EMPTY_BY_MODEL, 2.opinion:LEFT_EMPTY_BY_MODEL |
| u10 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 2 |
| Half copies, only fields not right (as in the summary) | 1 |
| A time written in another language | 0 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (2)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| u03: 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的。10:18在OKX买的，50USDT，均价0.3218，手续费0.1553ADA | 1 | opinion | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | no |
| u04: 9月25号21:06在OKX买了318.4713个ADA，0.314一个，手续费0.3184713ADA，跟着博主看多 | 1 | quantity | 318.4713个 | 318.4713 | 318.4713个ADA | 318.4713 | yes |

#### A time written in another language (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

</details>

### Run: writings set, prompt `second`, prompt experiment three

Results file: `evals/results/run-20261018T174542Z-writings-second.jsonl`, with its summary in `run-20261018T174542Z-writings-second.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | writings |
| final_exam_switch | False |
| set_file | evals/sets/writings.json |
| set_sha256 | 7ac6a2027ec4434f140db02e51a3a46ca27da7dc89da06b3088866351f38ffce |
| prompt | second |
| prompt file src/ledger_hand/extraction/prompts/second.py | sha256 6066b189cbf96fde8d7fb00a752ef125aa50afe061298858c291518d07ca0191 |
| prompt file src/ledger_hand/extraction/prompts/second_examples.py | sha256 c5080b438bd1412d7ad04b94edb50713a861be1343fb032589359a559dae6cd0 |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | 8b20aa9f69064c8bf6fb87d7db9b526d3befec4c769d3a9d2ed4611e3ed2cc68 |
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| method | one_list |
| commit | b17e746e3eb8b7155158a246a86c7bb301f6ed4f |
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
| started_at | 2026-10-18T17:45:42+00:00 |
| sentences | 20 |
| sum_of_sentence_seconds | 70.717 |
| first_sentence_seconds | 3.156 |
| longest_sentence_seconds | 6.079 |
| finished_at | 2026-10-18T17:46:53+00:00 |
| seconds_of_the_last_session | 70.749 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 20 | 20 / 20 (100.0%) | 13 / 22 (59.1%) | 0 | 0 | 0 / 93 (0.0%) | 0 / 0 (-) |
| one trade | 18 | 18 / 18 (100.0%) | 11 / 18 (61.1%) | 0 | 0 | 0 / 77 (0.0%) | 0 / 0 (-) |
| several trades | 2 | 2 / 2 (100.0%) | 2 / 4 (50.0%) | 0 | 0 | 0 / 16 (0.0%) | 0 / 0 (-) |
| - two trades | 2 | 2 / 2 (100.0%) | 2 / 4 (50.0%) | 0 | 0 | 0 / 16 (0.0%) | 0 / 0 (-) |
| - three or more trades | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| no trade (talk) | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| Chinese | 8 | 8 / 8 (100.0%) | 9 / 9 (100.0%) | 0 | 0 | 0 / 38 (0.0%) | 0 / 0 (-) |
| English | 10 | 10 / 10 (100.0%) | 2 / 11 (18.2%) | 0 | 0 | 0 / 46 (0.0%) | 0 / 0 (-) |
| mixed | 2 | 2 / 2 (100.0%) | 2 / 2 (100.0%) | 0 | 0 | 0 / 9 (0.0%) | 0 / 0 (-) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 22 / 22 (100.0%) |
| coin | 22 / 22 (100.0%) |
| quantity | 22 / 22 (100.0%) |
| price | 22 / 22 (100.0%) |
| total | 22 / 22 (100.0%) |
| price_currency | 22 / 22 (100.0%) |
| fee | 22 / 22 (100.0%) |
| fee_currency | 22 / 22 (100.0%) |
| time | 13 / 22 (59.1%) |
| platform | 22 / 22 (100.0%) |
| opinion | 22 / 22 (100.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 233 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 9 |
| - because the model's phrase is not a piece of the passage | 9 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 0 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 0 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (9; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| w04 | 1 | time | 昨天15:20 | yesterday at 15:20 | NOT_IN_PASSAGE | no |
| w08 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| w11 | 1 | time | 今天下午 | this afternoon | NOT_IN_PASSAGE | no |
| w12 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| w15 | 1 | time | 今天早上 | this morning | NOT_IN_PASSAGE | no |
| w16 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| w19 | 1 | time | 今天 | today | NOT_IN_PASSAGE | no |
| w20 | 1 | time | 今天 | today | NOT_IN_PASSAGE | no |
| w20 | 2 | time | 今天 | today | NOT_IN_PASSAGE | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| w01 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w02 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w03 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w04 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w05 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w06 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w07 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w08 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w09 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w10 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w11 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w12 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w13 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w14 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w15 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w16 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w17 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w18 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| w19 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w20 | en | extracted | 2 | 2 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON, 2.time:LEFT_EMPTY_WITH_REASON |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 2 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 9 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (2)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| w01: 前天在币安买了 2 w 个 DOGE，0.16 一个，手续费 1U | 1 | quantity | 2 w 个 | (empty) | 2 w 个 DOGE | (empty) | yes |
| w07: Picked up 50 万 PEPE at 0.0000098 on Monday, fee 0 | 1 | time | Monday | 2026-10-05 (day) | on Monday | 2026-10-05 (day) | yes |

#### A time written in another language (9)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| w04: Sold 0.2 BTC at 97.5 k yesterday at 15:20, fee 0 | 1 | time | 昨天15:20 | (empty) | yesterday at 15:20 | 2026-10-07T15:20:00+02:00 (minute) |
| w08: Sold 80 SOL for 1.2 万 USDT in total yesterday, fee 6 USDT | 1 | time | 昨天 | (empty) | yesterday | 2026-10-07 (day) |
| w11: Bought 0.05 BTC at 96 300 this afternoon, fee 2 USDT | 1 | time | 今天下午 | (empty) | this afternoon | 2026-10-08 (day) |
| w12: Sold 2 ETH for 6 900 in total on Bybit yesterday, fee 3 USDT | 1 | time | 昨天 | (empty) | yesterday | 2026-10-07 (day) |
| w15: Bought SOL 12 148.5 this morning on Binance, fee 0.2 USDT | 1 | time | 今天早上 | (empty) | this morning | 2026-10-08 (day) |
| w16: Sold LINK 25 14.2 yesterday, fee 0.1 LINK | 1 | time | 昨天 | (empty) | yesterday | 2026-10-07 (day) |
| w19: Sold 0.5 ETH at 3，510 today, fee 0.6 USDT | 1 | time | 今天 | (empty) | today | 2026-10-08 (day) |
| w20: Bought 0.1 BTC at 95,400，2 SOL at 150, both on OKX today, fee 0 | 1 | time | 今天 | (empty) | today | 2026-10-08 (day) |
| w20: Bought 0.1 BTC at 95,400，2 SOL at 150, both on OKX today, fee 0 | 2 | time | 今天 | (empty) | today | 2026-10-08 (day) |

</details>

### Run: debug set, prompt `third`, prompt experiment three

Results file: `evals/results/run-20261019T074847Z-debug-third.jsonl`, with its summary in `run-20261019T074847Z-debug-third.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | debug |
| final_exam_switch | False |
| set_file | evals/sets/debug.json |
| set_sha256 | 4529d98323ad1df4d38f5a5b73cdf1082b6a1cd08a0604a454ecf7986104f4d8 |
| prompt | third |
| prompt file src/ledger_hand/extraction/prompts/third.py | sha256 4e0cf32eecfe15902a404a7dbfcfa815419c9e03efb6c2cb726c39f9eec2f7a5 |
| prompt file src/ledger_hand/extraction/prompts/second.py | sha256 6066b189cbf96fde8d7fb00a752ef125aa50afe061298858c291518d07ca0191 |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | facabbe239e4ab100df1bb517ff25160711508d206f30f15d6185ac5d0001a65 |
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| method | one_list |
| commit | 5aba53fec069981e5a09a310b0a0e253c077ad90 |
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
| started_at | 2026-10-19T07:48:47+00:00 |
| sentences | 30 |
| sum_of_sentence_seconds | 126.579 |
| first_sentence_seconds | 9.9 |
| longest_sentence_seconds | 9.9 |
| finished_at | 2026-10-19T07:50:54+00:00 |
| seconds_of_the_last_session | 126.624 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 26 | 26 / 26 (100.0%) | 30 / 34 (88.2%) | 0 | 0 | 1 / 140 (0.7%) | 3 / 3 (100.0%) |
| one trade | 15 | 15 / 15 (100.0%) | 13 / 15 (86.7%) | 0 | 0 | 0 / 60 (0.0%) | 0 / 0 (-) |
| several trades | 8 | 8 / 8 (100.0%) | 17 / 19 (89.5%) | 0 | 0 | 1 / 80 (1.2%) | 0 / 0 (-) |
| - two trades | 5 | 5 / 5 (100.0%) | 9 / 10 (90.0%) | 0 | 0 | 0 / 42 (0.0%) | 0 / 0 (-) |
| - three or more trades | 3 | 3 / 3 (100.0%) | 8 / 9 (88.9%) | 0 | 0 | 1 / 38 (2.6%) | 0 / 0 (-) |
| no trade (talk) | 3 | 3 / 3 (100.0%) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 3 / 3 (100.0%) |
| Chinese | 10 | 10 / 10 (100.0%) | 12 / 13 (92.3%) | 0 | 0 | 0 / 52 (0.0%) | 1 / 1 (100.0%) |
| English | 9 | 9 / 9 (100.0%) | 10 / 12 (83.3%) | 0 | 0 | 0 / 49 (0.0%) | 1 / 1 (100.0%) |
| mixed | 7 | 7 / 7 (100.0%) | 8 / 9 (88.9%) | 0 | 0 | 1 / 39 (2.6%) | 1 / 1 (100.0%) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 34 / 34 (100.0%) |
| coin | 34 / 34 (100.0%) |
| quantity | 33 / 34 (97.1%) |
| price | 32 / 34 (94.1%) |
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
| RIGHT: right | 368 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 4 |
| - because the model's phrase is not a piece of the passage | 4 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 1 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 1 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (1)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |
| d23: 刚才连着 sell 了三笔：0.1 BTC @ 63,000，1.5 ETH @ 2,410，还有 TON 卖了 200 个，total 1,040 USDT | 3 | price | 1,040 USDT | 1040 | (empty) | MADE_UP |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (4; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| d05 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| d13 | 1 | time | 昨天 18:20 | yesterday at 18:20 | NOT_IN_PASSAGE | no |
| d19 | 1 | price | 2,450 | 两千四百五 | NOT_IN_PASSAGE | no |
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
| d05 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
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
| d19 | zh | extracted | 2 | 2 | 1 | 0 | 0 | 1.price:LEFT_EMPTY_WITH_REASON |
| d20 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d21 | zh | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d22 | en | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d23 | mixed | extracted | 3 | 3 | 2 | 0 | 0 | 3.quantity:LEFT_EMPTY_WITH_REASON, 3.price:MADE_UP, 3.total:LEFT_EMPTY_BY_MODEL |
| d24 | zh | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d25 | en | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d26 | mixed | extracted | 0 | 0 | 0 | 0 | 0 | - |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 1 |
| Half copies, any field whose phrase is part of the gold phrase | 0 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 2 |

#### A total put as the price (1; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| d23: 刚才连着 sell 了三笔：0.1 BTC @ 63,000，1.5 ETH @ 2,410，还有 TON 卖了 200 个，total 1,040 USDT | 3 | price | 1,040 USDT | 1040 | 1,040 USDT | 1040 |

#### Half copies, counted the second way (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |

#### A time written in another language (2)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| d05: Bought 120 ADA for 64.80 USDT total yesterday, fee 0.002 BNB | 1 | time | 昨天 | (empty) | yesterday | 2026-10-04 (day) |
| d13: Picked up 40 LINK at 13.85 yesterday at 18:20 while BTC sat near 61k, fee 0 | 1 | time | 昨天 18:20 | (empty) | yesterday at 18:20 | 2026-10-04T18:20:00+02:00 (minute) |

</details>

### Run: voice set, prompt `third`, prompt experiment three

Results file: `evals/results/run-20261019T075107Z-voice-third.jsonl`, with its summary in `run-20261019T075107Z-voice-third.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | voice |
| final_exam_switch | False |
| set_file | evals/sets/voice.json |
| set_sha256 | 884e678672d4fcedc2d36da18e96e7e70261785936b4fc48cd2a3259d2b35196 |
| prompt | third |
| prompt file src/ledger_hand/extraction/prompts/third.py | sha256 4e0cf32eecfe15902a404a7dbfcfa815419c9e03efb6c2cb726c39f9eec2f7a5 |
| prompt file src/ledger_hand/extraction/prompts/second.py | sha256 6066b189cbf96fde8d7fb00a752ef125aa50afe061298858c291518d07ca0191 |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | facabbe239e4ab100df1bb517ff25160711508d206f30f15d6185ac5d0001a65 |
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| method | one_list |
| commit | 8a62e97a10207bc907739ad3063a097af733e554 |
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
| started_at | 2026-10-19T07:51:07+00:00 |
| sentences | 10 |
| sum_of_sentence_seconds | 47.145 |
| first_sentence_seconds | 4.705 |
| longest_sentence_seconds | 9.111 |
| finished_at | 2026-10-19T07:51:54+00:00 |
| seconds_of_the_last_session | 47.159 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 9 | 9 / 9 (100.0%) | 2 / 10 (20.0%) | 0 | 0 | 2 / 12 (16.7%) | 0 / 0 (-) |
| one trade | 8 | 8 / 8 (100.0%) | 2 / 8 (25.0%) | 0 | 0 | 2 / 12 (16.7%) | 0 / 0 (-) |
| several trades | 1 | 1 / 1 (100.0%) | 0 / 2 (0.0%) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| - two trades | 1 | 1 / 1 (100.0%) | 0 / 2 (0.0%) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| - three or more trades | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| no trade (talk) | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| Chinese | 9 | 9 / 9 (100.0%) | 2 / 10 (20.0%) | 0 | 0 | 2 / 12 (16.7%) | 0 / 0 (-) |
| English | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| mixed | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 10 / 10 (100.0%) |
| coin | 10 / 10 (100.0%) |
| quantity | 7 / 10 (70.0%) |
| price | 10 / 10 (100.0%) |
| total | 8 / 10 (80.0%) |
| price_currency | 8 / 10 (80.0%) |
| fee | 10 / 10 (100.0%) |
| fee_currency | 10 / 10 (100.0%) |
| time | 10 / 10 (100.0%) |
| platform | 10 / 10 (100.0%) |
| opinion | 4 / 10 (40.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 97 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 1 |
| - because the model's phrase is not a piece of the passage | 1 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 5 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 5 |
| MADE_UP: a value in the draft where the gold answer is empty | 2 |
| - of them with an issue about the field | 2 |

#### Wrong values in drafts with no issue about them (5)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |
| u01: 今晚23:41在OKX买入ADA，花了30USDT，成交96.6494个，均价0.3104，手续费0.0966494ADA。ADA是我目前亏损最多的币种-45%，现在低位购买目的是拉低ADA平均持仓成本 | 1 | opinion | 低位购买目的是拉低ADA平均持仓成本 | 低位购买目的是拉低ADA平均持仓成本 | ADA是我目前亏损最多的币种-45%，现在低位购买目的是拉低ADA平均持仓成本 | WRONG_SILENT |
| u03: 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的。10:18在OKX买的，50USDT，均价0.3218，手续费0.1553ADA | 1 | opinion | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | WRONG_SILENT |
| u05: BTC 60000有支撑，买点，毕竟在牛市初期，无论是60,000还是62,000或是等到突破66,000之后回调的60,000都是一样的。今早8点05分OKX买入0.00040811BTC，花了25USDT，均价61,258.60，手续费0.0000004BTC | 1 | opinion | BTC 60000有支撑，买点，毕竟在牛市初期，无论是60,000还是62,000或是等到突破66,000之后回调的60,000都是一样的。 | BTC 60000有支撑，买点，毕竟在牛市初期，无论是60,000还是62,000或是等到突破66,000之后回调的60,000都是一样的。 | BTC 60000有支撑，买点，毕竟在牛市初期，无论是60,000还是62,000或是等到突破66,000之后回调的60,000都是一样的 | WRONG_SILENT |
| u07: 一个周之前设置的限单触发了，因为我觉得60000是个强支撑位。今天凌晨4点07分OKX成交，100USDT买到0.00165837BTC，均价60,300，手续费0.00000133BTC | 1 | opinion | 因为我觉得60000是个强支撑位 | 因为我觉得60000是个强支撑位 | 一个周之前设置的限单触发了，因为我觉得60000是个强支撑位 | WRONG_SILENT |
| u09: BTC跌破60000了，今天下午3点50在OKX补仓BTC，100USDT买到0.00167785BTC，均价59,600，手续费0.00000168BTC；好久没买ETH了，顺手20USDT买了0.008291ETH，均价2,412.25，手续费0.00000829ETH | 1 | opinion | 均价59,600，手续费0.00000168BTC | 均价59,600，手续费0.00000168BTC | BTC跌破60000了 | WRONG_SILENT |

#### Half copies: the model copied part of the gold phrase (3)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |
| u01 | 1 | opinion | 低位购买目的是拉低ADA平均持仓成本 | 低位购买目的是拉低ADA平均持仓成本 | ADA是我目前亏损最多的币种-45%，现在低位购买目的是拉低ADA平均持仓成本 | WRONG_SILENT |
| u03 | 1 | opinion | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | WRONG_SILENT |
| u07 | 1 | opinion | 因为我觉得60000是个强支撑位 | 因为我觉得60000是个强支撑位 | 一个周之前设置的限单触发了，因为我觉得60000是个强支撑位 | WRONG_SILENT |

#### Fields the program left empty (1; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| u01 | 1 | quantity | 96.6494 个 | 96.6494个 | NOT_IN_PASSAGE | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |
| u08: 在OKX挂了个BTC限价单，59,500买100U，觉得这里是强支撑，等它触发 | open_order | extracted | 1 | draft 1: stopped by SIDE, ONE_MORE_OF_QUANTITY_PRICE_TOTAL, FEE, OCCURRED |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| u01 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.quantity:LEFT_EMPTY_WITH_REASON, 1.opinion:WRONG_SILENT |
| u02 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.quantity:MADE_UP, 1.total:LEFT_EMPTY_BY_MODEL, 1.price_currency:LEFT_EMPTY_BY_MODEL |
| u03 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.opinion:WRONG_SILENT |
| u04 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| u05 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.opinion:WRONG_SILENT |
| u06 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.quantity:MADE_UP, 1.total:LEFT_EMPTY_BY_MODEL, 1.price_currency:LEFT_EMPTY_BY_MODEL |
| u07 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.opinion:WRONG_SILENT |
| u09 | zh | extracted | 2 | 2 | 0 | 0 | 0 | 1.opinion:WRONG_SILENT, 2.opinion:LEFT_EMPTY_BY_MODEL |
| u10 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 3 |
| Half copies, only fields not right (as in the summary) | 3 |
| A time written in another language | 0 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (3)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| u01: 今晚23:41在OKX买入ADA，花了30USDT，成交96.6494个，均价0.3104，手续费0.0966494ADA。ADA是我目前亏损最多的币种-45%，现在低位购买目的是拉低ADA平均持仓成本 | 1 | opinion | 低位购买目的是拉低ADA平均持仓成本 | 低位购买目的是拉低ADA平均持仓成本 | ADA是我目前亏损最多的币种-45%，现在低位购买目的是拉低ADA平均持仓成本 | ADA是我目前亏损最多的币种-45%，现在低位购买目的是拉低ADA平均持仓成本 | no |
| u03: 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的。10:18在OKX买的，50USDT，均价0.3218，手续费0.1553ADA | 1 | opinion | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | no |
| u07: 一个周之前设置的限单触发了，因为我觉得60000是个强支撑位。今天凌晨4点07分OKX成交，100USDT买到0.00165837BTC，均价60,300，手续费0.00000133BTC | 1 | opinion | 因为我觉得60000是个强支撑位 | 因为我觉得60000是个强支撑位 | 一个周之前设置的限单触发了，因为我觉得60000是个强支撑位 | 一个周之前设置的限单触发了，因为我觉得60000是个强支撑位 | no |

#### A time written in another language (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

</details>

### Run: writings set, prompt `third`, prompt experiment three

Results file: `evals/results/run-20261019T075208Z-writings-third.jsonl`, with its summary in `run-20261019T075208Z-writings-third.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | writings |
| final_exam_switch | False |
| set_file | evals/sets/writings.json |
| set_sha256 | 7ac6a2027ec4434f140db02e51a3a46ca27da7dc89da06b3088866351f38ffce |
| prompt | third |
| prompt file src/ledger_hand/extraction/prompts/third.py | sha256 4e0cf32eecfe15902a404a7dbfcfa815419c9e03efb6c2cb726c39f9eec2f7a5 |
| prompt file src/ledger_hand/extraction/prompts/second.py | sha256 6066b189cbf96fde8d7fb00a752ef125aa50afe061298858c291518d07ca0191 |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | facabbe239e4ab100df1bb517ff25160711508d206f30f15d6185ac5d0001a65 |
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| method | one_list |
| commit | f847fd082027a876cb01628158cf5fdf85cb8fd0 |
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
| started_at | 2026-10-19T07:52:08+00:00 |
| sentences | 20 |
| sum_of_sentence_seconds | 68.968 |
| first_sentence_seconds | 3.221 |
| longest_sentence_seconds | 5.961 |
| finished_at | 2026-10-19T07:53:17+00:00 |
| seconds_of_the_last_session | 68.996 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 20 | 20 / 20 (100.0%) | 15 / 22 (68.2%) | 0 | 0 | 0 / 93 (0.0%) | 0 / 0 (-) |
| one trade | 18 | 18 / 18 (100.0%) | 13 / 18 (72.2%) | 0 | 0 | 0 / 77 (0.0%) | 0 / 0 (-) |
| several trades | 2 | 2 / 2 (100.0%) | 2 / 4 (50.0%) | 0 | 0 | 0 / 16 (0.0%) | 0 / 0 (-) |
| - two trades | 2 | 2 / 2 (100.0%) | 2 / 4 (50.0%) | 0 | 0 | 0 / 16 (0.0%) | 0 / 0 (-) |
| - three or more trades | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| no trade (talk) | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| Chinese | 8 | 8 / 8 (100.0%) | 9 / 9 (100.0%) | 0 | 0 | 0 / 38 (0.0%) | 0 / 0 (-) |
| English | 10 | 10 / 10 (100.0%) | 4 / 11 (36.4%) | 0 | 0 | 0 / 46 (0.0%) | 0 / 0 (-) |
| mixed | 2 | 2 / 2 (100.0%) | 2 / 2 (100.0%) | 0 | 0 | 0 / 9 (0.0%) | 0 / 0 (-) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 22 / 22 (100.0%) |
| coin | 22 / 22 (100.0%) |
| quantity | 22 / 22 (100.0%) |
| price | 22 / 22 (100.0%) |
| total | 22 / 22 (100.0%) |
| price_currency | 22 / 22 (100.0%) |
| fee | 22 / 22 (100.0%) |
| fee_currency | 22 / 22 (100.0%) |
| time | 15 / 22 (68.2%) |
| platform | 22 / 22 (100.0%) |
| opinion | 22 / 22 (100.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 235 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 7 |
| - because the model's phrase is not a piece of the passage | 7 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 0 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 0 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (7; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| w04 | 1 | time | 昨天 15:20 | yesterday at 15:20 | NOT_IN_PASSAGE | no |
| w08 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| w12 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| w16 | 1 | time | 昨天 | yesterday | NOT_IN_PASSAGE | no |
| w19 | 1 | time | 今天 | today | NOT_IN_PASSAGE | no |
| w20 | 1 | time | 今天 | today | NOT_IN_PASSAGE | no |
| w20 | 2 | time | 今天 | today | NOT_IN_PASSAGE | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| w01 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w02 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w03 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w04 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w05 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w06 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w07 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w08 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w09 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w10 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w11 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w12 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w13 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w14 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w15 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w16 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w17 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w18 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| w19 | en | extracted | 1 | 1 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON |
| w20 | en | extracted | 2 | 2 | 0 | 0 | 0 | 1.time:LEFT_EMPTY_WITH_REASON, 2.time:LEFT_EMPTY_WITH_REASON |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 1 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 7 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (1)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| w07: Picked up 50 万 PEPE at 0.0000098 on Monday, fee 0 | 1 | time | Monday | 2026-10-05 (day) | on Monday | 2026-10-05 (day) | yes |

#### A time written in another language (7)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| w04: Sold 0.2 BTC at 97.5 k yesterday at 15:20, fee 0 | 1 | time | 昨天 15:20 | (empty) | yesterday at 15:20 | 2026-10-07T15:20:00+02:00 (minute) |
| w08: Sold 80 SOL for 1.2 万 USDT in total yesterday, fee 6 USDT | 1 | time | 昨天 | (empty) | yesterday | 2026-10-07 (day) |
| w12: Sold 2 ETH for 6 900 in total on Bybit yesterday, fee 3 USDT | 1 | time | 昨天 | (empty) | yesterday | 2026-10-07 (day) |
| w16: Sold LINK 25 14.2 yesterday, fee 0.1 LINK | 1 | time | 昨天 | (empty) | yesterday | 2026-10-07 (day) |
| w19: Sold 0.5 ETH at 3，510 today, fee 0.6 USDT | 1 | time | 今天 | (empty) | today | 2026-10-08 (day) |
| w20: Bought 0.1 BTC at 95,400，2 SOL at 150, both on OKX today, fee 0 | 1 | time | 今天 | (empty) | today | 2026-10-08 (day) |
| w20: Bought 0.1 BTC at 95,400，2 SOL at 150, both on OKX today, fee 0 | 2 | time | 今天 | (empty) | today | 2026-10-08 (day) |

</details>

## 2026-10-19: prompt experiment four, new examples with English passages and Chinese numbers, `qwen2.5:7b`

In prompt experiment three ("2026-10-18: prompt experiment three, more examples for the owner's way of writing, `qwen2.5:7b`"), `second` got 6 of 10 trades whole
on the voice set against 1 for `first`, but 29 of 34 on the debug set against
31, and `third` 2 of 10 and 30 of 34; the rule picked neither. The sentences
in which `second` got fewer trades whole than `first` were English passages
and Chinese numbers: on the debug set d04 (the price "六万三千五" given as
"6万35"), d08 ("this morning" given as "今天早上") and d11 (the quantity
"0.02" given as "0.02 个比特币", the words of an example of `first`), and on
the writings set w11 and w15 (an English time given in Chinese); `third` got
fewer in d19 (the price "两千四百五" given as "2,450"). See "The versions on
the debug set" and "The versions on the writings set" in that section. This
experiment measures one more version written for the owner's way of writing
and for those errors: `fourth` (`src/ledger_hand/extraction/prompts/fourth.py`,
its examples in `src/ledger_hand/extraction/prompts/fourth_examples.py`).

`fourth` changes two things from `first` at once, so its runs cannot tell
which of the two made a difference. Its instructions are those of `first`,
unchanged, followed by the two rules of `second` (the owner's words for a
buy; an amount with U or USDT right after it, said neither as the fee nor as
the price of one coin, is the total), the very same text, so its
instructions are those of `second` and `third` to the letter. Its examples
are the ten of `first`, unchanged and in their order, followed by seven more,
invented, each a buy on OKX with the fee paid in the coin bought. Five have
Chinese in them and are written the way the owner writes, with no space
between Chinese and a number: three show an amount in U that is the total,
with no quantity, said with 补了, 再补 and 买了点; two a long opinion with a
percentage in it that is not the trade's price, one before the trade and one
after it, copied whole and without the mark that sets it apart; between them
a quantity, a price and a fee written right against the Chinese, 买到, 买了点,
补仓 and a limit order filled, each a buy, and one passage of two trades that
share the time and the exchange, each with an opinion of its own; and one of
the five has its price in Chinese numbers ("五万九千八"), copied as written.
Two are in English only, each with an English time copied in English ("this
morning", "yesterday"), one with a quantity written as a bare number ("20"),
the other with an English coin name ("3.2 ATOM"). Its words for asking again
and its reply table are those of `first`. So `fourth` differs from `third`
only in the seven examples, and from `second` only in its examples: the
seven take the place of the six of `second`, none of which is used.

Two facts bear on every number below. The new examples were written after the errors of `first` on the voice set and after the errors of `second` and `third` on the debug and the writings set, so the scores of `fourth` on all three sets are not scores on passages it has not seen; the only passages it has not seen are those of the final set and of the owner's later use. And `first` already gets every trade of the final set whole, so the final set can show only whether a candidate falls behind `first`, not whether it does better.

### The rule

The rule below picks a candidate over `first`, and the final-set line after
it says when a candidate passes the final set. Both were written into the
module description of `evals/compare_sets.py` and committed in `48250bf`,
before any run of prompt experiment three. That file has not changed since,
up to `a9a6287`, the commit the first run of this experiment was made at,
and `--choose` and `--final` print them as they stand here. The rule:

A candidate is picked when, and only when, all five of these hold, each
against the run of `first` made in the same experiment:

1. on the voice set, more whole trades right than `first`;
2. on the debug set, no fewer whole trades right than `first`;
3. on the debug set, no more wrong values with no issue about them than
   `first` (the list "Wrong values in drafts with no issue about them" of
   the summary, the made-up values with no issue included);
4. on the debug set, no more trades missed and extra, added up over all
   scored sentences, than `first`;
5. on the voice set, no more wrong values with no issue about them than
   `first`.

The writings set is shown beside the debug and the voice set, with the same
counts, and judged by none of the five. The seconds are shown only. A later
candidate is held to the same rule against `first`, never against an
earlier candidate.

In this section, "the run of `first` made in the same experiment" is each of the three runs of `first` made for prompt experiment three, reused here and not made again: `first` was not run in this experiment. They may stand for runs of
this experiment because the model server's version, the model's
fingerprint, the content fingerprint of `first`, every parameter, the set
files and the reply table of those runs are those of the runs of `fourth`
(the gate of this section checks each); because that section records them
giving the same raw replies as the earlier runs of `first` on the same sets
(30 of 30, 10 of 10 and 20 of 20 sentences); and because the program did not
change between them: from `48250bf` to `a9a6287`, `src/` and `evals/` (the
results files and this record aside) gained only the files of the prompt
versions `third` and `fourth` and the lines that register them in
`evals/run.py` and `evals/compare.py`.

The final-set line:

The final set is run once, with the candidate the rule picked, and only
then. Its run is compared with an earlier run of `first` on the final set,
of the same model with the same parameters, and passes when all three of
these hold:

1. no fewer whole trades right than `first`;
2. no more trades missed and extra, added up over all scored sentences,
   than `first`;
3. no more wrong values with no issue about them than `first`.

### Conditions

`qwen2.5:7b` (fingerprint
`845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`), Ollama
0.34.3, and the settings' defaults in every run: temperature 0.0, top_p 1.0,
longest reply 1,024 tokens, context 16,384 tokens, 120 seconds per call, 2
retries 1 second apart, and asking again once after a reply that misses its
table; every passage read in one list. No variable starting with
`LEDGER_HAND_MODEL_` was set; each run named its model with `--model`. The
model was not loaded on purpose before a run, so the first sentence of a run
may include loading it into memory. `first` has the content fingerprint of
its earlier runs (`7a510f4aaf16f7830ea5df2ec2071a276006565014e61bf295aa44a57a297112`),
`third` has `facabbe239e4ab100df1bb517ff25160711508d206f30f15d6185ac5d0001a65`
and `fourth` `2297097d69cdfd23125895a0bce46e2328c9baa57aac314c3573a9ce1b514741`.
The three runs of `fourth` were made one after the other on 2026-10-19, at
commits that differ only by the results files of the runs before them. The
runs of `first` and `third` are those of prompt experiment three, not made
again; their commits and times below are read from their results files, and
their own subsections are under "The runs of prompt experiment three".
`third` is shown beside `first` and `fourth` because it differs from
`fourth` only in the seven examples; it is shown only, and judged by none of
the conditions of the rule.

| Run | Commit | Began (UTC) | Finished (UTC) |
| --- | --- | --- | --- |
| debug set, `first` (prompt experiment three) | `48250bf` | 2026-10-18 17:37:52 | 2026-10-18 17:39:50 |
| voice set, `first` (prompt experiment three) | `3459426` | 2026-10-18 17:40:17 | 2026-10-18 17:41:02 |
| writings set, `first` (prompt experiment three) | `fd326a0` | 2026-10-18 17:41:14 | 2026-10-18 17:42:21 |
| debug set, `third` (prompt experiment three) | `5aba53f` | 2026-10-19 07:48:47 | 2026-10-19 07:50:54 |
| voice set, `third` (prompt experiment three) | `8a62e97` | 2026-10-19 07:51:07 | 2026-10-19 07:51:54 |
| writings set, `third` (prompt experiment three) | `f847fd0` | 2026-10-19 07:52:08 | 2026-10-19 07:53:17 |
| debug set, `fourth` | `a9a6287` | 2026-10-19 11:06:19 | 2026-10-19 11:08:26 |
| voice set, `fourth` | `48343e4` | 2026-10-19 11:09:45 | 2026-10-19 11:10:29 |
| writings set, `fourth` | `8036cf9` | 2026-10-19 11:10:40 | 2026-10-19 11:11:49 |

How to read the subsections below. Each is printed by `evals/compare_sets.py`
from the results files of one set, given in the order `first`, `third`,
`fourth`. The first two tables hold the scores (see the top of this file)
and the three more counts, the sentences in which a reply was cut off, the
calls to the model, the sentences and their seconds: added up, per sentence
(added up, divided by the sentences), the first sentence's and the longest
sentence's, with the sentence it was. The third is each field, right of the
pairs, for each version (all scored sentences). The last lists, for the
voice set, every sentence, and for the other two sets every sentence not to
record and the sentences where the versions differ in result, drafts, whole
trades right or the fields not right. A sentence not to record shows its
drafts and, for each, whether it passes the check of a draft (`stopped` or
`passes`); it is counted in no score. The last column names a version that
gets fewer trades of a scored sentence whole right than `first`.

### The versions on the debug set

The runs share the set, the model, the way of reading a passage and every parameter; only the prompt version differs: `first`, `third`, `fourth`.

| Version | Well-formed | Whole trades right | One trade | Several trades | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | 26 / 26 (100.0%) | 31 / 34 (91.2%) | 13 / 15 (86.7%) | 18 / 19 (94.7%) | 0 | 0 | 2 / 140 (1.4%) | 3 / 3 (100.0%) |
| `third` | 26 / 26 (100.0%) | 30 / 34 (88.2%) | 13 / 15 (86.7%) | 17 / 19 (89.5%) | 0 | 0 | 1 / 140 (0.7%) | 3 / 3 (100.0%) |
| `fourth` | 26 / 26 (100.0%) | 33 / 34 (97.1%) | 15 / 15 (100.0%) | 18 / 19 (94.7%) | 0 | 0 | 0 / 140 (0.0%) | 3 / 3 (100.0%) |

| Version | Wrong values with no issue | A total put as the price | Half copies (any) | Half copies (not right) | A time in another language | Sentences with a reply cut off | Calls | Sentences | Seconds | Seconds per sentence | First sentence, seconds | Longest sentence, seconds | Results file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | 2 | 2 | 0 | 0 | 2 | 0 | 30 | 30 | 118.6 | 3.95 | 8.841 | 8.841 (d01) | `evals/results/run-20261018T173752Z-debug-first.jsonl` |
| `third` | 1 | 1 | 0 | 0 | 2 | 0 | 30 | 30 | 126.6 | 4.22 | 9.9 | 9.9 (d01) | `evals/results/run-20261019T074847Z-debug-third.jsonl` |
| `fourth` | 0 | 0 | 1 | 0 | 0 | 0 | 30 | 30 | 127.0 | 4.23 | 12.121 | 12.121 (d01) | `evals/results/run-20261019T110619Z-debug-fourth.jsonl` |

| Field | `first`, right / pairs | `third`, right / pairs | `fourth`, right / pairs |
| --- | --- | --- | --- |
| side | 34 / 34 (100.0%) | 34 / 34 (100.0%) | 34 / 34 (100.0%) |
| coin | 34 / 34 (100.0%) | 34 / 34 (100.0%) | 34 / 34 (100.0%) |
| quantity | 33 / 34 (97.1%) | 33 / 34 (97.1%) | 33 / 34 (97.1%) |
| price | 32 / 34 (94.1%) | 32 / 34 (94.1%) | 34 / 34 (100.0%) |
| total | 33 / 34 (97.1%) | 33 / 34 (97.1%) | 34 / 34 (100.0%) |
| price_currency | 34 / 34 (100.0%) | 34 / 34 (100.0%) | 34 / 34 (100.0%) |
| fee | 34 / 34 (100.0%) | 34 / 34 (100.0%) | 34 / 34 (100.0%) |
| fee_currency | 34 / 34 (100.0%) | 34 / 34 (100.0%) | 34 / 34 (100.0%) |
| time | 32 / 34 (94.1%) | 32 / 34 (94.1%) | 34 / 34 (100.0%) |
| platform | 34 / 34 (100.0%) | 34 / 34 (100.0%) | 34 / 34 (100.0%) |
| opinion | 34 / 34 (100.0%) | 34 / 34 (100.0%) | 34 / 34 (100.0%) |

The sentences where the versions differ in result, drafts, whole trades right or the fields not right, and every sentence not to record (8 of 30):

| Sentence | Group | Result, `first` | Result, `third` | Result, `fourth` | Drafts, `first` | Drafts, `third` | Drafts, `fourth` | Whole right, `first` | Whole right, `third` | Whole right, `fourth` | Fields not right, `first` | Fields not right, `third` | Fields not right, `fourth` | Checks of the drafts, `first` | Checks of the drafts, `third` | Checks of the drafts, `fourth` | Fewer whole right than `first` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| d05 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 0 | 0 | 1 | 1.price:MADE_UP, 1.time:LEFT_EMPTY_WITH_REASON | 1.time:LEFT_EMPTY_WITH_REASON | - | - | - | - | - |
| d13 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 0 | 0 | 1 | 1.time:LEFT_EMPTY_WITH_REASON | 1.time:LEFT_EMPTY_WITH_REASON | - | - | - | - | - |
| d19 | scored | extracted | extracted | extracted | 2 | 2 | 2 | 2 | 1 | 2 | - | 1.price:LEFT_EMPTY_WITH_REASON | - | - | - | - | `third` |
| d23 | scored | extracted | extracted | extracted | 3 | 3 | 3 | 2 | 2 | 2 | 3.quantity:LEFT_EMPTY_WITH_REASON, 3.price:MADE_UP, 3.total:LEFT_EMPTY_BY_MODEL | 3.quantity:LEFT_EMPTY_WITH_REASON, 3.price:MADE_UP, 3.total:LEFT_EMPTY_BY_MODEL | 3.quantity:LEFT_EMPTY_WITH_REASON | - | - | - | - |
| d27 | not_to_record | extracted | extracted | extracted | 1 | 1 | 1 | - | - | - | - | - | - | stopped | stopped | stopped | - |
| d28 | not_to_record | extracted | extracted | extracted | 2 | 2 | 2 | - | - | - | - | - | - | stopped, stopped | stopped, stopped | stopped, stopped | - |
| d29 | not_to_record | extracted | extracted | extracted | 1 | 1 | 1 | - | - | - | - | - | - | stopped | stopped | stopped | - |
| d30 | not_to_record | extracted | extracted | extracted | 0 | 0 | 0 | - | - | - | - | - | - | - | - | - | - |

`fourth` got fewer trades whole than `first` in no sentence of the debug
set. It got more in d05 and d13, where the raw replies of `first` and `third`
held the time in Chinese ("昨天" and "昨天 18:20", where the passages write
"yesterday" and "yesterday at 18:20"), which the program left empty, saying
so in the issues; `fourth` copied both as written. In d19, the one sentence
of the debug set in which `third` got fewer trades whole than `first`, see
"The versions on the debug set" in "2026-10-18: prompt experiment three, more examples for the owner's way of writing, `qwen2.5:7b`".

### The versions on the voice set

The runs share the set, the model, the way of reading a passage and every parameter; only the prompt version differs: `first`, `third`, `fourth`.

| Version | Well-formed | Whole trades right | One trade | Several trades | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | 9 / 9 (100.0%) | 1 / 10 (10.0%) | 1 / 8 (12.5%) | 0 / 2 (0.0%) | 0 | 0 | 4 / 12 (33.3%) | 0 / 0 (-) |
| `third` | 9 / 9 (100.0%) | 2 / 10 (20.0%) | 2 / 8 (25.0%) | 0 / 2 (0.0%) | 0 | 0 | 2 / 12 (16.7%) | 0 / 0 (-) |
| `fourth` | 9 / 9 (100.0%) | 8 / 10 (80.0%) | 6 / 8 (75.0%) | 2 / 2 (100.0%) | 0 | 0 | 0 / 12 (0.0%) | 0 / 0 (-) |

| Version | Wrong values with no issue | A total put as the price | Half copies (any) | Half copies (not right) | A time in another language | Sentences with a reply cut off | Calls | Sentences | Seconds | Seconds per sentence | First sentence, seconds | Longest sentence, seconds | Results file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | 6 | 0 | 2 | 2 | 0 | 0 | 10 | 10 | 45.3 | 4.53 | 4.442 | 8.8 (u09) | `evals/results/run-20261018T174017Z-voice-first.jsonl` |
| `third` | 5 | 0 | 3 | 3 | 0 | 0 | 10 | 10 | 47.1 | 4.71 | 4.705 | 9.111 (u09) | `evals/results/run-20261019T075107Z-voice-third.jsonl` |
| `fourth` | 1 | 0 | 2 | 1 | 0 | 0 | 10 | 10 | 44.3 | 4.43 | 4.873 | 8.67 (u09) | `evals/results/run-20261019T110945Z-voice-fourth.jsonl` |

| Field | `first`, right / pairs | `third`, right / pairs | `fourth`, right / pairs |
| --- | --- | --- | --- |
| side | 8 / 10 (80.0%) | 10 / 10 (100.0%) | 10 / 10 (100.0%) |
| coin | 10 / 10 (100.0%) | 10 / 10 (100.0%) | 10 / 10 (100.0%) |
| quantity | 7 / 10 (70.0%) | 7 / 10 (70.0%) | 10 / 10 (100.0%) |
| price | 10 / 10 (100.0%) | 10 / 10 (100.0%) | 10 / 10 (100.0%) |
| total | 7 / 10 (70.0%) | 8 / 10 (80.0%) | 10 / 10 (100.0%) |
| price_currency | 7 / 10 (70.0%) | 8 / 10 (80.0%) | 10 / 10 (100.0%) |
| fee | 9 / 10 (90.0%) | 10 / 10 (100.0%) | 10 / 10 (100.0%) |
| fee_currency | 9 / 10 (90.0%) | 10 / 10 (100.0%) | 10 / 10 (100.0%) |
| time | 10 / 10 (100.0%) | 10 / 10 (100.0%) | 10 / 10 (100.0%) |
| platform | 10 / 10 (100.0%) | 10 / 10 (100.0%) | 10 / 10 (100.0%) |
| opinion | 5 / 10 (50.0%) | 4 / 10 (40.0%) | 8 / 10 (80.0%) |

Every sentence (10 of 10):

| Sentence | Group | Result, `first` | Result, `third` | Result, `fourth` | Drafts, `first` | Drafts, `third` | Drafts, `fourth` | Whole right, `first` | Whole right, `third` | Whole right, `fourth` | Fields not right, `first` | Fields not right, `third` | Fields not right, `fourth` | Checks of the drafts, `first` | Checks of the drafts, `third` | Checks of the drafts, `fourth` | Fewer whole right than `first` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| u01 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 0 | 0 | 1 | 1.quantity:LEFT_EMPTY_WITH_REASON, 1.opinion:WRONG_SILENT | 1.quantity:LEFT_EMPTY_WITH_REASON, 1.opinion:WRONG_SILENT | - | - | - | - | - |
| u02 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 0 | 0 | 1 | 1.quantity:MADE_UP, 1.total:LEFT_EMPTY_BY_MODEL, 1.price_currency:LEFT_EMPTY_BY_MODEL | 1.quantity:MADE_UP, 1.total:LEFT_EMPTY_BY_MODEL, 1.price_currency:LEFT_EMPTY_BY_MODEL | - | - | - | - | - |
| u03 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 0 | 0 | 0 | 1.opinion:WRONG_SILENT | 1.opinion:WRONG_SILENT | 1.opinion:WRONG_SILENT | - | - | - | - |
| u04 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 1 | 1 | 1 | - | - | - | - | - | - | - |
| u05 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 0 | 0 | 1 | 1.opinion:WRONG_SILENT | 1.opinion:WRONG_SILENT | - | - | - | - | - |
| u06 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 0 | 0 | 0 | 1.total:LEFT_EMPTY_BY_MODEL, 1.price_currency:LEFT_EMPTY_BY_MODEL, 1.fee:MADE_UP, 1.fee_currency:MADE_UP | 1.quantity:MADE_UP, 1.total:LEFT_EMPTY_BY_MODEL, 1.price_currency:LEFT_EMPTY_BY_MODEL | 1.opinion:LEFT_EMPTY_WITH_REASON | - | - | - | - |
| u07 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 0 | 0 | 1 | 1.side:LEFT_EMPTY_BY_MODEL | 1.opinion:WRONG_SILENT | - | - | - | - | - |
| u08 | not_to_record | extracted | extracted | extracted | 1 | 1 | 0 | - | - | - | - | - | - | stopped | stopped | - | - |
| u09 | scored | extracted | extracted | extracted | 2 | 2 | 2 | 0 | 0 | 2 | 1.opinion:WRONG_SILENT, 2.opinion:LEFT_EMPTY_BY_MODEL | 1.opinion:WRONG_SILENT, 2.opinion:LEFT_EMPTY_BY_MODEL | - | - | - | - | - |
| u10 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 0 | 1 | 1 | 1.side:LEFT_EMPTY_BY_MODEL, 1.quantity:MADE_UP, 1.total:LEFT_EMPTY_BY_MODEL, 1.price_currency:LEFT_EMPTY_BY_MODEL | - | - | - | - | - | - |

`fourth` got fewer trades whole than `first` in no sentence of the voice set.
In the two scored sentences it did not get whole: u03's opinion leaves out
its first clause, as with `first` and `third`, with no issue about it; for
u06 the reply joins two parts of the passage ("BTC又回到6万附近了" and
"牛市初期不怕") into one opinion, which is not a piece of the passage, and the
program left it empty, saying so in the issues. For u08, the passage not to
record, `fourth` gave no draft, where `first` and `third` gave one.

### The versions on the writings set

The runs share the set, the model, the way of reading a passage and every parameter; only the prompt version differs: `first`, `third`, `fourth`.

| Version | Well-formed | Whole trades right | One trade | Several trades | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | 20 / 20 (100.0%) | 15 / 22 (68.2%) | 13 / 18 (72.2%) | 2 / 4 (50.0%) | 0 | 0 | 0 / 93 (0.0%) | 0 / 0 (-) |
| `third` | 20 / 20 (100.0%) | 15 / 22 (68.2%) | 13 / 18 (72.2%) | 2 / 4 (50.0%) | 0 | 0 | 0 / 93 (0.0%) | 0 / 0 (-) |
| `fourth` | 20 / 20 (100.0%) | 21 / 22 (95.5%) | 17 / 18 (94.4%) | 4 / 4 (100.0%) | 0 | 0 | 0 / 93 (0.0%) | 0 / 0 (-) |

| Version | Wrong values with no issue | A total put as the price | Half copies (any) | Half copies (not right) | A time in another language | Sentences with a reply cut off | Calls | Sentences | Seconds | Seconds per sentence | First sentence, seconds | Longest sentence, seconds | Results file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | 0 | 0 | 1 | 0 | 7 | 0 | 20 | 20 | 67.1 | 3.36 | 3.131 | 5.564 (w20) | `evals/results/run-20261018T174114Z-writings-first.jsonl` |
| `third` | 0 | 0 | 1 | 0 | 7 | 0 | 20 | 20 | 69.0 | 3.45 | 3.221 | 5.961 (w20) | `evals/results/run-20261019T075208Z-writings-third.jsonl` |
| `fourth` | 0 | 0 | 3 | 0 | 0 | 0 | 20 | 20 | 69.7 | 3.49 | 3.174 | 5.793 (w20) | `evals/results/run-20261019T111040Z-writings-fourth.jsonl` |

| Field | `first`, right / pairs | `third`, right / pairs | `fourth`, right / pairs |
| --- | --- | --- | --- |
| side | 22 / 22 (100.0%) | 22 / 22 (100.0%) | 22 / 22 (100.0%) |
| coin | 22 / 22 (100.0%) | 22 / 22 (100.0%) | 22 / 22 (100.0%) |
| quantity | 22 / 22 (100.0%) | 22 / 22 (100.0%) | 21 / 22 (95.5%) |
| price | 22 / 22 (100.0%) | 22 / 22 (100.0%) | 22 / 22 (100.0%) |
| total | 22 / 22 (100.0%) | 22 / 22 (100.0%) | 22 / 22 (100.0%) |
| price_currency | 22 / 22 (100.0%) | 22 / 22 (100.0%) | 22 / 22 (100.0%) |
| fee | 22 / 22 (100.0%) | 22 / 22 (100.0%) | 22 / 22 (100.0%) |
| fee_currency | 22 / 22 (100.0%) | 22 / 22 (100.0%) | 22 / 22 (100.0%) |
| time | 15 / 22 (68.2%) | 15 / 22 (68.2%) | 22 / 22 (100.0%) |
| platform | 22 / 22 (100.0%) | 22 / 22 (100.0%) | 22 / 22 (100.0%) |
| opinion | 22 / 22 (100.0%) | 22 / 22 (100.0%) | 22 / 22 (100.0%) |

The sentences where the versions differ in result, drafts, whole trades right or the fields not right, and every sentence not to record (7 of 20):

| Sentence | Group | Result, `first` | Result, `third` | Result, `fourth` | Drafts, `first` | Drafts, `third` | Drafts, `fourth` | Whole right, `first` | Whole right, `third` | Whole right, `fourth` | Fields not right, `first` | Fields not right, `third` | Fields not right, `fourth` | Checks of the drafts, `first` | Checks of the drafts, `third` | Checks of the drafts, `fourth` | Fewer whole right than `first` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| w04 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 0 | 0 | 1 | 1.time:LEFT_EMPTY_WITH_REASON | 1.time:LEFT_EMPTY_WITH_REASON | - | - | - | - | - |
| w06 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 1 | 1 | 0 | - | - | 1.quantity:LEFT_EMPTY_WITH_REASON | - | - | - | `fourth` |
| w08 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 0 | 0 | 1 | 1.time:LEFT_EMPTY_WITH_REASON | 1.time:LEFT_EMPTY_WITH_REASON | - | - | - | - | - |
| w12 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 0 | 0 | 1 | 1.time:LEFT_EMPTY_WITH_REASON | 1.time:LEFT_EMPTY_WITH_REASON | - | - | - | - | - |
| w16 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 0 | 0 | 1 | 1.time:LEFT_EMPTY_WITH_REASON | 1.time:LEFT_EMPTY_WITH_REASON | - | - | - | - | - |
| w19 | scored | extracted | extracted | extracted | 1 | 1 | 1 | 0 | 0 | 1 | 1.time:LEFT_EMPTY_WITH_REASON | 1.time:LEFT_EMPTY_WITH_REASON | - | - | - | - | - |
| w20 | scored | extracted | extracted | extracted | 2 | 2 | 2 | 0 | 0 | 2 | 1.time:LEFT_EMPTY_WITH_REASON, 2.time:LEFT_EMPTY_WITH_REASON | 1.time:LEFT_EMPTY_WITH_REASON, 2.time:LEFT_EMPTY_WITH_REASON | - | - | - | - | - |

In w06, the one sentence of the writings set in which `fourth` got fewer
trades whole than `first`, its raw reply held the quantity "5 万个", where the
passage writes "5 万 个"; it is not a piece of the passage, and the program
left it empty, saying so in the issues. In w04, w08, w12, w16, w19 and w20,
the raw replies of `first` and `third` held the time in Chinese ("昨天 15:20",
"昨天" or "今天", where the passages write "yesterday at 15:20", "yesterday"
or "today"); `fourth` copied it as written.

### The rule applied to `fourth`

`evals/compare_sets.py --choose`, given the runs of `first` and `fourth`
above, prints:

The rule, fixed before the first run it judges:

A candidate is picked when, and only when, all five of these hold, each
against the run of `first` made in the same experiment:

1. on the voice set, more whole trades right than `first`;
2. on the debug set, no fewer whole trades right than `first`;
3. on the debug set, no more wrong values with no issue about them than
   `first` (the list "Wrong values in drafts with no issue about them" of
   the summary, the made-up values with no issue included);
4. on the debug set, no more trades missed and extra, added up over all
   scored sentences, than `first`;
5. on the voice set, no more wrong values with no issue about them than
   `first`.

The writings set is shown beside the debug and the voice set, with the same
counts, and judged by none of the five. The seconds are shown only. A later
candidate is held to the same rule against `first`, never against an
earlier candidate.

`fourth` against `first`:

| Condition | Set | `first` | `fourth` | Holds |
| --- | --- | --- | --- | --- |
| 1. more whole trades right | voice | 1 | 8 | yes |
| 2. no fewer whole trades right | debug | 31 | 33 | yes |
| 3. no more wrong values with no issue | debug | 2 | 0 | yes |
| 4. no more trades missed and extra | debug | 0 | 0 | yes |
| 5. no more wrong values with no issue | voice | 6 | 1 | yes |

The same counts on the writings set, judged by none of the conditions:

| Count | `first` | `fourth` |
| --- | --- | --- |
| Whole trades right | 15 | 21 |
| Wrong values with no issue | 0 | 0 |
| Trades missed and extra | 0 | 0 |

Picked: `fourth`; all five conditions hold.

### The room in the context

Ollama does not refuse a prompt longer than the context it is given: it
drops the start of the prompt, where the instructions are, without an error.
So a version goes into the product only when its prompt, the longest
passage the ledger keeps and the longest reply fit in the context together.
The tokens the model read for the first call on the shortest passage of the
voice set, by characters, bound a version's own prompt from above; to them
are added about 11,600 tokens for the longest passage (as
`src/ledger_hand/settings.py` describes `LEDGER_HAND_MODEL_CONTEXT_TOKENS`)
and the longest reply, `max_reply_tokens`, and the sum is set against
`context_tokens` (both from the first line of the results file):

| Version | Shortest passage of the voice set | Characters | Tokens read, first call | With the longest passage and the longest reply | Context | Room left | Fits |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | u10 | 36 | 1,757 | 14,381 | 16,384 | 2,003 | yes |
| `fourth` | u10 | 36 | 3,116 | 15,740 | 16,384 | 644 | yes |

### The numbers in short

- Debug set: `first` 31 of 34 trades whole, `fourth` 33 (and `third`, shown
  only, 30). Wrong values with no issue 2 and 0; trades missed and extra 0
  and 0. `fourth` got fewer trades whole than `first` in no sentence, and
  more in d05 and d13.
- Voice set: `first` 1 of 10 trades whole, `fourth` 8 (`third` 2). Wrong
  values with no issue 6 and 1.
- Writings set: `first` 15 of 22 trades whole, `fourth` 21 (`third` 15).
  Wrong values with no issue 0 and 0. `fourth` got fewer trades whole in w06,
  and copied every English time as written, where `first` gave 7 in Chinese.
- Seconds per sentence, `first` and `fourth`: debug set 3.95 and 4.23; voice
  set 4.53 and 4.43; writings set 3.36 and 3.49. For u10, the shortest
  passage of the voice set, the model read 1,757 tokens with `first` and
  3,116 with `fourth`; with the longest passage and the longest reply, 2,003
  and 644 tokens of the context of 16,384 are left.
- The rule: `fourth` is picked; all five conditions hold. Its prompt fits in
  the context with the longest passage and the longest reply.
- The new examples were written after the errors of `first` on the voice set and after the errors of `second` and `third` on the debug and the writings set, so the scores of `fourth` on all three sets are not scores on passages it has not seen; the only passages it has not seen are those of the final set and of the owner's later use. `first` already gets every trade of the final set whole, so the final set can show only whether a candidate falls behind `first`, not whether it does better.

### The runs of prompt experiment four

Each run of `fourth` has its own subsection with the tables its results file
gives and its three more counts (`evals/extra_counts.py`). The runs of
`first` and `third` shown above have theirs under "The runs of prompt
experiment three".

### Run: debug set, prompt `fourth`, prompt experiment four

Results file: `evals/results/run-20261019T110619Z-debug-fourth.jsonl`, with its summary in `run-20261019T110619Z-debug-fourth.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | debug |
| final_exam_switch | False |
| set_file | evals/sets/debug.json |
| set_sha256 | 4529d98323ad1df4d38f5a5b73cdf1082b6a1cd08a0604a454ecf7986104f4d8 |
| prompt | fourth |
| prompt file src/ledger_hand/extraction/prompts/fourth.py | sha256 374328508b0ef73e7e2a77787654d0426ec8cd675648927d298078530a841a0b |
| prompt file src/ledger_hand/extraction/prompts/fourth_examples.py | sha256 b06372ca9f989044b0f57f56e6c6185b348afb79939ec294c65511d786ef4c9b |
| prompt file src/ledger_hand/extraction/prompts/second.py | sha256 6066b189cbf96fde8d7fb00a752ef125aa50afe061298858c291518d07ca0191 |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | 2297097d69cdfd23125895a0bce46e2328c9baa57aac314c3573a9ce1b514741 |
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| method | one_list |
| commit | a9a628758980ccc690b482f8891998a7597d85cb |
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
| started_at | 2026-10-19T11:06:19+00:00 |
| sentences | 30 |
| sum_of_sentence_seconds | 126.956 |
| first_sentence_seconds | 12.121 |
| longest_sentence_seconds | 12.121 |
| finished_at | 2026-10-19T11:08:26+00:00 |
| seconds_of_the_last_session | 127.0 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 26 | 26 / 26 (100.0%) | 33 / 34 (97.1%) | 0 | 0 | 0 / 140 (0.0%) | 3 / 3 (100.0%) |
| one trade | 15 | 15 / 15 (100.0%) | 15 / 15 (100.0%) | 0 | 0 | 0 / 60 (0.0%) | 0 / 0 (-) |
| several trades | 8 | 8 / 8 (100.0%) | 18 / 19 (94.7%) | 0 | 0 | 0 / 80 (0.0%) | 0 / 0 (-) |
| - two trades | 5 | 5 / 5 (100.0%) | 10 / 10 (100.0%) | 0 | 0 | 0 / 42 (0.0%) | 0 / 0 (-) |
| - three or more trades | 3 | 3 / 3 (100.0%) | 8 / 9 (88.9%) | 0 | 0 | 0 / 38 (0.0%) | 0 / 0 (-) |
| no trade (talk) | 3 | 3 / 3 (100.0%) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 3 / 3 (100.0%) |
| Chinese | 10 | 10 / 10 (100.0%) | 13 / 13 (100.0%) | 0 | 0 | 0 / 52 (0.0%) | 1 / 1 (100.0%) |
| English | 9 | 9 / 9 (100.0%) | 12 / 12 (100.0%) | 0 | 0 | 0 / 49 (0.0%) | 1 / 1 (100.0%) |
| mixed | 7 | 7 / 7 (100.0%) | 8 / 9 (88.9%) | 0 | 0 | 0 / 39 (0.0%) | 1 / 1 (100.0%) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 34 / 34 (100.0%) |
| coin | 34 / 34 (100.0%) |
| quantity | 33 / 34 (97.1%) |
| price | 34 / 34 (100.0%) |
| total | 34 / 34 (100.0%) |
| price_currency | 34 / 34 (100.0%) |
| fee | 34 / 34 (100.0%) |
| fee_currency | 34 / 34 (100.0%) |
| time | 34 / 34 (100.0%) |
| platform | 34 / 34 (100.0%) |
| opinion | 34 / 34 (100.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 373 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 1 |
| - because the model's phrase is not a piece of the passage | 1 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 0 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 0 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (1; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
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
| d05 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d06 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d07 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d08 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d09 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d10 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d11 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d12 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d13 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d14 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d15 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| d16 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d17 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d18 | mixed | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d19 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d20 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |
| d21 | zh | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d22 | en | extracted | 3 | 3 | 3 | 0 | 0 | - |
| d23 | mixed | extracted | 3 | 3 | 2 | 0 | 0 | 3.quantity:LEFT_EMPTY_WITH_REASON |
| d24 | zh | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d25 | en | extracted | 0 | 0 | 0 | 0 | 0 | - |
| d26 | mixed | extracted | 0 | 0 | 0 | 0 | 0 | - |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 1 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 0 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (1)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| d05: Bought 120 ADA for 64.80 USDT total yesterday, fee 0.002 BNB | 1 | quantity | 120 | 120 | 120 ADA | 120 | yes |

#### A time written in another language (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

</details>

### Run: voice set, prompt `fourth`, prompt experiment four

Results file: `evals/results/run-20261019T110945Z-voice-fourth.jsonl`, with its summary in `run-20261019T110945Z-voice-fourth.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | voice |
| final_exam_switch | False |
| set_file | evals/sets/voice.json |
| set_sha256 | 884e678672d4fcedc2d36da18e96e7e70261785936b4fc48cd2a3259d2b35196 |
| prompt | fourth |
| prompt file src/ledger_hand/extraction/prompts/fourth.py | sha256 374328508b0ef73e7e2a77787654d0426ec8cd675648927d298078530a841a0b |
| prompt file src/ledger_hand/extraction/prompts/fourth_examples.py | sha256 b06372ca9f989044b0f57f56e6c6185b348afb79939ec294c65511d786ef4c9b |
| prompt file src/ledger_hand/extraction/prompts/second.py | sha256 6066b189cbf96fde8d7fb00a752ef125aa50afe061298858c291518d07ca0191 |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | 2297097d69cdfd23125895a0bce46e2328c9baa57aac314c3573a9ce1b514741 |
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| method | one_list |
| commit | 48343e474047d968300c3bb195c86bd354b6c857 |
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
| started_at | 2026-10-19T11:09:45+00:00 |
| sentences | 10 |
| sum_of_sentence_seconds | 44.29 |
| first_sentence_seconds | 4.873 |
| longest_sentence_seconds | 8.67 |
| finished_at | 2026-10-19T11:10:29+00:00 |
| seconds_of_the_last_session | 44.306 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 9 | 9 / 9 (100.0%) | 8 / 10 (80.0%) | 0 | 0 | 0 / 12 (0.0%) | 0 / 0 (-) |
| one trade | 8 | 8 / 8 (100.0%) | 6 / 8 (75.0%) | 0 | 0 | 0 / 12 (0.0%) | 0 / 0 (-) |
| several trades | 1 | 1 / 1 (100.0%) | 2 / 2 (100.0%) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| - two trades | 1 | 1 / 1 (100.0%) | 2 / 2 (100.0%) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| - three or more trades | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| no trade (talk) | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| Chinese | 9 | 9 / 9 (100.0%) | 8 / 10 (80.0%) | 0 | 0 | 0 / 12 (0.0%) | 0 / 0 (-) |
| English | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| mixed | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 10 / 10 (100.0%) |
| coin | 10 / 10 (100.0%) |
| quantity | 10 / 10 (100.0%) |
| price | 10 / 10 (100.0%) |
| total | 10 / 10 (100.0%) |
| price_currency | 10 / 10 (100.0%) |
| fee | 10 / 10 (100.0%) |
| fee_currency | 10 / 10 (100.0%) |
| time | 10 / 10 (100.0%) |
| platform | 10 / 10 (100.0%) |
| opinion | 8 / 10 (80.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 108 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 1 |
| - because the model's phrase is not a piece of the passage | 1 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 0 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 1 |
| MADE_UP: a value in the draft where the gold answer is empty | 0 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (1)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |
| u03: 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的。10:18在OKX买的，50USDT，均价0.3218，手续费0.1553ADA | 1 | opinion | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | WRONG_SILENT |

#### Half copies: the model copied part of the gold phrase (1)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |
| u03 | 1 | opinion | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | WRONG_SILENT |

#### Fields the program left empty (1; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| u06 | 1 | opinion | BTC又回到6万附近了，牛市初期不怕 | 牛市初期不怕 | NOT_IN_PASSAGE | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |
| u08: 在OKX挂了个BTC限价单，59,500买100U，觉得这里是强支撑，等它触发 | open_order | extracted | 0 | - |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| u01 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| u02 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| u03 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.opinion:WRONG_SILENT |
| u04 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| u05 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| u06 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.opinion:LEFT_EMPTY_WITH_REASON |
| u07 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| u09 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| u10 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 2 |
| Half copies, only fields not right (as in the summary) | 1 |
| A time written in another language | 0 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (2)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| u03: 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的。10:18在OKX买的，50USDT，均价0.3218，手续费0.1553ADA | 1 | opinion | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | 看到博主加密庞克说他要做多了，虽然他说的是做多BTC，但是我就想买点ADA，毕竟目前我ADA是亏损最大的 | no |
| u04: 9月25号21:06在OKX买了318.4713个ADA，0.314一个，手续费0.3184713ADA，跟着博主看多 | 1 | quantity | 318.4713个 | 318.4713 | 318.4713个ADA | 318.4713 | yes |

#### A time written in another language (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

</details>

### Run: writings set, prompt `fourth`, prompt experiment four

Results file: `evals/results/run-20261019T111040Z-writings-fourth.jsonl`, with its summary in `run-20261019T111040Z-writings-fourth.summary.json`.

<details>
<summary>The generated tables of this run</summary>

#### Run
| Condition | Value |
| --- | --- |
| set | writings |
| final_exam_switch | False |
| set_file | evals/sets/writings.json |
| set_sha256 | 7ac6a2027ec4434f140db02e51a3a46ca27da7dc89da06b3088866351f38ffce |
| prompt | fourth |
| prompt file src/ledger_hand/extraction/prompts/fourth.py | sha256 374328508b0ef73e7e2a77787654d0426ec8cd675648927d298078530a841a0b |
| prompt file src/ledger_hand/extraction/prompts/fourth_examples.py | sha256 b06372ca9f989044b0f57f56e6c6185b348afb79939ec294c65511d786ef4c9b |
| prompt file src/ledger_hand/extraction/prompts/second.py | sha256 6066b189cbf96fde8d7fb00a752ef125aa50afe061298858c291518d07ca0191 |
| prompt file src/ledger_hand/extraction/prompts/first.py | sha256 e09ca774e7a4455891a9a8980c6932d3b9691f53c00cc189c3dfbcbbfb7368ba |
| prompt file src/ledger_hand/extraction/prompts/first_examples.py | sha256 3088812302b7895fac2c1c65a60a9f703bdfcec40b9cb556b7cf8ef5ec682c32 |
| prompt_content_sha256 | 2297097d69cdfd23125895a0bce46e2328c9baa57aac314c3573a9ce1b514741 |
| reply_table_sha256 | e3870b098001b51896b9671f15ef57491df1f7834c0b880d7588ae65b6548e70 |
| method | one_list |
| commit | 8036cf946ef12ea4187ef29391ca922082054e64 |
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
| started_at | 2026-10-19T11:10:40+00:00 |
| sentences | 20 |
| sum_of_sentence_seconds | 69.705 |
| first_sentence_seconds | 3.174 |
| longest_sentence_seconds | 5.793 |
| finished_at | 2026-10-19T11:11:49+00:00 |
| seconds_of_the_last_session | 69.731 |

#### Scores by group
| Group | Sentences | Well-formed | Whole trades right | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all scored sentences | 20 | 20 / 20 (100.0%) | 21 / 22 (95.5%) | 0 | 0 | 0 / 93 (0.0%) | 0 / 0 (-) |
| one trade | 18 | 18 / 18 (100.0%) | 17 / 18 (94.4%) | 0 | 0 | 0 / 77 (0.0%) | 0 / 0 (-) |
| several trades | 2 | 2 / 2 (100.0%) | 4 / 4 (100.0%) | 0 | 0 | 0 / 16 (0.0%) | 0 / 0 (-) |
| - two trades | 2 | 2 / 2 (100.0%) | 4 / 4 (100.0%) | 0 | 0 | 0 / 16 (0.0%) | 0 / 0 (-) |
| - three or more trades | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| no trade (talk) | 0 | 0 / 0 (-) | 0 / 0 (-) | 0 | 0 | 0 / 0 (-) | 0 / 0 (-) |
| Chinese | 8 | 8 / 8 (100.0%) | 8 / 9 (88.9%) | 0 | 0 | 0 / 38 (0.0%) | 0 / 0 (-) |
| English | 10 | 10 / 10 (100.0%) | 11 / 11 (100.0%) | 0 | 0 | 0 / 46 (0.0%) | 0 / 0 (-) |
| mixed | 2 | 2 / 2 (100.0%) | 2 / 2 (100.0%) | 0 | 0 | 0 / 9 (0.0%) | 0 / 0 (-) |

#### Each field, all scored sentences
| Field | Right / pairs |
| --- | --- |
| side | 22 / 22 (100.0%) |
| coin | 22 / 22 (100.0%) |
| quantity | 21 / 22 (95.5%) |
| price | 22 / 22 (100.0%) |
| total | 22 / 22 (100.0%) |
| price_currency | 22 / 22 (100.0%) |
| fee | 22 / 22 (100.0%) |
| fee_currency | 22 / 22 (100.0%) |
| time | 22 / 22 (100.0%) |
| platform | 22 / 22 (100.0%) |
| opinion | 22 / 22 (100.0%) |

#### Every field of every pair, by kind
| Kind | Fields |
| --- | --- |
| RIGHT: right | 241 |
| LEFT_EMPTY_WITH_REASON: left empty by the program, with the reason in the issues | 1 |
| - because the model's phrase is not a piece of the passage | 1 |
| - because the model's phrase cuts a number of the passage | 0 |
| - because the number reader was unsure of the phrase or could not read it | 0 |
| - because the time reader refused the phrase or gave two candidates | 0 |
| - because another issue about the field | 0 |
| LEFT_EMPTY_BY_MODEL: left empty, with no issue: the model copied nothing that gives it | 0 |
| WRONG_WITH_ISSUE: a wrong value in the draft, with an issue about the field | 0 |
| WRONG_SILENT: a wrong value in the draft, with no issue about the field | 0 |
| MADE_UP: a value in the draft where the gold answer is empty | 0 |
| - of them with an issue about the field | 0 |

#### Wrong values in drafts with no issue about them (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies: the model copied part of the gold phrase (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |
| --- | --- | --- | --- | --- | --- | --- |

#### Fields the program left empty (1; the model's phrase was exactly the gold phrase in 0)
| Sentence | Draft | Field | Model copied | Gold phrase | Reason | Model copied exactly the gold phrase |
| --- | --- | --- | --- | --- | --- | --- |
| w06 | 1 | quantity | 5 万个 | 5 万 个 DOGE | NOT_IN_PASSAGE | no |

#### Passages not to record (not in any score above)
| Sentence | Kind | Result | Drafts | What the check of a draft says |
| --- | --- | --- | --- | --- |

#### Every scored sentence
| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra | Fields not right (gold trade.field:kind) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| w01 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w02 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w03 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w04 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w05 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w06 | zh | extracted | 1 | 1 | 0 | 0 | 0 | 1.quantity:LEFT_EMPTY_WITH_REASON |
| w07 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w08 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w09 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w10 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w11 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w12 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w13 | mixed | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w14 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w15 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w16 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w17 | zh | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w18 | zh | extracted | 2 | 2 | 2 | 0 | 0 | - |
| w19 | en | extracted | 1 | 1 | 1 | 0 | 0 | - |
| w20 | en | extracted | 2 | 2 | 2 | 0 | 0 | - |

#### Three more counts
| Count | Cases |
| --- | --- |
| A total put as the price | 0 |
| Half copies, any field whose phrase is part of the gold phrase | 3 |
| Half copies, only fields not right (as in the summary) | 0 |
| A time written in another language | 0 |

#### A total put as the price (0; gold is the total)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

#### Half copies, counted the second way (3)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold | Field right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| w01: 前天在币安买了 2 w 个 DOGE，0.16 一个，手续费 1U | 1 | quantity | 2 w 个 | (empty) | 2 w 个 DOGE | (empty) | yes |
| w02: 昨天 sold 了 4.5 k 个 XRP at 0.52，fee 0.3 USDT | 1 | quantity | 4.5 k 个 | (empty) | 4.5 k 个 XRP | (empty) | yes |
| w07: Picked up 50 万 PEPE at 0.0000098 on Monday, fee 0 | 1 | time | Monday | 2026-10-05 (day) | on Monday | 2026-10-05 (day) | yes |

#### A time written in another language (0)
| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |
| --- | --- | --- | --- | --- | --- | --- |

</details>
