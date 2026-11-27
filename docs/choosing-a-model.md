# Choosing a model

The program extracts with `qwen2.5:7b` on this machine by default, and that
default is unchanged. This page says what else was measured, and which
model to pick for which machine, from one comparison: eight models on the
same rulers, with the same prompts and settings, on 2026-11-27. The full
figures, the rulers and how each was run are in `evals/RESULTS.md`,
"2026-11-27: eight models on the same rulers". A model is switched with
`LEDGER_HAND_MODEL_NAME`, and a cloud service with `LEDGER_HAND_MODEL_PLUG`
(README, "Model settings" and "Switching to a cloud model").

## The models

Every local model was measured on one Windows machine with an RTX 5080 of
16 GB. "Memory" is what `ollama ps` showed while the model was loaded; it
holds the context of 16384 tokens the program asks for and its cache, so
it is more than the file. "Seconds a sentence" is the whole run of 183
sentences, timed from outside, loading the model and starting Python
included. "Wrong with nothing said" adds up the trades with a wrong figure
and no mark on the practice halves of the exam said the owner's way, the
fields wrong with nothing said on the final set, and the proposals sent
wrong on the stock and change sets: the mistake a person would not see.

| Model | File | Memory on the RTX 5080 | Seconds a sentence | Cost of the whole run | Wrong with nothing said | In one line |
| --- | --- | --- | --- | --- | --- | --- |
| `qwen2.5:7b` (the default) | 4.7 GB | 5.6 GB, all on the card | 1.45 | none | 3 | The fewest silent mistakes of the local models, and the only one with every trade of the final set whole; saves fewer trades unchanged on the exam than `gemma4:12b`. |
| `gemma4:12b` | 8.0 GB | `ollama ps` showed 1.5 GB, which cannot be right for an 8 GB file; the card's memory in use rose by about 9.5 GB | 2.02 | none | 5 | No silent mistake on any tier of the exam, practice or hidden, and the most trades saved unchanged; but 5 fields wrong with nothing said on the final set, and the fewest changes done (13 of 17, and 2 of 4). |
| `qwen3.5:9b-q4_K_M` | 6.6 GB | 6.1 GB, all on the card | 1.96 | none | 6 | Close behind on the final set (21 of 22) and on changes; 5 silent mistakes on the exam's practice halves. |
| `qwen3:8b` | 5.2 GB | 7.5 GB, all on the card | 2.13 | none | 13 | Every change right, but 5 fields wrong with nothing said on the final set and 8 on the exam. |
| `qwen3.5:4b-q4_K_M` | 3.3 GB | 3.7 GB, all on the card | 1.37 | none | 15 | The smallest and fastest, but saved almost nothing unchanged on the two harder tiers of the exam (0% and 7.7%). |
| `qwen2.5:14b` | 9.0 GB | 11 GB, all on the card | 2.70 | none | 16 | Twice the size of the default and no better: 14 silent mistakes on the exam's practice halves. |
| `deepseek-flash` (cloud) | none | none | 2.34 | 0.18 CNY | 6 | No silent mistake on the exam, but 6 fields wrong with nothing said on the final set. |
| `deepseek-v4-pro` (cloud) | none | none | 3.78 | 0.70 CNY | 3 | The best of the eight overall: 3 silent mistakes, 2 on one practice tier and 1 on the final set; 21 of 22 on the final set, every change right, no silent mistake on any hidden tier. |

The cloud costs are the change in the DeepSeek balance over the whole run
of 183 sentences, retries included, at off-peak hours; DeepSeek charges
more at peak hours. That price list was read from DeepSeek's own pricing
page on 2026-11-27, and which column, peak or off-peak, applied to these
runs was not checked item by item; what was spent is taken from the
balance before and after (`scripts/cloud_balance.py`). Read right after
both runs, the balance had dropped by 0.88 CNY in all; read again a while
later, it was 0.18 CNY lower still. The balance shows charges a few
minutes late, so this was most likely a charge for the same runs arriving
late, though that is a guess; it may have been spent elsewhere with the
same key. Thinking was turned off for every model that can
think (`LEDGER_HAND_MODEL_THINK=off` on this machine; DeepSeek's plug turns
it off always). The program's default for that setting, `model`, leaves it
to each model; with it, `gemma4:12b`, `qwen3:8b` and both `qwen3.5` models
think by default, and were not measured that way.

## On a Mac with 16 GB of memory

Not measured on a Mac. Which models are candidates is worked out from this
machine: those that fitted on the card entirely and showed 10 GB or less.
That is `qwen2.5:7b`, `qwen3:8b`, `qwen3.5:9b-q4_K_M` and
`qwen3.5:4b-q4_K_M`, and `gemma4:12b` by the card's memory (about 9.5 GB,
close to the line) rather than by `ollama ps`. `qwen2.5:14b`, at 11 GB, may
not fit entirely on such a Mac. The seconds a sentence on a Mac are not
measured; once one or two of these are picked, ten sentences on the Mac
will say.

**On a 16 GB Mac, keep `qwen2.5:7b`.** Of the candidates it makes the
fewest mistakes that nothing points out, and the final set, which runs
through the Record page, is whole with it; it is also the smallest of them
but one. If the Assistant page matters most, `gemma4:12b` is the one to try
next: it made no silent mistake on the exam said the owner's way, but five
on the final set, and it is close to the memory line. One weakness of the
default shows on the hidden halves, which are not used to rank: on the
tier said the owner's way, `qwen2.5:7b` had 2 trades with a wrong figure
and no mark, where `gemma4:12b` and both DeepSeek models had none
(`evals/RESULTS.md`, the totals of "2026-11-27: eight models on the same
rulers").

**If privacy does not matter and the best results do, use
`deepseek-v4-pro`.** It made as few silent mistakes as the default,
saved more trades unchanged on every tier of the exam and did every
change right, though one trade fewer of the final set came out whole, for
about 0.70 CNY a whole run; what is
typed, and what the assistant looks up in the ledger, is then sent to
DeepSeek.

These are recommendations from one comparison, not a change: the default
stays `qwen2.5:7b` until it is decided otherwise.

## How the ranking was made

Models are ranked first by the practice halves and the other rulers, by
the mistakes nothing points out, then by the share saved unchanged, then
by speed and cost. The hidden halves of the exam were run once for each
model and only their totals read; they are shown beside the others in
`evals/RESULTS.md`, to confirm, not to rank, so that they stay as close to
unseen as they can.
