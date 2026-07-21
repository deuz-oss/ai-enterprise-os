from python_common.config import AppConfig


def test_config_model() -> None:
    cfg = AppConfig(service_name="x")
    assert cfg.service_name == "x"
