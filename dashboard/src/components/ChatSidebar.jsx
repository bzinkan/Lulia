'use client';
import { useState, useRef, useEffect } from 'react';
import { MessageCircle, X, Send, Sparkles } from 'lucide-react';
import { apiFetch } from '@/lib/api';

const SUGGESTIONS = [
  "Plan my week",
  "Show struggling students",
  "Generate a quick quiz",
  "Explain standard 4.NF.1",
];

export default function ChatSidebar() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  async function sendMessage(text) {
    if (!text?.trim()) return;
    const userMsg = { role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setSending(true);

    try {
      const data = await apiFetch('/api/v1/chat/message', {
        method: 'POST',
        body: JSON.stringify({ message: text, session_id: sessionId, context: { page: window.location.pathname } }),
      });
      setSessionId(data.session_id);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.response,
        tools: data.tool_results,
      }]);
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, something went wrong.' }]);
    } finally { setSending(false); }
  }

  if (!open) {
    return (
      <button onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 w-12 h-12 bg-coral hover:bg-coral-dark text-white rounded-full shadow-lg flex items-center justify-center z-40 transition-transform hover:scale-110">
        <MessageCircle className="w-6 h-6" />
      </button>
    );
  }

  return (
    <div className="fixed right-0 top-0 h-full w-[380px] bg-white shadow-2xl z-50 flex flex-col" style={{ borderLeft: '1px solid var(--border)' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'var(--border)', background: '#FEF9F2' }}>
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-coral" />
          <span className="font-semibold text-sm" style={{ fontFamily: "'DM Serif Display', serif", color: 'var(--text-dark)' }}>Lulia Assistant</span>
        </div>
        <button onClick={() => setOpen(false)} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <div className="text-center py-8">
            <Sparkles className="w-8 h-8 text-coral-light mx-auto mb-2" />
            <p className="text-sm text-gray-500">How can I help you today?</p>
            <div className="mt-4 flex flex-wrap gap-2 justify-center">
              {SUGGESTIONS.map(s => (
                <button key={s} onClick={() => sendMessage(s)}
                  className="text-xs px-3 py-1.5 rounded-full bg-cream text-coral-dark border border-coral-light hover:bg-cream">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm ${
              msg.role === 'user'
                ? 'bg-coral text-white rounded-br-md'
                : 'bg-gray-100 text-gray-800 rounded-bl-md'
            }`}>
              {msg.content}
              {msg.tools?.length > 0 && (
                <div className="mt-2 space-y-1">
                  {msg.tools.map((t, j) => (
                    <div key={j} className="text-[10px] px-2 py-1 bg-white/20 rounded">
                      Used: {t.tool}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {sending && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-2xl rounded-bl-md px-4 py-2">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t" style={{ borderColor: 'var(--border)' }}>
        <div className="flex gap-2">
          <input
            value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage(input)}
            placeholder="Ask Lulia anything..."
            className="flex-1 border border-gray-200 rounded-xl px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-coral-light"
          />
          <button onClick={() => sendMessage(input)} disabled={sending || !input.trim()}
            className="bg-coral hover:bg-coral-dark disabled:bg-coral-light text-white p-2 rounded-xl">
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
