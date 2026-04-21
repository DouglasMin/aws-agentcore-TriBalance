# Sleep Analysis Code Synthesis

You are generating Python code that will run inside a sandboxed Code Interpreter.
The sandbox has `pandas`, `numpy`, `matplotlib` preinstalled, and the working dir
contains a file `sleep.csv` with columns: `date` (ISO), `in_bed_min`, `asleep_min`.

## Produce code that

1. Loads `sleep.csv` into a DataFrame and parses `date` as datetime.
2. Computes `efficiency = asleep_min / in_bed_min` per row.
3. Prints a JSON line to stdout with keys:
   - `avg_duration_hr` (float, rounded to 2 decimals)
   - `avg_efficiency` (float, 0-1, rounded to 2 decimals)
   - `trend` (one of "up", "down", "stable") — compare first-half vs second-half averages of `asleep_min`; threshold 5%.
4. Saves a line chart of `asleep_min / 60` over `date` to `sleep_trend.png`
   with matplotlib; labeled axes; title "Sleep duration (hours)".

## Code constraints (IMPORTANT — your code will be wrapped in a function)

- Write **top-level statements only** — import, assignments, function calls, loops.
- **Do NOT** use `if __name__ == "__main__":`. Do not define module-level guards.
- Do not rely on variables or imports from prior executions. Import everything
  you need inside THIS code block (e.g. `import pandas as pd`).
- Do not use `return` at the top level.

## Output format

Return ONLY a single Python code block. No prose outside the block.
The JSON line MUST be exactly: `METRICS_JSON: {...}` on its own line.

## Feedback loop

If a previous attempt failed, the error is:

{error_feedback}

Fix the code so it runs cleanly.
