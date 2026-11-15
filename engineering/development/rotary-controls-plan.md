# LCD rotary encoder, pushbutton, and door controls plan

Date: November 15, 2026. Status: owner-approved planning decisions, saved at the owner's request. Implementation, committing, and pushing are not authorized by this document. Original planning prose is copyright 2026 Lee Bussy under the root [MIT License](../../LICENSE.md).

## Purpose and governing scope

Add rotary encoder and pushbutton controls to the emulator's graphical and terminal LCD interfaces, plus local door opening/closing and display dimming. Preserve the firmware's menu and confirmed-operation behavior except for the explicit, deterministic exceptions agreed below. Continue normal controller operation while the menu is open.

Follow the [project contract](../../CONTRACT.md), [implementation plan](../../IMPLEMENTATION_PLAN.md), [contributing guide](../../CONTRIBUTING.md), [behavioral contract](../protocol/behavioral-contract.md), [firmware findings](../protocol/firmware-findings.md), and [provenance gate](../licenses/README.md#review-gate). The owner's decisions in this plan supersede the earlier preserve-all-bugs instruction only for the local rotary/menu behavior described here. Serial behavior remains unchanged. This is not authorization to fix unrelated firmware quirks or modify reference repositories.

The source reference remains firmware `8f1fa1213cbbfc1f987fada5168d01925e1a2ee8`, normally the Uno/RevC personality. The [bug and edge-case register](../protocol/bugs-and-edge-cases.md) records historical firmware facts; retain those facts and distinguish approved emulator exceptions from actual reference behavior. No firmware code, headers, tables, routines, tests, fonts, or assets may be copied, translated, or adapted. Future code and tests must be independently authored under MIT.

Extend the current [LCD design](Add%20LCD.md) and [LCD review](lcd-review.md). Their read-only viewer/input prohibitions are superseded for the controls authorized in this plan, subject to a later implementation request. Existing unrelated work, candidate version 0.0.1-rc.1, frozen packages, release evidence, and hardware qualification boundaries remain outside this planning task. A later feature implementation needs its own source/package and release disposition; do not silently replace frozen artifacts.

## Decisions against the original ten-item firmware review

The owner's numbered answers referred to the ten-item review in chat, not to the R-series IDs in the saved register. This table preserves that correspondence.

| Original item | Topic | Agreed decision |
| --- | --- | --- |
| 1 | Rotation decoding and limits | Preserve rotation direction, full/half-step support, and endpoint wrapping, including temperature maximum-to-minimum and minimum-to-maximum wrapping. Graphical controls generate logical rotation events; electrical quadrature decoding can be tested separately. |
| 2 | Pushbutton handling | One deliberate virtual activation produces one pushbutton action. Do not introduce distinct double-click, long-press, release, or hold-repeat actions. GUI input has no physical contact bounce; held keys or mouse buttons must not cause accidental repeated confirmations. |
| 3 | Temperature editing | Retain tenths-of-the-configured-unit editing and configured bounds. Confirmation without rotation must preserve the exact original target, including precision beyond one decimal place. Local confirmation must not save an out-of-range target. If changed bounds exclude an existing target, bound it to the nearest extent. Preserve serial behavior; this is not a general serial validation change. |
| 4 | Timeout and cancellation | Stage the proposed mode and target together. Timeout discards the draft without changing live settings; there is no live mode change to undo. |
| 5 | Browsing side effects | Browsing must not alter live mode, targets, controller state, persistence, or annotations. Commit only on intentional final confirmation. Passing through Off must not disable targets, reset waiting state, or write settings. |
| 6 | Confirmed-setting effects | Preserve the appropriate firmware setter's controller evaluation, storage, and peak-detection effects after confirmation. The firmware reset called by these setters clears peak-detection flags; it is not a general PID integral/history reset. Preserve operation ordering and deferred output updates. |
| 7 | Annotations and display | Preserve firmware menu annotations, their existing 31-content-byte limit, and room-alternation suppression/restoration during editing. Emit annotations after successful confirmation using committed values, not previews. |
| 8 | Backlight interaction | Every deliberate turn or press resets inactivity, including on the normal screen. The first press both restores brightness and opens the menu. Implement dimmed text in both GUI and terminal, with an explicit keep-backlight-on option. |
| 9 | Blocking menu loops | Use a nonblocking state machine. Sampling, plant evolution, PID/state/output updates, serial processing, and viewer heartbeats continue while editing. Existing serial-parser blocking and output-backpressure rules are separate and remain unchanged. |
| 10 | Invalid modes | Allow only beer constant (`b`), fridge constant (`f`), beer profile (`p`), and off (`o`) through local controls. An invalid existing mode gets an explicit invalid editor state; do not index outside a lookup or silently change the live mode. Require deliberate valid selection and confirmation. Do not change serial mode behavior. |

## Resolved follow-up determinations

- Preserve the exact original temperature on confirmation without rotation. Once rotated, selection uses the existing firmware-compatible tenths conversion in the current display unit. An initially out-of-range selection is bounded to the nearest endpoint. If minimum exceeds maximum, refuse the edit with an explanation rather than inventing a range. When range enforcement changes an existing target, that is an explicit bounds exception to unchanged-target preservation.
- Retain the 20 C starting selection for an invalid or disabled target, converted to the current display unit and bounded to the configured range. Explicit confirmation can replace that invalid/disabled target with the displayed selection.
- Use wall-clock time for the nominal ten-second inactivity timeout, selection blinking, and dimming. These remain usable while the simulation is paused or accelerated; simulation time continues to own controller and plant behavior.
- Cancel an active draft when an external change affects its mode, target, units, or bounds. Do not overwrite the newer state on a stale confirmation, and do not roll back legitimate background controller updates or externally committed settings. Derived controller updates alone must not make normal beer-mode editing unusable; identify the draft's actual editable dependencies.
- In both GUI and terminal, a first turn or press restores brightness and performs its normal action. A first press opens the menu rather than being consumed solely to wake the display. Replace the physical startup-held-button concept with an explicit keep-backlight-on option; no boot-held GUI gesture is required.
- An invalid existing mode is displayed explicitly and stays live until the user deliberately commits a valid selection. The restriction applies to local controls, not serial writes or saved-state loading semantics.
- Discard unfinished edits on viewer loss, controller reset, and checkpoint resume. Preserve committed controller state. Viewer failure is not a controller reset.

The bounds exception must be implemented at the local control/menu boundary without changing serial converters, accepted serial values, command replies, or existing serial persistence behavior. External bounds changes invalidate a draft; the local editor must then use the new bounds and nearest valid selection. Do not turn this instruction into unsolicited rewriting of arbitrary serial writes.

## Graphical interface

Retain the existing green twenty-column, four-row LCD with the degree symbol and firmware text/layout. Add an original rotary control with a center pushbutton, clearly labeled clockwise/counterclockwise alternatives, and focused keyboard input: Left/Right rotate, and Enter/Space presses. Preserve usable focus indication and resizing; controls must not shift or reflow LCD cells. A held key/button must not repeatedly confirm across menu stages.

Add a door button labeled with its next action, Open door or Close door, and show the actual modeled door state. Door state is separate from an uncommitted menu draft. Opening/closing changes the modeled physical input so configured door sensing, controller behavior, lighting, and annotations follow their existing paths; it must not directly force a controller state or actuator output. Repeating an already-satisfied door request is an acknowledged no-op.

Dim LCD text after inactivity and restore it on deliberate interaction. The keep-backlight-on option bypasses automatic dimming. Use the same activity model as the terminal and do not fake dimming by changing LCD character data or serial L bytes.

## Terminal interface

Retain the LCD panel and add exactly one reusable command/status line beneath it. Read terminal input independently of the controller serial PTY. Input must remain nonblocking and must not compete with the host's serial connection or use redirected standard input as a new controller channel.

| Command | Physical action represented |
| --- | --- |
| `cw` | One clockwise logical rotation event. |
| `ccw` | One counterclockwise logical rotation event. |
| `press` | One encoder pushbutton event. |
| `door open` | Open the modeled door. |
| `door close` | Close the modeled door. |
| `help` | Show compact command guidance on the reusable line. |

Enter submits the typed command; it is not itself the encoder pushbutton. Only the press command represents that action. On submission, erase/rewrite the command line with a brief acknowledgment, then erase/rewrite it back to the prompt. New typing can dismiss the acknowledgment immediately. Errors and help use the same line without scrolling; command entry, acknowledgment, and prompt must not allocate additional terminal lines. Bound input length and keep even invalid or long input within the single-line editor.

Dim the terminal LCD text after inactivity while keeping the prompt readable. Deliberate input restores brightness. Support a keep-backlight-on option in terminal mode as well as GUI mode. Brief acknowledgments use nonblocking wall-clock deadlines; they must not delay the engine or lose newly typed commands.

Interactive terminal controls require cursor rewriting and adequate terminal geometry, including the new command line. Unsupported terminals receive an explanation instead of a scrolling imitation of the command interface. Terminal settings and owned input modes must be restored on exit and on handled shutdown paths. Preserve foreground/background handling, bounded output, redirected diagnostics, resize recovery, and viewer fallback properties from the existing LCD work. Record the unavoidable inability to restore state after SIGKILL without claiming that as clean shutdown behavior.

## Menu and confirmation model

Use explicit states for the normal controller screen, setting selection, mode selection, beer target editing, and fridge target editing. Preserve top-level Mode, Beer, Fridge ordering and the mode order `bfpo`. Rotation wraps; pressing opens/selects/confirms. No new Back, Cancel, profile-schedule editor, or additional controller settings menu was requested; inactivity discards the draft.

Keep editable proposals separate from the live controller. Selecting Beer or Fridge stages the matching constant mode and target instead of immediately switching modes. Selecting beer/fridge constant in the mode editor opens the associated target editor. The final temperature press commits the staged mode and target as one intentional operation. Selecting Profile or Off and pressing is its final confirmation; only an actual Off commit invokes target disabling. Preserve confirmed setter ordering and save semantics without importing firmware routines. Do not claim host-filesystem atomic durability beyond the existing storage guarantees.

Preserve selected-field blinking and suppress room alternation while the menu is open. Continue refreshing measured temperatures and controller status behind the editing fields. Restore the current live display on cancellation or timeout, not a stale copy of the screen or controller state captured on entry.

## Architecture and ownership

The current C++ engine owns controller state and the retained LCD shadow; the local presentation adapter and Tk child currently observe that shadow. Extend this arrangement rather than implementing a second controller or menu in Python. Python presents controls and sends physical-action events; C++ owns menu transitions, drafts, validation, confirmation, persistence, annotations, and authoritative door state.

Extend the existing private inherited IPC with versioned, strictly validated, bounded rotation, press, and door messages. No listening network port, additional serial client, shell execution, or unrestricted command injection is needed. Preserve nonblocking budgets, heartbeat progress, bounded queues, and owned-child cleanup. Action events cannot be coalesced like display frames: preserve accepted order, prevent duplicate commits, and provide explicit bounded-overload/failure behavior rather than silently losing actions or replaying old clicks after reconnect.

Process local events and serial/controller work in one deterministic engine ownership model; no GUI thread may mutate engine data directly. Resolve external changes before accepting a stale local confirmation. Treat the local menu/draft and display activity as transient interface state, not EEPROM-like settings. Checkpoint resume starts outside an unfinished edit while retaining committed controller state and the established engine checkpoint guarantees. Ensure a saved editing overlay cannot remain as a stale active-looking menu after resume.

GUI loss discards the draft before terminal fallback. Terminal input loss or loss of an interactive viewer likewise cannot leave a hidden pending commit. Closing a viewer must not stop normal controller execution. Door state belongs to the modeled physical environment rather than the draft and follows the existing plant/checkpoint ownership contract.

## Implementation sequence after separate authorization

1. Record these approved behavior exceptions in the owning LCD/control specifications while retaining the historical firmware findings and IDs. Define exact activity, conflict, event ordering, range reconciliation, and interface-state reset rules before coding.
2. Independently implement the staged, nonblocking menu model and explicit engine confirmation operations, preserving confirmed firmware setter behavior and serial compatibility outside the approved local exceptions.
3. Extend private IPC and the local presentation interface with bounded, validated action events, authoritative state feedback, and deterministic failure/duplicate handling.
4. Add the graphical rotary/pushbutton/door controls and the nonblocking single-line terminal editor, including focus, terminal cleanup, resize, fallback, and input ownership.
5. Add shared wall-clock inactivity and dimming behavior with keep-backlight-on support in both interfaces.
6. Run focused deterministic tests, existing affected regressions, and visual/terminal checks. Present implementation and evidence for review; committing, pushing, packaging, release, deployment, and physical qualification require their own authorization.

## Validation and acceptance

- Test each menu transition, both directions, endpoint wrapping, full/half-step handling at the appropriate input layer, one action per deliberate press, and no unintended hold-repeat or multi-stage confirmation.
- Test Celsius/Fahrenheit increments, unchanged-target precision, invalid/disabled starting targets, out-of-range existing targets, changed bounds, reversed bounds, and exact nearest-boundary behavior. Confirm unchanged serial acceptance, replies, and persistence.
- Prove browsing and timeout leave live mode, targets, controller state, saved settings, and annotations unaffected. Test intentional Profile/Off confirmation and paired constant-mode/target confirmation, including the preserved setter side effects and annotation limits.
- Prove temperatures, plant age, PID/state evaluation, output updates, serial commands, and viewer heartbeats continue during editing. Test pause and acceleration independently from wall-clock UI timers.
- Test conflicts from web/serial changes, invalid existing modes, resets, viewer failure, fallback, checkpoint resume, and restored live display. No canceled draft may undo newer committed state or survive invisibly for later replay.
- Test door open/close and repeated requests through both interfaces against configured sensor/controller behavior, annotations, lighting, and authoritative feedback. A local door command must not bypass device assignment semantics.
- Test dimming, activity refresh, first-action wake-and-act behavior, readable terminal prompt, and keep-backlight-on in GUI and terminal. Dimming must not alter controller LCD bytes or serial output.
- Test bounded malformed, excessive, duplicate, and stale IPC input; ordered rapid actions; slow consumers; child loss; and nonblocking acknowledgments. Preserve controller responsiveness and existing serial-output ordering/backpressure guarantees.
- Test terminal command submission, editing, invalid/long input, brief confirmation, new typing during acknowledgment, no command/status scrolling, resize, foreground recovery, redirected streams, unsupported terminal capabilities, and terminal restoration after handled exit.
- Visually verify the GUI's degree symbol, LCD geometry, controls, focus, resizing, door feedback, and dimmed text; separately verify terminal presentation and single-line behavior. Do not equate source review or simulated tests with physical Arduino or Pi qualification.

## Current stopping point

This document saves the discussion and decisions only. No implementation, reference change, test execution, commit, push, package replacement, CI run, service activation, deployment, or physical-device operation is authorized by saving it. Retain unrelated uncommitted LCD and R3 work unchanged.
