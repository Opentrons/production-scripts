# OT2R-API

## About

1. App Version: 6.3.1
2. Robot Server: 6.3.1
3. ThisVersion: 1.2.0

## News-1.2.0

1. updata HTTP API
   
   - get : /robot/door/status
     get the door status
   
   - get: /version
     get the release version

2. update the demo for PCR part (./examples/tc_load_slot8.py)
   
   - load lab-ware on slot8
   - run profile

3. update door_stauts demo (./examples/door_status.py)
   
   - get door status by HTTP API

4. update aspirate and dispense method
   
   - add arguments, include leading_air_gap and lagged_air_gap in aspirate and dispense method
   - call these methods in ./examples/transfer_liquid.py

5. protocol_context.py
   
   - return_tip()
   - mix_liquid()

## News-1.1.0

1. update a string of calibration HTTP API, include:
   - deck calibration
   - tip length calibration
   - pipette offset calibration
   - labware calibration
2. add load custom labware HTTP API, and demo file
3. add transfer liquid demo test by load custom labware
   
   

## API Document

[api-document](127.0.0.1/ot2-openapi_api_project.html)

## Hardware API Description

directory -> (./hardware_control)

1. home - done
2. move_to - done
3. move_rel - done
4. require_useful_pos - done
5. identify_robot - done

## Protocol API Description

directory -> (./protocol)

1. require_saved_pos - done
2. move_to - done
3. move_rel - done
4. move_to_slot - fail
5. move_to_well - done
6. require_last_run_status - done
7. require_all_runs - done
8. delete_run_by_id - done
9. clear_runs - done
10. wait_for_protocol_stop - done
11. home - done
12. run_protocol - done
13. stop_protocol - done
14. pause_protocol - done
15. drop - done
16. pick_up - done
17. load_liquid - done
18. load_pipette - done
19. load_labware - done
20. build-context - done
21. get_commands - done
22. blow_out - done
23. aspirate - done
24. dispense - done
25. touch_tip - debug

## System API Description

1. get_network_status - done
2. get_wifi_list - done
3. set_configure_wifi -done
4. get_wifi_keys - done
5. set_wifi_keys - done
6. set_delete_wifi_key -done
7. set_disconnect_wifi - done
8. set_ot2_blink_gantry_lights -done
9. get_robot_lights -done
10. set_robot_lights -done
11. get_settings -done
12. set_settings -done
13. set_log_level - done
14. set_log_level_upstream - done
15. get_settings_reset - done
16. get_robot_settings -done
17. get_pipette_settings - done
18. get_pipette_setting_by_id -done
19. patch_pipette_setting_by_id - done
20. get_calibration_status - done
21. set_execute_module_command -done
22. get_system_health - done
23. get_pipettes_currently_attached - done
24. get_engaged_motors - done
25. set_disengage_motors - done
26. set_capture_an_image - done
27. get_logs - done

## Modules/Heatershaker API Description

1. open_labware_latch - done
2. close_labware_latch - done
3. set_target_temperature - done
4. wait_for_temperature - done
5. get_target_temperature - done
6. get_target_speed - done
7. get_latch_status - done
8. deactivate_shaker - done
9. deactivate_heater - done
10. set_wait_shaker_speed - done

## Modules/Magnetic API Description

1. engage_magnetic - done
2. disengage - done

## Modules/TemperatureModule API Description

1. wait_for_temperature - done
2. get_target_temperature - done
3. set_temperature - done
4. deactivate - done

## Modules/Thermocycler

1. run_profile - fail
2. open_lid  - done
3. close_lid - done
4. set_lid_temperature - done
5. wait_for_lid_temperature - done
6. deactivate_lid - done
7. deactivate_block -done
8. wait_for_block_temperature - done
9. get_block_temperature - done
10. get_lid_temperature - done
11. get_lid_status - done
12. set_block_temperature - done

## QuickStart

```tex
请参考我们的一些示例: ./examples
进行一些移液，模块控制，和运动控制的基本操作。

- By合创生物
```

## TODO

1. calibration_flow
   校准deck, tiplength, pipette offset

2. load_protocol_flow
   load a protocol, analyze, and run

## 调用 HTTP 方法

```python
from http_client import HttpClient

ret = HttpClient.get("/health") # get 方法
ret = HttpClient.post("/robot/lights", data={"on": False}) # post 方法

# ret 返回元组，ret[0] = state_code: int, ret[1] = respons: dict 
```

## Opentrons branch tracker

```context
https://github.com/Opentrons/opentrons/tree/firerock-stable-6.3.1 
```

## Opentrons image tracker

```context
https://builds.opentrons.com/ot2-br/7722243621/ot2-fullimage.zip
```

## Google Drive

```text
https://drive.google.com/drive/folders/1-WOT8iaBbN7PJpk9yVO7vk3pkkGJjfhI
```


