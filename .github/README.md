# Repository automation

The [regression workflow](workflows/regression.yml) checks static specifications, helper regressions, native source builds/sanitizers, and isolated host/panel integration. Completion requires matching executed receipts from every lane. See the [development guide](../docs/development.md) and [CI helpers](../tests/ci/README.md). No workflow publishes releases, deploys, activates services, or accesses physical controllers.
