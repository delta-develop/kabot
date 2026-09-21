from app.models.session import TurnDraft


async def build_fact_merge_prompt(
    recent_messages: list[TurnDraft], previous_facts: dict
) -> dict:
    """Builds a prompt that merges facts from recent conversation turns.

    Args:
        recent_messages: Complete recent user and assistant turns.
        previous_facts: Previously stored facts about the subject.

    Returns:
        A system prompt for fact extraction and merging.
    """
    formatted_history = "\n".join(
        f"user: {turn.user_text}\nassistant: {turn.assistant_text}"
        for turn in recent_messages
    )
    formatted_facts = ", ".join(f"{k}: {v}" for k, v in previous_facts.items())

    return {
        "role": "system",
        "content": f"""
            Act as a fact extraction and maintenance engine for a conversational AI.

            You have two tasks:
            1. From the message history, extract important facts about the user: their
               name, preferences, tastes, contact details, or any persistent
               information that helps personalize future replies.
            2. Merge those new facts with the stored ones. When a stored fact and a new
               one conflict directly — a favorite brand changes, for instance — update
               the value. When the new fact complements what is stored, add it without
               removing what is already there.

            When the current known facts are 'None', build a new base structure from
            the recent conversation.

            Current known facts:
            {formatted_facts or 'None'}

            Recent conversation history:
            <conversation>
            {formatted_history}
            </conversation>

            Return a JSON object holding the user's updated facts. Keys are short
            snake_case identifiers; the prose belongs in the values, never in a key.
            """.strip(),
    }
