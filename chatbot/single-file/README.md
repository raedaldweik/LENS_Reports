# Single-file UI — lens-smart-assistant.html

`lens-smart-assistant.html` is the complete Smart Assistant UI in one
self-contained HTML file: all JavaScript, CSS, fonts (Tajawal + Manrope,
base64-inlined — no internet needed) and images are embedded. Host it on any
static web server, including the SAS content server.

It is a **build artifact** — don't edit it by hand except for the
`window.LENS_BACKEND` config block near the top, which is where you wire it to
a backend. To regenerate after UI changes:

```bash
cd chatbot/frontend
npm install
npm run build:single        # → dist-single/index.html
cp dist-single/index.html ../single-file/lens-smart-assistant.html
```

See `../INTEGRATION.md` for how to connect a backend (including SAS Job
Execution) and the exact request/response contract.
