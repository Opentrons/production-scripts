def get_sheet_name_by_testname(test_name: str, is_finished: bool):
    index = 0 if not is_finished else 1
    sheet_name = {
        "stress-test-qc-ot3": ["Gantry-Stress", "Gantry-Stress"],
        "robot-assembly-qc-ot3": ["DiagnosticWithoutCosmeticPanel", "DiagnosticWithCosmeticPanel"]
    }[test_name][index]
    return sheet_name