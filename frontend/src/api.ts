// Every call is relative: the page and the API share an origin through nginx,
// which proxies /api/ to core-api. No absolute URL, no CORS, no build-time host.

export type BlockSource = 'facts' | 'summary' | 'recall' | 'working'

export interface FragmentRef {
  session_id: string
  ts: string
  similarity: number
  usefulness?: number | null
  seqs: number[]
}

export interface ContextBlock {
  source: BlockSource
  tokens: number
  content: string
  fragments: FragmentRef[] | null
}

export interface Context {
  budget: number
  used: number
  system_tokens: number
  message_tokens: number
  blocks: ContextBlock[]
}

export interface SessionStatus {
  session_id: string
  subject_id: string
  status: string
  turn_count: number
}

export interface ChatReply {
  reply: string
  context: Context | null
}

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, detail: string) {
    super(detail)
    this.status = status
  }
}

interface PydanticError {
  msg?: unknown
}

// `detail` is a string from the handlers and an array of objects from pydantic's
// 422s. Both shapes reach the error strip as one line.
function readDetail(body: unknown, fallback: string): string {
  if (typeof body !== 'object' || body === null || !('detail' in body)) return fallback
  const detail = (body as { detail: unknown }).detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const messages = detail.map((entry: PydanticError) =>
      typeof entry?.msg === 'string' ? entry.msg : JSON.stringify(entry),
    )
    if (messages.length > 0) return messages.join('; ')
  }
  return fallback
}

async function call<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    path,
    body === undefined
      ? undefined
      : {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(body),
        },
  )
  if (!response.ok) {
    let parsed: unknown = null
    try {
      parsed = await response.json()
    } catch {
      // A proxy error page is not JSON; the status carries the message instead.
    }
    throw new ApiError(response.status, readDetail(parsed, `HTTP ${response.status}`))
  }
  return (await response.json()) as T
}

export function createSession(subjectId: string): Promise<{ session_id: string }> {
  return call('/api/sessions', { subject_id: subjectId })
}

export function getSession(sessionId: string): Promise<SessionStatus> {
  return call(`/api/sessions/${sessionId}`)
}

// `q` is never empty: the backend requires min_length=1 and answers 422.
export function getContext(sessionId: string, q: string, budget: number): Promise<Context> {
  const query = new URLSearchParams({ q, budget: String(budget) })
  return call(`/api/sessions/${sessionId}/context?${query}`)
}

export function chat(sessionId: string, message: string, budget: number): Promise<ChatReply> {
  return call(`/api/sessions/${sessionId}/chat`, { message, budget })
}
