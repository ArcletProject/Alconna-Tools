from typing_extensions import ParamSpec
from typing import TypeVar, Callable, Optional
from functools import wraps
from arclet.alconna.args import Args
from arclet.alconna.analysis.base import analyse_args

T = TypeVar("T")
P = ParamSpec("P")


def simple_type(raise_exception: bool = False):
    def deco(func: Callable[P, T]) -> Callable[P, Optional[T]]:
        _args, _ = Args.from_callable(func)

        @wraps(func)
        def __wrapper__(*args: P.args, **kwargs: P.kwargs):
            param = list(args)
            for k, v in kwargs.items():
                param.extend([f"{k}=", v])
            if not (result := analyse_args(_args, param, raise_exception)):
                return None
            res_args, kwargs, kwonly, varargs, kw_key, var_key = [], {}, {}, [], None, None
            if '$kwargs' in result:
                res_kwargs, kw_key = result.pop('$kwargs')
                result.pop(kw_key)
            if '$varargs' in result:
                varargs, var_key = result.pop('$varargs')
                result.pop(var_key)
            if '$kwonly' in result:
                kwonly = result.pop('$kwonly')
                for k in kwonly:
                    result.pop(k)
            res_args.extend(iter(result.values()))
            res_args.extend(varargs)
            addition_kwargs = {**kwonly, **kwargs}
            return func(*res_args, **addition_kwargs)  # type: ignore

        return __wrapper__

    return deco
