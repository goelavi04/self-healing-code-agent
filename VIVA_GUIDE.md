# Viva Guide: Line-by-Line Explanation

Line numbers match the files exactly as they are now. Open each file next to this guide.
Read the files in this order, because it follows the data: **executor → prompts →
test_cases → agent → app**.

---

## The 30-second explanation (say this first)

> "The user types a task in English. `agent.py` sends it to an LLM on Groq, which writes
> Python code. `executor.py` runs that code in a separate process with a 10-second limit.
> `diagnose()` checks three failures: a crash, a timeout, or wrong output (using
> `test_cases.py`). If it failed, the original task, the previous code and the full error
> go back to the LLM in a repair prompt from `prompts.py`. This loops until the code passes
> or we hit `MAX_RETRIES`. Every attempt is logged to a JSON file, and `app.py` shows it
> all in a Streamlit web page."

---

## 1. `executor.py`: runs the code safely

| Lines | Code | Explanation |
|---|---|---|
| 1–11 | `"""..."""` | Module docstring. Explains why we use a **separate process**: if we ran the code with `exec()` inside our own program, a crash or an infinite loop would crash or freeze the agent too. It also notes that this is *not* a real security sandbox. |
| 13 | `import os` | For file paths (`os.path.join`) and the environment variables (`os.environ`). |
| 14 | `import subprocess` | The standard-library module that starts other programs. This is the core of the file. |
| 15 | `import sys` | We need `sys.executable`, the path of the Python interpreter that is running right now. |
| 16 | `import tempfile` | Creates a temporary folder that deletes itself. |
| 17 | `import time` | To measure how long the code ran. |
| 20 | `TIMEOUT_SECONDS = 10` | A constant: the maximum run time. Capital letters are the Python convention for constants. |
| 23 | `def run_code(code, timeout=TIMEOUT_SECONDS):` | Takes the code as a string. `timeout` has a default value, so callers can skip it. |
| 24–35 | docstring | Documents the dictionary that the function returns. |
| 38 | `with tempfile.TemporaryDirectory() as folder:` | Creates a temporary folder. Because of `with`, the folder and everything in it is **deleted automatically** when the block ends, even if an error happens. |
| 39 | `script_path = os.path.join(folder, "generated_code.py")` | Builds the full path of the file we'll write. `os.path.join` uses the right slash for each OS (`\` on Windows, `/` on Linux). |
| 42–43 | `with open(script_path, "w", encoding="utf-8") as f: f.write(code)` | Writes the code into the file. `"w"` means write mode. `encoding="utf-8"` handles any special characters. The `with` closes the file automatically. |
| 46 | `env = os.environ.copy()` | A copy of the current environment variables. We copy them so we don't change the agent's own environment. |
| 47 | `env["PYTHONIOENCODING"] = "utf-8"` | Tells the child Python to print in UTF-8. Without it, Windows may crash when the code prints an emoji or a ✓. |
| 49 | `start = time.time()` | Records the start time (seconds since 1970). |
| 50 | `try:` | We expect a possible `TimeoutExpired` exception. |
| 51–61 | `subprocess.run([...], ...)` | **The key line.** It starts a new Python process and waits for it to finish. Arguments, one by one: |
| 52 | `[sys.executable, script_path]` | The command to run, as a list: `python generated_code.py`. `sys.executable` makes sure it's the same Python (the venv's Python). |
| 53 | `cwd=folder` | The child's working directory is the temp folder, so any files it creates get deleted. |
| 54 | `capture_output=True` | Collects stdout and stderr into variables instead of printing them on screen. |
| 55 | `text=True` | Gives us `str` instead of `bytes`. |
| 56–57 | `encoding="utf-8", errors="replace"` | Decodes as UTF-8. If a byte is invalid, it's replaced with `?` instead of crashing. |
| 58 | `stdin=subprocess.DEVNULL` | The child gets no keyboard input. If the code calls `input()`, it gets an `EOFError` straight away instead of waiting forever. |
| 59 | `timeout=timeout` | If the child runs longer than 10 s, Python **kills it** and raises `TimeoutExpired`. |
| 60 | `env=env` | Uses our modified environment from line 46. |
| 62–69 | `return {...}` | The program finished, so we return a dictionary. `completed.returncode` is **0 for success**, and anything else (usually 1) means it crashed. `stderr` contains the traceback. `round(..., 2)` gives 2 decimal places. |
| 70 | `except subprocess.TimeoutExpired:` | We get here if the code ran too long. |
| 71–79 | `return {...}` | The same dictionary shape, but `timed_out=True` and `returncode=None`, because the program never finished on its own. Using the same shape means the caller doesn't need special cases. |
| 83 | `if __name__ == "__main__":` | Runs only when you start this file directly (`python executor.py`), not when another file imports it. |
| 84–86 | three `run_code(...)` calls | A self-test with one success, one crash (`1/0`) and one infinite loop with a 2 s timeout. **This is a good live demo.** |

---

## 2. `prompts.py`: the text we send to the LLM

| Lines | Code | Explanation |
|---|---|---|
| 1–8 | docstring | There are two situations: **generate** (the first attempt) and **repair** (every later attempt). |
| 11–19 | `SYSTEM_PROMPT = """..."""` | The **system prompt** sets the LLM's role and rules for every request. A triple-quoted string can span several lines. |
| 15 | "ONE Python code block wrapped in \`\`\`python fences" | So that `extract_code()` can find the code reliably. |
| 16 | "no input() calls, no command-line arguments" | Our executor gives no keyboard input, so the program must run on its own. |
| 18 | "Print ONLY what the task asks for" | Extra text like `"The answer is: 61"` would fail the expected-output comparison. |
| 22–27 | `def build_generate_prompt(task):` | Prompt for the first attempt: just the task, inside an **f-string** (`f"""..."""`), where `{task}` is replaced by the variable's value. |
| 30 | `def build_repair_prompt(task, previous_code, error, attempt_number):` | Prompt for the repair attempts. |
| 38 | "This is repair attempt #..." | Tells the model this is a retry. |
| 40–41 | `=== ORIGINAL TASK ===` | **Required item 1:** the task, so the model remembers the goal. |
| 43–46 | `=== PREVIOUS CODE ===` | **Required item 2:** the code that failed, inside \`\`\`python fences. |
| 48–49 | `=== WHAT WENT WRONG ===` | **Required item 3:** the full traceback, the timeout message, or the wrong-output report. |
| 52 | "Find the root cause" | Asks it to reason about the cause, not just patch the symptom. |
| 53 | "Return the COMPLETE corrected script" | We run the reply directly, so a partial snippet would not run. |
| 54–55 | "ModuleNotFoundError … CANNOT be installed" | Without this, the LLM often says "run pip install" instead of rewriting the code. This line is what makes the missing-library demos heal. |
| 56 | "Do NOT hard-code the expected output" | Defends against cheating with `print("61")`. See Limitations. |

---

## 3. `test_cases.py`: the wrong-output check and the demo data

| Lines | Code | Explanation |
|---|---|---|
| 1–10 | docstring | A program can run without crashing and still be wrong. This file catches that. |
| 13 | `def normalize(text):` | Removes **invisible** differences before comparing. |
| 20 | `lines = text.strip().splitlines()` | `strip()` removes blank lines and spaces at the start and end. `splitlines()` splits on `\n` *or* `\r\n` (Windows), so line endings don't matter. |
| 21 | `return "\n".join(line.rstrip() for line in lines)` | Removes trailing spaces from each line, then joins the lines back together with `\n`. The `(... for ...)` part is a **generator expression**. |
| 24 | `def check_output(actual_output, expected_output):` | Returns a **tuple** `(passed, message)`. |
| 31–32 | `if expected_output is None or ...: return True, ""` | No expected output was given, so we can only check for crashes. It counts as a pass. |
| 34–35 | `actual = normalize(...)` / `expected = normalize(...)` | Normalize both sides. |
| 37–38 | `if actual == expected: return True, ""` | Exact string comparison. |
| 41–42 | `actual_lines = ...splitlines()` | Split both outputs into lists of lines. |
| 44 | `for i in range(max(len(...), len(...))):` | Loop up to the **longer** list, so missing or extra lines are caught too. |
| 45–46 | `got = actual_lines[i] if i < len(actual_lines) else "<missing line>"` | A **conditional expression** (one-line if/else). It avoids an `IndexError` when one list is shorter. |
| 47–49 | `if got != want: first_difference = ...; break` | Finds the **first** differing line and stops. `!r` shows the value with quotes, so hidden spaces are visible. |
| 51–56 | `message = (...)` | Builds the error text that the LLM will see. Strings next to each other inside brackets are joined automatically. |
| 57 | `return False, message` | Fail, plus an explanation. |
| 63–… | `DEMO_TASKS = [ {...}, ... ]` | A **list of dictionaries**. Each one has `name` (shown in the menu), `task`, `expected`, and an optional `buggy_code`. |
| 68 | demo 1 (humanize) | The library isn't installed, so the first attempt raises `ModuleNotFoundError`. |
| 79 | demo 2 (date range) | An off-by-one trap: an inclusive range needs `+1`. |
| 90 | demo 3 (date strings) | `strptime` can't parse "5th" or "Sept". |
| 109–… | demos 4–7 with `"buggy_code"` | **Hand-written broken code.** The agent runs it as attempt 1 without asking the LLM, so it always fails, and the demo always shows healing. The code is written as several `"..."` strings, one per line, ending in `\n`. Python joins them into one string. |

---

## 4. `agent.py`: the main loop (the most important file)

### Imports and settings (lines 1–36)

| Lines | Code | Explanation |
|---|---|---|
| 1–13 | docstring | An ASCII diagram of the loop. |
| 15 | `import json` | To read and write the log file. |
| 16 | `import os` | For paths and to read the API key from the environment. |
| 17 | `import re` | **Regular expressions**, used to extract code from the fences. |
| 18 | `import sys` | Used in `main()` to configure the console output. |
| 19 | `import time` | Timing. |
| 20 | `from datetime import datetime` | The timestamp for each run. |
| 22 | `from dotenv import load_dotenv` | From `python-dotenv`. It reads the `.env` file. |
| 23 | `from groq import Groq` | The official Groq client class. |
| 25–27 | `from executor import ...` etc. | Imports our own three modules. This is why the project is split into files: each file does one job. |
| 31 | `MODEL = "openai/gpt-oss-120b"` | Which LLM to use. The comment on line 30 explains that Llama 3.3 was retired. |
| 32 | `MAX_RETRIES = 3` | The number of **repairs** after the first attempt, so at most 4 attempts in total. |
| 33 | `TEMPERATURE = 0.2` | Controls randomness. 0 means nearly deterministic and 1+ means creative. Low is better for code. |
| 36 | `LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "history.json")` | Read it from the inside out: `__file__` is this file's path, `abspath` makes it absolute, `dirname` takes its folder, and `join` adds `logs/history.json`. This way the log is always next to the code, wherever you run it from. |

### `create_client()` (lines 40–46)

| Line | Explanation |
|---|---|
| 42 | `load_dotenv()` reads `.env` and puts `GROQ_API_KEY=...` into the environment variables. |
| 43 | `os.getenv("GROQ_API_KEY")` reads it. It returns `None` if the key is missing. |
| 44–45 | If the key is missing, we raise a clear `RuntimeError` instead of a confusing error later on. |
| 46 | Creates and returns the Groq client object. |

**Why `.env`?** So the secret key is never written into the code or pushed to GitHub (`.gitignore` excludes `.env`).

### `ask_llm()` (lines 49–59)

| Line | Explanation |
|---|---|
| 51 | `client.chat.completions.create(...)` is the API call. It uses the OpenAI-compatible "chat completions" format. |
| 52 | Which model to use. |
| 53–56 | `messages` is a list of chat messages. The **system** message holds the rules and the **user** message holds the request. Each message is a dictionary with a `role` and `content`. |
| 57 | The temperature. |
| 59 | `response.choices[0].message.content`: the API can return several choices, so we take the first one's text. |

### `extract_code()` (lines 62–75)

| Line | Explanation |
|---|---|
| 69 | The regex ```` r"```(?:python\|py)?[ \t]*\n(.*?)```" ````, piece by piece: `` ``` `` matches the opening fence. `(?:python\|py)?` optionally matches the word python or py (`?:` means "group, but don't capture"). `[ \t]*` matches any spaces. `\n` matches the end of the fence line. `(.*?)` **captures** the code; the `?` makes it *non-greedy*, so it stops at the *first* closing fence. Then `` ``` `` matches the closing fence. The `r"..."` is a raw string, so backslashes aren't treated as escapes. |
| 70 | `re.findall` returns a list of everything captured. `re.DOTALL` lets `.` also match newlines, which code needs. `re.IGNORECASE` also accepts \`\`\`Python. |
| 71–73 | If blocks were found, return the **longest** one (`max(..., key=len)`), because that's usually the full program rather than a small example. |
| 75 | Fallback when there are no complete fences: remove any stray \`\`\` and use the whole reply. |

### `diagnose()` (lines 79–100)

This returns **`None` if the run passed**, or the error text if it failed. The order of the checks matters:

| Line | Explanation |
|---|---|
| 88–90 | **Timeout**, checked first. The program was killed, so there's no useful return code. |
| 92–94 | **Crash**: return code ≠ 0. We return the traceback from stderr. The `or` gives a fallback message if stderr is empty. |
| 96–98 | **Wrong output**: only reached if the program ran successfully. It calls `check_output()` from `test_cases.py`. |
| 100 | No problems were found, so return `None`. |

### Logging (lines 104–121)

| Line | Explanation |
|---|---|
| 106–107 | If the log file doesn't exist yet, the history is empty. |
| 108–112 | Read the JSON. If the file is damaged (`JSONDecodeError`), start fresh instead of crashing. |
| 117 | `os.makedirs(..., exist_ok=True)` creates the `logs` folder. With `exist_ok=True`, it doesn't fail if the folder is already there. |
| 118–119 | Load the old runs and append the new one. |
| 120–121 | Write the whole list back. `indent=2` makes the file readable for humans. |

### `run_agent()`: the loop itself (lines 125–210)

| Line | Explanation |
|---|---|
| 125–126 | Parameters: the **task**, an optional **expected_output**, **max_retries**, an optional **client** (lets tests pass a fake one), **on_attempt** (a callback the UI uses to draw each step live), and **starting_code** (the buggy samples). |
| 136–137 | Create a Groq client if none was given. |
| 139 | `max_attempts = 1 + max_retries`: one first try plus N repairs. |
| 140–142 | `attempts` collects one record per attempt. `code` and `error` must exist *before* the loop, because the repair prompt uses the **previous** attempt's values. |
| 144 | `for attempt_number in range(1, max_attempts + 1):` counts 1, 2, 3, 4. `range` stops *before* its end value, which is why there's a `+1`. |
| 146–150 | **Buggy-sample mode**: on attempt 1 with starting code, use that code and skip the LLM. `kind = "given"`. |
| 152–154 | **GENERATE**: on attempt 1 with no starting code, build the normal prompt. |
| 155–157 | **REPAIR**: on any later attempt, build the repair prompt from the task, the **previous code** and the **previous error**. |
| 159–161 | Time the LLM call. |
| 162 | Extract clean code from the reply. |
| 165 | **EXECUTE**: run it in the subprocess. |
| 168 | **DIAGNOSE**: `error` is `None` if it passed, otherwise the error text. This value is used by the *next* repair prompt (line 157). |
| 171–181 | Build the log record: the attempt number, kind, code, output, error, passed flag, and the three timings. `"passed": error is None` stores a boolean. |
| 182 | Save the record in the list. |
| 183–184 | If a callback was given, call it. Streamlit uses this to show the attempt **immediately** instead of waiting for the whole loop. |
| 187–188 | If it passed, `break` leaves the loop early. Otherwise the loop continues, and the next round is a **repair**. |
| 191–196 | Final status: passed on attempt 1 → `passed_first_try`; passed later → `healed`; still failing after all attempts → `failed`. |
| 198–208 | A dictionary describing the whole run. `isoformat(timespec="seconds")` gives `2026-10-13T14:02:11`. `sum(a["time_taken_s"] for a in attempts)` adds up the time of every attempt. |
| 209–210 | Save to the log and return the run. |

### `status_message()` (lines 213–220)

This turns the status into the sentence shown to the user, for example **"Healed in 3 attempts"**.

### CLI: `print_attempt()` and `main()` (lines 224–277)

| Line | Explanation |
|---|---|
| 224–237 | Prints one attempt in the terminal, with `[PASS]` or `[FAIL]`. `"=" * 70` repeats the character 70 times. |
| 242 | `sys.stdout.reconfigure(errors="replace")`: some Windows terminals can't show every character, so they print `?` instead of crashing. |
| 246–247 | `enumerate(DEMO_TASKS, start=1)` gives numbered menu items 1, 2, 3, and so on. |
| 249 | Reads the user's choice. `strip()` removes stray spaces. |
| 252 | Checks whether the choice is a valid demo number, as a string. |
| 253 | `int(choice) - 1`: the menu starts at 1, but list indexes start at 0. |
| 256 | `demo.get("buggy_code")` returns `None` if the key doesn't exist, while `demo["buggy_code"]` would crash. |
| 261–263 | Custom task. The user can type `\n` to mean a new line in the expected output. `or None` turns an empty string into `None`. |
| 265–269 | Runs the agent. `except Exception` catches problems like a missing key, no internet, or a rate limit, and prints a friendly message instead of a traceback. |
| 271–273 | Prints the final result and where the log was saved. |
| 276–277 | `if __name__ == "__main__": main()` runs the CLI only when the file is executed directly. When `app.py` imports `agent`, `main()` does **not** run. |

---

## 5. `app.py`: the Streamlit web UI

**The key Streamlit idea for your viva:** Streamlit **re-runs the whole script from top to
bottom** every time the user interacts with the page (clicks, types, moves a slider).
`st.session_state` is a dictionary that **survives** those re-runs.

| Lines | Code | Explanation |
|---|---|---|
| 10 | `import difflib` | A standard-library module that computes the difference between two texts. We use it to show "the fix". |
| 12 | `import streamlit as st` | `st` is the conventional short name. |
| 14–15 | imports | We reuse `run_agent` from `agent.py`, so the UI has **no logic of its own**. It only displays results. |
| 17 | `st.set_page_config(...)` | The browser tab title and icon, and a wide layout. |
| 18–19 | `st.title`, `st.caption` | The heading and the subtitle. |
| 21 | `CUSTOM_TASK = ...` | The first option in the dropdown. |
| 24–35 | `def load_demo():` | Runs when the dropdown changes. It finds the chosen demo and copies its task, expected output and buggy code into `session_state`. The **text boxes are linked to those same keys**, so they update. If "Write my own task" was chosen, it clears the boxes. |
| 38 | `def show_attempt(record, previous_code):` | Draws one attempt. |
| 40–41 | icon and title | ✅ or ❌, plus the attempt number, kind and time. |
| 42 | `with st.expander(title, expanded=True):` | A collapsible box. Everything inside the `with` block goes into it. |
| 44 | `st.code(..., language="python")` | Shows the code with syntax highlighting. |
| 47–53 | `difflib.unified_diff(...)` | Compares the previous code with this attempt's code. Lines starting with `-` were removed and lines starting with `+` were added. This is **"the fix"**. `lineterm=""` stops it adding extra newlines. |
| 55–56 | Output | What the program printed. |
| 58–62 | `st.success` / error box | A green "Passed" box, or the error text that was sent back to the LLM. |
| 65–71 | `show_final_status()` | A red box for failed, green otherwise. |
| 75 | `with st.sidebar:` | Everything inside goes into the left sidebar. |
| 77–78 | `st.selectbox(..., key="demo_choice", on_change=load_demo)` | The dropdown. `key` stores its value in `session_state`, and `on_change` calls `load_demo` when it changes. |
| 79 | `st.slider(..., 0, 5, MAX_RETRIES)` | Minimum 0, maximum 5, default 3. |
| 85–89 | three `st.text_area(..., key=...)` | The input boxes. Because of `key=`, their content lives in `session_state`, which is how `load_demo` can fill them. |
| 92 | `if st.button(..., disabled=not task.strip()):` | `st.button` returns `True` only on the re-run caused by the click. The button is disabled while the task box is empty. |
| 93 | `codes_so_far = []` | Remembers each attempt's code, so the next attempt can show a diff. |
| 95–99 | `def on_attempt(record):` | The **callback** passed to `run_agent`. It runs after every attempt and draws it **immediately**, so you see the healing happen live. It's defined inside the `if` so it can use `codes_so_far` (a **closure**). |
| 101–104 | `with st.spinner(...): run = run_agent(...)` | Shows a loading spinner while the agent works. `expected.strip() or None` turns an empty box into `None`. |
| 105 | `st.session_state.last_run = run` | Saves the result so it **survives the next re-run**. |
| 107–108 | `except Exception` | Shows errors (bad key, no internet) in a red box instead of crashing the page. |
| 110–117 | `elif "last_run" in st.session_state:` | On a re-run (for example after moving the slider), the button returns `False`. Without this branch, the results would disappear, so we redraw them from memory. |
| 120–121 | divider, subheader | The history section. |
| 122 | `history = load_history()` | Reads `logs/history.json`. |
| 126–135 | `rows = [ {...} for r in reversed(history) ]` | A **list comprehension** that builds one table row per run, newest first. `r["task"][:80]` is a *slice* that shortens long tasks. |
| 136 | `st.dataframe(rows, width="stretch")` | An interactive table at full width. |
| 137–138 | `st.json(history[-1])` | The raw JSON of the latest run. `[-1]` is the last item. |

---

## Likely viva questions

**Q: Why `subprocess` and not `exec()`?**
`exec()` runs the code inside our own process. A crash, an infinite loop or `sys.exit()`
would take down the agent. A subprocess is isolated, can be killed on a timeout, and its
stdout and stderr can be captured separately.

**Q: Is it safe to run LLM-generated code?**
No. A subprocess is **not** a sandbox: the code can still read and delete files or use the
network. We only add a timeout, a temporary folder and no stdin. For production you would
use Docker or a VM with no network and resource limits. This is in the README under
Limitations & Safety.

**Q: How do you detect "wrong output"?**
We compare stdout with the user's expected output after normalising (ignoring trailing
spaces and line-ending differences). A mismatch becomes a `WrongOutputError` message that
shows the first differing line, and that message goes into the repair prompt.

**Q: What stops an infinite repair loop?**
`MAX_RETRIES`. The `for` loop runs at most `1 + MAX_RETRIES` times, so it always ends.

**Q: What if the LLM just prints the expected answer?**
That's the "fixing the test instead of the code" problem. The prompt forbids it, but that
is only a request. Real fixes are hidden test cases the LLM never sees, and several inputs
per task.

**Q: Why not LangChain?**
The brief asked for plain Python so the logic is visible. The whole loop is one `for` loop
in `run_agent()`, and no framework hides any steps.

**Q: What's the temperature and why 0.2?**
It controls randomness. For code we want predictable, correct output, so we keep it low.
It isn't 0, so that a repair can try a different approach.

**Q: Why does the repair prompt include the original task?**
Without it, the LLM only sees broken code and an error. It might "fix" the error by
changing what the program does. The task keeps it focused on the real goal.

**Q: How does the UI show attempts live?**
Through the `on_attempt` **callback**. `run_agent()` calls it after each attempt, and the
UI draws that attempt straight away, before the next LLM call starts.

**Q: Why the `if __name__ == "__main__":` lines?**
So that importing `agent.py` (which `app.py` does) doesn't start the CLI menu.
That code only runs when the file is executed directly.

**Q: Why did you change from Llama 3.3 to gpt-oss-120b?**
Groq retired `llama-3.3-70b-versatile`, and the API returned "model does not exist". The
model is one constant (`MODEL`), so switching was a one-line change.
