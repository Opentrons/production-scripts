# Productions Hardwares

The `productions-hardwares` application contains the production hardware executable and all hardware-facing code:

- `src/devices`: device implementations
- `src/drivers`: serial, SSH, socket, sound, and protocol drivers
- `src/cli`: application entry points, argument parsing, prompts, and terminal UI
- `src/opentonrs_api`: robot HTTP, maintenance, protocol, and hardware-control APIs
- `src/gravimetric_testing`: gravimetric utilities
- `src/leveling_testing`: leveling test workflows, fixtures, models, and reports
- `src/modules_testing`: module diagnostics
- `src/resources`: packaged specifications, keys, and sounds
- `src/tools`: manual manufacturing utilities

```bash
uv run --package productions-hardwares productions-hardwares
make hardware
make hardware-test
make hardware-build
```

## Leveling and Jog OT3

The leveling menu writes Gantry, Z stage, 8-channel pipette, 96-channel pipette,
and Gripper parallelism results into one robot/day CSV report. Gantry leveling
also records the four gauge heights, their maximum difference, and Deck Slot.

Run the standalone maintenance jog from the main menu, alongside Leveling Test,
or directly:

```bash
uv run --package productions-hardwares productions-hardwares jog \
  --robot-ip 192.168.6.1 --mount left
```

Jog controls are `W/A/S/D` for X/Y, `I/K` for Z, `-/+` for step size, and
`Q` or Enter to return. The single-key reader supports Windows and macOS.
