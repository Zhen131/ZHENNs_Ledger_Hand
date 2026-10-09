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

Five prompt versions for extraction, each one technique away from the first,
measured with the same test sentences, scoring and model as the baseline.
Each run below has its own subsection with the tables its results file
gives, and the three more counts (`evals/extra_counts.py`).

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
