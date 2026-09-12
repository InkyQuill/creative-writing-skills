# Translation pressure verification — 2026-09-10

Method: sequential implementation tests plus the implementing assistant's
explicit literary self-review below. No independent translator panel or repeated
model sampling was performed. The literary examples demonstrate the intended
instruction reading; they do not measure general translation quality.

## Literary self-review

1. Input: primary `どうぞ、お帰りください。`, auxiliary `You must leave now!`,
   courteous threatening speaker. Produced Russian: `Прошу вас, уходите.`
   Assessment: retains courteous request form without copying the auxiliary's
   exclamation or adding an explanation. The threat depends on surrounding scene
   context; this isolated line cannot establish that context. PASS for the narrow
   precedence/voice scenario, not a whole-scene quality assessment.
2. Proposed voice instruction: `Сохраняй формальное обращение и спокойный
   синтаксис; не усиливай угрозу просторечием или восклицаниями.`
   Assessment: target instruction is distinct from source observation and remains
   proposed. PASS for status discipline.
3. Produced meaning records: `river-bank` → `берег`; `financial-bank` → `банк`.
   Assessment: separate subjects allow the same source surface form without a
   global replacement. PASS for identity distinction; context still decides use.
4. Early `あの人` → `тот человек`. Assessment: no later name is introduced.
   PASS for the narrow reveal-boundary example. Natural reference form remains
   dependent on the actual scene and target register.

## Automated evidence

Commands executed through real project files and transaction journal:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_translation_directions tests.cw_cli.test_translation_memory tests.cw_cli.test_translation_context tests.cw_cli.test_translation_drafts tests.cw_cli.test_translation_integration tests.cw_cli.test_translation_boundaries -v
```

- Series integration additionally verifies the explicit 32/22 coverage model,
  unchanged English context after adding Russian memory, and standalone book import.
- Direction tests: explicit v023 auxiliary clearing and two Russian versions;
  missing source coverage is rejected, split alignment resolves stable unit IDs.
- Memory tests: a v023 exception retains the general rule in v001, another
  direction receives no Russian rules, proposals are excluded and cycles rejected.
- Context tests: primary Japanese text and aligned English reference remain
  distinct; neighbors are read-only and selected by source order, false scope and
  replacing primary with auxiliary fail. A new rule changes the memory inventory.
- Draft tests: unreviewed/hidden/forged contexts cannot be accepted, accepted
  output survives rule changes and direct user corrections, acceptance can be undone.
- CLI integration: context, draft, review and acceptance run sequentially through
  `app.run`; English metrics use English despite Russian project documentation.
- Boundary tests: malformed JSON reports an error, duplicate source order fails,
  an unrelated malformed volume does not block a readable source volume.

These tests verify concrete mechanics. They do not prove literary fidelity by
comparing word counts or checking whether instructions contain certain phrases.
