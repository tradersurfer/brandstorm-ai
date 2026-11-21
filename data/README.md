# data/

- `results.json` — the latest run's output (what the dashboard shows).
  Currently the Arizona sample-coffee run. Overwritten on every run.
- `examples/bynd-run-2026-11-11.json` — the preserved output of the
  first validation run (streetwear brief, 100 names, Class 025:
  44 clean / 56 partial / 0 conflict). Kept as a regression record;
  never overwritten by new runs.

## Where the private name-check files went

Three personal name-check files used to live here
(`safepark-class-009.json`, `safepark-class-042.json`,
`safepark-variants-class-009.json`). They were private research data,
not part of the product, so they were moved out of this repo to the
project's private notes folder:

`~/workspace/goals/brandstorm-ai-name-storming-and-clearance-engine/hidden_files/`

Nothing that ships in this repo should contain anyone's private
business data. If you run a check for yourself, keep the output in
`results.json` (local only) or your own private folder — not in
`data/examples/`, which is for labeled public fixtures.
