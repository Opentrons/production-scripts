import os
import sys

addpathpat = os.path.dirname(__file__)
addpath = os.path.dirname(os.path.dirname(__file__))
addpath2 = os.path.dirname(addpath)
if addpath not in sys.path:
    sys.path.append(addpath)
if addpath2 not in sys.path:
    sys.path.append(addpath2)
if addpathpat not in sys.path:
    sys.path.append(addpathpat)

from http_client import HttpClient


class system:
    def __init__(self):
        pass

    def get_network_status(self):
        """Query the current network connectivity state
        查询当前网络连接状态
        :return:
        """
        ret = {}
        try:
            ret = HttpClient.get("/networking/status")
            HttpClient.judge_state_code(ret)
            return ret[1]
        except:
            return ret

    def get_wifi_list(self):
        """Scan for visible Wi-Fi networks
        扫描可见wi - fi网络
        :return:
        """
        ret = {}
        try:
            ret = HttpClient.get("/wifi/list")
            HttpClient.judge_state_code(ret)
            return ret[1]
        except:
            return ret

    def set_configure_wifi(self, ssid, psk="scrt sqrl", hidden="false", securityType="wpa-psk", eapConfig: dict = {}):
        """Configure the OT-2's Wi-Fi
        配置ot2的wifi
        :return:
        """
        dataval = {
            "ssid": ssid,
            "psk": psk

        }
        ret = {}
        try:
            ret = HttpClient.post(api="/wifi/configure", data=dataval)
            HttpClient.judge_state_code(ret)
            return ret[1]
        except:
            return ret

    def get_wifi_keys(self):
        """Get Wifi Keys
        获取WiFi密码
        :return:
        """
        ret = {}
        try:
            ret = HttpClient.get("/wifi/keys")
            HttpClient.judge_state_code(ret)
            return ret[1]
        except:
            return ret

    def set_wifi_keys(self, key):
        """
        Post Wifi Key
        设置WiFi密码
        :return:
        """
        dataval = {
            "key": key
        }
        ret = {}
        try:
            ret = HttpClient.post(api="/wifi/keys", data=dataval)
            HttpClient.judge_state_code(ret)
            return ret[1]
        except:
            return ret

    def set_delete_wifi_key(self, keyid):
        """
        Delete Wifi Key
        删除指定ssid 的密码
        param keyid: 要删除的键的keyid The ID of key to delete, as determined by a previous call to GET /wifi/keys
        :return:
        """
        dataval = {
        }
        ret = {}
        try:
            ret = HttpClient.delete(api="/wifi/keys/{key_uuid}".format(keyid), data=dataval)
            HttpClient.judge_state_code(ret)
            return ret[1]
        except:
            return ret

    def set_disconnect_wifi(self, ssid):
        """
        Disconnect the OT-2 from Wi-Fi
        断开ot-2的wifi链接
        param ssid:wifi名称(The network's SSID)
        :return:
        """
        dataval = {
            "ssid": ssid
        }
        ret = {}
        try:
            ret = HttpClient.post(api="/wifi/disconnect", data=dataval)
            HttpClient.judge_state_code(ret)
            return ret[1]
        except:
            return ret

    def set_ot2_Blink_gantry_lights(self, seconds: int = 100):
        """
        Blink the OT-2's gantry lights so you can pick it out of a crowd
        使OT2龙门架灯闪烁
        param seconds: 闪烁时间
        :return {'message':'identifying'}
        """
        dataval = {

        }
        ret = {}
        try:
            ret = HttpClient.post(api="/identify?seconds={}".format(seconds), data=dataval)
            HttpClient.judge_state_code(ret)
            return ret[1]
        except:
            return ret

    def get_robot_lights(self):
        """
        Get the current status of the OT-2's rail lights 获取 OT-2 轨道灯的当前状态
        :return: {'on': False}
        """

        ret = {}
        try:
            ret = HttpClient.get("/robot/lights")
            HttpClient.judge_state_code(ret)
            return ret[1]
        except:
            return ret

    def set_robot_lights(self, on: bool = True):
        """
        Turn the rail lights on or off 打开或关闭轨道灯
        
        param on:  true 开 false 关
        return:{'on': True}
         """
        dataval = {
            "on": on
        }
        ret = {}
        try:
            ret = HttpClient.post(api="/robot/lights", data=dataval)
            HttpClient.judge_state_code(ret)
            return ret[1]
        except:
            return ret

    def get_setings(self):
        """Get a list of available advanced settings (feature flags) and their values
            获取可用高级设置（功能标志）及其值的列表
        :return: list
        """

        ret = {}
        try:
            ret = HttpClient.get("/settings")
            return ret
        except:
            return ret

    def set_setings(self, id, old_id, title, description, restart_required, value, restart):
        """Change an advanced setting (feature flag) 更改高级设置（功能标志）
        param id: The machine-readable property ID	机器可读的属性 ID
        param old_id:The ID by which the property used to be known; not useful now and may contain spaces or hyphens	 曾经的ID, 现在没有用，可能包含空格或连字符
        param title: A human-readable short string suitable for display as the title of the setting	适合作为设置标题显示的人类可读短字符串
        param description:A human-readable long string suitable for display as a paragraph or two explaining the setting 描述 可读的长字符串，适合显示为解释设置的一两段	
        param restart_required:Whether a robot restart is required to make this change take effect	是否需要重启
        param value:Whether the setting is off by previous user choice (false), true by user choice (true), or off and has never been altered (null) 设置是否由先前的用户选择关闭 (false)、由用户选择为真 (true) 或关闭且从未更改 (null)
        param restart:
        :return: list
        """

        dataval = {
            "settings": {"id": id,
                         "old_id": old_id,
                         "title": title,
                         "description": description,
                         "restart_required": restart_required,
                         "value": value

                         },
            "links": {"restart": restart}

        }
        ret = {}
        try:
            ret = HttpClient.post(api="/settings", data=dataval)
            HttpClient.judge_state_code(ret)
            return ret[1]
        except:
            return ret

    def set_log_level(self, log_level):
        """Set the minimum level of logs saved locally 设置本地保存日志的最低级别
        param log_level: 等级
        """

        dataval = {
            "log_level": log_level
        }
        ret = {}
        try:
            ret = HttpClient.post(api="/settings/log_level/local", data=dataval)
            HttpClient.judge_state_code(ret)
            return ret[1]
        except:
            return ret

    def set_log_level_upstream(self, log_level):
        """Set the minimum level of logs sent upstream via syslog-ng to Opentrons. Only available on a real robot. 设置通过 syslog-ng 向上游发送到 Opentrons 的日志的最低级别。 仅适用于真正的机器人。
        param log_level: 等级
        """

        dataval = {
            "log_level": log_level
        }
        ret = {}
        try:
            ret = HttpClient.post(api="/settings/log_level/upstream", data=dataval)
            HttpClient.judge_state_code(ret)
            return ret[1]
        except:
            return ret

    def get_setings_reset(self):
        """Get the settings that can be reset as part of factory reset
            获取可以作为出厂重置的一部分重置的设置
        :return: list
        """

        ret = {}
        try:
            ret = HttpClient.get("/settings/reset/options")
            HttpClient.judge_state_code(ret)
            return ret[1]
        except:
            return ret

    def get_robot_setings(self):
        """
        Get the current robot config 获取当前robot的配置
        :return: list
        """
        ret = {}
        try:
            ret = HttpClient.get("/settings/robot")
            HttpClient.judge_state_code(ret)
            return ret[1]
        except:
            return ret

    def get_pipette_setings(self):
        """
        List all settings for all known pipettes by id 按 ID 列出所有已知移液器的所有设置
        :return: list
        """
        ret = {}
        try:
            ret = HttpClient.get("/settings/pipettes")
            HttpClient.judge_state_code(ret)
            return ret[1]
        except:
            return ret

    def get_pipette_seting_by_id(self, pipette_id):
        """
        Get the settings of a specific pipette by ID 通过 ID 获取特定移液器的设置
        param pipette_id 移液器id
        :return: list
        """
        ret = {}
        try:
            ret = HttpClient.get("/settings/pipettes/{}".format(pipette_id))
            HttpClient.judge_state_code(ret)
            return ret[1]
        except:
            return ret

    def patch_pipette_setting_by_id(self, pipette_id):
        """
        Change the settings of a specific pipette 更改特定移液器的设置
        param pipette_id 移液器id
        :return: list
        """
        ret = {}
        try:
            ret = HttpClient.patch("/settings/pipettes/{}".format(pipette_id))
            HttpClient.judge_state_code(ret)
            return ret[1]
        except:
            return ret

    def get_calibration_status(self):
        """
        Get the calibration status 获取校准状态
        :return: list
        """
        ret = {}
        try:
            ret = HttpClient.get("/calibration/status")
            HttpClient.judge_state_code(ret)
            return ret[1]
        except:
            return ret

    def set_execute_module_command(self, serial, command_type, args: list):
        """Execute a command on a specific module. 在特定模块上执行命令
        Command a module to take an action. Valid actions depend on the specific module attached, which is the model value from GET /modules/{serial}/data or GET /modules
        命令模块采取行动。 有效操作取决于附加的特定模块，这是来自 GET /modules/{serial}/data 或 GET /modules 的模型值
        param log_level: 等级
        """

        dataval = {
            "command_type": command_type,
            "args": args
        }
        ret = {}
        try:
            ret = HttpClient.post(api="/modules/{}".format(serial), data=dataval)
            HttpClient.judge_state_code(ret)
            return ret[1]
        except:
            return ret

    def get_system_health(self):
        """
        Get information about the health of the robot server. Use the health endpoint to check that the robot server is running anr ready to operate. A 200 OK response means the server is running. The response includes information about the software and system.
        获取有关机器人服务器健康状况的信息。 使用健康端点检查机器人服务器是否正在运行并准备好运行。 
        200 OK 响应表示服务器正在运行。 响应包括有关软件和系统的信息。
        :return: list
        """

        ret = {}
        try:
            ret = HttpClient.get("/health")
            HttpClient.judge_state_code(ret)
            return ret[1]
        except:
            return ret

    def get_pipettes_currently_attached(self):
        """获取当前连接的移液器
        :return: dict
        """
        ret = {}
        try:
            ret = HttpClient.get("/pipettes")
            HttpClient.judge_state_code(ret)
            return ret[1]
        except:
            return ret

    def get_engaged_motors(self):
        """
        查询哪些电机正在运行并保持
        :return: dict
        """
        ret = {}
        try:
            ret = HttpClient.get("/motors/engaged")
            HttpClient.judge_state_code(ret)
            return ret[1]
        except:
            return ret

    def set_disengage_motors(self, axes: list):
        """Disengage a motor or set of motors
        断开一个或一组电机
        param axes: 轴 like ["x","y","z","a","b"]
        """

        dataval = {
            "axes": axes
        }
        ret = {}
        try:
            ret = HttpClient.post(api="/motors/disengage", data=dataval)
            HttpClient.judge_state_code(ret)
            return ret[1]
        except:
            return ret

    def set_capture_an_image(self):
        """Capture an image from the OT-2's on-board camera and return it
        从 OT-2 的机载相机捕获图像并将其返回
        """

        dataval = {

        }
        ret = {}
        try:
            ret = HttpClient.post(api="/camera/picture", data=dataval)
            return ret
        except Exception as err:
            return ret

    def get_Logs(self, log_identifier):
        """
        从机器人获取日志。
        param log_identifier: 日志标识符 like:api.log serial.log server.log
        :return: dict
        """
        ret = {}
        try:
            ret = HttpClient.get("/logs/{0}".format(log_identifier))
            return ret
        except Exception as err:
            print(err)
            return ret
