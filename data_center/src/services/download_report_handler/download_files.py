import os
import stat
import asyncio
from typing import Union, List, Optional, Callable, Dict, Any
from typing import Tuple
from ...settings import settings, TestNameConfigs, get_logger, setup_logging
from .driver import ParamikoDriver
from ...utils import *
from ...this_types import TestName, ProductionName, UploadOneUnitInterface
from datetime import datetime

logger = get_logger('file.handler')


class FilesHandler:
    def __init__(self, _client: ParamikoDriver):
        self.sshClient = _client
        self.remote_data = settings.remote_data_path
        self.ssh = self.sshClient.ssh
        self.sftp = self.sshClient.sftp

    async def list_dir(self, remote_dir) -> Union[bool, List[str]]:
        """列出远程目录的文件夹"""
        try:
            files = self.sftp.listdir(remote_dir)
            return files
        except Exception as e:
            logger.error(f"无法列出文件: {e}")
            return False

    async def list_files(
            self,
            remote_dir: str,
            recursive: bool = True,
            include_dirs: bool = False
    ) -> Union[bool, List[str]]:
        """
        列出远程目录的所有文件

        Args:
            remote_dir: 远程目录路径
            recursive: 是否递归列出子目录中的文件
            include_dirs: 返回结果中是否包含目录名

        Returns:
            - bool False: 列出失败
            - List[str]: 文件列表（如果recursive=True，则包含子目录中的文件）
        """
        try:
            # 确保路径标准化
            remote_dir = normalize_path(remote_dir)

            logger.debug(f"列出目录: {remote_dir}, 递归: {recursive}")

            # 获取目录内容
            items = self.sftp.listdir(remote_dir)
            all_files = []

            for item in items:
                item_path = f"{remote_dir}/{item}"

                try:
                    # 检查是文件还是目录
                    stat = self.sftp.stat(item_path)

                    if stat.st_mode & 0o40000 != 0:  # 是目录
                        if include_dirs:
                            all_files.append(item_path)

                        if recursive:
                            # 递归列出子目录中的文件
                            sub_files = await self.list_files(item_path, recursive=True, include_dirs=include_dirs)
                            if isinstance(sub_files, list):
                                all_files.extend(sub_files)
                            else:
                                logger.warning(f"无法列出子目录: {item_path}")

                    elif stat.st_mode & 0o100000 != 0:  # 是文件
                        all_files.append(item_path)

                except Exception as e:
                    logger.warning(f"处理项失败 {item}: {e}")
                    continue

            logger.debug(f"找到 {len(all_files)} 个文件/目录")
            return all_files

        except Exception as e:
            logger.error(f"无法列出文件 {remote_dir}: {e}")
            return False

    async def _is_dir(self, remote_path):
        """检查远程路径是否是目录"""
        try:
            return stat.S_ISDIR(self.sftp.stat(remote_path).st_mode)
        except IOError:
            return False
        except Exception as e:
            logger.error(f'List dir Fail, {e}')
            return False

    async def is_connected(self):
        return self.sshClient.is_connected()

    async def remote_dir_exists(self, dir_path: str) -> bool:
        """
        检查远程目录是否存在

        Args:
            dir_path: 远程目录绝对路径

        Returns:
            bool: 目录是否存在
        """
        try:
            # 获取目录属性（会跟随符号链接）
            attrs = self.sftp.stat(dir_path)
            return attrs.st_mode & 0o40000  # 检查是否是目录
        except FileNotFoundError:
            return False
        except Exception as e:
            logger.error(f"检查目录出错: {e}")
            return False

    async def rename_dir(self, dir_name, rename):
        """
        rename
        """
        try:
            if await self.remote_dir_exists(dir_name):
                self.sshClient.sftp.rename(dir_name, rename)
                return True
            else:
                return False
        except Exception as e:
            logger.error(f'重命名失败，${e}')

    def _is_remote_dir(self, remote_path: str) -> bool:
        """检查远程路径是否为目录"""
        try:
            stat = self.sftp.stat(remote_path)
            return stat.st_mode & 0o40000 != 0  # 检查目录位
        except Exception as e:
            logger.error(f"检查目录失败 {remote_path}: {e}")
            return False

    def _is_remote_file(self, remote_path: str) -> bool:
        """检查远程路径是否为文件"""
        try:
            stat = self.sftp.stat(remote_path)
            return stat.st_mode & 0o100000 != 0  # 检查普通文件位
        except Exception as e:
            logger.error(f"检查文件失败 {remote_path}: {e}")
            return False

    async def download_remote_directory(
            self,
            remote_dir: str,
            local_dir: str,
            max_depth: int = 10,
            include_hidden: bool = False,
            pattern_filter: Optional[str] = None,
            progress_callback: Optional[Callable[[Dict], None]] = None
    ) -> Dict[str, Any]:
        """
        递归下载远程目录中的所有文件和子目录

        Args:
            remote_dir: 远程目录路径
            local_dir: 本地保存目录
            max_depth: 最大递归深度
            include_hidden: 是否包含隐藏文件（以.开头的文件）
            pattern_filter: 文件模式过滤（如 "*.py"）
            progress_callback: 进度回调函数

        Returns:
            下载统计信息
        """
        if not await self.is_connected():
            return {
                'success': False,
                'message': '未建立连接',
                'stats': {
                    'total_dirs': 0,
                    'total_files': 0,
                    'downloaded_files': 0,
                    'failed_files': 0,
                    'skipped_files': 0,
                    'total_size': 0,
                    'failed_items': []
                }
            }

        # 标准化路径
        remote_dir = normalize_path(remote_dir)
        local_dir = os.path.abspath(local_dir)

        # 检查远程目录是否存在
        if not self._is_remote_dir(remote_dir):
            return {
                'success': False,
                'message': f'远程目录不存在或不是目录: {remote_dir}',
                'stats': {
                    'total_dirs': 0,
                    'total_files': 0,
                    'downloaded_files': 0,
                    'failed_files': 0,
                    'skipped_files': 0,
                    'total_size': 0,
                    'failed_items': []
                }
            }

        logger.info(f"开始下载目录: {remote_dir} -> {local_dir}")

        # 创建本地目录
        os.makedirs(local_dir, exist_ok=True)

        # 初始化统计信息
        stats = {
            'total_dirs': 0,
            'total_files': 0,
            'downloaded_files': 0,
            'failed_files': 0,
            'skipped_files': 0,
            'total_size': 0,
            'failed_items': [],
            'start_time': datetime.now(),
            'local_path': local_dir,
        }

        try:
            # 递归处理目录
            await self._process_directory_recursive(
                remote_dir=remote_dir,
                local_dir=local_dir,
                current_depth=0,
                max_depth=max_depth,
                include_hidden=include_hidden,
                pattern_filter=pattern_filter,
                stats=stats,
                progress_callback=progress_callback
            )

            # 计算耗时
            stats['end_time'] = datetime.now()
            stats['duration'] = (stats['end_time'] - stats['start_time']).total_seconds()

            # 生成结果消息
            if stats['failed_files'] == 0:
                message = (
                    f"下载完成。目录: {stats['total_dirs']} 个，"
                    f"文件: {stats['downloaded_files']}/{stats['total_files']} 个，"
                    f"大小: {format_bytes(stats['total_size'])}，"
                    f"耗时: {stats['duration']:.1f}秒"
                )
                success = True
            else:
                message = (
                    f"下载部分完成。目录: {stats['total_dirs']} 个，"
                    f"成功: {stats['downloaded_files']} 个文件，"
                    f"失败: {stats['failed_files']} 个文件，"
                    f"跳过: {stats['skipped_files']} 个文件"
                )
                success = False

            return {
                'success': success,
                'message': message,
                'stats': stats
            }

        except Exception as e:
            logger.error(f"下载目录失败: {e}")
            return {
                'success': False,
                'message': f'下载过程中发生错误: {e}',
                'stats': stats
            }

    async def _process_directory_recursive(
            self,
            remote_dir: str,
            local_dir: str,
            current_depth: int,
            max_depth: int,
            include_hidden: bool,
            pattern_filter: Optional[str],
            stats: Dict[str, Any],
            progress_callback: Optional[Callable[[Dict], None]]
    ):
        """递归处理目录"""
        if current_depth >= max_depth:
            logger.warning(f"达到最大深度 {max_depth}: {remote_dir}")
            return

        try:
            # 列出目录内容
            items = self.sftp.listdir(remote_dir)

            # 处理每个项目
            for item in items:
                # 跳过隐藏文件（如果设置）
                if not include_hidden and item.startswith('.'):
                    continue

                remote_path = f"{remote_dir}/{item}"
                local_path = os.path.join(local_dir, item)

                try:
                    # 获取文件信息
                    stat = self.sftp.stat(remote_path)

                    # 检查是否是目录
                    if stat.st_mode & 0o40000 != 0:  # 是目录
                        stats['total_dirs'] += 1

                        # 创建本地目录
                        os.makedirs(local_path, exist_ok=True)

                        # 递归处理子目录
                        await self._process_directory_recursive(
                            remote_dir=remote_path,
                            local_dir=local_path,
                            current_depth=current_depth + 1,
                            max_depth=max_depth,
                            include_hidden=include_hidden,
                            pattern_filter=pattern_filter,
                            stats=stats,
                            progress_callback=progress_callback
                        )

                    elif stat.st_mode & 0o100000 != 0:  # 是普通文件
                        stats['total_files'] += 1

                        # 检查文件过滤
                        if pattern_filter and not match_pattern(item, pattern_filter):
                            stats['skipped_files'] += 1
                            continue

                        # 下载文件
                        success = await self._download_single_file(
                            remote_path=remote_path,
                            local_path=local_path,
                            file_size=stat.st_size
                        )

                        if success:
                            stats['downloaded_files'] += 1
                            stats['total_size'] += stat.st_size

                            # 调用进度回调
                            if progress_callback:
                                progress_data = {
                                    'current_file': item,
                                    'current_path': remote_path,
                                    'current_size': stat.st_size,
                                    'downloaded_files': stats['downloaded_files'],
                                    'total_files': stats['total_files'],
                                    'failed_files': stats['failed_files'],
                                    'total_size': stats['total_size'],
                                    'progress_percent': (stats['downloaded_files'] / max(stats['total_files'], 1)) * 100
                                }
                                progress_callback(progress_data)
                        else:
                            stats['failed_files'] += 1
                            stats['failed_items'].append({
                                'path': remote_path,
                                'error': '下载失败'
                            })

                    else:  # 其他类型（如符号链接、设备文件等）
                        logger.warning(f"跳过非普通文件/目录: {remote_path}")
                        stats['skipped_files'] += 1

                except Exception as e:
                    logger.error(f"处理项目失败 {item}: {e}")
                    stats['failed_files'] += 1
                    stats['failed_items'].append({
                        'path': remote_path,
                        'error': str(e)
                    })

        except Exception as e:
            logger.error(f"列出目录失败 {remote_dir}: {e}")
            stats['failed_items'].append({
                'path': remote_dir,
                'error': f"无法列出目录: {e}"
            })

    async def _download_single_file(
            self,
            remote_path: str,
            local_path: str,
            file_size: int
    ) -> bool:
        """下载单个文件"""
        try:
            logger.debug(f"下载文件: {remote_path} -> {local_path}")

            # 检查文件是否已存在且完整
            if os.path.exists(local_path):
                local_size = os.path.getsize(local_path)
                if local_size == file_size:
                    logger.debug(f"文件已存在且完整，跳过: {local_path}")
                    return True

            # 创建本地目录（如果不存在）
            local_dir = os.path.dirname(local_path)
            os.makedirs(local_dir, exist_ok=True)

            # 下载文件
            self.sftp.get(remote_path, local_path)

            # 验证下载
            if os.path.exists(local_path):
                downloaded_size = os.path.getsize(local_path)
                if downloaded_size == file_size:
                    logger.info(f"下载成功: {remote_path} ({file_size} bytes)")
                    return True
                else:
                    logger.error(f"文件大小不匹配: 期望 {file_size}, 实际 {downloaded_size}")
                    # 删除不完整的文件
                    try:
                        os.remove(local_path)
                    except:
                        pass
                    return False
            else:
                logger.error(f"文件未创建: {local_path}")
                return False

        except Exception as e:
            logger.error(f"下载文件失败 {remote_path}: {e}")
            return False

    def list_remote_directory(self, remote_dir: str) -> Dict[str, Any]:
        """列出远程目录内容（用于调试）"""
        remote_dir = normalize_path(remote_dir)

        result = {
            'path': remote_dir,
            'exists': False,
            'is_directory': False,
            'items': []
        }

        try:
            # 检查路径状态
            stat = self.sftp.stat(remote_dir)
            result['exists'] = True
            result['is_directory'] = stat.st_mode & 0o40000 != 0

            if result['is_directory']:
                # 列出目录内容
                items = self.sftp.listdir(remote_dir)

                for item in items:
                    item_path = f"{remote_dir}/{item}"
                    try:
                        item_stat = self.sftp.stat(item_path)

                        item_info = {
                            'name': item,
                            'is_directory': item_stat.st_mode & 0o40000 != 0,
                            'is_file': item_stat.st_mode & 0o100000 != 0,
                            'size': item_stat.st_size if item_stat.st_mode & 0o100000 != 0 else 0,
                            'permissions': oct(item_stat.st_mode & 0o777),
                            'modified_time': datetime.fromtimestamp(item_stat.st_mtime).isoformat()
                        }
                        result['items'].append(item_info)

                    except Exception as e:
                        item_info = {
                            'name': item,
                            'error': str(e)
                        }
                        result['items'].append(item_info)

            return result

        except FileNotFoundError:
            result['error'] = "路径不存在"
            return result
        except Exception as e:
            result['error'] = str(e)
            return result

    async def delete_file(self, remote_path):
        """删除远程文件"""
        try:
            self.sftp.remove(remote_path)
            return True
        except Exception as e:
            logger.error(f"删除文件失败: {e}")
            return False

    async def delete_dir(self, remote_dir: str):
        files = self.sftp.listdir(remote_dir)
        if len(files) == 0:
            logger.info("文件夹目录为空, 删除跳出...")
            return

        for item in self.sftp.listdir(remote_dir):
            remote_path = os.path.join(remote_dir, item).replace('\\', '/')
            if await self._is_dir(remote_path):
                await self.delete_dir(remote_path)  # 递归处理子目录
            else:
                await self.delete_file(remote_path)
                # 删除空目录
                files = self.sshClient.sftp.listdir(remote_dir)
                if len(files) == 0:
                    try:
                        self.sshClient.sftp.rmdir(remote_dir)
                        logger.info(f"删除成功: {remote_dir}")
                    except Exception as e:
                        logger.info(f"删除失败: {e}")
                else:
                    pass

    async def download_testing_data(self) -> Union[bool, str]:
        """
        download the testing data and zip the data
        """
        download_path = settings.saved_data_path
        download_path = normalize_path(contact_path(download_path, 'testing_data' + "_" + get_time_str()))
        result = await self.download_remote_directory(self.remote_data, download_path)
        success_path = result['stats']['local_path']
        if result['success']:
            logger.info(f"下载成功: {result['message']}")
            logger.info(f"本地路径：: {success_path}")
            return success_path
        else:
            logger.error(f"下载失败: {result['message']}")
            return False

    async def is_production_exist(
            self,
            production: ProductionName,
            test_name: TestName,
            sn: str
    ) -> Union[bool, List[str]]:
        """
        判断产品的测试数据是否存在

        Args:
            production: 产品名称
            test_name: 测试名称
            sn: 序列号

        Returns:
            - bool False: 产品、测试名或序列号不存在
            - List[str]: 包含该序列号的所有文件路径列表
        """
        try:
            # 1. 检查产品和测试名配置
            if production not in TestNameConfigs:
                logger.error(f"产品 '{production}' 不存在于配置中")
                return False

            production_config = TestNameConfigs.get(production)
            if test_name not in production_config:
                logger.error(f"测试名 '{test_name}' 在产品 '{production}' 中不存在")
                return False

            # 2. 获取文件夹名称
            folder_name = production_config.get(test_name)
            if not folder_name:
                logger.error(f"无法获取测试名 '{test_name}' 对应的文件夹名称")
                return False

            # 3. 构建远程路径并标准化
            root_folder = contact_path(self.remote_data, folder_name)
            root_folder = normalize_path(root_folder)

            logger.debug(f"检查路径: {root_folder}, 序列号: {sn}")

            # 4. 检查远程目录是否存在
            if not await self.remote_dir_exists(root_folder):
                logger.warning(f"远程目录不存在: {root_folder}")
                return False

            # 5. 列出目录下的所有文件
            files = await self.list_files(root_folder)
            if not files:
                logger.warning(f"目录为空: {root_folder}")
                return False

            logger.debug(f"目录中找到 {len(files)} 个文件")

            # 6. 搜索包含序列号的文件
            matching_files = []
            for file in files:
                try:
                    # 检查文件名是否包含序列号
                    if sn in file:
                        # 构建完整路径
                        if '.csv' in file:
                            matching_files.append(file)
                            logger.debug(f"找到匹配文件: {file}")
                except Exception as e:
                    logger.warning(f"处理文件 '{file}' 时出错: {e}")
                    continue

            # 7. 返回结果
            if matching_files:
                logger.info(f"找到 {len(matching_files)} 个匹配文件，序列号: {sn}")
                return matching_files
            else:
                logger.warning(f"未找到包含序列号 '{sn}' 的文件")
                return False

        except ValueError as e:
            logger.error(f"配置错误: {e}")
            return False
        except Exception as e:
            logger.error(f"检查产品存在性时发生未知错误: {e}")
            return False

    async def download_test_unit(self, production: ProductionName, test_name: TestName, sn: str) \
            -> Optional[UploadOneUnitInterface]:
        """
        基于sn和测试名字只下载对应的测试结果，下载完删除机器里面的源文件
        :param production:
        :param test_name:
        :param sn:
        :return:
        """
        filenames = await self.is_production_exist(production, test_name, sn)
        if not filenames:
            return None
        if len(filenames) > 1:
            logger.warning(f"找到多个匹配目标 {sn}，将跳过前面，只取最后一个目标上传")
        filename = filenames[-1]
        dir_name = get_base_name(filename)
        download_path = settings.saved_data_path
        download_path = normalize_path(contact_path(download_path, TestNameConfigs[production][test_name] + '-' + sn))
        result = await self.download_remote_directory(dir_name, download_path)
        success_path = result['stats']['local_path']
        if result['success']:
            logger.info(f"下载成功: {result['message']}")
            logger.info(f"本地路径：: {success_path}")
            # 打包
            zip_path = zip_directory(success_path)
            return UploadOneUnitInterface(
                file_local=contact_path(success_path, filename.split('/')[-1]),
                file_local_path=success_path,
                production_name=production,
                test_name=test_name,
                sn=sn,
                zip_path=zip_path
            )
        else:
            logger.error(f"下载失败: {result['message']}")
            return None

    async def test_download(self):
        # download testing data
        setup_logging()
        # result = await  self.download_testing_data()
        result = await self.download_test_unit(ProductionName.P1000CH1, TestName.AssemblyQC, 'P1KSV3620251222A14')


if __name__ == '__main__':
    client = ParamikoDriver(host='192.168.0.96', port=22, username='root', password='root')
    fh = FilesHandler(client)
    asyncio.run(fh.test_download())
