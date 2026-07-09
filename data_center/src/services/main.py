from .download_report_handler import FilesHandler
from .download_report_handler import ParamikoDriver
from typing import Optional, List
from ..database import CollectionManager
from .google_driver_handler import updata_class
from ..settings import settings, get_logger, get_test_name
from ..this_types import UploadResult, UploadOneUnitInterface, TestPlanInterface, ProductionName, TestName
from ..product_name import normalize_product_name
from .slack import SlackBotMessenger
from datetime import datetime
from .flex_communications import scan_flex
import asyncio

logger = get_logger('service')


class ServiceHandler:
    def __init__(self):
        self.download_handler: Optional[FilesHandler] = None
        self.database_manager = CollectionManager()
        self.upload_handler: Optional[updata_class] = None
        self.slack: Optional[SlackBotMessenger] = None

    async def init_database(self):
        # 初始化数据库
        if self.database_manager.params is None or self.database_manager.test_plan is None:
            await self.database_manager.init_collection()

    async def init_service(self, hostname: str):
        # 初始化文件下载
        if self.download_handler is None:
            self.download_handler = FilesHandler(ParamikoDriver(hostname))
        else:
            self.download_handler.sshClient = ParamikoDriver(hostname)
        # 初始化数据库
        if self.database_manager.params is None or self.database_manager.test_plan is None:
            await self.database_manager.init_collection()
        # 初始化google drive连接
        if self.upload_handler is None:
            self.upload_handler = updata_class(settings.upload_env)
            self.upload_handler.star_int()
        # 初始化slack
        if self.slack is None:
            self.slack = SlackBotMessenger()
        logger.info('init service success !')

    def set_upload_process(self, progress: int, sn: str):
        """
        更新上传的进度
        :param progress:
        :param sn:
        :return:
        """
        self.database_manager.test_plan.set_database_filed(
            {"barcode": sn}, {"auto_upload": progress})

    async def upload_target(self, unit: UploadOneUnitInterface):
        """
        上传单个单元到服务器
        :param unit:
        :return:
        """
        logger.info(f"Starting to upload {unit.file_local}!")
        this_unit_name = get_test_name(unit.production_name, unit.test_name)
        production_name = normalize_product_name(unit.production_name.value)
        result = self.upload_handler.update_data_to_google_drive(
            unit.file_local, unit.sn, production_name, unit.zip_path, this_unit_name,
            func_callback=self.set_upload_process, csv_link=unit.csv_id)
        result_handler = UploadResult(**result)
        # 上传后把数据链接写入数据库
        self.database_manager.test_plan.set_database_filed(
            {"barcode": unit.sn}, {"link": result_handler.sheet_link})

        if result_handler.success:
            logger.info("=======================================================")
            logger.info(f"上传成功, sheet link: {result_handler.sheet_link}")
            logger.info("=======================================================")
            # slack 更新消息
            bot = SlackBotMessenger()
            # 发送测试通过消息
            bot.send_test_result(
                channel="production-data-center",
                test_type=this_unit_name,
                test_result=result_handler.test_result if result_handler is not None else "None",
                serial_number=unit.sn,
                test_data_link=result_handler.sheet_link if result_handler.sheet_link is not None else "None",
                tracking_sheet_link=result_handler.tracking_sheet if result_handler.tracking_sheet is not None else "None"
            )

    async def run_trial(self, test_plan: TestPlanInterface):
        """
        运行一个上传的所有流程, 目前的流程是员工填写上传计划，然后读取计划表
        1. 当前计划的填写时间是否是服务器时间的今天或过去几天填写（通过数据查找过滤）
        2. 当前计划表的uploaded参数是否为 ‘false’ ,如果已经上传则自动跳过
        :param test_plan: 上传plan单元的参数
        :return:
        """
        # 判断上传单元是否已上传
        auto_upload = test_plan.auto_upload == 100
        if auto_upload:
            logger.info(f"{test_plan.barcode}, {test_plan.test_name} already uploaded")
            return
        plan_date = test_plan.date
        current_date = datetime.now().strftime("%Y-%m-%d")
        # 只允许当天填写的可以上传
        if plan_date != current_date:
            logger.info(f"{test_plan.barcode}, {test_plan.test_name} out of date")
            return
        # Note: 每个单元对应的服务器不一样，hostname都会改变，所以需要每次都重新初始化server
        robot_ip = test_plan.fixture_ip
        sn = test_plan.barcode
        production = normalize_product_name(test_plan.product)
        if robot_ip == "":
            flex_group = scan_flex()
            # 使用 next() + 生成器表达式查找匹配的 IP
            robot_ip = next(
                (ip for ip, val in flex_group.items() if val["name"] == test_plan.fixture_name),
                None  # 如果没有匹配项，返回 None
            )
        if robot_ip is None:
            raise ValueError("robot ip is None")
        await self.init_service(robot_ip)
        # 用户运行一个test plan包含多个测试名，所以一个sn下可以遍历上传多个测试任务
        for test_name in test_plan.test_name:
            try:
                self.download_handler.sshClient.ensure_connection()
                # 获取production, test name
                _production = ProductionName.get_production_by_value(production)
                _test_name = TestName.get_test_name_by_value(test_name)
                if _production is None or _test_name is None:
                    raise Exception(f"获取测试 {production} or {test_name} fail")
                unit = await self.download_handler.download_test_unit(_production, _test_name, sn)
                # NOTE: 同一个条码的不同测试应该放到同一个csv sheet里面， 假如当前的测试已经生成了一个表格，那么接下来上传的测试
                # 应该在同一个表格里面填入，upload handler通过判断csv id是否存在来觉得是否新建一个表格模板填入数据。
                # 此时应该判断数据库里面是否已经存在csv id, 若有，把csv id传入上传unit里面
                _link = self.database_manager.test_plan.find_by_condition({"barcode": sn})[0]["link"]
                if _link == "":
                    pass
                else:
                    unit.csv_id = _link
                await self.upload_target(unit)
            except Exception as e:
                logger.info(f"上传下载 {sn}, {test_name} 失败, {e}")
        return

    async def run_trials(self):
        # 1. 遍历获取当日的test plan，然后将test plan放到线程池
        logger.info("run trials")
        await self.init_database()
        this_date = datetime.now().strftime("%Y-%m-%d")
        # 正确：使用filter_query参数查询当天的计划
        collections = self.database_manager.test_plan.find_all(
            filter_query={'date': this_date},
            limit=100
        )
        logger.info(f"查询到 {this_date} collections: {len(collections)}个")
        # 创建任务列表
        tasks: List[asyncio.Task] = []
        semaphore = asyncio.Semaphore(10)  # 控制并发数

        async def run_with_semaphore(test_plan_dict):
            """使用信号量控制并发的包装函数"""
            async with semaphore:
                test_plan = TestPlanInterface(**test_plan_dict)
                try:
                    await self.run_trial(test_plan)
                except Exception as e:
                    logger.error(f"运行测试计划失败: {e}")

        # 创建所有任务
        for collection in collections:
            task = asyncio.create_task(run_with_semaphore(collection))
            tasks.append(task)
        # 等待所有任务完成
        await asyncio.gather(*tasks, return_exceptions=True)

    async def download_and_upload_cycling(self):
        """
        循环读取和上传
        :return:
        """
        await self.init_database()
        number = 0
        while True:
            # step1 读取开关状态，是否需要打开自动上传开关
            logger.info("=" * 20)
            logger.info(f"Starting Cycle - {number + 1}")
            logger.info("=" * 20)
            is_turn_on = self.database_manager.params.auto_upload
            if is_turn_on:
                # step2 读取test plan table
                await self.run_trials()
            else:
                logger.info("Auto upload closed")
            await asyncio.sleep(settings.cycle_delay_min * 60)
            number += 1

    def close(self):
        """
        #TODO
        :return:
        """
        pass


if __name__ == '__main__':
    pass
