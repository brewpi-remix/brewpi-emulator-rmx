# Firmware diagnostic metadata v1

Original MIT specification of interoperability metadata, not copied source enums, diagnostic prose tables, or logger code. The selected ordinary profile logs errors, warnings, and info, with debug-only statements disabled. Version is 3. Records are `D`:{"`logType`":"`I|W|E`","`logID`":integer,"`V`":[arguments]} followed by CRLF. Type and ID jointly identify a message; each type starts its own ID numbering. The pinned host's metadata matches these signatures. Sources: [ID definitions](https://github.com/brewpi-remix/brewpi-firmware-rmx/blob/8f1fa1213cbbfc1f987fada5168d01925e1a2ee8/src/LogMessages.h#L49), [wire logger](https://github.com/brewpi-remix/brewpi-firmware-rmx/blob/8f1fa1213cbbfc1f987fada5168d01925e1a2ee8/src/Logger.cpp#L42), and [host metadata](https://github.com/brewpi-remix/brewpi-script-rmx/blob/d183fb5319b928f78b4c0eb6f05fe3620610ffff/LogMessages.h#L49).

## Required reachable mapping

| Type/ID | Behavioral event, independently described | Ordered `V` arguments |
| --- | --- | --- |
| `E0` | Sensor allocation failure. | `[ROM string]` |
| `E2` | Device allocation failure at the guarded installation point. | `[function integer]` |
| `E3` | `U` configuration validation fails after any specific validator diagnostic. | `[]` |
| `E4` | A stored device's chamber exceeds the EEPROM validator's inclusive 0–4 range during reload. `U` normally overwrites submitted ownership first. | `[chamber integer]` |
| `E5` | A stored device's beer exceeds the EEPROM validator's inclusive 0–6 range during reload. `U` normally overwrites submitted ownership first. | `[beer integer]` |
| `E6` | Patched device function lies outside 0–15. | `[function integer]` |
| `E7` | Patched owner/function combination fails validation. | `[owner integer, beer integer, chamber integer]` |
| `E8` | Device function type cannot use the hardware kind. | `[type integer, hardware integer]` |
| `E9` | A OneWire assignment uses a non-OneWire pin. | `[pin integer]` |
| `E10` | The object reader does not receive an opening brace. | `[received byte integer, -1 for no byte after the read wait]` |
| `W0` | A full `j` setting name does not match any converter. | `[]` |
| `W1` | Dispatch receives an unsupported byte. | `[command byte as AVR char-promoted integer]` |
| `W2` | A probe's connected flag changes to disconnected. | `[pin integer, ROM string]` |
| `W3` | EEPROM settings are absent or have the wrong version. | `[]` |
| `I0` | A previously disconnected probe becomes connected. | `[pin integer, ROM string]` |
| `I12` | A nonempty `j` key/value pair is about to be handled, even if unknown or conversion subsequently fails. | `[tokenized key string, tokenized value string]` |
| `I13` | Default constants have been loaded and `C` emitted. | `[]` |
| `I14` | Default settings have been loaded and `S` emitted. | `[]` |
| `I15` | `E` initialization has run, before subsequent settings reload. | `[]` |
| `I17` | A positive extremum was recognized by peak processing. | `[observed absolute temperature string, predicted absolute temperature string, previous estimate string, new estimate string]` |
| `I18` | A negative extremum was recognized. | Same four string categories as `I17`. |
| `I19` | The positive-drift timeout path reports an outcome. | Same four string categories; see sentinel-derived error finding `F15`. |
| `I20` | The negative-drift timeout path reports an outcome. | Same four string categories; see `F15`. |

Temperature-string diagnostic arguments use one decimal and current display units; estimate strings use three decimals in unscaled fixed-point numbers. Preserve the logger's leading positive numeric padding inside these strings. Integer arguments are JSON numbers. `I12` reflects token-reader transformations: literal spaces and quote characters were removed; escapes were not decoded. Do not normalize number spelling or replace text with parsed numeric values. The firmware does not escape every diagnostic string.

## Defined but normally unreachable or disabled metadata

`E1` takes a pin integer, `E11` no arguments, `E12` a conflicting-slot integer, and `E13` a conflicting-slot integer. `E12`/`E13` have no implemented uniqueness check and must not be invented as duplicate-rejection messages. `E1`/`E11` are declared without a normal active call in the reviewed paths. `E4`/`E5` are normalized away on normal `U` input but remain active on saved-device reload, which does not call `FORCE_DEVICE_DEFAULTS`. `W4` and `I21` are fallback-sensor metadata without a selected fallback implementation. `W5` and `I22` take a ROM string for disabled DS2413 support. These facts are recorded to avoid assigning a plausible-looking existing ID to a new emulator failure.

Info IDs 1–11 are debug/declared installation bookkeeping; `I2`'s signature is [pin integer, ROM string, absolute temperature string], `I3–9` each carry a function integer, `I10` a slot integer, and `I11` a value integer. `I2–6`/`I9`/`I10` have debug-guarded active call sites; `I7`/`I8`/`I11` are declared without an active selected-profile call. Do not emit any merely because a record is installed. `I1` is declared sensor-disconnect info with [pin, ROM], but the active transition path uses `W2`. `I16` is EEPROM debug-erase info, but `Z` is disabled. Do not copy their format strings. A newly constructed connected probe starts connected=`true`, so a successful initial `U`/`h` probe initialization normally produces no `I0`; `I0` is a reconnection transition. Source: [sensor constructor](https://github.com/brewpi-remix/brewpi-firmware-rmx/blob/8f1fa1213cbbfc1f987fada5168d01925e1a2ee8/src/OneWireTempSensor.h#L50).

## Ordering and failure policy

Successful `j`: `I12` before each handled pair, any setter `T` annotation at the source callback point, then `S` and `C`. Unknown name: `I12`, `W0`, then continue; known invalid conversion usually gets `I12` alone before final readbacks. A malformed opening brace produces `E10` but `receiveJson` still sends `S`/`C`. A normal `U` success produces `U` without an extra success diagnostic/`T`; failed validation produces its first applicable specific `E`, then `E3`, then old `U`. Negative/missing `U` indices are silently ignored before validation. Do not replace this with atomic-rejection messages, success-only `I12`, or a single-error policy.

The `E3` cascade is specific to the `U` caller. On boot/reload, failed stored-device validation emits the applicable `E4`/`E5`/`E6`/`E7`/`E8`/`E9` directly and clears that slot; it does not append `E3` or `U`. Output after `R` belongs to the reboot observation phase, not an immediate acknowledgment. The fixtures include explicit restart-completion barriers before later readback commands. Source: [reload caller](https://github.com/brewpi-remix/brewpi-firmware-rmx/blob/8f1fa1213cbbfc1f987fada5168d01925e1a2ee8/src/EepromManager.cpp#L124).

`C` orders `C` then `I13`; `S` orders `S` then `I14`; `E` emits `I15` after initialization, with any later reload diagnostics following it. Boot safe mode emits `W3`. I/O/host-storage failures are not Arduino diagnostic conditions and have no assigned invented version-3 ID; report them outside the serial protocol and do not claim a controller acknowledgment the reference does not provide. Diagnostics may occur while a reply list is open; host filtering already accounts for that stream structure.

[Original diagnostic vectors](test-vectors/diagnostics-v1.json) record numeric metadata and representative argument types for all 43 defined type/ID combinations, including reachability/guard labels. They contain no upstream expansion text. Metadata-vector coverage is not evidence that every runtime path was executed. Source-defined reachable diagnostics must be matched; hardware-allocation and undefined drift-path outcomes remain separately characterized in the findings register.
