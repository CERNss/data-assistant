import nonebot
from nonebot.adapters.qq import Adapter as QQAdapter

from telemetry import init_telemetry, install_error_hooks


def main() -> None:
    init_telemetry()
    install_error_hooks()
    nonebot.init()
    driver = nonebot.get_driver()
    driver.register_adapter(QQAdapter)
    nonebot.load_plugins("plugins")
    nonebot.run()


if __name__ == "__main__":
    main()
