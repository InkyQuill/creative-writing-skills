---
name: hieronymus-integration
description: >
  Apply the project's free-text memory agreement when literary work uses
  Hieronymus alongside or instead of file memory. Load when the user requests
  Hieronymus or the project agreement or binding refers to it; remain optional
  when its tools are unavailable.
---

# Hieronymus Integration

Apply the current project's memory agreement without turning it into a mode,
score, or required metadata. The user's current instruction, the nearest
project instructions, and an applicable technical binding can each activate
this skill even when Hieronymus tools are unavailable. A binding identifies a
memory destination; it neither grants trust nor authorizes a write.

Read [the workflow](resources/workflow.md) before choosing sources or resolving
a fallback. Read [the delivery recipes](resources/delivery.md) before calling
any Hieronymus read, capture, or decision tool.

Keep the skill that received the literary task as the one leading workflow.
Use this integration as a bounded memory layer; never recursively invoke a
second authoring or translation orchestrator. CWS remains fully usable without
Hieronymus, and a file-only user does not need to install it.

Treat retrieval, trust, and mutation as separate decisions. Preserve source
tags, provenance, internal rule status, author-only information, character and
reader knowledge boundaries, and unresolved conflicts. Use only public
Hieronymus surfaces discovered in the current host. Do not read a raw database,
ingest a whole project, start background synchronization, or create a new
memory store or transport inside CWS.
