import streamlit as st
import openai
import json
import re
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Frame First — AI for Vibe Coding",
    page_icon="🎯",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
#MainMenu, footer, header { visibility: hidden; }
.block-container { max-width: 860px; padding: 1.5rem 1rem 4rem; }
div[data-testid="metric-container"] > div { font-size: 13px; }
</style>
""", unsafe_allow_html=True)

# ── AI System Prompt ──────────────────────────────────────────────────────────
AI_SYSTEM = """You are strictly evaluating a business prompt for a QBR dashboard task. Be a harsh, accurate grader — do NOT infer or assume anything the prompt does not explicitly say.

SCENARIO: Genpact account team, GlobalBank F&A transformation, Q4 FY2024, $4.2M ARR. Dashboard for client CFO/COO reviewing renewal and 2025 scope.

Score 5 dimensions (0-20 each) using ONLY what is EXPLICITLY written in the prompt:
- role (0-20): 0 if no job title or expertise named. 8 if a role is vaguely mentioned. 15-20 only if specific domain expertise is stated.
- context (0-20): 0 if no audience or stakes. 8 if audience named but stakes missing. 15-20 only if both audience AND business stakes are explicit.
- control (0-20): 0 if no guardrails. NEVER give more than 5 if no explicit constraints. 15-20 only if tone, confidentiality, or scope boundaries stated.
- task (0-20): 0 if only "make a dashboard". 8 if some metrics named. 15-20 only if specific KPIs/sections explicitly listed.
- output (0-20): 0 if no format/layout. NEVER give more than 5 if no layout mentioned. 15-20 only if structure/format explicitly described.

Dashboard quality tier (base on total score):
- executive: total >= 85 AND all 5 dims >= 14
- structured: total 55-84
- partial: total 25-54
- minimal: total < 25

Return ONLY valid JSON with this exact structure:
{
  "scores": {
    "role":    {"score": 0, "feedback": "one sentence why"},
    "context": {"score": 0, "feedback": "one sentence why"},
    "control": {"score": 0, "feedback": "one sentence why"},
    "task":    {"score": 0, "feedback": "one sentence why"},
    "output":  {"score": 0, "feedback": "one sentence why"}
  },
  "ai_output": "bullet1\\nbullet2\\nbullet3",
  "gap": "One sentence explaining the single biggest gap.",
  "dashboard": {
    "title": "dashboard title based on prompt",
    "subtitle": "audience description",
    "dark_header": "header text",
    "kpis": [{"label":"KPI Name","value":"—","badge":"review needed","status":"unknown"}],
    "chart_title": "chart title",
    "has_renewals": false,
    "list_items": ["item 1","item 2"],
    "quality": "partial"
  }
}"""

# ── Helpers ───────────────────────────────────────────────────────────────────
def call_api(prompt_text):
    try:
        client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": AI_SYSTEM},
                {"role": "user",   "content": f'Evaluate this prompt:\n\n"{prompt_text}"'}
            ],
            response_format={"type": "json_object"},
            max_tokens=650,
            temperature=0.3
        )
        return json.loads(resp.choices[0].message.content), None
    except Exception as e:
        return None, str(e)


def keyword_score(p):
    t = p.lower()
    s = {"role": 0, "context": 0, "control": 0, "task": 0, "output": 0}
    if re.search(r'\b(analyst|manager|lead|director|cfo|coo|account team|genpact)\b', t): s["role"] = 10
    if re.search(r'\b(senior|domain expert|subject matter)\b', t): s["role"] = min(s["role"]+8, 20)
    if re.search(r'\b(globalbank|client|cfo|coo|board|stakeholder)\b', t): s["context"] = 10
    if re.search(r'\b(renewal|q4|arr|contract|stakes)\b', t): s["context"] = min(s["context"]+8, 20)
    if re.search(r'\b(confidential|tone|do not|avoid|only show|no raw)\b', t): s["control"] = 12
    if re.search(r'\b(sla|attainment|savings|revenue|margin|kpi|metric)\b', t): s["task"] = 10
    if sum(1 for w in ["sla","savings","renewal","revenue","margin","scope"] if w in t) >= 3:
        s["task"] = min(s["task"]+8, 20)
    if re.search(r'\b(table|chart|section|layout|format|slide|summary)\b', t): s["output"] = 12
    return s


def compute_quality(scores, total):
    if total >= 85 and all(v >= 14 for v in scores.values()):
        return "executive"
    elif total >= 55:
        return "structured"
    elif total >= 25:
        return "partial"
    return "minimal"


def extract_labels(prompt_text):
    p = prompt_text.lower()
    kpis, items = [], []
    title, subtitle, chart = "Dashboard", "", "Performance"

    co = re.search(r'GlobalBank|Genpact|[A-Z][a-zA-Z]+Bank', prompt_text)
    period = re.search(r'Q[1-4]\s*FY\d{2,4}|FY\d{2,4}|Q[1-4]', prompt_text, re.I)
    if co and period:   title = f"{co.group()} {period.group().upper()} Review"
    elif co:            title = f"{co.group()} Review"
    elif period:        title = f"{period.group().upper()} Dashboard"

    aud = re.search(r'\b(CFO|COO|CEO|board|executive)\b', prompt_text, re.I)
    if aud: subtitle = f"{aud.group().upper()} review"

    if re.search(r'\bsla\b|attainment', p):   kpis.append({"label":"SLA Attainment","value":"—","badge":"review needed"})
    if re.search(r'sav|process saving', p):   kpis.append({"label":"Process Savings","value":"—","badge":"review needed"})
    if re.search(r'renew|contract', p):        kpis.append({"label":"Renewal Status","value":"—","badge":"review needed"})
    if re.search(r'revenue|arr\b|financial', p): kpis.append({"label":"Revenue","value":"—","badge":"review needed"})
    if re.search(r'margin|profit', p):         kpis.append({"label":"Net Margin","value":"—","badge":"review needed"})
    if not kpis: kpis.append({"label":"KPI","value":"—","badge":"not specified"})

    if re.search(r'\bsla\b|attainment', p): chart = "SLA Performance"
    elif re.search(r'financial|revenue', p): chart = "Financial Overview"
    elif re.search(r'quarter|q[1-4]', p):   chart = "Quarterly Trend"

    if re.search(r'renew', p):   items.append("Contract renewal status")
    if re.search(r'\bsla\b', p): items.append("SLA compliance")
    if re.search(r'sav|process', p): items.append("Process savings summary")
    if re.search(r'scope|expand', p): items.append("2025 scope expansion")
    if re.search(r'risk|escalat', p): items.append("Risk & escalations")
    if not items: items.append("No specific items mentioned")

    return {"title": title, "subtitle": subtitle, "kpis": kpis[:3],
            "chart_title": chart, "list_items": items}


# ── Dashboard HTML ─────────────────────────────────────────────────────────────
EXEC_DASH = """
<div style="background:#1a1a2e;border-radius:12px;padding:18px;font-family:Inter,sans-serif;min-height:270px;">
  <div style="display:flex;justify-content:space-between;margin-bottom:14px;">
    <div>
      <div style="color:#9ca3af;font-size:10px;text-transform:uppercase;letter-spacing:1px;">Q4 FY24 Dashboard</div>
      <div style="color:white;font-size:15px;font-weight:600;">Auto-generated</div>
    </div>
    <div style="color:#9ca3af;font-size:10px;">Nov 2024</div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:12px;">
    <div style="background:#0f3460;border-radius:8px;padding:10px;">
      <div style="color:#9ca3af;font-size:9px;">Total Revenue</div>
      <div style="color:#60a5fa;font-size:19px;font-weight:700;">£4.2M</div>
      <div style="color:#9ca3af;font-size:8px;">annual total</div>
    </div>
    <div style="background:#0f3460;border-radius:8px;padding:10px;">
      <div style="color:#9ca3af;font-size:9px;">Operating Cost</div>
      <div style="color:#34d399;font-size:19px;font-weight:700;">£3.1M</div>
      <div style="color:#9ca3af;font-size:8px;">year to date</div>
    </div>
    <div style="background:#0f3460;border-radius:8px;padding:10px;">
      <div style="color:#9ca3af;font-size:9px;">Net Margin</div>
      <div style="color:#a78bfa;font-size:19px;font-weight:700;">26.2%</div>
      <div style="color:#9ca3af;font-size:8px;">overall figure</div>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
    <div style="background:#16213e;border-radius:8px;padding:10px;">
      <div style="color:#9ca3af;font-size:9px;margin-bottom:6px;">Performance</div>
      <div style="display:flex;align-items:end;gap:4px;height:44px;">
        <div style="background:#3b82f6;width:14px;height:28px;border-radius:2px;"></div>
        <div style="background:#3b82f6;width:14px;height:38px;border-radius:2px;"></div>
        <div style="background:#3b82f6;width:14px;height:32px;border-radius:2px;"></div>
        <div style="background:#60a5fa;width:14px;height:44px;border-radius:2px;"></div>
      </div>
      <div style="color:#6b7280;font-size:8px;margin-top:3px;">Q1 Q2 Q3 Q4</div>
    </div>
    <div style="background:#16213e;border-radius:8px;padding:10px;">
      <div style="color:#9ca3af;font-size:9px;margin-bottom:6px;">SLA Status</div>
      <div style="color:#e5e7eb;font-size:9px;">Process A <span style="float:right;color:#34d399;">92%</span></div>
      <div style="color:#e5e7eb;font-size:9px;margin:3px 0;">Process B <span style="float:right;color:#34d399;">87%</span></div>
      <div style="color:#e5e7eb;font-size:9px;">Process C <span style="float:right;color:#34d399;">94%</span></div>
    </div>
  </div>
</div>
"""


def build_right_dash(dashboard, quality):
    if quality == "executive":
        return EXEC_DASH

    title   = dashboard.get("title",      "Dashboard")
    sub     = dashboard.get("subtitle",   "CFO REVIEW")
    kpis    = dashboard.get("kpis",       [])
    chart   = dashboard.get("chart_title","Performance")
    items   = dashboard.get("list_items", [])

    if quality == "minimal":
        return f"""
<div style="background:#f8fafc;border:2px dashed #e2e8f0;border-radius:12px;padding:18px;font-family:Inter,sans-serif;min-height:270px;">
  <div style="background:#e2e8f0;border-radius:6px;padding:8px 12px;margin-bottom:12px;">
    <div style="color:#9ca3af;font-size:10px;">No context specified</div>
    <div style="color:#374151;font-size:14px;font-weight:600;">{title}</div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:10px;">
    <div style="background:#e2e8f0;height:48px;border-radius:6px;"></div>
    <div style="background:#e2e8f0;height:48px;border-radius:6px;"></div>
    <div style="background:#e2e8f0;height:48px;border-radius:6px;"></div>
  </div>
  <div style="display:grid;grid-template-columns:2fr 1fr;gap:8px;margin-bottom:10px;">
    <div style="background:#e2e8f0;height:76px;border-radius:6px;"></div>
    <div style="background:#e2e8f0;height:76px;border-radius:6px;"></div>
  </div>
  <div style="color:#9ca3af;font-size:11px;text-align:center;padding:6px;">Insufficient context to build structured output</div>
</div>
"""

    # partial / structured
    hdr_color = "#1e3a5f" if quality == "structured" else "#374151"
    kpi_cols  = max(1, len(kpis))
    kpi_html  = ""
    for k in kpis:
        kpi_html += f"""
    <div style="background:white;border:1px solid #e2e8f0;border-radius:8px;padding:10px;text-align:center;">
      <div style="color:#6b7280;font-size:9px;text-transform:uppercase;">{k.get('label','KPI')}</div>
      <div style="color:#1e293b;font-size:16px;font-weight:700;margin:3px 0;">{k.get('value','—')}</div>
      <div style="background:#fef3c7;color:#92400e;font-size:8px;padding:2px 6px;border-radius:10px;display:inline-block;">{k.get('badge','review needed')}</div>
    </div>"""

    list_html = "".join(
        f'<div style="color:#374151;font-size:10px;padding:3px 0;border-bottom:1px solid #f1f5f9;">• {i}</div>'
        for i in items[:4]
    )

    return f"""
<div style="background:#f8fafc;border-radius:12px;padding:16px;font-family:Inter,sans-serif;min-height:270px;">
  <div style="background:{hdr_color};border-radius:8px;padding:9px 13px;margin-bottom:11px;">
    <div style="color:#9ca3af;font-size:9px;text-transform:uppercase;">{sub}</div>
    <div style="color:white;font-size:14px;font-weight:600;">{title}</div>
  </div>
  <div style="display:grid;grid-template-columns:{'1fr '*kpi_cols};gap:8px;margin-bottom:11px;">
    {kpi_html}
  </div>
  <div style="display:grid;grid-template-columns:2fr 1fr;gap:8px;">
    <div style="background:white;border:1px solid #e2e8f0;border-radius:8px;padding:10px;">
      <div style="color:#6b7280;font-size:9px;margin-bottom:6px;">{chart}</div>
      <div style="display:flex;align-items:end;gap:4px;height:44px;">
        <div style="background:#93c5fd;width:14px;height:22px;border-radius:2px;"></div>
        <div style="background:#93c5fd;width:14px;height:34px;border-radius:2px;"></div>
        <div style="background:#93c5fd;width:14px;height:28px;border-radius:2px;"></div>
        <div style="background:#3b82f6;width:14px;height:44px;border-radius:2px;"></div>
      </div>
      <div style="color:#9ca3af;font-size:8px;margin-top:3px;">No target reference</div>
    </div>
    <div style="background:white;border:1px solid #e2e8f0;border-radius:8px;padding:10px;">
      <div style="color:#6b7280;font-size:9px;margin-bottom:6px;">Status</div>
      {list_html}
    </div>
  </div>
  <div style="color:#9ca3af;font-size:8px;text-align:right;margin-top:6px;">Generated from your prompt · Context Applied AI Studio</div>
</div>
"""


# ── Session State Init ────────────────────────────────────────────────────────
for k, v in [("screen","input"),("name",""),("prompt",""),("result",None),("api_error",None)]:
    if k not in st.session_state:
        st.session_state[k] = v


# ── Screen: Input ─────────────────────────────────────────────────────────────
def show_input():
    st.markdown("""
<div style="text-align:center;padding:36px 0 20px;">
  <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:2px;margin-bottom:10px;">
    FRAME FIRST · AI FOR VIBE CODING · GENPACT
  </div>
  <h1 style="font-size:30px;font-weight:700;color:#0f172a;margin:0 0 8px;">Write your AI prompt.</h1>
  <p style="color:#6b7280;font-size:14px;margin:0;">
    For the QBR dashboard task. Lock in when ready — 5 dimensions scored instantly.
  </p>
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:12px;padding:16px 20px;margin:0 0 18px;">
  <div style="font-size:11px;color:#0369a1;font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">
    THE SITUATION
  </div>
  <p style="color:#0f172a;font-size:14px;margin:0 0 6px;line-height:1.6;">
    You are on the <strong>Genpact account team</strong> managing GlobalBank's Finance &amp; Accounting transformation —
    a 3-year contract, $4.2M ARR. Tomorrow morning's QBR covers <strong>Q4 FY2024 performance,
    the renewal decision, and 2025 scope expansion.</strong>
  </p>
  <p style="color:#374151;font-size:13px;margin:0;line-height:1.5;">
    Your team lead used a 4-word AI prompt to build the dashboard. It produced something generic.
    <strong>Write a better one.</strong> Use the 5 dimensions below as your guide — the AI will score your prompt instantly.
  </p>
</div>
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px;">
  <span style="background:#ede9fe;color:#5b21b6;padding:5px 12px;border-radius:20px;font-size:12px;font-weight:600;">R — Role</span>
  <span style="background:#dbeafe;color:#1e40af;padding:5px 12px;border-radius:20px;font-size:12px;font-weight:600;">C — Context</span>
  <span style="background:#fce7f3;color:#9d174d;padding:5px 12px;border-radius:20px;font-size:12px;font-weight:600;">C — Control</span>
  <span style="background:#fef3c7;color:#92400e;padding:5px 12px;border-radius:20px;font-size:12px;font-weight:600;">T — Task</span>
  <span style="background:#dcfce7;color:#166534;padding:5px 12px;border-radius:20px;font-size:12px;font-weight:600;">O — Output</span>
</div>
""", unsafe_allow_html=True)

    with st.form("input_form"):
        name   = st.text_input("Your name", placeholder="Enter your name")
        prompt = st.text_area("Your prompt",
                              placeholder="Write your AI prompt for a QBR dashboard...",
                              height=130)
        st.caption(f"{len(prompt)} characters")

        _, col_btn = st.columns([2, 1])
        with col_btn:
            submitted = st.form_submit_button("🔒 Lock In", type="primary", use_container_width=True)

    if submitted:
        if not name.strip():
            st.warning("Please enter your name.")
        elif not prompt.strip():
            st.warning("Please write a prompt.")
        else:
            st.session_state.name   = name.strip()
            st.session_state.prompt = prompt.strip()
            st.session_state.result     = None
            st.session_state.api_error  = None
            st.session_state.screen = "results"
            st.rerun()


# ── Screen: Results ───────────────────────────────────────────────────────────
def show_results():
    name        = st.session_state.name
    prompt_text = st.session_state.prompt

    # Back button
    if st.button("← Refine my prompt"):
        st.session_state.screen = "input"
        st.session_state.result = None
        st.rerun()

    # Call API once
    if st.session_state.result is None and st.session_state.api_error is None:
        with st.spinner("Scoring your prompt with OpenAI…"):
            result, err = call_api(prompt_text)
            st.session_state.result    = result
            st.session_state.api_error = err

    result = st.session_state.result
    error  = st.session_state.api_error

    if error:
        st.warning(f"⚠️ API unavailable — using keyword fallback. ({error})")

    # ── Compute scores ──
    dim_feedback = {}
    ai_output_text = ""
    gap_text = ""
    dashboard = {}

    if result and "scores" in result:
        raw = result["scores"]
        scores = {d: min(20, max(0, int(raw.get(d, {}).get("score", 0) or 0)))
                  for d in ["role","context","control","task","output"]}
        dim_feedback = {d: raw.get(d, {}).get("feedback", "") for d in scores}
        ai_output_text = result.get("ai_output", "")
        gap_text       = result.get("gap", "")
        dashboard      = result.get("dashboard") or {}
    else:
        scores = keyword_score(prompt_text)

    total   = sum(scores.values())
    quality = compute_quality(scores, total)

    # Always override quality & fill missing dashboard fields from prompt
    ext = extract_labels(prompt_text)
    dashboard["quality"] = quality
    if not dashboard.get("title"):       dashboard["title"]       = ext["title"]
    if not dashboard.get("subtitle"):    dashboard["subtitle"]    = ext["subtitle"]
    if not dashboard.get("chart_title"): dashboard["chart_title"] = ext["chart_title"]
    if not dashboard.get("kpis"):        dashboard["kpis"]        = ext["kpis"]
    if not dashboard.get("list_items"):  dashboard["list_items"]  = ext["list_items"]

    # ── Quality badge ──
    BADGE = {
        "minimal":    ("#fef2f2","#991b1b","Too Vague"),
        "partial":    ("#fff7ed","#9a3412","Partial"),
        "structured": ("#fefce8","#854d0e","Structured"),
        "executive":  ("#f0fdf4","#166534","Expert"),
    }
    bg, fg, label = BADGE[quality]

    # ── Score header ──
    st.markdown(f"""
<div style="text-align:center;padding:24px 0 16px;">
  <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:2px;margin-bottom:6px;">
    {name} · Your result
  </div>
  <div style="font-size:68px;font-weight:700;color:#0f172a;line-height:1;">{total}</div>
  <div style="font-size:22px;color:#6b7280;margin-bottom:10px;">/100</div>
  <span style="background:{bg};color:{fg};padding:5px 18px;border-radius:20px;font-size:12px;font-weight:600;text-transform:uppercase;">
    {label}
  </span>
</div>
""", unsafe_allow_html=True)

    # ── Dimension bars ──
    st.markdown("#### How Your Prompt Scored")
    TIPS = {
        "role":    "Assign the AI a specific expertise — \"You are a senior Genpact account analyst...\"",
        "context": "Name the audience, the account, and the decision this dashboard must support.",
        "control": "Add guardrails — what should the AI NOT show? (e.g. internal metrics, raw data)",
        "task":    "The task was specific enough that the AI could build the right thing first time.",
        "output":  "Describe what the result should look and feel like — layout, scannability, format.",
    }
    DIM_LABEL = {"role":"Role","context":"Context","control":"Control","task":"Task","output":"Output"}
    for dim in ["role","context","control","task","output"]:
        sc  = scores[dim]
        tip = dim_feedback.get(dim) or TIPS[dim]
        c1, c2 = st.columns([5, 1])
        with c1:
            st.markdown(f"**{DIM_LABEL[dim]}**  <span style='color:#6b7280;font-size:12px;'>{tip}</span>",
                        unsafe_allow_html=True)
            st.progress(sc / 20)
        with c2:
            st.metric("", f"{sc}/20")

    # ── Prompt quote ──
    st.markdown(f"""
<div style="background:#f8fafc;border-left:4px solid #3b82f6;padding:12px 16px;
     border-radius:0 8px 8px 0;margin:16px 0;font-style:italic;color:#374151;font-size:14px;">
  "{prompt_text}"
</div>
""", unsafe_allow_html=True)

    # ── AI output bullets ──
    if ai_output_text:
        st.markdown("#### What the AI Would Build from Your Prompt")
        st.markdown(
            '<div style="color:#6b7280;font-size:13px;margin-bottom:8px;">Based on the instructions you gave, here\'s what GPT-4o-mini would actually produce:</div>',
            unsafe_allow_html=True
        )
        for bullet in ai_output_text.split("\n"):
            if bullet.strip():
                st.markdown(f"""
<div style="border-left:3px solid #3b82f6;padding:6px 12px;margin:4px 0;
     background:#eff6ff;border-radius:0 6px 6px 0;font-size:13px;color:#1e293b;">
  {bullet.strip()}
</div>""", unsafe_allow_html=True)

    # ── Gap sentence ──
    if gap_text:
        st.markdown(f"""
<div style="background:#fefce8;border:1px solid #fde047;border-radius:8px;
     padding:10px 14px;margin:12px 0;font-size:13px;color:#713f12;">
  <strong>+18 points if added:</strong> {gap_text}
</div>""", unsafe_allow_html=True)

    st.divider()

    # ── Side-by-side comparison ──
    st.markdown("#### The Difference Framing Makes")
    left, mid, right = st.columns([10, 1, 10])

    with left:
        st.markdown("""
<div style="margin-bottom:6px;">
  <span style="background:#fef3c7;color:#92400e;font-size:11px;font-weight:600;
        padding:3px 10px;border-radius:12px;text-transform:uppercase;">4-Word Prompt</span>
</div>
<div style="font-style:italic;color:#374151;font-size:13px;margin-bottom:10px;">"Build me a QBR dashboard."</div>
""", unsafe_allow_html=True)
        components.html(EXEC_DASH, height=295)

    with mid:
        st.markdown("<div style='text-align:center;padding-top:72px;font-size:22px;color:#9ca3af;'>→</div>",
                    unsafe_allow_html=True)

    with right:
        st.markdown(f"""
<div style="margin-bottom:6px;">
  <span style="background:{bg};color:{fg};font-size:11px;font-weight:600;
        padding:3px 10px;border-radius:12px;text-transform:uppercase;">
    Your Prompt — {label}
  </span>
</div>
<div style="font-style:italic;color:#374151;font-size:13px;margin-bottom:10px;">
  "{dashboard.get('title','Dashboard')}"
</div>
""", unsafe_allow_html=True)
        components.html(build_right_dash(dashboard, quality), height=295)


# ── Router ────────────────────────────────────────────────────────────────────
if st.session_state.screen == "input":
    show_input()
else:
    show_results()
