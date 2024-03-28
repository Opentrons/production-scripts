from drivers.socket_interface import Server


class AirSensor2:
    def __init__(self):
        self.server = Server()

    def connect(self):
        """
        initial server
        """
        self.server.initial_server()

    def get_air_params(self):
        """
        send get value
        """
        try:
            data = self.server.send_and_receive("GetMValue", 2)
            data_list = data.split('\r\n')
            pressure = data_list[0].split(' ')[0]
            humidity = data_list[1].split(' ')[0]
            temperature = data_list[2].split(' ')[0]
            return {
                "success": True,
                "data": {
                    "pressure": pressure,
                    "humidity": humidity,
                    "temperature": temperature
                }
            }
        except Exception as e:
            print(e)
            return {"success": False}


if __name__ == '__main__':
    sensor = AirSensor2()
    sensor.connect()
    sensor.get_air_params()
