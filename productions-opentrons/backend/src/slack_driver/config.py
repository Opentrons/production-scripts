import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any
from settings import get_logger, SLACK_CONFIG_PATH

logger = get_logger(__name__)


@dataclass
class SlackConfig:
    bot_token: str
    default_channel: str
    bot_name: str
    bot_icon: str
    templates: Dict[str, Any]
    
    @classmethod
    def from_yaml(cls, config_path: str | None = None, environment: str = "development"):
        config_path = config_path or SLACK_CONFIG_PATH
        config_file = Path(config_path)
        if not config_file.exists():
            logger.error(f"配置文件不存在: {config_path}")
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(config_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        slack_config = data['slack']

        env_config = slack_config.get('environments', {}).get(environment, {})
        base_config = {k: v for k, v in slack_config.items() if k != 'environments'}

        logger.info(f"成功加载 Slack 配置，environment: {environment}")

        return cls(
            bot_token=env_config.get('bot_token', base_config.get('bot_token')),
            default_channel=env_config.get('default_channel', base_config.get('default_channel')),
            bot_name=env_config.get('bot_name', base_config.get('bot_name')),
            bot_icon=env_config.get('bot_icon', base_config.get('bot_icon')),
            templates=base_config.get('templates', {})
        )


if __name__ == "__main__":
    config = SlackConfig.from_yaml(environment="development")
    print(config.bot_token)
