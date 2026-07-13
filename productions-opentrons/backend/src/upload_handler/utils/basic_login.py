import os
import sys
from pathlib import Path
from settings import TOKEN_PATH, get_logger

SRC_DIR = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

logger = get_logger(__name__)
GOOGLE_HEALTH_CHECK_URL = os.getenv(
    "GOOGLE_HEALTH_CHECK_URL",
    "https://www.googleapis.com/discovery/v1/apis/drive/v3/rest",
)
GOOGLE_HEALTH_CHECK_TIMEOUT_SECONDS = int(os.getenv("GOOGLE_HEALTH_CHECK_TIMEOUT_SECONDS", "30"))

def update_best_proxy():
    """运行代理测试，找到延迟最低的代理并更新配置文件"""
    try:
        import importlib.util
        # 动态导入 ghelper-test/node_test.py
        spec = importlib.util.spec_from_file_location(
            "node_test",
            BACKEND_ROOT / "ghelper-test" / "node_test.py"
        )
        node_test_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(node_test_module)

        get_best_proxy_and_update_config = node_test_module.get_best_proxy_and_update_config
        logger.info("开始测试代理节点延迟...")
        best_node, best_proxy_url = get_best_proxy_and_update_config(max_threads=10, update_subscription=True)
        if best_proxy_url:
            from upload_handler.utils import runtime_config

            runtime_config.reload_proxy_config()
            logger.info("已选择最佳代理: %s", getattr(best_node, "name", "unknown"))
            return True
        else:
            logger.warning("没有找到可用的代理节点")
            return False
    except Exception as e:
        logger.error(f"更新代理配置失败: {e}")
        return False

def google_drive_health_check():
    """
    检查 Google Drive 鉴权和 Google API 连通性。

    Health check 只验证现有 token 是否可用/可刷新，以及 Google API 是否可达；
    不初始化完整 Drive/Sheets client，不列文件，也不触发浏览器 OAuth 授权。
    """
    try:
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2.credentials import Credentials
        from upload_handler.drivers.google_drive import select_google_proxy_url
        from upload_handler.utils import runtime_config

        if not os.path.exists(TOKEN_PATH):
            logger.warning("Google token file not found: %s", TOKEN_PATH)
            return False

        proxy_url = select_google_proxy_url()
        auth_request = runtime_config.build_google_auth_request(proxy_url)
        creds = Credentials.from_authorized_user_file(TOKEN_PATH)
        if not creds.valid:
            if not (creds.expired and creds.refresh_token):
                logger.warning("Google token is invalid and cannot be refreshed")
                return False

            creds.refresh(auth_request)
            with open(TOKEN_PATH, "w", encoding="utf-8") as token_file:
                token_file.write(creds.to_json())
            logger.info("Google token refreshed during health check")

        session = AuthorizedSession(creds, auth_request=auth_request)
        proxies = runtime_config.proxies_from_url(proxy_url)
        if proxies:
            session.proxies.update(proxies)
            logger.info("Using proxy for Google health check: %s", runtime_config.get_proxy_label())

        response = session.get(
            GOOGLE_HEALTH_CHECK_URL,
            timeout=GOOGLE_HEALTH_CHECK_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        logger.info("Google health check passed: auth valid and API reachable")
        return True
    except Exception as e:
        logger.error(f"Google driver health check failed: {e}")
        return False

if __name__ == "__main__":
    from settings import setup_logging
    setup_logging()
    google_drive_health_check()
