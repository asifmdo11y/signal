# signal

User research synthesis from interview transcripts.

Drop a folder of interview transcripts into signal and get back a structured research brief — ranked pain points, JTBD patterns, notable quotes, and recommended focus areas. The kind of thing that used to take two days of affinity mapping now takes a few minutes.

```
$ python signal.py ./interviews --output research-brief.md

[signal] found 8 transcript(s) in /Users/asif/interviews

  extracting from interview_01_sarah.txt...
  extracting from interview_02_james.txt...
  extracting from interview_03_priya.txt...
  ...

  synthesizing 8 interviews...

============================================================

# User Research Brief
*8 interviews · synthesized by signal on 2025-01-14 09:32*

## TL;DR

Users consistently struggle with the handoff between planning and execution. The core
frustration isn't feature gaps — it's that existing tools don't reflect how teams
actually work, forcing workarounds that create more coordination overhead, not less.

## Top Pain Points

### 1. Status updates are manual and always stale `high` · 6/8 participants

Every team has a different way of reporting status, and none of them are automatic.
PMs end up chasing people down for updates instead of doing real work.

> "I spend like 40% of my week just trying to find out where things actually stand."

### 2. No single source of truth across planning and delivery `high` · 5/8 participants
...
```

## what you get

- **TL;DR** — 2-3 sentences a VP can read in 30 seconds
- **Top pain points** — ranked by how many participants mentioned them, with severity and a representative quote
- **Jobs to Be Done** — synthesized patterns of what people are actually trying to accomplish
- **Workarounds** — how people are solving the problem today (strong signal for real pain)
- **Feature requests** — what they asked for + the underlying need behind each request
- **What's working** — things not to break
- **Recommended focus areas** — synthesis-backed suggestions with rationale
- **Open questions** — what to investigate in the next round
- **Appendix** — per-interview summaries with standout quotes

## usage

```bash
python signal.py ./interviews                        # analyze all .txt/.md in folder
python signal.py ./interviews --output brief.md      # save report
python signal.py ./interviews --no-appendix          # skip per-interview section
python signal.py ./interviews --json                 # also save raw extracted data
```

## transcript format

Any plain text or markdown file works. Signal handles:
- Raw interview transcripts (with or without speaker labels)
- Cleaned notes from user calls
- Support ticket exports
- Survey open-ended responses

If you have speaker labels like `Interviewer:` / `Participant:` it'll use them, but it works fine without them too.

## setup

```bash
git clone https://github.com/asifmdo11y/signal
cd signal
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...

# put your transcripts in a folder
mkdir interviews
# ... add your .txt or .md files ...
python signal.py ./interviews --output brief.md
```

## notes

I built this because I kept doing the same synthesis work manually after every research sprint — copy-pasting quotes into Miro, doing affinity mapping, writing up a doc. This automates the first pass. You still need to review it and add judgment, but the scaffolding is there.

Works best with 5+ interviews. With fewer than 3 the synthesis is less interesting since patterns don't have enough signal to surface.

