import { useEffect, useRef, useState } from 'react'

export interface Message {
  role: 'you' | 'elephant'
  text: string
}

interface Props {
  messages: Message[]
  pending: boolean
  disabled: boolean
  onSend: (text: string) => void
}

export default function ChatPane({ messages, pending, disabled, onSend }: Props) {
  const [draft, setDraft] = useState('')
  const box = useRef<HTMLTextAreaElement>(null)
  const foot = useRef<HTMLDivElement>(null)

  useEffect(() => {
    foot.current?.scrollIntoView({ block: 'end' })
  }, [messages, pending])

  useEffect(() => {
    if (!pending && !disabled) box.current?.focus()
  }, [pending, disabled])

  function send() {
    if (!draft.trim()) return
    onSend(draft)
    setDraft('')
  }

  return (
    <div className="pane chat-pane">
      <div className="transcript">
        <h2 className="pane-title">CONVERSATION</h2>
        {messages.map((message, index) => (
          <div
            className={`bubble ${message.role === 'you' ? 'bubble-you' : 'bubble-elephant'}`}
            key={index}
          >
            <div className="bubble-role">{message.role}</div>
            {message.text}
          </div>
        ))}
        {pending ? <div className="thinking">Thinking…</div> : null}
        <div ref={foot} />
      </div>

      <div className="composer">
        <textarea
          ref={box}
          rows={3}
          maxLength={4000}
          placeholder="type a message…"
          value={draft}
          disabled={disabled || pending}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            // Enter sends, Shift+Enter breaks the line, and Enter does nothing
            // while a turn is in flight.
            if (event.key !== 'Enter' || event.shiftKey) return
            event.preventDefault()
            if (!pending && !disabled) send()
          }}
        />
        <div className="composer-actions">
          <button className="ghost-button" disabled={disabled || pending} onClick={send}>
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
