from modules.data_analysis.data_links import get_data_links


EXPECTED_ROBOT_LINKS = {
    "robot_update_diagnostic": "diagnostic",
    "robot_update_xy_belt_calibration": "xy_calibration",
    "robot_update_gantry_stress": "gantry_stress_test",
    "robot_update_leveling": "leveling_test",
    "robot_update_z_stage": "z_stage_test",
}


def test_data_links_include_robot_templates_and_tracker_links() -> None:
    result = get_data_links()
    robot_links = [entry for entry in result["links"] if entry["product"] == "Robot"]

    assert result["error"] is None
    assert {entry["config_key"]: entry["test_type"] for entry in robot_links} == (
        EXPECTED_ROBOT_LINKS
    )
    for entry in robot_links:
        assert any(link["available"] for link in entry["templates"])
        assert any(
            link["available"] and link["label"] == "Opentrons OT3"
            for link in entry["trackers"]
        )
        assert entry["raw_data_parent_folder"]["available"] is True
