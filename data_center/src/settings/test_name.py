from ..this_types import TestName, ProductionName

TestNameConfigs = {
    ProductionName.Robot: {
        TestName.AssemblyQC: "",
        TestName.XY_BeltCalibration: "",
        TestName.GantryStress: ""
    },
    ProductionName.P1000M: {
        TestName.AssemblyQC: "",
    },
    ProductionName.P50M: {
        TestName.AssemblyQC: "",
    },
    ProductionName.P50S: {
        TestName.AssemblyQC: "pipette-assembly-qc-ot3",
        TestName.SpeedAndCurrent: "pipette-current-speed-qc-ot3",
        TestName.Gravimetric: "",
    },
    ProductionName.P1000S: {
        TestName.AssemblyQC: "pipette-assembly-qc-ot3",
        TestName.SpeedAndCurrent: "pipette-current-speed-qc-ot3",
        TestName.Gravimetric: "",
    },

}


def get_test_name(production_name: ProductionName, test_name: TestName) -> str:
    # 1. 先检查产品名称是否存在
    if production_name not in TestNameConfigs:
        raise ValueError(f"Unknown production_name: {production_name}")

    # 2. 获取该产品的测试配置
    test_config = TestNameConfigs[production_name]

    # 3. 检查测试名称是否在该产品的配置中
    if test_name not in test_config:
        raise ValueError(
            f"Unknown test_name '{test_name}' for production '{production_name}'. "
            f"Available tests: {list(test_config.keys())}"
        )

    # 4. 返回测试名称
    return test_config[test_name]
