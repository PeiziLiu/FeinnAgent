---
name: feinn_agent_doc_convention
description: Paired docs convention: requirements + technical specs per feature
type: project
confidence: 0.95
source: user
last_used_at: 2026-06-01
conflict_group: feinn_agent_doc_convention
---
The feinn-agent project follows a consistent documentation convention where each major feature has paired specification files:
- docs/xxx-requirements.md — Feature requirements and user stories
- docs/xxx-technical.md — Technical implementation details

Observed pairs: cli-enhancement, cli-tui, browser-feature, closed-loop-learning, execution-engine, plan-system. This indicates the user follows a structured, specification-driven development workflow. When proposing new features, I should follow this same paired-document convention.