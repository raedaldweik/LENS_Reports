import { useState, useRef, useEffect } from 'react';
import { useChat } from '../context/ChatContext';
import ResponseCard from '../components/ResponseCard';
import { askQuestion, getScenarios } from '../services/api';

const SPARK_PATH = 'M12 3.4 13.75 9l5.6 1.75L13.75 12.5 12 18.1l-1.75-5.6L4.65 10.75 10.25 9 12 3.4Z';

const Spark = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d={SPARK_PATH} /></svg>
);

const CARD_ICONS = {
  report: <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>,
  search: <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>,
  alert: <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>,
  spark: <Spark size={19} />,
};

const ChatIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
);

function groupChats(chats) {
  const startOfToday = new Date(); startOfToday.setHours(0, 0, 0, 0);
  const weekAgo = new Date(startOfToday.getTime() - 6 * 86400000);
  const groups = { today: [], week: [], older: [] };
  chats.forEach(c => {
    const t = new Date(c.createdAt);
    if (t >= startOfToday) groups.today.push(c);
    else if (t >= weekAgo) groups.week.push(c);
    else groups.older.push(c);
  });
  return [
    ['اليوم', groups.today],
    ['هذا الأسبوع', groups.week],
    ['أقدم', groups.older],
  ].filter(([, list]) => list.length > 0);
}

export default function ChatPage() {
  const { chats, activeChat, activeChatId, setActiveChatId, addMessage, deleteChat, createNewChat } = useChat();
  const messages = activeChat?.messages || [];
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [scenarios, setScenarios] = useState([]);
  const inputRef = useRef(null);
  const endRef = useRef(null);

  const params = new URLSearchParams(location.search);
  const userName = params.get('user') || 'سيف أشرف';
  const userRole = params.get('role') || 'المركز الأمني';

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
      addMessage(activeChatId, { role: 'assistant', type: 'text', content: `تعذّر الاتصال: ${err.message}`, isError: true });
    }
    setLoading(false);
    inputRef.current?.focus();
  };

  const isFresh = messages.length === 0;

  return (
    <div className="body-row">

      {/* Sidebar — right side in RTL */}
      <aside className="side-card">
        <div className="flex-1 min-h-0 overflow-y-auto">
          {groupChats(chats).map(([label, list]) => (
            <div key={label}>
              <div className="side-group">{label}</div>
              {list.map(chat => (
                <div key={chat.id} className="relative group/item">
                  <button
                    className={`side-item ${chat.id === activeChatId ? 'active' : ''}`}
                    onClick={() => setActiveChatId(chat.id)} title={chat.title}>
                    <ChatIcon />
                    <span className="t" dir="auto">{chat.title}</span>
                  </button>
                  {chats.length > 1 && (
                    <button
                      onClick={e => { e.stopPropagation(); deleteChat(chat.id); }}
                      className="absolute top-1/2 -translate-y-1/2 end-2 p-1 rounded opacity-0 group-hover/item:opacity-100 transition-opacity"
                      style={{ color: 'var(--text-faint)' }} title="حذف المحادثة">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                        <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                      </svg>
                    </button>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>

        <button className="btn-new" onClick={createNewChat}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          محادثة جديدة
        </button>

        <div className="user-chip">
          <div className="avatar">{userName.trim().charAt(0)}</div>
          <div className="who">
            <span className="n">{userName}</span>
            <span className="r">{userRole}</span>
          </div>
        </div>
      </aside>

      {/* Main column */}
      <div className="main-col">
        <div className="main-card">
          {isFresh ? (
            <>
              <div className="hero animate-fade-up">
                <div className="hero-icon"><Spark size={34} /></div>
                <h2>كيف أساعدك في تحليل البيانات؟</h2>
                <p>
                  اسألني عن السائقين الخطرين والمخالفات والبلاغات الجنائية والتحركات،
                  أو اطلب تنبؤاً أو توصية — وسأجيبك مباشرةً من بيانات اللوحة، بالعربية أو الإنجليزية.
                </p>
              </div>
              {scenarios.length > 0 && (
                <div className="sugg-grid animate-slide-up">
                  {scenarios.map(sc => (
                    <button key={sc.id} className="sugg-card" onClick={() => send(sc.prompt)}>
                      <span className={`ico ico-${sc.color || 'green'}`}>
                        {CARD_ICONS[sc.icon] || CARD_ICONS.spark}
                      </span>
                      <span className="tx">
                        <span className="cat">{sc.category}</span>
                        <span className="pr" dir="auto">{sc.prompt}</span>
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="msgs">
              {messages.map((msg, i) => (
                <div key={i} className={`flex gap-2.5 animate-fade-up ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                  {msg.role === 'user' ? (
                    <div className="avatar-sq avatar-user" title={userName}>{userName.trim().charAt(0)}</div>
                  ) : (
                    <div className="avatar-sq avatar-bot" title="المساعد الذكي"><Spark size={18} /></div>
                  )}
                  <div className="max-w-[75%]">
                    {msg.type === 'structured' ? (
                      <ResponseCard data={msg.data} />
                    ) : (
                      <div dir="auto" className={`px-4 py-3 text-[13.5px] leading-[1.85] ${
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
                  <div className="avatar-sq avatar-bot"><Spark size={18} /></div>
                  <div className="msg-bot-bubble px-4 py-3">
                    <div className="flex gap-1.5">
                      {[0, 1, 2].map(j => (
                        <span key={j} className="w-1.5 h-1.5 rounded-full"
                          style={{ background: 'var(--mint)', opacity: 0.3, animation: `pop 1.4s ease-in-out infinite ${j * 0.15}s` }} />
                      ))}
                    </div>
                  </div>
                </div>
              )}
              <div ref={endRef} />
            </div>
          )}

          {/* Input pill */}
          <div className="input-row">
            <div className="input-pill">
              <span className="spark"><Spark size={17} /></span>
              <textarea ref={inputRef} rows="1" value={input} dir="auto"
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
                placeholder="اكتب سؤالك للمساعد الذكي..." />
              <button className="btn-send" onClick={() => send()} title="إرسال">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                  strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ transform: 'scaleX(-1)' }}>
                  <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
