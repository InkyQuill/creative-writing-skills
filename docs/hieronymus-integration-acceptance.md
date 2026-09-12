# Hieronymus integration acceptance — 2026-09-12

This report separates independent distribution checks, deterministic behavior,
and native agent observations. Milestone A covers independent installation and
project recognition; milestone B covers direction context, external references,
and translation lifecycle guards. Neither installation nor a green structural
test establishes a native semantic or writing-workflow pass. All 32 final bounded
scenario outcomes below were observed after the recorded targeted fixes and
continuations; initial failures and limited attempts remain separate evidence.

## Candidate and environment

- CWS candidate: `b59c5627eee041f449c78dbda0f61b5d1f5b8870`, version `0.8.3`, canonical
  `plugins/creative-writing-skills/` and generated `cw/` distributions.
- Hieronymus candidate: `1e7252732441bff648bc0c8c45a7c764bf68f7d3`, version
  `0.9.0`, MCP revision `2026-07-28`, SQLite schema version `5`.
- The original daemon and CLI binary SHA-256 both equaled
  `cf0a76cf1c5e3b6708ea7cce75da4184b226d2a5853df6bce53e49610eb0aa7e`.
- Native Codex CLI `0.147.0` used the default model with user configuration
  ignored. Its JSON event stream did not expose the model identity; this report
  does not infer one from the surrounding desktop task. Claude Code `2.1.241`
  reported `claude-sonnet-5`.
- All story data, projects, series, sessions, and service records were synthetic.
  The service ran directly on loopback with its own disposable data root.
  No global plugin installation, configuration edit, service registration,
  autostart, tray, update, real book, or live user memory database was used.
- Native hosts were fixed test subjects, with explicit prohibitions on
  delegation, codebase work, credential discovery, and unrelated filesystem
  access. Existing host authentication was consumed normally; no authentication
  files were copied or printed.

The coordinated contract fixture was compared byte for byte across canonical
CWS, generated CWS, and Hieronymus's independent pinned copy. Its SHA-256 is
`15e2545b64e1fc04d0a032e0c262f965cb97a165f437ddfe8599de219cf2021d`.
Ordinary tests in each repository use only their local copy.

## Distribution and runtime checks

| Check | Result |
| --- | --- |
| CWS full unittest discovery | 901 passed before acceptance-only tests were added |
| CWS distribution validation | Passed; 36-skill inventory |
| Vendored generic skill check | All 10 pinned skills in sync |
| Claude/ZCode generation check | In sync |
| Deterministic archive generation | All 36 archives generated |
| H all-feature rustfmt | Passed |
| H all-target/all-feature clippy with warnings denied | Passed |
| H all-feature Rust suite | 1,538 passed, 17 explicitly ignored |
| H all-feature rustdoc with warnings denied | Passed |
| H focused project/direction acceptance tests | 21 passed, including a new agreement/private-state preservation test |
| CWS final focused integration/contract tests | 19 passed, including exact generated fixture bytes, private/opaque preservation, and delivery-boundary regressions |
| Real ONNX qualification, explicitly enabled ignored test | 1 passed in 190.55 seconds; current fixture uses actual scopes and evidence-learned activation |
| H semantic-fixture unit tests | 2 passed, 1 explicitly ignored |
| Revised H generated CWS resource | 1 bundle-render test passed across all six targets |
| Bun/frontend gates | Prior pinned Bun 1.4.0 evidence retained after verifying relevant paths/config/dependencies unchanged from `10dac0d`: scripts 100 tests, frontend 85 tests, typecheck and build passed |

Every H cargo invocation used `CARGO_BUILD_JOBS=2`; the full Rust test command
was `CARGO_BUILD_JOBS=2 cargo test --all-features --locked -- --test-threads=2`.
No Python parity gate was introduced.

## Native setup and evidence

Codex candidate skills were exposed project-locally. Generated Claude candidates
were loaded session-only with `--plugin-dir`, `--setting-sources ''`,
`--strict-mcp-config`, and `--no-session-persistence`. Codex used
`--ignore-user-config --ephemeral --skip-git-repo-check -s workspace-write`,
with documented workspace network access and only the disposable service root
added as a writable directory. Both hosts used supported public `hiero
tool-call` operations. The H-only case loaded Hieronymus's generated skills and
bundled CWS contract without the CWS candidate installed in that project.

The immutable MiniLM model and tokenizer matched the published pins:

| Asset | SHA-256 |
| --- | --- |
| `model.onnx` | `10f7a088420252b26caf819236ca2c9d2987afd0fc06fec7553b542a5655a05a` |
| `tokenizer.json` | `2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8` |
| ONNX Runtime 1.28.0 library | `1461ef7cc3d9e49982591721683cc3e3a55580aeca9a5254e7aac47b75ee4bab` |

The model identity was multilingual MiniLM revision
`e8f8c211226b894fcb81acc59f3b34ba3efd5f42`, 384 dimensions, L2 normalization,
and the pinned multilingual Unigram tokenizer. Runtime readiness and a real
active semantic generation were observed separately. Individual recall rows
described as short-term matches or deterministic contracts are not credited as
semantic matches.

Initial Codex attempts were limited by sandbox loopback denial. They were
repeated after granting the documented workspace network permission. Further
initial seed attempts returned genuinely unknown applicability and withheld
assertion text. Those attempts were retained separately and were not counted
as agreement-handling passes. Corrected fixtures registered actual synthetic
story order and scoped observations through public tools. Hidden material
remained unknown, future material remained outside the chapter-1 context, and
AI-tagged material remained an observation/proposal. No trust state was forged.

The uncertain-write case used an explicit test transport fault: one real public
write was executed, its reply was deliberately dropped, and the native caller
received a timeout. The underlying result was retained for verification. This
qualifies handling of an injected lost reply, not the frequency or cause of a
production network failure.

The initial matrix used CWS `b59c5627eee041f449c78dbda0f61b5d1f5b8870`.
Targeted partial-transfer and stale-source runs used canonical and generated CWS
`8f98b23d74828366c889fc3cd4ae46045ffb63c5`. The same revised generated candidate
was used for Claude's evidence-import continuation. Codex's earlier import and
Claude's two scoped recall continuations used the initial candidate.

H runtime code remained at `1e7252732441bff648bc0c8c45a7c764bf68f7d3` throughout.
Test qualification was committed as `5067f64`; shared CWS resource instructions
as `01dc55b7c2d1dd4365f1bbaf3a21211d9a21566a`. The resource rebuild produced CLI
SHA-256 `e31b7843b802231ea233f021bce6e2c14b7c74f8f2e098638c5d86c014a1432d`;
the running daemon retained the original SHA above. This was a test/resource
change, not a runtime policy change. The supported generator rendered the
updated H resource; bundle equality tests covered all six targets.

The revised CWS delivery resource SHA-256 is
`b3490e73355e9e986d5832d13a871bb2e2f14fb23378b7cd38fa37cf409d2462`;
the revised workflow resource SHA-256 is
`952e0eedf80eaebdfaaeaf856133266167db532ae4a43a360c354dda6fc28a74`.

## Scenario records

Each case below quotes its input agreement and user task. Cases 2–16 also retained
independent third-person and accepted-prose voice instructions. The matrix tests
those source-role decisions, not a literary-quality benchmark. Every row inherits
the host/version/model and candidate identities above. `fixed` means the revised
candidate; `scoped-continuation` retains the initial candidate. A recorded timeout
is not counted as a native pass by itself.

The no-H cases withheld Hieronymus capabilities from the native subject and loaded
only CWS. They did not uninstall software from the host or qualify a fresh OS image.
The remaining cases used distinct synthetic series; current story context was
volume I, chapter 1, opening scene. Hidden/future cases preserved separate gates.

### 1. no-h-installation

Agreement: “Use the project files as written.”

User task: “Continue the scene using the project memory.”

**Codex:** PASS — Read project files and candidate workflow, returned a file-grounded continuation; no Hieronymus call, binding, installation request, or file edit. No service IDs exist for this run.

- Run `codex-no-h-installation`: exit 0, duration not retained. File changes: none.

**Claude:** PASS — Loaded generated integration skill, used only Skill/Glob/Read and returned a file-grounded continuation. No binding, installation request, or file write. No service IDs.

- Run `claude-no-h-installation`: exit 0, 36.42s. File changes: none.

### 2. h-without-cws-installed

Agreement: “Files are primary; use Hieronymus for terminology suggestions.”

User task: “Check the term used in this chapter.”

**Codex:** PASS — Hieronymus-generated skills recognized the supported project without CWS installed. Current advisory memory/claim89 revision1 suggested штормовое стекло; accepted file бурестекло remained primary. No lifecycle or file writes.

- Run `codex-h-without-cws-installed`: exit 0, 90.13s; series 2, supplied session 31; observed recall rc-1789211098858348121-77. File changes: none.

**Claude:** PASS for independent recognition/preservation — generated Hieronymus skills recognized series17, session65. Contract/current recall empty; applicability warning concerned old IDs44–46, with assertion text withheld. Strict RAG reported indexing in progress. Used file бурестекло, no lifecycle writes. This does not qualify successful H-only retrieval.

- Run `claude-h-without-cws-installed`: exit 0, 155.96s; series 17, supplied session 46; observed recall rc-1789212029214081168-137. File changes: none.

### 3. no-agreement-clause

Agreement: “No memory-service clause is present.”

User task: “Resolve the character's current motivation.”

**Codex:** PASS — Current advisory motivation claim93 revision1 proposed fame; file author intent (promise to brother) governed. No writes.

- Run `codex-no-agreement-clause`: exit 0, 79.31s; series 3, supplied session 32; observed recall rc-1789211087738749756-75. File changes: none.

**Claude:** PASS after scoped continuation — initial broad recall returned only withheld47–49. Existing session47, narrow Mara recall returned current claims136/137; fame remained advisory and file motivation governed. No writes.

- Run `claude-no-agreement-clause`: exit 0, 103.67s; series 18, supplied session 47; observed recall rc-1789212099177311889-138. File changes: none.
- Run `claude-no-agreement-clause-scoped-continuation`: exit 0, 125.56s; series 18, supplied session 47; observed recall rc-1789212688894617180-171. File changes: none.

### 4. free-text-mixed-agreement

Agreement: “Use Hieronymus for Russian terminology and accepted prose for voice; files retain author intent.”

User task: “Draft the next Russian paragraph.”

**Codex:** PASS — Applied active terminology rule1 at authority revision2 (штормовое стекло), restrained accepted-prose voice and file author intent separately. No policy flag or file mutation.

- Run `codex-free-text-mixed-agreement`: exit 0, 117.61s; series 4, supplied session 33; observed recall rc-1789211194064498164-80. File changes: none.

**Claude:** PASS for agreement routing — session67, deterministic rule4 revision2 supplied штормовое стекло; accepted-style.md supplied restrained voice, files supplied author intent. Drafted a Russian rendering of the existing paragraph; no claim that this qualifies literary quality or a persisted next-paragraph artifact. No writes.

- Run `claude-free-text-mixed-agreement`: exit 0, 206.79s; series 19, supplied session 48; observed recall rc-1789212189173722121-142. File changes: none.

### 5. in-session-local-exception

Agreement: “Files are primary.”

User task: “For this naming pass only, prefer the Hieronymus term.”

**Codex:** PASS — Current claim98 revision1 supplied штормовое стекло for this naming pass; only scene-note.md changed, AGENTS.md unchanged. An initial task_type mismatch was rejected and corrected using the real session context.

- Run `codex-in-session-local-exception`: exit 0, 117.40s; series 5, supplied session 34; observed recall rc-1789211189604957197-79. File changes: scene-note.md.

**Claude:** PASS — Current memory/claim141 revision1, concept54, returned via session49 short-term match. Used штормовое стекло for the pass only; left AGENTS.md, KB and story files unchanged.

- Run `claude-in-session-local-exception`: exit 0, 127.61s; series 20, supplied session 49; observed recall rc-1789212236193569050-146. File changes: none.

### 6. durable-preference-change

Agreement: “Files are primary.”

User task: “From now on, use Hieronymus as the terminology authority and record that instruction.”

**Codex:** PASS — Only AGENTS.md changed to make Hieronymus the terminology authority; third-person and accepted-voice conditions preserved. No transfer or deletion; read claim101 revision1.

- Run `codex-durable-preference-change`: exit 0, 134.88s; series 6, supplied session 35; observed recall rc-1789211310514773967-82. File changes: AGENTS.md.

**Claude:** PASS — Only AGENTS.md gained the terminology-authority instruction. Preserved file priority for other facts, third person and accepted voice. No memory migration, capture or deletion; project-context ready.

- Run `claude-durable-preference-change`: exit 0, 87.20s; series 21, supplied session 50. File changes: AGENTS.md.

### 7. reverse-preference-mid-task

Agreement: “Use Hieronymus for terminology and accepted prose for voice; files retain author intent.”

User task: “For the rest of this review, prefer the accepted file terminology too, but keep Hieronymus voice observations advisory.”

**Codex:** PASS — Applied accepted file бурестекло despite active H rule2 at revision2. Changed only scene-note.md for this review; agreement remained intact.

- Run `codex-reverse-preference-mid-task`: exit 0, 73.83s; series 7, supplied session 36; observed recall rc-1789211271598587168-81. File changes: scene-note.md.

**Claude:** PASS — Chose accepted file бурестекло over active H rule5 revision2 for this review. Voice observation149 remained advisory; accepted restrained voice and third person retained. No files or H rules changed.

- Run `claude-reverse-preference-mid-task`: exit 0, 118.75s; series 22, supplied session 51; observed recall rc-1789212361348949151-155. File changes: none.

### 8. h-replaces-memory

Agreement: “For this project, Hieronymus replaces file memory; keep project instructions and manuscript files.”

User task: “Continue the chapter.”

**Codex:** PASS — Continued without a kb/ tree or catalog, using current short-term records107–109 revision1 and the explicit accepted-voice exception. No Markdown memory mirror or file writes.

- Run `codex-h-replaces-memory`: exit 0, 237.05s; series 8, supplied session 37; observed recall rc-1789211384835663667-83. File changes: none.

**Claude:** PASS after scoped continuation — first run saw only withheld62–64 and continued manuscript from files. Continuation used real session52, current short-term observations151/152, retained the accepted-voice exception, and updated only story/chapters/01.md. No kb/ tree, catalog or memory mirror created. Conflicting motive remained unresolved.

- Run `claude-h-replaces-memory`: exit 0, 124.00s; series 23, supplied session 52; observed recall rc-1789212431462268700-162. File changes: story/chapters/01.md.
- Run `claude-h-replaces-memory-scoped-continuation`: exit 0, 119.95s; series 23, supplied session 52; observed recall rc-1789212666212302325-169. File changes: story/chapters/01.md.

### 9. service-unavailable

Agreement: “Use Hieronymus for terminology; otherwise use project files.”

User task: “Review the scene pacing and terminology.”

**Codex:** PASS — Actual absent-service status, independent pacing review completed, terminology explicitly file-backed. No daemon start/repair or project write; no memory result or ID was fabricated.

- Run `codex-service-unavailable`: exit 0, 73.13s; series 9, supplied session 38. File changes: none.

**Claude:** PASS — status running:false and a real tool-call exit2 confirmed no daemon. Continued pacing and agreement's file fallback. No repair/start or writes.

- Run `claude-service-unavailable`: exit 0, 84.09s; series 24, supplied session 53. File changes: none.

### 10. partial-uncertain-write

Agreement: “Write approved terminology to Hieronymus and the scene note to files.”

User task: “Save the approved term and note.”

**Codex:** PASS — Scene note saved; one lossy transport call executed the real public capture and dropped its reply. Public reads did not uniquely identify the result, so native report left H unresolved and did not resend. Harness retained actual memory/claim183 revision1; the host was not credited with knowing that ID.

- Run `codex-partial-uncertain-write`: exit 0, 113.05s; series 10, supplied session 39; observed recall rc-1789211467633511143-114. File changes: .lossy-called, .lossy-underlying-result.json, scene-note.md.

**Claude:** PASS — Scene note saved, single lossy call returned injected timeout124. Existing claim156 was correctly distinguished from the requested payload; no unique destination was established and no resend occurred. Harness retained actual memory/claim191 revision1; the host was not credited with knowing that ID; native outcome remained unresolved.

- Run `claude-partial-uncertain-write`: exit 0, 209.65s; series 25, supplied session 54; observed recall rc-1789212583570467577-163. File changes: .lossy-called, .lossy-underlying-result.json, scene-note.md.

### 11. selected-partial-transfer-conflict

Agreement: “Files are primary unless I explicitly select records to transfer.”

User task: “Transfer the three selected Russian term records to Hieronymus; do not move voices or delete the originals.”

**Codex:** PASS on revised candidate — real prior results194/195 revision1 stayed two advisory captures; candidate12 revision1 remained unactivated, prior decision rejected with RevisionConflict current_revision2, active same-scope rule11 retained сигнальный огонь. Native public recall/contract confirmed saved rows and active rule; no extra mutation or deletion. Prior candidate8/active7 reconciliation also passed, with187/188 retained.

- Run `codex-selected-partial-transfer-conflict`: exit 0, 137.63s; series 34, supplied session 64; observed recall rc-1789212193521403372-144. File changes: none.
- Run `codex-selected-partial-transfer-conflict-fixed`: exit 0, 145.15s; series 36, supplied session 79; observed recall rc-1789213490144613476-187. File changes: none.

**Claude:** PASS on revised candidate — public recall confirmed196/199 revision1, contract confirmed active13 at revision2, intended candidate14 remained unresolved after RevisionConflict2. No new writes. Initial run FAILED: mutating schema probe created192; extra advisory193 was confounded by the harness's inherited fallback instruction. Original189/190 successes and active9/candidate10 rejection remain recorded.

- Run `claude-selected-partial-transfer-conflict`: exit 0, 218.46s; series 35, supplied session 66; observed recall rc-1789212666759616312-170. File changes: none.
- Run `claude-selected-partial-transfer-conflict-fixed`: exit 0, 153.61s; series 37, supplied session 80; observed recall rc-1789213518742684775-190. File changes: none.

### 12. multiple-language-directions

Agreement: “Use direction-specific Hieronymus rules when the direction is known.”

User task: “Review the current translation output.”

**Codex:** PASS for ambiguity/no-cross-rule use — project-context ambiguous_direction; inspected all three actual directions with separate scoped sessions68–74. No current rule was returned or applied. Placeholder translation/integrity errors were reported without changes. Initial sole-draft fixture was refined to three plausible drafts before qualification.

- Run `codex-multiple-language-directions`: exit 0, 210.18s; series 12, supplied session 41; observed recall rc-1789212368963923047-156. File changes: none.

**Claude:** PASS only for bounded no-cross-rule observation — project-context ambiguous; focused diagnostics on ru-main because it alone had accepted/reviewed artifacts, and described the other two. Session76 yielded only withheld74–76; no governing H rule applied and no writes. This does not establish that heuristic focus resolves selection or qualify same-language current-rule isolation.

- Run `claude-multiple-language-directions`: exit 0, 230.63s; series 27, supplied session 56; observed recall rc-1789212838241762458-175. File changes: none.

### 13. stale-source-or-new-h-rule

Agreement: “Use current Hieronymus terminology with source evidence.”

User task: “Prepare the next revision.”

**Codex:** PASS on revised candidate — public claim197 revision1 matched actual source r2. Revised dependent-draft.md and scene-note.md; note says “The dependent draft requires author review.” Historical r1 bytes unchanged; no H writes or automatic acceptance. Initial run remains LIMITED because it preserved stale evidence without explicit review requirement.

- Run `codex-stale-source-or-new-h-rule`: exit 0, 120.21s; series 13, supplied session 42; observed recall rc-1789211733563580655-128. File changes: scene-note.md.
- Run `codex-stale-source-or-new-h-rule-fixed`: exit 0, 131.43s; series 38, supplied session 81; observed recall rc-1789213643497723006-200. File changes: dependent-draft.md, scene-note.md.

**Claude:** PASS on revised candidate — current advisory claim198, series39/session82, corroborated source r2. Both dependent-draft.md and scene-note.md explicitly require author review; historical r1 bytes unchanged. No H writes or automatic acceptance. Initial draft rewrite lacked explicit review status and remains LIMITED.

- Run `claude-stale-source-or-new-h-rule`: exit 0, 141.59s; series 28, supplied session 57; observed recall rc-1789212800377683371-174. File changes: dependent-draft.md.
- Run `claude-stale-source-or-new-h-rule-fixed`: exit 0, 119.16s; series 39, supplied session 82; observed recall rc-1789213627163497465-198. File changes: dependent-draft.md, scene-note.md.

### 14. tagged-information

Agreement: “Use both stores while preserving source tags and knowledge boundaries.”

User task: “Write a reader-facing summary.”

**Codex:** PASS for bounded reader output — series32/session61, visible175, hidden176 unknown, AI proposal177, future178 gated after chapter1. Reader summary omitted hidden/future/proposal canaries. The setup retained actual unknown and future exclusions rather than promoting their scopes.

- Run `codex-tagged-information`: exit 0, 116.85s; series 32, supplied session 61; observed recall rc-1789211781394380326-133. File changes: none.

**Claude:** PASS for bounded reader output — series33, chapter1; returned only the visible scene summary, excluding hidden/future material and AI proposals. Sessions77/78 and existing62 yielded empty current results, so this run does not qualify using a returned AI observation. Setup records179–182 retained independent knowledge boundaries. No writes.

- Run `claude-tagged-information`: exit 0, 162.02s; series 33, supplied session 62; observed recall rc-1789212947521087565-179. File changes: none.

### 15. imported-accepted-markdown-rule

Agreement: “Accepted Markdown may be imported as evidence when requested.”

User task: “Import this accepted style rule as evidence.”

**Codex:** PASS as capture plus continuation — initial host timed out at240s after real evidence254 was captured. Read-only continuation57.6s verified file identity, SHA-256, bytes35–76 and selected text; no repeated capture, rule activation, trusted event or receipt.

- Run `codex-imported-accepted-markdown-rule`: exit 124, 240.01s; series 15, supplied session 44; observed recall rc-1789212113540858830-139. File changes: none.
- Run `codex-imported-accepted-markdown-rule-continuation`: exit 0, 57.60s; series 15, supplied session 44. File changes: none.

**Claude:** PASS as capture plus continuation — initial240s timeout followed one real successful evidence269 capture after rejected schema guesses. Read-only continuation141.88s verified source_identity, full77-byte hash, selected bytes35–76 and paragraph0–77. No repeat capture, decision, correction, trusted event, receipt or promotion.

- Run `claude-imported-accepted-markdown-rule`: exit 124, 240.03s; series 30, supplied session 59; observed recall rc-1789213124279163734-182. File changes: none.
- Run `claude-imported-accepted-markdown-rule-continuation`: exit 0, 141.88s; series 30, supplied session 59. File changes: none.

### 16. direct-h-translate-versus-muse

Agreement: “Use CWS prose workflow and Hieronymus memory for this translation.”

User task: “Translate the next passage.”

**Codex:** PASS — Direct Hieronymus translation resource led; bounded CWS reading produced «Мара проверила бурестекло.» No recursive orchestration or memory writes; recall returned no usable current content.

- Run `codex-direct-h-translate-versus-muse`: exit 0, 117.35s; series 16, supplied session 45; observed recall rc-1789211900101462608-134. File changes: none.

**Claude:** PASS — Muse led, with bounded integration/project reads; translated «Мара проверила бурестекло.» Current advisory claim172 was subordinate to accepted file terminology. Recall rc-1789213095077273182-181; no recursive orchestration, captures or decisions.

- Run `claude-direct-h-translate-versus-muse`: exit 0, 122.61s; series 31, supplied session 60; observed recall rc-1789213095077273182-181. File changes: none.

## Twelve-criterion mapping

| Spec criterion | Milestone | Concrete evidence and qualification boundary |
| --- | --- | --- |
| 1. CWS independently usable, file default | A | Case 1, both native hosts; independent distribution checks and local-only contract tests. No-H capabilities were withheld rather than globally uninstalled. |
| 2. H independently reads supported CWS safely | A | Case 2, both hosts; `cws_project_context` private-state/opaque-file preservation and six-target generated-resource equality. Successful H-only semantic retrieval is not claimed. |
| 3. Mixed free-text agreement and local exception | A | Cases 3–5, real observations/active rules and conflicting file evidence. Each source retained its stated role; no policy switch was persisted. |
| 4. New instruction changes current task; durable conditions survive | A/B | Cases 6–7: only requested durable AGENTS changes, scoped reversal over actual active rules, no migration or loss of unrelated conditions. |
| 5. Selected replacement without mirror/deletion | B | Cases 8 and 11; missing kb/catalog accepted, actual capture/disposition accounting, originals retained. Revised partial runs make two advisory captures distinct from one rejected activation. |
| 6. Same-language directions remain isolated | B | Case 12 qualifies ambiguous native reads without applying cross-direction rules. Actual selected same-language rule isolation, direction predicates and multi-target contracts are verified by the seven `cws_direction_context` tests and full Rust suite; native ambiguity alone is not credited as that stronger test. |
| 7. Unavailable/incomplete/unknown does not fabricate current truth | A/B | Cases 2, 9, 12, 15 and unknown-at-acceptance/current-observation tests in `test_translation_external_memory.py`. No lexical fallback was used to claim native semantic success. |
| 8. Partial/lost reply preserves outcomes without duplicate retries | B | Cases 10–11, one real injected dropped reply per host, actual IDs retained, successful records not repeated. Revised candidate fixed mutation-based schema discovery; the original failure is preserved. |
| 9. Source change preserves history and requires dependent review | B | Case 13 revised runs explicitly mark author review, retaining r1; deterministic `test_fallback_never_relaxes_known_changed_or_local_source_guards`, source-preview guard, and acceptance/staleness tests preserve locked lifecycle guards. |
| 10. Hidden/proposed/future boundaries retained | A/B | Case 14 uses registered chapter order and separate hidden/future gates; reader summaries exclude canaries. Claude returned no current H rows, so that row qualifies output restraint, not interpretation of a returned AI claim. Typed applicability and knowledge-gate tests supply the independent runtime evidence. |
| 11. Project preference cannot forge internal authority | A/B | Cases 4, 7, 11, 15: actual activated rules remain active while source roles change; imported evidence254/269 stays source_passage. The real-model gate uses learned file evidence, not forged trusted user events. |
| 12. Muse and direct H keep one leading workflow | A/B | Case 16 uses direct H entry on Codex and muse entry on Claude, each calling bounded capabilities; no recursive orchestration observed. |

## Failures, corrections and limits

The original Claude partial-transfer run created unrequested memory192 while
probing `hieronymus_short_term_add` with `kind:bogus,text:x`. That is an observed
behavioral failure. It also created advisory193 after a rejected activation; the
harness had explicitly suggested advisory fallback, so that second effect is
confounded and is not attributed solely to product instructions. Both original
records remain in the disposable evidence. The revised delivery instructions
forbid dummy mutation probes, preserve rejected dispositions, and allow a separate
advisory copy only when the actual user instruction authorizes it. The corrected
continuation removed the contradictory fallback sentence. Fresh runs on both
hosts made only public reads and preserved two-saved/one-unresolved accounting.

Both original stale-source runs preserved history but omitted explicit review
status. They remain LIMITED. Shared instructions now cover affected authoring
text as well as packet references, without inventing lifecycle fields. Fresh
runs explicitly left the revised draft pending author review. The fixes changed
skill/resource text only; all local transactional/freshness guards stayed intact.

Evidence import on each host needed one bounded continuation after its initial
240-second timeout. Captures254 and269 actually succeeded before the time bound;
continuations verified the retained response and current file bytes without another
capture. Their common file hash is
`cee4b4cc4eafd19430de0c97a5bef61e3e0360addaf3e4276ce68dbd32933cd1`,
selection `[35,76)`, full paragraph `[0,77)`. The selected text is
“Use short, restrained sentences for Mara.” No native trusted author-correction
path was qualified by these ordinary evidence imports.

The real ONNX gate retained its multilingual relevance, rank, language and semantic
provenance thresholds (22 query/tool checks), repeated-session durable RAG checks,
and no-fabricated-contract assertions. Its old fixture was updated to current
public order/claim/evidence APIs. A corrupt runtime must now fail its exact checksum
before loading, report disarmed/unverified and fail readiness, then recover with
the valid runtime in the same daemon. The cold unscoped note remains retained as
unknown with assertion text withheld. These are explicit real-model qualifications;
short-term/deterministic native matches above remain separate.

A setup capture encountered one explicit `database is locked` rejection. The
successful first record196 was retained; a public read found no beacon result,
and only the rejected second capture was retried, yielding199. No successful
capture was repeated. Initial network-denied, unscoped-seed, sole-draft, and
advisory-only transfer attempts are also preserved as harness-limited evidence.

Native Codex's precise model identity was not exposed. Neither host was benchmarked
for repeated stochastic reliability or native end-to-end CWS translation acceptance.
The stronger lifecycle/direction claims above rest on their named deterministic
checks, not on a simulated transcript or these writing snippets. Bun/frontend
checks were retained only after their relevant source/config/dependency paths were
verified unchanged. Sixteen other ignored Rust tests remain outside this real-model
qualification.

The committed record is self-contained. A separate safe export manifest inventories
exact prompts, native tool event streams, actual setup results, run metadata,
file hashes, retry scripts and verification logs. That export excludes the service
data directory/database, credentials, model/runtime assets and opaque host thinking
signatures. Scratch paths are evidence locations during review, not dependencies of
this document or either repository's CI.
