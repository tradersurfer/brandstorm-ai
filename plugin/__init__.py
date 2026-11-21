"""BrandStorm AI — Hermes plugin registration (v0.3.0).

Registers 4 tools. Thin wiring only: the tools in plugin/tools.py
delegate to the existing brandstorm package at the repo root, so the
plugin directory ships no pipeline logic of its own.

Import note: the brandstorm package sits at the repo root, next to
this ``plugin/`` package (same layout scripts/run_brief.py uses), so
the repo root is added to sys.path here before importing tools.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from . import schemas, tools  # noqa: E402


def _brandstorm_command(raw_args):
    return (
        "BrandStorm AI: use brandstorm_brief to build a brief "
        "(industry, region, states, Nice Class), then brandstorm_run to "
        "generate and clear names, brandstorm_results to read the "
        "shortlist, and brandstorm_state_links for the manual state "
        "registry checks. "
        f"Input was: {raw_args}"
    )


def register(ctx):
    ctx.register_tool(
        name="brandstorm_brief", toolset="brandstorm",
        schema=schemas.BRANDSTORM_BRIEF, handler=tools.brandstorm_brief,
    )
    ctx.register_tool(
        name="brandstorm_run", toolset="brandstorm",
        schema=schemas.BRANDSTORM_RUN, handler=tools.brandstorm_run,
    )
    ctx.register_tool(
        name="brandstorm_results", toolset="brandstorm",
        schema=schemas.BRANDSTORM_RESULTS, handler=tools.brandstorm_results,
    )
    ctx.register_tool(
        name="brandstorm_state_links", toolset="brandstorm",
        schema=schemas.BRANDSTORM_STATE_LINKS, handler=tools.brandstorm_state_links,
    )
    ctx.register_command("brandstorm", _brandstorm_command,
                         description="BrandStorm AI naming brief help")
