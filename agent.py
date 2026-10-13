"""
agent.py - The Self-Healing Code Agent (the main loop).

    task --> GENERATE code --> EXECUTE it --> DIAGNOSE the result
                 ^                                   |
                 |          failed? (crash /         |
                 +---- REPAIR <-- wrong output / ----+
                                  timeout)

The loop stops when the code passes, or when we run out of retries.

Run from the terminal:   python agent.py
"""

import json
import os
import re
import sys
import time
from datetime import datetime

from dotenv import load_dotenv
from groq import Groq

from executor import run_code
from prompts import SYSTEM_PROMPT, build_generate_prompt, build_repair_prompt
from test_cases import DEMO_TASKS, check_output

# ----------------------------- Settings ------------------------------------
# Free model on Groq. ("llama-3.3-70b-versatile" was retired; see the model list at console.groq.com)
MODEL = "openai/gpt-oss-120b"
MAX_RETRIES = 3                     # repair attempts allowed AFTER the first attempt
TEMPERATURE = 0.2                   # low = more predictable code

# The log file lives in a "logs" folder next to this file.
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "history.json")


# ----------------------------- LLM helpers ---------------------------------
def create_client():
    """Read GROQ_API_KEY from the .env file and create a Groq client."""
    load_dotenv()  # copies the values from .env into environment variables
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not found. Create a .env file containing: GROQ_API_KEY=your_key_here")
    return Groq(api_key=api_key)


def ask_llm(client, user_prompt):
    """Send one prompt to the LLM and return its text reply."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},  # the rules
            {"role": "user", "content": user_prompt},      # the actual request
        ],
        temperature=TEMPERATURE,
    )
    return response.choices[0].message.content


def extract_code(llm_text):
    """
    Pull the Python code out of the LLM's reply.

    LLMs usually answer like:   Here you go:\n```python\nprint("hi")\n```
    The regex captures whatever is between ```python (or ``` / ```py) and the closing ```.
    """
    pattern = r"```(?:python|py)?[ \t]*\n(.*?)```"
    blocks = re.findall(pattern, llm_text, re.DOTALL | re.IGNORECASE)
    if blocks:
        # If there are several blocks, the longest one is usually the full program.
        return max(blocks, key=len).strip()
    # No complete fenced block: remove any stray fences and use the whole reply.
    return llm_text.replace("```python", "").replace("```", "").strip()


# ----------------------------- Diagnosis -----------------------------------
def diagnose(result, expected_output):
    """
    Decide whether an execution failed. Returns None if it PASSED,
    otherwise a text description of the error (this is what the LLM will see).
    Three kinds of failure:
        1. timeout       - the program ran too long (e.g. infinite loop)
        2. crash         - the program raised an exception (non-zero return code)
        3. wrong output  - it ran fine but printed the wrong thing
    """
    if result["timed_out"]:
        return (f"TimeoutError: the program did not finish within {result['timeout']} seconds. "
                "It probably has an infinite loop or is waiting for input.")

    if result["returncode"] != 0:
        # stderr holds the full Python traceback.
        return result["stderr"].strip() or f"The program exited with error code {result['returncode']}."

    passed, message = check_output(result["stdout"], expected_output)
    if not passed:
        return message

    return None  # no problems found


# ----------------------------- Logging -------------------------------------
def load_history():
    """Read all past runs from the JSON log file (empty list if none yet)."""
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []  # the file was damaged; start a fresh history


def save_log(run):
    """Append one run (with all its attempts) to the JSON log file."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    history = load_history()
    history.append(run)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


# ----------------------------- The main loop -------------------------------
def run_agent(task, expected_output=None, max_retries=MAX_RETRIES, client=None, on_attempt=None,
              starting_code=None):
    """
    Generate -> execute -> diagnose -> repair, until success or out of retries.

    on_attempt:    optional function called after every attempt (the Streamlit
                   app uses it to show each attempt live, as it happens).
    starting_code: optional code to use for attempt 1 INSTEAD of asking the LLM
                   (used for the hard-coded buggy demo samples).
    Returns a dict describing the whole run (also saved to the log file).
    """
    if client is None:
        client = create_client()

    max_attempts = 1 + max_retries  # 1 first try + N repairs
    attempts = []                   # one record per attempt
    code = ""
    error = None

    for attempt_number in range(1, max_attempts + 1):
        # ---- 1. GENERATE (first time) or REPAIR (every later time) ----
        if attempt_number == 1 and starting_code:
            # Use the code the user gave us; no LLM call needed.
            kind = "given"
            code = starting_code
            llm_time = 0.0
        else:
            if attempt_number == 1:
                kind = "generate"
                prompt = build_generate_prompt(task)
            else:
                kind = "repair"
                prompt = build_repair_prompt(task, code, error, attempt_number)

            llm_start = time.time()
            llm_text = ask_llm(client, prompt)
            llm_time = round(time.time() - llm_start, 2)
            code = extract_code(llm_text)

        # ---- 2. EXECUTE ----
        result = run_code(code)

        # ---- 3. DIAGNOSE ----
        error = diagnose(result, expected_output)

        # ---- Record this attempt ----
        record = {
            "attempt": attempt_number,
            "kind": kind,                    # "given", "generate" or "repair"
            "code": code,
            "stdout": result["stdout"],
            "error": error,                  # None means it passed
            "passed": error is None,
            "llm_time_s": llm_time,
            "run_time_s": result["run_time_s"],
            "time_taken_s": round(llm_time + result["run_time_s"], 2),
        }
        attempts.append(record)
        if on_attempt is not None:
            on_attempt(record)

        # ---- 4. Stop if it worked; otherwise loop again (= REPAIR) ----
        if error is None:
            break

    # Final status of the whole run.
    if error is None and len(attempts) == 1:
        status = "passed_first_try"
    elif error is None:
        status = "healed"
    else:
        status = "failed"

    run = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "task": task,
        "expected_output": expected_output,
        "starting_code": starting_code,
        "model": MODEL,
        "status": status,
        "total_attempts": len(attempts),
        "total_time_s": round(sum(a["time_taken_s"] for a in attempts), 2),
        "attempts": attempts,
    }
    save_log(run)
    return run


def status_message(run):
    """A short human-readable summary of the final status."""
    n = run["total_attempts"]
    if run["status"] == "passed_first_try":
        return "Passed on the first attempt (no healing needed)"
    if run["status"] == "healed":
        return f"Healed in {n} attempts"
    return f"Failed after {n} attempts"


# ----------------------------- Command-line interface ----------------------
def print_attempt(record):
    """Pretty-print one attempt in the terminal."""
    line = "=" * 70
    print(f"\n{line}\nAttempt {record['attempt']} ({record['kind']})  -  {record['time_taken_s']}s\n{line}")
    print("--- Code ---")
    print(record["code"])
    print("--- Output ---")
    print(record["stdout"].strip() or "<nothing printed>")
    if record["passed"]:
        print("[PASS]")
    else:
        print("--- Error ---")
        print(record["error"])
        print("[FAIL] -> sending the error back to the LLM to repair...")


def main():
    # Some Windows terminals can't show every character; print '?' instead of crashing.
    sys.stdout.reconfigure(errors="replace")

    print("Self-Healing Code Agent")
    print("-----------------------")
    for i, demo in enumerate(DEMO_TASKS, start=1):
        print(f"  {i}) {demo['name']}")
    print("  0) Type my own task")
    choice = input("Choose an option: ").strip()

    starting_code = None
    if choice in [str(i) for i in range(1, len(DEMO_TASKS) + 1)]:
        demo = DEMO_TASKS[int(choice) - 1]
        task = demo["task"]
        expected = demo["expected"]
        starting_code = demo.get("buggy_code")  # only the [Buggy code] samples have this
        print(f"\nTask:\n{task}\n\nExpected output:\n{expected}")
        if starting_code:
            print("\n(Attempt 1 will run the hard-coded buggy code instead of asking the LLM.)")
    else:
        task = input("\nDescribe the program you want: ").strip()
        expected = input("Expected output (optional; type \\n for a new line; Enter to skip): ")
        expected = expected.replace("\\n", "\n").strip() or None

    try:
        run = run_agent(task, expected, on_attempt=print_attempt, starting_code=starting_code)
    except Exception as e:  # e.g. missing API key, no internet, rate limit
        print(f"\nERROR: {e}")
        return

    print("\n" + "#" * 70)
    print(f"RESULT: {status_message(run)}  (total {run['total_time_s']}s)")
    print(f"Log saved to: {LOG_FILE}")


if __name__ == "__main__":
    main()
