import { useCallback, useEffect, useState } from 'react'
import { ApiError, chat, createSession, getContext, type Context } from './api'
import ChatPane, { type Message } from './ChatPane'
import ContextPane from './ContextPane'

const DEFAULT_SUBJECT = 'leo'
const BUDGETS = [400, 800, 1200, 2000, 4000]
const DEFAULT_BUDGET = 2000

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [context, setContext] = useState<Context | null>(null)
  const [lastUserMessage, setLastUserMessage] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [subject, setSubject] = useState(DEFAULT_SUBJECT)
  const [budget, setBudget] = useState(DEFAULT_BUDGET)

  // SESSION_TTL_SECONDS is 1800: a session created tonight does not exist
  // tomorrow, so it is never persisted and always created fresh on mount.
  const startSession = useCallback(async (subjectId: string, notice: string | null) => {
    setSessionId(null)
    setMessages([])
    setContext(null)
    setLastUserMessage('')
    try {
      const created = await createSession(subjectId)
      setSessionId(created.session_id)
      setError(notice)
      return created.session_id
    } catch (failure) {
      setError(`the API did not answer · ${(failure as Error).message}`)
      return null
    }
  }, [])

  useEffect(() => {
    void startSession(DEFAULT_SUBJECT, null)
  }, [startSession])

  // A 404 is an expired session and a 409 one that is no longer open. Both are
  // recovered once, without replaying the message that hit them.
  async function handleFailure(failure: unknown) {
    if (failure instanceof ApiError && (failure.status === 404 || failure.status === 409)) {
      await startSession(subject, 'session expired · started a new one')
      return
    }
    setError(`the API did not answer · ${(failure as Error).message}`)
  }

  async function send(text: string) {
    const message = text.trim()
    if (!sessionId || pending || !message) return
    setPending(true)
    setMessages((current) => [...current, { role: 'you', text: message }])
    setLastUserMessage(message)
    try {
      // D2: the evidence is painted before the answer, and in sequence, so there
      // is one live request at a time and no ordering to reconcile.
      setContext(await getContext(sessionId, message, budget))
      const reply = await chat(sessionId, message, budget)
      // The context of /chat is the authoritative one: it is what the model got.
      if (reply.context) setContext(reply.context)
      setMessages((current) => [...current, { role: 'elephant', text: reply.reply }])
      setError(null)
    } catch (failure) {
      await handleFailure(failure)
    } finally {
      setPending(false)
    }
  }

  // Moving the budget re-reads /context, which spends an embedding and no
  // completion, and writes no turn. Before the first message it does nothing:
  // an empty `q` is a 422.
  async function changeBudget(next: number) {
    setBudget(next)
    if (!sessionId || pending || !lastUserMessage) return
    try {
      setContext(await getContext(sessionId, lastUserMessage, next))
    } catch (failure) {
      await handleFailure(failure)
    }
  }

  function commitSubject(value: string) {
    const next = value.trim()
    if (!next || next === subject) return
    setSubject(next)
    void startSession(next, null)
  }

  const turnCount = messages.filter((message) => message.role === 'elephant').length

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <strong>ELEPHANT</strong>
          <span>· memory inspector</span>
        </div>
        <label className="control">
          subject
          <input
            // Remounting on the committed subject restores the field when the
            // value is cleared or the session is restarted from elsewhere.
            key={subject}
            defaultValue={subject}
            onBlur={(event) => commitSubject(event.target.value)}
            onKeyDown={(event) => {
              if (event.key !== 'Enter') return
              event.preventDefault()
              commitSubject(event.currentTarget.value)
            }}
          />
        </label>
        <label className="control">
          budget
          <select
            value={budget}
            onChange={(event) => void changeBudget(Number(event.target.value))}
          >
            {BUDGETS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <button className="ghost-button" onClick={() => void startSession(subject, null)}>
          ⟲ new
        </button>
      </header>

      {error ? <div className="error-strip">{error}</div> : null}

      <div className="panes">
        <ChatPane
          messages={messages}
          pending={pending}
          disabled={sessionId === null}
          onSend={(text) => void send(text)}
        />
        <ContextPane context={context} turnCount={turnCount} />
      </div>
    </div>
  )
}
