# AI Writing Antipatterns

Patterns that distinguish AI-generated prose from human-written prose. Organized by evidence quality so you know what to trust.

Resolve the manuscript-language, prose-profile, and applicable project
style/sample resources before using any surface signal. Research findings may
describe a limited corpus; apply them only when the selected prose stack and
same-language evidence support the comparison.

## Research-Backed Signals

These patterns have been identified in peer-reviewed studies with measurable effect sizes. They're worth investigating when you spot them, though none are proof in isolation.

**Sources:** Kobak et al. (2024), BEA 2025 shared task, Ghostbuster (NAACL 2024), RAID (ACL 2024), Nature HSSCOMMS (2025).

### Lexical or reference-pattern uniformity
Some corpora show narrower working vocabulary or altered reference patterns.
Use only metrics supported for the manuscript language, and compare them with
accepted text in the same profile and viewpoint scope. A difference is an
investigation trigger; the passage itself must establish the reader cost.

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
Characters perform the same physical expressions of emotion: breath catching, jaw clenching, stomach dropping, heart hammering. The same metaphor clusters appear across different emotional contexts. Check `cw check prose` repetition output: if the same physical action words cluster across paragraphs, investigate.

### Tidy-summary endings
Scenes and chapters end with a paragraph that summarizes the emotional meaning of what just happened. "As I watched the sunset, I realized that..." or "For the first time, I understood that..." Real prose more often ends on action, image, or dialogue: letting the reader draw the conclusion.

### Overused metaphor clusters
Certain metaphor domains recur across AI-generated text regardless of prompting: weight/heaviness for emotional burden, light/dark for knowledge/ignorance, water/drowning for being overwhelmed. Individual uses are fine; the pattern is in the frequency and predictability.

## Vocabulary Tells Require Local Evidence

No universal word list identifies machine prose. Frequencies shift by model,
prompt, genre, community, and language. Use a lexical tell only when it is
documented in the selected language resource or evidenced as a recurring
project issue. Even then, density plus reader effect matters; never trigger an
edit or an authorship claim on one word. Structural clusters and uniform
emotional altitude are more durable signals; see `tells.md`.

Detector skepticism has a human cost, too: plain, low-variation prose is the normal register of many fluent non-native and formal writers, and detectors have misclassified exactly that prose as machine-made (Liang et al. 2023; Juzek & Ward 2025). Flag what a change would gain for the reader, never what would "pass a detector."
