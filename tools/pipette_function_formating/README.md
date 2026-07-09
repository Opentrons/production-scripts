# Pipette Function Formatting

Small utility for formatting pipette function table data copied from Google Drive/Sheets into bracketed function text files.

## Files

```text
tools/pipette_function_formating/
├── function_formating.py  # Interactive formatter
├── ylcs.txt               # Default input file
└── *.txt                  # Existing formatted function examples
```

## Input

Paste the source table data into:

```text
tools/pipette_function_formating/ylcs.txt
```

Each line should contain numeric values separated by tabs or spaces. The script converts each line into bracketed comma-separated values.

## Run

From the repository root:

```bash
uv run python tools/pipette_function_formating/function_formating.py
```

The script asks for an output file name. If no name is entered, it writes:

```text
function.txt
```

## Naming Rule

Use a descriptive function name:

```text
Type_Model_Tips_Description_Date
```

Example:

```text
P1KHV36_T1000_backlash3_20240101
```

## Notes

- Generated function files are local artifacts unless they are intentionally added as examples.
- Review generated values before using them in a production protocol.
