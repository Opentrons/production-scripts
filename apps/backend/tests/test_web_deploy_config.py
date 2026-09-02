from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
WEB_DEPLOY_SCRIPT = REPOSITORY_ROOT / "deploy" / "web.sh"


def test_spa_routes_load_before_authentication_refresh() -> None:
    source = WEB_DEPLOY_SCRIPT.read_text(encoding="utf-8")

    assert source.count("absolute_redirect off;") == 2
    assert source.count(r"try_files \$uri /index.html;") == 2
    assert "location @login_redirect" not in source
    assert r"return 302 /login?redirect=\$uri;" not in source
    # The remaining auth_request lives in the data-center endpoint generator,
    # not in either SPA location block.
    assert source.count("auth_request /_auth;") == 1
