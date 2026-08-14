from modules.agent.attachment_store import inspect_attachment, read_attachment


def inspect_agent_attachment(attachment_id: str) -> dict:
    return inspect_attachment(attachment_id)


def read_agent_attachment(attachment_id: str, offset: int = 0, max_chars: int = 16_000) -> dict:
    return read_attachment(attachment_id, offset=offset, max_chars=max_chars)
