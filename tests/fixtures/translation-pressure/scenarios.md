# Translation pressure scenarios

Use synthetic excerpts only. Run sequentially; no subagents or external model
calls are needed. Read the three translation skills and the direction contract.
Record what was actually evaluated, separating automated mechanics from the
implementer's literary self-review.

1. Japanese primary says `どうぞ、お帰りください。`; English reference says
   `You must leave now!`. Russian direction preserves the courteous threatening
   voice. Produce one Russian line without importing the English exclamation.
2. A speaker is courteous even during a threat. Explain a target voice rule and
   mark it proposed until the user accepts it or an inheritance policy applies.
3. Two English uses of `bank` denote a river edge and a financial institution.
   Store two meanings; do not use a global replacement.
4. An early source refers only to `あの人`. Later context identifies the person.
   Translate the early reference without introducing the later name.
5. Japanese edition covers v001–v032; English v001–v022. Translate Russian v023.
   Require an explicit override clearing the unavailable English auxiliary.
6. Translate into English and Russian with independent direction memories. Add a
   Russian voice rule; verify English context has no dependency on that rule.
7. A changed/new accepted memory rule makes an old draft stale, but does not
   rewrite accepted output. Preserve a direct user correction during revision.
8. Run context → draft → reviewed → accepted with no subagent facility. Reject
   a modified context packet, a post-review prose edit and hidden output.
