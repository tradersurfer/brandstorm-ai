"""Secretary of State business-search registry map — all 50 states + DC.

Each entry: SOS portal name, business-entity search URL, and a note.
URLs are the official search page where we are confident of it; where the
exact search URL was uncertain we link the SOS business-search landing
page instead and the note says so — never a URL that only looks official.

``verified`` / ``verified_status`` / ``verified_at`` come from
``registries_verification.json`` (same folder), produced by running
``scripts/verify_registries.py`` — a status-only GET of every URL.
An entry with verified=False was not re-checked in this build; use its
URL as a starting point, not as a confirmed search page.

This table is DATA, not a check: the portals are form/session-gated, so
Tier 3 is still a manual-check tier (see clearance/state.py). What
changed in v0.2 is that the tier is now USER-DRIVEN — it returns the
portals for the states the user's brief asks for, never a hardcoded
home region.
"""

from __future__ import annotations

import json
import os

# code -> {name, portal, url, note}
REGISTRIES: dict[str, dict[str, str]] = {
    "AL": {
        "name": "Alabama",
        "portal": "Alabama Secretary of State — Business Entities",
        "url": "https://www.sos.alabama.gov/business-entities",
        "note": "Landing page — use the entity search link from the Business Entities page.",
    },
    "AK": {
        "name": "Alaska",
        "portal": "Alaska Division of Corporations, Business & Professional Licensing",
        "url": "https://www.commerce.alaska.gov/web/cbp/",
        "note": "Landing page — use the business entity search from the Corporations section.",
    },
    "AZ": {
        "name": "Arizona",
        "portal": "Arizona Corporation Commission — eCorp",
        "url": "https://ecorp.azcc.gov/",
        "note": "eCorp portal; entity search requires an interactive session.",
    },
    "AR": {
        "name": "Arkansas",
        "portal": "Arkansas Secretary of State — Corporation Search",
        "url": "https://sos-corp-search.ark.org/corps",
        "note": "Corporation search; plain GET returns 405 (form is POST-based) — host verified answering 2026-11-12.",
    },
    "CA": {
        "name": "California",
        "portal": "California Secretary of State — bizfile Online",
        "url": "https://bizfileonline.sos.ca.gov/search/business",
        "note": "Business search page.",
    },
    "CO": {
        "name": "Colorado",
        "portal": "Colorado Secretary of State — Business Search",
        "url": "https://www.sos.colorado.gov/biz/BusinessEntityCriteriaExt.do",
        "note": "Business entity search form.",
    },
    "CT": {
        "name": "Connecticut",
        "portal": "Connecticut Secretary of the State — Business Services",
        "url": "https://portal.ct.gov/sots",
        "note": "SOS home — business lookup is under Business Services (the old service.ct.gov lookup path returned 404 on 2026-11-12).",
    },
    "DE": {
        "name": "Delaware",
        "portal": "Delaware Division of Corporations — Entity Search",
        "url": "https://icis.corp.delaware.gov/ecorp/entitysearch/NameSearch.aspx",
        "note": "Entity name search form.",
    },
    "DC": {
        "name": "District of Columbia",
        "portal": "DC DLCP / BOSS CorpOnline",
        "url": "https://boss.dc.gov/",
        "note": "JS portal; entity search requires an interactive session.",
    },
    "FL": {
        "name": "Florida",
        "portal": "Florida Division of Corporations — Sunbiz",
        "url": "https://search.sunbiz.org/Inquiry/CorporationSearch/ByName",
        "note": "Search by name page.",
    },
    "GA": {
        "name": "Georgia",
        "portal": "Georgia Secretary of State — Corporations eCorp",
        "url": "https://ecorp.sos.ga.gov/BusinessSearch",
        "note": "Business search page.",
    },
    "HI": {
        "name": "Hawaii",
        "portal": "Hawaii DCCA — Business Registration Search",
        "url": "https://hbe.ehawaii.gov/documents/search.html",
        "note": "Business documents search page.",
    },
    "ID": {
        "name": "Idaho",
        "portal": "Idaho Secretary of State — SOSBiz",
        "url": "https://sosbiz.idaho.gov/search/business",
        "note": "Business search page.",
    },
    "IL": {
        "name": "Illinois",
        "portal": "Illinois Secretary of State — Corporate/LLC Search",
        "url": "https://apps.ilsos.gov/corporatellc/",
        "note": "Corporate/LLC search landing page.",
    },
    "IN": {
        "name": "Indiana",
        "portal": "Indiana Secretary of State — Business Search",
        "url": "https://bsd.sos.in.gov/publicbusinesssearch",
        "note": "Public business search page.",
    },
    "IA": {
        "name": "Iowa",
        "portal": "Iowa Secretary of State — Business Search",
        "url": "https://sos.iowa.gov/search/business",
        "note": "Business search page.",
    },
    "KS": {
        "name": "Kansas",
        "portal": "Kansas Secretary of State — Business Entity Search (BESS)",
        "url": "https://www.kansas.gov/bess/",
        "note": "Business entity search portal.",
    },
    "KY": {
        "name": "Kentucky",
        "portal": "Kentucky Secretary of State — Business Services",
        "url": "https://www.sos.ky.gov/",
        "note": "SOS home — business search is under Business Services (the ftsearch path returned 404 on 2026-11-12).",
    },
    "LA": {
        "name": "Louisiana",
        "portal": "Louisiana Secretary of State — Commercial Search (CORA)",
        "url": "https://coraweb.sos.la.gov/commercialsearch/commercialsearch.aspx",
        "note": "Commercial search form.",
    },
    "ME": {
        "name": "Maine",
        "portal": "Maine Secretary of State — Corporate Name Search",
        "url": "https://icrs.informe.org/nei-sos-icrs/ICRS?MainPage=x",
        "note": "Corporate search portal (informe).",
    },
    "MD": {
        "name": "Maryland",
        "portal": "Maryland SDAT Business Express",
        "url": "https://egov.maryland.gov/BusinessExpress/EntitySearch",
        "note": "ASP.NET form (VIEWSTATE POST); no public GET search.",
    },
    "MA": {
        "name": "Massachusetts",
        "portal": "Massachusetts Secretary of the Commonwealth — Corporate Search",
        "url": "https://corp.sec.state.ma.us/corpweb/CorpSearch/CorpSearch.aspx",
        "note": "Corporation search form.",
    },
    "MI": {
        "name": "Michigan",
        "portal": "Michigan LARA — Corporations Search",
        "url": "https://cofs.lara.state.mi.us/SearchApi/Search/Search",
        "note": "Business entity search page.",
    },
    "MN": {
        "name": "Minnesota",
        "portal": "Minnesota Secretary of State — Business Search",
        "url": "https://mblsportal.sos.state.mn.us/Business/Search",
        "note": "Business search page.",
    },
    "MS": {
        "name": "Mississippi",
        "portal": "Mississippi Secretary of State — Business Search",
        "url": "https://corp.sos.ms.gov/corp/portal/c/page/corpBusinessIdSearch",
        "note": "Business search page.",
    },
    "MO": {
        "name": "Missouri",
        "portal": "Missouri Secretary of State — Business Entity Search",
        "url": "https://bsd.sos.mo.gov/BusinessEntity/BESearch.aspx?SearchType=0",
        "note": "Business entity search form.",
    },
    "MT": {
        "name": "Montana",
        "portal": "Montana Secretary of State — Business Search",
        "url": "https://biz.sosmt.gov/search",
        "note": "Business search page.",
    },
    "NE": {
        "name": "Nebraska",
        "portal": "Nebraska Secretary of State — Corporate Search",
        "url": "https://www.nebraska.gov/sos/corp/corpsearch.cgi",
        "note": "Corporate search form.",
    },
    "NV": {
        "name": "Nevada",
        "portal": "Nevada Secretary of State — Business Entity Search",
        "url": "https://esos.nv.gov/EntitySearch/OnlineEntitySearch",
        "note": "Online entity search page.",
    },
    "NH": {
        "name": "New Hampshire",
        "portal": "New Hampshire Secretary of State — Business Inquiry",
        "url": "https://quickstart.sos.nh.gov/online/BusinessInquiry",
        "note": "Business inquiry page.",
    },
    "NJ": {
        "name": "New Jersey",
        "portal": "New Jersey Division of Revenue — Business Name Search",
        "url": "https://www.njportal.com/DOR/BusinessNameSearch/Search/BusinessName",
        "note": "Business name search page.",
    },
    "NM": {
        "name": "New Mexico",
        "portal": "New Mexico Secretary of State — Business Filing Search",
        "url": "https://portal.sos.nm.gov/BFS/online",
        "note": "Business filing search portal.",
    },
    "NY": {
        "name": "New York",
        "portal": "New York Department of State — Entity Search",
        "url": "https://apps.dos.ny.gov/publicInquiry/EntitySearch",
        "note": "Entity search page.",
    },
    "NC": {
        "name": "North Carolina",
        "portal": "North Carolina Secretary of State — Business Services",
        "url": "https://www.sosnc.gov/",
        "note": "SOS home — business search is under Business Services (the /search/profession/business path returned 404 on 2026-11-12).",
    },
    "ND": {
        "name": "North Dakota",
        "portal": "North Dakota Secretary of State — FirstStop Business Search",
        "url": "https://firststop.sos.nd.gov/",
        "note": "FirstStop portal; business search from the home page.",
    },
    "OH": {
        "name": "Ohio",
        "portal": "Ohio Secretary of State — Business Search",
        "url": "https://businesssearch.ohiosos.gov/",
        "note": "Business search portal.",
    },
    "OK": {
        "name": "Oklahoma",
        "portal": "Oklahoma Secretary of State — Corporation Search",
        "url": "https://www.sos.ok.gov/corp/corpInformation.aspx",
        "note": "Corporation information search page.",
    },
    "OR": {
        "name": "Oregon",
        "portal": "Oregon Secretary of State — Business Name Search",
        "url": "https://egov.sos.state.or.us/br/pkg_web_name_srch_inq.login",
        "note": "Business name search login page.",
    },
    "PA": {
        "name": "Pennsylvania",
        "portal": "Pennsylvania Department of State — Business Search",
        "url": "https://file.dos.pa.gov/search/business",
        "note": "Business search page.",
    },
    "RI": {
        "name": "Rhode Island",
        "portal": "Rhode Island Secretary of State — Business Services",
        "url": "https://www.sos.ri.gov/",
        "note": "SOS home — corporate search is under Business Services (the business.sos.ri.gov path returned 404 on 2026-11-12).",
    },
    "SC": {
        "name": "South Carolina",
        "portal": "South Carolina Secretary of State — Business Filings Search",
        "url": "https://businessfilings.sc.gov/BusinessFiling/Entity/Search",
        "note": "Entity search page.",
    },
    "SD": {
        "name": "South Dakota",
        "portal": "South Dakota Secretary of State — Business Services",
        "url": "https://sdsos.gov/",
        "note": "SOS home — business name search is under Business Services (the sosenterprise path returned 404 on 2026-11-12).",
    },
    "TN": {
        "name": "Tennessee",
        "portal": "Tennessee Secretary of State — Business Search (TNBear)",
        "url": "https://tnbear.tn.gov/ECommerce/FilingSearch.aspx",
        "note": "Filing search page.",
    },
    "TX": {
        "name": "Texas",
        "portal": "Texas Secretary of State — SOSDirect Entity Search",
        "url": "https://www.sos.state.tx.us/corp/sosda/index.shtml",
        "note": "SOSDirect landing page; entity search from inside the portal.",
    },
    "UT": {
        "name": "Utah",
        "portal": "Utah Division of Corporations — Business Entity Search",
        "url": "https://secure.utah.gov/bes/",
        "note": "Business entity search portal.",
    },
    "VT": {
        "name": "Vermont",
        "portal": "Vermont Secretary of State — Business Search",
        "url": "https://www.sec.state.vt.us/corporationsbusiness-services/search",
        "note": "Business search page.",
    },
    "VA": {
        "name": "Virginia",
        "portal": "Virginia SCC CIS",
        "url": "https://cis.scc.virginia.gov/",
        "note": "Cookie-consent / session gate; no public GET search.",
    },
    "WA": {
        "name": "Washington",
        "portal": "Washington Secretary of State — Corporations Search",
        "url": "https://ccfs.sos.wa.gov/",
        "note": "Corporations search portal.",
    },
    "WV": {
        "name": "West Virginia",
        "portal": "West Virginia Secretary of State — Business Search",
        "url": "https://apps.sos.wv.gov/business/corporations/",
        "note": "Business/corporations search landing page.",
    },
    "WI": {
        "name": "Wisconsin",
        "portal": "Wisconsin DFI — Corporate Search",
        "url": "https://www.wdfi.org/apps/CorpSearch/Search.aspx",
        "note": "Corporate search form.",
    },
    "WY": {
        "name": "Wyoming",
        "portal": "Wyoming Secretary of State — Business Filing Search",
        "url": "https://wyobiz.wyo.gov/Business/FilingSearch.aspx",
        "note": "Business filing search page.",
    },
}


def _load_verification() -> dict:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "registries_verification.json")
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def get_registry(code: str) -> dict | None:
    """One registry entry, with verification info attached when available."""
    code = (code or "").strip().upper()
    entry = REGISTRIES.get(code)
    if not entry:
        return None
    out = dict(entry)
    out["code"] = code
    ver = _load_verification().get(code, {})
    out["verified"] = bool(ver.get("verified"))
    out["verified_status"] = ver.get("http_status")
    out["verified_at"] = ver.get("checked_at")
    out["verified_final_url"] = ver.get("final_url")
    return out


def all_codes() -> list[str]:
    return sorted(REGISTRIES)
