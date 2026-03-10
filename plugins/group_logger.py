from __future__ import annotations

from loguru import logger


async def handle_group_message(*args: object, **kwargs: object) -> None:
    logger.warning("group_logger is deprecated; use NapCat pipeline instead")


async def handle_c2c_message(*args: object, **kwargs: object) -> None:
    logger.warning("group_logger is deprecated; use NapCat pipeline instead")


async def handle_group_receive_notice(*args: object, **kwargs: object) -> None:
    logger.warning("group_logger is deprecated; use NapCat pipeline instead")


async def handle_group_reject_notice(*args: object, **kwargs: object) -> None:
    logger.warning("group_logger is deprecated; use NapCat pipeline instead")
