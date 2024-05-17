import time

from devices.air_sensor import AirSensor
from devices.air_sensor2 import AirSensor2
from utils import Utils


def init_connection(sensor1=None):
    if sensor1 is None:
        sensor1 = None
    else:
        sensor1 = AirSensor()
    sensor2 = AirSensor2(49846)
    sensor3 = AirSensor2(49847)
    sensor2.connect()
    sensor3.connect()
    return sensor1, sensor2, sensor3


def read_air_params(sensor1, sensor2, sensor3):
    """
    read tem/humidity/pressure
    """
    if sensor1 is not None:
        sensor1_tem, sensor1_hum = sensor1.get_read()
    else:
        sensor1_tem = ""
        sensor1_hum = ""

    for i in range(30):
        air_params_2 = sensor2.get_air_params()
        air_params_3 = sensor3.get_air_params()
        if air_params_2["success"] is True and air_params_3["success"] is True:
            sensor2_tem = air_params_2["data"]["temperature"]
            sensor2_hum = air_params_2["data"]["humidity"]
            sensor2_pressure = air_params_2["data"]["pressure"]
            sensor2_pressure_diff = air_params_2["data"]["p_difference"]

            sensor3_tem = air_params_3["data"]["temperature"]
            sensor3_hum = air_params_3["data"]["humidity"]
            sensor3_pressure = air_params_3["data"]["pressure"]
            sensor3_pressure_diff = air_params_3["data"]["p_difference"]

            return (sensor1_tem, sensor1_hum), (sensor2_tem, sensor2_hum, sensor2_pressure, sensor2_pressure_diff), \
                (sensor3_tem, sensor3_hum, sensor3_pressure, sensor3_pressure_diff)
        else:
            if i < 9:
                print(f"Reading Fail {i + 1} times")
                time.sleep(1)
            else:
                raise ValueError


def reading_and_write_csv(file_name):
    # write title
    Utils.write_to_csv(file_name, ["Time", "Sensor1-Temperature", "Sensor1-Humidity", "Sensor2-Temperature",
                                   "Sensor2-Humidity", "Sensor2-Pressure", "Sensor2-Pressure-Diff",
                                   "Sensor3-Temperature",
                                   "Sensor3-Humidity", "Sensor3-Pressure", "Sensor3-Pressure-Diff"])
    sensor1, sensor2, sensor3 = init_connection()

    while True:
        air_params = read_air_params(None, sensor2, sensor3)
        current_time = Utils.get_time_string()
        print("========Sensor1========")
        print(f"Temperature: {air_params[0][0]}, Humidity: {air_params[0][1]} \n")
        print("========Sensor2========")
        print(
            f"Temperature: {air_params[1][0]}, Humidity: {air_params[1][1]}, Pressure: {air_params[1][2]}, Diff: {air_params[1][3]}\n")
        print("========Sensor3========")
        print(
            f"Temperature: {air_params[2][0]}, Humidity: {air_params[2][1]}, Pressure: {air_params[2][2]}, Diff: {air_params[2][3]}\n")

        this_line = [current_time, air_params[0][0], air_params[0][1], air_params[1][0], air_params[1][1],
                     air_params[1][2], air_params[1][3], air_params[2][0], air_params[2][1],
                     air_params[2][2], air_params[2][3]]
        Utils.write_to_csv(file_name, this_line)


if __name__ == '__main__':
    start_time = Utils.get_time_string(format=True)
    reading_and_write_csv(f'testing_data/reading-air-sensor-{start_time}.csv')
