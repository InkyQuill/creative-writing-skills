# Relationship diagrams

Use a diagram when the edges between items carry the main idea. Start with a
small Mermaid diagram or plain SVG. Keep node labels brief and explain the
relationship in nearby text. If nodes link to detail, use ordinary links or
buttons that remain keyboard accessible; avoid making click handlers the
only route to information.

Read `/md-validation` for Mermaid syntax and check the rendered result.
For large graphs, first consider splitting the subject into smaller views.
Use an interactive graph library only when users must rearrange or filter
nodes; package any required library with the artifact when offline use is
part of the task.
