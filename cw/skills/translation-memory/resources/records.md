# Translation records

Shared entity identity and direction memory follow the current free-text memory
agreement. File-backed entity records use the project entity KB, and file-backed
direction memory contains terms, voices, decisions, and a direction-wide style
record. When the selected store is Hieronymus, use its supported public records
without requiring a Markdown catalog or record. There is no mandatory Markdown
mirror. For file-backed records, use the flat frontmatter contract documented by
/project-maintenance; keep the actual instructions, examples and rationale in the
Markdown body.

A term record should state the entity/meaning, preferred rendering, permitted
inflections or aliases, rejected forms and context-dependent exceptions. A voice
record should separate observed evidence from the chosen target strategy:

> Observation: the speaker remains formally courteous while threatening.
> Russian instruction: retain formal address and composed syntax; do not add
> slang to intensify the threat. Let the contrast between wording and action
> carry the menace.

Preserve each record's actual provenance, disposition, scope, identifier, and
source revision when the selected store exposes them. Record file references as
edition/unit evidence with a readable locator, for example
`ja-original:u001 — Volume 1, Chapter 3: Scene where the host threatens the guest`.
For direct user decisions, cite the actual decision in the body and use a
`user:` evidence label. Never manufacture a citation or assert certainty from an
unreadable source. Cross-edition identity links remain provisional if ambiguous.

Scope fields combine across dimensions: volume AND entity, for example. A list
within one field means any of the listed identities. An omitted or empty scope
is unrestricted. For a unit scope, use the qualified `edition:unit` identity.
Set the subject narrowly enough to identify the decision, such as `hero-name`
and `hero-voice`, rather than treating all rules about a person as one choice.

An accepted exception cites the general record through `supersedes` and narrows
its scope. The general rule continues elsewhere. A same-scope replacement marks
the predecessor superseded. Cycles and unrelated subjects are invalid. Keep
historical evidence in the record; do not erase rejected choices merely because
another choice was adopted.

When importing precedent, first compare relevant original and translated
passages. Extract names, recurrent expressions, address and voice tendencies,
then apply only the approved inheritance categories. A spelling error, omission
or editorial shortening is a discrepancy to record, not a precedent to repeat.
Import or transfer only records the user selected and authorized. A preference
change alone is not proof that any record moved.
