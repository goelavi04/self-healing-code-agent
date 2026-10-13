"""
app.py - Streamlit web UI for the Self-Healing Code Agent.

Run with:   streamlit run app.py

Each attempt is shown as a step: the code, what changed since the last attempt
(the "fix"), the output, and the error. At the end it shows the final status.
"""

import difflib

import streamlit as st

from agent import MAX_RETRIES, load_history, run_agent, status_message
from test_cases import DEMO_TASKS

st.set_page_config(page_title="Self-Healing Code Agent", page_icon="🩹", layout="wide")
st.title("🩹 Self-Healing Code Agent")
st.caption("Generate → Execute → Diagnose → Repair … until the code works.")

CUSTOM_TASK = "✏️ Write my own task"


def load_demo():
    """When a demo is picked in the dropdown, copy its text into the input boxes."""
    for demo in DEMO_TASKS:
        if demo["name"] == st.session_state.demo_choice:
            st.session_state.task_text = demo["task"]
            st.session_state.expected_text = demo["expected"]
            st.session_state.starting_code_text = demo.get("buggy_code") or ""
            return
    # "Write my own task" was chosen: clear the boxes.
    st.session_state.task_text = ""
    st.session_state.expected_text = ""
    st.session_state.starting_code_text = ""


def show_attempt(record, previous_code):
    """Draw one attempt as a box: code, fix (diff), output, error."""
    icon = "✅" if record["passed"] else "❌"
    title = f"{icon} Attempt {record['attempt']} — {record['kind']} ({record['time_taken_s']}s)"
    with st.expander(title, expanded=True):
        st.markdown("**Code**")
        st.code(record["code"], language="python")

        # Show only the lines that changed compared to the previous attempt.
        if previous_code is not None:
            diff = difflib.unified_diff(
                previous_code.splitlines(), record["code"].splitlines(),
                fromfile="previous attempt", tofile="this attempt", lineterm="",
            )
            st.markdown("**The fix (what changed since the last attempt)**")
            st.code("\n".join(diff) or "(no changes)", language="diff")

        st.markdown("**Output**")
        st.code(record["stdout"].strip() or "<nothing printed>", language="text")

        if record["passed"]:
            st.success("Passed")
        else:
            st.markdown("**Error (sent back to the LLM)**")
            st.code(record["error"], language="text")


def show_final_status(run):
    """Green box if it worked, red box if it failed."""
    message = f"{status_message(run)} — total {run['total_time_s']}s"
    if run["status"] == "failed":
        st.error(message)
    else:
        st.success(message)


# ----------------------------- Sidebar -------------------------------------
with st.sidebar:
    st.header("Settings")
    st.selectbox("Load a demo task", [CUSTOM_TASK] + [d["name"] for d in DEMO_TASKS],
                 key="demo_choice", on_change=load_demo)
    max_retries = st.slider("Max retries (repair attempts)", 0, 5, MAX_RETRIES)
    st.markdown("---")
    st.markdown("**How it works**\n\n1. LLM writes code\n2. Code runs in a subprocess (10 s limit)\n"
                "3. Crash / wrong output / timeout → error goes back to the LLM\n4. Repeat until it passes")

# ----------------------------- Inputs --------------------------------------
task = st.text_area("Task (plain English)", key="task_text", height=140)
expected = st.text_area("Expected output (optional — if given, wrong output also counts as a failure)",
                        key="expected_text", height=110)
starting_code = st.text_area("Starting code (optional — paste buggy code here; attempt 1 runs it "
                             "as-is, then the LLM heals it)", key="starting_code_text", height=180)

# ----------------------------- Run -----------------------------------------
if st.button("▶ Run agent", type="primary", disabled=not task.strip()):
    codes_so_far = []  # remembers previous code, so we can show the diff

    def on_attempt(record):
        """Called by run_agent() after every attempt, so steps appear live."""
        previous = codes_so_far[-1] if codes_so_far else None
        show_attempt(record, previous)
        codes_so_far.append(record["code"])

    try:
        with st.spinner("Agent is working…"):
            run = run_agent(task, expected.strip() or None, max_retries, on_attempt=on_attempt,
                            starting_code=starting_code.strip() or None)
        st.session_state.last_run = run  # keep it so it survives page reruns
        show_final_status(run)
    except Exception as e:  # missing API key, no internet, rate limit...
        st.error(f"Error: {e}")

elif "last_run" in st.session_state:
    # The page re-ran (e.g. a slider moved): redraw the last run from memory.
    run = st.session_state.last_run
    previous = None
    for record in run["attempts"]:
        show_attempt(record, previous)
        previous = record["code"]
    show_final_status(run)

# ----------------------------- History -------------------------------------
st.divider()
st.subheader("📜 Run history (from logs/history.json)")
history = load_history()
if not history:
    st.info("No runs yet.")
else:
    rows = [
        {
            "time": r["timestamp"],
            "task": r["task"][:80],
            "status": r["status"],
            "attempts": r["total_attempts"],
            "total time (s)": r["total_time_s"],
        }
        for r in reversed(history)  # newest first
    ]
    st.dataframe(rows, width="stretch")
    with st.expander("Raw JSON of the latest run"):
        st.json(history[-1])
