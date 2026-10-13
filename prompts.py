"""
prompts.py - All the text we send to the LLM lives here, so it is easy to read and tweak.

There are two situations:
    1. GENERATE: first attempt - "here is a task, write code for it".
    2. REPAIR:   later attempts - "here is the task, your previous code, and the
                 exact error it produced; please fix it".
"""

# The system prompt sets the LLM's "role" and the rules it must always follow.
SYSTEM_PROMPT = """You are an expert Python programmer.
You write complete, runnable Python 3 scripts.

Rules:
- Reply with ONE Python code block wrapped in ```python fences. No explanation outside it.
- The script must run on its own with `python script.py`: no input() calls, no command-line arguments.
- Print the final result to standard output.
- Print ONLY what the task asks for: no extra labels, headings or debug prints.
"""


def build_generate_prompt(task):
    """Prompt for the FIRST attempt: just the task."""
    return f"""Write a Python script for this task:

{task}
"""


def build_repair_prompt(task, previous_code, error, attempt_number):
    """
    Prompt for a REPAIR attempt.
    It contains the three things the LLM needs to fix the program:
        1. the original task (so it doesn't forget the goal),
        2. the code it wrote last time,
        3. the full error / traceback / wrong-output report.
    """
    return f"""The previous Python script did not work. This is repair attempt #{attempt_number}.

=== ORIGINAL TASK ===
{task}

=== PREVIOUS CODE ===
```python
{previous_code}
```

=== WHAT WENT WRONG (full error) ===
{error}

=== INSTRUCTIONS ===
1. Find the root cause of the error above.
2. Return the COMPLETE corrected script (not just the changed lines).
3. If the error is ModuleNotFoundError, that library is NOT installed and CANNOT be installed.
   Rewrite the code using only the Python standard library.
4. If the output was wrong, fix the LOGIC. Do NOT hard-code the expected output.
"""
