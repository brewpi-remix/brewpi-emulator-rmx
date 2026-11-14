# Development checklist

Status key: ✅ complete, ⏳ in progress, ▧ not started. Checklist status describes evidence available, not approval to proceed.

- ✅ Record source-backed implementation plan and protocol review.
- ✅ Record the independent implementation requirement and MIT license decision.
- ✅ Establish repository documentation, metadata, and directory scaffolding.
- ✅ Review scaffolding/plan consistency and clarify MIT contribution, dependency, and provenance requirements.
- ✅ Create the public GitHub repository, initialize local `main`, and configure the HTTPS `origin`.
- ✅ Complete milestone 1's firmware-faithful contract, fixed-point defaults/units, diagnostic metadata, original fixtures, findings, and independent MIT/dependency disposition.
- ✅ Review and publish milestone 1 to main; characterization-required cases remain unresolved.
- ✅ Implement and validate milestone 2 transport, device registry, and persistence; see the [review record](engineering/development/milestone-2-review.md).
- ✅ Review milestone 2 and authorize its commit and push to main; milestone 3 was subsequently authorized for local implementation/validation.
- ✅ Implement milestone 3 controller behavior, independent thermal model, clock, scenarios, and checkpoint resume; execute all 48 source-defined reviewed cases.
- ✅ Review milestone 3, fix identified issues, and authorize its commit and push to main.
- ✅ Complete and review milestone 4 isolated host/panel integration, fix identified issues, and authorize its setup, tests, and supporting docs for commit and push to main.
- ✅ Complete milestone 5 for the owner-selected isolated Debian 12 ARM64 Linux target and prepare operating procedures; see the [review record](engineering/development/milestone-5-review.md). After review and fixes, the owner authorized its commit and push to main.
- ▧ Qualify physical Pi operation and actual systemd activation if separately requested; retain all nine unresolved firmware-characterization gates.
- ▧ Establish CI, branch-protection, and release policies when separately requested.

The [implementation plan](IMPLEMENTATION_PLAN.md) owns milestone acceptance criteria. Milestones 2 and 3 have native build/test evidence; milestone 4 adds reviewed isolated host/panel integration evidence, and milestone 5 adds selected Linux software qualification and operating guidance. Physical Pi and actual systemd activation remain outstanding.
