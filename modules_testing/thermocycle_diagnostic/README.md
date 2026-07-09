# Thermocycle Diagnostic

Thermocycler diagnostic workflow for production/module testing. The script talks to the thermocycler over serial, runs the diagnostic command sequence, evaluates responses against specs, and writes a CSV-style report.

## Files

```text
modules_testing/thermocycle_diagnostic/
├── tc_diagnostic.py   # Main diagnostic workflow
├── driver.py          # Serial connection wrapper
├── report.py          # Report writer
└── README.md
```

The test specification is loaded from:

```text
shared_data/modules/tc_test_specification.json
```

## Run

From the repository root:

```bash
uv run python -m modules_testing.thermocycle_diagnostic.tc_diagnostic
```

Older manual usage also works from this directory:

```bash
python3 tc_diagnostic.py
```

## Operator Flow

1. Connect the thermocycler over serial.
2. Start the script.
3. Enter the barcode when prompted.
4. Follow the on-screen prompts, including lid and plate checks.
5. Review the generated diagnostic report.

## Notes

- The script is interactive and expects real hardware.
- Keep generated reports out of git.
- If the shared test specification changes, update `shared_data/modules/tc_test_specification.json` together with this README if the flow changes.
