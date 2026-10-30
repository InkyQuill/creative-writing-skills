# Preserve What Human Reviewers Value

Use this procedure when processing `good` or `brilliant` signals. Capture the
human judgment before consuming the overlay so later passes know what worked.
This is review evidence, not a story fact or an automatic standing style rule.

## Choose a Durable Home

Reuse the project's existing strengths, review-learning, or voice-evidence
notes. Use `$kb-management` for file conventions and source/status boundaries,
and `$story-memory` for later retrieval. Keep one source of truth and link to it
from relevant character/style references instead of copying the evidence.

When capture is within the active review-processing scope and no record exists,
create a concise `review-strengths.md` in the existing project notes/reference
location if that home is unambiguous. Do not create a new folder structure,
register the record as a chapter, or copy manuscript content to global memory.
If the destination is materially ambiguous, retain the signal and resolve the
destination; do not discard praise to complete sidecar cleanup.

## Record the Evidence

Keep each signal traceable even when several entries are grouped by chapter:

- **Source identity:** book ID when available, chapter ID, original sidecar
  path, and signal ID. Use this composite identity for deduplication, not the
  excerpt or signal ID alone across different books.
- **Source passage:** chapter path and scene citation when known, exact
  `selected_text`, and the source hash/anchor context available in the sidecar.
  The excerpt must survive later edits or removal of the original passage.
- **Human judgment:** `good` (liked) or `brilliant` (loved), and the comment
  verbatim when present. Record “no reason supplied” for an empty comment.
  Record reviewer identity only when actually known; the sidecar does not
  require an identity field. Do not substitute the author for an unknown reviewer.
- **Applicable scope:** manuscript language and the passage's known narrator,
  character, scene, or context. Leave unavailable details unknown.
- **Interpretation, if useful:** a concise, passage-grounded hypothesis about
  what works. Mark assistant interpretation with `<AI>...</AI>` and keep it
  separate from the human's actual judgment. Preserve `<hidden>` boundaries.

For example, an uncommented `brilliant` mark supports “the reviewer loved this
exchange”; it does not support “the reviewer loves sarcasm” or “all dialogue
should be shorter.” If the reviewer says “I love how she refuses to answer,”
preserve that wording; a broader avoidance/voice principle is still a proposal.
Praise on a draft is evidence of preference, not acceptance of its story facts.
Do not mark the excerpt as an authoritative style sample without that decision.

## Save, Verify, Then Consume

1. Read current source and sidecar. Resolve the intended excerpt against its
   anchor. A stale hash alone does not invalidate praise. If the passage has
   changed, distinguish the praised version from the current one; never attach
   praise silently to a similar replacement. Keep ambiguous records unresolved.
2. Save the evidence with the source identity. On retry, reuse an identical
   capture; if the same identity's type or comment has changed, reconcile that
   evidence before cleanup instead of creating a duplicate or losing the change.
3. Re-read the saved record and verify the identity, excerpt, type, comment,
   and source/version scope. If saving or verification fails, leave the signal.
4. Re-read the sidecar and confirm that the signal still matches what was saved.
   If it changed concurrently, capture the current judgment before consuming it.
   Remove only the verified signal ID; preserve all other records and fields.
5. Verify both the saved evidence and sidecar cleanup. A capture followed by an
   interrupted cleanup is safe to retry using the same source identity.

Read-only tasks return proposed captures without writing or consuming anything.
A positive signal itself is enough evidence to record praise within authorized
processing; do not ask the reviewer to explain or reconfirm an empty comment.

## Use the Evidence Later

Before related drafting, revision, or review, retrieve the relevant praise
records even when their original sidecars have been consumed. Treat them as
features and effects to preserve, with `brilliant` indicating stronger expressed
appreciation, not a numerical quality score or a veto on edits.

When revising, identify what the human valued and preserve it where compatible
with the current request. A requested change can supersede the old preference;
keep the historical evidence and clarify its old scope rather than rewriting
history. Preserve differing reviewers' judgments without inventing consensus.
Repeated praise can motivate a proposed style principle, but never silently
turn a local example into a universal rule or a catchphrase to imitate.
