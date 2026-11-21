"""Deterministic combinatorial name generator (v0.2).

No LLM is wired — names are built from curated word banks by aesthetic
+ anchor compounding + variation rules, with a seed taken from the brief
so a run is reproducible. An LLM generator can replace ``generate``
later behind the same signature.

Anchors come ONLY from the brief's ``direct_anchor_rules``
``must_include_exact_variations`` — nothing is hardcoded here. A
variation like "Desert Roast" yields:
- anchor tokens: desert, roast
- lead: Desert
- other lead: Roast
A 3+ word variation also yields an acronym lead from its words'
initials (e.g. "Desert Roast Coffee" -> DRC), which is itself an
anchor token. "/" in a variation is treated as a space.

Rules enforced:
- Every name is a compound (2+ tokens) — no single-word names, so no
  single-word collisions.
- Every name contains at least one anchor token from the brief (when
  the brief defines variations at all).
- Names are unique case-insensitively within a batch.
"""

from __future__ import annotations

import hashlib
import random
import re

from . import words

_STOPWORDS = {"the", "a", "an", "and", "of", "&"}


def _clean_variation(var: str) -> str:
    """'Desert/Roast' -> 'Desert Roast'; collapse whitespace."""
    return re.sub(r"\s+", " ", var.replace("/", " ")).strip()


def anchor_variations(brief: dict) -> list[str]:
    """The brief's must-include variations, cleaned, order preserved."""
    rules = brief.get("direct_anchor_rules", {}) or {}
    out: list[str] = []
    for var in rules.get("must_include_exact_variations", []) or []:
        cleaned = _clean_variation(str(var))
        if cleaned and cleaned not in out:
            out.append(cleaned)
    return out


def _content_words(variation: str) -> list[str]:
    return [t for t in re.split(r"[^A-Za-z0-9]+", variation) if t and t.lower() not in _STOPWORDS]


def _acronym(variation: str) -> str | None:
    """Initials of a 3+ word variation, e.g. 'Desert Roast Coffee' -> 'DRC'.

    All words count, including short ones ('the' gives the middle
    letter, as in a variation like 'Roast of the Desert' -> ROTD) —
    that is how acronyms are conventionally formed.
    """
    words = [w for w in re.split(r"[^A-Za-z0-9]+", variation) if w]
    if len(words) >= 3:
        return "".join(w[0].upper() for w in words)
    return None


def anchor_tokens(brief: dict) -> set[str]:
    """Lowercase tokens a generated name must contain one of."""
    tokens: set[str] = set()
    for var in anchor_variations(brief):
        for w in _content_words(var):
            tokens.add(w.lower())
        acr = _acronym(var)
        if acr:
            tokens.add(acr.lower())
    return tokens


def anchor_leads(brief: dict) -> list[str]:
    """Lead tokens for compounding: first word of each variation + acronyms."""
    leads: list[str] = []
    for var in anchor_variations(brief):
        first = _content_words(var)
        if first and first[0] not in leads:
            leads.append(first[0])
        acr = _acronym(var)
        if acr and acr not in leads:
            leads.append(acr)
    return leads


def anchor_other_leads(brief: dict) -> list[str]:
    """Non-first content words of the variations, usable as leads."""
    leads: list[str] = []
    for var in anchor_variations(brief):
        for w in _content_words(var)[1:]:
            if w not in leads:
                leads.append(w)
    return leads


def _seed_from_brief(brief: dict) -> int:
    digest = hashlib.sha256(repr(sorted(brief.items())).encode()).hexdigest()
    return int(digest[:8], 16)


def _pool_roots(brief: dict) -> list[str]:
    aesthetics = brief.get("brand_aesthetic", []) or list(words.ROOTS_BY_AESTHETIC)
    pool: list[str] = []
    for aesthetic in aesthetics:
        pool.extend(words.ROOTS_BY_AESTHETIC.get(aesthetic, []))
    # De-duplicate while preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for root in pool:
        if root.lower() not in seen:
            seen.add(root.lower())
            out.append(root)
    return out


def _tokens(name: str) -> set[str]:
    return {t.lower() for t in re.split(r"[\s/]+", name) if t}


def _is_compound(name: str) -> bool:
    return len([t for t in re.split(r"[\s/]+", name) if t]) >= 2


def generate(brief: dict, count: int | None = None, seed: int | None = None) -> list[str]:
    """Generate ``count`` unique compound names for the brief."""
    count = count or int(brief.get("candidate_batch_size", 100))
    seed = seed if seed is not None else _seed_from_brief(brief)
    rng = random.Random(seed)
    roots = _pool_roots(brief)
    suffixes = words.SUFFIXES
    variations = anchor_variations(brief)
    leads = anchor_leads(brief)
    other_leads = anchor_other_leads(brief)
    tokens = anchor_tokens(brief)

    seen: set[str] = set()
    names: list[str] = []

    def add(name: str) -> None:
        name = re.sub(r"\s+", " ", name).strip()
        key = name.lower()
        if key in seen:
            return
        if not _is_compound(name):
            return
        if tokens and not (_tokens(name) & tokens):
            return
        seen.add(key)
        names.append(name)

    if leads:
        # Pattern A: LEAD + ROOT
        combos_a = [(lead, root) for lead in leads for root in roots]
        rng.shuffle(combos_a)
        for lead, root in combos_a:
            add(f"{lead} {root}")
            if len(names) >= count:
                return names

        # Pattern B: LEAD + ROOT + SUFFIX
        combos_b = [(lead, root, suf) for lead in leads for root in roots for suf in suffixes]
        rng.shuffle(combos_b)
        for lead, root, suf in combos_b:
            if root.lower() == suf.lower():
                continue
            add(f"{lead} {root} {suf}")
            if len(names) >= count:
                return names

        # Pattern C: ANCHOR VARIATION + ROOT — honours the must-include
        # variations verbatim.
        combos_c = [(var, root) for var in variations for root in roots]
        rng.shuffle(combos_c)
        for var, root in combos_c:
            add(f"{var} {root}")
            if len(names) >= count:
                return names

        # Pattern D: other anchor words as lead + ROOT
        for lead in other_leads:
            for root in roots:
                add(f"{lead} {root}")
                if len(names) >= count:
                    return names
    else:
        # No anchor variations in the brief: root + root compounds.
        combos_e = [(r1, r2) for r1 in roots for r2 in roots if r1.lower() != r2.lower()]
        rng.shuffle(combos_e)
        for r1, r2 in combos_e:
            add(f"{r1} {r2}")
            if len(names) >= count:
                return names
        for root in roots:
            for suf in suffixes:
                if root.lower() == suf.lower():
                    continue
                add(f"{root} {suf}")
                if len(names) >= count:
                    return names

    return names


def compact(name: str) -> str:
    """Name squashed for domains/handles: 'Desert Ridge' -> 'desertridge'."""
    return re.sub(r"[^a-z0-9]", "", name.lower())
