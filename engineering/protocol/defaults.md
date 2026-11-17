# Firmware defaults and units

Original MIT defaults and [machine-readable data](test-vectors/defaults-v1.json) for the normal Uno/RevC profile in the [behavioral contract](behavioral-contract.md).

The `i2c` profile uses the same numeric/control defaults and synthetic probe ROMs, with bus pin `14`, output inventory 5, 6, 2, 10, and default virtual heater/cooler/light/fan pins 6/5/2/10. Explicit scenario loads override these physical defaults. Profile selection does not simulate an electrical LCD bus; see the [profile table and persistence rules](../../docs/operation.md#connect-brewpi-remix).

## Numeric categories and representation

The controller uses signed 16-bit temperatures/factors with 512 internal units per degree and a temperature offset: absolute `C` = raw/512 + 48. Raw -32768 and -32767 are invalid/disabled absolute-temperature sentinels and print `null`. Other raw values are data, so zero-initialized absolute peak variables print 48 C rather than `null`. Difference/factor values have no offset. Output positive numeric text has a leading space; negative text has a minus sign. Rounding occurs at the firmware's fixed-point and final decimal stages. JSON semantic comparisons preserve number-versus-string/`null` types; explicit byte vectors additionally preserve padding and framing. Sources: [formats](https://github.com/brewpi-remix/brewpi-firmware-rmx/blob/8f1fa1213cbbfc1f987fada5168d01925e1a2ee8/src/TemperatureFormats.h#L46) and [formatting](https://github.com/brewpi-remix/brewpi-firmware-rmx/blob/8f1fa1213cbbfc1f987fada5168d01925e1a2ee8/src/TemperatureFormats.cpp#L46).

| Category | `C/F` behavior | Fields |
| --- | --- | --- |
| Absolute | Offset and scale conversion, including AVR fixed-point rounding, before decimal output. | `T` measurements/setpoints; `S` `beerSet`/`fridgeSet`; `C` `tempSetMin`/`tempSetMax`; `V` `estPeak`/`negPeakEst`/`posPeakEst`/`negPeak`/`posPeak`; device temperature `v`. |
| Difference/rate | Scale by the `C/F` ratio without an absolute offset, with fixed-point rounding. | `C` `pidMax`/`iMaxErr`/`idleRangeH`/`idleRangeL`/`heatTargetH`/`heatTargetL`/`coolTargetH`/`coolTargetL`; `V` `beerDiff`/`diffIntegral`/`beerSlope`; calibration `j`. |
| Unscaled number | Raw fixed-point number unchanged by display units. | `S` `heatEst`/`coolEst`; `C` `Kp`/`Ki`/`Kd`; `V` `p/i/d`. |
| Character/integer | No temperature conversion. | `mode`/`tempFormat`, filters, flags, indices, times, and states. |

All `S`/`C` fields are writable `j` names, but their converters differ. Processing is sequential; a `tempFormat` write affects subsequent values in the same object and stores the already-mutated current configuration. Duplicates are processed repeatedly. Mode/`tempFormat` take the first character without an enum check. Numeric converters do not enforce gain/temperature/filter bounds; do not add them. Null absolute setpoints are supported. A failed known converter usually leaves its target unchanged without a warning; unknown names get `W0` after `I12`. Gains/estimates can be negative where the source converter permits it. Source: [converter mapping](https://github.com/brewpi-remix/brewpi-firmware-rmx/blob/8f1fa1213cbbfc1f987fada5168d01925e1a2ee8/src/PiLink.cpp#L922).

Fixed-point scalar conversion rejects leading plus/exponent text, but follows the source's custom minus/digit handling rather than a stricter JSON numeric parser. Values are constrained to raw -32766 through 32767 when that converter calls for it, reserving the two lower `int16` values for invalid/disabled temperature sentinels. Unsigned time input clips above 65535; negative time input is ignored. Filter input uses `atol` narrowed to `uint8`. Flag input accepts `true`/`false`, otherwise integer narrowing occurs before 0/1 acceptance, so 256 can behave as 0. Extreme arithmetic/overflow and malformed long tokens are characterization cases in [findings](firmware-findings.md), not newly rejected schema errors. Source: [numeric converters](https://github.com/brewpi-remix/brewpi-firmware-rmx/blob/8f1fa1213cbbfc1f987fada5168d01925e1a2ee8/src/TemperatureFormats.cpp#L117).

## `S` factory values

| Key | Saved/raw fact | `C` and `F` wire value/type |
| --- | --- | --- |
| `mode` | Normal default off. | String `o`. |
| `beerSet` | Disabled raw -32767. | `null`. |
| `fridgeSet` | Disabled raw -32767. | `null`. |
| `heatEst` | Raw 102, formed by integer division for the nominal 0.2 estimate. | Number 0.199, three decimals. |
| `coolEst` | Raw 2560. | Number 5.000, three decimals. |

Beer/fridge targets use two decimals when valid. The same factory live values can have different saved EEPROM values after `S` because `S`'s mode setter can persist before the later default assignments. `E` writes final defaults and initialized slots. Source: [settings defaults and storage](https://github.com/brewpi-remix/brewpi-firmware-rmx/blob/8f1fa1213cbbfc1f987fada5168d01925e1a2ee8/src/TempControl.cpp#L595).

## Complete `C` factory values

The F column is actual fixed-point-format output, not a decimal multiplication of the `C` display string. Factor/difference/absolute categories match the source output handlers. JSON values are numeric except `tempFormat`; integer rows stay integers.

| Key | Internal/raw default | `C` wire | F wire | Category |
| --- | --- | --- | --- | --- |
| `tempFormat` | `C` initially. | `C` | `F` | String, selected unit rather than two simultaneous defaults. |
| `tempSetMin` | `-24064` | `1.0` | `33.8` | Absolute, one decimal. |
| `tempSetMax` | `-9216` | `30.0` | `86.0` | Absolute, one decimal. |
| `pidMax` | `5120` | `10.000` | `18.000` | Difference, three decimals. |
| `Kp` | `2560` | `5.000` | `5.000` | Unscaled, three decimals. |
| `Ki` | `128` | `0.250` | `0.250` | Unscaled, three decimals. |
| `Kd` | `768` | `1.500` | `1.500` | Unscaled, positive default despite the nearby source comment. |
| `iMaxErr` | `256` | `0.500` | `0.900` | Difference. |
| `idleRangeH` | `512` | `1.000` | `1.801` | Difference. |
| `idleRangeL` | `-512` | `-1.000` | `-1.801` | Difference. |
| `heatTargetH` | `154` | `0.301` | `0.541` | Difference. |
| `heatTargetL` | `-102` | `-0.199` | `-0.359` | Difference. |
| `coolTargetH` | `102` | `0.199` | `0.359` | Difference. |
| `coolTargetL` | `-154` | `-0.301` | `-0.541` | Difference. |
| `maxHeatTimeForEst` | `600` | `600` | `600` | Integer seconds. |
| `maxCoolTimeForEst` | `1200` | `1200` | `1200` | Integer seconds. |
| `fridgeFastFilt` | `1` | `1` | `1` | Integer byte. |
| `fridgeSlowFilt` | `4` | `4` | `4` | Integer byte. |
| `fridgeSlopeFilt` | `3` | `3` | `3` | Integer byte. |
| `beerFastFilt` | `3` | `3` | `3` | Integer byte. |
| `beerSlowFilt` | `4` | `4` | `4` | Integer byte. |
| `beerSlopeFilt` | `4` | `4` | `4` | Integer byte. |
| `lah` | `0` | `0` | `0` | Integer flag. |
| `hs` | `0` | `0` | `0` | Integer flag; rotary hardware has no physical emulation initially. |

Sources: [constant defaults](https://github.com/brewpi-remix/brewpi-firmware-rmx/blob/8f1fa1213cbbfc1f987fada5168d01925e1a2ee8/src/TempControl.cpp#L744), [output fields](https://github.com/brewpi-remix/brewpi-firmware-rmx/blob/8f1fa1213cbbfc1f987fada5168d01925e1a2ee8/src/PiLink.cpp#L575), and [C/F fixed-point conversion](https://github.com/brewpi-remix/brewpi-firmware-rmx/blob/8f1fa1213cbbfc1f987fada5168d01925e1a2ee8/src/TemperatureFormats.cpp#L250).

## `V` and initial live state

`V` has `beerDiff`, `diffIntegral`, `beerSlope`, `p`, `i`, `d`, `estPeak`, `negPeakEst`, `posPeakEst`, `negPeak`, and `posPeak`. On a cold controller start its raw static values are all zero. The first six serialize as 0.000; the five absolute peak values serialize as 48.0 C or 118.4 F, not `null`. Later invalid peak sentinels can serialize as `null`. `V` difference/factor fields use three decimals and absolute peaks one decimal. `S`/`C`/`E` do not promise to erase stale diagnostics. Off or missing-sensor mode does not introduce an extra `V`-clearing action. Source: [static diagnostics](https://github.com/brewpi-remix/brewpi-firmware-rmx/blob/8f1fa1213cbbfc1f987fada5168d01925e1a2ee8/src/TempControl.cpp#L64) and [V serializers](https://github.com/brewpi-remix/brewpi-firmware-rmx/blob/8f1fa1213cbbfc1f987fada5168d01925e1a2ee8/src/PiLink.cpp#L625).

`diffIntegral` is a signed 32-bit internal accumulator, but `V`'s generic difference handler reads only a signed 16-bit word at that field's address. On the selected little-endian AVR this is the low word; do not serialize the full accumulator as a corrective change. For raw `diffIntegral=66048`, the visible raw word is 512, so `V` reports 1.000 C or 1.801 F while the internal accumulator remains 66048. All other `V` field widths follow their declared source types. Finding `F21` and its original vector distinguish internal state from this narrowed telemetry. Sources: [accumulator type](https://github.com/brewpi-remix/brewpi-firmware-rmx/blob/8f1fa1213cbbfc1f987fada5168d01925e1a2ee8/src/TempControl.h#L86) and [16-bit output handler](https://github.com/brewpi-remix/brewpi-firmware-rmx/blob/8f1fa1213cbbfc1f987fada5168d01925e1a2ee8/src/PiLink.cpp#L532).

Default automatic state is idle 0; disabled targets override the intermediate off state. Default hardware is unassigned, with fallback sensors/actuators. The physical inventory exists independently of saved slot state. A new erased store enters `W3` safe mode; `E` initializes EEPROM version 4 and 16 empty slots. Fixture preset `initialized` is a constructed initialized reference state with zero controller time, unchanged cold `V`, and a rendered default LCD, not a claim that physical startup finishes at wall second zero. Fixture preset `assigned` means its records were already installed with filters initialized from the declared temperatures; it is not a different factory default. The dataset's explicit controller preconditions and fixture-format guide define saved/live state, histories, timestamps, and reset barriers.

## Virtual external environment

The default instance ID is `chamber1`, with three explicitly configured synthetic DS18B20-family ROMs and their fixed search order in [defaults-v1.json](test-vectors/defaults-v1.json). They were independently selected and given CRC-8/MAXIM-DOW check bytes through one-off fixture arithmetic, not obtained from real sensors or a copied OneWire routine. Other instances require their own fixed ROM set; identities remain stable through controller reset. A zero-address assignment is accepted and wildcard-matched during inventory lookup, but its live read follows the literal zero-ROM selection; see finding `F20`. The EEPROM-like store and external hardware identity configuration are distinct.

Physical load wiring is pin 5 heater at 25 W, pin 6 cooler at 60 W, pin 2 light at 0 W, and pin 19 fan at 0 W. Loads are active-low, consistent with discovered `x=1`; door pin 4 begins closed and is available for direct configuration but not enumerated by the selected sensor-pin setting. Do not force a physical load off just because its old function was removed if the firmware leaves that pin's electrical latch unchanged; the hardware model follows the electrical state. Shared fallback actuators can have live logical state without any physical pin. Unknown digital pins require a declared virtual electrical disposition without a new firmware validation error.

The independent plant begins beer/chamber/room at 20 C, with 18.927 L beer, density 1000 kg/m³, specific heat 4180 J/(kg·K), carboy capacity 6000 J/K, chamber volume 400 L, cabinet capacity 2000 J/K, and air volumetric capacity 1210 J/(m³·K). Beer/carboy capacity is 85114.86 J/K and chamber air/cabinet capacity 2484 J/K. Conductance is 3 W/K beer-to-chamber and 1.67 W/K chamber-to-room. Baseline room is fixed 20 C, probe noise is zero, probe lag is zero, quantization is 0.0625 C, and random seed is 1. These describe emulated external physics, not invented firmware control changes or measurements of a real refrigerator.

Baseline fermentation heat is off. The independent active-fermentation environment has maximum 5 W, age 0, zero heat through 8 hours, linear rise to maximum at 20 hours, maximum through 44 hours, linear decay to zero at 92 hours, then zero. This is a declared external scenario, not the Arduino simulator build, whose bugs remain documented separately and whose serial dialect is not selected. An optional daily room curve has a 24-hour simulated period with explicit configured phase; none is enabled by default.

Clock starts at zero with speed 1. Controller seconds use the reference 16-bit observable width; plant age can use a wider independent clock. Minimum heat/cool off times are 300 s, minimum heat/cool on thresholds 180 s with strict greater-than release, opposite-direction switch 600 s, fridge-constant cool off 600 s, positive peak timeout 900 s, and negative peak timeout 1800 s. Preserve the source's boundary and timer-update order; do not replace them with rounded human expectations. Fixtures pause unsolicited ticking and introduce explicit tick/evaluation events where needed. Source: [normal timing constants](https://github.com/brewpi-remix/brewpi-firmware-rmx/blob/8f1fa1213cbbfc1f987fada5168d01925e1a2ee8/src/TempControl.h#L43).
