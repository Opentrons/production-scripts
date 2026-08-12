from core.i18n import (
    get_request_locale,
    normalize_locale,
    reset_request_locale,
    set_request_locale,
    translate,
)


def test_normalize_locale_supports_browser_language_lists():
    assert normalize_locale("en-US,en;q=0.9,zh-CN;q=0.8") == "en-US"
    assert normalize_locale("zh-Hans-CN,zh;q=0.9") == "zh-CN"
    assert normalize_locale("fr-FR") == "zh-CN"


def test_request_locale_controls_translated_error_messages():
    token = set_request_locale("en-GB")
    try:
        assert get_request_locale() == "en-US"
        assert translate("auth.permission_denied") == "This account cannot use device controls."
    finally:
        reset_request_locale(token)

    assert get_request_locale() == "zh-CN"
    assert translate("auth.permission_denied") == "当前账号无设备控制权限"
