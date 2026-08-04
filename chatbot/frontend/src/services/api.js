// Dev uses the Vite proxy to :8000. Same-origin in prod.
const API = '';

async function req(path, opts = {}) {
  const r = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!r.ok) {
    const e = await r.json().catch(() => ({ detail: 'Connection error' }));
    throw new Error(e.detail || `HTTP ${r.status}`);
  }
  return r.json();
}

export const askQuestion = (query, conversationHistory = []) =>
  req('/api/query', {
    method: 'POST',
    body: JSON.stringify({ query, conversation_history: conversationHistory }),
  });

export const getScenarios = () => req('/api/scenarios');
