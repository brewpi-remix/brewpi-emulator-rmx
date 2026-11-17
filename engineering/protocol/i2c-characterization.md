# Uno I2C firmware characterization

This reference describes observations of the physical Uno I2C personality reporting `v=0.2.13`, `n=da7e14a9`, `s=5`, `y=0`, `b=s`, and `l=3`, using 57600-baud USB serial and three powered OneWire probes on A0. These are independently described interoperability facts, not imported firmware implementation or raw fixtures. The owner's setup uses I2C rather than RevC; these observations do not automatically qualify the pinned RevC fixtures or every I2C build.

The separately retained candidate `brewpi-arduino-uno-i2c-0.2.13+da7e14a9.hex` has SHA-256 `ccf240909702618815864633071e4f1b9e4dba32805241a4f9346b96afdb69ca`. Its name matches the running identity; flash contents have not been read back and compared, so this hash alone does not prove the installed bytes or exact compiler inputs.

## LCD degree byte

Repeated `L` reads from this identified I2C artifact contain raw byte `DF` in the degree cells. RevC retains its source-defined raw byte `B0`. The emulator exports the selected profile byte unchanged on serial, while its local graphical and terminal adapters render either byte as Unicode `°`.

The regression checks cover both profiles, Celsius and Fahrenheit, configuration/default resets, controller restart, checkpoint continuation, and exact serial LCD bytes. These checks do not qualify physical LCD rendering, rotary behavior, or the nine unresolved RevC characterization cases. No firmware implementation, binary, raw capture, generated table, test, or asset is incorporated into the MIT emulator.

## Duplicate heater pin history

With active-low heater slot 4 on D6, installing a second heater in slot 8 on D10 makes both slot aliases command D10. D6 retains its prior driven level. The four tested histories combine initially inactive/active D6 with removing the older/newer record first. Each history was repeated three times from a restored, restarted baseline, with identical independent input-level sequences. D6→D11 and D10→D12 monitoring passed independent polarity/continuity checks before and after the suite. The existing door-input record was temporarily selected on D11/D12 with noninverted input readback, in test mode; it was restored to inverted D4 during cleanup. These sequential same-board input samples include internal pull-ups and are not calibrated voltage or simultaneous edge measurements.

| History stage | Initially inactive D6 | Initially active D6 | D10 |
| --- | --- | --- | --- |
| Duplicate installed inactive | HIGH | LOW | HIGH |
| Either slot alias commands heater on/off | Remains HIGH | Remains LOW | LOW/HIGH |
| Newer D10 alias commanded on before removal | HIGH | LOW | LOW |
| Either record removed, surviving alias commanded on, then off | Remains HIGH | Remains LOW | Remains LOW |
| Surviving record removed | Remains HIGH | Remains LOW | Remains LOW |
| Explicit controlling assignments restored inactive | HIGH | HIGH | HIGH |

After the first removal, the surviving record's logical readback can follow its on/off writes while D10 remains physically LOW through the independent input. Neither removal order restores control of the old D6 object. Record deletion and mode transitions were separated; cleanup explicitly reinstalls controlling assignments before driving both outputs inactive. These observations qualify the declared artifact, pins, and histories; they do not establish every duplicate-function or floating-pin outcome. They support the existing F07/F17 compatibility limits and do not promote unrelated unresolved fixtures to passing cases.

The emulator's [slot-query path](../../src/engine.cpp) preserves this fallback read/write behavior when a surviving actuator record has lost its live target, while leaving orphaned pin levels unchanged. The original [native regression](../../tests/model.cpp) replays all four observed I2C histories, including both alias writes, both removal orders, fallback readings, and retained physical-pin state. It failed with a missing `v` before the correction and passes afterward. This covers the observed action/reaction; it does not qualify other duplicate-function histories or the unresolved RevC fixture.

## Recorded command observations


| Finding | Physical I2C observation | Compatibility implication |
| --- | --- | --- |
| Identity and inventory | Shield identity is 5; digital outputs enumerate as D5, D6, D2, and D10 after the A0 probes. | Select the emulator's I2C profile for corresponding checks. |
| LCD bytes (`F16`) | Repeated `L` reads contain raw byte `DF` in degree cells, rather than the RevC contract's `B0`. | The emulator exports `DF` for I2C and retains `B0` for RevC; its local displays render both as Unicode `°`. Preserve raw wire bytes instead of assuming UTF-8. |
| Incremental settings (`F01`) | Valid keys before and after an unknown key take effect; `I12` precedes each attempted pair, the unknown key emits `W0`, and the last duplicate key wins. | Settings writes are not atomic transactions. |
| Partial token timeout (`F02`) | `j{Kp:8` without a closing brace applies 8 and returns settings/constants; the captured first response byte arrived after about 1.016 seconds. | Preserve partial application and wall-clock blocking; this one measurement is not a universal timing tolerance. |
| Long-key reuse (`F02`) | A 30-character later key reports its first 29 characters with the previous value; remaining punctuation returns to dispatch and emits `W1`. | Do not substitute strict JSON rejection or discard the whole input. |
| Scalar conversion (`F03`) | Leading-plus and exponent spellings fail conversion without an unknown-key warning; an oversized positive unsigned time clips to 65535, and a negative time leaves it unchanged. `beerFastFilt=257` reads back as 1. | Preserve converter-specific behavior and byte wrapping; extreme signed overflow remains unqualified. |
| Beer patch ownership (`F06`) | A calibration-only beer patch omitting `f` returns `E7`, then `E3`, and retains the original record. With `f=9`, submitted out-of-range ownership becomes chamber 1/beer 1. | Omitted ownership is not conventionally preserved. |
| Calibration sentinel (`F08`) | After setting calibration to 0.5 C, submitting -0.0625 C leaves it at 0.5 C. | Signed-byte -1 collides with the omitted-field sentinel. |
| Discovery leakage (`F09`) | An unassigned last probe has `i=-1` but inherits the preceding chamber record's `t=1,f=5`; unused-only discovery instead reports `t=0,f=0`. | Preserve search order and conditional record leakage. |
| Duplicate records (`F07`) | A second chamber function using the beer probe's ROM is accepted alongside the original records. Duplicate heater-function output records are also accepted. | Stored ROM/function uniqueness is not enforced; acceptance alone does not qualify physical removal history. |
| Zero-ROM probe (`F20`, `F04`) | An all-zero ambient ROM is accepted and wildcard-matches discovery, but `RoomTemp` disappears from telemetry. | Zero ROM does not select the first connected live probe. Physical cable-loss recovery is separate. |
| Device read selectors | A probe still returns its temperature with `r=1,w=0`. | A write selector does not suppress sensor reads as it does actuator reads. |
| Volatile constants (`F05`) | After storing `Kp=7`, `C` shows default 5; restarting restores 7. | Resetting live constants does not necessarily replace saved constants. |
| Intermediate settings save (`F05`) | With a changed mode and `heatEst=0.5`, `S` shows default 0.199; after restart, 0.5 returns. | A settings reset can persist an intermediate snapshot instead of its final displayed defaults. |
| Profile save threshold (`F05`) | A target change from 20 to exactly 20.25 C is visible live but restarts at 20; a change to 20.3125 survives, displayed as 20.31. | The save threshold is strictly greater than 0.25 C. |
| Off-mode no-op | An off-mode target of 21 survives another `mode:o` write, but becomes null on restart. | Already-off mode writes differ from forced mode application during reload. |
| Cold diagnostics (`F13`) | Immediately after restart, captured peak fields in `V` are 48 C, and the other captured values are zero. | These are startup artifacts, not measured peaks or missing-value nulls. |
| Logical outputs | In test mode, each assigned D5/D6/D2/D10 actuator reads logical 1 after a direct on write, and 0 after an off write. | This establishes serial logical behavior, not an electrical pin or LED measurement. |
| Door indication | With D4 grounded, door and light read logical 1, `L` says `Door open`, and `T.State` remains 0 in mode off. Releasing D4 returns both logical values to 0 and restores the ordinary LCD state row; the operator observed the D2 LED change. | Door indication overrides the LCD state without requiring `T.State=2`; the door-driven light can operate while temperature control is off. |
| Removed active output (`F17`) | In a test with separate five-second stages, D6 was activated, its heater assignment was removed while still in test mode, mode was changed to off, and the inactive heater assignment was restored. The operator observed the active indication persist through removal and mode off, changing only at restoration; the reported sequence was HIGH, LOW, HIGH. | Removing an actuator assignment or requesting off mode does not universally clear an orphaned physical pin. Restore a controlling assignment and explicitly drive it inactive before finishing. |

The operator observed all four shield actuator indicators respond during individual five-second logical-on/off tests in the order D5, D6, D2, and D10. This confirms a visible response on this shield, without establishing LED polarity, drive voltage, load capacity, or exact transition timing.

An earlier D6 removal observation was ambiguous because removal and the mode change occurred together, and the operator initially reported a change at removal. The separated-stage repeat is the evidence for `F17`; retain both observations with their command sequences rather than silently discarding the initial response. Those single-record observations are separate from the four independently monitored duplicate histories above; none is a calibrated voltage or electrical-edge timing trace.

## Evidence-backed regression coverage

The I2C identity reply uses the observed `da7e14a9` revision; RevC retains `8f1fa12`, and the default remains RevC. The [profile tests](../../tests/model.cpp) check both complete identities, and the [process tests](../../tests/pacing.py) check them through the public endpoint before and after restart and checkpoint resume. These are emulated firmware identities, separate from the emulator application's own version; matching an identity does not establish installed flash equality.

The original `i2c_observations` regressions in [protocol edges](../../tests/edges.py) cover the following observed facts. They execute the I2C profile through the original [fixture driver](../../tests/driver.cpp), which defaults to RevC and accepts an optional `revc` or `i2c` argument. Synthetic probe identifiers substitute for physical ROMs in the same enumeration/role order, with fixed 20 C inputs. Uncontrolled physical temperatures, temperature-dependent PID values, and USB/host delivery intervals are not copied into numerical expectations. Raw captures and reference implementation remain outside the tests and source package.

| Recorded Arduino facts | Regression ID or location | Qualified assertion |
| --- | --- | --- |
| Complete identity, A0 inventory, D5/D6/D2/D10 order, raw degree byte | `i2c.identity_inventory_degree` | Exact `N` bytes, inventory fields, and `DF` degree cells. The initial physical checker expected `B0`; its retained raw `DF` bytes, rather than that incorrect expectation, establish the I2C fact. |
| Incremental writes, unknown and duplicate keys, partial pair, long-key value reuse | `i2c.incremental_partial_long_key` | Applied values and ordered diagnostics, including returned punctuation. Wall-clock parser waits are separately covered by existing endpoint tests; the captured approximately 1.016-second interval is not a universal tolerance. |
| Plus/exponent conversion failure, unsigned clipping/negative ignore, filter-byte wrap | `i2c.scalar_and_byte_conversions` | The observed converter outcomes; wrapping a stored coefficient does not establish its live filter routing. |
| Beer patch rejection, forced ownership, -1 calibration sentinel | `i2c.ownership_and_calibration` | `E7` before `E3`, retained record, forced `c/b`, and unchanged 0.5 calibration after -0.0625. |
| Discovery field leakage, unused discovery, duplicate ROM/function acceptance, zero ROM, read/write selectors | `i2c.discovery_duplicates_zero_rom_selectors` | Record fields and omitted `RoomTemp`; no physical cable-loss, conversion-latency, or embedded-diagnostic claim. |
| Volatile `C`, intermediate `S` save, strict profile-save threshold, off-mode no-op, cold `V` | `i2c.persistence_cold_values_off_noop` | Live versus restarted values, 20.25 versus 20.3125 target persistence, null targets after forced off reload, and 48 C startup peaks. |
| Logical outputs and separated single-heater removal | `i2c.logical_outputs_and_removed_pin` | Four logical output readings, write-selector precedence, and retained D6 latch across removal and mode off. |
| Duplicate heater replacement and both removal orders | `duplicate_actuator_fallback` in [model tests](../../tests/model.cpp) | All four independently monitored D6/D10 histories, shared live aliases, fallback read/write state, and unchanged orphaned pins. |
| D4 grounded/released, door-driven light, LCD override | `i2c.door_light_and_lcd_override` and [local-control tests](../../tests/controls-core.cpp) | Active-low I2C contact input with `x=1`, light response while off, `T.State=0`, and LCD door indication; both physical door actions and inversion remain effective. |
| Ordinary camera expiry and test-mode retention | `i2c.camera_ordinary_expiry_and_test_retention` | Light on before expiry and off afterward; a request activated in ordinary mode remains on through 615 controller seconds in test mode and expires on returning to ordinary mode. |

The camera evidence consists of two ordinary GPIO expiries observed near 601.8 and 601.0 host seconds and two retained requests followed by ordinary-mode deactivation near 615.2 seconds. The regression uses an ordinary on/off observation window around expiry and the retained test-mode history, without claiming exact AVR comparator or electrical-edge precision from host timestamps.

The default modeled I2C door contact is asserted LOW, matching the recorded D4-to-GND active/open bench convention with device inversion `x=1`. The RevC model retains its previous asserted-HIGH contact wiring, normally used with `x=0`. A modeled physical door action changes its contact level; the firmware inversion flag is then applied separately. This corrects the I2C physical-door/controller disagreement without bypassing inversion, changing serial validation, or changing thermal door state into an electrical-level flag.

## Explicit evidence limits

These regressions qualify the recorded action/reaction above. The partial hand-warming trace does not qualify live filter routing, settling, or slope response. Existing filter, protection-timer, and estimator tests retain their source-defined basis; their presence is not proof of unobserved Arduino behavior. No fixed discovery/conversion delay or fabricated embedded diagnostic is introduced from ordinary connected-probe response intervals.

Single-probe cable-loss recovery, floating/shared-pin electrical effects outside the declared model, exact protection boundaries, missing-peak arithmetic, physical display/rotary behavior, and memory-sensitive cases remain unqualified by this evidence. D11/D12 were measurement inputs on the physical bench, not a claim that the emulator models those loopback jumpers. The nine unresolved RevC fixtures retain their classifications. No new physical session is required or implied by this regression suite, and an unobserved case is not reported as passing.
