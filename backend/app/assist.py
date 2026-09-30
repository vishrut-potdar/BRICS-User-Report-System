"""Generative AI assist features, grounded in the platform's own data.

- understand: reads a citizen's draft complaint before it is filed (language, sector, urgency, translation, places)
- cluster brief: a short briefing on one problem cluster for an official
- area brief: the state of a whole area (top priorities, silent units, suspicious campaigns)

Gemini writes the text when configured. Otherwise a deterministic template does, and the response says so
(`ai: false`). The model only sees redacted English summaries and score inputs, never phone numbers or original
text, and it is told not to rank, re-rank or invent facts: the score stays the deterministic formula.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from .language import ExtractionError, LanguageProvider
from .language.gemini import LANGUAGE_NAMES
from .taxonomy import SECTOR_DESCRIPTIONS

log = logging.getLogger(__name__)

SECTOR_LABEL = {"water": "drinking water", "sanitation": "sanitation", "roads": "roads", "health": "health services",
                "education": "schools", "electricity": "electricity", "waste": "waste collection", "other": "other civic"}
DEPARTMENT = {"water": "water supply department", "sanitation": "sanitation wing of the local body",
              "roads": "public works department", "health": "district health office", "education": "education department",
              "electricity": "electricity distribution company", "waste": "municipal solid-waste team",
              "other": "district collector's office"}
ALIGNMENT = {"none": "No funded or planned project covers this yet.", "delayed": "A planned project here is delayed.",
             "funded": "A funded project already covers this; check its progress before new spending."}
RULES = """Rules:
- Use only the facts given below. Do not invent numbers, names, places or dates.
- Do not rank, re-rank or score. The priority score is a fixed public formula; you may quote it, not change it.
- No personal names, phone numbers or addresses.
- Plain text, no markdown headings, no bullet symbols other than "- ".
- Write in {language}."""


def _is_ai(provider: LanguageProvider) -> bool:
    return getattr(provider, "name", "") == "gemini" and hasattr(provider, "write")


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code, code)


# --- citizen: understand a draft ---------------------------------------------------------------

def understand(provider: LanguageProvider, text: str) -> dict[str, Any]:
    extraction = provider.extract(text=text)
    return {
        "ai": _is_ai(provider),
        "provider": provider.name,
        "lang": extraction.lang,
        "lang_name": language_name(extraction.lang),
        "category": extraction.category,
        "urgency": extraction.urgency,
        "text_en": extraction.text_en if not extraction.text_en.startswith("[untranslated") else None,
        "summary": extraction.summary_redacted,
        "places": extraction.location_mentions,
        "district_guess": extraction.district_guess,
    }


# --- official: cluster brief -------------------------------------------------------------------

def _dates(requests: list[dict[str, Any]]) -> tuple[str, str] | None:
    stamps = sorted(r["created_at"] for r in requests if r.get("created_at"))
    if not stamps:
        return None
    fmt = lambda s: datetime.fromisoformat(s).strftime("%d %b %Y")  # noqa: E731
    return fmt(stamps[0]), fmt(stamps[-1])


def cluster_facts(view: dict[str, Any], area: str) -> str:
    requests = view.get("requests", [])
    summaries = list(dict.fromkeys(r["summary"] for r in requests if r.get("summary")))[:12]
    span = _dates(requests)
    lines = [
        f"Area: {view['district']} ({area})",
        f"Sector: {view['sector']} ({SECTOR_DESCRIPTIONS.get(view['sector'], '')})",
        f"People reporting: {view['n_requesters']}; messages: {view['n_messages']}; marked urgent: {view['n_urgent']}",
        f"Reporting period: {span[0]} to {span[1]}" if span else "",
        f"Priority score: {view.get('score')} (rank {view.get('rank')}); components 0-1: {view.get('components', {})}",
        f"Planned projects: {ALIGNMENT.get(view.get('alignment_status', ''), 'unknown')}",
        f"Integrity multiplier: {view['integrity']['multiplier']} flags: {view['integrity']['flags'] or 'none'}",
        f"Current status: {view.get('work_status')}",
        "Redacted summaries of what residents wrote:",
        *[f"- {s}" for s in summaries],
    ]
    return "\n".join(line for line in lines if line)


def cluster_brief(provider: LanguageProvider, view: dict[str, Any], area: str, lang: str = "en") -> dict[str, Any]:
    if _is_ai(provider):
        prompt = (
            "You brief a district official about one cluster of citizen complaints on a public-works planning tool.\n"
            "Write at most 130 words in three short paragraphs: (1) what residents report, how many and since when; "
            "(2) who is affected and how urgent it is; (3) one concrete next step, naming the responsible department.\n"
            + RULES.format(language=language_name(lang)) + "\n\nFacts:\n" + cluster_facts(view, area)
        )
        try:
            return {"ai": True, "provider": provider.name, "lang": lang, "text": provider.write(prompt)}
        except ExtractionError as exc:
            log.warning("cluster brief fell back to the template: %s", exc)
    return {"ai": False, "provider": "template", "lang": "en", "text": _cluster_template(view)}


def _cluster_template(view: dict[str, Any]) -> str:
    requests = view.get("requests", [])
    span = _dates(requests)
    sample = next((r["summary"] for r in requests if r.get("summary")), "")
    urgent = round(100 * view["n_urgent"] / max(1, view["n_messages"]))
    parts = [
        f"{view['n_requesters']} people ({view['n_messages']} messages) in {view['district']} report "
        f"{SECTOR_LABEL.get(view['sector'], view['sector'])} problems" + (f" between {span[0]} and {span[1]}." if span else "."),
        f"{urgent}% of messages describe a risk to health or safety." if urgent else "No message reports an immediate risk to life.",
        f"Typical report: “{sample}”" if sample else "",
        ALIGNMENT.get(view.get("alignment_status", ""), ""),
        "Part of this demand looks coordinated and is down-weighted." if view["integrity"]["multiplier"] < 0.9 else "",
        f"Suggested next step: ask the {DEPARTMENT.get(view['sector'], 'district office')} to verify on site and report back.",
    ]
    return " ".join(p for p in parts if p)


# --- official: area brief ----------------------------------------------------------------------

def area_facts(area: str, items: list[dict[str, Any]], districts: list[dict[str, Any]], silent: list[dict[str, Any]]) -> str:
    total = sum(d["n_requests"] for d in districts)
    people = sum(d.get("n_requesters", 0) for d in districts)
    by_sector: dict[str, int] = {}
    for item in items:
        by_sector[item["sector"]] = by_sector.get(item["sector"], 0) + item["n_requesters"]
    flagged = [i for i in items if i["integrity"]["multiplier"] < 0.9]
    lines = [
        f"Area: {area}",
        f"Active requests: {total}; people reporting: {people}; ranked problem clusters: {len(items)}",
        "People reporting by sector (ranked clusters): " + ", ".join(f"{k} {v}" for k, v in sorted(by_sector.items(), key=lambda kv: -kv[1])),
        "Top 5 ranked clusters (score, place, sector, people, planned-project status, sample):",
        *[f"- {i['score']}: {i['district']}, {i['sector']}, {i['n_requesters']} people, projects {i.get('alignment_status')}, "
          f"“{(i.get('sample_summaries') or [''])[0]}”" for i in items[:5]],
        "Silent units (poor, few reports per 100k people): " + (", ".join(f"{s['district']} ({s['requests_per_100k']})" for s in silent) or "none"),
        f"Clusters down-weighted as possible coordinated campaigns: {len(flagged)}"
        + (" (" + ", ".join(f"{f['district']} {f['sector']}" for f in flagged[:3]) + ")" if flagged else ""),
    ]
    return "\n".join(lines)


def area_brief(provider: LanguageProvider, area: str, items: list[dict[str, Any]], districts: list[dict[str, Any]],
               silent: list[dict[str, Any]], lang: str = "en") -> dict[str, Any]:
    if _is_ai(provider):
        prompt = (
            "You brief a senior official on citizen demand for public works in one area, from a transparent ranking tool.\n"
            "Write at most 170 words: two sentences on the overall picture, then 3 to 5 lines starting with \"- \" on the "
            "top priorities (why each ranks high), then one line on silent areas that need outreach and one on any "
            "suspected coordinated campaigns.\n"
            + RULES.format(language=language_name(lang)) + "\n\nFacts:\n" + area_facts(area, items, districts, silent)
        )
        try:
            return {"ai": True, "provider": provider.name, "lang": lang, "text": provider.write(prompt, max_tokens=900)}
        except ExtractionError as exc:
            log.warning("area brief fell back to the template: %s", exc)
    return {"ai": False, "provider": "template", "lang": "en", "text": _area_template(area, items, districts, silent)}


def _area_template(area: str, items, districts, silent) -> str:
    total = sum(d["n_requests"] for d in districts)
    lines = [f"{area}: {total} active requests, {len(items)} ranked problem clusters."]
    for i in items[:5]:
        lines.append(f"- {i['district']}: {SECTOR_LABEL.get(i['sector'], i['sector'])}, {i['n_requesters']} people, score {i['score']}.")
    if silent:
        lines.append("Silent areas needing outreach: " + ", ".join(s["district"] for s in silent) + ".")
    flagged = [i for i in items if i["integrity"]["multiplier"] < 0.9]
    if flagged:
        lines.append(f"{len(flagged)} cluster(s) look coordinated and are down-weighted.")
    return "\n".join(lines)
