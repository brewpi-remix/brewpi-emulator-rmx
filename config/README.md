# Scenario configuration

Pass a JSON file with `--scenario PATH`. Unknown fields, invalid physical parameters, and input/output path aliases are rejected. Omitted fields use the built-in defaults. Inputs are read without modification. A scenario sets external equipment/initial conditions; it does not change firmware constants or replace a resumed checkpoint history.

The source tree includes [active-fermentation.json](active-fermentation.json) and [room-cycle.json](room-cycle.json). For a standalone binary, create a scenario file, for example:

```json
{
  "initial_temperatures_c": {"beer": 20, "chamber": 20, "room": 22},
  "fermentation_enabled": true,
  "random_seed": 1
}
```

## Fields

| Field | Meaning and units |
| --- | --- |
| `initial_temperatures_c` | Object with `beer`, `chamber`, and `room` initial temperatures in degrees Celsius. |
| `beer_liters` | Beer volume in liters; default five US gallons, approximately 18.927 liters. |
| `beer_density_kg_per_m3`, `beer_specific_heat_j_per_kg_k` | Beer density and specific heat. |
| `carboy_capacity_j_per_k` | Carboy heat capacity. |
| `chamber_liters`, `air_capacity_j_per_m3_k`, `cabinet_capacity_j_per_k` | Chamber air volume, volumetric heat capacity, and cabinet heat capacity. |
| `beer_chamber_conductance_w_per_k`, `chamber_room_conductance_w_per_k` | Thermal coupling between beer/chamber and chamber/room. |
| `physical_loads` | Array of objects with `pin`, `kind` (`heater`/`cooler`/`light`/`fan`), nonnegative `watts`, and `active_low`. The `cooler` kind removes heat; other kinds add it. Pin assignments must be unique. |
| `probe_quantization_c`, `probe_lag_seconds`, `noise_amplitude_c` | Probe quantization, lag, and noise magnitude. |
| `random_seed` | Deterministic pseudo-random seed. |
| `room_daily_amplitude_c`, `room_daily_phase_hours` | Daily room-temperature sinusoid amplitude and phase. |
| `door_pin`, `door_open`, `door_extra_conductance_w_per_k` | Modeled door input and added heat transfer when open. |
| `fermentation_enabled`, `fermentation_age_hours` | Enable fermentation heat and set its initial age. |
| `active_fermentation_profile` | Object with `maximum_watts` and `breakpoints_hours_watts`, an ordered array of `[hours, watts]` pairs. At least two points are required, hours must increase, and the final power must be zero. |
| `instance_id` | Hardware identity profile; `chamber1` is the supported value. |
| `speed_factor` | Initial simulation pacing factor; `--speed` overrides it. |

Use separate files/directories for scenarios, controller stores, checkpoints, PTY links, and locks. Repeatability requires the same configuration, seed, and input/event history. Host profiles and chart timestamps remain wall-clock based.

Examples and scenario documentation are original MIT work. See [model details](../engineering/protocol/controller.md) for arithmetic, defaults, and checkpoint behavior.
