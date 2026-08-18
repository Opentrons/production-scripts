from starlette.requests import Request

from api.routers.file_transfer import _client_ip


def _request(*, headers: dict[str, str] | None = None, client: tuple[str, int] | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "headers": [
                (name.lower().encode("latin-1"), value.encode("latin-1"))
                for name, value in (headers or {}).items()
            ],
            "client": client,
        }
    )


def test_client_ip_uses_nginx_real_ip_header() -> None:
    request = _request(headers={"X-Real-IP": "192.168.7.42"}, client=("127.0.0.1", 34000))

    assert _client_ip(request) == "192.168.7.42"


def test_client_ip_falls_back_to_direct_connection() -> None:
    assert _client_ip(_request(client=("192.168.8.18", 34000))) == "192.168.8.18"
