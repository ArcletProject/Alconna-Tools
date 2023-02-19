from functools import wraps
from typing import Callable, Optional, TypeVar

from arclet.alconna import Alconna, CommandMeta, Args
from arclet.alconna.action import ArgAction
from typing_extensions import ParamSpec

T = TypeVar("T")
P = ParamSpec("P")


def simple_type(raise_exception: bool = False):
    def deco(func: Callable[P, T]) -> Callable[P, Optional[T]]:
        def inner(*args: P.args, **kwargs: P.kwargs):
            return {"$func": func(*args, **kwargs)}
        name: str = f"{id(func)}"
        _cmd = Alconna(
            name, Args.from_callable(func)[0],
            action=ArgAction(inner), meta=CommandMeta(raise_exception=raise_exception)
        )

        @wraps(func)
        def __wrapper__(*args: P.args, **kwargs: P.kwargs):
            param = [name, *args]
            for k, v in kwargs.items():
                param.extend([f"{k}=", v])
            return (
                result.main_args.get("$func", None)
                if (result := _cmd.parse(param)).matched
                else None
            )

        return __wrapper__

    return deco
