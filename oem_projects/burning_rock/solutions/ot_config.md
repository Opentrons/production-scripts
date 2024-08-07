## OT Config Path

```json
{
  "labware_database_file": "/data/opentrons.db",
  "labware_calibration_offsets_dir_v2": "/data/labware/v2/offsets",
  "labware_user_definitions_dir_v2": "/data/labware/v2/custom_definitions",
  "feature_flags_file": "/data/feature_flags.json",
  "robot_settings_file": "/data/robot_settings.json",
  "deck_calibration_file": "/data/deck_calibration.json",
  "log_dir": "/data/logs",
  "api_log_file": "/data/logs/api.log",
  "serial_log_file": "/data/logs/serial.log",
  "wifi_keys_dir": "/data/user_storage/opentrons_data/network_keys",
  "hardware_controller_lockfile": "/data/hardware.lock",
  "pipette_config_overrides_dir": "/data/pipettes",
  "tip_length_calibration_dir": "/data/tip_lengths",
  "robot_calibration_dir": "/data/robot",
  "pipette_calibration_dir": "/data/robot/pipettes",
  "custom_tiprack_dir": "/data/tip_lengths/custom_tiprack_definitions",
  "gripper_calibration_dir": "/data/robot/gripper"
}
```

## deck_calibration.json

```json
{"attitude": [[0.9981, 0.0012, 0.0], [0.0011, 1.002, 0.0], [0.0, 0.0, 1.0]], "last_modified": "2023-07-19T08:59:51.836588+00:00", "source": "user", "pipette_calibrated_with": "P20SV202021110202", "tiprack": "60e107ba7e6e5d23beefe9f0c888f860f7b923c71906aaa5e7f460ab25c4f38a", "status": {"markedBad": false, "source": null, "markedAt": null}}
```

## Calibration Position

```
"calibrationPoints": [
      {
        "id": "1BLC",
        "position": [12.13, 9.0, 0.0],
        "displayName": "Slot 1 Bottom Left Cross"
      },
      {
        "id": "3BRC",
        "position": [380.87, 9.0, 0.0],
        "displayName": "Slot 3 Bottom Right Cross"
      },
      {
        "id": "7TLC",
        "position": [12.13, 258.0, 0.0],
        "displayName": "Slot 7 Top Left Cross"
      },
      {
        "id": "9TRC",
        "position": [380.87, 258.0, 0.0],
        "displayName": "Slot 9 Top Right Cross"
      },
      {
        "id": "10TLC",
        "position": [12.13, 348.5, 0.0],
        "displayName": "Slot 10 Top Left Cross"
      },
      {
        "id": "11TRC",
        "position": [248.37, 348.5, 0.0],
        "displayName": "Slot 11 Top Right Cross"
      },
      {
        "id": "1BLD",
        "position": [12.13, 6.0, 0.0],
        "displayName": "Slot 1 Bottom Left Dot"
      },
      {
        "id": "3BRD",
        "position": [380.87, 6.0, 0.0],
        "displayName": "Slot 3 Bottom Right Dot"
      },
      {
        "id": "7TLD",
        "position": [12.13, 261.0, 0.0],
        "displayName": "Slot 7 Top Left Dot"
      },
      {
        "id": "9TRD",
        "position": [380.87, 261.0, 0.0],
        "displayName": "Slot 9 Top Right Dot"
      },
      {
        "id": "10TLD",
        "position": [12.13, 351.5, 0.0],
        "displayName": "Slot 10 Top Left Dot"
      },
      {
        "id": "11TRD",
        "position": [248.37, 351.5, 0.0],
        "displayName": "Slot 11 Top Right Dot"
      }
    ],
    "fixtures": [
      {
        "id": "fixedTrash",
        "slot": "12",
        "labware": "opentrons_1_trash_1100ml_fixed",
        "displayName": "Fixed Trash"
      }
    ]
  },
```



## Deck Calibraiton

0. exit session

    ```
    command calibration.exitSession
    ```

1. get session

2. post session

3. excuse load labware

4. excuse move to labware - slot8

5. excuse jog

   ```
   command calibration.jog
   ```

6. excuse pick up

   ```
   command calibration.pickUpTip
   ```

7. excuse try again

   ```
   command calibration.invalidateTip
   ```

8. excuse pick up

   ```
   command calibration.pickUpTip
   ```

9. excuse move to deck

   ```
   command calibration.moveToDeck
   ```

10. excuse save offset

   ```
   command calibration.saveOffset
   ```

11. excuse move to point one

    ```
    command calibration.moveToPointOne
    ```

12. excuse save offset

    ```
    command calibration.saveOffset
    ```

13. excuse move to point two

    ```
    command calibration.deck.moveToPointTwo
    ```

14. excuse save offset

    ```
    command calibration.saveOffse
    ```

15. excuse move to point three

    ```
    command calibration.deck.moveToPointThree
    ```

16. excuse save offset

    ```
    command calibration.saveOffset
    ```

17. move to tiprack

    ```
    calibration.moveToTipRack
    ```

18. calibration exit

    ````
    calibration.exitSession
    ````

## Tip Length Calibration

1. load labware

2. move to labware

   ```
   calibration.moveToReferencePoint
   ```

3. save offset

4. move to tip rack

5. jog

6. pick up

7. move to labware

   ```
   calibration.moveToReferencePoint
   ```

8. save offset

9. move to tip rack

10. take away

11. exit

## Pipette offset calibration

```
pipetteOffsetCalibration
```

1. load labware - slot 8
2. move to tip rack
3. jog
4. pick up
5. move to deck
6. jog
7. save offset
8. move to point one
9. jog
10. save offset 
11. exit

## Labware calibration

1. get run - get

   ```
   http://169.254.219.45:31950/runs/23b20c34-d904-4b26-916c-3237bb70bd36
   ```

2. get analyse - get

   ```
   http://169.254.219.45:31950/protocols/3fbf32e2-5ef0-4aa9-83ca-39f968e6b15f/analyses
   ```

3. create - post

   ```
   http://169.254.219.45:31950/runs/23b20c34-d904-4b26-916c-3237bb70bd36/commands?waitUntilComplete=true
   ```

4. move to well 

   ```
   top
   ```

5. save postion

6. moveRelative

7. save position

8. pickUpTip
