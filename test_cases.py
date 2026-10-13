"""
test_cases.py - Checks the program's OUTPUT, not just whether it crashed.

A program can run without any exception and still be wrong (e.g. prints 60
instead of 61). If the user gives an "expected output", we compare it with what
the program actually printed. A mismatch is treated as a failure, so the agent
will try to repair it just like a crash.

This file also holds the 3 demo tasks used in the live demo.
"""


def normalize(text):
    """
    Make the comparison forgiving about invisible differences:
    - ignore spaces at the end of each line,
    - ignore blank lines at the very start/end,
    - treat Windows (\\r\\n) and Linux (\\n) line endings the same.
    """
    lines = text.strip().splitlines()
    return "\n".join(line.rstrip() for line in lines)


def check_output(actual_output, expected_output):
    """
    Returns (passed, message).
        passed  -> True if the output is correct (or no expected output was given)
        message -> a description of the mismatch, sent to the LLM for repair
    """
    # No expected output given -> we can only check for crashes, so it passes.
    if expected_output is None or expected_output.strip() == "":
        return True, ""

    actual = normalize(actual_output)
    expected = normalize(expected_output)

    if actual == expected:
        return True, ""

    # Find the first line that differs, to give the LLM a precise hint.
    actual_lines = actual.splitlines()
    expected_lines = expected.splitlines()
    first_difference = ""
    for i in range(max(len(actual_lines), len(expected_lines))):
        got = actual_lines[i] if i < len(actual_lines) else "<missing line>"
        want = expected_lines[i] if i < len(expected_lines) else "<no line expected>"
        if got != want:
            first_difference = f"First difference on line {i + 1}: expected {want!r} but got {got!r}"
            break

    message = (
        "WrongOutputError: the program ran without crashing, but its output is wrong.\n"
        f"{first_difference}\n\n"
        f"--- Expected output ---\n{expected}\n\n"
        f"--- Actual output ---\n{actual if actual else '<nothing was printed>'}"
    )
    return False, message


# ---------------------------------------------------------------------------
# Demo tasks: chosen because LLMs OFTEN get them wrong on the first try.
# (LLMs are random, so there is no 100% guarantee it fails the first time.)
# ---------------------------------------------------------------------------
DEMO_TASKS = [
    {
        # Trap: the `humanize` library is not installed -> ModuleNotFoundError.
        # The agent must heal by rewriting the logic with the standard library.
        "name": "1. Missing library (humanize)",
        "task": (
            "Use the `humanize` library's intword() function to print these numbers "
            "in human-friendly form, one per line: 1234567, 5000000000, 999.\n"
            "The output should look like '1.2 million', '5.0 billion', '999'."
        ),
        "expected": "1.2 million\n5.0 billion\n999",
    },
    {
        # Trap: off-by-one. "Including both dates" means end - start + 1,
        # and 2024 is a leap year (February has 29 days).
        "name": "2. Off-by-one (inclusive date range)",
        "task": (
            "Count the days from 2024-01-01 to 2024-03-01, INCLUDING both the start "
            "and the end date. On the first line print the total number of days. "
            "On the second line print how many of those days are weekdays (Monday to Friday)."
        ),
        "expected": "61\n45",
    },
    {
        # Traps: "5th"/"1st" ordinals, "Sept" (strptime only knows "Sep"),
        # day-first format, and the trailing "Z" timezone marker.
        "name": "3. Tricky date strings",
        "task": (
            "Using ONLY the Python standard library (no dateutil), convert each of these "
            "date strings to the format YYYY-MM-DD and print one per line, in the same order:\n"
            "'03/04/2024' (this one is DAY/MONTH/YEAR)\n"
            "'March 5th, 2024'\n"
            "'2024-02-29T23:59:59Z'\n"
            "'1st of Jan 2023'\n"
            "'Sept 9 2023'"
        ),
        "expected": "2024-04-03\n2024-03-05\n2024-02-29\n2023-01-01\n2023-09-09",
    },
    # -----------------------------------------------------------------------
    # Hard-coded BUGGY samples: attempt 1 runs this broken code as-is
    # (no LLM), so it ALWAYS fails, and the demo always shows healing.
    # -----------------------------------------------------------------------
    {
        # Bug: forgot "import math" -> NameError.
        # Second bug: range(1, 31) stops at 30, so 31 is missing (off-by-one).
        "name": "4. [Buggy code] Missing import + off-by-one (primes)",
        "task": "Print a Python list of all prime numbers from 1 up to and INCLUDING 31.",
        "expected": "[2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31]",
        "buggy_code": (
            "def is_prime(n):\n"
            "    if n < 2:\n"
            "        return False\n"
            "    for i in range(2, int(math.sqrt(n)) + 1):\n"
            "        if n % i == 0:\n"
            "            return False\n"
            "    return True\n"
            "\n"
            "primes = [n for n in range(1, 31) if is_prime(n)]\n"
            "print(primes)\n"
        ),
    },
    {
        # Bug: (end - start).days does NOT include the end date -> prints 60 and 44.
        # No crash at all: only the expected-output check catches it.
        "name": "5. [Buggy code] Off-by-one (wrong output, no crash)",
        "task": (
            "Count the days from 2024-01-01 to 2024-03-01, INCLUDING both the start "
            "and the end date. On the first line print the total number of days. "
            "On the second line print how many of those days are weekdays (Monday to Friday)."
        ),
        "expected": "61\n45",
        "buggy_code": (
            "from datetime import date, timedelta\n"
            "\n"
            "start = date(2024, 1, 1)\n"
            "end = date(2024, 3, 1)\n"
            "\n"
            "days = [start + timedelta(days=i) for i in range((end - start).days)]\n"
            "print(len(days))\n"
            "print(sum(1 for d in days if d.weekday() < 5))\n"
        ),
    },
    {
        # Bug: strptime() can't handle "5th", "Sept" or "1st of" -> ValueError.
        "name": "6. [Buggy code] Tricky date parsing (ValueError)",
        "task": (
            "Using ONLY the Python standard library, convert each of these date strings "
            "to YYYY-MM-DD and print one per line, in order: "
            "'March 5th, 2024', 'Sept 9 2023', '1st of Jan 2023'."
        ),
        "expected": "2024-03-05\n2023-09-09\n2023-01-01",
        "buggy_code": (
            "from datetime import datetime\n"
            "\n"
            "dates = ['March 5th, 2024', 'Sept 9 2023', '1st of Jan 2023']\n"
            "for d in dates:\n"
            "    print(datetime.strptime(d, '%B %d, %Y').strftime('%Y-%m-%d'))\n"
        ),
    },
    {
        # Bug: forgot "i += 1" inside the while loop -> infinite loop -> timeout.
        # (This one takes 10 seconds to fail, because of the timeout.)
        "name": "7. [Buggy code] Infinite loop (timeout)",
        "task": "Print the average of the numbers 4, 8, 15, 16, 23, 42.",
        "expected": "18.0",
        "buggy_code": (
            "numbers = [4, 8, 15, 16, 23, 42]\n"
            "total = 0\n"
            "i = 0\n"
            "while i < len(numbers):\n"
            "    total += numbers[i]\n"
            "print(total / len(numbers))\n"
        ),
    },
]
