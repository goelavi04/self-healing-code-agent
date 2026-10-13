"""
executor.py - Runs a piece of Python code in a SEPARATE process and reports what happened.

Why a separate process?
    If we used exec() inside our own program, a crash or infinite loop in the
    generated code would crash or freeze the agent itself. Running it with
    `subprocess` keeps the agent safe: we just start a new Python interpreter,
    wait for it (up to a time limit), and read what it printed.

Note: this is NOT a real security sandbox. See "Limitations & Safety" in README.md.
"""

import os
import subprocess
import sys
import tempfile
import time

# Maximum number of seconds the generated program is allowed to run.
TIMEOUT_SECONDS = 10


def run_code(code, timeout=TIMEOUT_SECONDS):
    """
    Save `code` to a temporary .py file, run it with Python, and return a dict:

        {
            "stdout":     text the program printed normally,
            "stderr":     error text (e.g. the traceback),
            "returncode": 0 means success, anything else means it crashed,
            "timed_out":  True if we had to stop it after `timeout` seconds,
            "timeout":    the time limit that was used,
            "run_time_s": how long it ran, in seconds,
        }
    """
    # A temporary folder that is deleted automatically when the "with" block ends.
    # We also run the program inside it, so any files it creates get cleaned up too.
    with tempfile.TemporaryDirectory() as folder:
        script_path = os.path.join(folder, "generated_code.py")

        # Write the generated code into the file.
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)

        # Force the child program to print using UTF-8 (avoids encoding errors on Windows).
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        start = time.time()
        try:
            completed = subprocess.run(
                [sys.executable, script_path],  # sys.executable = the same Python that runs this agent
                cwd=folder,                      # run inside the temp folder
                capture_output=True,             # collect stdout and stderr instead of showing them
                text=True,                       # give us str, not bytes
                encoding="utf-8",
                errors="replace",                # never crash on strange characters
                stdin=subprocess.DEVNULL,        # if the code calls input(), it gets EOF instead of hanging
                timeout=timeout,                 # kill the program if it runs too long
                env=env,
            )
            return {
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "returncode": completed.returncode,
                "timed_out": False,
                "timeout": timeout,
                "run_time_s": round(time.time() - start, 2),
            }
        except subprocess.TimeoutExpired:
            # subprocess.run() has already killed the program for us at this point.
            return {
                "stdout": "",
                "stderr": f"Program was stopped after {timeout} seconds.",
                "returncode": None,
                "timed_out": True,
                "timeout": timeout,
                "run_time_s": round(time.time() - start, 2),
            }


# Tiny self-test: run `python executor.py` to see the executor working on its own.
if __name__ == "__main__":
    print(run_code("print('hello from the child process')"))
    print(run_code("print(1 / 0)"))
    print(run_code("while True: pass", timeout=2))
