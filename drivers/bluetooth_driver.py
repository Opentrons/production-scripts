import bluetooth


class BluetoothDevice:

    @classmethod
    def find_deveces(cls):
        print("Finding nearby bluetooth devices, please wait for several seconds...")
        devices = bluetooth.discover_devices(duration=30, lookup_names=True)
        for address, name in devices:
            print(address, name)

    def __init__(self):
        self.sock = None

    def build_device(self, device_mac_addr):
        print(f"Connecting {device_mac_addr}...")
        try:
            self.sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            self.sock.connect((device_mac_addr, 1))
        except Exception as e:
            print(f"Connecting {device_mac_addr} failed")
            print(e)

    def send(self, data):
        self.sock.send(data)

    def receive(self, lenth):
        data = self.sock.recv(lenth)
        return data


if __name__ == '__main__':
    b = BluetoothDevice()
    devices = b.find_deveces()

    addr = "06:9C:F5:AC:F7:BC"
    b.build_device(addr)
    # print(b.receive(28))
    # for i in devices:
    #     b.build_device(i)
    #     # print(b.receive(28))
