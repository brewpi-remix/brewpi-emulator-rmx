# Milestone 1 review handoff

Date: November 13, 2026. Status: specification and original fixture deliverable complete for owner review; implementation not started. The owner's firmware-first instruction governs all behavioral ambiguities, including bugs. Completion here is a documentation/data result, not accepted runtime conformance or authorization for milestone 2.

## Deliverables and acceptance mapping

| Milestone 1 requirement | Delivered artifact and evidence |
| --- | --- |
| Reference identity/build personality and startup | [Behavioral contract](../protocol/behavioral-contract.md): pinned normal Uno/RevC profile, identity fields, startup sequence, real host timing, and explicit PTY/USB distinction. |
| Full supported command/response contract | Same contract: command actions/order, byte/token semantics, fields/types, query/patch behavior, unsupported selected-build commands, annotations, LCD layout/bytes, and tick/persistence interactions. |
| Default settings/constants/diagnostics and initial conditions | [Defaults](../protocol/defaults.md) and [original default dataset](../protocol/test-vectors/defaults-v1.json): raw facts, exact C/F wire values, cold V=48 C peaks, synthetic IDs, normal timing, presets, physical loads, and external plant conditions. |
| Diagnostic IDs and arguments | [Diagnostic mapping](../protocol/diagnostics.md) and [43 metadata records](../protocol/test-vectors/diagnostics-v1.json), including reachable, debug-guarded, inactive, and EEPROM-reload-only validation paths; no copied diagnostic expansion prose. |
| Firmware bugs and questions | [21 findings](../protocol/firmware-findings.md) preserve deterministic bugs and identify undefined/hardware-dependent evidence requirements. No cleaner protocol policy is substituted. |
| Original protocol fixtures | [Format/coverage guide](../protocol/test-vectors/README.md) and [57 cases](../protocol/test-vectors/protocol-v1.json): 48 source-defined cases and nine explicitly unqualified characterization cases. |
| Live/saved settings, units, and reset semantics | Contract/defaults plus cases for incremental j, S/C volatility/intermediate stores, profile save thresholds, E/R, byte-wrapped conversion, and ordered unit interpretation. |
| Independent MIT licensing and dependency disposition | [Provenance record](../licenses/milestone-1.md), root MIT license, and [third-party inventory](../../THIRD_PARTY_NOTICES.md): original authored data/prose, no reference implementation, no incorporated library, and external tool/client roles clearly separated. |

## Follow-up review corrections

The follow-up review distinguishes U normalization from saved-record validation: E4/E5 remain reachable during EEPROM reload, invalid stored records are cleared without a U acknowledgment or generic E3, and valid nonlocal owners can retain records without a live sensor target. It also specifies the parser's stale-value behavior after a full later key and the low-signed-word narrowing of V.diffIntegral, with original vectors preserving both quirks.

Preset construction now defines raw cold variables, timer/latch/filter state, live/saved agreement, and coherent clock constraints. Reset-dependent observations use explicit restart-completion barriers, camera timeout setup includes the active latch, and mixed diagnostic/reply observations have explicit ordering where needed. Empty-object discovery/settings and stored-owner boundary cases close additional fixture gaps. These changes add four source-defined cases and one finding without introducing implementation or copied reference material.

## Static checks and evidence limits

Validated JSON parseability without duplicate object keys, metadata/license markers, unique case IDs, preset and artifact-pointer references, valid input/output hex, exact source/default field sets and number/string/null types, diagnostic type/ID/argument signatures, raw identity/settings/LCD payloads, synthetic ROM CRCs, declared bus search order, source-link paths/line bounds, local Markdown links/anchors, whitespace, and tracked/untracked file scope. Independent one-off arithmetic cross-checked C/F defaults and physical capacities. These are artifact/data checks; no emulator/parser/controller or executable fixture runner was created to make the expectations pass.

Final inventory checks passed for 42 project files, 138 local file links, five heading-anchor links, 108 revision-pinned source links, 57 unique cases, 116 reply expectations, 60 diagnostic expectations, and 43 metadata signatures. The root MIT text and historical handoff/setup records are unchanged. These checks were completed before staging the milestone, with the initial main commit unchanged. The owner subsequently authorized committing and pushing the reviewed artifacts and supporting documentation to main, while retaining the implementation stop.

All six reference checkouts remain unchanged at the recorded revisions. No reference test/client/logger/parser/model was imported or executed. There was no native build, automated emulator test suite, host/panel process, Arduino/hardware test, Pi installation, commit, or push during specification creation and review. Original expected data came from the independently written contract and interoperability facts, not recorded outputs or copied tests.

The source-defined expectations are inferences requiring later execution, not proven Arduino observations. The nine requires_reference_trace cases have no fabricated exact output and counts_as_pass=false. They cover slot-16/uninitialized-record/ROM-overrun behavior, duplicate-target and electrical-latch histories, sentinel-based drift arithmetic, sensor transaction/embedded-diagnostic timing, extreme scalar overflow, and pin/OneWire conflicts. A future conformance report must keep these unresolved until the exact reference artifact and setup have been characterized; it must not count them as passing or silently change behavior.

## Review stopping point

Review the contract, raw defaults, findings, and fixture format before authorizing any code. In particular, confirm the selected normal Uno/RevC personality and the distinction between faithful controller quirks and independently modeled external brewing physics. The exact physical Pi model/OS remains a later qualification input; this does not leave the defined protocol semantics provisional. No next implementation action is authorized by this handoff.
