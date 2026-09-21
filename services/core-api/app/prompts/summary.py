from app.models.session import TurnDraft


async def build_summary_merge_prompt(
    recent_messages: list[TurnDraft], previous_summary: str
) -> dict:
    """Builds a prompt that generates a conversational summary, or merges one.

    Args:
        recent_messages: Complete recent user and assistant turns.
        previous_summary: The summary stored for this subject, if any.

    Returns:
        A system prompt for summary generation and merging.
    """
    if not recent_messages and not previous_summary:
        return {
            "role": "system",
            "content": "There is no history and no prior summary. No summary can be generated.",
        }

    formatted_history = "\n".join(
        f"user: {turn.user_text}\nassistant: {turn.assistant_text}"
        for turn in recent_messages
    )

    if not previous_summary:
        return {
            "role": "system",
            "content": f"""
                Act as the summary memory of a conversational AI.

                Write a TL;DR of the recent messages between a user and an assistant.
                Capture intent, tone, the questions that mattered, the answers that
                mattered, and any relevant personal information.

                Recent messages:
                <conversation>
                {formatted_history}
                </conversation>

                Return only the summary. No headers, no explanations.
                """.strip(),
        }

    return {
        "role": "system",
        "content": f"""
            Act as the summary memory of a conversational AI.

            Your task has two steps:
            1. Read the recent messages between a user and an assistant and write a new
               TL;DR capturing intent, tone, the questions that mattered, the answers
               that mattered, and any relevant personal information.
            2. Merge that new summary with the stored one into a single summary that
               holds the whole context coherently and compactly.

            Previous summary:
            {previous_summary}

            Recent messages:
            <conversation>
            {formatted_history}
            </conversation>

            Return only the merged summary. No headers, no explanations.
            """.strip(),
    }
