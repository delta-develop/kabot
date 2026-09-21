import type { FragmentRef } from './api'

// The array arrives chronological, not by similarity, and _recall_block can drop
// the closest fragment for its size and admit a smaller one. A numbered position
// would lie, so the chips carry the similarity and nothing else.
function label(fragment: FragmentRef): string {
  const seqs = fragment.seqs
  const span =
    seqs.length > 1
      ? `window max · seqs ${Math.min(...seqs)}–${Math.max(...seqs)}`
      : `seq ${seqs[0]}`
  // MM-DD straight off the UTC string: going through Date would shift the day on
  // fragments seeded after midnight.
  const day = fragment.ts.slice(5, 10)
  const useful =
    fragment.usefulness === null || fragment.usefulness === undefined
      ? ''
      : ` · useful ${fragment.usefulness.toFixed(2)}`
  return `${fragment.similarity.toFixed(4)} · ${span} · ${day}${useful}`
}

export default function FragmentChips({ fragments }: { fragments: FragmentRef[] }) {
  const ranked = [...fragments].sort((a, b) => b.similarity - a.similarity)
  return (
    <div className="chips">
      {ranked.map((fragment) => (
        <span className="chip" key={`${fragment.session_id}-${fragment.seqs.join('-')}`}>
          {label(fragment)}
        </span>
      ))}
      <span className="chips-note">
        text below is chronological; chips are ranked by similarity
      </span>
    </div>
  )
}
