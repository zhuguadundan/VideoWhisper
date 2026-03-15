from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS_PATH = ROOT / "web" / "static" / "js" / "app.js"
SETTINGS_JS_PATH = ROOT / "web" / "static" / "js" / "settings.js"
UI_HELPERS_PATH = ROOT / "web" / "static" / "js" / "ui-helpers.js"


def test_ui_helpers_exposes_sensitive_data_masker():
    source = UI_HELPERS_PATH.read_text(encoding="utf-8")

    assert "function maskSensitiveData(value, seen = new WeakSet())" in source
    assert "normalized === 'api_key'" in source
    assert "normalized.includes('cookie')" in source
    assert "normalized === 'mobile'" in source
    assert "normalized === 'userid'" in source
    assert "normalized.includes('mentioned_mobile')" in source
    assert "normalized.includes('mentioned_userid')" in source


def test_settings_save_does_not_log_raw_config():
    source = SETTINGS_JS_PATH.read_text(encoding="utf-8")

    assert "console.log('保存配置:', config);" not in source
    assert "window.UIHelpers.maskSensitiveData(config)" in source
    assert "window.apiConfigManager = configManager;" in source


def test_upload_process_does_not_log_raw_runtime_config():
    source = APP_JS_PATH.read_text(encoding="utf-8")

    assert "API配置获取成功: ${JSON.stringify(config)}" not in source
    assert "处理参数: provider=${provider}, config=${JSON.stringify(config)}" not in source
    assert "请求数据: ${JSON.stringify(requestData)}" not in source
    assert "getSafeLogPayload(config)" in source


def test_settings_save_masks_wecom_mention_targets():
    source = UI_HELPERS_PATH.read_text(encoding="utf-8")

    assert "normalized.endsWith('_mobiles')" in source
    assert "normalized.endsWith('_userids')" in source
