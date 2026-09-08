LENS Smart Assistant - deployment package
=========================================

Contents
  lens-smart-assistant.html   the chat UI (one self-contained file)
  images/                     logos + background used by the page
  lens_chat_job.sas           SAS Job Execution job that answers the chat

Steps
-----
1. Host this folder on your web server, keeping the layout as-is.
   The page loads the images from ./images/ automatically.
   (To host the images somewhere else instead, edit window.LENS_ASSETS
   at the top of the HTML and paste the full URL of each image.)

2. Create a Job Execution job from lens_chat_job.sas
   (SAS Studio > New > Job). Fill in the CONFIGURATION section:
   CAS host/credentials, caslib + table, and the LLM endpoint.

3. Connect the page to the job: edit window.LENS_BACKEND at the top of
   the HTML. A ready-made snippet with the exact code is in the header
   comment of lens_chat_job.sas - set _program to your job's content
   path and you are done.

4. Open the page and ask a question. The first answer takes longer
   (compute session start-up). If the response arrives wrapped in an
   HTML page instead of raw JSON, add your Viya release's output
   option (e.g. _output_type=json) to the request parameters in the
   snippet.

Notes
-----
- Host the page, the images and the job on the SAME server: requests
  are then same-origin, the viewer's SAS logon authenticates them, and
  no CORS setup is needed. Same-origin images are also required for
  the PDF export button to work.
- The chat answers from the CAS table configured inside the job; the
  model receives up to MAX_ROWS_TO_SEND rows per question. Keep that
  cap within the LLM's context window.
- Expect roughly 15-90 seconds per answer (compute session + CAS fetch
  + LLM). Raise any proxy read timeouts accordingly.
