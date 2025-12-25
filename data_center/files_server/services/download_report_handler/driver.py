import paramiko
from ...settings import get_logger
from paramiko.ssh_exception import BadAuthenticationType
from ...utils import get_key
import io

logger = get_logger('services.drive')


class ParamikoDriver:
    def __init__(self, host, username, password=None, port=22):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.ssh = None
        self.sftp = None
        self.connect()

    def connect(self, timeout=10):
        """建立 SSH 和 SFTP 连接"""
        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            if not self.password:
                self.password = "None"
            self.ssh.connect(self.host, port=self.port, username=self.username, password=self.password, timeout=timeout)
            self.sftp = self.ssh.open_sftp()
            logger.info(f'{self.host} Connected')
            return True
        except BadAuthenticationType:
            try:
                key_data = get_key()
                key = paramiko.RSAKey.from_private_key(io.StringIO(key_data.decode("utf-8")))
                self.ssh.connect(self.host, port=self.port, username=self.username, password=self.password,
                                 timeout=timeout, pkey=key)
                self.sftp = self.ssh.open_sftp()
                return True
            except Exception as e:
                logger.error(f'{self.host} connection fail with public key, {e}')
                return False
        except Exception as error:
            logger.error(f'Connect Fail, {error}')

    def ensure_connection(self):
        """确保连接有效，如果断开则重连"""
        try:
            # 检查连接是否活跃
            if hasattr(self, 'sftp') and self.sftp:
                self.sftp.stat('.')  # 尝试执行一个简单操作
                logger.info("连接正常")
                return True
        except (AttributeError, paramiko.SSHException, EOFError):
            pass

        # 连接已断开，重新连接
        try:
            logger.info("连接已经断开，正在重连")
            self.close()  # 先关闭可能的残留连接
            success, message = self.connect()
            return success
        except Exception as e:
            logger.info(f"重连失败: {e}")
            return False

    def close(self):
        """关闭连接"""
        try:
            if self.sftp:
                self.sftp.close()
            if self.ssh:
                self.ssh.close()
            logger.info("连接已关闭")
        except Exception as error:
            logger.error(f'关闭连接失败，${error}')
