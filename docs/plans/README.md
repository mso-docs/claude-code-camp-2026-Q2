# Plans

One plan per `week1_baseline` step, written before porting starts (or,
for steps 00–03, reconstructed immediately after — see each file's
`Status`). Each covers: goal, files being ported, the design decisions or
Ruby/Python differences anticipated going in, how it'll be verified, and an
`Outcome` section filled in once the step lands.

- [00 · Configuration](00_config.md)
- [01 · Struct Skeleton](01_struct_skeleton.md)
- [02 · The Tool Registry](02_the_registry.md)
- [03 · The Prompt Builder](03_prompt_builder.md)
- [04 · The API Client](04_api_client.md)
- [05 · The Agent Loop](05_agent_loop.md)
- [06 · The Logger](06_the_logger.md)
- [07 · The Boukensha.run DSL](07_the_run_dsl.md)
- [08 · The REPL Loop](08_the_repl_loop.md)
- [09 · Global Executable](09_global_executable.md)
- [10 · A Standard Tool Library](10_standard_tool_library.md)
- [11 · A Terminal UI](11_tui.md)
- [12 · Context Management](12_context.md)

See also the living [architecture diagram](../architecture-baseline.md),
updated alongside each step.

## Week 2 and final-week capability work

New capability work in `week2_capable/` — not a Ruby→Python port step, so
these plans don't follow the reference-diff format above.

- [13 · Structured Knowledge Base & Observability Dashboard](13_knowledge_observability.md)
- [14 · Navigator Tool — Semantic Matching, Weighted Pathing & Reasoned Targets](14_navigator_tool.md)
- [15 · OpenTelemetry Tracing & Error Logs](15_otel_tracing.md)
- [16 · State-Aware Execution & Efficient Memory](16_state_aware_execution.md)
