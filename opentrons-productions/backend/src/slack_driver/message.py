from __future__ import annotations

import json
import socket
from datetime import datetime

import requests
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

import settings as setting
from settings import get_logger, setup_logging

from .config import SlackConfig

logger = get_logger("slack.message")

FAIL_COLOR = "#fc1c37"
ERROR_TEXT_LIMIT = 1800


def _display_value(value: str | None, fallback: str = "N/A") -> str:
    text = str(value or "").strip()
    return text or fallback


def _truncate_text(text: str, limit: int = ERROR_TEXT_LIMIT) -> str:
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:limit]}\n...(已截断，完整内容见服务器日志)"


def _format_bool_status(value: bool | None) -> str:
    if value is True:
        return "成功"
    if value is False:
        return "失败"
    return "未知"


def _build_runtime_context() -> str:
    hostname = socket.gethostname()
    return (
        f"服务器: `{setting.DATA_HANDLER_HOST}` | "
        f"主机名: `{hostname}` | "
        f"环境: `{setting.RUN_ENV}` | "
        f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )


def build_failure_blocks(
    *,
    error: str,
    failure_stage: str,
    csv_path: str | None = None,
    zip_path: str | None = None,
    production_name: str | None = None,
    test_type: str | None = None,
    serial_number: str | None = None,
    record_id: str | None = None,
    upload_success: bool | None = None,
    database_success: bool | None = None,
    unit_tracker_status: str | None = None,
    missing_tests: list[str] | None = None,
    hints: list[str] | None = None,
) -> list[dict]:
    error_text = _truncate_text(error)
    blocks: list[dict] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":x: *数据上传失败*\n"
                    f"*失败阶段:* `{failure_stage}`\n"
                    f"*Google 上传:* {_format_bool_status(upload_success)} | "
                    f"*数据库写入:* {_format_bool_status(database_success)}"
                ),
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*错误信息*\n```{error_text}```",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*产品*\n`{_display_value(production_name)}`"},
                {"type": "mrkdwn", "text": f"*测试类型*\n`{_display_value(test_type)}`"},
                {"type": "mrkdwn", "text": f"*序列号*\n`{_display_value(serial_number)}`"},
                {"type": "mrkdwn", "text": f"*上传记录 ID*\n`{_display_value(record_id)}`"},
                {"type": "mrkdwn", "text": f"*CSV 文件*\n`{_display_value(csv_path)}`"},
                {"type": "mrkdwn", "text": f"*Zip 文件*\n`{_display_value(zip_path)}`"},
            ],
        },
    ]

    if unit_tracker_status:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Unit Tracker 状态*\n`{_display_value(unit_tracker_status)}`",
                },
            }
        )

    if missing_tests:
        missing_text = "、".join(missing_tests)
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*未完成组合测试*\n`{missing_text}`",
                },
            }
        )

    if hints:
        hint_lines = "\n".join(f"• {hint}" for hint in hints)
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*排查建议*\n{hint_lines}",
                },
            }
        )

    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": _build_runtime_context(),
                }
            ],
        }
    )
    return blocks

class SlackBotMessenger:
    def __init__(self, environment="development", webhook_url=None, bot_name=None,
                 bot_icon_emoji=":robot_face:", timeout=None):
        logger.info(f"初始化 SlackBotMessenger，environment: {environment}")
        
        self.config = SlackConfig.from_yaml(environment=environment)
        self.bot_name = self.config.default_channel
        self.bot_icon_emoji = bot_icon_emoji
        self.bot_icon = bot_icon_emoji
        self.token = self.config.bot_token
        self.webhook_url = webhook_url
        
        if self.token:
            self.client = WebClient(token=self.token, timeout=timeout)
            logger.info("Slack OAuth Token 已加载，WebClient 已初始化")
        else:
            self.client = None
            logger.warning("未提供 bot_token，将使用 Webhook 方式发送消息")

    def send_test_result(self, channel, test_type, test_result, serial_number,
                         test_data_link, tracking_sheet_link, custom_bot_name=None,
                         message_title=None):
        """
        发送测试结果消息，显示完整的 Bot 信息
        """
        logger.info(f"准备发送测试结果 - 频道: {channel}, 类型: {test_type}, 结果: {test_result}, 序列号: {serial_number}")
        
        bot_display_name = custom_bot_name or self.config.bot_name
        logger.debug(f"bot name {bot_display_name}")

        try:
            if self.client:
                logger.debug("使用 OAuth Token 方式发送消息")
                return self._send_via_oauth(
                    channel,
                    test_type,
                    test_result,
                    serial_number,
                    test_data_link,
                    tracking_sheet_link,
                    message_title=message_title,
                )
            elif self.webhook_url:
                logger.debug("使用 Webhook 方式发送消息")
                return self._send_via_webhook(
                    test_type,
                    test_result,
                    serial_number,
                    test_data_link,
                    tracking_sheet_link,
                    bot_display_name,
                    message_title=message_title,
                )
            else:
                logger.error("未提供 token 或 webhook_url，无法发送消息")
                return False

        except Exception as e:
            logger.error(f"发送消息失败: {str(e)}")
            return False

    def send_fail_message(
        self,
        channel,
        *,
        error: str,
        title: str | None = None,
        failure_stage: str = "上传流程",
        csv_path: str | None = None,
        zip_path: str | None = None,
        production_name: str | None = None,
        test_type: str | None = None,
        serial_number: str | None = None,
        record_id: str | None = None,
        upload_success: bool | None = None,
        database_success: bool | None = None,
        unit_tracker_status: str | None = None,
        missing_tests: list[str] | None = None,
        hints: list[str] | None = None,
    ):
        """发送结构化失败消息，便于在 Slack 中快速定位问题。"""
        logger.info(
            "准备发送失败消息 - 频道: %s, 阶段: %s, 序列号: %s",
            channel,
            failure_stage,
            serial_number or "N/A",
        )
        if not self.client:
            logger.error("未提供 bot_token，无法发送失败消息")
            return False

        blocks = build_failure_blocks(
            error=error,
            failure_stage=failure_stage,
            csv_path=csv_path,
            zip_path=zip_path,
            production_name=production_name,
            test_type=test_type,
            serial_number=serial_number,
            record_id=record_id,
            upload_success=upload_success,
            database_success=database_success,
            unit_tracker_status=unit_tracker_status,
            missing_tests=missing_tests,
            hints=hints,
        )
        message_title = title or f"Data Upload Failed ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
        fallback_text = (
            f"{message_title}\n"
            f"阶段: {failure_stage}\n"
            f"错误: {_truncate_text(error, limit=500)}"
        )

        try:
            response = self.client.chat_postMessage(
                channel=channel,
                text=fallback_text,
                attachments=[{"color": FAIL_COLOR, "blocks": blocks}],
            )
            logger.info("失败消息发送成功！消息ID: %s", response["ts"])
            return True
        except SlackApiError as exc:
            logger.error("Slack API 错误: %s", exc.response["error"])
            return False
        except Exception as exc:
            logger.error("发送失败消息失败: %s", exc)
            return False


    def _send_via_oauth(self, channel, test_type, test_result, serial_number,
                        test_data_link, tracking_sheet_link, message_title=None):
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
        logger.debug(f"通过 OAuth 发送消息 - 频道: {channel}")

        try:

            if test_result is not None and test_result.lower() == "pass":
                color_emoji = ":large_green_circle:"
                color_code = "#36a64f"
                status_text = "通过"
            else:
                color_emoji = ":red_circle:"
                color_code = "#fc1c37"
                status_text = "失败"

            logger.debug(f"消息内容 - 测试类型: {test_type}, 状态: {status_text}")

            blocks = [{
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🧪 测试类型:* {test_type.strip()}\n{color_emoji} *测试结果:* {test_result} ({status_text})"
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

            title = message_title or f"Data Upload ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) !"
            response = self.client.chat_postMessage(
                channel=channel,
                text=title,
                attachments=attachments
            )

            logger.info(f"测试结果消息发送成功！消息ID: {response['ts']}")
            return True

        except SlackApiError as e:
            logger.error(f"Slack API 错误: {e.response['error']}")
            return False

    def _send_via_webhook(self, test_type, test_result, serial_number,
                          test_data_link, tracking_sheet_link, bot_name,
                          message_title=None):
        """使用 Webhook 发送"""
        logger.debug(f"通过 Webhook 发送消息 - Bot: {bot_name}")
        
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

        title = message_title or f"{test_type} 测试结果: {test_result} - 序列号: {serial_number}"
        payload = {
            "text": title,
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
            logger.error(f"Webhook 发送失败: {response.status_code}")
            return False


# 使用示例
if __name__ == "__main__":
    # 方式1: 使用 OAuth Token
    setup_logging()
    bot = SlackBotMessenger()
    bot.send_fail_message(
        "production-data-center",
        error="Failed to upload data",
        csv_path="/data/temp/example.csv",
        production_name="Opentrons P1000S",
        test_type="Assembly QC",
        serial_number="P50SV3620250101A01",
        failure_stage="示例阶段",
        hints=["查看 /var/log/data-handler-error.log"],
    )
    # 发送测试通过消息
    # bot.send_test_result(
    #     channel="production-data-center",
    #     test_type="Pipette Gravimetric Test",
    #     test_result="Pass",
    #     serial_number="P50SV3620250101A01",
    #     test_data_link="https://docs.google.com/spreadsheets/d/...",
    #     tracking_sheet_link="https://docs.google.com/spreadsheets/d/..."
    # )
