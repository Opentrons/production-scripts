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
