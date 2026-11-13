# BrewPi emulator planning handoff

Historical snapshot: the handoff below records the original planning request before Git initialization. The public [brewpi-remix/brewpi-emulator-rmx](https://github.com/brewpi-remix/brewpi-emulator-rmx) repository and local `main` now exist, with HTTPS `origin` configured; the owner has authorized the initial plan/scaffolding commit and push. The [project contract](CONTRACT.md) and [revised plan](IMPLEMENTATION_PLAN.md) supersede the original code-reuse suggestion with independent MIT implementation requirements. Emulator implementation remains unapproved.

We are starting brewpi-emulator-rmx: a native C++ emulator that runs on the same Raspberry Pi/Linux machine as BrewPi and replaces the Arduino for hardware-free integration testing.

Begin by reviewing the local repositories and creating a concrete implementation plan. Do not implement yet. Read SETUP.md for the repository inventory and preparation completed on 2026-11-13.

## Local repositories

- /Users/lbussy/GitHub/brewpi-emulator-rmx — the new application and planning destination.
- /Users/lbussy/GitHub/brewpi-firmware-rmx — authoritative reference for Arduino behavior, serial protocol, device configuration, and existing thermal simulation.
- /Users/lbussy/GitHub/brewpi-script-rmx — the actual host client used to establish compatibility.
- /Users/lbussy/GitHub/brewpi-www-rmx — existing web control panel and device configuration workflows.
- /Users/lbussy/GitHub/brewpi-tools-rmx — installation and service conventions.
- /Users/lbussy/GitHub/brewpi-userdocs-rmx — existing operator documentation.
- /Users/lbussy/GitHub/fuscus — historical Python implementation for reference; do not assume current compatibility.

Read applicable AGENTS.md instructions, inspect branches and working-tree state, and preserve unrelated changes. Verify current source rather than relying on the earlier discussion. The project directory contains handoff documentation only and has not been initialized as a Git repository.

## Objective

Run BrewPi and its external control panel without an Arduino, physical temperature sensors, relays, heater, or refrigerator. The emulator must respond plausibly to control changes so the panel can display and exercise the system.

## Requirements

1. Implement the emulator as a native C++ Linux application suitable for Raspberry Pi.
2. Expose a pseudo-terminal through a stable configurable path that BrewPi can open as its serial port. Actual USB enumeration is not required.
3. Reproduce the Arduino serial protocol sufficiently to support startup, normal monitoring, control changes, device discovery and assignment, and relevant configuration workflows.
4. Expose stable firmware/controller identity, device IDs, and sensor serial numbers/OneWire addresses as expected by the host and panel. Determine the exact fields and formats from source.
5. Distinguish protocol identity from USB metadata. A pseudo-terminal does not provide USB VID/PID or USB serial descriptors. Identify any discovery assumptions and propose the smallest necessary configuration or integration change.
6. Simulate a fermentation chamber containing a carboy with five US gallons of beer, approximately 18.9 liters. Track beer, chamber, and surrounding-room temperatures separately.
7. Model fermentation heat generated in the beer, heat transfer between beer and chamber, heat loss/gain between chamber and room, and heating/cooling effects. Include enough thermal mass and lag to produce believable behavior.
8. React to setpoints, control modes, device assignments, and heater/cooler states. Temperatures must evolve from the thermal model rather than follow a canned trace.
9. Reuse the firmware PID, filtering, and heating/cooling state machine where practical. The objective is reactive integration testing, not PID qualification or exact reproduction of a particular refrigerator.
10. Evaluate the existing firmware simulator before designing a replacement thermal model. Fuscus may provide reference material, but do not assume it is current or protocol-complete.
11. Support persistent configuration, stable identities across restarts, repeatable initial conditions, and an optional accelerated simulation clock.
12. Keep the initial implementation hardware-free.

## Planning work

- Inventory the host-to-controller commands, response framing, identity fields, device schemas, startup sequence, timing expectations, and unsolicited messages.
- Trace which identities and discovery mechanisms the actual host and control panel consume. Review brewpi-www-rmx as the available panel reference; identify any additional external panel that needs clarification.
- Assess which firmware components can compile natively and which Arduino dependencies need adapters. Check licensing and attribution obligations for reused source.
- Propose boundaries between the controller core, thermal model, simulation clock, serial transport, device registry, and persistence.
- Explain real-time versus accelerated-time behavior, including how acceleration interacts with host-side fermentation profiles and timestamps.
- Identify compatibility gaps, assumptions, and questions requiring user input.
- Propose bounded milestones and meaningful integration checks.

## Initial acceptance scenario

Start the emulator, configure BrewPi to use its serial path, discover and assign simulated sensors and actuators, change a beer setpoint through the normal panel, and observe plausible temperatures and heating/cooling states over time. Restart the emulator and verify that configured identities and settings persist.

## Deliverable and stopping point

Deliver a concise source-backed review and save an implementation plan in this project using its established documentation conventions. Include acceptance criteria, proposed dependencies/build approach, and material risks. Distinguish source review from behavior actually verified by execution. Write each prose paragraph and each prose list item on one physical line, separating paragraphs with blank lines.

Stop after the plan for review. Do not begin implementation, initialize Git, commit, push, publish, install software on a Pi, or change the reference repositories during this planning stage.
