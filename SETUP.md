# Workspace preparation

Current repository status, November 13, 2026: [brewpi-remix/brewpi-emulator-rmx](https://github.com/brewpi-remix/brewpi-emulator-rmx) is public, local Git is initialized on `main`, and `origin` is `https://github.com/brewpi-remix/brewpi-emulator-rmx.git`. The owner has authorized the initial plan/scaffolding commit and push. The remaining text preserves the earlier preparation-time snapshot; its no-Git/no-commit statements describe that earlier stage. No emulator implementation has started. See the [project contract](CONTRACT.md) and [implementation plan](IMPLEMENTATION_PLAN.md) for current scope.

Prepared on 2026-11-13 for the existing Codex project. No emulator implementation, build, or runtime testing has started.

The destination /Users/lbussy/GitHub/brewpi-emulator-rmx already existed as an empty directory. HANDOFF.md and this setup record were added. The directory has not been initialized as a Git repository; no remote was created and nothing was committed or pushed.

## Reference repository state

All existing checkouts were clean before preparation. Fetched origin references and tags for all five existing BrewPi repositories. Fast-forwarded brewpi-userdocs-rmx from c0fcaeb to bc8704c; the other four already matched their upstream branches. Cloned the missing brewpi-remix/fuscus repository into /Users/lbussy/GitHub/fuscus.

| Local directory under /Users/lbussy/GitHub | Branch | Verified HEAD | Action |
| --- | --- | --- | --- |
| brewpi-firmware-rmx | master | 8f1fa1213cbbfc1f987fada5168d01925e1a2ee8 | Fetched; already current |
| brewpi-script-rmx | main | d183fb5319b928f78b4c0eb6f05fe3620610ffff | Fetched; already current |
| brewpi-tools-rmx | main | 7e95e19796bed3e8cd6aa08f08f89db05ac66fa4 | Fetched; already current |
| brewpi-userdocs-rmx | main | bc8704c40b09afbc5d3d8df2df04cc7ed358c9ba | Fetched and fast-forwarded |
| brewpi-www-rmx | main | f79631830a99575e250403f08a19be8bf944596c | Fetched; already current |
| fuscus | master | ac371054ed181afff1c1b74f9be8e93d5a86c8e1 | Cloned |

Each origin is https://github.com/brewpi-remix/<directory-name>.git. After preparation, every reference checkout had an empty git status --porcelain result and zero ahead/behind commits relative to its configured upstream. No reference source files were edited locally. This is a preparation-time snapshot; recheck status before further work.

## Next action

Read HANDOFF.md, inspect applicable instructions and the local source, and produce the implementation plan for user review. Do not start implementation.
