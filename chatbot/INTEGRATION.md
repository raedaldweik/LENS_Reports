# Connecting the Smart Assistant UI to a backend

The chat UI is a static frontend — it holds no data and runs no models. Every
question is sent to a backend over HTTP, and the backend's JSON reply is what
the UI renders (markdown answer, charts, reasoning trace). This document is the
contract any backend must satisfy, plus wiring notes for hosting the
single-file build on SAS.

There are two deliverables of the same UI:

| Form | Where | Backend wiring |
|---|---|---|
| Vite app (`frontend/`) served by the FastAPI backend | `python -m uvicorn main:app` or Docker | built in — same origin `/api/*` |
| **Single file** (`single-file/lens-smart-assistant.html`) | any static host, e.g. the SAS content server | edit the `window.LENS_BACKEND` block near the top of the file |

## The contract

### `POST /api/query` — answer a question

Request body:

```json
{
  "query": "كم سائقاً خطراً لديه بلاغات جنائية مقلقة؟",
  "conversation_history": [
    { "role": "user", "content": "previous question" },
    { "role": "assistant", "content": "previous answer (truncated to 300 chars)" }
  ]
}
```

Response — only `answer` is required; the UI fills in the rest:

```json
{
  "answer": "Markdown text. **Bold**, bullets and small tables all render.",
  "charts": [
    {
      "type": "bar",
      "title": "المخالفات حسب الفئة",
      "subtitle": "optional",
      "data": [ { "category": "خطير", "drivers": 176 }, { "category": "متوسط", "drivers": 291 } ],
      "xKey": "category",
      "yKeys": [ { "key": "drivers", "label": "السائقون", "color": "#2ee59d" } ],
      "yAxisLabel": "optional",
      "footnote": "optional"
    }
  ],
  "trace": [
    {
      "agent": "police_data_agent",
      "tool": "police_query",
      "description": "Querying cases dataset",
      "detail": "Retrieved 353 rows",
      "duration_ms": 120
    }
  ],
  "status": "answered"
}
```

Notes:

- `charts` — chart `type` is `bar | line | area | pie | scatter`. Charts render
  in the chat and are embedded in the exported PDF report. Omit or send `[]`
  for text-only answers.
- `trace` — feeds the collapsible "reasoning steps" panel. Omit or send `[]`
  to hide it.
- A plain string response, or `{"answer": "..."}` alone, is also accepted.
- Errors: return a non-2xx status with `{"detail": "message"}` — the UI shows
  the message in an error bubble.

### `GET /api/scenarios` — suggestion cards (optional)

Returns the four cards on the empty state. **If this endpoint doesn't exist or
fails, the UI falls back to built-in cards** — a static host with only a query
endpoint works fine.

## Wiring the single file (`window.LENS_BACKEND`)

At the top of `lens-smart-assistant.html` there is an editable config block.
Left as `{}`, the UI calls `/api/query` on its own origin.

**Different URL, same JSON contract:**

```html
<script>
  window.LENS_BACKEND = {
    queryUrl: '/SASJobExecution/?_program=/Public/Jobs/lens_chat&_action=execute',
  };
</script>
```

**Full control** — when the endpoint needs different request encoding (form
fields, CSRF headers) or its output needs reshaping into the contract:

```html
<script>
  window.LENS_BACKEND = {
    sendQuery: async (query, history) => {
      const r = await fetch('/SASJobExecution/?_program=/Public/Jobs/lens_chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ question: query, history: JSON.stringify(history) }),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const out = await r.json();
      return { answer: out.answer, charts: out.charts, trace: out.trace };
    },
  };
</script>
```

Other accepted keys: `baseUrl` (prefix for the default paths), `scenariosUrl`,
`headers` (added to every request), `scenarios` (static array of cards).

## Brand images (`window.LENS_ASSETS`)

The single file embeds no images. Host the four brand images anywhere (e.g.
upload to SAS Viya and use each file's content URL) and paste the URLs into
the `window.LENS_ASSETS` block at the top of the file:

```html
<script>
  window.LENS_ASSETS = {
    police:     'https://<viya-host>/files/files/<id>/content', // Dubai Police lockup
    center:     'https://<viya-host>/files/files/<id>/content', // SAS + centre lockup
    badge:      '',                                             // small shield (used only if police is empty)
    background: 'https://<viya-host>/files/files/<id>/content', // page background
  };
</script>
```

Any entry left empty degrades gracefully: logos render as typographic
lockups, the background as the built-in gradient. The `police` and `center`
URLs are also used in the exported PDF report header, so serve them from the
same origin as the page (a cross-origin image can block the PDF export's
canvas rendering).

## Ready-made SAS job

`sas/lens_chat_job.sas` is a Job Execution job adapted from the PSD team's
`proc python` program: it reads the user's question from the `question`
request parameter (plus optional `history`), runs the same CAS read + on-prem
LLM call, and writes `{"answer": "..."}` to `_webout`. Its header comment
contains the exact `window.LENS_BACKEND` block to paste into
`lens-smart-assistant.html`. Fill in the CONFIGURATION section (CAS + LLM
endpoints) before deploying.

## Notes for a SAS-hosted deployment

- **Host the HTML and the API on the same origin** (the same SAS web server).
  Then requests are same-origin: no CORS configuration, and the viewer's SAS
  logon session authenticates the Job Execution calls automatically.
- **The SAS job must write the contract JSON to `_webout`** with
  `Content-Type: application/json`. Easiest from `proc python`: build a Python
  dict, `json.dumps` it, write it to the `_webout` fileref.
- **Latency**: each Job Execution call may spin up a compute session before the
  program runs. The UI shows a typing indicator and waits — but any proxy in
  front must allow long requests (raise read timeouts to 120–300 s).
- **CSRF**: some Viya deployments require an `X-CSRF-TOKEN` header on POSTs to
  `/SASJobExecution`. Fetch it once (the first response's
  `X-CSRF-TOKEN` header) and pass it via `headers` or inside `sendQuery`.
- **Multi-turn**: the UI sends up to the last 6 turns in
  `conversation_history`. If the SAS program is stateless, it can ignore it —
  each question then stands alone.
- **Charts and trace**: without them the chat still works, but the dynamic
  charts and the reasoning panel — the parts that match the dashboards — stay
  empty. Worth wiring through if the on-prem LLM emits structured output.
