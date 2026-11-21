# Example briefs

These are **fixtures for testing and learning** — not the product.
BrandStorm AI itself is generic: it runs whatever brief you give it, for
any industry, any place, any Nice Class.

## bynd-streetwear.json

The first validation run of the concept (2026-11-11): a streetwear and
lifestyle apparel brief, batch of 100, Nice Class 025. Result: **44
clean / 56 partial / 0 conflict** — and the run caught a live Class 025
mark (serial 97042722) behind 48 of the candidates, which is exactly
what the pipeline is for. The full output of that run is preserved at
`../data/examples/bynd-run-2026-11-11.json`.

Keep this brief as a **regression fixture**: re-run it after pipeline
changes and compare counts. Live data moves, so small shifts are
expected; a big shift means something in the pipeline changed.

Nothing in this folder is a default. The default brief is
`../sample-arizona-coffee.json` — a clearly labeled sample. Your own
briefs go in `briefs/` (see `../README.md` for the schema).
