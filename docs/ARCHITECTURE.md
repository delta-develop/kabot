# Architecture

## What this is

A brain that only knows how to talk. **Memory as a service.**

Elephant stores conversations, compresses them, and answers one question on demand:

> *A message is about to arrive. What should I put in the prompt, without exceeding N tokens?*

```
GET /sessions/{id}/context?q=<message>&budget=2000
```

It does not know what business it serves. The domain and the channel belong to whoever
consumes it — never to the core.

---

## The architecture

### Four layers, one question

The layers are not four features. They are four answers to the same question: *how do I
spend fewer tokens without forgetting?*

| Layer | Answer | Store |
|---|---|---|
| **Working** | the last turns go in verbatim — they are few and cheap | Redis |
| **Summary** | the middle gets compressed | MongoDB |
| **Facts** | what endures gets extracted and kept small | MongoDB |
| **Episodic** | the rest is archived and **indexed to retrieve only what applies** | Postgres + pgvector |

### Three stores, three access patterns

Not polyglot persistence for show. Each store is chosen for how its layer is read and
written.

| Store | Pattern |
|---|---|
| **Redis** | volatile, ordered, discarded when the session closes |
| **MongoDB** | documents replaced whole — facts and summary are `$set`, never appended |
| **Postgres + pgvector** | a log that grows forever and must be searched by similarity |

MongoDB is good at replacing a document. The episodic log is the opposite: it only grows,
and it has to be queried by meaning. That is a different job.

That argument justifies *a* document store. It does not justify *a separate managed
service*, and on that second question MongoDB does not survive — it is inherited, and
*Where the cost goes next* is where it comes out.

### The budget is the product

Every response proves it respected its own ceiling:

```json
{
  "budget": 2000,
  "used": 1847,
  "system_tokens": 198,
  "message_tokens": 14,
  "blocks": [
    { "source": "facts",   "tokens": 120, "content": "..." },
    { "source": "summary", "tokens": 310, "content": "..." },
    { "source": "recall",  "tokens": 527, "content": "..." },
    { "source": "working", "tokens": 890, "content": "..." }
  ]
}
```

**The invariant: `used` never exceeds `budget`. Ever.**

An episodic layer that fires and dumps the whole history into the prompt has an unbounded
worst case, which is disqualifying in a system whose thesis is token efficiency. The
ceiling is what makes the thesis checkable on every single response instead of on average.

`budget` covers **memory**, not the full prompt. The system instruction and the user's
message are reported separately so nobody has to guess.

### Spending order is not reading order

The budget is **spent** by priority:

```
facts → summary → working → recall
```

The prompt is **rendered** in reading order:

```
facts
summary
recall      ← older memories, chronological, with their dates visible
working     ← the live conversation
<user message>
```

Working memory sits next to the question because it is the immediate context. Recall comes
before it because it is old memory — the model should read it as background, not as what
just happened.

### Cosine ranks the topic; a noul ranks the help

pgvector returns the `k` nearest fragments by cosine similarity, which ranks a fragment
by what it is *about*. Measurement 1 below is the evidence that this is not the same as
whether it **answers the question**.

So a second pass asks one narrow question per candidate — *would putting this excerpt in
front of the assistant change or improve its reply?* — and gets back a probability
between 0 and 1. Every candidate travels in a single request and each one gets its own
question, so the hot path pays one round trip, not `k`.

Both numbers then travel with the fragment, in the API response and on screen. Measured
on a freshly seeded subject:

```
similarity 0.3466   usefulness 0.77   ← the beef-broth story
similarity 0.1760   usefulness 0.03   ← the passport distractor
```

On a corpus polluted with a stray test session the gap opens further. That session is a
near-paraphrase of the question, and it scores **0.7621 by cosine — the highest fragment
in the block — against 0.64 by usefulness, below a fragment cosine ranks at 0.3384 and
usefulness puts first at 0.88.** Cosine ranks the echo of the question highest. The noul
ranks the fact that answers it highest.

**Only the order changes. Nothing is filtered.** Filtering needs a threshold, a threshold
needs a distribution of nouls that does not exist yet, and the budget ceiling already
decides who gets cut.

This is a dependency that is allowed to fail. With `TYPESAFE_API_KEY` unset, or the
service slow past its 1.5 s timeout, the re-rank logs a warning and returns the cosine
order untouched with `usefulness: null` — verified by running it with the key removed. A
clone of this repository with nothing but an OpenAI key gets a working system.

### `turn` is a log by discipline

Nothing in Postgres enforces it. The table is append-only because the code treats it that
way, and that buys a property: **if the embedding model changes, the index can be rebuilt
from the same table with no loss.**

A table with an append-only discipline and a monotonic sequence *is* a log — one that also
has indexes, which is exactly what a log normally lacks.

Kafka becomes the right answer when a second consumer needs to read the same events at its
own pace. Until then, it is a table.

### Consolidation is the sleep phase

Closing a session returns `202` and enqueues. A separate worker drains a Redis Stream:
it builds the turns, embeds them in one batch, writes them to Postgres, merges the summary,
extracts the facts, and only then acknowledges the message.

This is not an optimization dressed up as a metaphor. It is the same division of labour
the brain makes: during sleep, a consolidation process filters the day's experiences and
decides which are worth keeping. The worker is that phase, and running it out of process
is what lets an API restart and a consolidation survive each other.

### Self-auditing is part of the contract

`/context` reports `used`, `budget`, `system_tokens`, `message_tokens` and a token count
per block on every call. That is not a debugging aid left switched on. **A system that
sells a ceiling has to expose the measurement of that ceiling**, or the guarantee is a
claim rather than a contract.

It also defends a subtle invariant. BPE tokenizers merge across boundaries, so
`tokens(a) + tokens(b) ≠ tokens(a+b)` unless each unit ends at a clean break. Every
rendered block therefore ends with a newline, and the test that matters is not
`sum(blocks) == used` — which is self-consistent and can still be wrong — but that `used`
matches the tokenized length of the real prompt. Without that, the invariant this system
sells would quietly understate the true cost while every test stayed green.

---

## Where this sits

**Convergence, not priority.** This is MemGPT's memory hierarchy, arrived at
independently. The decomposition matches, which says the split is where anyone attacking
this problem ends up — not that it is novel.

| | Its position |
|---|---|
| **Mem0** | extracts atomic facts; fused semantic + keyword + entity retrieval |
| **Zep / Graphiti** | bitemporal knowledge graph — *"what was true, and when?"* |
| **Letta** | the agent edits its own memory |
| **Elephant** | **composing context under an explicit token budget** |

*(Landscape surveyed 2026-09-19. This space moves fast — re-check before quoting it.)*

### Why measure anything, when they publish benchmarks

Because the published numbers disagree with each other. Mem0 reports **94.4** on
LongMemEval; an independent comparison reports **49** for Mem0 against **71.2** for Zep —
on the same benchmark.

Nobody is lying. The setups differ. Which is the point: **a number without its method is
marketing**, and that applies to the numbers in this document too.

---

## What the measurements say

Four measurements decide four design choices. **Two of them rule out the idea being
tested**, which is the main reason this section exists.

### 1 · A similarity floor does not separate signal from noise

`RECALL_MIN_SIMILARITY` is `-1.0`: the floor is off. A floor is a minimum score below
which retrieved turns are discarded, so the system would not "remember" something
irrelevant just because it was the least-bad match. It does not work, and this is why.

Measured with real embeddings on a seeded conversation:

```
relevant   [0.2634, 0.3664]
noise      [0.2711, 0.3460]
```

**The ranges overlap completely.** The best distractor beats two of the four relevant
turns. The worst relevant turn scores below every distractor.

A second measurement, different corpus and different language, with three embedding
models:

```
text-embedding-3-small  1536    separation  -0.1639
text-embedding-3-large  1536    separation  -0.1250
text-embedding-3-large  3072    separation  -0.1227
```

A better model barely moves it. **This is not a resolution problem.**

The reason is visible in the data: for the query *"I'm putting together a dinner for six
people — any suggestions?"*, the single most useful turn in the corpus —
*"I've been vegetarian for about a year"* — scores **lowest of everything**, below all
noise. Meanwhile *"the commute to the office is killing me"* scores near the top, because
it shares "work" semantics with the question.

**Cosine similarity measures what a passage is about, not whether it answers the question.**

**What bounds the cost instead** is the budget ceiling, not a relevance threshold. Noise
that fits is cheap; noise that does not fit is cut by the ceiling.

This measurement is also what the re-rank answers — see *Cosine ranks the topic; a noul
ranks the help*. A threshold on the wrong signal cannot work; the fix is to measure a
different signal, not to tune this one.

### 2 · The neighbor window does the work similarity cannot

Retrieving a single matching turn often returns something unreadable:

```
seq 14   user:      "and how was that one?"
         assistant: "honestly, not great"
```

*"That one"* lives in the previous turn. So each hit is returned with its neighbors as an
atomic **fragment** — it enters the prompt whole or not at all.

This matters more than the ranking does. In both measurements, the lowest-scoring relevant
turn only makes sense attached to its neighbor — it would never be retrieved on its own
score. **The window rescues exactly what the ranking loses.**

Two independent samples, different corpora, different languages, pointing at the same
thing.

### 3 · XML tags cost 15% of the budget

Turns render as `User:` / `Assistant:` under `##` headers rather than as XML. Measured
with `tiktoken`:

```
bare content                 31 tokens
<user></user>                41    envelope +10   →  15% of a 2000 budget over 30 turns
User: / Assistant:           35    envelope  +4   →   6%
```

`U:` costs exactly the same as `User:` — both words are a single token — so there is no
reason to abbreviate.

Worse in the recall block: a single turn wrapped with `<recall session="…" date="…">` costs
**60 tokens against 31 of content**. The envelope nearly doubles it.

**So:** plain prefixes, one date line per fragment rather than per turn, and the
`session_id` kept out of the prompt entirely — the model does not need it, and it belongs
in the API response where a developer can see it.

That format is 474 tokens per turn where the XML one is 665, a 29% difference.

> **That 29% is the envelope, not the thesis.** It is what not using XML tags saves. The
> layered-vs-naive comparison is the separate measurement below.

### 4 · Against the naive arm, the win is the ceiling — not the average

`?naive=true` is the control arm: it dumps the subject's entire episodic history into the
prompt with no ceiling at all. Both arms measured on the same freshly seeded subject,
answering the same question:

```
corpus            12 turns across 3 sessions   (./examples/seed-demo.sh)
question          "I'm putting together a dinner for six people this Thursday…"

naive             819 tokens of memory   the whole history, verbatim
layered (2000)    833 tokens of memory   facts 183 · summary 263 · recall 387
```

**The layered arm costs 14 tokens more.** At this size it should. The corpus is small
enough to fit whole, and facts and summary are paid for *on top of* the turns they are
derived from — compression only pays once there is something to compress.

A rendered turn on this corpus costs 68 tokens on average (26 low, 138 high), so the naive
arm passes a 2000-token budget at roughly turn 30 — the seventh session of this length —
and keeps growing forever after that. The layered arm sits at 833 and cannot exceed 2000,
whatever the subject's history holds.

**The claim this system makes is not "fewer tokens". It is "the number you chose, proven
on every response".** A benchmark at demo scale that reported a saving would be measuring
the size of the corpus, not the design.

---

## What it costs to run

### How this kind of estimate is built

A single "cost per user" is not an answer, because the number depends entirely on a
denominator nobody stated. The exercise has five steps, and skipping any one of them
produces a figure that cannot be defended in a room.

1. **Define the unit, and make it pessimistic.** "A user" means nothing. Worse, a
   flattering usage assumption produces a flattering number that collapses the moment
   somebody asks *how often*. Four named profiles are given below and the **heaviest
   realistic one is used as the baseline**, because an estimate that survives scrutiny is
   worth more than one that sounds good.
2. **Separate variable from fixed.** Variable cost is incurred per message and scales
   linearly from zero — here, the API calls. Fixed cost is the cluster, and it is a **step
   function**: the same bill whether one user or ten thousand use it.
3. **Allocate the fixed cost at a stated scale.** `cost per user = variable + fixed ÷ N`.
   Report it at several values of `N`, never one, because the shape of that curve *is* the
   finding.
4. **Treat storage as cumulative.** It only grows, so cost per user rises with tenure.
   Month 1 and month 24 are different businesses.
5. **State what is excluded and run one sensitivity check.** An estimate whose boundaries
   are unstated reads as a promise.

Every input below is either measured on this stack or a published list price, dated. None
is written by hand; `examples/cost-model.py` is the model itself, and changing the profile
re-derives every table on this page.

### What a turn costs, and why it stops growing

Prompt tokens were measured across a real session against a subject that already had
history, so recall fired on every turn — the expensive case, not the flattering one:

```
turn      1      2      3      4      5      6
in    1,103  1,049  1,218  1,427  1,684  1,994
```

**It climbs while working memory fills and then pins against the ceiling.** By turn six
the assembled memory is 1,890 tokens against a 2,000 budget, and every turn after that
costs the same 1,994. That saturation is the whole reason a long conversation has a
predictable price, and it is what the model below extrapolates from.

### Who is using it, and how much

| Profile | Sessions/month | Turns each | Messages/month | Represents |
|---|---|---|---|---|
| Safety companion | 4 | 8 | 32 | incidents and travel only |
| Daily assistant | 20 | 6 | 120 | a few times a week |
| **Support agent** | **22** | **14** | **308** | **every working day, longer threads** |
| Power user | 60 | 12 | 720 | several times a day |

**The support-agent profile is the baseline for everything below.** It is the heaviest
load a normal deployment would see before it stops being a conversational product and
becomes a batch one, and choosing it means no number on this page depends on the user
being quiet.

One session of that profile, all fourteen turns:

```
chat            24,427 tokens in   1,736 out
summary merge    2,367 tokens in     485 out
fact merge       2,326 tokens in     299 out
embeddings       4,032 tokens in
re-rank         13,888 tokens in
```

At list price for `gpt-5.6-luna` ($0.20 / $1.20 per 1M), `text-embedding-3-small`
($0.02 per 1M), and TypeSafe at its quoted $42 per billion input tokens:

```
input        $0.005824    61.2%
output       $0.003024    31.8%
re-rank      $0.000583     6.1%
embeddings   $0.000081     0.8%
──────────────────────────────────
per session  $0.009512
```

### What one user costs, by how much they use it

```
profile            | msgs/mo |  $/month |  $/year | represents
-------------------+---------+----------+---------+------------
safety companion   |      32 | $ 0.0224 | $  0.27 | incidents and travel only
daily assistant    |     120 | $ 0.0862 | $  1.03 | a few times a week
support agent      |     308 | $ 0.2093 | $  2.51 | every working day  ← baseline
power user         |     720 | $ 0.4927 | $  5.91 | several times a day
```

APIs only; the cluster is shared and divided next. **The honest headline is the third
row.** A heavy daily user costs **$2.51 a year in API calls**, and even the power user —
720 messages a month, every month — costs $5.91.

Two things in that split are worth saying out loud. **Output is 32% of the cost while
being 6% of the tokens** — a shorter reply is a cheaper lever than any prompt trim. And
**the re-rank is 6.1%**: a sixteenth of the bill to fix the one ranking problem
measurement 1 says cosine cannot fix on its own.

### The cluster

ECS Fargate, single AZ, no HA, us-east-1 list prices fetched 2026-09-21:

| Line | Spec | $/month | Share |
|---|---|---|---|
| Fargate · `core-api` | 1 vCPU, 2 GB | $35.97 | 20.7% |
| Fargate · `consolidator` | 0.5 vCPU, 1 GB | $17.99 | 10.3% |
| RDS PostgreSQL | `db.t4g.medium`, single-AZ | $47.45 | 27.3% |
| RDS storage | 50 GB gp3 ⚠ | $5.75 | 3.3% |
| ElastiCache Redis | `cache.t4g.micro` | $11.68 | 6.7% |
| ALB | base + 1 LCU | $22.27 | 12.8% |
| NAT gateway | one | $32.85 | 18.9% |
| **Total** | | **$173.96** | |

⚠ the gp3 per-GB rate is the one line not confirmed against a primary source; it is 3% of
the total, so it does not move the conclusion.

**MongoDB is not in that table** — see *Where the cost goes next*, below.

**The NAT gateway is 19% of the infrastructure** — $32.85 a month so that a container can
reach `api.openai.com`. Putting the tasks in a public subnet removes the line entirely.
It is the cheapest saving on the list and the easiest one to miss.

### The curve

```
  users |    infra |     APIs |    total |  $/year | dominates
--------+----------+----------+----------+---------+----------
    100 | $ 1.7396 | $ 0.2093 | $ 1.9488 | $ 23.39 | infra
  1,000 | $ 0.1740 | $ 0.2093 | $ 0.3832 | $  4.60 | the API bill
  2,000 | $ 0.0870 | $ 0.2093 | $ 0.2962 | $  3.55 | the API bill
  5,000 | $ 0.0348 | $ 0.2093 | $ 0.2441 | $  2.93 | the API bill
 10,000 | $ 0.0174 | $ 0.2093 | $ 0.2267 | $  2.72 | the API bill
 50,000 | $ 0.0035 | $ 0.2093 | $ 0.2127 | $  2.55 | the API bill
```

**The crossover is 831 users.** Below it the bill is mostly an idle cluster and the answer
to "how do I cut costs" is *get more users*. Above it the infrastructure is noise and the
only lever that matters is tokens per message — which is the lever this system exposes as
a parameter.

At 10,000 heavy users the whole thing costs **$2,267 a month, or $2.72 per user per
year**, and 92% of that is the API bill. The same table for the lightest profile reads
$0.48 a year, and for the power user $6.12 — **the spread between the lightest and
heaviest realistic user is 13×, which is why quoting one number without its profile is
meaningless.**

### What the budget ceiling buys

The same user, run through the naive arm — the whole episodic history in every prompt, no
ceiling — using the measured 93.9 tokens per rendered turn:

```
month | turns held | naive in/msg | naive $/mo | layered $/mo
------+------------+--------------+------------+-------------
    1 |        308 |       14,578 | $    0.944 | $     0.2093
    3 |        924 |       72,420 | $    4.507 | $     0.2093
    6 |      1,848 |      159,184 | $    9.852 | $     0.2093
   12 |      3,696 |      332,711 | $   20.541 | $     0.2093
   24 |      7,392 |      679,765 | $   41.919 | $     0.2093
```

**Month 6 is 47×. Month 12 is 98×. Month 24 is 200×, and still climbing.** In annual terms
per user: $246 against $2.51 after one year. At 10,000 users, month 12 alone is $205,584 a
month against $2,267.

The column that matters is not the money, though — it is `naive in/msg`. It grows without
bound, so the naive arm does not merely get expensive: **it eventually stops fitting in any
context window and simply fails.** The layered column is flat because it was chosen, and it
stays flat for a user with ten years of history.

**That is the cost/benefit of this project in one line: it converts an unbounded, silently
growing cost into a constant that a caller picks per request — and it proves the constant
on every response.**

### Storage, and what actually sizes the database

Measured with `pg_total_relation_size('turn')`, not estimated: **30,782 bytes per turn.** A
1536-dimension vector is 6,152 of them and the HNSW index roughly doubles that; the
remainder is page overhead that shrinks as the table grows, so this figure over-states the
steady state and is used here because over-stating is the safe direction.

```
 1,000 users · 12 months =  3,696,000 turns =    114 GB
10,000 users · 12 months = 36,960,000 turns =  1,138 GB
```

At gp3 rates a terabyte is $131 a month, which is real but not decisive. **The bill is not
in the disk, it is in the RAM**: an HNSW index answers quickly when it is resident, and 37
million vectors do not fit in a `db.t4g.medium`. **The instance class is chosen by the
index, not by the data**, and that is the line that moves when this grows.

### The levers, in the order they pay

1. **Shorter replies.** Output is 32% of the variable cost and only 6% of the tokens.
   The largest lever, and the least architectural.
2. **A lower `budget`.** It is a request parameter, so it can be tuned per use case rather
   than per deployment — a support bot and a personal assistant do not need the same
   ceiling.
3. **Prompt caching.** Input is priced at $0.02 per 1M when a prefix repeats, a 10×
   discount, and the render order already puts the stable blocks — facts, then summary —
   in front. On the measured subject that prefix is **598 tokens against a documented
   1,024-token minimum**, so this workload pays full price today and starts caching on its
   own as a subject's facts and summary grow. Nothing needs to change for that to happen.
4. **Drop the NAT gateway**, and drop the third store — which is the next section.

### Where the cost goes next

Neither of the two changes below is finished. Both are the reason this is a system under
work rather than a finished product, and the second one is the more interesting.

**MongoDB comes out.** It is inherited. The original architecture had a document store
because summary and facts were its only long-term memory and documents were the natural
shape for them; pgvector arrived later, for a different layer, and nobody revisited the
first decision. Revisited now, it does not survive: **facts and summary are two documents
per subject, fetched by key and written whole.** Postgres `JSONB` does exactly that,
Postgres is already in the stack, and a managed document database has a per-instance floor
that buys nothing here.

The line item is the smaller half of the saving. Removing it also removes a second
connection pool, a second failure mode during consolidation, a second backup policy and a
second thing to right-size. **Three stores earn their keep in a design argument about
access patterns; two of them earn it in a bill.**

**The database goes distributed, and it is cheap here for a structural reason.** The
forcing function is the index, not the data: 37 million vectors want more RAM than one
affordable instance has. The usual answer is sharding, and the usual objection is that
sharding is expensive because queries cross shards.

**No query in this product crosses a subject.** Recall is scoped to one `subject_id` and
excludes one session; facts and summary are keyed by subject; working memory is keyed by
session. There is no cross-subject join, no global ranking, no aggregate that spans people.
**`subject_id` is therefore a perfect shard key, and it was not chosen to be one** — it is
just what the access pattern already was.

What that changes in the bill:

- **Down:** per-node instances are right-sized to a working set instead of one node being
  bought for the largest index. Cold subjects — people who have not spoken in months —
  can live on cheaper storage without touching the hot path.
- **Down again:** recall reads can be served from replicas. The `turn` table is
  append-only and written only at consolidation, and recall explicitly excludes the live
  session, so replication lag is almost always invisible. The one case it is not is a user
  who closes a session and immediately opens another; the failure mode there is *not
  recalling the conversation that just ended*, which is benign and which working memory
  covered anyway.
- **Up:** more nodes means more baseline, and availability multiplies whatever the replica
  factor is. Below a few million turns this costs more than it saves.

The honest summary is that **the distributed step is deferred, not designed around** — the
schema happens to permit it cleanly, which is worth saying out loud precisely because it
was luck as much as foresight.

### What this excludes

Development and staging environments · backups and point-in-time recovery · CloudWatch and
any observability vendor · an AWS support plan · data transfer out · multi-AZ redundancy,
which roughly doubles the database lines · and every human being involved, who costs more
than all of the above combined.

The TypeSafe rate is quoted rather than taken from a public pricing page, because there is
not one. It is also the only line the system runs without: with the key unset, recall keeps
its cosine order and the bill drops by 6%.

**Sensitivity:** the one input that would move the conclusion if it were wrong is tokens
per reply. Double it and the variable cost goes from $0.2093 to $0.2758 a month — the
annual figure moves from $2.51 to $3.31, and the crossover from 831 users to 631. Nothing
else on this page is load-bearing at 2×.

---

## Where it breaks

A design document without this section is a brochure.

**Redundancy between facts and recall.** When facts say *"vegetarian"* and recall returns
the turn where the user said it, the prompt pays twice. Tens of tokens. Deduplicating
across layers is a real technique and it is not worth its cost at this scope.

**Contradiction between old facts and new turns.** Facts are lossy compression; a turn is
the dated original. When they disagree, the resolution is an ordering rule and one line of
system prompt — not a temporal knowledge graph. **This is strictly worse than what Zep
does**, and it is the right trade for this scope.

**The episodic index is only written at session close.** The live conversation is not
retrievable by similarity. Working memory covers it, which is what working memory is for,
but it does mean "remember what I said five minutes ago in this same session" goes through
recency, not meaning.

**Retrieval is single-hop.** *"What did I say about the place my sister recommended?"*
requires connecting two memories. This system retrieves one at a time.

**Consolidation is nearly-exactly-once.** Only the turn log is idempotent, through
`UNIQUE (session_id, seq)`. A retry that dies past the append re-merges the same turns into
the summary and the facts, so a twice-consolidated session can state the same thing twice.
Degraded, never corrupted, and no turn is lost. The way out is a per-step marker in Redis
keyed by session — new state to maintain for a case expected never to happen.

**One consumer on the stream.** The moment analytics and audit need to read the same
consolidation events at their own pace, Redis Streams stops being enough. The migration is
log-to-log, so the model is already right — but it is not done.

**`budget` covers memory, not the prompt.** System instruction and user message are
outside it and reported separately. Defensible, but it must be stated or the numbers get
misread.

---

## What is deliberately not built

**One microservice per memory layer is the wrong shape.** The four layers share a session
lifecycle, and splitting them multiplies latency without buying any real isolation. The one
process that genuinely needs to be separate — consolidation — is separate, because it
survives an API restart and an API restart survives it. An API gateway, a service mesh,
Helm charts, canary releases and multi-region failover are all downstream of that split and
inherit the same verdict.

### Out of scope, with the reasoning intact

Orders and transactions · inventory with reservations · consigned stock allocation ·
declarative ingest adapters · domain-as-configuration · multi-tenancy · analytics over
turns *(the schema already allows it; only the exposure is missing)* · semantic
deduplication across layers · multi-hop retrieval · hybrid vector + lexical search with
rank fusion.

That last one deserves a note: **it is the mature answer to the signal/noise problem
measured above.** Postgres ships `tsvector` and GIN indexes, so it costs no new dependency.
It is unbuilt because the budget ceiling already bounds the damage and the demo does not
need it.

### Two that deserve their own paragraph

**The consolidation filter.** Every turn is stored. A sleep phase that also *decides which
experiences are worth keeping* is the part of the metaphor the worker does not yet
implement. The integration point is consolidation, between mapping the turns and embedding
them. It is a high-volume typed decision, **not a generation task**, which is what System
One models exist for.

What stops it is not the model — the same class of model already runs on the read path, as
*Cosine ranks the topic* describes. It is that **discarding a turn is irreversible and
there is no measured threshold to discard one at.** The re-ranker reorders and filters
nothing for exactly the same reason. A threshold invented rather than measured would
silently lose memory, which is the one failure this product cannot have.

> The first route offered for that API key is an unaffiliated third-party site that takes
> the key **on its own endpoint** — which is where the conversation turns would travel. It
> is not used. The integration talks to `api.typesafe.ai`, the key is read from the
> environment inside the backend, and the console container is deliberately given no
> `env_file` so it never receives one.

**A second consumer.** Shared memory across coding-assistant sessions: a consumer from a
completely different domain than the first one, running against the same core with no
platform changes. That is the reusability claim, demonstrable rather than asserted.
