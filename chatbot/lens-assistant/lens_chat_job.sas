/* ============================================================
   LENS Smart Assistant - chat job for SAS Job Execution
   ============================================================

   Adapted from the PSD team's proc python analysis program so it
   can serve the chat UI (lens-smart-assistant.html). Same CAS
   read, same LLM call, same guardrails - plus the three pieces a
   chat endpoint needs:

     1. Reads the user's question from the &QUESTION request
        parameter (and optional &HISTORY - a JSON array of prior
        turns sent by the UI).
     2. Answers that question directly. When no question is passed
        the job falls back to the original fixed two-section
        dashboard summary, so it still works for the VA card.
     3. Writes {"answer": "..."} JSON to _webout so the browser
        receives the response. Errors also come back as JSON
        instead of only being printed to the log.

   DEPLOY
   ------
   Create a Job Execution job with this code (SAS Studio > New >
   Job, or the Job Execution web app), note its content path, e.g.
   /Public/Jobs/lens_chat, and fill in the CONFIGURATION section.

   Then, in lens-smart-assistant.html, set the config block near
   the top of the file to:

     window.LENS_BACKEND = {
       sendQuery: async (query, history) => {
         const params = new URLSearchParams({
           _program: '/Public/Jobs/lens_chat',   // <- your job path
           question: query,
           history: JSON.stringify(history || []),
         });
         const r = await fetch('/SASJobExecution/?' + params, {
           headers: { 'Accept': 'application/json' },
         });
         if (!r.ok) throw new Error('HTTP ' + r.status);
         const text = await r.text();
         try { return JSON.parse(text); } catch { return { answer: text }; }
       },
     };

   Host the HTML on the same SAS web server so the call is
   same-origin: the viewer's SAS logon then authenticates it and
   no CORS setup is needed. If the response comes back wrapped in
   an HTML page instead of raw JSON, add the appropriate output
   option for your Viya release (e.g. _output_type=json) to the
   parameters.

   NOTES / LIMITS (inherited from the original design)
   ---------------------------------------------------
   - Every question re-reads the CAS table and re-sends up to
     MAX_ROWS_TO_SEND rows to the LLM. Keep the row cap within the
     model's context window or answers will degrade or fail.
   - The chat only "knows" this one table per job. Point QUESTION
     at a different CASLIB/TABLE by cloning the job, or extend the
     code to pick a table per request.
   - Expect roughly 15-90s per answer (compute session + CAS fetch
     + LLM). Any proxy in front needs read timeouts raised
     accordingly. The UI shows a typing indicator while it waits.
   ============================================================ */

/* Request parameters arrive as macro variables. Default them so
   the job also runs standalone (dashboard mode). */
%global question history;
%let workpath = %sysfunc(pathname(work));

proc python;
submit;

import swat
import pandas as pd
import json
import traceback
from openai import OpenAI
import httpx


# ============================================================
# 1. CONFIGURATION
# ============================================================

CAS_HOST = ""
CAS_PORT = 5570
CAS_USER = ""

# Replace with secure credential handling in production
CAS_PASS = ""

CASLIB = ""
TABLE_NAME = ""


# ============================================================
# 2. LLM CONFIGURATION
# ============================================================

LLM_BASE_URL = ""
LLM_API_KEY = ""
MODEL = ""

# "ar" = Arabic, "en" = English (used when the question language
# is ambiguous; otherwise the model mirrors the question language)
OUTPUT_LANGUAGE = "ar"

MAX_ROWS_TO_SEND = 1000
MAX_OUTPUT_TOKENS = 700


# ============================================================
# 3. REQUEST INPUT (from the chat UI)
# ============================================================

QUESTION = (SAS.symget("question") or "").strip()

try:
    HISTORY = json.loads(SAS.symget("history") or "[]")
    if not isinstance(HISTORY, list):
        HISTORY = []
except Exception:
    HISTORY = []

# Keep history small: the UI already truncates, this is a backstop.
HISTORY = [
    {"role": h.get("role", "user"), "content": str(h.get("content", ""))[:300]}
    for h in HISTORY[-6:]
    if h.get("role") in ("user", "assistant")
]

WORK_PATH = SAS.symget("workpath")
ANSWER_FILE = f"{WORK_PATH}/lens_answer.json"


def write_answer(text, status="answered"):
    """The one exit point: whatever happens, the UI gets JSON."""
    payload = json.dumps(
        {"answer": text, "status": status},
        ensure_ascii=False,
        default=str,
    )
    with open(ANSWER_FILE, "w", encoding="utf-8") as f:
        f.write(payload)


# ============================================================
# 4. SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are the Smart Assistant embedded in a Dubai Police analytics
dashboard built on SAS Visual Analytics.

You analyze driver-risk, traffic violations, fines, vehicles,
risk classifications, and related traffic-safety information.

You will receive data that represents the records currently
available from the SAS Visual Analytics data source.

============================================================
STRICT DATA RULES
============================================================

1. Analyze ONLY the supplied data.

2. Never invent, estimate, assume, or fabricate values that are
   not present in the supplied data.

3. Do not use external statistics, benchmarks, or assumptions.

4. If information needed for a conclusion is unavailable,
   state the conclusion conservatively.

5. Recommendations must be proportional to the risk actually
   visible in the supplied data.

6. Never exaggerate low-risk cases.

7. Do not repeat every row of the supplied data.

8. Focus on useful patterns, risk indicators, repeated violations,
   fines, status information, vehicle information, and operational
   findings supported by the supplied data.

============================================================
DATA INTERPRETATION
============================================================

First determine whether the data represents one driver or multiple
drivers.

SINGLE DRIVER:
- Treat fields constant across rows as driver profile information.
- Treat fields that vary across rows as individual violations,
  vehicles, events, dates, fines, or other observations.
- Do not double-count profile information repeated on every row.
- Identify repeated violations or repeated concerning behaviour.

MULTIPLE DRIVERS:
- Analyze the displayed population as a group.
- Identify dominant risk categories, frequent violations, and
  concentrations of higher-risk drivers.
- Mention counts and totals only when they can be calculated from
  the supplied records.

Column names may be Arabic or English. Interpret columns by their
semantic meaning ("الاسم"/"Name" identifies a driver,
"خطورة"/"Risk"/"Category" describes risk, "غرامة"/"Fine" is a
fine, "مخالفة"/"Offence" is a violation). Do NOT assign meaning to
an ambiguous field unless the data clearly supports it.

============================================================
OUTPUT REQUIREMENTS
============================================================

Return ONLY the final answer. Never output your reasoning, thought
process, analysis steps, JSON, or code.

WHEN A USER QUESTION IS PROVIDED:
- Answer that question directly and concisely, grounded strictly
  in the supplied data.
- Answer in the language of the question (Arabic question gets an
  Arabic answer, English gets English).
- Use short sentences; bullet points and a small table only when
  they genuinely help.
- Add a "التوصيات:" / "Recommendations:" section only when the
  user asks for recommendations or the findings clearly call for
  operational action.

WHEN NO QUESTION IS PROVIDED (dashboard mode):
Produce EXACTLY two sections:

الملخص:
A single professional paragraph of 2 to 4 sentences.

التوصيات:
- actionable recommendation
- actionable recommendation
- actionable recommendation

(Or "Summary:" / "Recommendations:" if English is requested.
A fourth recommendation may be included only if useful.)

In all cases highlight the most important numbers, categories,
violations, statuses, or terms using **double asterisks**. Keep
the response concise, professional, operational, and suitable for
display inside a Dubai Police dashboard.
"""


# ============================================================
# 5. MAIN
# ============================================================

conn = None

try:

    print("=" * 80)
    print("STEP 1 - CONNECTING TO CAS")
    print("=" * 80)

    conn = swat.CAS(CAS_HOST, CAS_PORT, CAS_USER, CAS_PASS)
    print("CAS connection successful.")

    print("\n" + "=" * 80)
    print("STEP 2 - READING CAS TABLE")
    print("=" * 80)

    result = conn.table.fetch(
        table={"name": TABLE_NAME, "caslib": CASLIB},
        to=MAX_ROWS_TO_SEND,
    )
    df = result["Fetch"]

    print(f"Table: {CASLIB}.{TABLE_NAME}")
    print(f"Rows loaded: {len(df)}")

    if len(df) == 0:
        raise Exception(f"{CASLIB}.{TABLE_NAME} returned zero rows.")

    print("\n" + "=" * 80)
    print("STEP 3 - PREPARING DATA")
    print("=" * 80)

    df = df.where(pd.notnull(df), None)
    for column in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[column]):
            df[column] = df[column].astype(str)

    records = df.to_dict(orient="records")
    table_json = json.dumps(records, ensure_ascii=False, default=str)
    print(f"Rows being sent: {len(records)}")
    print(f"JSON size: {len(table_json):,} characters")

    print("\n" + "=" * 80)
    print("STEP 4 - BUILDING LLM PROMPT")
    print("=" * 80)

    if QUESTION:
        task_instruction = f"""
============================================================
USER QUESTION
============================================================

{QUESTION}

Answer THIS question from the supplied data, in the language of
the question. Return only the final answer.
"""
    elif OUTPUT_LANGUAGE.lower() == "ar":
        task_instruction = """
اكتب الإجابة باللغة العربية الفصحى.

يجب أن يكون الإخراج بهذا الشكل فقط:

الملخص:
فقرة واحدة من 2 إلى 4 جمل.

التوصيات:
- توصية عملية
- توصية عملية
- توصية عملية
"""
    else:
        task_instruction = """
Write the answer in English.

The output must have exactly this structure:

Summary:
One paragraph of 2 to 4 sentences.

Recommendations:
- actionable recommendation
- actionable recommendation
- actionable recommendation
"""

    if HISTORY:
        history_block = (
            "============================================================\n"
            "CONVERSATION SO FAR (for context only)\n"
            "============================================================\n\n"
            + json.dumps(HISTORY, ensure_ascii=False)
            + "\n"
        )
    else:
        history_block = ""

    USER_PROMPT = f"""
The following data comes from the current SAS Visual Analytics
data source.

Table:
{CASLIB}.{TABLE_NAME}

Number of supplied rows:
{len(df)}

Column names:
{json.dumps(list(df.columns), ensure_ascii=False)}

============================================================
DATA
============================================================

{table_json}

============================================================
END OF DATA
============================================================

{history_block}{task_instruction}
"""

    print("Prompt successfully created.")
    print(f"Prompt size: {len(USER_PROMPT):,} characters")

    print("\n" + "=" * 80)
    print("STEP 5 - CONNECTING TO LLM")
    print("=" * 80)

    client = OpenAI(
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        http_client=httpx.Client(verify=False, timeout=120.0),
    )

    print(f"Model: {MODEL}")
    print("Sending request...")

    # Qwen models may support a "thinking" mode; enable_thinking=False
    # prevents the model from returning reasoning instead of the answer.
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT},
            ],
            max_tokens=MAX_OUTPUT_TOKENS,
            temperature=0.2,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
    except Exception:
        print("Gateway did not accept enable_thinking=False.")
        print("Retrying using standard OpenAI-compatible request...")
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT},
            ],
            max_tokens=MAX_OUTPUT_TOKENS,
            temperature=0.2,
        )

    print("\nLLM response received successfully.")

    # Do NOT print(message): some providers include reasoning_content
    # there, which must never reach the log or the user.
    final_answer = response.choices[0].message.content

    if final_answer is not None:
        final_answer = str(final_answer).strip()

    if not final_answer:
        print("\nWARNING: model returned no final content "
              "(endpoint may be forcing reasoning mode).")
        final_answer = (
            "لم يتم إرجاع إجابة نهائية من النموذج. "
            "قام مزود النموذج بإرجاع reasoning_content بدلاً من content."
        )

    write_answer(final_answer)

    print("\n" + "=" * 80)
    print("FINAL LLM ANSWER (also written to _webout as JSON)")
    print("=" * 80)
    print()
    print(final_answer)
    print()
    print("=" * 80)


except Exception as e:

    print("\n" + "=" * 80)
    print("ERROR")
    print("=" * 80)
    print(str(e))
    print("\nDetailed traceback:")
    traceback.print_exc()

    # The UI still gets a well-formed JSON answer on failure.
    write_answer(
        "تعذّر الحصول على إجابة من الخادم — راجع سجل المهمة في SAS. "
        f"(النوع: {type(e).__name__})",
        status="error",
    )

finally:

    if conn is not None:
        try:
            conn.close()
            print("\nCAS connection closed successfully.")
        except Exception as close_error:
            print("\nWarning while closing CAS:", close_error)

print("\nPython program finished.")

endsubmit;
run;

/* ============================================================
   Return the JSON produced above as the HTTP response body.
   ============================================================ */
filename ans "&workpath./lens_answer.json" encoding="utf-8";

data _null_;
  infile ans lrecl=1000000 truncover;
  file _webout encoding="utf-8";
  input;
  put _infile_;
run;

filename ans clear;
