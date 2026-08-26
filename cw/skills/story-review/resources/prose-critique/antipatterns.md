# AI Writing Antipatterns

Patterns that distinguish AI-generated prose from human-written prose. Organized by evidence quality so you know what to trust.

## Research-Backed Signals

These patterns have been identified in peer-reviewed studies with measurable effect sizes. They're worth investigating when you spot them, though none are proof in isolation.

**Sources:** Kobak et al. (2024), BEA 2025 shared task, Ghostbuster (NAACL 2024), RAID (ACL 2024), Nature HSSCOMMS (2025).

### Lower lexical variability
AI text tends to reuse a narrower working vocabulary than human text of comparable length and genre. Measurable via MATTR (Moving Average Type-Token Ratio) or similar windowed metrics. Raw TTR is unreliable at varying text lengths. Compare only against a baseline in the same language: morphologically rich languages such as Russian naturally run higher lexical variety, so an English-calibrated threshold misfires there.

### Fewer personal pronouns
AI-generated fiction uses fewer first-person and second-person pronouns relative to total word count. The prose reads as more "reported" than "experienced." Check the pronoun distribution output from `analyze.py`: if a first-person chapter has unusually low I/me/my counts, investigate.

### More positive-emotion language
AI text skews toward positive sentiment, even in scenes that should be neutral or negative. This manifests as:
- Characters processing grief with remarkable resilience
- Dark situations described with silver-lining framing
- Emotional reactions that resolve too cleanly within the same paragraph

### Shallow character interiority
Characters think in summary rather than in the messy, associative way real thoughts work. Internal monologue reads like a narrator describing thoughts rather than a character having them. Signs:
- Thoughts are always grammatically complete and logically ordered
- No intrusive/unwanted thoughts, no tangents, no mid-thought corrections
- Emotional states are named rather than experienced ("I felt a surge of determination")

### Low dialogue subtext
Characters say what they mean directly. Subtext, the gap between what's said and what's meant, is rare. Conversations are efficient rather than realistic. Signs:
- Characters articulate their feelings clearly in dialogue
- Disagreements are stated rather than shown through evasion, topic-changing, or body language
- No conversations where the real subject is never mentioned

## Community-Identified Structural Patterns

These patterns are widely recognized by writers and editors who work with AI output. They haven't been formally studied with controlled experiments, but they're consistent enough across models and prompting approaches to be useful investigation triggers.

### "Clean but hollow" prose
Grammatically polished, rhythmically smooth, but lacking the irregularity that gives prose texture. Every sentence is competent. None are surprising. The prose is correct rather than alive.

### Generic arc progression
Scenes follow a predictable emotional trajectory: setup → complication → moment of doubt → resolution with growth. Real scenes often end unresolved, escalate without payoff, or achieve resolution in unexpected dimensions.

### Repetitive emotional choreography
Characters perform the same physical expressions of emotion: breath catching, jaw clenching, stomach dropping, heart hammering. The same metaphor clusters appear across different emotional contexts. Check `analyze.py` repetition output: if the same physical action words cluster across paragraphs, investigate.

### Tidy-summary endings
Scenes and chapters end with a paragraph that summarizes the emotional meaning of what just happened. "As I watched the sunset, I realized that..." or "For the first time, I understood that..." Real prose more often ends on action, image, or dialogue: letting the reader draw the conclusion.

### Overused metaphor clusters
Certain metaphor domains recur across AI-generated text regardless of prompting: weight/heaviness for emotional burden, light/dark for knowledge/ignorance, water/drowning for being overwhelmed. Individual uses are fine; the pattern is in the frequency and predictability.

## Vocabulary Tells: Use Density, Not Single Words

Lists of specific words claimed to indicate AI authorship (delve, tapestry, testament, nuanced, etc.) are **not reliable single-document detection signals.** They are:

- Model-version dependent: word frequencies shift with each model update
- Prompt-dependent: style instructions dramatically change vocabulary
- Genre-confounded: "delve" appears in plenty of human-written academic and fantasy prose
- Near-random for Claude specifically: word-level heuristics trained on GPT output don't transfer

They still earn a place as an editorial-taste policy when applied with cluster density instead of one-at-a-time:

- **Distinctive words** (delve, tapestry, testament, myriad, pivotal, underscore): worth noting when two or more land in the same passage.
- **Overused workhorse words** (foster, leverage, seamless, robust, comprehensive): note only at high density, never replace on sight — half of them are ordinary English.
- **Ordinary words** (crucial, key, significant, moreover): corpus-level signals only; never flag them in a single manuscript.

The word set also dates fast: the 2023 tells are not the 2026 tells, and the absence of old tells clears nothing. The tiers above are calibrated on English; on a non-English manuscript they do not apply — vocabulary tells need a list observed in that language's machine output, or should be skipped in favor of structural tells. When you act on vocabulary, be honest that it's a style choice, not a detection method — and never trigger an edit on a single feature. The reliable signal is a cluster of tells plus prose that stays at one pleasant altitude regardless of the scene; see `tells.md`.

Detector skepticism has a human cost, too: plain, low-variation prose is the normal register of many fluent non-native and formal writers, and detectors have misclassified exactly that prose as machine-made (Liang et al. 2023; Juzek & Ward 2025). Flag what a change would gain for the reader, never what would "pass a detector."
