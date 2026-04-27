#!/usr/bin/env python3
"""
signal - synthesize user research from interview transcripts

drop a folder of interview transcripts (.txt or .md files) and get back:
- ranked pain points by frequency across interviews
- jobs-to-be-done patterns
- notable quotes worth sharing
- a shareable research brief ready to paste into a doc
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

import anthropic


EXTRACT_PROMPT = """You are a user researcher analyzing an interview transcript.

Extract structured insights from this interview. Be specific — use the participant's actual words
where possible. Don't invent things not present in the transcript.

Transcript:
---
{transcript}
---

Return a JSON object:
{{
  "participant_summary": "1 sentence describing who this person seems to be",
  "pain_points": [
    {{
      "pain": "short label",
      "description": "what exactly frustrates them",
      "severity": "high/medium/low based on how much emphasis they gave it",
      "quote": "a direct quote illustrating this, or empty string if none"
    }}
  ],
  "jobs_to_be_done": [
    {{
      "job": "when [situation], I want to [motivation], so I can [outcome]",
      "frequency": "how often this comes up — daily/weekly/occasionally"
    }}
  ],
  "workarounds": [
    "things they're doing today to work around the problem"
  ],
  "feature_requests": [
    {{
      "request": "what they asked for",
      "underlying_need": "the real need behind the request"
    }}
  ],
  "positive_signals": [
    "things they like, things that are working well"
  ],
  "standout_quote": "the single most insightful or memorable quote from this interview"
}}

Return only valid JSON.
"""

SYNTHESIS_PROMPT = """You are a senior product manager synthesizing findings from {n} user interviews.

Here are the extracted insights from each interview:

{analyses}

Synthesize across all interviews into a research brief.

Return a JSON object:
{{
  "tldr": "2-3 sentence summary a VP could read in 30 seconds",
  "participant_overview": "brief description of who was interviewed",
  "top_pain_points": [
    {{
      "pain": "label",
      "description": "consolidated description",
      "mentioned_by": number,
      "severity": "high/medium/low",
      "representative_quote": "best quote across all interviews"
    }}
  ],
  "jtbd_themes": [
    {{
      "theme": "theme name",
      "description": "what people are trying to accomplish",
      "frequency": "how many participants mentioned this"
    }}
  ],
  "workarounds_spotted": [
    "consolidated list of workarounds showing where the pain is real"
  ],
  "feature_requests_ranked": [
    {{
      "request": "what they want",
      "underlying_need": "what they actually need",
      "mentioned_by": number
    }}
  ],
  "things_working_well": [
    "positive signals not to break"
  ],
  "recommended_focus_areas": [
    {{
      "area": "focus area name",
      "rationale": "why this, backed by the data"
    }}
  ],
  "open_questions": [
    "questions this research raises that need further investigation"
  ]
}}

Return only valid JSON.
"""


def read_transcripts(directory: Path) -> list[tuple[str, str]]:
    """Load all .txt and .md files from the directory."""
    files = list(directory.glob("*.txt")) + list(directory.glob("*.md"))
    files = sorted(files)

    if not files:
        print(f"[signal] no .txt or .md files found in {directory}")
        sys.exit(1)

    results = []
    for f in files:
        content = f.read_text(encoding="utf-8", errors="replace").strip()
        if not content:
            print(f"[signal] skipping empty file: {f.name}")
            continue
        results.append((f.name, content))

    return results


def extract_from_transcript(client: anthropic.Anthropic, name: str, transcript: str) -> dict:
    print(f"  extracting from {name}...", flush=True)

    # truncate very long transcripts — 100k chars is usually more than enough
    if len(transcript) > 100_000:
        print(f"  (truncating {name} — it's very long)")
        transcript = transcript[:100_000]

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": EXTRACT_PROMPT.format(transcript=transcript)
        }]
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw, "parse_error": True, "file": name}


def synthesize(client: anthropic.Anthropic, analyses: list[tuple[str, dict]]) -> dict:
    print(f"\n  synthesizing {len(analyses)} interviews...")

    formatted = "\n\n".join(
        f"=== Interview: {name} ===\n{json.dumps(a, indent=2)}"
        for name, a in analyses
    )

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=3000,
        messages=[{
            "role": "user",
            "content": SYNTHESIS_PROMPT.format(n=len(analyses), analyses=formatted)
        }]
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw, "parse_error": True}


def format_brief(synthesis: dict, n_interviews: int, ts: str) -> str:
    lines = [
        "# User Research Brief",
        f"*{n_interviews} interviews · synthesized by signal on {ts}*",
        "",
    ]

    if synthesis.get("parse_error"):
        return "\n".join(lines) + "\n\n" + synthesis.get("raw", "synthesis failed")

    tldr = synthesis.get("tldr")
    if tldr:
        lines += ["## TL;DR", "", tldr, ""]

    overview = synthesis.get("participant_overview")
    if overview:
        lines += ["## Who We Talked To", "", overview, ""]

    pain_points = synthesis.get("top_pain_points", [])
    if pain_points:
        lines += ["## Top Pain Points", ""]
        for i, p in enumerate(pain_points, 1):
            severity = p.get("severity", "")
            mentions = p.get("mentioned_by", "?")
            lines.append(f"### {i}. {p.get('pain', 'Unnamed')} `{severity}` · {mentions}/{n_interviews} participants")
            lines.append("")
            lines.append(p.get("description", ""))
            quote = p.get("representative_quote")
            if quote:
                lines.append(f"\n> \"{quote}\"")
            lines.append("")

    jtbd = synthesis.get("jtbd_themes", [])
    if jtbd:
        lines += ["## Jobs to Be Done", ""]
        for j in jtbd:
            lines.append(f"**{j.get('theme', '?')}** _(mentioned by {j.get('frequency', '?')})_")
            lines.append(j.get("description", ""))
            lines.append("")

    workarounds = synthesis.get("workarounds_spotted", [])
    if workarounds:
        lines += ["## How People Are Working Around the Problem Today", ""]
        for w in workarounds:
            lines.append(f"- {w}")
        lines.append("")

    requests = synthesis.get("feature_requests_ranked", [])
    if requests:
        lines += ["## What They're Asking For", ""]
        for r in requests:
            mentions = r.get("mentioned_by", "?")
            lines.append(f"- **{r.get('request', '?')}** ({mentions} participants)")
            underlying = r.get("underlying_need")
            if underlying:
                lines.append(f"  *underlying need: {underlying}*")
        lines.append("")

    working = synthesis.get("things_working_well", [])
    if working:
        lines += ["## What's Working (Don't Break This)", ""]
        for w in working:
            lines.append(f"- {w}")
        lines.append("")

    focus = synthesis.get("recommended_focus_areas", [])
    if focus:
        lines += ["## Recommended Focus Areas", ""]
        for i, f in enumerate(focus, 1):
            lines.append(f"**{i}. {f.get('area', '?')}**")
            lines.append(f.get("rationale", ""))
            lines.append("")

    questions = synthesis.get("open_questions", [])
    if questions:
        lines += ["## Open Questions for Next Round", ""]
        for q in questions:
            lines.append(f"- {q}")
        lines.append("")

    return "\n".join(lines)


def format_appendix(analyses: list[tuple[str, dict]]) -> str:
    lines = ["---", "", "# Appendix: Per-Interview Summaries", ""]
    for name, a in analyses:
        lines.append(f"## {name}")
        lines.append("")

        if a.get("parse_error"):
            lines.append(a.get("raw", "extraction failed"))
            lines.append("")
            continue

        summary = a.get("participant_summary")
        if summary:
            lines.append(f"_{summary}_")
            lines.append("")

        standout = a.get("standout_quote")
        if standout:
            lines.append(f"> \"{standout}\"")
            lines.append("")

        pains = a.get("pain_points", [])
        if pains:
            lines.append("**Pain points:**")
            for p in pains:
                lines.append(f"- {p.get('pain', '?')} ({p.get('severity', '?')}) — {p.get('description', '')}")
            lines.append("")

        lines.append("---\n")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="signal - synthesize user research from interview transcripts"
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="directory containing transcript files (.txt or .md)"
    )
    parser.add_argument(
        "--output", "-o",
        help="save the research brief to a markdown file"
    )
    parser.add_argument(
        "--no-appendix",
        action="store_true",
        help="skip per-interview summaries in output"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="also save raw extracted JSON"
    )
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[signal] ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    directory = Path(args.directory).resolve()
    if not directory.is_dir():
        print(f"[signal] {directory} is not a directory")
        sys.exit(1)

    transcripts = read_transcripts(directory)
    print(f"[signal] found {len(transcripts)} transcript(s) in {directory}\n")

    analyses = []
    for name, content in transcripts:
        result = extract_from_transcript(client, name, content)
        analyses.append((name, result))

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    synthesis = synthesize(client, analyses)
    brief = format_brief(synthesis, len(analyses), ts)

    if not args.no_appendix:
        brief += "\n" + format_appendix(analyses)

    print("\n" + "="*60 + "\n")
    print(brief)

    if args.output:
        out = Path(args.output)
        out.write_text(brief)
        print(f"\n[signal] brief saved to {out}")

    if args.json:
        json_path = Path(args.output).with_suffix(".json") if args.output else Path("signal_raw.json")
        json_path.write_text(json.dumps(
            {name: a for name, a in analyses},
            indent=2
        ))
        print(f"[signal] raw JSON saved to {json_path}")


if __name__ == "__main__":
    main()
