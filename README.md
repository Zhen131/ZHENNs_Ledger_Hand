# Ledger Hand

## What this is

Ledger Hand is a small program that runs on your own machine and has one
chat box. You type a trade the way you would say it, in Chinese, English or
both, for example "bought 0.02 BTC at 94,900 at 9:40, fee 2 USDT", and it
works out the coin, the side, the quantity, the price, the total, the fee
and the time, and asks about whatever is missing instead of guessing. It
shows the result in a preview table, saves only when you press Save, and
exports a JSON file in the import format of the Local-First Trading Ledger.
A passage that mentions several trades gives one entry per trade. A
screenshot of an order can be uploaded instead: a model that can see
pictures reads the order on it out as text, which you check and can change,
add a note to if you like, and send on the way a typed passage goes. The
language model runs on this machine by default, so nothing typed leaves it;
a cloud service can be chosen instead (see "Switching to a cloud model").
The Record page never writes into the ledger application itself; it only
hands over a file. A third page, Assistant, is a chat that records, asks
about, changes and deletes trades through the ledger's tools (see "The
assistant page"). It only proposes: a proposal waits in the ledger until
it is confirmed there, and once the real ledger is connected that is done
on the ledger's own page. The real ledger is not connected yet: today the
assistant reaches a demo ledger, an invented book in memory, and
confirming is tried with `scripts/try_assistant.py --save` or with the
demo buttons on the Assistant page, which work on the demo ledger alone.

**Do not import an export file into the ledger yet.** The ledger's present
import replaces the whole ledger with what the file holds, which would leave
it with only the few trades in the file. The file's name says
`incremental`, and the interface says the same beside Export.

`docs/project-report.md` describes the project for a reader new to it: the
problem, the steps a passage goes through, the prompt techniques, the
parameters and why, the error handling, the experiments and their results,
the design decisions, the known limitations, and the course's checklist
mapped onto the repository. `docs/architecture.md` says how the code is
divided; `docs/known-gaps.md` lists the known limits.

## Where it stands

What the program does today, each part with its tests, and, last, what it
does not do yet:

- **Recording.** A passage typed in the interface or at the command line is
  judged (does it report a trade the ledger records?), its trades are
  extracted and checked, and whatever is missing is asked about, one
  question at a time, until every trade is a record, is left out, or cannot
  be recorded and why.
- **Keeping and exporting.** Save keeps the records in the book, a SQLite
  file of this program's own. Export writes the trades not exported yet
  into a new file in the ledger's backup format (backup format 3, ledger
  schema 5); the ledger tier of the checks has the ledger's own validator
  judge such files.
- **The model.** `qwen2.5:7b` through Ollama on this machine by default; a
  cloud service through its OpenAI-style chat endpoint when chosen. Every
  parameter is a setting with a default and the reason for it. Two local
  models have been measured side by side, `qwen2.5:7b` and `qwen3-vl:8b`
  (`evals/RESULTS.md`, "2026-10-13: second model, `qwen2.5:7b` and
  `qwen3-vl:8b`"); the default is still `qwen2.5:7b`. Another model is
  chosen with `LEDGER_HAND_MODEL_NAME`, or in the model field of the
  Settings page (for that browser tab only), and in an experiment with
  `--model`. `qwen3-vl:8b` has run the debug, final and voice sets through
  the experiment runner: with the settings' defaults most of its replies
  came back empty, and with thinking off every one on the debug and the
  voice set (see "Measured" below). So recording with it has not been shown
  to work; it is the model that reads a screenshot.
- **Measured.** On the 30 debug sentences the extraction prompt `first`
  gets 31 of 34 trades whole, and on the 20 sentences kept back for the end
  22 of 22; the versions of the first prompt experiment, each one technique
  away from it, and a second way of reading a passage did not beat it
  (`evals/RESULTS.md`). The product uses `first`, and reads
  a passage in one call. Under the same prompt and parameters `qwen3-vl:8b`
  got 3 of 34 and 5 of 22, most of its replies coming back empty, and on
  the ten passages of the voice set `qwen2.5:7b` got 1 of 10 trades whole
  and `qwen3-vl:8b` 0 of 10. Two more versions written after those errors,
  `second` and `third`, got 6 of 10 and 2 of 10 on the voice set, and 29 and
  30 of 34 on the debug set, against 31 for `first` in the same experiment;
  the rule fixed beforehand picked neither, so the final set was not run for
  them and the product still uses `first` (`evals/RESULTS.md`, "2026-10-18:
  prompt experiment three, more examples for the owner's way of writing,
  `qwen2.5:7b`"). One more, `fourth`, written after the errors of `first`,
  `second` and `third` on those sets, got 8 of 10 on the voice set and 33 of
  34 on the debug set, and the rule picked it; on the final set it got 18 of
  22 against 22 for `first`, so it did not pass, and the product still uses
  `first` (`evals/RESULTS.md`, "2026-10-19: prompt experiment four, new
  examples with English passages and Chinese numbers, `qwen2.5:7b`"). With
  thinking off, `qwen3-vl:8b` got 0 of 34 on the debug set, every reply
  empty, against 3 of 34 with nothing sent, so the plug still sends nothing
  about thinking by default (`evals/RESULTS.md`, "2026-10-19: the thinking
  switch, `qwen3-vl:8b`").
- **Screenshots.** A screenshot of an order can be uploaded on the Record
  page (see "Recording from a screenshot"), or tried with
  `scripts/try_screenshot.py` (see "Trying a screenshot by hand"): a model
  that can see pictures (`qwen3-vl:8b` by default) reads the order on it out
  as text, which on the page the person checks and can change; the note
  typed beside it is put after that text, and the passage they make is
  extracted with the default model, as a typed one is. No real screenshot
  has been tried yet, not even by hand (see `docs/known-gaps.md`, "Reading a
  screenshot: no guard that the model only copies").
- **The thinking setting.** The local plug can ask the model to think before
  it answers, or not (`LEDGER_HAND_MODEL_THINK`); by default it sends
  nothing, and each model does as its own default says. With thinking off,
  `qwen3-vl:8b` gave an empty reply on every sentence of the debug and the
  voice set (`evals/RESULTS.md`, "2026-10-19: the thinking switch,
  `qwen3-vl:8b`").
- **The assistant.** The Assistant page and `scripts/try_assistant.py`
  hand the model eight tools: it picks one, and the program judges the
  call, asks the ledger, lays out the tables, records through the same
  recording flow and finds the trade to change. It records a trade
  (shares priced in US dollars among them), answers four kinds of
  question, changes or deletes one trade, and records a screenshot's text;
  every proposal waits in the ledger to be confirmed. Behind it is the
  demo ledger, never the real one. Measured with `qwen2.5:7b` at the latest
  runs: the first step right on 19 of 19 sentences, 23 of 27 questions
  looked up right, 13 of 17 changes and deletions done right with none
  done wrong, and 16 of 18 sentences recording a share done right with
  none recorded wrong (see "Sentences for a demo" and
  `docs/project-report.md`, section 6).
- **Not done yet.** Measuring how well real screenshots are read: none has
  been read yet. Connecting the assistant to the real ledger's tools: it
  reaches the demo ledger only. Tuning the assistant on sentences the
  owner says in their own way, and judging on them whether it picks the
  right kind of work for 95% of new sentences: those sentences have not
  been written, so that line is not measured. Known limits are in
  `docs/known-gaps.md`.

How each part works is described in "How it works, part by part" below.

## Setting up from scratch

You need Python 3.12 or newer and Git. The commands below are for macOS or
Linux and are run from the top of a Git checkout of this repository. (A plain
copy without its `.git` directory is not enough: the hygiene scan asks Git
which files to look at.)

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install --no-deps -e .
```

With a newer Python, use its own name, such as `python3.13`, in the first
command.

The second command installs the pinned run-time dependencies (httpx,
Streamlit and tzlocal, with what Streamlit brings with it) and the
development tools. The third installs this package in editable mode, so the
tests import the code in `src/` directly. Both need network access; the third also fetches the build backend
(setuptools) into a temporary build environment.

Then confirm that everything works:

```sh
scripts/check.sh
```

The last line should read `quick: all checks passed`.

The quick checks need no model. The interface, the command-line scripts,
the live tier and the experiments do: by default Ollama running on this
machine with the model `qwen2.5:7b`. Install Ollama, fetch the model once
with `ollama pull qwen2.5:7b`, and leave Ollama running; it answers at
`http://127.0.0.1:11434`, the default address. Reading a screenshot, on the
Record page or with `scripts/try_screenshot.py`, and the live tier also
need `qwen3-vl:8b`, the model that reads a screenshot, which is also the
second model that has been measured: fetch it the same way,
`ollama pull qwen3-vl:8b`. To use a cloud service instead, see "Switching
to a cloud model".

## Starting the interface

You need the model server running first: by default Ollama on this machine
with `qwen2.5:7b`, and, to record from a screenshot, `qwen3-vl:8b`, the
model that reads it (see "Setting up from scratch" and "Model settings").
Then, from the top of the repository:

```sh
.venv/bin/streamlit run src/ledger_hand/ui/app.py
```

and open http://127.0.0.1:8501 in your browser yourself: the terminal
prints the address and asks nothing. Start it from the top of the
repository: Streamlit reads its settings from `.streamlit/config.toml` in
the folder it is started in. They keep it from sending usage statistics,
make it listen on this machine's own address only, and start it headless, so
it neither stops at the terminal to ask for an e-mail address nor writes a
credentials file into your home folder, and it does not open a browser by
itself. It may suggest installing the Watchdog module, which only helps
Streamlit notice changes to the code; the program does not need it. Stop it
with Ctrl+C in the terminal.

Type a passage in the box under the chat, for example "Bought 0.02 BTC at
94,900 yesterday". The program's questions come back in the chat, each with
a label saying which trade and which field it is about; type the answer in
the same box, or "skip" to leave that trade out, or "cancel" to drop the
whole passage. The table on the right shows every trade as it stands, with
the price and the total side by side, so a total written where the price
belongs shows at a glance; an amount the program worked out is marked `*`.
Once every trade is settled, "Don't save" leaves one trade out, "Discard
all" drops the passage, and Save keeps the rest in the book and says how
many it saved. Save cannot be pressed while a question is waiting; the
sentence beside it says why.

The current moment is the machine's clock and the time zone is the
machine's own, read with tzlocal; a zone name the program does not take as
it stands, or a model setting it refuses, is said on the page instead of
the chat. The chat lasts as long as the browser tab and is never written to
disk; only the trades saved are kept, in the book (see "Where the data is
kept"). When the model fails, the chat says so in one sentence and
nothing of that passage is kept; type it again once the model server is
running.

Two more things are said in the chat, as reminders that hold nothing back.
When the same passage, or one that differs from it only in spacing or
full-width characters, was saved before, the chat says so first, with the
day of each earlier save and how many trades it saved; the passage can
still be answered and saved. When a trade's fee is paid in a third coin,
neither USDT nor the coin traded (buying ETH with the fee taken in BNB,
say), its fee coin is marked "(not in cost)" in the table, a sentence under
the table says why, and the chat says it once every trade is settled: the
ledger takes the trade, but leaves that fee out when it works out the cost.

### Recording from a screenshot

Under the chat, "Or record from a screenshot of an order" takes one PNG or
JPEG file at a time. The program first checks, without asking anything of
anyone, that the plug is local (the cloud plug sends no pictures), that the
file is no larger than `LEDGER_HAND_MODEL_SCREENSHOT_MAX_MB` (20 MB by
default), and that it is a PNG or a JPEG by what it holds, whatever its
name. Then it asks the model server whether it has the vision model
(`LEDGER_HAND_MODEL_VISION_NAME`, `qwen3-vl:8b` by default), and only then
sends the picture: the vision model reads the order on it out as text,
which can take a minute.

The text read appears in a box that can be changed, beside an empty box for
a note: what the screen leaves out, such as a fee or the platform, or why
you traded. Check the text, put right what is wrong, add a note if you
like, and press Continue: the two are joined into one passage, the text
first, which is shown in the chat as yours and goes on exactly as a typed
passage does, with its questions, the table and Save. "Drop the screenshot"
drops what was read, and nothing is sent. While a screenshot read waits,
the upload box is greyed out, and a message typed in the chat is not taken:
the chat says to press Continue or Drop first. While a passage is being
recorded, the upload box is greyed out too. The two boxes keep what is in
them while the Settings page is shown, and are empty again for the next
screenshot. When a screenshot cannot be used, or nothing could be read off
it, the chat says why in one sentence (see "What the page says when
something fails"), nothing of it is kept, and the same file can be uploaded
again.

With the longest reply at its default, 1,024 tokens, the vision model read
nothing off a clear, invented picture of an order; at 4,096 it read it.
That was one picture, tried once, and does not promise that every
screenshot is read. Before recording from a screenshot, on this page or on
the Assistant page, try setting `LEDGER_HAND_MODEL_MAX_REPLY_TOKENS` to
4096 on the Settings page (see
`docs/known-gaps.md`, "A screenshot may need a longer reply to be read").

The browser offers every kind of file, and the upload box shows
Streamlit's own limit of 200 MB per file; the program's checks, of what the
file holds and of its own limit, are the ones that answer. The picture is
never written to disk, and nothing of it is kept once it is read, but
Streamlit keeps the uploaded file in memory until the browser tab is
closed: the page empties the upload box by drawing a new one, which does
not let go of it (see `docs/known-gaps.md`).

### Exporting from the interface

Export, under the table, writes the saved trades not exported yet into a new
file in the exports folder, the same file `record_trades.py --export`
writes, and marks them as exported. The page then says where the file is
and how many trades it holds; with nothing new it says so and writes
nothing. When the trades cannot be written as a file as they are, it gives
every reason, one to a line; when the file cannot be written, it says why;
in both cases nothing is marked. When the file was written but its trades
could not be marked, it says where the file is and that the next export
writes them again.

Beside the button, always, a line in red says not to import this file into
the ledger yet: the ledger's import replaces the whole ledger with what the
file holds, which would leave it with these trades only.

### The settings page

Settings, at the top of the page beside Record, says first which plug
talks to the model now (local or cloud), at which address, and whether
there is a key. Then it lists every model setting (see "Model settings")
with its value now, its default, what it sets and why its default is what
it is; the key only says whether there is one.
Every setting but the key can be changed there: type the new value, as it
would be written in the environment, and press Apply. A blank value takes
the default. The values are read and checked exactly as the environment's
are; a value that is refused is named with its rule, and nothing changes.
So is a switch to the cloud plug whose address or key do not fit it (see
"Switching to a cloud model"); the key itself can only be set in the
environment. Once applied, the next call to the model uses it, even in the
middle of a passage. "Back to the environment and the defaults" drops every
change.

A change lasts for the browser tab only: opening the page again, or
starting the program again, goes back to the environment variables and the
defaults. Nothing is written to a file or to the environment, and what the
page does not change, the key among it, stays as the environment set it.
The data folder is shown there too, and is changed only with
`LEDGER_HAND_DATA_DIR` before the program starts. When a setting in the
environment is refused, the Record page says why and shows nothing else,
and the Settings page still opens, with the same sentence and every
setting's default and why.

### The assistant page

The third page, Assistant, at the top beside Record and Settings, is a chat
with the assistant (see "Trying the assistant by hand" for what it does).
A line at the top always says which ledger it reaches: the demo ledger,
an invented book in memory (the demo book; see "The demo book" below),
which every new tab reaches first; or your own ledger page, in a coloured
box that cannot be taken for the demo's, once you choose it in the block
under that line (see "Connecting the assistant to your ledger"). Type a
sentence in the box under the chat: ask about your trades ("我现在持有什么",
"10月6号我买了什么"), record one ("今天15:30在IBKR买了2股MSFT，410美元一股，
手续费1美元") or change or delete one ("把10月6号那笔的手续费改成0.000009").

It does four kinds of thing, in Chinese or English; an English sentence
for each, from "Sentences for a demo" below:

- record a trade: "Bought 2 MSFT at 410 USD each on IBKR on 18 November
  2026 at 15:30, fee 1 USD.";
- ask about the ledger: "Which coins and shares am I holding at the
  moment?";
- change or delete one trade: "Delete the MSFT sell on 12 November 2026.";
- record from a screenshot of an order, uploaded under the chat (below).

It does not place orders, give advice on buying or selling, or forecast a
price; asked to, the model answers in words and nothing is sent. It records no
exchange of one money for another ("用美元买了500 USDT", "bought 500 USDT
with dollars"): that is left to
the ledger. It answers with the model `LEDGER_HAND_MODEL_NAME` names
(`qwen2.5:7b` by default), changed in the model field of the Settings
page for the browser tab, or in the environment before the program
starts; it runs on the local plug only.

What you typed is shown as you typed it. When the program tidied it first
(number words and a time said in Chinese written in digits; see "Trying
the assistant by hand"), a small line under your words, in the same
bubble, says what it read them as: "Read as: 2026年11月20号下午14点12分买了
0.005个BTC". Nothing is shown when nothing was changed.

Under each reply the page shows who wrote it (the model, the program's own
words, or the recording's question), any failure in one plain sentence, the
tables the program lays out (what the ledger found, under the days, the
asset and the side it was looked up with; the trades sent, each figure
written in full with thousands marks and the money it is in; a change
before and after, the parts that change marked), and one line saying what
reached the ledger, or that nothing did. "How this was done", closed until
opened, lists each step of the model: the tool it asked for and with what,
what was handed back or why it was a wrong step, whether the program took
over, and how many times the model was asked. While a question waits, the
answers it offers (a question's choices, each listed trade's number, which
amount follows) are buttons under the latest reply; pressing one says that
answer, as if typed.

On the right, one card for each proposal sent in this chat says where it
stands. With the demo ledger it is asked each time the page is drawn, and
Refresh asks again. With your ledger page, a proposal is confirmed on the
ledger's own page, and a card is asked only when you press "Check with the
ledger" on it (see "Connecting the assistant to your ledger"). When the
ledger took some trades of one message and turned others down, the table
of the trades sent says, for each, whether it waits in the ledger or was
not taken, and why. With the demo ledger, and
only then, each waiting card also has "Save in the demo
ledger" and "Reject in the demo ledger", which do there what you would do
on the ledger's page, so the whole path can be tried. New chat forgets the
chat and its cards; a question left unanswered is dropped. The chat lasts
as long as the browser tab; the demo ledger is kept when a setting is
changed. What was said is kept on disk in one place only, the assistant's
record (below).

A screenshot can be uploaded under the chat, as on the Record page: the
text read waits in a box to be checked and changed, beside a note, and
Continue records the two exactly as the same words typed, without asking
the model that chooses tools. The two pages keep their screenshots apart.
The upload box is greyed out while a question waits. The assistant runs
on the local plug only: with the cloud plug set, the page says so in one
sentence and greys the input out. When `LEDGER_HAND_ASSISTANT_STEPS` is
refused, the page says why and greys out both the input and the upload
box, so no screenshot is read for nothing.

### Connecting the assistant to your ledger

The Assistant page can reach your own ledger, the Local-First Trading
Ledger, through its assistant link: a small Node.js program in the
ledger's folder that passes the assistant's questions and proposals to the
ledger page you have open, and nothing else. The assistant only looks
things up and proposes; nothing is written to your ledger until you press
Save in the ledger page's pending list.

What you need:

- the ledger's folder, at its `dev` version (this was walked through
  against `dev@a6ba639`), with its programs installed: run `npm install`
  in that folder once, and again whenever the ledger adds a package (when
  one is missing, the page says so and names this command);
- Node.js 24 or later, which the ledger asks for;
- `LEDGER_HAND_LEDGER_DIR` set to that folder before this program starts.

The ports have defaults the ledger shares, and are read only from the
environment, never from the Settings page, since the whole program runs
one link:

| Variable | Default | What it sets |
| --- | --- | --- |
| `LEDGER_HAND_LEDGER_DIR` | (none) | The ledger's folder, where the link is started. |
| `LEDGER_HAND_LEDGER_LINK_PORT` | `47651` | The port of this computer the link listens on. |
| `LEDGER_HAND_LEDGER_PAGE_PORT` | `3000` | The port the ledger page is opened on; the link takes pages from there only. |
| `LEDGER_HAND_ASSISTANT_LEDGER` | `demo` | Which ledger a new tab of the Assistant page reaches first: `demo` or `page`. The demo ledger is the default because the checks, the measured results and the sentences for a demo all run against it. |

On the Assistant page, choose "Your ledger page" in the block at the top
(the choice takes at once; the tab's chat is cleared, and says why, since
the two ledgers number their trades and proposals apart), then press
Start. The block shows the port and three steps:

1. Open the ledger page (http://127.0.0.1:3000 by default) and open your
   ledger.
2. Press "Connect assistant" on the ledger page.
3. Enter the port, and paste the token: press "Show token" to see it.

The block says where the link stands, read each time the page is drawn
(Refresh reads it again): not started; waiting for your ledger page;
connected; your ledger page disconnected (disconnected there, closed or
reloaded: connect it again); the link stopped by itself. Stop stops the
link for every tab of this program, which then says so; Start starts a new
one. While the ledger page is not connected, what you type is answered by
the page itself, that it is not connected and how to connect, without
asking the model, and the screenshot box is greyed out.

The token's rules, which are the ledger's: a new token each time the link
starts; you paste it yourself each time, and press Connect yourself; it is
never remembered, and nothing connects by itself. Here it is drawn only
after "Show token" is pressed, as text you can copy, and not drawn at all
after "Hide token". It is kept nowhere: not in the chat, the assistant's
record, a log, a failure's words, anything handed to the model, or the
page's address.

With your ledger page, each card says its proposals were sent to the
pending list there and wait for you to press Save. Press "Check with the
ledger" on a card to ask where each stands: still waiting; saved; rejected;
void, with the ledger's words; void because the ledger page disconnected
(the ledger lets go of every waiting proposal then; that is not a
rejection: say it again to send it again); the ledger page not connected
(connect it first); or, after the ledger page was reloaded, that its result
can no longer be looked up, which does not mean it was not saved: look at
the ledger. Drawing the page asks nothing, since a ledger page left in the
background can take most of a minute to answer.

When it does not connect, the block says why in one sentence: no
`LEDGER_HAND_LEDGER_DIR`, Node.js missing or too old, the folder not the
ledger's or its packages not all installed, or the port already used by
another program (perhaps a second copy of this one). When this program
stops, the link stops with it. Each entry of the assistant's record says
which kind of ledger it was said to, never the port or the token.

### The assistant's record on this computer

Each time the assistant has dealt with one thing said (typed, an answer,
or a screenshot's text), the program adds one line to
`assistant-record.jsonl` in the data folder (see "Where the data is
kept"). Started from the top of the repository, as this README does, that
is the repository's own `data/` folder, which Git ignores. Each line is
one entry of JSON, with its own version number, holding: when, what you
said (for a screenshot, the text and note you continued with; the picture
itself is never kept), what the program read it as once tidied, with each
change ("read_as", empty when nothing was changed), which way it went, who wrote the reply, each tool
the model asked for with its arguments, a short piece of what the ledger
handed back and any failure codes, the trades proposed with their amounts
and money, each trade not sent and why, the kinds of reminder said, the
proposals sent and how they stood, and the model and prompt versions
used. The most recent 1,000 entries are kept; older ones are dropped.
The record is now at version 3: version 3 added "read_as". Entries of
versions 1 and 2, written before, are still read as they are, and a file
may hold all three.

**The file is plain text, not encrypted: it holds what you said to the
assistant, word for word, with its numbers.** It stays on this computer;
it is not in Git and not in the book of the Record page. Keep it out of
anything shared.

The Settings page shows, under the data folder, which file it is, says
that it is plain text with your words in it, and how many entries it
holds. "Clear the assistant's record" asks first; "Yes, delete the
record" deletes the file, and "Keep it" leaves it. A record written by a
newer version of the program, or with a line that cannot be read, is
never changed or deleted by the program: nothing more is added to it, the
Assistant page says so under each reply (what was said is still done),
and the Settings page says why it cannot be read; it can still be cleared
there, by your own two presses. Only a last line cut off half-way (the
program stopped while writing it) is passed over, and cut off before the
next entry. When the file cannot be written, the reply is still done and
the page says it was not kept.

### What the page says when something fails

Each failure is said in one plain sentence: what happened, and what can be
done. The page never breaks, and nothing is recorded, saved or marked by
the step that failed.

| What failed | What the page says |
| --- | --- |
| No model answered | The address asked; whether Ollama is running; the address on the Settings page |
| The model took too long | The time allowed; the first call has to load the model and can be slow; try again, or allow more time on the Settings page |
| The model is not there | The model's name and the address. With the local plug: check the name, or install it with `ollama pull`. With the cloud plug: check the name on the Settings page against the service's own list of models |
| Called too often | The server turned the call away; wait a little, then try again. When the server said how long to wait: that many seconds |
| The key refused (status 401 or 403) | The address; check `LEDGER_HAND_MODEL_KEY` in the environment and that the key may use the model, then start the program again |
| The request refused (status 400) | The address and the start of what the server answered; check the model's name; a service that does not take the reply table refuses every call this way |
| The server failed | Its status code, when it gave one; try again, or look at the server's own log |
| A reply not in the agreed form | The reply could not be used; try again, or put the passage another way |
| Replies that cannot be read as a table | The same, said apart |
| An empty passage | Nothing was sent to the model: the passage is empty |
| A passage too long | The limit, 16,384 characters; split it into shorter passages |
| A passage that is not valid text | Type it again, or paste it from somewhere else |
| A setting in the environment refused | Which one and its rule; correct or remove it, then start the program again |
| A change on the settings page refused | Which one and its rule; the settings were not changed |
| The book written by a newer version, not a database, or not this program's book | Which file; for a newer version, that this program does not touch it; for a file that is not a database, that it was left as it is; for a database that is not this program's book, that this program does not use it; use the newer version, move the file away, or point `LEDGER_HAND_DATA_DIR` elsewhere |
| The book damaged | Which file, and that the program does not write to it; keep a copy and move it away, or point `LEDGER_HAND_DATA_DIR` elsewhere |
| The book in use, unreadable or unwritable, clashing with what was asked, or failing otherwise | Why, in the book's own words; what to check, then try again |
| An export refused | Every reason, one to a line; nothing was marked |
| An export file not written | Why; nothing was marked; press Export again once that is put right |
| An export file written but not marked | Where it is; the next export writes the trades again |
| A screenshot with the cloud plug | The cloud plug sends no pictures, so nothing was sent; typing works as before; set `LEDGER_HAND_MODEL_PLUG` to local on the Settings page |
| A screenshot too large | Its size and the limit, in MB; nothing was sent; take a smaller one, or raise `LEDGER_HAND_MODEL_SCREENSHOT_MAX_MB` on the Settings page |
| A file that is neither a PNG nor a JPEG | Judged by what it holds, not by its name; nothing was sent; save it as one of the two and try again, or type the trade |
| The vision model is not there | Its name and the address; it reads screenshots, it is not the model that extracts; check `LEDGER_HAND_MODEL_VISION_NAME`, or install it with `ollama pull` |
| The server cannot be asked for the vision model | That it could not be asked and the picture was not sent, then the sentence for that kind of failure, with the vision model's name |
| The vision model fails while reading | That it gave no usable reply, then the sentence for that kind of failure, with the vision model's name; a request turned down with status 400 says to check that the model can see pictures, and a reply not in the agreed form says to try again |
| The vision model reads nothing | Check that it is a screenshot of an order and try again; or raise `LEDGER_HAND_MODEL_MAX_REPLY_TOKENS`, or set `LEDGER_HAND_MODEL_THINK` to off |
| A reading cut off at the longest reply | It was not used; raise `LEDGER_HAND_MODEL_MAX_REPLY_TOKENS`, or set `LEDGER_HAND_MODEL_THINK` to off, then try again |

The sentences are in `src/ledger_hand/ui/failure_words.py`, one for each
kind of each failure, one for each status a cloud service turns a call
down with (401, 403, 400), and one for a model the cloud service does not
have, which says nothing of Ollama; and one for each way a screenshot is
not read, where a model's failure is said with the vision model's name, and,
while reading, a request turned down with status 400 or a reply not in the
agreed form has a sentence of its own, since nothing there is about a reply
table or a passage. A test walks every kind, so a new one cannot go without a
sentence. None of them ever shows the key. When SQLite first rolled back a
write to the book that had been cut off part way, a refusal can still use
the sentence that says the file was not touched, or was left as it is,
though the rollback wrote to it; the book's own message, after the
sentence, says so (see `docs/known-gaps.md`, "The book after a write was cut
off").

When the model fails while it reads an answer to a question, the page says
that kind of failure in its own sentence, looked up the same way, and asks
the question again. That sentence goes by the kind alone, not by the status
code or the wait the server asked for, so a refused key, a refused request
or a rate limit with its wait is said in the kind's general sentence there.
The command line (`scripts/record_trades.py`) still prints the reason with
the kind's code word, such as `(asked again: the model could not be asked
to read the answer (timed_out))`.

## Recording at the command line

The recording, saving and exporting the interface does can also be run at
the command line, with `scripts/record_trades.py`; `scripts/try_extraction.py`
runs extraction alone, and `scripts/try_screenshot.py` reads a screenshot
and extracts the passage it gives. They ask the models the settings name, so
the model server has to be running, and they are run from the top of the
repository.
`.venv/bin/python scripts/record_trades.py --help` lists its options.
`scripts/try_extraction.py` has no options: everything after its name is
the passage, except `--help` or `-h` given alone, which prints how to use
it (giving a passage, standard input, the exit statuses) and reads nothing
else.

### Trying extraction by hand

```sh
.venv/bin/python scripts/try_extraction.py "9:40 bought 0.02 BTC at 94,900, fee 2 USDT"
echo "昨天卖了 2 ETH，价格 3,420" | .venv/bin/python scripts/try_extraction.py
```

The passage is the arguments, or else standard input. The script sends it
to the model the settings name and prints every draft field by field, the
issues, and one line per call to the model with how long it took and how
many tokens it read and wrote. The current moment is the machine's clock and
the time zone is the machine's own, read with tzlocal; a zone name the
program does not take as it stands stops the script instead of being
replaced. Nothing is written to disk. Exit status: `0` the passage was read
(even with no trade in it), `1` it was not (refused, no readable reply, or
the model failed), `2` the script could not start (a setting or the zone).

### Trying a screenshot by hand

```sh
.venv/bin/python scripts/try_screenshot.py path/to/order.png
.venv/bin/python scripts/try_screenshot.py path/to/order.jpg --note "fee 0.1 USDT, bought on OKX"
.venv/bin/python scripts/try_screenshot.py --help
```

The picture is a PNG or JPEG file, told apart by its first bytes. The
vision model the settings name (`LEDGER_HAND_MODEL_VISION_NAME`, by default
`qwen3-vl:8b`) is shown it with the reading prompt `read-1`
(`src/ledger_hand/extraction/prompts/read.py`) and reads the order on it out
as text: each value with the label the screen gives it, as it stands. The
script prints that text, then the note, if one is given with `--note`, then
the passage the two are joined into (the text read, an empty line, the
note), and extracts the passage as `scripts/try_extraction.py` does, with
the model `LEDGER_HAND_MODEL_NAME` names and the product's prompt, printing
the drafts, the issues and one line per call; the call that read the picture
has its line last. The two models take turns in memory, so loading one
shows in the time of its call. Pictures are read through the local plug
only: settings that choose the cloud plug stop the script before anything is
sent. Only the one file is read; nothing is written to disk, and the picture,
the text read and the passage are not kept. `--help` or `-h` alone prints how
to use it and reads nothing else. Exit status: `0` the picture was read and
its passage extracted (even with no trade in it), `1` the picture was not
read (the model failed, or the reading was cut off at the longest reply) or
its passage was not extracted, `2` the script could not start (the
arguments, a file that cannot be read or is neither PNG nor JPEG, a setting,
the cloud plug, or the zone).

### Trying the assistant by hand

```sh
.venv/bin/python scripts/try_assistant.py "我现在手里有哪些币"
.venv/bin/python scripts/try_assistant.py "我10月一共买了多少钱的币" "那9月呢"
.venv/bin/python scripts/try_assistant.py "What do I hold?" "Which assets are there?"
.venv/bin/python scripts/try_assistant.py "今天上午9:40在币安买了0.02 BTC，价格94900" "手续费 0.1 USDT"
.venv/bin/python scripts/try_assistant.py --save "Bought 0.02 BTC at 94900 on Binance at 9:40 this morning, fee 2 USDT."
.venv/bin/python scripts/try_assistant.py --save "把9月25号那笔ADA的平台改成Binance"
.venv/bin/python scripts/try_assistant.py "把10月6号那笔的手续费改成0.000009" "第二笔"
.venv/bin/python scripts/try_assistant.py "把10月6号那笔BTC的数量改成0.0081" "总额"
.venv/bin/python scripts/try_assistant.py --clock "What do I hold?"
.venv/bin/python scripts/try_assistant.py --help
```

The assistant is the beginning of a way to keep the ledger by talking: the
model is handed eight tools (list the assets, list the trades, sum a
stretch of time, the holdings, propose to record, change or delete trades,
and where a proposal stands) and decides which to ask for; the program
judges every call before it runs it and stops the model after two wrong
steps in a row or `LEDGER_HAND_ASSISTANT_STEPS` asks (six by default). Each
argument is the user's own words copied or a choice from a list, never a
number or date the model writes. Behind the tools is the fake ledger, an
invented book kept in memory, never the real ledger. All eight are
connected: asking the ledger, recording, changing or deleting one trade,
and where a proposal stands.

Asking is answered by the program, with the model's help in two places
only: it picks the tool, and it copies the words that say which time. Four
kinds of question can be answered:

- the trades ("10月6号那天我都做了什么交易", "What did I sell last month?"),
  each with its time, side, asset, quantity, price, total and money, fee and
  what it was taken in, and platform; a sell also with the profit or loss
  it made;
- the sums of a stretch of time ("我10月一共买了多少钱的币"): for each money
  the trades were priced in, what the buys spent, what the sells brought in
  and the profit or loss, never two moneys added together; the fees, one
  line for each asset they were taken in; and how many trades;
- what is held now ("我现在手里有哪些币"): quantity, cost, and the profit or
  loss on paper, or why it is not worked out;
- the assets the ledger knows.

The time is taken only from the model's copy of the user's own words; a
time the model writes in other words ("今年" for "this year") is a wrong
step, and the model is told to copy it again. With no time from the model,
the lookup covers all time. The program turns
the time words into days itself: "10月" is 2026-10-01 to
2026-10-31, "上周" the Monday to Sunday before this week, "最近7天" today
and the six days before. Words it cannot read, words with two meanings
("12月" said in November, which may be last December), and times wholly in
the future are not guessed at: nothing is looked up, and the program says
which words, and why. The asset and the side are used only when the user
named them; "比特币" and "BTC" are the same asset, "币" names none, and
"买卖" asks for both sides. A question asked on ("那ETH呢") keeps the asset
and the side of the one before when it names none. An asset the ledger does not have ("DOGE") is
said so. The program lays the table out itself, under a header that names
the days, the asset and the side it was looked up with; every figure is the
ledger's own. The model writes a sentence or two beside it; a number in
them that is not in the table is not shown, and the program's own words
take their place ("Here is what the ledger returned."). Questions none of
the four answers, such as how much the holdings grew between two days, what
a price will do or whether to sell, are answered with what the assistant
can do; an answer with no table may hold no figure like an amount.

A sentence said in Chinese number words is first tidied, before the model
sees it: number words become digits, a time said in Chinese is written
the way the program reads it, seconds are dropped, and the zone trades
are recorded in is dropped when it is said ("匈牙利时间"). Only how a
number or a time is written changes, never its value, and anything the
program cannot check is left as it was said. The line `read as:` shows
what the program read, just before the route. For example, with invented
figures:

```text
you said: 二六年十一月二十号下午十四点十二分三十一秒在币安买了零点零零五个BTC
read as: 2026年11月20号下午14点12分在币安买了0.005个BTC
```

The words as said still go to the ledger with each trade; the model and
the program's checks work on the words tidied. While a question waits,
the line `asked about:`, just before the ending, names what it asks about
(`time`, `fee`, and so on).

Cash cannot be asked about yet: none of the eight tools reads a cash
balance, a deposit or a withdrawal. A question about cash ("我还有多少USDT",
"现金余额是多少", "How much USD did I deposit?") is caught by the program
before the model is asked, and answered with the program's own words: the
assistant cannot look up cash yet, the ledger's home page shows the cash
balance, and no figure is worked out from the trades. No table is shown.
Under a table of holdings or of sums the page says it holds no cash
balance. What the catch knows and does not know is in
`docs/known-gaps.md`, "The assistant: cash".

Recording is the program's, not the model's. When the model asks to record
a trade, what the user said, tidied as above, is handed to the same recording
flow the Record page uses: it judges the words, extracts the trades and
asks for what is missing, such as the fee, one question at a time. The next
thing said is the answer ("skip" and "cancel" work as on the Record page).
Once every trade is settled, the trades go to the ledger as one proposal,
which waits there until it is saved or rejected on the ledger's own page;
nothing is confirmed in the assistant. Every figure is the recording flow's,
and the user's words go with each trade. A trade said only with its day, or
naming an asset the ledger does not have, is left out, with a sentence
saying why; an open order, or words with no trade in them, send nothing.

What can be recorded, and the money it is priced in, come from the
ledger's own list of assets, asked for once when recording begins: with a
share and US dollars in the ledger,
"今天15:30在IBKR买了2股MSFT，410美元一股，手续费1美元" sends one trade of
MSFT priced in USD, its fee taken in USD.
When the ledger prices trades in more than one money, a price said with no
money ("价格94900") is asked about first ("Which currency was this trade
priced in?"), and one money is never taken for another: "U" is USDT,
"美元" is the US dollar.

"美金", "刀", "美刀", "$" and "bucks" are vague: each may mean USDT or the
US dollar. Such a word follows the money the same trade names outright on
its own price, total or fee ("花了30美金买ETH，成交均价2400 USDT" is a trade in
USDT, asked nothing); what the rest of the words say ("账户里还剩500 USDT",
another trade) does not count. When the trade names neither, the money of
the asset's last trade in the ledger is taken, and the reply says it is a
guess ("Trade 1: no currency was said, so it is priced in USDT, the
currency of the last ETH trade in the ledger. This is a guess; check it
before you confirm."). When the ledger has no trade of the asset, cannot be
asked, or the asset's last day of trades used both moneys, the user is
asked. A word that names one money ("欧元", "EUR", "人民币", "福林") counts
only when the ledger has that money: "价格2200欧元" with no euro in the
ledger is not sent, and the reply says the ledger has no currency EUR yet.
An answer whose money is not the trade's ("2400美元" for a trade in USDT)
is not filled in: the user is asked which money it is. The words are two
lists in `core/ledger_table.py` (`MONEY_WORDS`, `VAGUE_MONEY_WORDS`); a
word is added there in one line. An asset the ledger lacks ("TSLA", or
"狗狗币" with no DOGE in it) is not sent, and the user is asked to add it in
the ledger first; money bought with money ("用美元买了500 USDT") is an
exchange, which the assistant leaves to the ledger. The Record page keeps
the built-in coins and USDT.

A share or a coin said by a name the ledger's list does not hold as it is
("微软", "微软的股票", "Coca Cola") is asked about today: "The ledger lists
no asset by that name; which asset was it?", with a note to answer with
the code ("MSFT") or to add the asset in the ledger first. A step that
hands such a name to the model to pick from the ledger's list is in the
code but off (`ASSISTANT_PICKS_ASSETS` in `flows/conversation.py`): on the
names set, every prompt version tried picked a listed asset for some name
the ledger lacks ("谷歌" as AAPL, "柚子币" as SOL), which would send a wrong
asset; see `evals/RESULTS.md`. Turned on, it works as follows. The model
is handed only the words and the ledger's list of the assets that can be
traded (each its code, name and kind), to pick one or none.
The program takes the code only when it is on the list, the words the
model picked out were said, and nothing is left around them but words
such as "的", "股票" or "公司": "以太坊经典" read as "以太坊" is not taken.
The reply would then say, when recording begins and once it ends, what
was taken and that the model matched it, for example `Took "微软" as MSFT
(Microsoft) from the ledger's list of assets. The model matched it, not
the program, so please check it before you confirm.` A name the model
does not pick, or whose pick the program does not take, is asked about as
above. With the ledger's own list, a question calls a share a share, a coin a coin, and an asset
not yet known an asset. A name that can be written as a code ("TSLA") is
never handed over, nor a coin the built-in table knows that the ledger
lacks ("狗狗币").
If the model goes wrong two steps in a row, the program hands the words
once to the recording flow and says what it found, an open order among
them; only words with no trade in them end with "please say it another
way".

Changing or deleting one trade is the program's too. The model only says
which trade, in the user's words ("9月25号", "ADA"), which part, and the new
value, as the user wrote it; the program finds the trade itself, every
time, and the model never picks one:

- "把9月25号那笔ADA的平台改成Binance": the book holds one ADA trade that day,
  so a change is proposed at once, and the program shows the trade before
  and after, side by side, the platform marked as changed. Nothing changes
  until the change is confirmed on the ledger's own page.
- "把10月6号那笔的手续费改成0.000009": two trades fall on that day, so the
  program lists them, numbered from 1 from the earliest, and asks which.
  "第二笔", "2", "the second one" or "最后一笔" answers; the trade is looked
  up again and its change proposed. "cancel" drops it.
- "把10月6号那笔BTC的数量改成0.0081": quantity times price would no longer
  be the total, so the program asks which follows: the total becomes
  501.714 USDT, or the price becomes 62704.69135802 USDT, each worked out
  by the ledger's rules. "总额", "price", "1" or "2" answers.
- "把10月7号那笔BTC删掉": no trade matches; the program says so, with the
  day, asset and side it looked for, and does not look more widely.
- "把那笔删掉", naming no day, asset or side, looks nothing up: the program
  asks which trade is meant.

The new value is read by the program: a number by the same rules as a
recorded one ("1.500", which may be one thousand five hundred, is not
taken); a time only with the day and the time of day ("9月24号20:37"); a
number with a unit only when the unit is what that part is in now ("0.3U"
for a fee taken in BTC changes nothing). A value the trade already has
changes nothing. One change or deletion is done at a time. Say the trade's
time in full ("9月13号那笔", not only "9月"): a time the model copies as only
part of what you said, such as the month of a day, is not looked up, and
you are asked to say it again with the date. The ledger
checks each proposal; one it turns down, such as deleting a buy that a later
sell rests on, waits nowhere, and the program gives the ledger's reason.

Each argument is one thing the user says, in order, in one chat. For each
the script prints which way it went (the model chose the tools, it was the
answer to a question waiting, or the program took over), then each step:
the tool asked for and its arguments, and what was handed back, why the
call was a wrong step (a copied argument that is not the user's words, such
as "BTC" when the user said "比特币", among them), or that it was not run
because its step went to recording. After a read tool it prints the
table, header first, as the program laid it out. When a trade was recorded, it prints
the recording's calls to the model and each trade sent, as the proposal
holds it. When recording begins it also prints one line for each name of
an asset handed to the model to pick from the ledger's list (none while
the step is off): `asset
picked: "微软的股票" -> MSFT (the model picked out "微软")`, or `asset not
picked: "特斯拉" (the model said the list does not hold it)`. A change or
a deletion prints its list, question or table in the program's words. Then one line, from the program, on what reached the ledger
(`sent to the ledger: proposal-1, 1 trade(s)`, `sent to the ledger:
proposal-1, change of t-06`, or `sent to the ledger: nothing`), who wrote the last words (`words by: the model`, or the program,
with the reason when the model's were not shown), the assistant's last
words and how it ended. `--save` or
`--reject`, before the sentences, saves or rejects every proposal still
pending once everything is said, and prints the book's count of trades
before and after, the trades added, and each trade changed (before and
after) or deleted. "Now" is the invented book's fixed
moment, 24 November 2026, 23:55 in Budapest, printed first; `--clock` takes
the machine's clock and zone instead. The assistant runs on the local plug
only: settings that choose the cloud plug stop the script before anything
is sent. Nothing is written to disk. Exit status: `0` everything said was
done or the user was told why not (an answer, a question waiting, a
proposal sent, or nothing sent with the reason), `1` something was not (a
model or ledger failure, the step limit, or a takeover that found no
trade), `2` the script could not start.

`.venv/bin/python -m evals.tool_run` measures which tool the model asks for
first on each of the assistant's nineteen sentences (`evals/sets/tools.json`),
and `.venv/bin/python -m evals.ask_run` runs every question about the ledger
of `evals/sets/asks.json` to the end and judges the table it came to;
`.venv/bin/python -m evals.edit_run` runs each sentence of
`evals/sets/edits.json` that changes or deletes a trade to the end,
answering the program's question with the gold answer's words, and judges
the proposal sent; `.venv/bin/python -m evals.stock_run` says each sentence
of `evals/sets/stocks.json`, recording a share bought with dollars, once,
and judges every field of what was sent, or the question asked, by the
ledger's codes; `.venv/bin/python -m evals.name_run --direct` hands the
words for the asset of each sentence of `evals/sets/stock_names.json` (a
share or a coin named the way people say it, on the demo book's list or
off it) straight to the step that picks an asset, and
`.venv/bin/python -m evals.name_run` says each sentence to the whole
assistant against the demo book; both run one half of the set at a time
(`--half practice`, the default, or `--half locked`, which prints the
counts alone) and judge every asset picked, named or sent;
`.venv/bin/python -m evals.judged_run --screen screen-2
--extract first-3` runs the debug set (or, with `--final-exam`, the final
set) through the start of recording, judging step and all, to hold a
prompt version the assistant uses to the old sentences;
`.venv/bin/python -m evals.spoken_run --set <file>` says each sentence of
the exam said the owner's way (`evals/sets/spoken/`, see "The exam said
the owner's way") to the whole assistant against the exam book and judges
every gold trade; all of them write
into `evals/tool_results/`; see the last sections of `evals/RESULTS.md`.

### Recording trades by hand

```sh
.venv/bin/python scripts/record_trades.py "昨天晚上在 OKX 买了 0.3 个 ETH，又卖了 50 个 SOL"
.venv/bin/python scripts/record_trades.py --answers answers.txt "sold 2 SOL at 150 yesterday"
printf '3,180\nnone\ndone\n' | .venv/bin/python scripts/record_trades.py --answers - "..."
```

The passage is the arguments, or else the first line of standard input. The
script records it as described under "Recording a passage" in "How it works, part by
part": each
question is printed with its label and the program's notes beside it, and
the answer is read from standard input. Answer "skip" to leave the trade
being asked about out, or "cancel" to drop the whole passage. Once every
trade is settled, the records are listed with the trades skipped, those
that cannot be recorded and why, the reminders and anything set aside; then
"remove N" leaves record N out, "cancel" drops the whole passage, and "done"
ends. Nothing is saved unless `--save` is given (see "Saving, listing and
exporting").

With `--answers FILE` the script is not interactive: the answers are the
lines of the file (`-` for standard input, after the passage when the
passage is not given as arguments), each printed after its question. When
they run out before every trade is settled, the script stops; when they run
out once every trade is settled, that counts as "done". The current moment
is the machine's clock and the zone the machine's own, read with tzlocal.
Without `--save`, `--list` or `--export`, nothing is written to disk and no
book is opened. Exit status: `0` done, with the records listed (there may be
none); `1` nothing is kept (the passage was refused, stopped, held no trade,
the model failed, or the passage was dropped); `2` the script could not
start (a setting or the zone); `3` the answers or the input ran out before
the end.

### Saving, listing and exporting

```sh
.venv/bin/python scripts/record_trades.py --save "昨天晚上在 OKX 买了 0.3 个 ETH，价格 3,180，手续费 0"
.venv/bin/python scripts/record_trades.py --list
.venv/bin/python scripts/record_trades.py --export
```

`--save` records the passage as above, with the book open. Before the first
question it says whether the same passage, or one that differs from it only
in spacing or full-width characters, was saved before: on which day, and how
many trades. That is a reminder only; nothing is held back. The coins
confirmed and saved before need no confirming again. Once the records are
final (after "done", and any "remove N" before it), it asks whether to save
them, and saves them only when the answer is `save` (or `yes`, `y`, `存`,
`保存`). Any other answer saves nothing, and so does running out of answers
with `--answers`: saving is never assumed.

`--list` lists every saved trade with its identifier, its fields, when it was
saved and whether and when it was exported. `--export` writes the saved
trades not exported yet into a new file in the exports folder and marks them
as exported, as described under "Keeping the records" in "How it works, part by
part"; with nothing
new, it says so and writes nothing.

The book and the exports folder are in the data folder; see "Where the data
is kept". Exit status, besides those above: `0` saved (or there was
nothing to save), listed, exported, or nothing new to export; `1` the
records were not saved, or the export was refused or its file could not be
written (nothing was marked); `4` the book failed (the message gives its
kind), or the export file was written but its trades could not be marked,
so that the next export writes them again.

## The demo book

The Assistant page and `scripts/try_assistant.py` start the fake ledger
with the demo book (`src/ledger_hand/ledger/demo_book.py`): the invented
book the tests use, unchanged, with seven more assets and nine buys in
August 2026. The assets added are SOL and DOT (coins) and Intel, Coca-Cola,
Apple, NVIDIA and PepsiCo (shares, named in English as the ledger names
them, so that a Chinese name such as "英特尔" is matched from the list).
The buys, one each of BTC, ETH, SOL, ADA, MSFT, INTC, KO, AAPL and NVDA,
all fall before the invented book's first trade, coins in USDT and shares
in USD, and are large enough that a sale said later in the autumn is not
turned down for want of a holding. PepsiCo and DOT have no trade at all.
The new assets and ADA have no market price, so their profit on paper is
not worked out. Every figure is invented.

## Sentences for a demo

These sentences show the assistant at work, one of each kind, on the
Assistant page or with `scripts/try_assistant.py`. Each is said on its own,
in a new chat, to the demo ledger as it starts (the demo book; see "The
demo book" below); under each is what it gets.
Every figure, platform and date is invented. None names a time relative to
now ("yesterday", "this month"): the try-out script takes the invented
book's moment, 24 November 2026, 23:55 in Budapest, as now, and the page
the machine's clock, so only dates and clock times written in full give
the same result in both. A question asked in English with a time in it is
often not looked up today (the model writes the time in Chinese; see
`docs/known-gaps.md`), so in a demo, say the questions as they are listed
here.

They were run at temperature 0, five runs on one machine, with
`qwen2.5:7b`, and each got what is written under it every time. That shows
the same sentence comes out the same again; it does not show that other
words for the same thing would. The live tier says each of them once more
(`tests/live/test_live_demo_sentences.py`, against
`tests/live/demo_sentences.json`), and a quick test keeps this list and
that file the same, word for word. Three of them (the MSFT trades, the
assets and the holdings) were written for the invented book and gained
rows with the demo book; those three were said once more against it, not
five times.

1. `Bought 0.004 BTC at 63250 USDT on OKX on 20 November 2026 at 14:20, fee 0.25 USDT.`
   Gets: One trade sent to the ledger, waiting there: a buy of 0.004 BTC at 63250 USDT, total 253 USDT, fee 0.25 USDT, on 20 November 2026 at 14:20, OKX. No reminder line.
2. `Bought 2 MSFT at 410 USD each on IBKR on 18 November 2026 at 15:30, fee 1 USD.`
   Gets: One trade sent to the ledger, waiting there: a buy of 2 MSFT at 410 USD, total 820 USD, fee 1 USD, on 18 November 2026 at 15:30, IBKR. No reminder line.
3. `Sold 0.1 ETH at 2690 USDT on Binance on 22 November 2026 at 17:05, fee 0.27 USDT.`
   Gets: One trade sent to the ledger, waiting there: a sell of 0.1 ETH at 2690 USDT, total 269 USDT, fee 0.27 USDT, on 22 November 2026 at 17:05, Binance. No reminder line.
4. `Bought 30 USDT of ADA at 0.31 on OKX on 21 November 2026 at 16:40, fee 0.`
   Gets: Nothing sent: the money was said where the quantity goes, and the reply says so and asks for the trade again with the money as the total. No reminder line.
5. `Show me my MSFT trades.`
   Gets: A table of every MSFT trade, all time, buys and sells: 3 rows, the buys of 12 August and 2 October 2026 and the sell of 12 November 2026. The header also says it was not narrowed to buys: the model asks for buys, and the program widens it, since the question names no side.
6. `Which assets does my ledger have?`
   Gets: A table of the ledger's assets: 13 rows, USDT, USD, BTC, ETH, ADA, MSFT, SOL, INTC, KO, AAPL, NVDA, PEP and DOT.
7. `Which coins and shares am I holding at the moment?`
   Gets: A table of what is held: 9 rows, AAPL, ADA, BTC, ETH, INTC, KO, MSFT, NVDA and SOL, each with its cost and its profit or loss on paper (not worked out for ADA, SOL, INTC, KO, AAPL and NVDA, which have no market price).
8. `Change the platform of the ADA buy on 25 September 2026 to Binance.`
   Gets: A change sent to the ledger, waiting there: the ADA buy of 25 September 2026, its platform from OKX to Binance, shown before and after.
9. `Delete the MSFT sell on 12 November 2026.`
   Gets: A deletion sent to the ledger, waiting there: the sell of 1 MSFT on 12 November 2026.

With the try-out script, `--save` before a sentence saves what it sent in
the demo ledger, as confirming would on the ledger's page:
`.venv/bin/python scripts/try_assistant.py --save "Delete the MSFT sell on 12 November 2026."`.
On the page, "Save in the demo ledger" on the proposal's card does the same.

No screenshot is among them: the repository holds no picture of an order.
To show recording from a screenshot, first set the longest reply to 4096
on the Settings page; one clear picture was read that way, which does not
promise that every one will be (see "Recording from a screenshot").

## Running the checks

```sh
scripts/check.sh          # the same as: scripts/check.sh quick
```

The script takes one argument, the tier: `quick` (the default), `ledger` or
`live`.

`quick` needs no network and no running model, and runs these steps in order:

| Step | What it runs | What it guards |
| --- | --- | --- |
| `format` | `ruff format --check .` | Formatting is left to the tool. |
| `lint` | `ruff check .` | Basic errors, import order, naming, common pitfalls, needless complexity, boolean flag parameters, overlong functions. |
| `types` | `mypy` | Strict type checking of `core/` and `ports.py`. |
| `layering` | `pytest tests/guardrails/test_repo_layering.py` | Each part of the package imports only what the layering table allows; `core/` reads no clock and uses no floating-point number; `extraction/`, `asking/` and `flows/` read no clock and no zone of the machine; only `settings.py` reads environment variables; only `ui/` imports Streamlit and only the wiring module imports tzlocal. |
| `hygiene` | `pytest tests/guardrails/test_repo_hygiene.py` | No machine-specific paths, private work-log identifiers or tool-attribution text in any file Git tracks or would add. |
| `tests` | `pytest` | Every test except the live ones, including the tests of the two guardrails themselves. No test reaches the network: the model plug is tested against a fake transport, and a test that tries to connect fails on the spot. |

The script stops at the first step that fails and ends with `FAILED: <step>`,
so the last line always says where to look. Exit status: `0` when every step
passed, `1` when a step failed, `2` when the script could not start (unknown
tier, or no Python environment), `3` when the tier was skipped.

### The ledger tier

```sh
LEDGER_HAND_LEDGER_DIR=path/to/LocalFirstTradingLedger scripts/check.sh ledger
```

`ledger` asks the ledger itself whether it accepts the files this program
writes. It needs a checkout of the Local-First Trading Ledger on the same
machine with its packages installed (`npm install` there), and Node.js on the
`PATH`. The checkout is named by the environment variable
`LEDGER_HAND_LEDGER_DIR`; `scripts/ledger_check.py --ledger PATH` takes it as
an argument instead.

It is two scripts. `scripts/ledger_check.py` (Python) writes the sample files
into a fresh temporary directory, runs the ledger's validator on them and
judges each answer. `scripts/ledger_validate.ts` (TypeScript) is the part that
runs inside the ledger checkout: started with the checkout's own `tsx`, it
imports the ledger's `parseBackupJson` and prints what it says about each
file. Each sample is expected to be accepted with no error, refused only for
selling more than is held (this program cannot know what the ledger holds), or
refused with exactly the errors planted in it. Two samples, which hold a
trade in every time zone, are expected to be accepted except for one known
gap: where the ledger's time zone database gives a zone another offset than
ours, the ledger refuses the trade's offset. Which zones and moments those
are is worked out each run by asking both sides
(`scripts/ledger_offsets.ts`); such refusals are announced in a notice marked
`!!!` and not counted as a failure, and any other refusal is. The gap is
described in `docs/known-gaps.md`. The output lists every error the ledger
reported for every sample.

On the machine the checks run on now, one sample does not pass:
`attack-earliest-moments.json`, a trade at noon on 2 January of the year 1
in every zone whose offset then is a whole number of minutes. There
Python's copy of the time zone database (2026e) holds
`EST5EDT`, `CST6CDT`, `MST7MDT` and `PST8PDT` as zones of their own, and the
ledger's Node (tz 2026a, ICU 78.2) takes the four names for New York,
Chicago, Denver and Los Angeles, whose offsets before 18 November 1883 have
seconds in them; with both at once, the ledger's validator throws on those
trades instead of refusing them, and the tier fails. With Python reading
2026c and Node carrying 2026a, the sample was accepted. Why the sample and
the tests are left as they are is in `docs/known-gaps.md`, "Time zone
database versions".

What is checked is listed in `tests/ledger_check/cases.py`: the golden sample,
edge cases, batches of awkward trades (every time zone, the first and last
days there are, awkward characters, extreme numbers, buys followed by sales,
the ledger's limits of one file) and copies with mistakes planted in them.
One sample is the file the export flow writes from a book of invented trades
in a temporary folder, so that what the flow writes is judged as well. The
two samples that allow for the gap between the time zone databases are also
judged strictly: once both sides have been asked which of their trades they
give different offsets, those trades are left out, the rest are exported
again, and these two samples must be accepted with no error at all. The
output lists every trade left out, with its zone, its moment and both
offsets.
Each sample is handed to the ledger together with the date it is to take as
today, the same date it was exported on, and is judged three times: in the
machine's own time zone, in Los Angeles and in Kiritimati. Before that, the
export itself must refuse one coin, one trade and one byte more than a file
may hold. One sample is about 128 MiB, so the tier takes several seconds and
over a gigabyte of memory.

The ledger checkout is only read. Before and after, the tier asks Git whether
the checkout is clean, with `git --no-optional-locks status --porcelain`,
which writes nothing into it, and fails when it is not. `tsx` runs with
`--no-cache`, and the configuration file it needs (one that extends the
ledger's own, because it has to name the checkout) is generated in the
temporary directory. Git does not see files it ignores, such as caches under
`node_modules`; to make sure nothing at all was written, look for files newer
than a marker made just before the run (`find <checkout> -newer <marker>`).

When no checkout is named, the named one is missing, or `tsx`, Node.js or Git
is missing, the tier is skipped: it prints why and ends with exit status `3`,
which is neither a pass nor a failure. `quick` never depends on it.

### The live tier

```sh
scripts/check.sh live
```

`live` talks to a real model, so it is only ever run by hand. It needs the
model server named in the settings running, with the model there: by
default Ollama on this machine with `qwen2.5:7b`. It runs the tests marked
`live_model` in `tests/live/`, with the settings read from the environment
as the program reads them. It asks the server for its version and the
model's fingerprint, then hands the model an invented question with a small
table (a JSON schema) and checks that the reply is valid JSON that follows
the table. It prints the table, the reply, how long the call took and the
token counts. Then it takes four invented passages (one trade in Chinese,
one in English, several trades, and talk with no trade) the whole way
through extraction, prints the drafts, the issues and how long each passage
took, and checks only that each comes back as drafts and a list of issues;
whether the model read them right is not judged there. Then it judges the
debug set (never the final set): the four sentences that report only what
the ledger does not record (leverage, one coin for another, an order not
filled, a plan) must each be stopped, with nothing extracted and no
question asked; the kind the model named is printed beside the kind the
sentence was written as. For the other 26 it prints where each would go,
and checks nothing about it. It also runs the page headless with the parts
the wiring module builds (the data folder pointed at a temporary one), sends
one invented passage, and checks that the page comes to its first question
or settles every trade without breaking; it prints what the program said,
the table and how long it took. On the settings page it then points the
model's address at a port on this machine nobody listens on, checks that a
passage is answered by the sentence that names that address, goes back to
the environment and the defaults, and checks that the same passage comes to
its first question. It shows the vision model the settings name
(`LEDGER_HAND_MODEL_VISION_NAME`, by default `qwen3-vl:8b`) a picture of one
plain colour, 64 by 64 pixels, drawn in memory and never written anywhere,
asks what colour it is, and checks only that words came back from that
model; it prints the reply, whether it named the colour, and the time. Then
it extracts one of the four invented passages with the vision model and
thinking off, and checks only that the server took the request (it was not
turned down with a status from 400 to 499); what came back is printed and
not judged. Both build the plug with thinking off, whatever the default. So
the live tier needs the vision model on this machine as well: without it,
those two checks fail, and are not skipped. Last, it tries the cloud plug against the same server:
Ollama also answers the OpenAI-style chat endpoint under `/v1` of its
address, so the cloud plug is pointed there, with an invented key that
Ollama does not check, and asked the same small question once, with no
retries; the reply must be valid JSON that follows the table. It also asks
for a model the server does not have, through both plugs, and prints the
kind, the status code and the sentence the page would show: through the
local plug it names `ollama pull`, through the cloud plug it says nothing of
Ollama. No cloud service is called: when the address the settings name is
not on this machine (a cloud address left set in the shell, say), those two
checks send nothing and are skipped, saying why. Unset the cloud settings before running
the live tier: every other live check talks to the address they name. When the server cannot be reached, it fails with a
message that starts with `unreachable`.
The first call after the model has been idle includes loading it into
memory, which takes several seconds more than the calls after it.

The assistant is checked there too, with the demo ledger and the invented
book's moment: what is held now, one trade told in full, one day's trades,
and each of the sentences for a demo (`tests/live/test_live_demo_sentences.py`,
see "Sentences for a demo"), each held to what `tests/live/demo_sentences.json`
says it must come to.

To see what happens when no model server is running, do not stop the one you
have: point the address at a port nothing listens on instead, for example
`LEDGER_HAND_MODEL_URL=http://127.0.0.1:59999 scripts/check.sh live`.
`quick` gives the same result either way, because it never talks to a model.

## Running an experiment

An experiment measures one change against the yardstick in `evals/`: a
prompt version, the way a passage is read, a model or a parameter. It runs
from the top of the repository with the model server running, and goes like
this:

1. Make the change. A new wording of a prompt is a new version in a new
   file under `src/ledger_hand/extraction/prompts/`, registered in
   `PROMPTS` in `evals/run.py`; a version once measured is never changed.
   The way a passage is read is chosen with `--method`, another model with
   `--model` (pulled into Ollama by hand first), a parameter with its
   environment variable.
2. Before running, write down the rule that will pick one, the way
   `evals/compare.py`, `evals/compare_methods.py` and `evals/compare_sets.py`
   do.
3. Run the debug set with each candidate, and commit each results file
   with its section of `evals/RESULTS.md`: a test of the quick tier checks
   that the record shows exactly what every committed results file gives.
4. Apply the rule (`--choose`).
5. Run the final set once, with `--final-exam`, with the one picked, and
   never tune anything against it. When the one picked has the prompt, the
   way of reading, the model and the parameters of an earlier final run, at
   temperature 0, that run stands and the final set is not run again. The
   comparison of two models ran the final set once more with `qwen2.5:7b`
   all the same, because it picks nothing: it lays both models side by side
   on the same sets at one commit.

The four prompt experiments, the comparison of two models and the trial of
the thinking switch made so far, their tables and the rules the experiments
used are in `evals/RESULTS.md`;
`docs/project-report.md`, section 6, sums them up.

### The prompts and their techniques

Each prompt version is a file of its own, never changed once measured; a new
wording is a new version.

| Prompt | Step | Technique |
| --- | --- | --- |
| `first` (`extraction/prompts/first.py`) | Extraction: copy the phrases of each trade into a table | A few examples (few-shot), in a file beside it |
| `zero_shot` (`extraction/prompts/zero_shot.py`) | Extraction, for experiments only | No example at all (zero-shot): `first` without its examples |
| `persona` (`extraction/prompts/persona.py`) | Extraction, for experiments only | A role (persona): a paragraph before `first`'s instructions |
| `stepwise` (`extraction/prompts/stepwise.py`) | Extraction, for experiments only | Step by step (chain of thought): `first` asks for a written analysis, in a field `steps` of its own reply table, before the rows |
| `price_total` (`extraction/prompts/price_total.py`) | Extraction, for experiments only | A changed content: `first` and one more rule, that a total is never the price |
| `second` (`extraction/prompts/second.py`) | Extraction, for experiments only | A changed content, two changes at once: `first`'s instructions and two more rules (the owner's words for a buy; an amount with U right after it is the total), and `first`'s ten examples and six more written the way the owner writes, in `extraction/prompts/second_examples.py` |
| `third` (`extraction/prompts/third.py`) | Extraction, for experiments only | A changed content: `first` and the two rules of `second`, without its six examples |
| `fourth` (`extraction/prompts/fourth.py`) | Extraction, for experiments only | A changed content, two changes at once: `first`'s instructions and the two rules of `second`, and `first`'s ten examples and seven more, five written the way the owner writes and two in English, in `extraction/prompts/fourth_examples.py`; it differs from `third` only in those examples |
| `split-1` (`extraction/prompts/split.py`) | Splitting a passage, for experiments only: copy the pieces of the passage each trade needs | A few examples (few-shot), in the same file |
| `screen-1` (`extraction/prompts/screen.py`) | Judging a passage: which kinds of thing it reports | No example at all (zero-shot) |
| `answer-1` (`extraction/prompts/answer.py`) | Reading an answer the rules could not: copy the one piece that gives what was asked | No example at all (zero-shot) |
| `read-1` (`extraction/prompts/read.py`) | Reading a screenshot out as text, before extraction: each value with the label the screen gives it, as it stands | No example at all (zero-shot) |
| `bookkeeper-1` (`asking/prompts/bookkeeper.py`) | Wording a follow-up question | A role (persona): a meticulous bookkeeper who asks for one thing at a time |
| `spoken-1`, `spoken-2`, `spoken-3` (`extraction/prompts/spoken1.py`, `spoken2.py`, `spoken3.py`) | Extraction of words with a Chinese character in them, for experiments only | A changed content: `first-3`'s instructions and examples, then rules and examples written the way the owner speaks, already tidied (`spoken1_examples.py` and after); the version is chosen by whether the words hold a Chinese character (`extraction/prompt_language.py`), English keeping `first-3`. None was picked: the assistant extracts with `first-3` |
| `assistant-5` (`assistant/prompts/assistant_fifth.py`) | The assistant's system prompt, for experiments only | A changed content: `assistant-4` with its rule on finding a trade to change said as the tools say (call the tool straight away). It met the rule it was held to and is the default the assistant turns with (`evals/RESULTS.md`) |

`zero_shot`, `persona`, `stepwise` and `price_total` each differ from
`first` in that one thing only, and a test checks it. `second` differs from
`first` in two things at once, more rules and more examples, so its runs
cannot tell which of the two made a difference; `third` has the rules of
`second` without its examples. `fourth` differs from `first` in two things
as well, the rules of `second` and seven examples of its own, and from
`third` in its examples only. Tests check each of the three against what it
declares it adds. The product records passages with `first`: the rule fixed
before the third prompt experiment picked neither `second` nor `third`, and
the rule fixed before the fourth picked `fourth`, which then did not pass
the final set. A
version may bring a reply table of its own (`stepwise` does); otherwise it
sends the one table every version shares. The module descriptions of
`zero_shot`, `persona`, `stepwise` and `price_total` say what was true when
each was measured, such as the version the product records passages with;
a measured file is never changed.

Every prompt except the one for wording a question runs at the temperature
of `LEDGER_HAND_MODEL_TEMPERATURE` (0 by default); wording a question runs
at `LEDGER_HAND_MODEL_QUESTION_TEMPERATURE`. The state of a recorded passage
names the version used for each step.

### The exam said the owner's way

`evals/sets/spoken/` holds about a hundred sentences written the way the
owner talks, every figure made up: recording in three tiers, as said
(`spoken-r100-*.json`), a little tidier (`spoken-r80-*.json`) and tidy
(`spoken-r70-*.json`); questions about the ledger (`spoken-asks-*.json`);
and changes and deletions (`spoken-edits-*.json`). Each kind is cut in two
halves: the odd-numbered sentences are the practice half (`*-practice.json`),
which may be looked at while prompts are tuned; the even-numbered ones are
the hidden half (`*-hidden.json`), which is not. A file says which half it
is (`"half"`), so a run of a hidden half prints its counts alone, never a
sentence nor its identifier, and adds one line to the hidden-run log
(`evals/tool_results/hidden-runs.log`), which is only ever added to; a test
sees that every hidden results file has its line there. Every sentence is
said against the exam book (`evals/exam_book.py`): the demo book and seven
more trades the questions and changes need.

```sh
.venv/bin/python -m evals.spoken_run --set evals/sets/spoken/spoken-r100-practice.json
.venv/bin/python -m evals.spoken_run --set evals/sets/spoken/spoken-r70-hidden.json
.venv/bin/python -m evals.ask_run --set evals/sets/spoken/spoken-asks-practice.json
.venv/bin/python -m evals.edit_run --set evals/sets/spoken/spoken-edits-hidden.json
```

`evals.spoken_run` says each recording sentence once, in a chat of its own,
to the whole assistant, and judges each gold trade into one ending (①
saved with no cell changed; ② sent, every wrong cell carrying its own
mark; ③ a wrong figure with no mark; ④ asked, rightly or not, or waiting
another trade's turn; ⑤ not sent; or not measured), with the columns kept
apart beside them (`evals/spoken_judge.py`, `evals/spoken_tally.py`). It
answers one question only: the asset's code, once a trade, when the
program asks which asset a trade is; a trade saved after that is counted
apart (①a). A sentence the ledger cannot take yet (a payment in euros) is
not enabled and counted in a table of its own. The question and change
measures read the same two keys at a set's top: `"book": "exam"` holds the
exam book, and `"half": "hidden"` keeps the run to its totals; a set that
names neither runs as before.

`--extract` names the extraction version for words with a Chinese
character in them (`first-3`, the assistant's own, or `spoken-1` to
`spoken-3`); English is extracted with `first-3` either way, through the
same choice the assistant makes (`extraction/prompt_language.py`).
`evals.stock_run` takes the same switch, and `evals.judged_run` sends a
version for Chinese through that choice too. The three versions were
written on the practice halves only, and a gate checks that none copies a
sentence of either half
(`tests/extraction/test_spoken_prompts_copy_no_exam_sentence.py`). How
they were measured and why none was picked is in `evals/RESULTS.md`.

```sh
.venv/bin/python -m evals.spoken_run --set evals/sets/spoken/spoken-r80-practice.json --extract spoken-2
.venv/bin/python -m evals.stock_run --extract spoken-2
.venv/bin/python -m evals.judged_run --screen screen-2 --extract spoken-2 --hold-other-unit --tidy
```

### The commands

```sh
.venv/bin/python -m evals.run                    # the debug set, prompt "first", the model the settings name
.venv/bin/python -m evals.run --model qwen2.5:7b --prompt first
.venv/bin/python -m evals.run --prompt stepwise  # any version: first, zero_shot, persona, stepwise, price_total, second, third, fourth
.venv/bin/python -m evals.run --set writings --prompt first
.venv/bin/python -m evals.run --set voice --model qwen3-vl:8b
.venv/bin/python -m evals.run --method split_first     # split each passage first; default one_list
.venv/bin/python -m evals.run --model <another model>  # any model the server has
.venv/bin/python -m evals.run --resume evals/results/<file>.jsonl
.venv/bin/python -m evals.summarize evals/results/<file>.jsonl [--check]
.venv/bin/python -m evals.extra_counts evals/results/<file>.jsonl
.venv/bin/python -m evals.compare evals/results/<file>.jsonl ... [--choose]
.venv/bin/python -m evals.same_replies evals/results/<earlier>.jsonl evals/results/<later>.jsonl
.venv/bin/python -m evals.compare_methods evals/results/<one list>.jsonl evals/results/<split first>.jsonl [--choose]
.venv/bin/python -m evals.compare_models evals/results/<one model>.jsonl evals/results/<other model>.jsonl [--parameter <name>]
.venv/bin/python -m evals.compare_sets evals/results/<run of first>.jsonl evals/results/<run of a candidate>.jsonl ... [--choose | --final]
.venv/bin/python -m evals.spoken_run --set evals/sets/spoken/spoken-<r100|r80|r70>-<practice|hidden>.json [--extract <first-3|spoken-1|spoken-2|spoken-3>]
.venv/bin/python -m evals.stock_run [--extract <first-3|spoken-1|spoken-2|spoken-3>]
.venv/bin/python -m evals.ask_run --set evals/sets/spoken/spoken-asks-<practice|hidden>.json
.venv/bin/python -m evals.edit_run --set evals/sets/spoken/spoken-edits-<practice|hidden>.json
```

Run these from the top of the repository, with the model server running.
The runner takes the debug set. `--set writings` takes instead the small
set of sentences written for the hard ways of writing a number (`3 w`,
`100 万`, `94 900`, `0.02 94900`, `94，900`), which is scored the same way
but reported apart. `--set voice` takes the ten passages written in the
owner's own voice, with invented numbers, also scored apart and never
merged into the debug set. The final set is run only with `--final-exam`, and its
results file says so; it is meant for the last run of an experiment, once
the prompt is settled, so that the scores are not tuned to it. `--only`
runs some sentences of the set by their ids. `--prompt` names the prompt
version; the parameters are the settings' (set one with its environment
variable, such as `LEDGER_HAND_MODEL_TEMPERATURE`, to run a parameter
comparison). `--method` chooses how each passage is read: `one_list`, the
default and the product's way, sends the whole passage in one call;
`split_first` splits it into one segment per trade first (prompt
`split-1`) and extracts each segment on its own, and the results file
name ends in `-split_first`. `--model` names another model the server has
instead of the setting's, which is how a second model is run: the run line
records the name given and that model's fingerprint, and a name the server
does not have stops the run before any results file is written (exit
status 2). Nothing is downloaded: a model is pulled into Ollama by hand
first.

The first line of the results file records the conditions: the set and
its fingerprint, the prompt version with its files and their fingerprints
(a version built on `first` lists `first`'s files too), the fingerprint of
the reply table it sends, the commit and whether the work tree was clean,
the model, its fingerprint and the server's version, every parameter
(temperature included, as the settings give it) and when the run began;
also the way each passage is read and, when it is split first, the split
prompt with its file and fingerprints. Each sentence's line is added the
moment it is done: the model's raw replies, the drafts, the issues, the
phrases the model copied, the scores and how long it took; also the record
of every reply read (`reads`: which call split the passage and which
extracted a segment, the rows each reply gave and the draft each row
became), from which the scores take each draft's phrases, and when the
passage was split first, how (`split`: the route, the trades the split
listed, the segments). A run cut short
can be carried on with `--resume`, under the same conditions only. The
summary is saved beside the results file and printed as tables;
`evals.summarize` works it out again from the file alone, and `--check`
compares it with the saved one. `evals.extra_counts` works out three more
counts from the file alone: a total put as the price, half copies counted
whether or not the field came out right, and a time written in another
language. `evals.compare` lays several runs side by side and, with
`--choose`, applies the rule fixed before the first prompt experiment: the
most whole trades right; then the fewest wrong values with no issue; then
the fewest trades missed and extra; then the first of `first`,
`price_total`, `persona`, `zero_shot`, `stepwise`, so that a new version is
picked only when it does strictly better than `first`. Its tables name each
run by its prompt version, and their column "Differs from `first` in" says
how that version differs from `first`, so a run of `first` reads "the
baseline" there even when a parameter was changed for it; the parameter is
in the run's first line. `evals.compare_models` with `--parameter`, below,
names the parameter's value in each row instead. `evals.same_replies`
tells two runs' raw replies apart from what the program made of them.
`evals.compare_methods` lays a one-list run and a split-first run side by
side (by number of trades, with the calls to split counted apart), shows
how each passage was split and, with `--choose`, applies the rule fixed
before the second prompt experiment: the most whole trades right; then the
fewest wrong values with no issue; then the fewest trades missed and extra;
then one list, so that splitting first is picked only when it does strictly
better. `evals.compare_models` lays the runs of two models on one set side
by side: the scores, what each sentence gave (model failures by kind, empty
replies apart), each field, the seconds per sentence and the sentences where
the two differ; it refuses two runs that differ in anything but the model,
and `--parameter` lets one parameter differ, which it then names. With
`--parameter` it also compares two runs of the same model, when that
parameter is the only difference and the model's fingerprint and the
server's version are the same; each row is then named by the model and the
parameter's value.
`evals.compare_sets` lays the runs of `first` and of other prompt versions
side by side on each set: the scores, the three more counts, the seconds,
each field and the sentences where they differ; it refuses runs that differ
in the set, the model, the server's version, the way of reading a passage,
the parameters or the reply table. With `--choose` it applies to one
candidate the rule fixed before the third prompt experiment, and with
`--final` it sets a candidate's run of the final set against an earlier one
of `first`.

The debug set took about two minutes with `qwen2.5:7b` on the machine it
was built on, with the model already loaded (`stepwise`, which writes its
analysis first, about three); the first sentence of a run includes loading
the model when it is not. With `qwen3-vl:8b`, which thinks before it
replies, the debug set took 1282.1 seconds, 42.74 a sentence
(`evals/RESULTS.md`).

The quick tier tests the scoring against cases worked out by hand and the
test sentences (coverage, no repeat of a prompt example, every gold answer
kept by the core's rules), and reads the final set only: no test sends a
test sentence to a model. The writings set is tested the same way, and one
test runs one of its sentences through the scripted model; so is the voice
set, whose file is also pinned by its fingerprint. It also checks that every committed run is
finished, that its saved summary is the one its results file gives, and
that `evals/RESULTS.md` shows exactly the tables each results file gives,
the three more counts of every run after the baseline, and the comparisons of
the two prompt experiments as their results files give them, and the
comparison of the two models likewise, with what the first line of each of
its runs must show (`tests/evals/test_model_comparison_record.py`). Each committed
line that holds the record of every reply read must hold, one per draft,
exactly the phrases that record gives, and the runs made before that record
existed must give the same summaries and counts as before. The split prompt
is checked, like the others, to hold no test sentence nor any clause of one.
A sample of what `first` sends to the model
(`tests/extraction/first_prompt_calls.json`) is compared byte for byte, so
the baseline cannot move unnoticed.

To let the tool fix formatting instead of only reporting it:

```sh
.venv/bin/python -m ruff format .
```

`scripts/check.sh` uses the Python in `.venv/`. Set `LEDGER_HAND_PYTHON` to
the path of another interpreter to use that one instead.

## Settings

Every setting is an environment variable, read when the program starts. The
model settings can also be changed on the interface's Settings page, for the
browser tab only; the data folder and the variables the scripts read cannot.

### Model settings

The model settings are read from these environment variables. A variable
that is not set, or is blank, takes its default. A value in the wrong form
or out of range stops the program with a message that names the variable,
and so does a variable that starts with `LEDGER_HAND_MODEL_` but is not one
of these, because a misspelt name would otherwise be ignored without a word.
Every one of them but the key can also be changed on the interface's
settings page, for the browser tab only (see "The settings page").

| Variable | Default | What it sets | Why this default |
| --- | --- | --- | --- |
| `LEDGER_HAND_MODEL_PLUG` | `local` | Which plug talks to the model: local, Ollama's own chat endpoint; or cloud, the OpenAI-style chat endpoint most cloud services offer. The cloud plug needs the service's address, and for an address off this machine https and a key. | Local, so that by default the model runs on this machine and nothing that is typed leaves it. Setting an address or a key never switches to a cloud service; only this does. |
| `LEDGER_HAND_MODEL_URL` | `http://127.0.0.1:11434` | Where the model server is: an http or https address, with no user name, password, query or fragment. | Ollama's own address on this machine, so by default the model runs locally and nothing that is typed leaves the machine. |
| `LEDGER_HAND_MODEL_NAME` | `qwen2.5:7b` | Which model to ask. | The model the program was built and measured with. |
| `LEDGER_HAND_MODEL_KEY` | (none) | A key, sent as a bearer token, for a server that needs one. Never shown, and set in the environment only. | None: the local Ollama needs no key. |
| `LEDGER_HAND_MODEL_TEMPERATURE` | `0` | How adventurous the model is when it judges a passage, extracts the trades and reads an answer. 0 or more. | Extraction has to give the same answer to the same text, so the model always takes its likeliest word. |
| `LEDGER_HAND_MODEL_TOP_P` | `1` | Keeps only the likeliest words whose chances add up to this. Above 0, at most 1. | Keeps every word in play, so the temperature alone says how adventurous the model is; at temperature 0 it changes nothing. |
| `LEDGER_HAND_MODEL_MAX_REPLY_TOKENS` | `1024` | The longest reply, in tokens, the pieces of words a model counts in. A whole number, 1 or more. | Room for a JSON list of about ten trades. A reply that reaches it is marked as cut off rather than passed on as if it were whole. |
| `LEDGER_HAND_MODEL_CONTEXT_TOKENS` | `16384` | How much the model reads at once, in tokens. A whole number, 1 or more. | Ollama's own default (2048 or 4096, depending on the version) is too short for a prompt with examples and a schema, and Ollama drops the start of a prompt that does not fit, without an error. Measured with qwen2.5:7b, which reads up to 32768: the first prompt with its examples is about 1,750 tokens, and the longest passage the ledger keeps, 16,384 characters of Chinese, about 11,600 (English text takes fewer). With a full reply that is about 14,400, which leaves some 2,000 to spare; a longer window costs memory. |
| `LEDGER_HAND_MODEL_TIMEOUT_SECONDS` | `120` | How long to wait for the whole reply, in seconds. Above 0. Not sent to the model. | Leaves room for loading the model into memory on the first call (a cold start takes seconds to tens of seconds) and then writing a full-length reply. |
| `LEDGER_HAND_MODEL_RETRIES` | `2` | How many times a call that timed out, was rate limited or met a server error is tried again; a request the server turned down as wrong, with a status from 400 to 499 other than 429, is not. 0 to 10. | Three tries in all, for the failures that may pass on their own, without keeping the person waiting for long. |
| `LEDGER_HAND_MODEL_RETRY_WAIT_SECONDS` | `1` | The wait before the first retry, in seconds; each later wait is twice the one before. A server that says how long to wait is waited for that long instead, up to a minute. 0 or more. | A second gives a busy server a moment to recover, and with each wait twice the one before, two retries add three seconds at most when the server does not say how long to wait. |
| `LEDGER_HAND_MODEL_QUESTION_TEMPERATURE` | `0.7` | The temperature for wording a follow-up question. 0 or more. | Wording a follow-up question is the one call where some variety reads more naturally than the same sentence every time. What is asked, and every fact the question may use, are fixed by the program before the model writes, and a sentence that strays is replaced by the program's own, so a higher temperature changes only the wording. Judging a passage, extraction and reading an answer keep LEDGER_HAND_MODEL_TEMPERATURE, 0 by default. |
| `LEDGER_HAND_MODEL_VISION_NAME` | `qwen3-vl:8b` | Which model reads a screenshot: the one shown the picture, which writes out the order on it as text. The text it reads is then extracted by the model LEDGER_HAND_MODEL_NAME names, as a typed passage is. Read through the local plug only. | A model on this machine that can see pictures; qwen2.5:7b, the model the program extracts with, cannot. |
| `LEDGER_HAND_MODEL_THINK` | `model` | Whether the local plug asks the model to think before it answers: on sends Ollama's think field as true, off sends it as false, model sends nothing and leaves it to the model's own default. The cloud plug never sends it. A model that cannot think refuses on: Ollama answers with status 400, saying the model does not support thinking. | Model: nothing is sent, so each model answers as its own default says. Measured with qwen3-vl:8b on the debug set (see "2026-10-19: the thinking switch, `qwen3-vl:8b`" in evals/RESULTS.md), off got fewer trades whole than nothing sent, and every reply it gave was empty, so off is not the default; nor is on, which qwen2.5:7b, the model the program extracts with, cannot do. |
| `LEDGER_HAND_MODEL_SCREENSHOT_MAX_MB` | `20` | The largest screenshot taken, in MB of 1,048,576 bytes; a larger file is turned away before anything is sent. A whole number, from 1 to 200, the most Streamlit takes in one upload by default. | Above any phone's screenshot, so none is turned away: the largest phone screens, 1320 by 2868 pixels, come to about 14.4 MB even with no compression at all, four bytes to a pixel, and a PNG of an order page, mostly flat colour, is far smaller. A file larger than that, such as a camera's photo or a file chosen by mistake, is turned away at once rather than after a long wait for the vision model. |

Numbers are written with plain digits and at most one point (`0.7`, `45`),
with no sign or exponent. The defaults are named constants in
`src/ledger_hand/settings.py`. What each variable sets and why its default
is what it is are kept there once, as data (`ABOUT`); this table and the
interface's settings page show them as written there, and a test checks
this table against them.

The time allowed is counted from sending. Connecting, sending and each wait
for the next piece of the reply are each cut off at the time allowed, and a
reply still arriving once that time has passed is abandoned at its next
piece. So a server that keeps trickling bytes cannot keep a call open for
long past the time allowed.

The plug ignores the proxy settings of the environment (`HTTP_PROXY` and the
like), so a request for the model on this machine never leaves it through a
proxy.

### Where the data is kept

| Variable | Default | What it sets | Why this default |
| --- | --- | --- | --- |
| `LEDGER_HAND_DATA_DIR` | `data` in the working directory | The data folder. The book is `ledger-hand-book.sqlite3` in it, export files go into `exports/` in it, and the assistant's record is `assistant-record.jsonl` in it. A relative folder is taken from the working directory; a leading `~` is the home folder. | Started from the top of the repository, as this README does, the program keeps everything it writes in one folder that the repository's ignore file keeps out of Git. |

The data folder and the exports folder are made when something is first
written there; reading the setting makes nothing, and recording a passage
without `--save` never opens the book. The interface opens the book when it
takes a passage (to find an earlier save of it and the coins confirmed
before), so the book is made then if it is not there yet; it writes trades
into it only on Save. This variable is not one of the model
settings and does not start with their prefix, so setting it never
makes the model settings refuse anything; neither do `LEDGER_HAND_LEDGER_DIR`
and `LEDGER_HAND_PYTHON`, which the scripts read. The default `data/` is
kept out of Git by the repository's ignore file. The book holds the original
passages, as typed, and the assistant's record holds what was said to the
assistant, in plain text: keep both out of anything shared.

### How far the assistant may go

| Variable | Default | What it sets | Why this default |
| --- | --- | --- | --- |
| `LEDGER_HAND_ASSISTANT_STEPS` | `6` | How many times the assistant may ask the model in one turn, from 2 to 20. | A change takes the most steps of any task the assistant is meant to do (look the trade up, propose the change, answer); six leaves room for that and one wrong step, while a model going round in circles is stopped after about half a minute on this machine. |

Like the data folder, this is not one of the model settings: it does not
start with their prefix and is not shown on the settings page. The
Assistant page reads it when the program starts; a value it refuses stops
that page alone, which says why, and the Record and Settings pages work as
before.

### Variables the scripts read

| Variable | Default | What it sets | Why this default |
| --- | --- | --- | --- |
| `LEDGER_HAND_LEDGER_DIR` | (none) | The checkout of the Local-First Trading Ledger that the ledger tier of the checks asks (see "The ledger tier"). | None: the ledger is a project of its own, and without a checkout the tier is skipped, never failed. |
| `LEDGER_HAND_PYTHON` | `.venv/bin/python` | The Python that `scripts/check.sh` runs the tools with. | The repository's own environment, built as "Setting up from scratch" says. |

## Switching to a cloud model

By default the model runs on this machine, through Ollama, and nothing that
is typed leaves it. The program can instead talk to a cloud service through
the chat endpoint most of them offer, first made by OpenAI
(`POST <address>/chat/completions`). Nothing else changes: the same
prompts, the same checks of every reply, the same questions.

**Once you switch, everything you type is sent to that service:** each
passage, each answer to a question, and the prompts with their examples. Do
not switch for passages you would not hand to that service.

To switch, set four variables before the program starts (see "Model
settings" for all of them):

```sh
export LEDGER_HAND_MODEL_PLUG=cloud
export LEDGER_HAND_MODEL_URL=https://api.example.com/v1   # the service's address, with its version
export LEDGER_HAND_MODEL_KEY=...                          # the key the service gave you
export LEDGER_HAND_MODEL_NAME=...                         # a model the service offers
```

`api.example.com` stands for the service's own address; the program names
no service and has no cloud address of its own. Only
`LEDGER_HAND_MODEL_PLUG` switches: setting an address or a key alone
leaves the local plug in use. The plug, the address and the model can also
be changed on the settings page, for the browser tab only; the key cannot.
Unsetting `LEDGER_HAND_MODEL_PLUG`, or "Back to the environment and the
defaults" when the switch was made on the page, goes back to the local
model.

The program refuses to build the cloud plug, and says which variable to
set, when the address is still the local Ollama's own, when an address off
this machine does not start with `https://` (the key and every passage
would travel unencrypted), or when an address off this machine has no key.
A server on this machine that offers the same endpoint (`127.0.0.1`,
`localhost` or `::1`) may go without https and without a key. Reading the
settings checks each variable on its own; these checks are made when the
plug is built, so a refusal names the variable to change.

What is sent with each call: the model's name, the messages, `temperature`,
`top_p` and `max_tokens` (the longest reply), and, when the program wants a
reply in the shape of a table, that table as a JSON schema in
`response_format` (type `json_schema`, `strict` true). The key goes in the
`Authorization: Bearer` header and nowhere else. How much the model reads
at once (`LEDGER_HAND_MODEL_CONTEXT_TOKENS`) is not sent: the endpoint has
no such field, and the service decides it. The time allowed is how long
this side waits, as for the local model.

When the service answers 429, "called too often", the program waits as long
as its `Retry-After` header asks (in seconds or as a date), up to a minute,
then tries again; each such wait counts as one of the retries. A longer wait
is not sat through: the page says how many seconds the service asked for.
Without the header the waits double as for the local model. A key the
service does not take (401, 403) and a request it turns down (400) are said
in plain words at once and not tried again; a model the service does not
have (404 saying so) is said as a missing model.

Known limits:

- Some services' newer endpoints name the longest reply
  `max_completion_tokens`. This plug sends `max_tokens`, the name every such
  service takes; a model that takes only the newer name turns the call down
  with 400.
- A service that does not take a reply table as a strict JSON schema in
  `response_format` refuses every call with 400. There is no second way of
  asking (such as plain JSON without the table); the page says the call was
  turned down and quotes the start of the service's answer.
- No test calls a real cloud service. The quick checks feed the cloud plug
  answers shaped like a cloud service's through a fake transport; the live
  tier sends it once to the local Ollama's OpenAI-style endpoint (`/v1`),
  which shows that the request is in a form such a server takes, but not
  how any one service answers.
- The experiment tools (`evals/run.py`) use the local plug only, because
  they ask Ollama itself for the model's fingerprint. With the cloud plug
  set (`LEDGER_HAND_MODEL_PLUG=cloud`) they refuse to start, before anything
  is sent, and say so with exit status 2. Unset it, or set it to `local`,
  before running an experiment.

## How it works, part by part

**The rules of one trade.** `src/ledger_hand/core/` knows what a trade looks
like and which rules it has to keep. Hand it a draft, the coin table and the
current moment, and `check_draft` returns either a finished record or two
lists: what is still missing, and what breaks a rule. A draft that names two
of quantity, price and total gets the third calculated; an unknown coin has
to be confirmed first; the fee has to be stated even when it is zero; nothing
dated in the future is accepted, and neither is a moment whose offset from UTC
has seconds in it (some zones had one before the 1970s). The limits of the ledger (digits, lengths,
tolerance) are copied into one file and applied the way the ledger applies
them.

**Numbers as people write and say them.** `read_number` turns a short piece
of text into an exact decimal: "94,900", "1.2k", "3w", "8万刀", "两万三",
"9万4", "零点五". A unit that came with the number is handed back as written,
but only a unit made of words the program knows: the words for USDT, the
coins in the coin table, a few counters such as "个", and any word the caller
allows for that one call. When the text has more than one reading ("1,5",
"一亿五千"), names no single exact amount ("8万到8万5", "大概两万", "半个"),
has more digits than the ledger holds or carries any other unit ("3个w",
"2 thousands", "100 sats", "5毛"), the answer is "unsure" with a reason, never
a guess. `write_number` goes the other way and writes an exact decimal the
way the ledger accepts it.

**Times as people say them.** `read_time` turns a short piece of text into a
definite time, given the current moment and the time zone, both handed in by
the caller: "刚才", "3 小时前", "昨天晚上 9 点 40", "上周五下午三点", "last
Friday 3pm", "Oct 2", "15:05:30". A date said gives a day, and so does a day
with only a half of it ("昨天晚上", "Friday night"), with a caution; a clock
time gives the minute, or the second when seconds were said. Spans back from
now count real elapsed time, so they stay right when the clocks change; day
words, weekdays and dates count calendar days. Every part of the text must be
one the program knows. When the text can mean more than one time ("10/2",
"晚上 12 点", "last Monday" on most days of the week), the clocks skipped
that time, or it lies in the future, the answer says so, never a guess; on
the night the clocks go back, a time shown twice comes back as two
candidates. A date said without its year whose day this year is still to
come ("10月8号" said on 7 October) is ambiguous too: it may mean last year's,
or the day may be a slip, and the program asks instead of picking one. A day
of the month without its month ("8号" said on the 7th) is the same. Only a
day this year (this month) does not have at all, such as 29 February, is
looked for further back. `write_time` writes a time the way the ledger takes
it: a date, or a moment with its seconds and offset.

**A file the ledger accepts.** `export_backup` in `src/ledger_hand/export/`
writes saved trades as the text of a backup file in the ledger's own format
(backup format 3, ledger schema 5): the trades, in the order they happened,
and a card for every coin they use, with its full name and Binance market
taken from the coin table. A saved trade (`core/stored.py`) is a finished
record with the identifier and the creation and change moments that saving
gives it. The same trades always give the same bytes. The caller hands in
today's date, and the ledger is meant to be given the same one. Nothing is
written when there is no trade; an identifier is empty, too long or used
twice (compared the way the ledger compares text); a coin is missing from the
coin table; a trade's time has an offset from UTC with seconds in it (the
ledger cannot write it; the check of a draft already refuses one, and this is
a second guard); a trade's
date, in its own zone, is after today; or there are more coins, trades or
bytes than one ledger file may hold. The answer lists every such issue
instead. A time zone name is taken only when it is spelled exactly as the
zone database lists it.
`backup_file_name` names the file, with the word `incremental` in it: the
ledger's present import replaces the whole ledger, and a file of a few new
trades must never be taken for a full backup. A golden sample, a committed
export that the export must reproduce byte for byte, records what this format
looks like, and the ledger tier of the checks has the ledger's own validator
judge it (see "The ledger tier").

**Talking to a language model.** The rest of the program will only ever
talk to the model port in `src/ledger_hand/ports.py`: send a list of
messages, optionally a JSON schema the reply has to follow, and the sampling
parameters; get back the reply's text and a short record of the call (which
model answered, how long it took, how many tokens it read and wrote, and
whether it stopped by itself or was cut off at the length limit). A second
call shows the model pictures: the same messages, with one or more PNG or
JPEG pictures on the last one, the user's, and no schema. Two
plugs, in `src/ledger_hand/llm/`, sit behind it. The local plug, the
default, talks to a local Ollama server through its own chat endpoint; the
cloud plug talks to the OpenAI-style chat endpoint most cloud services
offer (see "Switching to a cloud model"). Both wait for the whole
reply. `connect_model(load_model_settings())` builds the plug the settings
choose. Every failure is one `ModelError` with one of six kinds:
`unreachable` (nothing answers at the address: the server is not running,
or the name does not resolve), `timed_out`, `model_not_found`,
`rate_limited` (with the wait the server asked for, when it said),
`server_error` (also for anything no other kind fits, with the raw status
and the start of the answer attached) and `malformed_reply` (not JSON, a
field missing, empty text, too long, not valid text). No odd answer makes a
plug raise anything else or wait without end. Timed out, rate limited and
server error are tried again a few times, with waits that double each time;
a server that says how long to wait (its Retry-After header) is waited for
that long instead, up to a minute, and one that asks for longer is not
waited for at all. A request the server turns down as wrong, with a status
from 400 to 499 other than 429 (a key refused, a field not taken), is not
tried again: it would be turned down again. Pictures go through the local
plug only, in Ollama's `images` field; the cloud plug refuses a call with
pictures before sending anything, naming `LEDGER_HAND_MODEL_PLUG`, and
`connect_vision_model` builds the local plug with the vision model the
settings name. Whether the model thinks before it answers is a setting of
the local plug, sent as Ollama's `think` field when it is on or off and left
out by default; the cloud plug never sends it. What the reply's text says is
not checked here: a model reply is untrusted input, and whoever asked
checks it. A small function asks the local server for its version and the
model's fingerprint, for the records of an experiment.

Where the model is, which one, its key and the default parameters are
settings read from environment variables (see "Model settings");
`src/ledger_hand/settings.py` is the only place in the package that reads
them. A key is never printed and never appears in an error, not even when
a server writes it back escaped as JSON, percent-encoded or as HTML.

**A passage becomes drafts.** `extract` in `src/ledger_hand/extraction/`
takes a passage as typed, a model port, the current moment, the time zone's
name and the coin table. The model does one thing only: it copies phrases
out of the passage into a flat table, one row per trade, each cell a piece of
the passage or empty. The program does the rest. Every phrase must be a
piece of the passage (compared after tidying width and runs of whitespace,
and never cutting a number in two), or the field stays empty; the piece, the
user's own writing, is what goes on. Numbers and times are turned into values
by the core's rules, and whatever the core is unsure of, cannot read, finds
ambiguous or in the future leaves the field empty with the core's reason. A
comma written full width ("，") ends a number unless the core's number
reader reads both sides together as one number it is sure of: "94，900" is
one number, "63,000，1.5" is two, and so is "1，5" (1 and 5, not 1.5). A
unit written with a price, total or fee names its currency when that field
was left empty. Every draft keeps the whole passage as its original text.
What comes back is the drafts and a list of issues: every field left empty
and why, every value kept with a caution, every row left out, and the
numbers of the passage no trade used, since a trade may be missing. A reply
that is not the table makes the program ask again, as often as the caller
allows; a failure of the model port is handed back as it was raised. An
empty passage, or one longer than the ledger keeps, is never sent. The
prompt (`extraction/prompts/first.py`) is its first version, with its
invented examples in a file beside it. `scripts/try_extraction.py` tries it
by hand with the real model.

**Measuring how well the model reads.** `evals/` holds the yardstick: 50
invented test sentences with gold answers (30 to tune against, 20 kept back
for the last run of an experiment), the scoring and a runner. The gold
answer says what the drafts of extraction should hold, field by field. The
runner sends every sentence of a set through extraction, with the
sentence's own fixed moment and zone, saves each result the moment it is
done, and scores the run: how often the reply could be read at all, each
field, whole trades right (the main score), trades missed and extra, values
made up, and passages with no trade. Every field that came out wrong is
sorted into its kind: left empty by the program with a reason, left empty
because the model gave nothing, a wrong value with or without an issue about
it, or a value made up. The results of each run are in `evals/results/`,
and `evals/RESULTS.md` records them; the first is the baseline of the first
prompt with `qwen2.5:7b` on the debug set.

**Comparing prompt versions.** Four more versions of the extraction prompt,
each one technique away from the first (no examples, a role, a written
step-by-step analysis, one more rule on price and total), were run on the
debug set and on a small set of hard ways of writing a number, side by side
with the first; a rule fixed beforehand picked one version, and only that
one ran the final set, once. Two more versions, written for the owner's
way of writing, were measured later on the debug, voice and writings sets;
the rule fixed before them picked neither, so the final set was not run for
them. One more, written after their errors, was picked by the rule fixed
before it, ran the final set once and did not pass it. `evals/RESULTS.md`
has the tables. The product still records passages with the first prompt.

**Splitting a passage first.** `split_then_extract` in
`src/ledger_hand/extraction/splitting.py` is the other way to read a passage
that reports several trades: the model first copies out the pieces of the
passage each trade needs (prompt `split-1`), the program builds one segment
per trade from the passage's own text, each segment goes through `extract`
on its own, and the rows of all of them are read once more against the
whole passage. When the split lists fewer than two trades, or goes wrong
(a piece that is not a piece of the passage, a reply that cannot be read),
the whole passage is extracted once, as without splitting. It was measured
against the one call on the debug set; a rule fixed beforehand compared the
two, and `evals/RESULTS.md` has the tables. The product still reads a
passage in one call.

**Judging a passage first.** `screen` in
`src/ledger_hand/extraction/screening.py` asks the model which kinds of thing
a passage reports, from one fixed list: a filled spot trade, futures or
leverage, one coin swapped for another, an order not filled yet, and a plan.
Each report comes with the words of the passage that show it, quoted only
when they really are a piece of the passage. The program decides what
follows: a passage that reports only the kinds the ledger does not record is
stopped, with the reason for each; one that reports nothing has no trade;
one that reports a filled spot trade goes on to extraction, and anything
else it reports is set aside as a caution. The prompt
(`extraction/prompts/screen.py`) gives no example at all.

**Asking about what is missing.** `core/followup.py` says what to ask next
about a draft the check did not pass, from one fixed order of every problem
the check can name: a cell to ask for, a coin word to confirm, which of
several cells is wrong (quantity times price not matching the total; a fee
in the bought coin not below the quantity), or that the trade cannot be
recorded and why (the coin is USDT, or the trade is priced in another coin).
The model words each question as a meticulous bookkeeper
(`src/ledger_hand/asking/`), behind a label of the program's own that says
which trade and which field is asked about; when the model fails, or writes
anything but one plain question, or brings in a number, a coin or a word
that is not among the facts, the program's own sentence is used. An answer
is read by rules first (`extraction/answer_phrase.py`): a number, a time with
the passage's own moment and zone, a coin, and short fixed word lists for
buy or sell, yes or no, "no fee", "skip", "cancel" and which cell is wrong.
Only when the rules cannot read the whole answer is the model asked to copy
the one piece of it that gives what was asked; the piece must be a piece of
the answer, and it is read by the same rules. An answer that cannot be used
gets the same question again, with the reason.

**Recording a passage.** `src/ledger_hand/flows/recording.py` strings all of
this together: judge the passage, extract its trades, check each one, then
ask one trade at a time and one field at a time, put each answer back and
check the trade again, until every trade is a record, skipped or impossible
to record. Each step hands back the whole state as one value that never
changes (`flows/progress.py`): the stage, every trade, the question waiting,
the records, why the passage was stopped, the reminders, which prompt
versions were used, and whether a record can still be removed or the whole
passage dropped. A record can be removed once every trade is settled, even
one that was complete from the start, so a wrong value seen in the records
can be kept out. When the model fails while judging or extracting, nothing
is kept. `scripts/record_trades.py` runs it at the command line (see
"Recording trades by hand").

**A passage from a screenshot.** `read_picture` in
`src/ledger_hand/extraction/picture_reading.py` shows the vision model one
screenshot with the zero-shot prompt `read-1` and hands back the text it
reads, or why there is none: the model failed, or the reading was cut off at
the longest reply, which is never passed on as if it were whole. What it
reads cannot be checked against the picture: there are no words of the
person's own to compare it with (see `docs/known-gaps.md`).
`src/ledger_hand/flows/screenshot.py` joins the text read and the note typed
beside it into one passage, the text first, and starts it as a typed
passage is started, with the model that extracts; the reading's call and
prompt come first in the state it hands back, and a screenshot that was not
read ends the passage there, at the step "reading the screenshot". Each
draft keeps the joined passage as its original text, and a fact in the note
fills what the screen left out. `scripts/try_screenshot.py` tries it by hand
(see "Trying a screenshot by hand"). On the Record page,
`src/ledger_hand/flows/uploading.py` checks an uploaded file first, step by
step (the plug, the size, a PNG or a JPEG by its first bytes, the vision
model on the server), and has it read; the person then sees the text read,
can change it, and joins it with the note (see "Recording from a
screenshot").

**Keeping the records.** Saved trades are kept in the book: one SQLite file
of this program's own, behind the storage port in `src/ledger_hand/ports.py`
(save the trades of one passage, say whether a passage was saved before,
list the saved trades, mark trades as exported, list the coins the user
confirmed). The one plug, in `src/ledger_hand/storage/`, uses Python's own
`sqlite3`. Each trade is kept field by field: numbers and times as the ledger
writes them, as text, never as floating-point numbers, so a trade read back
is equal to the one saved, down to which amount was worked out; bookkeeping
moments in UTC to the microsecond. The book carries its own version number
(1 today) and a mark that says it is this program's, both in the file's
header, and both are read before anything else: a file that is newer than
this program, not a database or not this program's book is refused, and not
one byte of it is written; a missing or empty file becomes a new book, with
its folder. There is one exception: a write cut off part way (the process
killed, the power lost) leaves SQLite's journal beside the book
(`ledger-hand-book.sqlite3-journal`), which the read-only first look cannot
roll back. When that is the only reason the book cannot be read, and the
file's first 100 bytes, read straight from the disk, show SQLite's header
with this program's mark and a version it knows, the book is opened once
for writing so that SQLite itself rolls the write back and removes the
journal; then it is checked again from the start, and a refusal then says
that SQLite rolled a write back first. The journal itself is not read, so a
journal another book left beside it is rolled back all the same (see
`docs/known-gaps.md`). Any other file with a journal beside it is refused as
before, and neither file is written to.
Numbered upgrade scripts (`storage/upgrades/`) bring an older
book up to date, one transaction each, and are never changed once
committed; neither is the golden sample of each version
(`tests/storage/golden/`). Every failure of the book is one `StorageError`
with one of eight kinds (newer version, not a database, not this program's,
damaged, locked, inaccessible, conflict, unexpected); nothing of `sqlite3`
leaks out. Each operation opens the book and closes it again.

`flows/saving.py` saves the final records of a passage, only when the person
asked for it: each gets a new identifier (`hand-` and a random UUID) and the
moment of saving; the coins the user confirmed that the saved trades use are
kept with them, in the same transaction, and a coin confirmed for a trade
that was then left out is forgotten. When a book is handed to the recording
of a passage, the passage is first looked up by its fingerprint (a digest of
the passage with spacing and character width made uniform): an earlier save
of it is shown as a reminder, with its date and number of trades, and holds
nothing back; and the coins confirmed and saved before are known.

`flows/exporting.py` writes the saved trades not exported yet into a new
file in the exports folder, with `export_backup` (the export moment is the
current moment, and today its date in the person's time zone) and
`backup_file_name`, then marks them as exported, with that moment. A refusal
writes nothing and marks nothing, and says every reason; with nothing new,
nothing is written. The file is written under a temporary name first and
only then given its real one, in a way that never replaces a file of that
name: two exports in the same second would be given the same name, and the
second then writes nothing and marks nothing. A file and the book cannot be
changed together in one step, so the order is chosen for what an
interruption leaves behind: the file is written first and its trades marked
after. Cut off in between, the result is a file whose trades are not
marked, and the next export writes them again, which the person can see;
never trades marked as exported with no file, which would lose them.

**The interface.** `src/ledger_hand/ui/` is three Streamlit pages. The
Record page has a chat on the left and, on the right, a table of what will
be recorded (see "Starting the interface"). A passage typed in the chat is
recorded as above; each question comes back in the chat with its label, and
the answer is typed in the same box. The table has one row per trade, with where it stands
(complete, asking, left out, or cannot record and why), its time, coin,
side, quantity, price and total side by side, fee and fee coin, platform and
note; the amount the program worked out is marked once the trade has passed
the check. Each row has a "Don't save" button, and under the table are
Save and "Discard all"; each can be pressed only when the flow offers it.
Save keeps the records in the book and empties the table. A new passage
typed while the last one is settled but neither saved nor discarded is not
taken: the page says so and offers the two choices. Under the chat, a
screenshot can be uploaded instead: the text the vision model reads off it
is shown in a box to be checked and changed, beside a note, and Continue
records the two as one passage, as if typed. The interface decides nothing
itself: what to ask, whether a passage is settled, whether it can be saved
and which trade can be left out all come from the flow's progress, and
whether a screenshot can be read, and why not, from the upload flow. It
gets the model, with the local plug the vision model and a way to ask the
server whether it has it, the book, the clock and the machine's zone from
one wiring module, `src/ledger_hand/wiring.py`, the only place in the
package that reads the machine's zone (with tzlocal).

Under the table, Export writes the saved trades not exported yet into a new
file, says where and how many, and marks them; beside it, always, a line in
red says not to import that file into the ledger yet. The second page,
Settings, lists every model setting with its value now, its default and why
the default is what it is, and lets every one but the key be changed for
the browser tab. Every failure, from a model nobody answers to a book
written by a newer version of the program, is said in one plain sentence
that says what happened and what can be done, and nothing breaks. A passage
saved before is reminded of, with the day and the number of trades, and a
fee paid in a third coin, which the ledger leaves out of the cost, is
pointed out in its row and in the chat; neither holds anything back.
The third page, Assistant, is the assistant's chat, with the program's
tables under each reply and a card for each proposal it sent (see "The
assistant page"); what to do with each thing said, and where a proposal
stands, come from the flows.

Apart from asking the model, keeping the book and drawing the page, all of
this is pure computation.

The repository also has its Python environment, one command that runs every
check, and two guardrails that keep the code base in shape (the layering
check and the hygiene scan).

## What is where

| Path | What it is |
| --- | --- |
| `pyproject.toml` | Package metadata and the configuration of every tool (pytest, ruff, mypy). |
| `requirements.txt` | Exact versions of the run-time dependencies (httpx, Streamlit, tzlocal, and what Streamlit brings with it) and the development tools, so the environment can be rebuilt identically. |
| `.streamlit/config.toml` | Streamlit's settings for the interface: no usage statistics, listen on this machine only, start without questions at the terminal, no developer options (and so no Deploy button) in the menu. Read from the folder Streamlit is started in. |
| `src/ledger_hand/` | The package. Today it holds its version, `core/`, `export/`, the ports file, the settings, `llm/`, `storage/`, `ledger/`, `extraction/`, `asking/`, `assistant/`, `flows/`, the wiring module and `ui/`. |
| `src/ledger_hand/core/` | Core rules: pure computation, no network, files, database, user interface or clock. Holds the shapes of a trade (`trade.py`), the coin table (`coins.py`), the ledger's limits (`ledger_limits.py`), exact decimal arithmetic (`arithmetic.py`), the reading and writing of numbers (`numbers.py`), the reading and writing of times (`timeparse.py`, with the wording of a time phrase in `time_wording.py`), a stretch of time named in words (`time_range.py`) and the check of a draft (`validation.py`), what to ask next about a draft (`followup.py`), a saved trade (`stored.py`), what the book keeps beside it (`book.py`), the form a passage is compared in (`passage_form.py`), which time zone names are taken (`zones.py`), whether the ledger counts a trade's fee in the cost (`fee_cost.py`), and what the ledger port hands back (`ledger_records.py`, `proposals.py`). |
| `src/ledger_hand/export/` | The ledger's backup format: the whole file (`backup.py`), one trade (`trade_entry.py`), one coin (`coin_card.py`), bookkeeping moments (`moments.py`) and the file's name (`file_name.py`). Writes no file itself. |
| `src/ledger_hand/ports.py` | The three ports. The model port: messages, pictures, tools, parameters, the reply and its record, and the error with its six kinds. The ledger port: the person's ledger as the assistant reaches it, and the error with its four kinds. The storage port: its operations and the error with its eight kinds; the shapes it takes and gives are in `core/book.py`. Only shapes; it sends and stores nothing. |
| `src/ledger_hand/settings.py` | The only place in the package that reads environment variables: the model settings, their defaults and their checks, what each sets and why its default is what it is (as data, `ABOUT`), changes from the settings page read the same way (`apply_changes`), and where the data is kept. |
| `src/ledger_hand/storage/` | The SQLite plug for the storage port (`sqlite_store.py`): opening a book, its version and its mark (`book_file.py`), a trade as a row and back (`rows.py`), SQLite's failures as the port's kinds (`failures.py`), and the numbered upgrade scripts (`upgrades/`). The only part that may import sqlite3. |
| `src/ledger_hand/llm/` | The plugs for the model port. The local plug (`ollama.py`), what it sends (`ollama_request.py`) and how what comes back is read (`ollama_reply.py`); the cloud plug (`cloud.py`), what it sends (`cloud_request.py`) and how what comes back is read (`cloud_reply.py`); what both share in writing a request (`request_body.py`) and reading a reply (`reply_json.py`); one HTTP exchange and how its failures are sorted (`exchange.py`), making a server's words safe to show (`error_text.py`) and finding the key in them however it was written back (`key_forms.py`), reading how long a server asks to wait (`retry_after.py`), trying again (`retry.py`), the plug the settings choose, checked and assembled, and the plug that reads a screenshot (`connect.py`), the assembled local model alone (`local.py`), and the local server's version and the model's fingerprint (`ollama_identity.py`). The only part that may import httpx. |
| `src/ledger_hand/extraction/` | A passage to drafts: the entry point (`extractor.py`), the table the model fills (`reply_table.py`) and how its reply is read (`reply_parser.py`), finding a copied phrase in the passage (`passage.py`) and the numbers written in a text (`passage_numbers.py`), one row to one draft (`row_draft.py`), which currency a unit names (`unit_currency.py`), the issues (`issues.py`), the messages a prompt version makes (`prompting.py`), and the prompt versions with their examples (`prompts/`). Also the check of a passage before it is sent (`passage_check.py`), judging a passage (`screening.py`, with the list the model fills in `screen_table.py`), reading an answer to a question (`answer_phrase.py`, with its word lists in `answer_words.py` and what the model copies in `answer_table.py`), splitting a passage first, for experiments (`splitting.py`, with the pieces the model copies in `split_table.py` and the segments made of them in `segments.py`), and reading a screenshot out as text (`picture_reading.py`, with the shape of its prompt in `picture_prompt.py`). Reads no clock, no zone of the machine and no environment variable. |
| `src/ledger_hand/ledger/` | The plugs for the ledger port: the fake ledger (`fake_ledger.py`), an invented book in memory (`invented_book.py`) with its own way of working out cost and profit (`moving_average.py`, `fake_sums.py`); and the real ledger's plug (`link_ledger.py`) over its assistant link (`link_client.py`, `link_failures.py`, `link_tools.py`), the program's one link kept by `link_keeper.py`. |
| `src/ledger_hand/assistant/` | What the assistant's model is handed: the eight tools (`tools.py`) and the system prompt (`prompting.py`, `prompts/`); judging each tool call (`judging.py`); whether a lookup's asset and side are ones the user asked for (`narrowing.py`); what a read tool found and its table (`lookups.py`); whether the model's words may be shown (`explanation.py`); what is handed back for one (`results.py`); how a turn went (`outcome.py`); judging a change or a deletion (`edit_calls.py`), reading its new value and putting it into the trade (`new_values.py`), reading which trade or which amount the user picks (`picking.py`), and the program's words and tables for it (`edit_words.py`). |
| `src/ledger_hand/asking/` | Wording a follow-up question: the facts, the model's sentence and its checks (`question_text.py`), the program's own sentences (`templates.py`) and the prompt (`prompts/bookkeeper.py`). Imports only `core/` and the ports file; reads no clock. |
| `src/ledger_hand/flows/` | Recording a passage from start to records (`recording.py`), or from a screenshot and a note (`screenshot.py`), with the checks made on an uploaded screenshot before it is read (`uploading.py`): the state it hands back (`progress.py`), putting a question together (`questions.py`) and putting an answer back (`filling.py`). Saving the records (`saving.py`) with new identifiers (`identifiers.py`), a passage's fingerprint (`fingerprint.py`), the confirmed coins between the book and the coin table (`coin_book.py`), and exporting (`exporting.py`) into a new file that never replaces another (`export_file.py`). One turn of the assistant (`assisting.py`), asking the ledger through its read tools (`asking.py`), changing or deleting one trade (`editing.py`), each thing said to the assistant (`conversation.py`), and where a proposal stands, with the demo ledger's save and reject (`standing.py`). |
| `src/ledger_hand/wiring.py` | The wiring module: builds the model, with the local plug the vision model and a way to ask the server whether it has it, the book, the coin table, the clock and the machine's zone, the demo ledger and how many steps the assistant may take, from the settings, with the settings page's changes put in, for the interface to hand to the flows. The only part of the package that may import tzlocal. |
| `src/ledger_hand/ui/` | The interface, three Streamlit pages: the entry (`app.py`), the Record page (`record_page.py`) with the chat (`chat.py`), the table and its buttons (`preview.py`), Export (`export_panel.py`) and the screenshot area under the chat (`screenshot_panel.py`); the Settings page (`settings_page.py`) and its inputs (`settings_form.py`); what happens on a message, an upload or a click (`turns.py`), what the program says (`sayings.py`), the plain sentence for every failure (`failure_words.py`), a setting's value as it is shown (`setting_text.py`), the last word after Export or a change of setting (`notes.py`) and what is kept between reruns (`session.py`); the Assistant page (`assistant_page.py`) with its chat and the tables and buttons under each reply (`assistant_view.py`, `assistant_tables.py`, `assistant_how.py`), its proposal cards (`assistant_cards.py`), what happens on its messages, buttons and uploads (`assistant_turns.py`), how it writes a number (`assistant_numbers.py`), its sentences for failures (`assistant_failure_words.py`), what it keeps between reruns (`assistant_session.py`), which ledger a tab reaches and the one assistant link every tab shares (`assistant_ledger.py`), the block that chooses it and starts the link (`assistant_link_panel.py`) and what it says about the link (`assistant_link_words.py`). The only part that may import Streamlit. |
| `tests/` | The tests. `tests/core/`, `tests/export/`, `tests/llm/`, `tests/extraction/`, `tests/asking/`, `tests/storage/` and `tests/flows/` have one test module per module, or more; `tests/llm/` also has a fake Ollama server, the pieces of a fake cloud service and a batch of attacks on each plug, and `tests/extraction/` a batch of attacks on extraction. `tests/storage/` runs the same tests of the storage port against the SQLite plug and the in-memory stand-in, and holds the golden book. `tests/flows/` also tests the scripts for recording trades and for trying a screenshot. `tests/ui/` runs the pages headless with Streamlit's own test runner, against fake models and a book in a temporary folder (Export, the settings page, a screenshot uploaded, every failure, the reminders), checks the plain sentence for every failure, and checks the settings file. `tests/evals/` tests the experiment kit and the test sentences. |
| `tests/conftest.py` | Stops every test that is not marked `live_model` from reaching the network. |
| `tests/fakes/` | Stand-ins for the outside world: a scripted model that plays back replies and errors in order and records what it was asked, a model that answers each kind of call (judging, extraction, wording a question, reading an answer, reading a screenshot) from its own script, and a book kept in memory that can be made to fail. |
| `tests/live/` | The live check, which talks to a real model, the small schema check it uses, the smoke test of extraction, the check of judging the debug set, the smoke test of the page, the check of the settings page against an address nobody listens on, one call of the cloud plug to the local Ollama's OpenAI-style endpoint, a model the server does not have asked for through both plugs, a run that names a model the server does not have, a plain picture read by the vision model, and thinking off taken by the server; the assistant's checks (`test_live_assistant.py`, `test_live_conversation.py`) and the sentences for a demo (`test_live_demo_sentences.py`, with `demo_sentences.json`); and one test that needs no model, run by the quick tier, which keeps the README's sentences for a demo and that file the same (`test_demo_sentences_readme.py`). |
| `tests/export/samples.py`, `tests/export/attack.py`, `tests/export/golden/` | Invented trades to export, batches of edge cases made to find where this program and the ledger part ways, both shared with the ledger tier, and the golden sample. A golden sample is never edited once committed; a new format version gets one of its own. |
| `tests/guardrails/` | The layering check and the hygiene scan, the tests that prove they catch what they should, and the two gate tests that apply them to this repository. |
| `scripts/check.sh` | One command that runs all checks. |
| `evals/` | The experiment kit, outside the package: the test sentences and their gold answers (`sets/debug.json`, `sets/final.json`, read by `gold.py`), what they cover (`coverage.py`), the small set of hard ways of writing a number (`sets/writings.json`, described by `writings.py`), the ten passages in the owner's own voice (`sets/voice.json`, described by `voice.py`), judging one field (`cells.py`), pairing drafts with gold trades (`matching.py`), the scores (`scoring.py`), the results file (`records.py`), the summary and its tables (`tables.py`), the runner (`run.py`), the summary worked out again (`summarize.py`), three more counts beside the summary (`extra_counts.py`), prompt versions side by side with the rule that picks one (`compare.py`), prompt versions side by side on each set with the rule that picks a candidate over `first` (`compare_sets.py`), two runs compared sentence by sentence (`same_replies.py`), the two ways of reading a passage (`methods.py`) side by side with the rule that picks one (`compare_methods.py`), two models side by side on one set (`compare_models.py`), and the record of every reply read for a passage (`reads.py`), and the assistant's measures: its first step (`tool_set.py`, `tool_run.py`), asking the ledger (`ask_set.py`, `ask_run.py`), changing or deleting a trade (`sets/edits.json`, `edit_set.py`, `edit_run.py`), recording a share bought with dollars (`sets/stocks.json`, `stock_set.py`, `stock_run.py`), picking an asset named the way people say it from the ledger's list (`sets/stock_names.json`, `name_set.py`, `name_run.py`), the extraction sets run through the start of recording, judging and all (`judged_run.py`), and the exam said the owner's way: its ten sets (`sets/spoken/`), their gold answers and checks (`spoken_set.py`), the exam book (`exam_book.py`), judging each trade (`spoken_judge.py`), the counts (`spoken_tally.py`), its runner (`spoken_run.py`) and the log of every run of a hidden half (`hidden_runs.py`, `tool_results/hidden-runs.log`). |
| `evals/results/` | One results file per run (`*.jsonl`) and its summary (`*.summary.json`). In Git: all of it is invented data. |
| `evals/tool_set.py`, `evals/tool_run.py`, `evals/sets/tools.json`, `evals/tool_results/` | The assistant's nineteen sentences, the measure of the model's first step on each, its runner and its results. |
| `evals/ask_set.py`, `evals/ask_run.py`, `evals/sets/asks.json` | The questions about the ledger with their gold answers, how one answer is judged, and the runner that runs each to the end; its results go to `evals/tool_results/` too. |
| `evals/RESULTS.md` | The results record: what each run measured, with the tables its results file gives. |
| `scripts/try_extraction.py` | Try extraction by hand: a passage in, the drafts, the issues and a record of each call to the model out (see "Trying extraction by hand"). |
| `scripts/try_screenshot.py` | Try a screenshot by hand: a picture and a note in, the text read, the passage, the drafts and a record of each call out (see "Trying a screenshot by hand"). |
| `scripts/try_assistant.py` | Try the assistant by hand: one or more sentences in, every step, what reached the ledger and the last words out; records a trade, asking what is missing (see "Trying the assistant by hand"). |
| `scripts/record_trades.py` | Record trades from a passage at the command line, one question at a time (see "Recording trades by hand"). |
| `scripts/ledger_check.py`, `scripts/ledger_validate.ts`, `scripts/ledger_offsets.ts` | The ledger tier of the checks: sample files judged by the ledger's own validator, and the ledger's offsets compared with ours. |
| `tests/ledger_check/` | What the ledger tier checks (`cases.py`), tests of the tier's own logic, and the one sample for it written by hand. |
| `docs/architecture.md` | How the layers are divided, who may import whom, the house rules, and where new features go. |
| `docs/known-gaps.md` | Known limits of the program as it stands, each with what it affects and, where a choice is needed, waiting for the project owner. |
| `docs/project-report.md` | The project described for a reader new to it: the problem, the steps, the prompt techniques, the parameters, the error handling, the experiments, the design decisions, the known limitations, and the course's checklist mapped onto the repository. `tests/test_project_report_paths.py` checks that every path it names is in the repository. |
| `tests/storage/golden/` | The golden book of version 1, a SQLite file, and its text dump. Never edited once committed; a new version of the book gets one of its own. |
| `tests/flows/golden/` | The golden assistant's record of version 1: four invented entries. Never edited once committed; a new version of the record gets one of its own. |
| `data/` | Not in Git. The data folder by default: the book (`ledger-hand-book.sqlite3`), the export files (`exports/`) and the assistant's record (`assistant-record.jsonl`). Created when first written to. |
| `.venv/` | Not in Git. The local Python environment. |

A folder or file is created by the change that first needs it;
`docs/architecture.md` lists them all under "Layout".

## Changing the development tools

Dependencies are declared in `pyproject.toml` and pinned in
`requirements.txt`. After changing them, rewrite the pin file from the
environment:

```sh
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pip freeze --exclude-editable > requirements.txt
```

`--exclude-editable` keeps this package itself out of the file; without it
the file would carry the absolute path of your checkout.
