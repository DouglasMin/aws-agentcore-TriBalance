# Activity Analysis Code Synthesis

You are generating Python code that will run inside a sandboxed Code Interpreter.
The sandbox has `pandas`, `numpy`, `matplotlib` preinstalled, and the working dir
contains a file `activity.csv` with columns: `date` (ISO), `steps`, `active_kcal`, `exercise_min`.

## Produce code that

1. Loads `activity.csv` into a DataFrame; parses `date` as datetime.
2. Prints a JSON line to stdout with keys:
   - `avg_steps` (int)
   - `avg_active_kcal` (int)
   - `avg_exercise_min` (int)
   - `trend` (one of "up", "down", "stable") — compare first-half vs second-half averages of `steps`; threshold 5%.
3. Saves a line chart of `steps` over `date` to `activity_trend.png` with matplotlib;
   labeled axes; title "Daily steps".

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
