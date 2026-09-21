# Elephant — demo runbook

**Hold this. Do not paste it into the deck.** Slide content lives in `PRESENTATION.md`;
this is the thing you read from while the room watches the screen.

**Where it sits:** between slide 3 (*One endpoint, one question*) and slide 4 (*What you
just saw*). One excursion to the browser, at minute two, back once, never again.

## The three paste blocks, up front

**Paste 1 — the dinner question.** Used in beat 1 and again in beat 5.

```
I'm putting together a dinner for six people this Thursday. Any suggestions on where to take them?
```

**Paste 2 — the follow-up.**

```
Two of them are coming from out of town, so somewhere memorable would be good.
```

**Paste 3 — the different question.**

```
I'm thinking of travelling abroad next month. Anything I should sort out first?
```

---

## The five beats — 5:00 total

### BEFORE THE ROOM IS WATCHING

1. Console open at `http://localhost:8003`
2. **Subject field: `demo`** — press Enter to commit it
3. Budget slider at **2000**
4. Have this file open on a second screen or phone for the paste blocks

---

### BEAT 1 — the inference · 1:10

**Say, 20 seconds:**

> "This person has talked to the system three times before. Once about a restaurant, once
> about swimming lessons, once about renewing a passport. I am going to ask something that
> none of those three conversations was about."

**Paste 1:**

```
I'm putting together a dinner for six people this Thursday. Any suggestions on where to take them?
```

**STOP before the answer arrives.** Point at the right pane.

> "This is what the model is about to receive. Three blocks, each priced in tokens. 944 of
> a 2000 budget. The one called `recalled` is a conversation from weeks ago that the
> system decided was worth paying for."

**Read the beef-broth fragment out loud.** Then:

> "Nobody ever filled in a form that says *vegetarian*. He mentioned it once, complaining
> about a restaurant, and that sentence is what came back. Similarity 0.35, usefulness
> 0.79 — hold on to those two numbers."

*(Verified: `facts 210 · summary 258 · recall 476 · used 944`. Broth `0.3513 / 0.79`;
distractors `0.06` and `0.03`.)*

---

### BEAT 2 — the fourth slot appears · 0:40

**Say:**

> "Three blocks, not four. There is no `current` block, because this is the first message
> of the session — there is no live conversation yet. Watch."

**Paste 2:**

```
Two of them are coming from out of town, so somewhere memorable would be good.
```

**Point at the new slot:**

> "There it is. Four layers now: what is known about him, how his history condenses, what
> was recalled, and the conversation happening right now. The absence a moment ago was
> information, which is why these are four fixed slots and not a list."

*(Verified: `facts 210 · summary 258 · recall 503 · working 174 · used 1145`.)*

---

### BEAT 3 — the budget is the product · 0:50

**Say:**

> "The budget is not a setting, it is the product. Watch what happens when I make it
> smaller."

**Drag the slider to each of these. Pause two seconds. Do not talk over it.**

| Slider | What the room sees | Say this |
|---|---|---|
| **800** | recall shrinks | "Recall got smaller. It dropped fragments one at a time." |
| **600** | recall disappears | "Now it is gone. Facts and summary are still whole." |
| **400** | summary disappears | "Summary went next. Facts survived." |

**Drag it back to 2000 and land it:**

> "That order is not an accident. Facts are paid for first and go in whole or not at all —
> the layer holding *vegetarian* is the last thing at risk. Recall is the only one that
> shrinks, because you can drop a fragment without breaking the rest. And it never once
> went over the ceiling."

*(Verified staircase on the first message: `2000 → 944` · `800 → 740` · `600 → 468` ·
`400 → 210` · `200 → nothing fits`. Moving the slider re-reads `/context`: no turn
written, no completion spent, free and repeatable.)*

---

### BEAT 4 — it is not a one-trick corpus · 0:50

**Say:**

> "The obvious objection is that it holds one interesting thing and returns it every time.
> So — different question."

**Paste 3:**

```
I'm thinking of travelling abroad next month. Anything I should sort out first?
```

**Point at the recall block:**

> "Different fragment. The passport conversation — it expires in April, and the
> appointment system had nothing until June. Similarity 0.49, usefulness 0.55. The
> restaurant story that dominated a minute ago is down at 0.05, because it has nothing to
> do with this question."

*(Verified on a first message: `used 1038` · passport `0.4940 / 0.55` · other `0.05`.)*

---

### BEAT 5 — it is about the person, not the prompt · 0:40

**Say:**

> "Last one, and it is the question I would ask if I were you: how do I know any of this
> is real, and not just written into the system prompt?"

**Change the subject field to `newhire` and press Enter.** The transcript clears.

**Paste 1 again — the exact same dinner question.**

**Point at the empty pane:**

> "Zero. Not a smaller context — *no blocks at all*. Same code, same prompt, same
> question. The only thing that changed is which person is asking. Everything you saw for
> the last three minutes was memory about one individual, and it did not exist for this
> one."

*(Verified: `used 0/2000`, no blocks. Any unused subject name works; the subject is
created implicitly.)*

---

### CLOSING LINE — 0:10

> "Nothing I typed mentioned a diet, or a passport. It read what was said and decided what
> was worth carrying."

Switch back to the deck. Do not linger, do not take questions here.

---

### IF SOMETHING BREAKS

Do not debug in front of the room. Say **"I have this captured"** and go to appendix slides
A6 and A7. One sentence, keep moving.

If only the reply is slow: keep talking over it — the context pane has already painted,
and the context pane is the part that matters.

### BACKUP QUESTION

If beat 3 needs a different angle:

```
I have a free morning this Tuesday. Any ideas what to do with it?
```

*(Pulls the swimming session — `sim 0.3989 · usefulness 0.39`. Weaker separation than the
travel question, which is why it is the backup and not the primary.)*

### WHY A SEEDED SUBJECT AND NOT A LIVE COLD START

Worth having the answer ready, because somebody may ask.

Memory becomes long-term at **session close**, not per message — consolidation is
asynchronous, and the console deliberately has no close button. Teaching it live would mean
a terminal command mid-demo and a wait while three model calls run. In a twelve-minute talk
that is dead air.

The honest answer is that this is not a fixture: `./examples/seed-demo.sh` builds it by
talking to the public API exactly as any consumer would, twelve messages across three
sessions. **Anybody who clones the repository runs one script and reaches this same
state.** If asked, say that — and offer to run it afterwards.

---
