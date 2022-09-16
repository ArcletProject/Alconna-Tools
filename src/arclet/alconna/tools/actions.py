"""Alconna ArgAction相关"""

from datetime import datetime
from typing import Literal
from arclet.alconna.components.behavior import ArpamarBehavior
from arclet.alconna.exceptions import OutBoundsBehave
from arclet.alconna.config import config
from arclet.alconna.arpamar import Arpamar


def exclusion(target_path: str, other_path: str):
    """
    当设置的两个路径同时存在时, 抛出异常

    Args:
        target_path: 目标路径
        other_path: 其他路径
    """

    class _EXCLUSION(ArpamarBehavior):
        def operate(self, interface: "Arpamar"):
            if interface.query(target_path) and interface.query(other_path):
                raise OutBoundsBehave(
                    config.lang.behavior_exclude_matched.format(target=target_path, other=other_path)
                )

    return _EXCLUSION()


def cool_down(seconds: float):
    """
    当设置的时间间隔内被调用时, 抛出异常

    Args:
        seconds: 时间间隔
    """

    class _CoolDown(ArpamarBehavior):
        def __init__(self):
            self.last_time = datetime.now()

        def operate(self, interface: "Arpamar"):
            current_time = datetime.now()
            if (current_time - self.last_time).total_seconds() < seconds:
                raise OutBoundsBehave(config.lang.behavior_cooldown_matched)
            else:
                self.last_time = current_time

    return _CoolDown()


def inclusion(*targets: str, flag: Literal["any", "all"] = "any"):
    """
    当设置的路径不存在时, 抛出异常

    Args:
        targets: 路径列表
        flag: 匹配方式, 可选值为"any"或"all", 默认为"any"
    """

    class _Inclusion(ArpamarBehavior):
        def operate(self, interface: "Arpamar"):
            if flag == "all":
                for target in targets:
                    if not interface.query(target):
                        raise OutBoundsBehave(config.lang.behavior_inclusion_matched)
            else:
                all_count = len(targets) - sum(1 for target in targets if interface.query(target))
                if all_count > 0:
                    raise OutBoundsBehave(config.lang.behavior_inclusion_matched)
    return _Inclusion()
