# Establishing a Project Baseline

Prose metrics are meaningless in isolation. A numeric sentence-length result
tells you nothing without knowing what is normal for this project, author,
language, prose profile, viewpoint, and scene type. Build a baseline from
accepted evidence selected through the resolved prose stack. Never compare
surface metrics across languages or incompatible voice scopes.

## Building the Baseline

Run the bundled `/project-maintenance` prose check from the project root and
record its per-document metrics:

```bash
cw check prose . > baseline_report.txt
```

From the collected results, note:

- **Sentence length range**: what's the typical mean and standard deviation across chapters? A chapter with mean sentence length 2 standard deviations from the project average is worth investigating.
- **Opener distribution**: which repeated structures are normal in this
  language, viewpoint, and voice scope, and which create audible uniformity?
- **Dialogue ratio**: what range do conversation-heavy chapters fall in vs action chapters? This gives you genre-appropriate expectations for new scenes.
- **Repetition baseline**: every author has words they lean on. The baseline tells you which repetitions are voice and which are unintentional echoes.

## Comparing a Draft

Run the same `cw check prose` command with the draft in its managed project
path, then compare section by section against the baseline. Look for:

- **Metrics that fall outside the project's established range**: these are investigation triggers, not automatic problems. A chapter that breaks pattern might be doing so intentionally (a tense scene with shorter sentences, a reflective passage with longer ones).
- **Sudden shifts within a single document**: if the first half of a chapter has dramatically different metrics than the second half, that's worth examining. It may indicate a voice drift, especially in AI-assisted drafts where the model's tendencies gradually override the project style.
- **POV consistency**: use only language-supported signals, then inspect the
  text to determine whether a metric shift reflects viewpoint drift.

## What the Baseline Can't Tell You

The baseline captures mechanical patterns, not quality. A draft that matches every metric perfectly can still be lifeless prose. A draft that deviates dramatically might be the best chapter in the project. The baseline helps you ask "is this consistent with the project's voice?" The answer to "is this good?" requires human judgment.

## Updating the Baseline

When new chapters are published and approved, add them to the baseline. The baseline should represent the project as it currently stands, not a frozen snapshot from chapter 1. Author voice evolves: the baseline should track that evolution.

If the project has distinct voices (different POV characters, different narrative modes), maintain separate baselines per voice/mode. Comparing a third-person chapter against first-person chapters will produce misleading deviations.
