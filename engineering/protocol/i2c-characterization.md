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
