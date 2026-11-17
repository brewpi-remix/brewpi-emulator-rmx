# Arduino bench validation checklist

This reusable procedure validates practical BrewPi Remix workflows using the Uno I2C firmware build, an Arduino Uno R3, a rudimentary shield, a compatible 20×4 I²C LCD, temperature probes, GPIO indicator LEDs, and a rotary encoder. The five practical checks below are the acceptance gate. Detailed protocol, boundary, and characterization checks are optional. BrewPi firmware must be installed before protocol testing. Actuators are unnecessary for serial, probe, and LED observations; physical heating/cooling performance remains outside this setup. Encoder checks remain deferred until the ordered Fabteck module is installed and its connections are verified.

This document specifies checks, not completed hardware qualification. Use an external evidence copy to record results: `not run`, `in progress`, `pass`, `fail`, `blocked` with the missing prerequisite, or `deferred` with the reason. All unchecked items below are not run unless explicitly marked deferred. A pass requires retained evidence and satisfied preconditions; an unavailable measurement is not a pass.

Follow the [behavioral contract](behavioral-contract.md), [firmware findings](firmware-findings.md), [fixture semantics](test-vectors/README.md), and [provenance gate](../licenses/README.md#review-gate). Arduino action/reaction, including deterministic bugs, governs the comparison. Undefined or build-dependent observations qualify only the recorded artifact and history.

Run the emulator with `--profile i2c` for comparison with this Uno I2C bench. RevC remains the emulator default and the existing 48 source-defined fixtures' personality. The I2C profile matches the bench's shield identity, A0 probe bus, and output pin inventory; physical probe ROMs and LCD driver/electrical behavior remain separate observations. Keep the RevC fixture expectations unchanged.

## Practical acceptance gate

This gate applies to the optional Arduino bench exercise. Physical bench acceptance is separate from software-release publication.

Complete wiring and firmware setup before these checks. Use an isolated BrewPi Remix host configuration and fresh emulator state; keep working brewery configuration separate. Run the ordinary host workflows against the Arduino and emulator separately, discovering and assigning each controller's own probes and pins. Record firmware/emulator/host versions, the wiring and assignments, initial settings, steps, relevant logs/readbacks, and observed results. Exact raw byte/timing traces are needed for optional byte-level or characterization claims, not every ordinary acceptance observation.

- [ ] **1. Host communication:** BrewPi Remix connects, identifies the expected controller personality, reads temperatures and state, applies a normal mode/setpoint change, and reconnects after a controller restart. Confirm the host shows the resulting settings and fresh telemetry; record unexpected errors or recovery steps.
- [ ] **2. Probes:** discover and assign the available beer, chamber, and ambient probes, testing roles sequentially if necessary. Warm/cool each probe independently to confirm the correct role responds. Disconnect and restore each assigned probe, checking missing-data reporting, discovery/assignment retention, and recovery; confirm a missing ambient reading is omitted as specified. Demonstrate response and repeatability; accuracy certification is unnecessary for this gate.
- [ ] **3. Control outputs:** with valid probe assignments and ordinary setpoint changes, observe heating, cooling, idle, and waiting states alongside the correctly labeled LEDs. Check that outputs follow their logical assignments/polarity, ordinary protection waits occur, and required-probe loss and restoration produce the documented controller/output response. Check normal on/off operation of any light/fan outputs included in the bench setup. Exact one-second timer boundaries, pin-removal history, and physical load performance are outside this gate.
- [ ] **4. Persistence:** save ordinary settings and device assignments, record them, and compare after reset and a controlled power cycle. Confirm the settings expected to persist and probe/output assignments survive, telemetry resumes, and the host reconnects. Restart the emulator with its saved controller state for the corresponding check; compare saved configuration without requiring its virtual plant to reproduce physical temperatures.
- [ ] **5. LCD and encoder:** confirm the I²C LCD displays readable mode, probe temperatures, targets, and controller state. Use the Fabteck encoder to enter menus, rotate in both directions, select settings, and confirm mode/target changes; after exit, verify the resulting settings over serial and through the host. Repeat ordinary interactions to expose skipped turns or duplicate presses. If the LCD or encoder is unavailable, mark this check deferred and report partial acceptance rather than passing all five.

Accept the practical baseline when all five checks pass with evidence and no unexplained failure affecting those workflows. Run the comparable emulator workflows at normal speed with `--profile i2c`, allowing its documented local UI behavior. Physical probe warming and cable disconnection are Arduino stimuli; use the emulator's documented scenarios and assignment controls for available comparisons, and record any physical stimulus without a public emulator equivalent as a comparison limit. Do not invent a probe-disconnect control or count native driver state injection as a public workflow. Firmware menu quirks are observations to record, not a reason to assume the physical menu matches the emulator's draft-only controls. An unexpected result in a practical check needs investigation even if it resembles an optional edge case.

The supported conclusion is “works for the tested BrewPi Remix workflows on the recorded setup.” Optional tests may remain not run, blocked, or deferred without preventing that conclusion. They remain unresolved limits; practical acceptance does not establish exact parity for every input, qualify real actuators, or change existing native regression requirements.

## Emulator personality and comparison scope

Separate I2C and parallel display transport modes are unnecessary for this practical gate: the emulator exchanges serial messages and renders a virtual LCD, while the physical firmware drives the actual display. Compare ordinary readings and settings through that shared serial interface.

Controller personality is visible to the host. Start a separate emulator instance with `--profile i2c`, a dedicated `--state` path, and explicit serial path; follow the [startup and persistence rules](../../docs/operation.md#connect-brewpi-remix). Verify `n` reports `s=5`, discovery reports probes on A0 (`14`), and outputs enumerate as 5, 6, 2, 10. Initialize and assign the emulator's own synthetic ROMs rather than copying physical probe records. An A4 probe assignment must produce the documented invalid-OneWire-bus diagnostics while preserving the prior valid slot. Keep `--profile i2c` on restart and checkpoint resume. Profile mismatches fail locally, and older untagged state/checkpoints belong to RevC. The shared virtual LCD does not characterize the physical I²C bus or backpack.

## Equipment and evidence prerequisites

- [ ] Record the Uno R3 identity, USB connection, shield wiring/revision, probe count/type, probe power arrangement, OneWire pull-up, LCD/backpack model, and available LEDs, resistors, encoder, switches, and measurement tools; verify that the rudimentary shield can support the I2C wiring below.
- [ ] Trace the shield connections against the selected firmware's pin assignments before applying test stimuli; record each pin's purpose, LED orientation, and whether illumination represents logical active or inactive.
- [ ] Verify that each added LED has appropriate current limiting, that shield loading is suitable for the Uno, and that test connections cannot join driven outputs; leave actuator loads disconnected.
- [ ] Identify the OneWire data connection separately from output connections; do not place an output indicator or output assignment on the probe bus during ordinary checks.
- [ ] Prepare one probe for initial testing; add other probes individually, label each physical probe with its discovered ROM, and record any roles that must be tested sequentially because probes are limited.
- [ ] Prepare safe, repeatable temperature changes, such as hand warming or separate cool/warm environments; immerse only probes rated for immersion, and keep the board and connectors dry. Record a reference thermometer and acceptance tolerance if claiming temperature accuracy; without one, claim response/repeatability only.
- [ ] Create an evidence directory outside tracked source/package inputs. For the practical gate, retain the setup/version/assignment record and enough logs, readbacks, and LED/LCD observations to support each result. For optional exact-characterization claims, also retain artifact hashes, EEPROM history, exact transmitted/received bytes, timestamps, failures, and recovery actions.
- [ ] Use a dedicated serial session and isolated emulator state, without a working BrewPi installation or another serial client accessing the Uno. Identify the port explicitly; never select a device by trial writes.

## Bench wiring

Wire with USB and other power disconnected. Use the Uno's regulated 5 V and GND rails for this short bench setup, with a common ground for every component. Verify module ratings and connector pinouts first; probe wire colors and encoder contact positions are not standardized. The tables describe Uno header labels, not ATmega package pin numbers. Do not attach LEDs or other output loads to A0, A4, A5, or the encoder signals.

The firmware assignments below are interoperability facts from the pinned [I2C pin map](https://github.com/brewpi-remix/brewpi-firmware-rmx/blob/8f1fa1213cbbfc1f987fada5168d01925e1a2ee8/src/Pins.h#L141). Inspect existing shield connections and pull-ups before adding parallel parts.

### LCD

Use a 5 V, 20×4 HD44780-compatible character LCD with a PCF8574-style backpack whose expander-to-LCD wiring matches the firmware driver. An arbitrary I²C display or a 16×2 display is not an equivalent substitute. The pinned [LCD driver](https://github.com/brewpi-remix/brewpi-firmware-rmx/blob/8f1fa1213cbbfc1f987fada5168d01925e1a2ee8/src/I2cLcd.h) uses P0 for RS, P1 for R/W, P2 for Enable, P3 for backlight control, and P4–P7 for LCD D4–D7.

| LCD backpack contact | Uno connection |
| --- | --- |
| VCC, for a verified 5 V module | 5 V |
| GND | GND |
| SDA | A4 / SDA |
| SCL | A5 / SCL |

The Uno R3's dedicated SDA/SCL header contacts duplicate A4/A5; they are not a second bus. The firmware [address scan](https://github.com/brewpi-remix/brewpi-firmware-rmx/blob/8f1fa1213cbbfc1f987fada5168d01925e1a2ee8/src/I2cLcd.cpp#L76) selects the first responding address from 8 through 119, without identifying the device type. Connect only the LCD on I²C during baseline validation, record its address, and adjust the backpack contrast control for legible text. Confirm existing I²C pull-ups rather than adding resistors blindly.

### Temperature probes

For verified DS18B20 probes, use three-wire external power for the baseline, following the [DS18B20 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ds18b20.pdf). If the probes are another type or the cable pinout is unknown, establish compatibility and the pinout before using this table.

| Probe contact | Uno connection |
| --- | --- |
| VDD | 5 V |
| GND | GND |
| DQ / data, all probes in parallel | A0 |
| One shared bus pull-up | 4.7 kΩ between A0 and 5 V, unless a suitable pull-up is already fitted |

All beer, chamber, and ambient probes share A0; software assigns roles by each probe's ROM. Start with short leads and one probe, then add the others. Use one bus pull-up for the baseline, not one additional resistor per probe. This external OneWire pull-up is separate from the firmware's internal encoder pull-ups. A0 is digital pin identifier `14` in device records on the Uno; use the actual discovered pin value when assigning probes. Do not use the RevC fixture's bus pin `18` (A4), because A4 is SDA in this build.

### Rotary encoder

The selected bench module is the Fabteck rotary encoder with hardware debounce. Verify its supplied documentation and actual output labels before connecting it; do not infer connector order or wire colors from a bare encoder diagram. Connect its identified A output to D8, B output to D9, pushbutton output to D7, supply to 5 V, and ground to GND. Confirm that the conditioned pushbutton output is active LOW and that the outputs produce valid logic levels with the firmware's enabled internal pull-ups before using it for acceptance. Record its hardware revision and any required interface changes. Basic encoder operation belongs to check 5 once installed; extended encoder characterization remains optional.

The following table is an alternative for a bare contact encoder, not the Fabteck module's power wiring.

Use a plain mechanical quadrature encoder with A/B/common contacts and a separate normally open momentary pushbutton. No I²C encoder interface or encoder library is required. The default [encoder input configuration](https://github.com/brewpi-remix/brewpi-firmware-rmx/blob/8f1fa1213cbbfc1f987fada5168d01925e1a2ee8/src/RotaryEncoder.cpp#L114) uses the Uno's internal pull-ups, so short bench wiring needs no added pull-up resistors or debounce capacitors.

| Encoder contact | Uno connection |
| --- | --- |
| A | D8 |
| B | D9 |
| Common / C | GND |
| Pushbutton contact 1 | D7 |
| Pushbutton contact 2 | GND |

A bare contact encoder needs no 5 V connection. Identify the contacts from its datasheet or continuity checks; do not assume the middle contact or mounting tabs have a particular function. If clockwise/counterclockwise behavior is reversed, record the observation and swap A/B with power removed. Encoder modules with VCC or conditioning components require their own wiring review. Leave encoder checks deferred if it is not connected.

### GPIO indicator LEDs

Fit up to four ordinary indicator LEDs, each with its own 1 kΩ series resistor. For an active-low indication, connect each branch as `5 V → 1 kΩ resistor → LED anode → LED cathode → output pin`. A driven LOW lights the LED; a driven HIGH extinguishes it. This choice limits each branch to less than 5 mA even before the LED's forward drop is considered. Arduino's [external LED guidance](https://docs.arduino.cc/built-in-examples/basics/Blink) explains LED polarity and the need for a series resistor; the larger resistance here is a conservative bench choice.

| Label for this bench | Uno output pin | Serial pin identifier | Function to assign |
| --- | --- | --- | --- |
| Cooler | D5 | `5` | Chamber cooler, `f=3` |
| Heater | D6 | `6` | Chamber heater, `f=2` |
| Light | D2 | `2` | Chamber light, `f=4` |
| Fan | D10 | `10` | Chamber fan, `f=7` |

These labels are bench assignments; the firmware does not automatically install device slots or permanently tie those functions to those pins. Discover and assign each output with inversion `x=1` for the active-low wiring above. Illumination then represents logical active only while that assignment actually controls the pin. When testing `x=0`, the same LED indicates logical inactive instead. Unassigned, floating, or previously latched pins need separate observation. Do not share one resistor among multiple LEDs, and do not use the Uno's built-in D13 LED as a substitute for these output indicators.

### Wiring verification

- [ ] With power removed, verify 5 V/GND polarity, the probe pull-up, each LED's resistor and orientation, and absence of shorts; remove any previous RevC connections that use A4 for probes or A5 for an output.
- [ ] Confirm A0 is reserved for OneWire, A4/A5 for I²C, D7–D9 for the optional encoder, and D5/D6/D2/D10 for output indicators; reserve D0/D1 for USB serial.
- [ ] Connect the LCD and one probe first, establish startup and discovery, then add other probes and LED branches with power removed between wiring changes. Add the encoder only after the baseline is repeatable.
- [ ] Photograph or draw the final wiring and record probe ROM labels, LED labels, LCD address, and any shield components already providing pull-ups or indicators.

## Firmware installation and baseline

The bench reference is firmware revision `8f1fa1213cbbfc1f987fada5168d01925e1a2ee8`, Uno I2C personality, debug 0. Its [build configuration](https://github.com/brewpi-remix/brewpi-firmware-rmx/blob/8f1fa1213cbbfc1f987fada5168d01925e1a2ee8/platformio.ini) defines the Uno `I2C` environment and 57600-baud runtime serial connection. Select `I2C` explicitly, not `RevC` or `Glycol`. Reference firmware and tools remain external components under their own licenses.

- [ ] Select or prepare the Uno I2C firmware artifact in a separate build location; record its version, revision, binary hash, and build environment. Retain full compiler/framework/dependency versions, flags, and build output when making optional compiler-dependent characterization claims. Identity text alone does not identify binary bytes.
- [ ] Before upload, record the board's existing program/EEPROM status and recovery method. Upload the selected artifact only during an owner-authorized hardware session; this checklist does not itself execute or authorize a flash.
- [ ] Record the actual post-upload EEPROM state; do not assume uploading firmware erases EEPROM or that a fresh board is already initialized for BrewPi.
- [ ] Open serial at 57600 baud, capture startup from connection/reset, and record whether opening the port resets this Uno. Allow startup to settle before queries; retain boot messages separately from command replies.
- [ ] Send `n`; record all `N` fields and verify the Uno I2C identity, including shield field `s=5` from the pinned [shield identifiers](https://github.com/brewpi-remix/brewpi-firmware-rmx/blob/8f1fa1213cbbfc1f987fada5168d01925e1a2ee8/src/Brewpi.h#L44). Verify the emulator also reports `s=5` with `--profile i2c`; its default RevC fixture still uses `s=2`.
- [ ] If startup reports an invalid/erased controller store, record it and initialize for ordinary testing. Deliberately establishing an erased-store precondition and characterizing `W3` is optional; do not treat arbitrary preexisting EEPROM bytes as a controlled erased-store test.
- [ ] Send `E` to initialize controller configuration, capture its actual diagnostics, then explicitly query `s`, `c`, `v`, and `d{e:1}`. Check defaults and empty assignments without expecting an invented bulk acknowledgment from `E`.
- [ ] Save a reproducible initialized baseline and the commands needed to recreate it; restore that baseline between cases that mutate settings or assignments.

## Optional detailed checks

All subsections below, before the acceptance record, supplement the five practical checks and are not additional acceptance gates. Select checks when diagnosing a practical discrepancy or making a more specific compatibility claim. A native fixture pass remains distinct from an Arduino observation; unexecuted characterization remains unresolved.

### Serial protocol and saved settings

- [ ] Query `n`, `s`, `c`, `v`, `t`, and `l`; check reply prefixes, order, scalar types, numeric formatting, CRLF, and raw LCD bytes against the contract. Distinguish serial LCD shadow checks from physical LCD qualification.
- [ ] Exercise bounded ordinary `j` writes: recognized and unknown keys, duplicate keys, failed conversions, and a later valid member. Verify per-pair diagnostics, incremental changes, annotation ordering, and final `S` then `C`, including no mandatory extra final `T`.
- [ ] Exercise case sensitivity, ignored space/CR/LF, invalid tab/unsupported bytes, first-character aliases, unquoted tokens, trailing commas, and controlled partial-token timeouts. Retain exact byte/chunk timing; use the original fixtures for bounded token-length cases rather than arbitrary fuzzing.
- [ ] Check C/F conversion, fixed-point readback, byte-wrapped flags/filter selectors, and ignored known conversion failures against their specified cases; separate these from extreme-overflow characterization.
- [ ] Compare live and post-reboot state after mode/setpoint/constant changes, `S`, `C`, and `E`; preserve the documented intermediate saves and volatile resets rather than assuming every reset persists defaults.
- [ ] Exercise profile setpoint persistence below, at, and above the 0.25 C saved-target threshold with controlled starting targets; compare settings after restart.
- [ ] Compare `R`, reset-button restart, USB reconnection, and a controlled power cycle, recording which operations actually reset the MCU and what EEPROM state survives. Do not equate `E` with a full reboot.
- [ ] Review all 48 source-defined fixtures for hardware applicability. Map each to a public serial/physical stimulus or mark it blocked by an unestablished precondition; native driver state injection is not an Arduino command and cannot establish a hardware pass. Document every I2C-specific pin/identity substitution in a separate bench case without altering the RevC fixtures.

### Probe discovery, assignment, and telemetry

- [ ] With one probe connected, run discovery with and without values; record ROM, bus pin, enumeration fields, values, and latency. Repeat for each probe and then together, recording actual OneWire search order rather than assuming ROM sorting.
- [ ] Assign discovered ROMs to chamber, beer, and ambient roles through `U`, using the verified A0 bus pin (`p=14`) and valid slots. Verify resulting `U`, installed `d` records, and `t` readings; reassign sequentially if fewer than three probes are available.
- [ ] Compare discovery values, calibrated installed-device reads, and filtered telemetry: `h` values are uncalibrated, `d` with `r=1` is calibrated and unfiltered, and beer/chamber `T` readings are fast-filtered.
- [ ] Warm/cool each probe separately and confirm the intended role changes. Record filter lag and repeatability; do not infer an exact emulator trace match from uncontrolled physical temperatures.
- [ ] Apply and remove a modest calibration offset in C and F; verify difference-unit conversion and the `-0.0625 C` omitted-calibration quirk (`F08`), restoring the original calibration afterward.
- [ ] Disconnect and reconnect each assigned probe using a controlled connection method; record discovery disappearance, retained installed slot, telemetry, diagnostics, controller response, LED state, and recovery time. A disconnected ambient probe must omit `RoomTemp` rather than send a fabricated clearing field.
- [ ] Reboot with probes connected, missing, and subsequently restored; verify assignments persist and capture initialization delays without imposing a universal 250 ms limit.
- [ ] Exercise assigned/unassigned discovery selectors and the `F09` record-field leak with enough probes or safe digital inventory entries to establish the ordering preconditions.
- [ ] Test the accepted zero-ROM assignment separately from actual ROMs; observe live disconnection and bus-dependent timing rather than assuming it resolves to the first real probe (`F20`). Restore the normal assignment afterward.

### GPIO LEDs and controller behavior

An LED establishes an observable indicator state only after its wiring and polarity are known. It does not establish drive voltage, current capacity, relay operation, transient timing, or actuator performance. Readback may describe a logical fallback object rather than the electrical pin. Record logical value, expected pin polarity, and observed illumination separately.

- [ ] Inventory the I2C build's output pins against shield wiring and capture actual discovery order; verify the set is D5, D6, D2, and D10 on both the Arduino and emulator with `--profile i2c`. The default RevC profile has a different set, including A5 (`19`); A5 is SCL on this physical bench and must not receive an LED output assignment.
- [ ] Assign each usable output independently to heater, cooler, light, or fan as appropriate, checking normal and inverted polarity. Use controlled `d` writes in test mode to observe on/off LEDs without ordinary controller output updates immediately overwriting the stimulus; verify that mode and assignments actually establish those preconditions.
- [ ] Read logical output state separately from LED state; test deactivation and reassignment, and retain any disagreement rather than treating logical readback as pin proof.
- [ ] Return to ordinary control and vary chamber temperature/setpoint to request heat, idle, and cooling. Correlate `T` state, output readback, and LEDs while respecting startup, minimum-off, minimum-on, and heat/cool switching waits.
- [ ] Record timing around output transitions and the documented strict minimum-on boundary at 180 seconds. Use timed video or an instrument if exact LED transition timing is needed; unaided visual observations do not prove a one-second boundary.
- [ ] Enter beer constant and profile modes with valid probe assignments; observe derived chamber targets, state changes, and LEDs. Record which PID/filter/estimator outcomes cannot be isolated with the available temperature stimulus; absent loads do not create a controlled thermal response.
- [ ] Change beer filter settings and compare live response with behavior after `C` or reboot, targeting the documented filter-routing quirk (`F10`); block exact coefficient/history claims if the physical stimulus cannot distinguish them.
- [ ] Exercise light/camera requests and their timeout, including test mode skipping output/timeout updates (`F11`); record the actual pin and logical state with the required light assignment.
- [ ] If a verified door input and jumper/switch are available, exercise open/closed indications, annotations, control effects, and recovery without joining driven outputs. Otherwise mark this check blocked by the missing input fixture; it does not require a rotary encoder.
- [ ] Observe LEDs during boot, mode off, probe loss, reset, removal of an active assignment, and reassignment. Do not assume removal clears a latched output; retain that sequence for `F17` characterization.
- [ ] End by requesting mode off, recording resulting LEDs, and removing bench power after capture; mode off alone is not proof that every previously assigned pin is inactive.

### Unresolved characterization register

The [nine characterization fixtures](test-vectors/protocol-v1.json) have no invented exact expected reply and do not count as passing. Run ordinary checks first. Each characterization run needs its own reproducible preconditions, exact artifact, EEPROM history, raw bytes/timing, recovery record, and repeats. Retain observations as artifact-specific evidence even if repeated runs agree. Their supplied stimuli target RevC: review pins before use, replace the OneWire bus with `p=14` and output pins with verified I2C outputs where applicable, and record these as separate I2C variants. Such observations do not close the original RevC artifact obligations automatically.

| Check | Status before execution | Available method and limits |
| --- | --- | --- |
| `U_slot_16` (`F14`) | Not run; separate edge-case session | USB trace, reset/recovery observations, and EEPROM comparison; uninitialized-memory results are artifact-dependent. |
| `overlong_ROM` (`F14`) | Not run; separate edge-case session | USB trace and recovery evidence; memory overrun can invalidate later state, so reestablish the baseline afterward. |
| `U_before_E` (`F18`) | Blocked until erased/invalid-store precondition is controlled | Establish and record the store state separately; ordinary initialized runs do not cover it. |
| `duplicate_function_remove_history` (`F07`) | Not run | Use separate verified LED output pins, duplicate assignments, and both removal orders; record live ownership and pin history. |
| `drift_sentinel_error` (`F15`) | Blocked until missing-peak timeout conditions are reproducible | Physical probe stimulus and elapsed time may help; LEDs alone do not establish internal error/estimator arithmetic. |
| `removed_active_pin_latch` (`F17`) | Not run | Observe a known active LED before/after removal and reassignment; add a meter or logic analyzer for electrical-level or timing claims. |
| `sensor_initialization_and_embedded_D` (`F19`) | Not run | Controlled probe interruption during value discovery with raw serial capture; record diagnostics inside open lists and latency. |
| `large_numeric_overflow` (`F03`) | Not run; separate edge-case session | Exact AVR artifact and USB trace, followed by recovery and baseline restoration; no cross-build guarantee. |
| `digital_pin_conflicts_with_OneWire_bus` (`F17`, `F19`) | Deferred pending electrical review of the shield and probe bus | The I2C variant concerns A0 (`14`), not the RevC fixture's A4 (`18`), which would instead conflict with SDA here. Assigning an output to the bus can disturb connected hardware; specify a suitable isolated/current-limited fixture before running this case. |

### Extended I²C LCD checks

- [ ] Record LCD dimensions, controller/backpack markings, expander wiring, address, supply, and contrast adjustment; confirm all four rows are legible after a cold start.
- [ ] Compare visible mode, temperatures, setpoints, state/wait text, units, and room/chamber alternation with `l` readback during ordinary operation. Preserve raw degree bytes in serial captures; physical glyph rendering is a separate observation.
- [ ] Observe LCD initialization, repaint, and backlight behavior after `C`, `E`, `R`, reset-button restart, and power cycling; record display-only faults separately from serial/control faults.
- [ ] Record I²C write/startup timing and display history under the I2C artifact; do not use these observations as proof of the RevC SPI driver's timing or history.

### Extended encoder checks and unavailable hardware

Basic display/encoder operation is required by practical check 5 when the hardware is available. The extended checks below remain optional and deferred until their equipment is connected; the unavailable physical-load checks do not block practical acceptance with GPIO LEDs.

- [ ] **Optional, deferred — rotary encoder:** count individual detents, characterize bounce, and exercise rapid/reversed input and missed steps beyond the ordinary rotation checks in gate 5.
- [ ] **Optional, deferred — rotary encoder/pushbutton:** once installed, characterize timeout, button bounce, and any supported long-press behavior beyond the ordinary menu entry/selection/confirmation required by check 5; compare with settings and annotations captured after exit.
- [ ] **Deferred — rotary encoder:** characterize mode changes while browsing, timeout restoration, setpoint confirmation, and persistence after restart. The reference menu is not guaranteed to use the emulator's draft-only UI semantics; preserve observed firmware quirks.
- [ ] **Deferred — rotary encoder:** measure control and serial responsiveness during menu activity. The pinned [menu loops](https://github.com/brewpi-remix/brewpi-firmware-rmx/blob/8f1fa1213cbbfc1f987fada5168d01925e1a2ee8/src/Menu.cpp) block ordinary main-loop serial processing; use the physical LCD to observe intermediate edits, then query `s`, `t`, and `l` after exit. Do not treat queued queries or a serial timeout as a live menu trace, and avoid flooding the receive buffer.
- [ ] **Deferred — physical LCD, if unavailable:** mark the LCD section deferred and use ordinary serial `l` shadow checks only; full visible menu interaction remains deferred until both LCD and encoder are connected.
- [ ] **Deferred — actuators and thermal plant:** relay/contact behavior, connected-load polarity, heater/cooler performance, compressor protection under actual operation, and closed-loop thermal response. GPIO LED observations qualify only the recorded output observations.

## Acceptance record

- [ ] Repeat successful ordinary cases from a known baseline, record intermittent failures, and separate firmware startup traffic and asynchronous control messages from direct replies.
- [ ] Compare the emulator at normal speed with matched public preconditions and `--profile i2c`; retain intentional physical-versus-virtual differences, including actual probe ROMs, USB reset behavior, uncontrolled temperature trajectories, and the physical LCD driver. Verify matching I2C identity, OneWire pin, and output inventory; do not mask differences in raw captures. Keep RevC observations separate when explicitly using that profile.
- [ ] Record a result and evidence pointer for each of the five practical checks. Record optional checks separately if attempted; skipped optional checks do not need execution to complete the practical baseline. Keep not-run, blocked, deferred, failed, source-defined regression, and artifact-specific characterization results distinct. Do not report all nine cases resolved merely because ordinary bench checks pass.
- [ ] Review discrepancies against the firmware-first contract before changing the emulator. Author minimal original interoperability expectations only after provenance review; keep firmware binaries, reference code, and raw captures outside MIT fixtures and distributed inputs.
- [ ] State the qualified I2C firmware artifact, Uno/shield/LCD/probe setup, observed GPIO coverage, and remaining limits. Preserve encoder, any unavailable LCD, electrical measurements, actuator deferrals, and unqualified RevC-specific behavior individually rather than claiming full hardware equivalence.

Use the following record in the external evidence copy; all results start as not run.

| Acceptance check | Arduino result / evidence | Emulator result / evidence |
| --- | --- | --- |
| 1. Host communication | Not run | Not run |
| 2. Probes | Not run | Not run; discovery/assignment and scenario readings, with physical-stimulus comparison limits recorded |
| 3. Control outputs | Not run; LED observations | Not run; virtual output observations |
| 4. Persistence | Not run | Not run |
| 5. LCD and encoder | Deferred until connected | Not run; local controls and virtual LCD |

Report the overall result as accepted for the recorded practical workflows, failed with the affected check, or partial with outstanding/deferred checks. Include optional findings only where they explain a discrepancy or limit the claimed coverage.
