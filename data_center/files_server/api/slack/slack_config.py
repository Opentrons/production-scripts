import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class SlackConfig:
    bot_token: str
    default_channel: str
    bot_name: str
    bot_icon: str
    templates: Dict[str, Any]

    @classmethod
    def from_yaml(cls, config_path: str = "/files_server/slack.yaml", environment: str = "development"):
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(config_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        slack_config = data['slack']

        env_config = slack_config.get('environments', {}).get(environment, {})
        base_config = {k: v for k, v in slack_config.items() if k != 'environments'}

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