# 🩹 Self-Healing Code Agent

You describe a programming task in **plain English**. An LLM writes Python code for it, the
agent **runs** that code, and if it fails (an exception, wrong output, or a timeout), the
error is sent back to the LLM to **repair**. This repeats until the code works or the agent
runs out of retries.

```
task ──► GENERATE ──► EXECUTE ──► DIAGNOSE ──► passed? ──yes──► ✅ Healed in N attempts
             ▲                                  │
             └──────────── REPAIR ◄──── no ─────┘   (up to MAX_RETRIES times, then ❌ Failed)
```

Built for a college lab project. The code is plain, commented Python, with **no LangChain
and no LangGraph**, so you can see every step of the loop.

---

## ✨ Features

- **Generate → Execute → Diagnose → Repair loop** in about 100 lines of plain Python (`agent.py`)
- **Safe-ish execution:** the code runs in a separate process with a **10-second timeout**, and stdout, stderr and the return code are captured
- **Three kinds of failure detected:** a crash (exception), **wrong output** (compared with the expected output), and a **timeout** (infinite loop)
- **Repair prompt** with the original task, the previous code and the **full traceback**
- Extracts code from LLM replies, even when it's wrapped in ```` ```python ```` fences
- **Streamlit web UI** that shows every attempt live, with the code, a diff of the fix, the output and the error, then **"Healed in N attempts"** or **"Failed"**
- **CLI** version with the same features
- Every run is **logged to `logs/history.json`** (attempt number, code, error, time taken) and shown as a history table in the UI
- **Demo tasks** and **hard-coded buggy samples** that reliably show healing

## 🧰 Tech stack

| Part | Used |
|---|---|
| Language | Python 3.10+ |
| LLM | [Groq API](https://console.groq.com) (free tier), model `openai/gpt-oss-120b`, via the official `groq` package |
| Secrets | `python-dotenv` (reads `GROQ_API_KEY` from `.env`) |
| Execution | `subprocess` (standard library) |
| UI | Streamlit |

> **Note on the model:** the project was first planned for `llama-3.3-70b-versatile`, but Groq
> has retired that model. To use a different model, change the `MODEL` line in `agent.py`.
> Your account's models are listed at <https://console.groq.com/docs/models>.

---

## 📁 Project structure

```
self_healing_loop/
├── agent.py          # main loop (generate → execute → diagnose → repair) + CLI + logging
├── executor.py       # runs code in a subprocess with a 10 s timeout
├── prompts.py        # system prompt, generate prompt, repair prompt
├── test_cases.py     # expected-output check + demo tasks + buggy samples
├── app.py            # Streamlit web UI
├── requirements.txt  # groq, python-dotenv, streamlit
├── .env.example      # template for your API key (copy to .env)
├── .gitignore        # keeps .env, .venv and logs out of git
└── logs/history.json # created automatically: every run and every attempt
```

| File            | What it does |
|-----------------|--------------|
| `agent.py`      | The main loop: generate → execute → diagnose → repair. Also the CLI, the code extraction and the JSON logging. |
| `executor.py`   | Runs generated code in a separate Python process with `subprocess`, a 10 s timeout, and captures stdout, stderr and the return code. |
| `prompts.py`    | The system prompt, the generate prompt, and the repair prompt (task + previous code + full error). |
| `test_cases.py` | Compares the actual output with the expected output, so wrong output also counts as a failure. Also holds the demo tasks and buggy samples. |
| `app.py`        | Streamlit UI. Shows each attempt as a step (code, fix, output, error), the final status and the run history. |

---

## 🚀 Setup (step by step)

### Windows (PowerShell)

```powershell
# 1. Get the code
git clone https://github.com/goelavi04/self-healing-code-agent.git
cd self-healing-code-agent

# 2. Create a virtual environment
python -m venv .venv

# 3. Activate it  (your prompt will start with "(.venv)")
.\.venv\Scripts\Activate.ps1
#    If you see "running scripts is disabled on this system", run this once, then try again:
#    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# 4. Install the requirements
python -m pip install --upgrade pip
pip install -r requirements.txt

# 5. Add your API key (get a free one at https://console.groq.com/keys)
Copy-Item .env.example .env
notepad .env          # replace your_groq_api_key_here with your real key, then save
#    Put the key in .env, NOT in .env.example. .env.example gets committed to git.

# 6a. Run the command-line version
python agent.py

# 6b. Run the web UI (opens http://localhost:8501 in your browser; Ctrl+C to stop)
streamlit run app.py
```

### macOS / Linux (bash)

```bash
git clone https://github.com/goelavi04/self-healing-code-agent.git
cd self-healing-code-agent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
nano .env                     # put in your real key: GROQ_API_KEY=gsk_...
python agent.py               # CLI
streamlit run app.py          # web UI
```

To check that the executor works on its own (no API key needed): `python executor.py`

---

## 🖥️ Usage

**Web UI** (`streamlit run app.py`)
1. In the sidebar, choose a demo from **Load a demo task**, or type your own task.
2. Optional: fill in **Expected output**. Wrong output then also counts as a failure.
3. Optional: paste broken code into **Starting code**. Attempt 1 runs it as-is, then the LLM heals it.
4. Set **Max retries** with the slider (default 3), then click **▶ Run agent**.
5. Watch each attempt appear. The run history table at the bottom is read from `logs/history.json`.

**CLI** (`python agent.py`): choose a demo number, or `0` to type your own task and expected output.

---

## 🧪 Example tasks to type (tested: they fail first, then heal)

Copy any of these into the **Task** box. Each one was run twice against `openai/gpt-oss-120b`.
Both times, the first attempt failed and the agent **healed it in 2 attempts**.

**Missing library → `ModuleNotFoundError` → rewritten with the standard library**

| Task (paste this) | Expected output (optional) |
|---|---|
| `Use the tabulate library to print a table with columns Name and Marks for: Asha 91, Ravi 78, Meera 85.` | *(leave empty)* |
| `Use the PyYAML library to parse this YAML text and print the value of the port:`<br>`server:`<br>`  host: localhost`<br>`  port: 8080` | `8080` |
| `Use the colorama library to print the word SUCCESS in green.` | *(leave empty)* |
| `Use the num2words library to print the number 2024 in English words.` | *(leave empty)* |

**Too slow → `TimeoutError` after 10 s → rewritten with a faster algorithm**

| Task (paste this) | Expected output (optional) |
|---|---|
| `Calculate the 40th Fibonacci number (where fib(1) = fib(2) = 1) using a simple recursive function, and print it.` | `102334155` |
| `Print the sum of all prime numbers below 2,000,000 by checking each number with a simple loop that tries dividing by every number smaller than it.` | `142913828922` |

**Why do these fail?** The libraries aren't installed, and the agent never installs
packages, so the first attempt crashes and the LLM has to rewrite the code with only the
standard library. The slow tasks ask for an inefficient method on purpose, so the first
attempt hits the 10-second timeout, and the LLM switches to memoisation or a sieve.

**Tasks that usually pass on the first try** (use these to show the normal case):
`Print the first 10 prime numbers.`, `Reverse the string "hello world" and print it.`,
`Print the multiplication table of 7 from 1 to 10.`

---

## 🎬 Built-in demos (sidebar / CLI menu)

### LLM-generated (attempt 1 comes from the LLM)

| # | Task | What happens |
|---|------|--------------|
| 1 | Use the `humanize` library to print 1234567, 5000000000 and 999 in words | `humanize` is not installed, so the first attempt raises `ModuleNotFoundError` and is then healed. **Reliable.** |
| 2 | Count the days from 2024-01-01 to 2024-03-01, including both dates, and count the weekdays | An off-by-one trap: `(end - start).days` gives 60, but the right answer is 61. Weaker models fall for it; `gpt-oss-120b` usually gets it right the first time. |
| 3 | Convert `'March 5th, 2024'`, `'Sept 9 2023'`, `'1st of Jan 2023'` and others to YYYY-MM-DD using only the standard library | `strptime` can't parse "5th", "1st" or "Sept", so the first attempt raises a `ValueError` and is then healed. **Usually reliable.** |

### Hard-coded buggy samples (guaranteed healing)

Demos 4–7 come with **hand-written broken code**. Attempt 1 runs that code as-is, without
the LLM, so it **always fails**. Then the LLM repairs it. Each one shows a different kind of failure:

| # | Bug in the sample code | Failure the agent sees |
|---|------------------------|------------------------|
| 4 | Uses `math.sqrt` without `import math`, and `range(1, 31)` misses 31 | `NameError` (crash) |
| 5 | `range((end - start).days)` leaves out the end date | Prints 60 / 44 instead of 61 / 45 (**wrong output**, no crash) |
| 6 | `strptime(d, '%B %d, %Y')` on `'March 5th, 2024'` | `ValueError` (crash) |
| 7 | `while` loop without `i += 1` | **Timeout** after 10 s (infinite loop) |

> LLMs are random. A task sometimes passes on the first try. If that happens, run it again.
> Every run is kept in the history, so you can always show an earlier healed run.

---

## 🏗️ Architecture

```
                        +------------------+
   User task  --------> |    agent.py      |  run_agent()
   (+ expected output)  |   (main loop)    |
   (+ starting code)    +--------+---------+
                                 |
          +----------------------+------------------------+
          |                      |                        |
          v                      v                        v
  +---------------+     +-----------------+      +-----------------+
  |  prompts.py   |     |   Groq API      |      |  executor.py    |
  | generate /    |---->| gpt-oss-120b    |      | subprocess +    |
  | repair prompt |     | returns code    |      | 10 s timeout    |
  +---------------+     +--------+--------+      +--------+--------+
                                 |                        |
                                 | extract_code()         | stdout / stderr /
                                 +---------> code ------->| return code
                                                          |
                                                          v
                                                 +-----------------+
                                                 |  diagnose()     |
                                                 |  + test_cases.py|
                                                 +--------+--------+
                                                          |
                              passed? ------- yes ------> DONE (Healed in N / Passed)
                                 |
                                 no  -> error text goes into the REPAIR prompt
                                 |      (loop again, up to MAX_RETRIES times)
                                 v
                              FAILED (out of retries)

   Every attempt is appended to logs/history.json.
   app.py (Streamlit) calls run_agent() and draws each attempt as it finishes.
```

---

## 🔁 How the loop works

1. **Generate.** `build_generate_prompt(task)` plus `SYSTEM_PROMPT` are sent to the LLM.
   The system prompt says: reply with one ```` ```python ```` block, no `input()`, and print only
   the result.
   If **starting code** was given (the buggy samples), attempt 1 skips the LLM and runs that
   code as-is. The record's `kind` is then `"given"` instead of `"generate"`.
2. **Extract.** `extract_code()` uses a regular expression to take the code from between the
   ```` ``` ```` fences. If there are several blocks, it takes the longest one. If there are no
   fences, it uses the whole reply.
3. **Execute.** `run_code()` writes the code to a temporary file and runs it with
   `subprocess.run([sys.executable, file], timeout=10, capture_output=True)`.
4. **Diagnose.** `diagnose()` checks three things, in this order:
   - **timeout:** the program was killed after 10 s
   - **crash:** the return code is not 0, and stderr holds the traceback
   - **wrong output:** `check_output()` compares stdout with the expected output (only if
     one was given)
5. **Repair.** If any check fails, `build_repair_prompt()` sends the **original task**, the
   **previous code**, and the **full error** to the LLM, which returns a complete corrected
   script. Go back to step 2.
6. **Stop.** The loop stops when an attempt passes or after `1 + MAX_RETRIES` attempts
   (default 3, so at most 4 attempts in total).
7. **Log.** The whole run is appended to `logs/history.json`.

**Final status:**
- `passed_first_try`: the first attempt worked
- `healed`: it worked after at least one repair ("Healed in N attempts")
- `failed`: still broken after the last retry

### Log format (`logs/history.json`)

```json
[
  {
    "timestamp": "2026-10-13T14:02:11",
    "task": "...",
    "expected_output": "61\n45",
    "starting_code": null,
    "model": "openai/gpt-oss-120b",
    "status": "healed",
    "total_attempts": 2,
    "total_time_s": 3.41,
    "attempts": [
      { "attempt": 1, "kind": "generate", "code": "...", "stdout": "60\n44\n",
        "error": "WrongOutputError: ...", "passed": false,
        "llm_time_s": 1.2, "run_time_s": 0.05, "time_taken_s": 1.25 },
      { "attempt": 2, "kind": "repair", "code": "...", "stdout": "61\n45\n",
        "error": null, "passed": true,
        "llm_time_s": 2.1, "run_time_s": 0.06, "time_taken_s": 2.16 }
    ]
  }
]
```

---

## ⚠️ Limitations & Safety

**Running untrusted code.** The LLM's code runs on your own computer with your user's
permissions. `subprocess` keeps a crash or an infinite loop away from the agent, but it is
**not a security sandbox**. The generated code could delete files, read your `.env`, or use
the network. This project only adds a timeout, a temporary working folder, and `stdin`
closed. A real system would run the code in a Docker container or a VM with no network,
a read-only filesystem, and CPU and memory limits. Only use this project with tasks you trust.

**Infinite fix loops.** The LLM can "fix" one bug and add another, or swing between two
wrong versions. `MAX_RETRIES` puts a hard limit on the loop so it always ends. The repair
prompt only includes the last attempt, so the model can't see what it already tried.
Sending the full history would help, but it uses more tokens.

**The LLM "fixing" the test instead of the code.** When the output is wrong, the repair
prompt shows the expected output. The model can then cheat with `print("61\n45")`.
That passes the check but solves nothing. The repair prompt tells it not to hard-code
answers, but that is only a request. Stronger defences are hidden test cases (inputs the
LLM never sees), several test inputs per task, and checking the code for hard-coded results.
Also, we only check the output, so a correct output does not prove the code is correct.

**Cost and latency.** Every repair is another LLM call, so a run with 4 attempts costs
about 4 times as much and takes 4 times as long as a single call. Repair prompts are also
longer than the first prompt, because they include the code and the traceback. The Groq
free tier has rate limits (requests and tokens per minute), so many fast runs can return a
rate-limit error. Each execution can also take up to 10 s before it times out.

**Other limitations.**
- Generated code can only use libraries that are already installed. The agent does not
  install packages, on purpose.
- Programs that need user input (`input()`) or a GUI won't work. `input()` gets EOF straight
  away.
- Output comparison is exact apart from trailing whitespace, so "61" and "61 days" count
  as different.
