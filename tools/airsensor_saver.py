import time

from devices.air_sensor import AirSensor
from devices.air_sensor2 import AirSensor2
from utils import Utils


def init_connection():
    sensor1 = AirSensor()
    sensor2 = AirSensor2()
    sensor2.connect()
    return sensor1, sensor2


def read_air_params(sensor1, sensor2):
    """
    read tem/humidity/pressure
    """
    sensor1_tem, sensor1_hum = sensor1.get_read()
    air_params = sensor2.get_air_params()
    for i in range(30):
        if air_params["success"] is True:
            sensor2_tem = air_params["data"]["temperature"]
            sensor2_hum = air_params["data"]["humidity"]
            sensor2_pressure = air_params["data"]["pressure"]
            return (sensor1_tem, sensor1_hum), (sensor2_tem, sensor2_hum, sensor2_pressure)
        else:
            if i < 9:
                print(f"Reading Fail {i+1} times")
                time.sleep(1)
            else:
                raise ValueError


def reading_and_write_csv(file_name):
    # write title
    Utils.write_to_csv(file_name, ["Time", "Sensor1-Temperature", "Sensor1-Humidity", "Sensor2-Temperature",
                                   "Sensor2-Humidity", "Sensor2-Pressure"])
    sensor1, sensor2 = init_connection()

    while True:
        air_params = read_air_params(sensor1, sensor2)
        current_time = Utils.get_time_string()
        print("========Sensor1========")
        print(f"Temperature: {air_params[0][0]}, Humidity: {air_params[0][1]} \n")
        print("========Sensor2========")
        print(f"Temperature: {air_params[1][0]}, Humidity: {air_params[1][1]}, Pressure: {air_params[1][2]}\n")

        this_line = [current_time, air_params[0][0], air_params[0][1], air_params[1][0], air_params[1][1],
                     air_params[1][2]]
        Utils.write_to_csv(file_name, this_line)


if __name__ == '__main__':
    start_time = Utils.get_time_string(format=True)
    reading_and_write_csv(f'testing_data/reading-air-sensor-{start_time}.csv')
