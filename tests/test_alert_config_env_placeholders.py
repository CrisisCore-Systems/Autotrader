from textwrap import dedent

from autotrader.alerts.config import load_alert_config


def test_load_alert_config_resolves_env_placeholders(tmp_path, monkeypatch):
    config_path = tmp_path / "alerts.yaml"
    config_path.write_text(
        dedent(
            """
            telegram:
              enabled: true
              bot_token: "${TELEGRAM_BOT_TOKEN}"
              chat_id: "${TELEGRAM_CHAT_ID}"
            email:
              enabled: false
            """
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "test-chat")

    config = load_alert_config(config_path)

    assert config.telegram is not None
    assert config.telegram.bot_token == "test-token"
    assert config.telegram.chat_id == "test-chat"


def test_load_alert_config_disables_telegram_when_placeholder_env_missing(
    tmp_path, monkeypatch
):
    config_path = tmp_path / "alerts.yaml"
    config_path.write_text(
        dedent(
            """
            telegram:
              enabled: true
              bot_token: "${TELEGRAM_BOT_TOKEN}"
              chat_id: "${TELEGRAM_CHAT_ID}"
            email:
              enabled: false
            """
        ),
        encoding="utf-8",
    )

    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    config = load_alert_config(config_path)

    assert config.telegram is None
    assert not config.is_configured()
