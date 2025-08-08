import serial
import serial.tools.list_ports
import time

def list_serial_ports():
    """列出所有可用的串口"""
    ports = serial.tools.list_ports.comports()
    return [port.device for port in ports]


def serial_debug(port_name, baudrate=9600):
    """串口调试函数"""
    try:
        # 打开串口
        ser = serial.Serial(port_name, baudrate, timeout=1)
        print(f"已连接到 {port_name}, 波特率 {baudrate}")

        while True:
            # 发送字符 'r'
            ser.write(b'r')
            print("已发送: 'r'")
            time.sleep(0.5)
            # 读取返回数据
            received_data = ser.readline().decode('utf-8').strip()

            print(f"接收到: {received_data}")



    except serial.SerialException as e:
        print(f"串口错误: {e}")
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("串口已关闭")


if __name__ == "__main__":
    # 列出可用串口
    available_ports = list_serial_ports()
    if not available_ports:
        print("没有找到可用的串口")
        exit()

    print("可用的串口:")
    for i, port in enumerate(available_ports, 1):
        print(f"{i}. {port}")

    # 选择串口
    try:
        choice = int(input("请选择要使用的串口编号: ")) - 1
        selected_port = available_ports[choice]
    except (ValueError, IndexError):
        print("无效的选择")
        exit()

    # 设置波特率
    baudrate = 2400
    try:
        baudrate = int(baudrate)
    except ValueError:
        print("无效的波特率，使用默认值9600")
        baudrate = 9600

    # 启动调试
    serial_debug(selected_port, baudrate)