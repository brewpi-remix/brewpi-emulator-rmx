# Milestone 3 development operation

Milestone 3 adds the controller/filter/thermal loop and clock to the reviewed transport/registry/persistence foundation. This is a development implementation for review, not a release or physical-controller qualification. All 48 source-defined reviewed cases pass; the nine reference-characterization cases remain unresolved. Existing host/panel integration is recorded separately in the [milestone 4 guide](milestone-4.md).

## Build and validate

Use CMake 3.16+, a C++17 compiler, and Python 3.9+ for the standard-library test clients. No external JSON, controller, or physics library is downloaded or incorporated.

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build -j 4
ctest --test-dir build --output-on-failure
```

```sh
cmake -S . -B build-sanitize -DCMAKE_BUILD_TYPE=Debug -DRMX_SANITIZERS=ON
cmake --build build-sanitize -j 4
ctest --test-dir build-sanitize --output-on-failure
```

The six suites cover reviewed protocol fixtures, legacy regression/PTY behavior, independent filter arithmetic, controller/physical energy/clock behavior, and actual process pacing/resume. Reports remain in the invoking build directory's ignored test-results directory. The [review](../engineering/development/milestone-3-review.md) records exact environments, results, and limits.

## Isolated operation

Use private paths and an explicit serial port rather than a working BrewPi installation:

```sh
./build/brewpi-emulator-rmx --serial "$PWD/runs/chamber1/serial" --state "$PWD/state/chamber1/controller.json"
```

The default is speed 1. A new store emits W3 safe mode; E initializes it, and normal h/U commands discover and assign the original three probes and four load pins. The normal controller runs automatically. Query t/v/l to see current measurements, control diagnostics, and the retained LCD bytes. Mode and target writes retain firmware annotations, persistence quirks, and callback order. No USB reset/descriptors, service installation, host configuration change, or physical GPIO access is performed.

--speed 10 or --speed 60 changes wall pacing. --speed 0 pauses scheduled controller/plant time; serial commands still execute their synchronous actions, and partial-token waits still expire on wall time. The accepted pacing range is 0..1000, but measured qualification is limited to the environments and factors in the review. A larger speed never changes the fixed 100 ms physical step, one-second controller eligibility, source thresholds, or filter arithmetic. Accelerated runs do not accelerate the real host's wall-clock profiles, serial deadlines, chart dates, or logs.

The stable serial path and state ownership/cleanup rules in the [milestone 2 guide](milestone-2.md) remain applicable. Tests that require the controlled milestone 2 observation windows run the process paused. Ordinary production ticking can legitimately generate transition T frames and diagnostics.

## External scenarios

--scenario PATH reads an original JSON scenario without changing the file or creating an adjacent lock. Omitted fields use the reviewed baseline: three temperatures initially 20 C; five US gallons of beer; capacities 85114.86 and 2484 J/K; conductances 3 and 1.67 W/K; fixed loads on pins 5/6/2/19; no fermentation, noise, or probe lag. The fixed synthetic identities belong to the single supported chamber1 personality. Unknown scenario fields, alternate instance IDs without configured hardware identities, nonfinite/negative physical parameters, invalid load maps, or thermal parameters too stiff for the fixed step are environment errors outside serial.

The [active fermentation example](../config/active-fermentation.json) enables the reviewed 0/8/20/44/92-hour curve with a 5 W maximum. fermentation_age_hours can select another initial fermentation age for a repeatable scenario. The [room-cycle example](../config/room-cycle.json) sets a 2 C daily room amplitude and explicit phase, plus optional extra door conductance. With a room cycle, initial_temperatures_c.room is the mean boundary, and the explicit phase determines its initial instantaneous value. Door changes affect the physical conductance independently of whether a logical door sensor is assigned.

Other supported fields follow the reviewed external_scenario names for capacities, conductances, initial temperatures, physical loads, probe_quantization_c, probe_lag_seconds, noise_amplitude_c, random_seed, door_pin, and door_open. speed_factor supplies pacing only when --speed is absent. Quantum, lag, and bounded deterministic noise are external sensor behavior, separate from the firmware's cascaded filtering and calibration. Firmware functions route electrical signals to fixed physical pins; changing a logical heater's pin does not relocate the 25 W physical heater.

## Reboot and checkpoint semantics

R recreates controller volatile state, clocks, counters, and histories while preserving the physical plant/age and the saved firmware-like configuration. E preserves the reviewed subset of V/history/latches, clears slots, and writes defaults. A process restart without --resume starts the scenario's fresh external plant and loads only firmware-saved settings/slots. This distinction is deliberate and is tested.

```sh
./build/brewpi-emulator-rmx --serial "$PWD/runs/chamber1/serial" --state "$PWD/state/chamber1/controller.json" --checkpoint "$PWD/state/chamber1/checkpoint.json"
```

SIGINT/SIGTERM requests a checkpoint at the current logical simulation boundary. It includes live versus saved state, clocks and fractional pending time, sensor/filter histories and counters, peaks, latches/pins, display shadow and timer, plant/lag/random state, scenario, and pacing fraction. It requires a completed command and drained serial output; otherwise the process reports an environment error and retains the previous checkpoint. A checkpoint is not a saved host connection or raw serial backlog.

```sh
./build/brewpi-emulator-rmx --serial "$PWD/runs/chamber1/serial" --state "$PWD/state/chamber1/controller.json" --resume "$PWD/state/chamber1/checkpoint.json" --checkpoint "$PWD/state/chamber1/checkpoint.json"
```

Resume adds no stopped wall time, reinitializes no sensor histories, and does not silently mix a snapshot with subsequently changed saved controller configuration. A missing state file is initialized from a validated snapshot; an existing state file must match its saved configuration. --scenario cannot override a resumed physical history. --speed may override resumed pacing, including 0 for paused inspection. Native checkpoint corruption is an environment error, not an Arduino diagnostic. Partial/invalid snapshots are rejected without changing the running engine or rolling back the controller store.

## Qualification limits

The nine reviewed memory/bus/arithmetic characterization cases and additional undefined filter-shift or signed-overflow paths have no fabricated passing oracle. Detected unsafe paths halt outside serial instead of performing native undefined writes/shifts or inventing controller errors. Actual OneWire conversion latency, nested diagnostic placement, complicated duplicate-target/electrical-contention histories, and exact reference-artifact overflow outcomes remain unqualified. The virtual disconnection tests validate controlled model transitions, not physical bus timing. Thermal plausibility, native tests, and sanitizers do not establish physical Arduino or Pi parity. The owner authorized committing and pushing the reviewed milestone 3 implementation, tests, and documentation to main. Actual host/panel workflows, Pi installation, and releases remain outside this milestone task.
