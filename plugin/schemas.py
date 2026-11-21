"""BrandStorm AI — Hermes plugin tool schemas (what the LLM sees).

Thin wrappers over the existing brandstorm package: no pipeline logic
is duplicated here. See plugin/tools.py.
"""

BRANDSTORM_BRIEF = {
    "name": "brandstorm_brief",
    "description": (
        "Validate and build a naming brief from the user's input: industry, "
        "geographic scope, states for Tier 3 checks, brand aesthetic, Nice "
        "Class, anchor words, batch size, and TLDs. No network, no keys, "
        "no files written. Use this first, before brandstorm_run."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "industry": {"type": "string", "description": "The industry, e.g. Specialty Tea House. Required."},
            "geographic_scope": {"type": "string", "description": "Where the brand operates, e.g. Portland, Oregon / US National."},
            "states": {
                "type": "array",
                "items": {"type": "string"},
                "description": "US state/DC codes for Tier 3 state-registry checks, e.g. [\"OR\"]. Unknown codes are dropped and reported, never silently kept.",
            },
            "brand_aesthetic": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Any of: Trendy, Minimalist, High-End, Urban Utility, Rustic, Artisan, Modern, Playful.",
            },
            "nice_class": {"type": "string", "description": "Trademark Nice Class as a string, e.g. \"030\". Defaults to \"025\"."},
            "candidate_batch_size": {"type": "integer", "description": "How many names to generate (1-100). Defaults to 50."},
            "tlds": {
                "type": "array",
                "items": {"type": "string"},
                "description": "TLDs Tier 1 checks, e.g. [\"com\", \"co\"]. Defaults to com, co, studio, supply, app.",
            },
            "must_include_exact_variations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Anchor words/phrases every generated name must contain one token of, e.g. [\"Cascade Leaf\"].",
            },
        },
        "required": ["industry"],
    },
}

BRANDSTORM_RUN = {
    "name": "brandstorm_run",
    "description": (
        "Generate candidate names from a brief and clear them through the "
        "4-tier pipeline (domain, USPTO trademark, state registries, "
        "social handles). Returns the summary counts, the shortlist, and "
        "per-name per-tier evidence. Live network checks run keyless by "
        "default; no key is required. Takes minutes for a full batch."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "brief": {
                "type": "object",
                "description": "A brief dict as built by brandstorm_brief (industry, geographic_scope, states, nice_class, ...).",
            },
            "industry": {"type": "string", "description": "Industry, if no brief dict is given. Required when brief is absent."},
            "geographic_scope": {"type": "string", "description": "Where the brand operates."},
            "states": {
                "type": "array",
                "items": {"type": "string"},
                "description": "US state/DC codes for Tier 3 checks.",
            },
            "brand_aesthetic": {"type": "array", "items": {"type": "string"}},
            "nice_class": {"type": "string", "description": "Trademark Nice Class, e.g. \"030\"."},
            "candidate_batch_size": {"type": "integer", "description": "How many names to generate (1-100)."},
            "tlds": {"type": "array", "items": {"type": "string"}},
            "must_include_exact_variations": {"type": "array", "items": {"type": "string"}},
            "write_results": {"type": "boolean", "description": "Write the run payload to data/results.json for the dashboard. Defaults to true."},
        },
        "required": [],
    },
}

BRANDSTORM_RESULTS = {
    "name": "brandstorm_results",
    "description": (
        "Read the latest run from data/results.json: summary counts, the "
        "clean shortlist, and per-name per-tier evidence (domain TLDs, "
        "USPTO matches, state status, social handles). No network. "
        "Unknown tiers are reported as unknown with the reason, never as clear."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "badge": {
                "type": "string",
                "description": "Filter to one badge: clean, partial, or conflict. Empty returns all results.",
            },
            "limit": {"type": "integer", "description": "Max results to return. Defaults to 50."},
        },
        "required": [],
    },
}

BRANDSTORM_STATE_LINKS = {
    "name": "brandstorm_state_links",
    "description": (
        "Return the Secretary of State manual-check links for the states "
        "the brief asks for. Tier 3 portals are form/session-gated, so "
        "these are links for a human to check, not automated results — "
        "never reported as clear or taken. No states requested returns "
        "not_requested with guidance."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "states": {
                "type": "array",
                "items": {"type": "string"},
                "description": "US state/DC codes, e.g. [\"OR\", \"WA\"].",
            },
            "geographic_scope": {"type": "string", "description": "Region text to resolve states from when no explicit states are given, e.g. Pacific Northwest."},
        },
        "required": [],
    },
}
