# Translation records

Shared entity records belong in the project entity KB. Direction memory contains
terms, voices, decisions, and a direction-wide style record. Use the flat
frontmatter contract documented by /project-maintenance; keep the actual
instructions, examples and rationale in the Markdown body.

A term record should state the entity/meaning, preferred rendering, permitted
inflections or aliases, rejected forms and context-dependent exceptions. A voice
record should separate observed evidence from the chosen target strategy:

> Observation: the speaker remains formally courteous while threatening.
> Russian instruction: retain formal address and composed syntax; do not add
> slang to intensify the threat. Let the contrast between wording and action
> carry the menace.

Record references as edition/unit evidence with a readable locator, for example
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
