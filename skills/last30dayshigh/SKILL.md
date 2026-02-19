---
name: last30dayshigh
description: Use when user wants ultra-comprehensive research across all sources with maximum web coverage. Triggers on /last30dayshigh, "deep research", "comprehensive search", or when user wants exhaustive multi-source coverage of a topic.
---

# last30dayshigh: Ultra-Comprehensive Research

Thin fork of `/last30days`. Same script, more WebSearch coverage. Use this when you want maximum breadth — 6-8 WebSearches instead of 2, all sources enabled, query diversification.

## Parse User Intent

Same as `/last30days`: extract TOPIC, TARGET_TOOL, QUERY_TYPE from input. Display parsing before running tools.

## Step 1: Pre-flight + Query Variants

**Step 1a — Pre-flight context search:**
```
WebSearch("{TOPIC}")
```

**Step 1b — Generate 3-4 query variants** (not 2 like standard):
- V1: synonym/alternate terminology
- V2: community jargon / niche angle
- V3: use-case framing ("best X for Y")
- V4 (optional): recent news angle ("{TOPIC} 2026")

Same rules: DIFFERENT terminology, 2-5 words each, keyword-optimized.

## Step 2: Run the Research Script

```bash
python3 "$HOME/.claude/skills/last30days/scripts/last30days.py" "$ARGUMENTS" --ultra --include-web --queries="$TOPIC|||$V1|||$V2|||$V3|||$V4" --emit=compact 2>&1
```

Note: calls the **main skill's script** — no scripts directory here.

## Step 3: Extended WebSearch Boost (ALWAYS — not just on sparse)

Run **6-8 targeted WebSearches** regardless of script output:

1. `"{TOPIC} reddit discussion 2026"` — forum threads
2. `"{TOPIC} review comparison 2026"` — reviews and analysis
3. `"{TOPIC} tutorial guide"` — how-to content
4. `"{TOPIC} alternative vs"` — comparison content
5. `"{TOPIC} problems issues"` — pain points and gotchas
6. `"{TOPIC} announcement release"` — recent launches
7. (optional) `"{V1} best practices"` — using variant terminology
8. (optional) `"{V2} examples"` — practical examples

Synthesize web results INTO the script output. Web items rank lower than API-sourced items (no engagement data, -15 penalty) but fill coverage gaps.

## Step 4: Analysis + Output

Follow the same analysis and output format as `/last30days`:
- Engagement-ranked results with source attribution
- Cross-source signal boosting (same URL in 2+ sources → bonus)
- Section by QUERY_TYPE (recommendations, news, how-to, general)
- Copy-paste prompts if TARGET_TOOL is known
