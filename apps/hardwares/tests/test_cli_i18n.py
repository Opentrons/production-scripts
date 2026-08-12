from cli.interface import ui


def test_bilingual_uses_selected_language():
    original = ui.get_language()
    try:
        ui.set_language("zh-CN")
        assert ui.bilingual("English", "中文") == "中文"
        ui.set_language("en-US")
        assert ui.bilingual("English", "中文") == "English"
    finally:
        ui.set_language(original)
