# Test CLI

Cross-platform production test CLI for OT3/Flex workflows.

## Start

From the repository root:

```bash
uv run test-cli leveling
```

Open a terminal-style launcher window:

- macOS: double-click `launchers/test-cli.command`
- Windows: double-click `launchers/test-cli.bat`
- Windows PowerShell: run `launchers/test-cli.ps1`

The launcher opens the Test CLI entry screen. First select the test name, enter
the operator name, then choose whether to use simulating mode. Simulating mode
defaults to `No`. Test-specific fields such as robot serial number and IP are
requested inside that test flow.

Simulation mode does not connect to robot hardware or serial sensors:

```bash
uv run test-cli leveling --simulate --test all --robot-sn SIM-001 --robot-ip simulator
```

Run one leveling test directly:

```bash
uv run test-cli leveling --test ch8
uv run test-cli leveling --simulate --test ch96 --robot-sn SIM-CH96
```

## Commands

```bash
uv run test-cli --help
uv run test-cli leveling --help
```

## Makefile

Run Make targets from this directory or from the repository root with `make -C test_cli ...`.

```text
make                 Start interactive test-cli
make leveling        Start leveling CLI
make simulate        Run all leveling tests in simulation mode
make build           Build current-platform executable into ../dist
make build-clean     Clean then build executable
make update-compensation  Update leveling_config.json from test_cli/leveling_test/Templete.xlsx
make clean           Remove build artifacts
```

`make update-compensation` only reads `test_cli/leveling_test/Templete.xlsx`. If the file is missing, the command exits with an error instead of using an older template.

## Package Layout

```text
test_cli/
├── cli/                    # Rich UI, prompts, exception display
├── core/                   # Shared hardware/API/protocol primitives
│   ├── hardware_control/
│   ├── maintenance_api/
│   └── protocol/
├── leveling_test/          # Current leveling test suite
├── main.py                 # test-cli entry point
└── http_client.py
```

Reports are written to `testing_data/` under the selected `--script-dir`.
