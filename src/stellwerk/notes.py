from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable


_URL_RE = re.compile(r"https?://[^\s)\]>\"']+", re.IGNORECASE)


def _strip_url(url: str) -> str:
    return url.rstrip(".,;:!?\")']>")


def _extract_urls(text: str) -> list[str]:
    urls: list[str] = []
    for m in _URL_RE.finditer(text or ""):
        u = _strip_url(m.group(0))
        if u and u.startswith(("http://", "https://")):
            urls.append(u)
    # preserve order, de-dupe
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def _is_checkbox(line: str) -> bool:
    s = line.strip()
    return s.startswith("- [ ") or s.startswith("- [x") or s.startswith("- [X")


def _parse_checkbox(line: str) -> tuple[bool, str] | None:
    s = line.strip()
    if not s.startswith("- ["):
        return None
    # - [ ] text
    # - [x] text
    if len(s) < 6:
        return None
    checked = s[3:4].lower() == "x"
    # find closing bracket
    end = s.find("]")
    if end == -1:
        return None
    text = s[end + 1 :].strip()
    return checked, text


def _is_ordered_item(line: str) -> bool:
    return bool(re.match(r"^\s*\d+\.\s+", line))


def _strip_ordered_prefix(line: str) -> str:
    return re.sub(r"^\s*\d+\.\s+", "", line).strip()


def _is_bullet(line: str) -> bool:
    s = line.strip()
    return s.startswith("- ") or s.startswith("* ")


def _strip_bullet_prefix(line: str) -> str:
    s = line.strip()
    if s.startswith("- "):
        return s[2:].strip()
    if s.startswith("* "):
        return s[2:].strip()
    return s


@dataclass(frozen=True)
class ParsedNotes:
    summary: str
    steps: list[str]
    checklist: list[dict[str, object]]  # {text, done}
    risks: list[str]
    sources: list[str]
    images: list[str]
    extra_sections: dict[str, str]
    raw: str

    def as_dict(self) -> dict[str, object]:
        return {
            "summary": self.summary,
            "steps": self.steps,
            "checklist": self.checklist,
            "risks": self.risks,
            "sources": self.sources,
            "images": self.images,
            "extra_sections": self.extra_sections,
            "raw": self.raw,
        }


def _norm_heading(h: str) -> str:
    return re.sub(r"\s+", " ", (h or "").strip()).lower()


def _heading_from_line(line: str) -> str | None:
    s = line.strip()
    if s.startswith("### "):
        return s[4:].strip()
    if s.startswith("## "):
        return s[3:].strip()
    if s.startswith("# "):
        return s[2:].strip()

    # Tolerate "Titel:" style headings.
    if s.endswith(":") and 2 <= len(s) <= 40:
        return s[:-1].strip()

    return None


def _collect_text(lines: Iterable[str]) -> str:
    # Keep readable spacing, but avoid huge multi-blank blocks.
    out: list[str] = []
    blank = 0
    for ln in lines:
        if not ln.strip():
            blank += 1
            if blank <= 1:
                out.append("")
            continue
        blank = 0
        out.append(ln.rstrip())
    return "\n".join(out).strip()


@lru_cache(maxsize=4096)
def parse_work_package_notes(notes: str) -> ParsedNotes:
    raw = (notes or "").strip()
    if not raw:
        return ParsedNotes(
            summary="",
            steps=[],
            checklist=[],
            risks=[],
            sources=[],
            images=[],
            extra_sections={},
            raw="",
        )

    lines = raw.splitlines()

    # Split into sections.
    sections: dict[str, list[str]] = {"__preamble__": []}
    current = "__preamble__"

    for line in lines:
        h = _heading_from_line(line)
        if h:
            current = h
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)

    preamble = _collect_text(sections.get("__preamble__", []))

    def pick(*names: str) -> str:
        for n in names:
            for k, v in sections.items():
                if _norm_heading(k) == _norm_heading(n):
                    return _collect_text(v)
        return ""

    # Steps / Ablauf
    steps_text = pick("Schritte", "Ablauf", "Vorgehen", "Plan", "Workflow")
    steps: list[str] = []
    for ln in (steps_text.splitlines() if steps_text else []):
        if _is_ordered_item(ln):
            steps.append(_strip_ordered_prefix(ln))
        elif _is_bullet(ln):
            steps.append(_strip_bullet_prefix(ln))
        else:
            # tolerate plain lines as steps if they look like short imperatives
            s = ln.strip()
            if s and len(s) <= 120 and not s.startswith("```"):
                steps.append(s)

    # Definition of Done / Checklist
    dod_text = pick(
        "Definition of Done",
        "DoD",
        "Checkliste",
        "Done",
        "Ergebnis",
    )
    checklist: list[dict[str, object]] = []
    if dod_text:
        for ln in dod_text.splitlines():
            if _is_checkbox(ln):
                parsed = _parse_checkbox(ln)
                if parsed:
                    done, text = parsed
                    if text:
                        checklist.append({"text": text, "done": bool(done)})
            elif _is_bullet(ln):
                text = _strip_bullet_prefix(ln)
                if text:
                    checklist.append({"text": text, "done": False})

    # Risks
    risks_text = pick("Risiken", "Risiko", "Risks", "Stolpersteine")
    risks: list[str] = []
    if risks_text:
        for ln in risks_text.splitlines():
            if _is_bullet(ln):
                text = _strip_bullet_prefix(ln)
                if text:
                    risks.append(text)
            else:
                s = ln.strip()
                if s and len(s) <= 160:
                    risks.append(s)

    # Sources (URLs)
    sources_text = pick("Quellen", "Quellen & Links", "Links", "Sources")
    sources = _extract_urls(sources_text) if sources_text else []

    # Images (URLs)
    images_text = pick("Bilder", "Images")
    images = _extract_urls(images_text) if images_text else []

    # Extra sections: keep everything not recognized.
    used = {
        "__preamble__",
        "Schritte",
        "Ablauf",
        "Vorgehen",
        "Plan",
        "Workflow",
        "Definition of Done",
        "DoD",
        "Checkliste",
        "Done",
        "Ergebnis",
        "Risiken",
        "Risiko",
        "Risks",
        "Stolpersteine",
        "Quellen",
        "Quellen & Links",
        "Links",
        "Sources",
        "Bilder",
        "Images",
    }

    extra_sections: dict[str, str] = {}
    for k, v in sections.items():
        if k == "__preamble__":
            continue
        if _norm_heading(k) in {_norm_heading(x) for x in used}:
            continue
        text = _collect_text(v)
        if text:
            extra_sections[k.strip()] = text

    # Summary: prefer preamble, else first non-empty section.
    summary = preamble
    if not summary:
        for k, v in sections.items():
            if k == "__preamble__":
                continue
            txt = _collect_text(v)
            if txt:
                summary = txt
                break

    return ParsedNotes(
        summary=summary,
        steps=steps,
        checklist=checklist,
        risks=risks,
        sources=sources,
        images=images,
        extra_sections=extra_sections,
        raw=raw,
    )


def default_work_package_details(*, title: str, notes: str) -> dict[str, object]:
    parsed = parse_work_package_notes(notes).as_dict()
    if parsed["summary"] or parsed["steps"] or parsed["checklist"] or parsed["risks"]:
        return parsed

    # If the model/user left notes empty, still present a useful structured scaffold.
    summary = f"Ziel dieses Arbeitspakets: {title.strip() or 'Arbeitspaket'}"
    return {
        "summary": summary,
        "steps": [
            "Rahmen klären (Scope, Inputs, Abhängigkeiten)",
            "Umsetzung in kleinen Schritten", 
            "Review/Abnahme + Ergebnis dokumentieren",
        ],
        "checklist": [
            {"text": "Scope ist klar und klein genug", "done": False},
            {"text": "Ergebnis ist nachvollziehbar dokumentiert", "done": False},
            {"text": "Risiken/Offene Fragen sind adressiert", "done": False},
        ],
        "risks": [
            "Unklarer Scope → vorher 5-Minuten-Abgrenzung",
            "Zu große Änderung → in 2–3 Teilaufgaben schneiden",
        ],
        "sources": [],
        "images": [],
        "extra_sections": {},
        "raw": notes or "",
    }
