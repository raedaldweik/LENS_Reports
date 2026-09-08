# Single-file UI — lens-smart-assistant.html

`lens-smart-assistant.html` is the complete Smart Assistant UI in one
self-contained HTML file: all JavaScript, CSS and fonts (Tajawal + Manrope,
base64-inlined — no internet needed) are embedded. Host it on any static web
server, including the SAS content server.

The four brand images (police logo, center logo, badge, background) are NOT
embedded: host them separately (e.g. on SAS Viya) and paste each image's URL
into the `window.LENS_ASSETS` block near the top of the file. Entries left
empty fall back gracefully — text lockups for the logos, the built-in
gradient for the background.

It is a **build artifact** — don't edit it by hand except for the
`window.LENS_ASSETS` and `window.LENS_BACKEND` config blocks near the top
(image URLs and backend wiring). To regenerate after UI changes:

```bash
cd chatbot/frontend
npm install
npm run build:single        # → dist-single/index.html
cp dist-single/index.html ../single-file/lens-smart-assistant.html
```

See `../INTEGRATION.md` for how to connect a backend (including SAS Job
Execution) and the exact request/response contract.
