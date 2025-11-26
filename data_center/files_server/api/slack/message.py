from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from datetime import datetime
import requests
import json
from files_server.api.slack import slack_config
from files_server.logs import get_logger

logger = get_logger("slack.send.message")

class SlackBotMessenger:
    def __init__(self, environment="development", webhook_url=None, bot_name=None,
                 bot_icon_emoji=":robot_face:"):
        self.config = slack_config.SlackConfig.from_yaml(environment=environment)
        self.bot_name = self.config.default_channel
        self.bot_icon_emoji = bot_icon_emoji
        self.bot_icon = bot_icon_emoji
        self.token = self.config.bot_token
        self.webhook_url = webhook_url
        
        if self.token:
            self.client = WebClient(token=self.token)
        else:
            self.client = None

    def send_test_result(self, channel, test_type, test_result, serial_number,
                         test_data_link, tracking_sheet_link, custom_bot_name=None):
        """
        发送测试结果消息，显示完整的 Bot 信息
        """
        bot_display_name = custom_bot_name or self.config.bot_name
        logger.info(f"bot name {bot_display_name}")

        try:
            if self.client:
                # 使用 OAuth Token 方式
                return self._send_via_oauth(channel, test_type, test_result, serial_number,
                                            test_data_link, tracking_sheet_link)
            elif self.webhook_url:
                # 使用 Webhook 方式
                return self._send_via_webhook(test_type, test_result, serial_number,
                                              test_data_link, tracking_sheet_link, bot_display_name)
            else:
                logger.info("错误: 未提供 token 或 webhook_url")
                return False

        except Exception as e:
            logger.info(f"发送消息失败: {str(e)}")
            return False

    def _send_via_oauth(self, channel, test_type, test_result, serial_number,
                                 test_data_link, tracking_sheet_link):
        """
        发送测试结果消息框

        Args:
            token (str): Slack Bot Token
            channel (str): 频道ID或名称
            test_type (str): 测试类型
            test_result (str): 测试结果 "Pass" 或 "Fail"
            serial_number (str): 序列号
            test_data_link (str): 测试数据链接
            tracking_sheet_link (str): Tracking Sheet 链接
        """
        try:

            if test_result is not None and test_result.lower() == "pass":
                color_emoji = ":large_green_circle:"
                color_code = "#36a64f"
                status_text = "通过"
            else:
                color_emoji = ":red_circle:"
                color_code = "#fc1c37"
                status_text = "失败"

            blocks = [{
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🧪 测试类型:* {test_type}\n{color_emoji} *测试结果:* {test_result} ({status_text})"
                }
            }, {
                "type": "divider"
            }, {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"📋 *序列号:* `{serial_number}`"
                },
            }, {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"📊 *测试数据:* <{test_data_link}|查看测试数据>"
                }
            }, {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"📁 *Tracking Sheet:* <{tracking_sheet_link}|打开 Tracking Sheet>"
                }
            }, {
                "type": "context",
                "elements": [
                    {
                        "type": "image",
                        "image_url": "https://api.slack.com/img/blocks/bkb_template_images/notifications.png",
                        "alt_text": "status icon"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"测试完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}| 序列号: `{serial_number}` | 状态: {status_text}"
                    }
                ]
            }]

            # 添加时间戳和状态

            # 使用 attachments 来设置侧边颜色
            attachments = [
                {
                    "color": color_code,
                    "blocks": blocks
                }
            ]

            response = self.client.chat_postMessage(
                channel=channel,
                text=f"{test_type} 测试结果: {test_result} - 序列号: {serial_number}",
                attachments=attachments
            )

            logger.info(f"测试结果消息发送成功！消息ID: {response['ts']}")
            return True

        except SlackApiError as e:
            logger.info(f"Slack API 错误: {e.response['error']}")
            return False

    def _send_via_webhook(self, test_type, test_result, serial_number,
                          test_data_link, tracking_sheet_link, bot_name):
        """使用 Webhook 发送"""
        if test_result is not None and test_result.lower() == "pass":
            color = "#36a64f"
        else:
            color = "#fc1c37"

        attachments = [
            {
                "color": color,
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*🧪 测试类型:* {test_type}\n*测试结果:* {test_result}"
                        }
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*📋 序列号:*\n`{serial_number}`"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*📊 测试数据:* <{test_data_link}|查看测试数据>"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*📁 Tracking Sheet:* <{tracking_sheet_link}|打开 Tracking Sheet>"
                            }
                        ]
                    },
                ]
            }
        ]

        payload = {
            "text": f"{test_type} 测试结果: {test_result} - 序列号: {serial_number}",
            "attachments": attachments,
            "username": bot_name,
            "icon_emoji": self.bot_icon
        }

        response = requests.post(
            self.webhook_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            logger.info(f"Webhook 消息发送成功！Bot: {bot_name}")
            return True
        else:
            logger.info(f"发送失败: {response.status_code}")
            return False


# 使用示例
if __name__ == "__main__":
    # 方式1: 使用 OAuth Token
    bot = SlackBotMessenger()

    # 发送测试通过消息
    bot.send_test_result(
        channel="production-data-center",
        test_type="Pipette Gravimetric Test",
        test_result="Pass",
        serial_number="P50SV3620250101A01",
        test_data_link="https://docs.google.com/spreadsheets/d/...",
        tracking_sheet_link="https://docs.google.com/spreadsheets/d/..."
    )
