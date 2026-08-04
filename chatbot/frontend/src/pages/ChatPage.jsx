import { useState, useRef, useEffect } from 'react';
import { useChat } from '../context/ChatContext';
import ResponseCard from '../components/ResponseCard';
import { askQuestion, getScenarios } from '../services/api';

export default function ChatPage() {
  const { chats, activeChat, activeChatId, setActiveChatId, addMessage, renameChat, deleteChat, createNewChat } = useChat();
  const messages = activeChat?.messages || [];
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [chatMenu, setChatMenu] = useState(null);
  const [renamingChat, setRenamingChat] = useState(null);
  const [renameValue, setRenameValue] = useState('');
  const [scenarios, setScenarios] = useState([]);
  const inputRef = useRef(null);
  const endRef = useRef(null);

  useEffect(() => {
    getScenarios().then(setScenarios).catch(() => setScenarios([]));
  }, []);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, loading]);

  const send = async (text) => {
    const q = (text || input).trim();
    if (!q || loading) return;
    setInput('');
    addMessage(activeChatId, { role: 'user', type: 'text', content: q });
    setLoading(true);
    try {
      const history = messages.slice(-6).map(m => ({
        role: m.role === 'user' ? 'user' : 'assistant',
        content: m.role === 'user' ? m.content : (m.data?.answer || m.content || '').slice(0, 300),
      }));
      const res = await askQuestion(q, history);
      addMessage(activeChatId, { role: 'assistant', type: 'structured', data: res, query: q });
    } catch (err) {
      addMessage(activeChatId, { role: 'assistant', type: 'text', content: `Error: ${err.message}`, isError: true });
    }
    setLoading(false);
    inputRef.current?.focus();
  };

  const startRename = (chat) => { setRenamingChat(chat.id); setRenameValue(chat.title); setChatMenu(null); };
  const finishRename = (id) => { if (renameValue.trim()) renameChat(id, renameValue.trim()); setRenamingChat(null); };

  // Show suggestion chips when the conversation is fresh (only the welcome message)
  const isFresh = messages.length <= 1;

  return (
    <div className="h-full flex gap-4 p-4">

      {/* Chat history panel (left) */}
      <div className="w-[260px] shrink-0 glass-card flex flex-col">
        <div className="p-4 border-b border-[rgba(233,246,239,0.08)]">
          <p className="panel-title">Recent conversations</p>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {chats.map(chat => {
            const isRenaming = renamingChat === chat.id;
            const menuOpen = chatMenu === chat.id;
            return (
              <div key={chat.id} className="relative group">
                {isRenaming ? (
                  <div className="px-2 py-1.5">
                    <input value={renameValue} onChange={e => setRenameValue(e.target.value)}
                      onBlur={() => finishRename(chat.id)} onKeyDown={e => e.key === 'Enter' && finishRename(chat.id)} autoFocus
                      className="w-full rounded-lg px-2 py-1.5 text-xs border outline-none"
                      style={{ background: 'rgba(8,26,19,0.8)', borderColor: 'var(--gold-hi)', color: 'var(--text)' }} />
                  </div>
                ) : (
                  <div className="flex items-center">
                    <button onClick={() => setActiveChatId(chat.id)}
                      className={`flex-1 flex items-center gap-2 px-3 py-2.5 rounded-lg text-xs text-left truncate transition-all ${
                        chat.id === activeChatId
                          ? 'font-semibold'
                          : 'hover:bg-[rgba(45,212,167,0.06)] border border-transparent'
                      }`}
                      style={chat.id === activeChatId
                        ? { color: 'var(--gold-hi)', background: 'rgba(45,212,167,0.12)', border: '1px solid rgba(45,212,167,0.30)', borderLeft: '3px solid var(--gold)' }
                        : { color: 'var(--text-md)' }
                      }>
                      <span className="text-sm">💬</span>
                      <span className="truncate flex-1" dir="auto">{chat.title}</span>
                    </button>
                    <button onClick={e => { e.stopPropagation(); setChatMenu(menuOpen ? null : chat.id); }}
                      className="p-1 rounded-md opacity-0 group-hover:opacity-100 hover:bg-[rgba(45,212,167,0.12)] transition-all shrink-0 ml-0.5"
                      style={{ color: 'var(--text-faint)' }}>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="5" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="12" cy="19" r="1"/>
                      </svg>
                    </button>
                  </div>
                )}
                {menuOpen && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setChatMenu(null)} />
                    <div className="absolute right-0 top-full mt-0.5 rounded-xl shadow-xl overflow-hidden z-50 min-w-[130px] animate-fade-up"
                      style={{ background: 'rgba(9,28,20,0.97)', border: '1px solid rgba(45,212,167,0.25)', backdropFilter: 'blur(20px)' }}>
                      <button onClick={() => startRename(chat)} className="w-full flex items-center gap-2 px-3 py-2 text-[11px] hover:bg-[rgba(45,212,167,0.08)]" style={{ color: 'var(--text-md)' }}>
                        Rename
                      </button>
                      <button onClick={() => { deleteChat(chat.id); setChatMenu(null); }} className="w-full flex items-center gap-2 px-3 py-2 text-[11px] hover:bg-[var(--red-bg)]" style={{ color: 'var(--red)' }}>
                        Delete
                      </button>
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>
        <div className="p-3 border-t border-[rgba(233,246,239,0.08)]">
          <button onClick={() => { createNewChat(); }}
            className="w-full py-2.5 rounded-lg text-xs font-bold transition-all"
            style={{ border: '2px dashed rgba(45,212,167,0.35)', color: 'var(--gold)', background: 'rgba(45,212,167,0.04)' }}>
            + New conversation
          </button>
        </div>
      </div>

      {/* Main chat area */}
      <div className="flex-1 glass-card flex flex-col relative" style={{ boxShadow: 'var(--glass-shadow-lg)' }}>
        <img src="/badge.svg" alt="" className="chat-watermark" onError={e => e.target.style.display='none'} />

        {/* Header with title */}
        <div className="flex items-center justify-between px-6 py-3 border-b border-[rgba(233,246,239,0.08)] relative z-[1]">
          <div className="flex items-center gap-2">
            <span className="w-[3px] h-4 rounded" style={{ background: 'var(--gold-grad)' }} />
            <span className="text-sm font-bold" dir="auto" style={{ color: 'var(--text)' }}>{activeChat?.title || 'New conversation'}</span>
          </div>
          <span className="text-[9.5px] font-bold tracking-[0.14em] uppercase" style={{ color: 'var(--text-faint)' }}>
            Violations · Criminal Reports · Movements
          </span>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5 relative z-[1]">
          {messages.map((msg, i) => (
            <div key={i} className={`flex gap-2.5 animate-fade-up ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
              {/* Avatar */}
              {msg.role === 'user' ? (
                <div className="w-8 h-8 rounded-lg shrink-0 flex items-center justify-center text-xs font-bold"
                  title="Officer"
                  style={{ background: 'rgba(45,212,167,0.12)', border: '1px solid rgba(45,212,167,0.30)', color: 'var(--gold-hi)' }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
                  </svg>
                </div>
              ) : (
                <div className="w-8 h-8 rounded-lg shrink-0 flex items-center justify-center p-1"
                  style={{ background: 'var(--nav-grad)', border: '1px solid rgba(45,212,167,0.35)' }}>
                  <img src="/badge.svg" alt="Assistant" className="w-full h-full object-contain" />
                </div>
              )}
              {/* Bubble */}
              <div className="max-w-[70%]">
                {msg.type === 'structured' ? (
                  <ResponseCard data={msg.data} />
                ) : (
                  <div dir="auto" className={`px-4 py-3 text-[13px] leading-[1.75] ${
                    msg.role === 'user' ? 'msg-user-bubble' : 'msg-bot-bubble'
                  } ${msg.isError ? 'text-[var(--red)]' : ''}`}
                    style={{ color: msg.isError ? undefined : 'var(--text)' }}>
                    {msg.content}
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex gap-2.5 animate-fade-up">
              <div className="w-8 h-8 rounded-lg shrink-0 flex items-center justify-center p-1"
                style={{ background: 'var(--nav-grad)', border: '1px solid rgba(45,212,167,0.35)' }}>
                <img src="/badge.svg" alt="Assistant" className="w-full h-full object-contain" />
              </div>
              <div className="msg-bot-bubble px-4 py-3">
                <div className="flex gap-1.5">
                  {[0, 1, 2].map(j => (
                    <span key={j} className="w-1.5 h-1.5 rounded-full"
                      style={{ background: 'var(--gold)', opacity: 0.3, animation: `pop 1.4s ease-in-out infinite ${j * 0.15}s` }} />
                  ))}
                </div>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {/* Suggestion chips - only when conversation is fresh */}
        {isFresh && scenarios.length > 0 && (
          <div className="px-5 pb-1 pt-1 relative z-[1]">
            <p className="text-[9px] tracking-widest uppercase font-bold mb-2 px-1" style={{ color: 'var(--text-dim)' }}>
              Suggested prompts · أسئلة مقترحة
            </p>
            <div className="flex flex-wrap gap-2">
              {scenarios.map(sc => (
                <button key={sc.id} onClick={() => send(sc.prompt)} className="suggestion-chip" title={sc.description}>
                  <span className="chip-tag">{sc.label}</span>
                  <span dir="auto">{sc.prompt}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Input bar */}
        <div className="px-5 pb-4 pt-2 relative z-[1]">
          <div className="flex items-center gap-1.5 px-2 py-1 rounded-xl border border-[rgba(233,246,239,0.10)] transition-all focus-within:border-[var(--gold-hi)] focus-within:shadow-[0_0_0_3px_rgba(45,212,167,0.12)]"
            style={{ background: 'var(--glass-strong)', backdropFilter: 'blur(12px)' }}>

            {/* Text input */}
            <textarea ref={inputRef} rows="1" value={input} dir="auto"
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
              placeholder={`Ask about the data in English or Arabic — اسأل عن البيانات`}
              className="flex-1 bg-transparent border-none outline-none text-[13px] py-2 px-2 resize-none leading-relaxed"
              style={{ fontFamily: "'Manrope', 'IBM Plex Sans Arabic', sans-serif", color: 'var(--text)' }} />

            {/* Send */}
            <button onClick={() => send()}
              className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 hover:scale-105 transition-transform"
              style={{ background: 'var(--gold-grad)', color: '#04110a', boxShadow: '0 3px 12px rgba(45,212,167,0.35)' }}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
