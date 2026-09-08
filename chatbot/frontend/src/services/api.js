// Backend wiring. By default the UI talks to the FastAPI backend same-origin
// (dev uses the Vite proxy to :8000). A host page can rewire everything by
// defining `window.LENS_BACKEND` BEFORE the app bundle loads — see the config
// block in index.html. This is how the UI is pointed at another backend
// (e.g. a SAS Job Execution endpoint) without rebuilding.
//
// window.LENS_BACKEND = {
//   baseUrl:      '',              // prefix for the default endpoints below
//   queryUrl:     '/api/query',    // POST {query, conversation_history} -> JSON
//   scenariosUrl: '/api/scenarios',// GET -> [{id, icon, color, category, prompt}]
//   headers:      {},              // extra headers on every request (e.g. CSRF)
//   scenarios:    [...],           // static suggestion cards (skips scenariosUrl)
//   sendQuery:    async (query, history) => ({answer, charts, trace}),
//                                  // full override: do the call yourself and
//                                  // return anything; it gets normalized below
// };

const CFG = (typeof window !== 'undefined' && window.LENS_BACKEND) || {};
const BASE = CFG.baseUrl || '';

// Suggestion cards shown when no backend /api/scenarios is reachable (static
// hosting). Kept in sync with backend/routers/chat.py.
const FALLBACK_SCENARIOS = [
  { id: 'reports', icon: 'report', color: 'green',
    category: 'تقارير وملخصات',
    prompt: 'لخّص لي حالة لوحة السائقين الخطرين الآن مع أهم المؤشرات' },
  { id: 'query', icon: 'search', color: 'blue',
    category: 'استعلام عن البيانات',
    prompt: 'أظهر جميع الأشخاص من الهند الذين غادروا الدولة' },
  { id: 'alerts', icon: 'alert', color: 'amber',
    category: 'تنبيهات وأنماط',
    prompt: 'كم سائقاً خطراً لديه بلاغات جنائية مقلقة وهو داخل الدولة حالياً؟' },
  { id: 'models', icon: 'spark', color: 'purple',
    category: 'التنبؤ والنماذج',
    prompt: 'شغّل نموذج التنبؤ لأعداد السائقين الخطرين حتى 2030 واعرضه بيانياً' },
];

async function req(url, opts = {}) {
  const r = await fetch(url, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...(CFG.headers || {}), ...(opts.headers || {}) },
  });
  if (!r.ok) {
    const e = await r.json().catch(() => ({ detail: 'Connection error' }));
    throw new Error(e.detail || `HTTP ${r.status}`);
  }
  return r.json();
}

// Whatever the backend returns, coerce it into the shape ResponseCard expects:
// {answer: markdown, charts: [], trace: [], status}. A bare string, or an
// object with only {answer}, is a valid backend response.
function normalizeAnswer(res) {
  if (typeof res === 'string') res = { answer: res };
  if (!res || typeof res !== 'object') res = {};
  return {
    answer: res.answer || res.text || res.message || '(لم يصل ردّ من الخادم)',
    charts: Array.isArray(res.charts) ? res.charts : [],
    trace: Array.isArray(res.trace) ? res.trace : [],
    status: res.status || 'answered',
    query_id: res.query_id,
  };
}

export async function askQuestion(query, conversationHistory = []) {
  if (typeof CFG.sendQuery === 'function') {
    return normalizeAnswer(await CFG.sendQuery(query, conversationHistory));
  }
  const res = await req(CFG.queryUrl || `${BASE}/api/query`, {
    method: 'POST',
    body: JSON.stringify({ query, conversation_history: conversationHistory }),
  });
  return normalizeAnswer(res);
}

export async function getScenarios() {
  if (Array.isArray(CFG.scenarios)) return CFG.scenarios;
  try {
    return await req(CFG.scenariosUrl || `${BASE}/api/scenarios`);
  } catch {
    return FALLBACK_SCENARIOS;
  }
}
