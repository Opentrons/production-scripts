from BayOmicsLib import BayOmicsLib
from opentrons import protocol_api

from BayOmicsLib import USER_LIQUID_LABWARE_DEF, USER_LIQUID_SLOT, USER_LIQUID_LABWARE_LABEL, LABWARE_DEF, \
    LABWARE_LABEL, USER_LABWARE_SLOT

from BayOmicsLib import UserMode, DropMethod, transform_round, USER_PRESSURE, DARK_DURATION, HEAT_SETTING

# metadata
metadata = {
    "protocolName": "__BayOmicsTemperatureModule__V1.4.5",
    "author": "Name <opentrons@example.com>",
    "description": "Simple protocol to get started using the OT-2",
}

# requirements
requirements = {"robotType": "OT-2", "apiLevel": "2.18"}

"""
增加用户参数
"""


def add_parameters(parameters: protocol_api.Parameters):
    """
    :param parameters:
    :return:
    """
    parameters.add_int(
        variable_name="user_pwd",
        display_name="管理员密码",
        description="部分功能需要管理员密码才能生效",
        default=999999,
        minimum=0,
        maximum=999999,
        unit=""
    )

    parameters.add_bool(
        variable_name="led_virtual",
        display_name="LED虚拟值显示",
        description="是否按虚拟值显示当前LED",
        default=True
    )

    parameters.add_bool(
        variable_name="pause_selection",
        display_name="暂停观察",
        description="是否运行过程中等待操作员操作",
        default=True
    )

    parameters.add_int(
        variable_name="sample_number",
        display_name="样品数量",
        description="实验的样品数量，最大不能超过96",
        default=8,
        minimum=8,
        maximum=96,
        unit="个"
    )


# protocol run function
def run(protocol: protocol_api.ProtocolContext):
    """
    :param protocol:
    :return:
    """
    """Opentrons 加载移液器，耗材
    1. load pipette
    2. load labware
    3. loda module
    4. 定义中间move to location
    """
    # labware
    tiprack_1 = protocol.load_labware(
        "opentrons_96_tiprack_20ul", location="4"
    )
    tiprack_2 = protocol.load_labware(
        "opentrons_96_tiprack_20ul", location="5"
    )
    tiprack_3 = protocol.load_labware(
        "opentrons_96_tiprack_20ul", location="6"
    )

    move_to_location = tiprack_3

    # pipettes
    left_pipette = protocol.load_instrument("p20_multi_gen2", mount="left",
                                            tip_racks=[tiprack_1, tiprack_2, tiprack_3])
    sample_liquid = protocol.load_labware('armadillo_96_wellplate_200ul_pcr_full_skirt', location='2')  # 样本

    # customer labware
    customer_liquid = protocol.load_labware_from_definition(USER_LIQUID_LABWARE_DEF, USER_LIQUID_SLOT,
                                                            USER_LIQUID_LABWARE_LABEL)  # 试剂
    user_labware = protocol.load_labware_from_definition(
        LABWARE_DEF,
        USER_LABWARE_SLOT,
        LABWARE_LABEL,
    )
    # TD module
    temp_mod = protocol.load_module(
        module_name="temperature module gen2", location="3"
    )
    temp_adapter = temp_mod.load_adapter("opentrons_96_well_aluminum_block")
    enzyme_liquid = temp_adapter.load_labware("armadillo_96_wellplate_200ul_pcr_full_skirt")
    # parameters
    simulating = protocol.is_simulating()
    sample_counts = protocol.params.sample_number
    led_virtual = protocol.params.led_virtual
    user_pwd = protocol.params.user_pwd
    pause_selection = protocol.params.pause_selection
    """
    检查参数
    """
    verificaiton_value = sample_counts % 8
    assert verificaiton_value == 0, 'sample counts should be multiples of 8 (样本数不是8的倍数)'

    """一、连接串口
    1. 建立设备连接
    2. 初始化LED屏幕
    """
    protocol.comment(">>>>>1.连接串口<<<<<")
    serial_module = BayOmicsLib(19200, protocol)
    serial_module.build_connection(simulating, led_virtual, user_pwd)

    if serial_module.device is not None:
        protocol.comment(">>>>>2.初始化设备<<<<<")
        """二、初始化
        1. 使能电机，初始化速度和复位
        2. 关闭加压
        3. 关闭温度控制器
        4. 开启灯带
        5. 开启TD
        """
        serial_module.init_device()
        if serial_module.user_mode == UserMode.Debugging:
            pass
        else:
            temp_mod.start_set_temperature(celsius=4)

        protocol.comment(">>>>>3.开始实验<<<<<")
        _protocol = None
        """三、执行实验步骤(移液&正压)
        1. 向样本处理器中加入60ul试剂 Ac
        """
        transform_round(left_pipette, customer_liquid, user_labware, "Ac", sample_counts, 60, move_to_location,
                        serial_module, protocol=_protocol, pressure_setting=USER_PRESSURE['step1'])
        """三、执行实验步骤(移液&正压)
        2. 向样本处理器中加入60ul试剂 Wa
        """
        transform_round(left_pipette, customer_liquid, user_labware, "Wa", sample_counts, 60, move_to_location,
                        serial_module, protocol=_protocol, pressure_setting=USER_PRESSURE['step2'])
        if pause_selection:
            protocol.pause("观察试剂过柱情况")
        """三、执行实验步骤(移液&正压)
        3. 向样本处理器中加入30ul样本
        """
        transform_round(left_pipette, sample_liquid, user_labware, "Sample", sample_counts, 30, move_to_location,
                        serial_module, drop_method=DropMethod.DropForAColumn, protocol=_protocol,
                        pressure_setting=USER_PRESSURE['step3'])
        """三、执行实验步骤(移液&正压)
        4. 向样本处理器中加入30ul试剂 Wa
        """
        transform_round(left_pipette, customer_liquid, user_labware, "Wa", sample_counts, 30, move_to_location,
                        serial_module, protocol=_protocol, pressure_setting=USER_PRESSURE['step4'])
        """三、执行实验步骤(移液&正压)
        5. 向样本处理器中加入30ul试剂 Ac
        """
        transform_round(left_pipette, customer_liquid, user_labware, "Ac", sample_counts, 30, move_to_location,
                        serial_module, protocol=_protocol, pressure_setting=USER_PRESSURE['step5'])
        """三、执行实验步骤(移液&正压)
        6. 向样本处理器中加入30ul试剂 Rd - 再加入30ul Rd -  遮光孵化 - 正压
        """
        transform_round(left_pipette, customer_liquid, user_labware, "Rd", sample_counts, 30, move_to_location,
                        serial_module, protocol=_protocol, drop_method=DropMethod.DoNotDrop,
                        pressure_setting=USER_PRESSURE['step6_1'])
        transform_round(left_pipette, customer_liquid, user_labware, "Rd", sample_counts, 30, move_to_location,
                        serial_module, protocol=_protocol, drop_method=DropMethod.DoNotPickUp,
                        pressure_setting=USER_PRESSURE['step6_2'])
        if pause_selection:
            protocol.pause("开始做避光孵化，请确认...")
        if serial_module.user_mode == UserMode.Debugging:
            serial_module.dark_incubation(1, pressure_setting=USER_PRESSURE['step6_3'])
        else:
            serial_module.dark_incubation(DARK_DURATION * 60, pressure_setting=USER_PRESSURE['step6_3'])
        """三、执行实验步骤(移液&正压)
        7. 向样本处理器中加入30ul试剂 Ds
        """
        transform_round(left_pipette, customer_liquid, user_labware, "Ds", sample_counts, 30, move_to_location,
                        serial_module, protocol=_protocol, pressure_setting=USER_PRESSURE['step7'])
        """三、执行实验步骤(移液&正压)
        8. 向样本处理器中加入13ul + 5ul酶
        """
        transform_round(left_pipette, enzyme_liquid, user_labware, "Enzyme", sample_counts, 13, move_to_location,
                        serial_module, protocol=_protocol, drop_method=DropMethod.DoNotDrop,
                        pressure_setting=USER_PRESSURE['step8_1'])
        transform_round(left_pipette, enzyme_liquid, user_labware, "Enzyme", sample_counts, 5, move_to_location,
                        serial_module, protocol=_protocol, drop_method=DropMethod.DoNotPickUp,
                        pressure_setting=USER_PRESSURE['step8_2'])
        # close td
        if serial_module.user_mode == UserMode.Debugging:
            pass
        else:
            temp_mod.deactivate()
        # 保温
        if serial_module.user_mode == UserMode.Debugging:
            serial_module.heat_incubation([{"temperature": 52, "time": 120}])
        else:
            serial_module.heat_incubation(HEAT_SETTING)
        """三、执行实验步骤(移液&正压)
        9. 向样本处理器中加入60ul试剂 Tf
        """
        transform_round(left_pipette, customer_liquid, user_labware, "Tf", sample_counts, 60, move_to_location,
                        serial_module, pressure_setting=USER_PRESSURE['step9'])
        """三、执行实验步骤(移液&正压)
        10. 向样本处理器中加入60ul试剂 Wa
        """
        transform_round(left_pipette, customer_liquid, user_labware, "Wa", sample_counts, 60, move_to_location,
                        serial_module, drop_method=DropMethod.DoNotDrop, pressure_setting=USER_PRESSURE['step10'])
        """三、执行实验步骤(移液&正压)
        11. 向样本处理器中加入60ul试剂 Wa
        """
        transform_round(left_pipette, customer_liquid, user_labware, "Wa", sample_counts, 60, move_to_location,
                        serial_module, drop_method=DropMethod.DoNotPickUp, pressure_setting=USER_PRESSURE['step11'])
        protocol.pause("请更换收集板...")
        """三、执行实验步骤(移液&正压)
        12. 向样本处理器中加入60ul试剂 Et
        """
        transform_round(left_pipette, customer_liquid, user_labware, "Et", sample_counts, 60, move_to_location,
                        serial_module, pressure_setting=USER_PRESSURE['step12'])
        protocol.pause("实验结束...恢复即将复位设备...")
    if serial_module.device is not None:
        protocol.comment(">>>>>4.实验结束<<<<<")
        serial_module.release_device()
