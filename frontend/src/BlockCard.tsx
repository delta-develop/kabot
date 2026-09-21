import type { ContextBlock } from './api'
import FragmentChips from './FragmentChips'

export interface Slot {
  source: ContextBlock['source']
  store: string
  spent: number
}

interface Props {
  slot: Slot
  block: ContextBlock | undefined
  absentReason: string
}

export default function BlockCard({ slot, block, absentReason }: Props) {
  const source = slot.source.toUpperCase()
  const classes = ['card']
  if (slot.source === 'recall') classes.push('card-recall')
  if (!block) classes.push('card-absent')

  return (
    <section className={classes.join(' ')}>
      <div className="card-head">
        <strong>{source}</strong>
        <span>· {slot.store}</span>
        <span>· spent #{slot.spent}</span>
        {block ? <span>· {block.tokens} tok</span> : null}
        {block && slot.source === 'working' ? (
          <span className="card-note">· what the model saw (−1 turn)</span>
        ) : null}
      </div>
      {block ? (
        <>
          {block.fragments === null || block.fragments === undefined ? null : (
            <FragmentChips fragments={block.fragments} />
          )}
          <div className="card-body">
            <pre>{block.content}</pre>
          </div>
        </>
      ) : (
        <div className="card-empty">{absentReason}</div>
      )}
    </section>
  )
}
