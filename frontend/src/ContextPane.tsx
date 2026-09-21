import type { Context } from './api'
import BlockCard, { type Slot } from './BlockCard'

// Read in this order; spent in another. Working memory sits next to the question
// because it is the immediate context, so it is paid for before recall.
const SLOTS: Slot[] = [
  { source: 'facts', store: 'mongodb', spent: 1 },
  { source: 'summary', store: 'mongodb', spent: 2 },
  { source: 'recall', store: 'postgres + pgvector', spent: 4 },
  { source: 'working', store: 'redis', spent: 3 },
]

interface Props {
  context: Context | null
  turnCount: number
}

export default function ContextPane({ context, turnCount }: Props) {
  if (!context) {
    return (
      <div className="pane">
        <h2 className="pane-title">WHAT THE MODEL ACTUALLY SAW</h2>
        <p className="placeholder">send a message to see the context</p>
      </div>
    )
  }

  const prompt = context.blocks.map((block) => block.content).join('')
  const pct = Math.round((context.used / context.budget) * 100)

  return (
    <div className="pane">
      <h2 className="pane-title">WHAT THE MODEL ACTUALLY SAW</h2>

      <div className="budget">
        <div className="budget-total">
          {context.used} / {context.budget} tokens
        </div>
        <div className="budget-bar">
          <div className="budget-track">
            {context.blocks.map((block) => (
              <div
                key={block.source}
                style={{
                  width: `${(block.tokens / context.budget) * 100}%`,
                  background: `var(--${block.source})`,
                }}
              />
            ))}
          </div>
          <span className="budget-pct">{pct}%</span>
        </div>
        <div className="budget-outside">
          +{context.system_tokens} system · +{context.message_tokens} message (outside
          budget)
        </div>
        {context.blocks.length === 0 ? (
          <div className="budget-note">nothing remembered about this subject yet</div>
        ) : null}
      </div>

      <div className="slots">
        {SLOTS.map((slot) => {
          const block = context.blocks.find((candidate) => candidate.source === slot.source)
          // Only two strings, and no eviction string: the response reports what is
          // present and says nothing about why the rest is missing.
          const absentReason =
            slot.source === 'working' && turnCount <= 1
              ? 'first message of this session'
              : 'not included this turn'
          return (
            <BlockCard
              key={slot.source}
              slot={slot}
              block={block}
              absentReason={absentReason}
            />
          )
        })}
      </div>

      <details className="prompt">
        <summary>show the exact prompt ({context.used} tokens)</summary>
        <div className="prompt-body">
          <button
            className="ghost-button"
            onClick={() => void navigator.clipboard.writeText(prompt)}
          >
            copy
          </button>
          <pre>{prompt}</pre>
        </div>
      </details>
    </div>
  )
}
