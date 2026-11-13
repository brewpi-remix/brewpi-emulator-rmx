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
- ✅ Review milestone 2 and authorize its commit and push to main; milestone 3 remains unapproved.
- ▧ Implement independent controller behavior, thermal model, and clock after authorization.
- ▧ Verify the actual host/panel workflows and retain interface-specific evidence.
- ▧ Qualify the agreed Raspberry Pi/Linux target and document operating procedures.
- ▧ Establish CI, branch-protection, and release policies when separately requested.

The [implementation plan](IMPLEMENTATION_PLAN.md) owns milestone acceptance criteria. Milestone 2 has local build/test evidence; actual host/panel integration and Pi qualification remain outstanding.
