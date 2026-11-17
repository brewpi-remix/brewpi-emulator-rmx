# Implementation

Original C++17 implementation under MIT. See [architecture](../engineering/architecture.md), [protocol reference](../engineering/protocol/README.md), and [source build instructions](../docs/development.md).

Serial parsing follows the selected firmware's byte semantics; native scenario/store/checkpoint JSON is a separate interface. The external thermal model does not introduce controller policy. The local viewer does not consume serial traffic, and local confirmation rules do not tighten serial acceptance.

[Profile definitions](profile.hpp) select the Uno shield identity, OneWire bus, output discovery order, and default equipment wiring. RevC remains the constructor and CLI default; I2C is explicit. Saved profile tags prevent cross-profile store/checkpoint interpretation, with untagged legacy files interpreted as RevC.
