# High Voltage Test

Manual high-voltage tester control utility. The tool uses the GPT serial driver to connect to the tester, select a manual test step, configure buzzer and function-test settings, and query measurement output.

## Files

```text
tools/high_voltage_test/
├── Makefile
├── main.py              # Interactive manual workflow
└── GPT/
    ├── GptDevice.py    # Serial driver and command helpers
    ├── cmd_args.py     # Enum arguments
    └── code.py         # Device command definitions and simulated responses
```

## Makefile Help

```text
Available targets:
  make setup  Install root project dependencies with uv
  make pip    List packages in the uv environment
  make run    Run the high-voltage manual test workflow
  make gpt    Run the GPT device driver module
  make show   Show resolved project root and Python command
```

## Run

From this directory:

```bash
make run
```

Or from the repository root:

```bash
make -C tools/high_voltage_test run
```

## Notes

- The driver scans for a GPT device with USB VID/PID `10C4:EA60`.
- If no device is found, the driver falls back to simulation mode.
- The workflow is interactive; enter `9` to exit the manual loop.
