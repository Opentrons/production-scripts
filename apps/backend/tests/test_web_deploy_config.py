from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
WEB_DEPLOY_SCRIPT = REPOSITORY_ROOT / "deploy" / "web.sh"


def test_login_redirects_preserve_the_public_origin() -> None:
    source = WEB_DEPLOY_SCRIPT.read_text(encoding="utf-8")

    assert source.count("absolute_redirect off;") == 2
    assert r"return 302 /login?redirect=\$uri;" in source
