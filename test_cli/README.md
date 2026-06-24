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
