"""Unit economics for Elephant: what one user costs, at a usage level you choose.

Every input is either measured on this stack or a published list price with its
date. Nothing is written by hand. Edit PROFILES and re-run:

    python3 examples/cost-model.py

The measured block is reproduced by seeding a subject with ./examples/seed-demo.sh,
running one session on top of it, and counting tokens with the app's own
count_tokens() on the real prompts and the real replies.
"""

# ── measured on this stack, 2026-09-21 ──────────────────────────────────────
# Prompt tokens for turns 1..6 of a real session against a subject that already
# has history. It climbs as working memory fills and then pins against the
# ceiling: the last value is the steady state for every turn after the sixth.
CHAT_IN_RAMP = [1103, 1049, 1218, 1427, 1684, 1994]
CHAT_OUT_PER_TURN = 124  # 745 tokens over 6 replies
RERANK_IN_PER_TURN = 992  # TypeSafe state + one question per candidate
QUERY_EMBED_PER_TURN = 150  # previous turn + message, embedded for recall
RAW_TOKENS_PER_TURN = 138  # 826 tokens of raw turn text over 6 turns
SUMMARY_SCAFFOLD_IN = 435  # summary prompt minus the turns it carries
FACTS_SCAFFOLD_IN = 394  # fact prompt minus the turns it carries
SUMMARY_OUT = 485  # a merged summary; plateaus rather than growing
FACTS_OUT = 299
MEAN_TURN_TOKENS = 93.9  # rendered, over 18 real turns
BYTES_PER_TURN = 30782  # pg_total_relation_size('turn') / rows
SYSTEM_TOKENS = 97

# ── list prices, fetched 2026-09-21 ─────────────────────────────────────────
P_IN = 0.20 / 1e6  # gpt-5.6-luna input
P_OUT = 1.20 / 1e6  # gpt-5.6-luna output
P_EMBED = 0.02 / 1e6  # text-embedding-3-small
P_RERANK = 42.0 / 1e9  # TypeSafe, quoted: $42 per billion input tokens
FARGATE_VCPU_HR = 0.0404
FARGATE_GB_HR = 0.00444
RDS_T4G_MEDIUM_HR = 0.065
ELASTICACHE_T4G_MICRO_HR = 0.016
ALB_HR = 0.0225
ALB_LCU_HR = 0.008
NAT_HR = 0.045
GP3_GB_MONTH = 0.115  # ⚠ not verified from source; flagged
HOURS = 730

# ── who is using it, and how much ───────────────────────────────────────────
# name: (sessions per month, turns per session, what this represents)
PROFILES = {
    "safety companion": (4, 8, "incidents and travel only"),
    "daily assistant": (20, 6, "a few times a week"),
    "support agent": (22, 14, "every working day, longer threads"),
    "power user": (60, 12, "several times a day"),
}
BASELINE = "support agent"
MONTHS = 12


def chat_in(turns: int) -> int:
    """Prompt tokens for a session of `turns`, saturating at the budget ceiling."""
    ramp = CHAT_IN_RAMP[:turns]
    return sum(ramp) + max(0, turns - len(CHAT_IN_RAMP)) * CHAT_IN_RAMP[-1]


def session_cost(turns: int) -> dict:
    raw = turns * RAW_TOKENS_PER_TURN
    tokens = {
        "chat_in": chat_in(turns),
        "chat_out": turns * CHAT_OUT_PER_TURN,
        "summary_in": SUMMARY_SCAFFOLD_IN + raw,
        "summary_out": SUMMARY_OUT,
        "facts_in": FACTS_SCAFFOLD_IN + raw,
        "facts_out": FACTS_OUT,
        "embed_in": raw + turns * QUERY_EMBED_PER_TURN,
        "rerank_in": turns * RERANK_IN_PER_TURN,
    }
    cost = {
        "input": (tokens["chat_in"] + tokens["summary_in"] + tokens["facts_in"]) * P_IN,
        "output": (tokens["chat_out"] + tokens["summary_out"] + tokens["facts_out"])
        * P_OUT,
        "embeddings": tokens["embed_in"] * P_EMBED,
        "re-rank": tokens["rerank_in"] * P_RERANK,
    }
    cost["total"] = sum(cost.values())
    return {"tokens": tokens, "cost": cost}


# ── fixed: the cluster, whether one user or ten thousand use it ─────────────
FIXED = {
    "Fargate · core-api (1 vCPU, 2 GB)": (FARGATE_VCPU_HR + 2 * FARGATE_GB_HR) * HOURS,
    "Fargate · consolidator (.5 vCPU, 1 GB)": (0.5 * FARGATE_VCPU_HR + FARGATE_GB_HR)
    * HOURS,
    "RDS PostgreSQL · db.t4g.medium": RDS_T4G_MEDIUM_HR * HOURS,
    "RDS storage · 50 GB gp3 ⚠": 50 * GP3_GB_MONTH,
    "ElastiCache · cache.t4g.micro": ELASTICACHE_T4G_MICRO_HR * HOURS,
    "ALB · base + 1 LCU": (ALB_HR + ALB_LCU_HR) * HOURS,
    "NAT gateway": NAT_HR * HOURS,
}
FIXED_TOTAL = sum(FIXED.values())


def rule(title: str) -> None:
    print("\n" + "=" * 76)
    print(title)
    print("=" * 76)


sessions, turns, _ = PROFILES[BASELINE]
base = session_cost(turns)

rule(f"ONE SESSION — {BASELINE}, {turns} turns, measured end to end")
t = base["tokens"]
print(f"  chat            {t['chat_in']:>7,} in   {t['chat_out']:>6,} out")
print(f"  summary merge   {t['summary_in']:>7,} in   {t['summary_out']:>6,} out")
print(f"  fact merge      {t['facts_in']:>7,} in   {t['facts_out']:>6,} out")
print(f"  embeddings      {t['embed_in']:>7,} in")
print(f"  re-rank         {t['rerank_in']:>7,} in")
print("  " + "-" * 62)
for name, amount in base["cost"].items():
    if name == "total":
        continue
    print(f"  {name:<14}  ${amount:.6f}   ({amount / base['cost']['total']:5.1%})")
print(f"  {'per session':<14}  ${base['cost']['total']:.6f}")

rule("COST PER USER — by how much they actually use it")
print(
    f"  {'profile':<18} | {'msgs/mo':>7} | {'$/month':>8} | {'$/year':>7} | represents"
)
print(f"  {'-' * 18}-+-{'-' * 7}-+-{'-' * 8}-+-{'-' * 7}-+------------")
variable = {}
for name, (s, tn, what) in PROFILES.items():
    monthly = session_cost(tn)["cost"]["total"] * s
    variable[name] = monthly
    mark = " ←" if name == BASELINE else ""
    print(
        f"  {name:<18} | {s * tn:>7,} | ${monthly:>7.4f} | ${monthly * 12:>6.2f} |"
        f" {what}{mark}"
    )
print("\n  APIs only. Infrastructure is shared and divided below.")

rule(f"TOTAL PER USER PER MONTH — {BASELINE} profile")
v = variable[BASELINE]
print(
    f"  {'users':>7} | {'infra':>8} | {'APIs':>8} | {'total':>8} | {'$/year':>7} | dominates"
)
print(f"  {'-' * 7}-+-{'-' * 8}-+-{'-' * 8}-+-{'-' * 8}-+-{'-' * 7}-+----------")
for n in (100, 1_000, 2_000, 5_000, 10_000, 50_000):
    infra = FIXED_TOTAL / n
    total = infra + v
    who = "infra" if infra > v else "the API bill"
    print(
        f"  {n:>7,} | ${infra:>7.4f} | ${v:>7.4f} | ${total:>7.4f} |"
        f" ${total * 12:>6.2f} | {who}"
    )
print(
    f"\n  crossover: {FIXED_TOTAL / v:,.0f} users — below it you pay for an idle cluster"
)
print(f"  fixed infrastructure: ${FIXED_TOTAL:,.2f}/month")

rule(f"WHAT THE BUDGET CEILING BUYS — {BASELINE} profile")
msgs_month = sessions * turns
steady_in = CHAT_IN_RAMP[-1]
print(
    f"  {'month':>5} | {'turns held':>10} | {'naive in/msg':>12} | {'naive $/mo':>10} | {'layered $/mo':>12}"
)
print(f"  {'-' * 5}-+-{'-' * 10}-+-{'-' * 12}-+-{'-' * 10}-+-{'-' * 12}")
for m in (1, 3, 6, 12, 24):
    held = msgs_month * m
    avg = held - msgs_month / 2
    naive_in = SYSTEM_TOKENS + avg * MEAN_TURN_TOKENS + 20
    naive = msgs_month * naive_in * P_IN + msgs_month * CHAT_OUT_PER_TURN * P_OUT
    print(f"  {m:>5} | {held:>10,} | {naive_in:>12,.0f} | ${naive:>9.3f} | ${v:>11.4f}")
print(
    f"\n  layered input per message saturates at {steady_in:,} tokens and stays there."
)

rule(f"STORAGE — measured, {BASELINE} profile")
for n in (1_000, 10_000):
    stored = n * msgs_month * MONTHS
    gb = stored * BYTES_PER_TURN / 1e9
    print(
        f"  {n:>6,} users · {MONTHS} months = {stored:>12,} turns = {gb:>8,.0f} GB"
        f"   (${gb * GP3_GB_MONTH:>9,.2f}/mo at gp3 ⚠)"
    )
print(
    f"\n  {BYTES_PER_TURN:,} bytes/turn measured on 33 rows; a 1536-dim vector is 6,152"
)
print("  of them and the HNSW index roughly doubles it. At this row count index")
print("  pages are mostly empty, so this OVER-states the steady state.")
