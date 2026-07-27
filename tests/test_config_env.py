from dialogue_os.config import Settings


def test_comma_separated_tuple_settings_from_environment(monkeypatch):
    monkeypatch.setenv(
        "CHIEF_FEATHERLESS_FALLBACK_MODELS",
        "darkc0de/XORTRON, deepseek-ai/DeepSeek-V3",
    )
    monkeypatch.setenv(
        "UNCENSORED_FALLBACK_MODELS",
        "model/one,model/two",
    )
    monkeypatch.setenv(
        "WAR_ROOM_ALLOWED_ORIGINS",
        "https://one.example/, https://two.example",
    )

    settings = Settings(_env_file=None)

    assert settings.chief_featherless_fallback_models == (
        "darkc0de/XORTRON",
        "deepseek-ai/DeepSeek-V3",
    )
    assert settings.uncensored_fallback_models == ("model/one", "model/two")
    assert settings.war_room_allowed_origins == (
        "https://one.example",
        "https://two.example",
    )
