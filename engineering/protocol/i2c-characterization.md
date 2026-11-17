# Uno I2C firmware characterization

This reference describes observations of the physical Uno I2C personality reporting `v=0.2.13`, `n=da7e14a9`, `s=5`, `y=0`, `b=s`, and `l=3`, using 57600-baud USB serial and three powered OneWire probes on A0. These are independently described interoperability facts, not imported firmware implementation or raw fixtures. The owner's setup uses I2C rather than RevC; these observations do not automatically qualify the pinned RevC fixtures or every I2C build.

The separately retained candidate `brewpi-arduino-uno-i2c-0.2.13+da7e14a9.hex` has SHA-256 `ccf240909702618815864633071e4f1b9e4dba32805241a4f9346b96afdb69ca`. Its name matches the running identity; flash contents have not been read back and compared, so this hash alone does not prove the installed bytes or exact compiler inputs.

## LCD degree byte

Repeated `L` reads from this identified I2C artifact contain raw byte `DF` in the degree cells. RevC retains its source-defined raw byte `B0`. The emulator exports the selected profile byte unchanged on serial, while its local graphical and terminal adapters render either byte as Unicode `°`.

The regression checks cover both profiles, Celsius and Fahrenheit, configuration/default resets, controller restart, checkpoint continuation, and exact serial LCD bytes. These checks do not qualify physical LCD rendering, rotary behavior, or the nine unresolved RevC characterization cases. No firmware implementation, binary, raw capture, generated table, test, or asset is incorporated into the MIT emulator.
