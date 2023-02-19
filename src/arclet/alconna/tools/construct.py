import asyncio
import inspect
import re
import sys
from contextlib import suppress
from functools import partial, wraps
from types import FunctionType, MethodType, ModuleType
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    Generic,
    Iterable,
    List,
    Literal,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    get_args,
)

from arclet.alconna import store_value
from arclet.alconna.action import ArgAction
from arclet.alconna.args import ArgFlag, Args, TAValue
from arclet.alconna.arparma import Arparma
from arclet.alconna.base import Option, Subcommand
from arclet.alconna.config import config as global_config
from arclet.alconna.core import Alconna, CommandMeta
from arclet.alconna.exceptions import NullMessage
from arclet.alconna.manager import command_manager
from arclet.alconna.typing import DataCollection, KeyWordVar, MultiVar
from arclet.alconna.util import init_spec, split, split_once
from nepattern import AllParam, AnyOne, pattern_map, type_parser
from typing_extensions import get_origin

T = TypeVar("T")
TCallable = TypeVar("TCallable", bound=Callable)

PARSER_TYPE = Callable[
    [Callable[..., T], Arparma, Dict[str, Any], asyncio.AbstractEventLoop],
    T,
]


def default_parser(
    func: Callable[..., T],
    result: Arparma,
    local_arg: Dict[str, Any],
    loop: asyncio.AbstractEventLoop,
) -> T:
    return result.call(func, **local_arg)


class Executor(Generic[T]):
    """
    以 click-like 方法创建的 Alconna 结构体, 可以被视为一类 CommanderHandler
    """

    command: Alconna
    parser_func: Callable[
        [Callable[..., T], Arparma, Dict[str, Any], asyncio.AbstractEventLoop],
        T,
    ]
    local_args: Dict[str, Any]
    exec_target: Callable[..., T]

    def __init__(self, command: Alconna, target: Callable):
        self.command = command
        self.exec_target = target
        self.parser_func = default_parser
        self.local_args = {}

    def set_local_args(self, local_args: Optional[Dict[str, Any]] = None):
        """
        设置本地参数

        Args:
            local_args (Optional[Dict[str, Any]]): 本地参数
        """
        self.local_args = local_args or {}

    def set_parser(self, parser_func: PARSER_TYPE):
        """
        设置解析器

        Args:
            parser_func (PARSER_TYPE): 解析器, 接受的参数必须为 (func, args, local_args, loop)
        """
        self.parser_func = parser_func
        return self

    def __call__(self, message: DataCollection[Union[str, Any]]) -> Arparma:
        if not self.exec_target:
            raise RuntimeError(global_config.lang.construct_decorate_error)
        result = self.command.parse(message)
        if result.matched:
            self.parser_func(
                self.exec_target,
                result,
                self.local_args,
                asyncio.get_event_loop(),
            )
        return result

    def from_commandline(self):
        """从命令行解析参数"""
        if not self.command:
            raise RuntimeError(global_config.lang.construct_decorate_error)
        args = sys.argv[1:]
        args.insert(0, self.command.command)
        return self.__call__(" ".join(args))


# ----------------------------------------
# click-like
# ----------------------------------------


class AlconnaDecorate:
    """
    Alconna Click-like 构造方法的生成器

    Examples:
        >>> cli = AlconnaDecorate()
        >>> @cli.command()
        ... @cli.option("--name|-n", Args["name", str, "your name"])
        ... @cli.option("--age|-a", Args["age", int, "your age"])
        ... def hello(name: str, age: int):
        ...     print(f"Hello {name}, you are {age} years old.")
        ...
        >>> hello("hello --name Alice --age 18")

    Attributes:
        namespace (str): 命令的命名空间
    """

    namespace: str
    building: bool
    buffer: Dict[str, Any]
    default_parser: PARSER_TYPE

    def __init__(self, namespace: str = "Alconna"):
        """
        初始化构造器

        Args:
            namespace (str): 命令的命名空间
        """
        self.namespace = namespace
        self.building = False
        self.buffer = {}
        self.default_parser = default_parser

    def command(
        self,
        name: Optional[str] = None,
        headers: Optional[List[Any]] = None,
    ) -> Callable[[Callable[..., T]], Executor]:
        """
        开始构建命令

        Args:
            name (Optional[str]): 命令名称
            headers (Optional[List[Any]]): 命令前缀
        """
        self.building = True

        def wrapper(func: Callable[..., T]) -> Executor[T]:
            alc = Alconna(
                name or func.__name__,
                headers or [],
                self.buffer.pop("args", Args()),
                *self.buffer.pop("options", []),
                meta=self.buffer.pop("meta", CommandMeta()),
                namespace=self.namespace,
            )
            if alc.meta.example and "$" in alc.meta.example and alc.headers:
                alc.meta.example = alc.meta.example.replace("$", alc.headers[0])
            self.building = False
            return Executor(alc, func).set_parser(self.default_parser)

        return wrapper

    @init_spec(Option, True)
    def option(self, opt: Option) -> Callable[[TCallable], TCallable]:
        """
        添加命令选项

        """
        if not self.building:
            raise RuntimeError(global_config.lang.construct_decorate_error)

        def wrapper(func: TCallable) -> TCallable:
            self.buffer.setdefault("options", []).append(opt)
            return func

        return wrapper

    @init_spec(Subcommand, True)
    def subcommand(self, sub: Subcommand) -> Callable[[TCallable], TCallable]:
        """
        添加命令选项

        """
        if not self.building:
            raise RuntimeError(global_config.lang.construct_decorate_error)

        def wrapper(func: TCallable) -> TCallable:
            self.buffer.setdefault("options", []).append(sub)
            return func

        return wrapper

    def main_args(self, args: Args) -> Callable[[TCallable], TCallable]:
        """
        添加命令参数

        Args:
            args (Args): 参数
        """
        if not self.building:
            raise RuntimeError(global_config.lang.construct_decorate_error)

        def wrapper(func: TCallable) -> TCallable:
            self.buffer["args"] = args
            return func

        return wrapper

    @init_spec(Args, True)
    def argument(self, arg: Args) -> Callable[[TCallable], TCallable]:
        """
        添加命令参数
        """
        if not self.building:
            raise RuntimeError(global_config.lang.construct_decorate_error)

        def wrapper(func: TCallable) -> TCallable:
            if args := self.buffer.get("args"):
                args: Args
                args.__merge__(arg)
            else:
                self.buffer["args"] = Args().__merge__(arg)
            return func

        return wrapper

    def meta(self, content: CommandMeta) -> Callable[[TCallable], TCallable]:
        """
        添加命令元数据
        """
        if not self.building:
            raise RuntimeError(global_config.lang.construct_decorate_error)

        def wrapper(func: TCallable) -> TCallable:
            self.buffer["meta"] = content
            return func

        return wrapper

    def help(
        self,
        description: str,
        usage: Optional[str] = None,
        example: Optional[str] = None,
    ) -> Callable[[TCallable], TCallable]:
        """
        添加命令元数据
        """
        if not self.building:
            raise RuntimeError(global_config.lang.construct_decorate_error)

        def wrapper(func: TCallable) -> TCallable:
            self.buffer["meta"] = CommandMeta(description, usage, example)
            return func

        return wrapper

    def set_default_parser(self, parser_func: PARSER_TYPE):
        """
        设置默认的参数解析器

        Args:
            parser_func (PARSER_TYPE): 参数解析器, 接受的参数必须为 (func, args, local_args, loop)
        """
        self.default_parser = parser_func
        return self


def args_from_list(args: List[List[str]], custom_types: Dict[str, type]) -> Args:
    """
    从处理好的字符串列表中生成Args

    Examples:
        >>> args_from_list([["foo", "str"], ["bar", "digit", "123"]], {"digit":int})
    """
    _args = Args()
    for arg in args:
        if (_le := len(arg)) == 0:
            raise NullMessage
        default = arg[2].strip(" ") if _le > 2 else None
        name = arg[0].strip(" ")
        value = (
            AllParam
            if name.startswith("...")
            else (
                AnyOne
                if name.startswith("..")
                else (arg[1].strip(" ") if _le > 1 else name.lstrip(".-"))
            )
        )
        name = name.replace("...", "").replace("..", "")
        _multi, _kw, _slice = "", False, -1
        if value not in (AllParam, AnyOne):
            if mat := re.match(
                r"^(?P<name>.+?)(?P<multi>[+*]+)(\[)?(?P<slice>\d*)(])?$", value
            ):
                value = mat["name"]
                _multi = mat["multi"][0]
                _kw = len(mat["multi"]) > 1
                _slice = int(mat["slice"] or -1)
            with suppress(NameError, ValueError, TypeError):
                value = pattern_map.get(value, None) or type_parser(eval(value, custom_types))  # type: ignore
                default = (
                    (get_origin(value.origin) or value.origin)(default)
                    if default
                    else default
                )
            if _multi:
                value = MultiVar(
                    KeyWordVar(value) if _kw else value,
                    _slice if _slice > 1 else _multi,
                )
        _args.add(name, value=value, default=default)
    return _args


def _from_format(
    format_string: str,
    format_args: Optional[Dict[str, Union[TAValue, Args, Option, List[Option]]]] = None,
    meta: Optional[CommandMeta] = None,
) -> "Alconna":
    """
    以格式化字符串的方式构造 Alconna

    该方法建议使用多个重名的命令时使用

    Examples:

        >>> from arclet.alconna.tools import AlconnaFormat
        >>> alc1 = AlconnaFormat(
        ...     "lp user {target:str} perm set {perm:str} {default}",
        ...     {"default": Args["val", bool, True]},
        ... )
        >>> alc2 = AlconnaFormat(
        ...     "lp user {target:str} perm del {perm:str}",
        ... )
        >>> alc3 = AlconnaFormat(
        ...     "lp user {target:str} perm info {perm:str}"
        ... )
        >>> alc1.parse("lp user AAA perm set admin.all False")
        >>> alc1.parse("lp user AAA perm info admin.all")
    """
    format_args = format_args or {}
    _key_ref = 0
    strings = split(format_string)
    command = strings.pop(0)
    options = []
    main_args = Args()

    _string_stack: List[str] = []
    for i, string in enumerate(strings):
        if not (arg := re.findall(r"{(.+)}", string)):
            _string_stack.append(string)
            _key_ref = 0
            continue
        _key_ref += 1
        key = arg[0]
        try:
            value = format_args[key]
            try:
                _name, _requires = _string_stack[-1], _string_stack[:-1]
                if isinstance(value, Option):
                    options.append(Subcommand(_name, value, requires=_requires))
                elif isinstance(value, list):
                    options.append(Subcommand(_name, *value, requires=_requires))
                elif isinstance(value, Args):
                    options.append(Option(_name, args=value, requires=_requires))
                else:
                    options.append(
                        Option(_name, Args(**{key: value}), requires=_requires)
                    )
                _string_stack.clear()
            except IndexError:
                if i == 0:
                    if isinstance(value, Args):
                        main_args.__merge__(value)
                    elif not isinstance(value, Option) and not isinstance(value, list):
                        main_args.__merge__(Args(**{key: value}))
                elif isinstance(value, Option):
                    options.append(value)
                elif isinstance(value, Args):
                    options[-1].args.__merge__(value)
                    options[-1].nargs = len(options[-1].args.argument)
                else:
                    options[-1].args.__merge__(Args(**{key: value}))
                    options[-1].nargs += 1
        except KeyError:
            may_parts = re.split(r"[:=]", key.replace(" ", ""))
            _arg = (
                Args[may_parts[0], Any]
                if len(may_parts) == 1
                else args_from_list([may_parts], {})
            )
            if _string_stack:
                if _key_ref > 1:
                    options[-1].args.__merge__(_arg)
                    options[-1].nargs = len(options[-1].args.argument)
                else:
                    options.append(
                        Option(_string_stack[-1], _arg, requires=_string_stack[:-1])
                    )
                    _string_stack.clear()
            else:
                main_args.__merge__(_arg)
    return Alconna(command, main_args, *options, meta=meta)


def _from_string(
    command: str, *option: str, sep: str = " ", meta: Optional[CommandMeta] = None
) -> "Alconna":
    """
    以纯字符串的形式构造Alconna的简易方式, 或者说是koishi-like的方式

    Examples:

        >>> from arclet.alconna.tools import AlconnaString
        >>> alc = AlconnaString(
        ...     "test <message:str:hello> #HELP_STRING",
        ...     "--foo|-f <val:bool>",
        ...     "-bar <bar:str> [baz:int]",
        ...     "-qux &123"
        ... )
        >>> alc.parse("test abcd --foo True")
    """

    _options = []
    meta = meta or CommandMeta()
    head, others = split_once(command, sep)
    headers = [head]
    if re.match(r"^\[(.+?)]$", head):
        headers = head.strip("[]").split("|")

    def args_gen(_others: str):
        arg = [re.split("[:=]", p) for p in re.findall(r"<(.+?)>", _others)]
        for p in re.findall(r"\[(.+?)]", _others):
            res = re.split("[:=]", p)
            res[0] = f"{res[0]};?"
            arg.append(res)
        return arg

    args = args_gen(others)
    if help_string := re.findall(r"(?: )#(.+)$", others):  # noqa
        meta.description = help_string[0]
    custom_types = getattr(inspect.getmodule(inspect.stack()[1][0]), "__dict__", {})
    _args = args_from_list(args, custom_types.copy())
    for opt in option:
        opt_head, opt_others = split_once(opt, sep)
        opt_args = args_gen(opt_others)
        _typs = custom_types.copy()
        _opt_args = args_from_list(opt_args, _typs)
        opt_action_value = re.findall(r"&(.+?)(?: #.+?)?$", opt_others)
        if not (opt_help_string := re.findall(r"(?: )#(.+)$", opt_others)):  # noqa
            opt_help_string = [opt_head]
        _options.append(Option(opt_head, args=_opt_args))
        if opt_action_value:
            _options[-1].action = store_value(
                eval(opt_action_value[0].rstrip(), {"true": True, "false": False})
            )
        _options[-1].help_text = opt_help_string[0]
    meta.fuzzy_match = True
    return Alconna(headers, _args, *_options, meta=meta)


config_key = Literal[
    "headers",
    "raise_exception",
    "description",
    "get_subcommand",
    "namespace",
    "command",
]


def visit_config(obj: Any, config_keys: Iterable[str]):
    result = {}
    if isinstance(obj, (FunctionType, MethodType)):
        codes, _ = inspect.getsourcelines(obj)
        _get_config = False
        _start_indent = 0
        for line in codes:
            indent = len(line) - len(line.lstrip())
            if line.lstrip().startswith("class") and line.lstrip().rstrip(
                "\n"
            ).endswith("Config:"):
                _get_config = True
                _start_indent = indent
                continue
            if _get_config:
                if indent == _start_indent:
                    break
                if line.lstrip().startswith("def"):
                    continue
                _contents = re.split(r"\s*=\s*", line.strip())
                if len(_contents) == 2 and _contents[0] in config_keys:
                    result[_contents[0]] = eval(_contents[1])
    elif config := inspect.getmembers(
        obj, lambda x: inspect.isclass(x) and x.__name__.endswith("Config")
    ):
        config = config[0][1]
        result = {k: getattr(config, k) for k in config_keys if k in dir(config)}
    return result


class AlconnaMounter(Alconna):
    mount_cls: Type
    instance: object
    config_keys: FrozenSet[str] = frozenset(get_args(config_key))

    def _instance_action(self, option_dict, varargs, kwargs):
        if not self.instance:
            self.instance = self.mount_cls(*option_dict.values(), *varargs, **kwargs)
        else:
            for key, value in option_dict.items():
                setattr(self.instance, key, value)
        return option_dict

    def _get_instance(self):
        return self.instance

    def _inject_instance(self, target: Callable):
        @wraps(target)
        def __wrapper(*args, **kwargs):
            return target(self._get_instance(), *args, **kwargs)

        return __wrapper

    def _parse_action(self, message):
        ...

    def parse(
        self,
        message: DataCollection[Union[str, Any]],
        duplication: Optional[Any] = None,
        interrupt: bool = False,
    ):  # noqa
        message = self._parse_action(message) or message
        return super().parse(  # noqa
            message, duplication=duplication, interrupt=interrupt
        )


class FuncMounter(AlconnaMounter):
    def __init__(
        self, func: Union[FunctionType, MethodType], config: Optional[dict] = None
    ):
        config = config or visit_config(func, self.config_keys)
        func_name = func.__name__
        if func_name.startswith("_"):
            raise ValueError(global_config.lang.construct_function_name_error)
        _args, method = Args.from_callable(func)
        if method and isinstance(func, MethodType):
            self.instance = func.__self__
            func = cast(FunctionType, partial(func, self.instance))
        super(FuncMounter, self).__init__(
            config.get("headers", []),
            config.get("command", func_name),
            _args,
            meta=CommandMeta(
                description=config.get("description", func.__doc__ or func_name),
                raise_exception=config.get("raise_exception", True),
            ),
            action=ArgAction(func),
            namespace=config.get("namespace", None),
        )


def visit_subcommand(obj: Any):
    result = []
    subcommands: List[Tuple[str, Type]] = inspect.getmembers(
        obj, lambda x: inspect.isclass(x) and not x.__name__.endswith("Config")
    )

    class _MountSubcommand(Subcommand):
        sub_instance: object

    for cls_name, subcommand_cls in filter(
        lambda x: not x[0].startswith("_"), subcommands
    ):
        init = inspect.getfullargspec(subcommand_cls.__init__)
        members = inspect.getmembers(
            subcommand_cls, lambda x: inspect.isfunction(x) or inspect.ismethod(x)
        )
        config = visit_config(subcommand_cls, ["command", "description"])
        _options = []
        sub_help_text = (
            subcommand_cls.__doc__ or subcommand_cls.__init__.__doc__ or cls_name
        )

        if len(init.args + init.kwonlyargs) > 1:
            sub_args = Args.from_callable(subcommand_cls.__init__)[0]
            sub = _MountSubcommand(
                config.get("command", cls_name),
                sub_args,
                help_text=config.get("description", sub_help_text),
            )
            sub.sub_instance = subcommand_cls

            class _InstanceAction(ArgAction):
                def handle(
                    self, option_dict, varargs=None, kwargs=None, raise_exception=False
                ):
                    if not sub.sub_instance:
                        sub.sub_instance = subcommand_cls(
                            *option_dict.values(), *varargs, **kwargs
                        )
                    else:
                        for key, value in option_dict.items():
                            setattr(sub.sub_instance, key, value)
                    return option_dict

            sub.action = _InstanceAction(lambda: None)
        else:
            sub = _MountSubcommand(
                config.get("command", cls_name),
                help_text=config.get("description", sub_help_text),
            )
            sub.sub_instance = subcommand_cls()

        def _get_sub_instance(_sub):
            return _sub.sub_instance

        def _inject_sub_instance(target: Callable):
            @wraps(target)
            def __wrapper(*args, **kwargs):
                return target(_get_sub_instance, *args, **kwargs)

            return __wrapper

        for name, func in filter(lambda x: not x[0].startswith("_"), members):
            help_text = func.__doc__ or name
            _opt_args, method = Args.from_callable(func)
            if method:
                func = _inject_sub_instance(func)
            _options.append(
                Option(name, _opt_args, action=ArgAction(func), help_text=help_text)
            )
        sub.options = _options
        result.append(sub)
    return result


class ClassMounter(AlconnaMounter):
    def __init__(self, mount_cls: Type, config: Optional[dict] = None):
        self.mount_cls = mount_cls
        self.instance: mount_cls = None
        config = config or visit_config(mount_cls, self.config_keys)
        init = inspect.getfullargspec(mount_cls.__init__)
        members = inspect.getmembers(
            mount_cls, lambda x: inspect.isfunction(x) or inspect.ismethod(x)
        )
        _options = []
        if config.get("get_subcommand", False):
            subcommands = visit_subcommand(mount_cls)
            _options.extend(subcommands)
        main_help_text = (
            mount_cls.__doc__ or mount_cls.__init__.__doc__ or mount_cls.__name__
        )

        if len(init.args + init.kwonlyargs) > 1:
            main_args = Args.from_callable(
                mount_cls.__init__,
            )[0]

            instance_handle = self._instance_action

            class _InstanceAction(ArgAction):
                def handle(
                    self, option_dict, varargs=None, kwargs=None, raise_exception=False
                ):
                    return instance_handle(option_dict, varargs, kwargs)

            main_action = _InstanceAction(lambda: None)
            for name, func in filter(lambda x: not x[0].startswith("_"), members):
                help_text = func.__doc__ or name
                _opt_args, method = Args.from_callable(func)
                if method:
                    func = self._inject_instance(func)
                _options.append(
                    Option(name, _opt_args, action=ArgAction(func), help_text=help_text)
                )
            super().__init__(
                config.get("command", mount_cls.__name__),
                main_args,
                config.get("headers", []),
                *_options,
                namespace=config.get("namespace", None),
                meta=CommandMeta(
                    description=config.get("description", main_help_text),
                    raise_exception=config.get("raise_exception", True),
                ),
                action=main_action,
            )
        else:
            self.instance = mount_cls()
            for name, func in filter(lambda x: not x[0].startswith("_"), members):
                help_text = func.__doc__ or name
                _opt_args, method = Args.from_callable(func)
                if method:
                    func = self._inject_instance(func)
                _options.append(
                    Option(
                        name,
                        args=_opt_args,
                        action=ArgAction(func),
                        help_text=help_text,
                    )
                )
            super().__init__(
                config.get("command", mount_cls.__name__),
                config.get("headers", []),
                *_options,
                namespace=config.get("namespace", None),
                meta=CommandMeta(
                    description=config.get("description", main_help_text),
                    raise_exception=config.get("raise_exception", True),
                ),
            )

    def _parse_action(self, message):
        if self.instance:
            for arg in self.args.argument:
                if hasattr(self.instance, arg.name):
                    arg.field.default = getattr(self.instance, arg.name)


class ModuleMounter(AlconnaMounter):
    def __init__(self, module: ModuleType, config: Optional[dict] = None):
        self.mount_cls = module.__class__
        self.instance = module
        config = config or visit_config(module, self.config_keys)
        _options = []
        members = inspect.getmembers(
            module, lambda x: inspect.isfunction(x) or inspect.ismethod(x)
        )
        for name, func in members:
            if name.startswith("_") or func.__name__.startswith("_"):
                continue
            help_text = func.__doc__ or name
            _opt_args, method = Args.from_callable(func)
            if method:
                func = partial(func, func.__self__)
            _options.append(
                Option(
                    name, args=_opt_args, action=ArgAction(func), help_text=help_text
                )
            )
        super().__init__(
            config.get("command", module.__name__),
            config.get("headers", []),
            *_options,
            namespace=config.get("namespace", None),
            meta=CommandMeta(
                description=config.get(
                    "description", module.__doc__ or module.__name__
                ),
                raise_exception=config.get("raise_exception", True),
            ),
        )

    def _parse_action(self, message):
        if self.command.startswith("_"):
            if isinstance(message, str):
                message = f"{self.command} {message}"
            else:
                message.inject(0, self.command)
        return message


class ObjectMounter(AlconnaMounter):
    def __init__(self, obj: object, config: Optional[dict] = None):
        self.mount_cls = type(obj)
        self.instance = obj
        config = config or visit_config(obj, self.config_keys)
        obj_name = obj.__class__.__name__
        init = inspect.getfullargspec(obj.__init__)
        members = inspect.getmembers(
            obj, lambda x: inspect.isfunction(x) or inspect.ismethod(x)
        )
        _options = []
        if config.get("get_subcommand", False):
            subcommands = visit_subcommand(obj)
            _options.extend(subcommands)
        main_help_text = obj.__doc__ or obj.__init__.__doc__ or obj_name
        for name, func in filter(lambda x: not x[0].startswith("_"), members):
            help_text = func.__doc__ or name
            _opt_args, _ = Args.from_callable(func)
            _options.append(
                Option(
                    name, args=_opt_args, action=ArgAction(func), help_text=help_text
                )
            )
        if len(init.args) > 1:
            main_args = Args.from_callable(obj.__init__)[0]
            for arg in main_args.argument:
                if hasattr(self.instance, arg.name):
                    arg.field.default = getattr(self.instance, arg.name)

            instance_handle = self._instance_action

            class _InstanceAction(ArgAction):
                def handle(
                    self, option_dict, varargs=None, kwargs=None, raise_exception=False
                ):
                    return instance_handle(option_dict, varargs, kwargs)

            main_action = _InstanceAction(lambda: None)
            super().__init__(
                config.get("command", obj_name),
                main_args,
                config.get("headers", []),
                *_options,
                meta=CommandMeta(
                    description=config.get("description", main_help_text),
                    raise_exception=config.get("raise_exception", True),
                ),
                action=main_action,
                namespace=config.get("namespace", None),
            )
        else:
            super().__init__(
                config.get("command", obj_name),
                config.get("headers", []),
                *_options,
                namespace=config.get("namespace", None),
                meta=CommandMeta(
                    description=config.get("description", main_help_text),
                    raise_exception=config.get("raise_exception", True),
                ),
            )


def _from_object(
    target: Optional[Union[Type, object, FunctionType, MethodType, ModuleType]] = None,
    command: Optional[str] = None,
    config: Optional[Dict[config_key, Any]] = None,
) -> AlconnaMounter:
    """
    通过解析传入的对象，生成 Alconna 实例的方法, 或者说是Fire-like的方式

    Examples:

        >>> from arclet.alconna.tools import AlconnaFire
        >>> def test_func(a, b, c):
        ...     print(a, b, c)
        ...
        >>> alc = AlconnaFire(test_func)
        >>> alc.parse("test_func 1 2 3")
    """
    if inspect.isfunction(target) or inspect.ismethod(target):
        r = FuncMounter(target, config)
    elif inspect.isclass(target):
        r = ClassMounter(target, config)
    elif inspect.ismodule(target):
        r = ModuleMounter(target, config)
    elif target:
        r = ObjectMounter(target, config)
    else:
        r = ModuleMounter(
            inspect.getmodule(inspect.stack()[1][0]) or sys.modules["__main__"], config
        )
    command = command or (" ".join(sys.argv[1:]) if len(sys.argv) > 1 else None)
    if command:
        with suppress(Exception):
            r.parse(command)
        command_manager.require(r).reset()
    return r


def delegate(cls: Type) -> Alconna:
    attrs = inspect.getmembers(cls, predicate=lambda x: not inspect.isroutine(x))
    _help = cls.__doc__ or cls.__name__
    _main_args = None
    _options = []
    _headers = []
    for name, attr in filter(lambda x: not x[0].startswith("_"), attrs):
        if isinstance(attr, Args):
            _main_args = attr
        elif isinstance(attr, (Option, Subcommand)):
            _options.append(attr)
        elif name.startswith("prefix"):
            _headers.extend(attr if isinstance(attr, (list, tuple)) else [attr])
    return Alconna(
        cls.__name__,
        _main_args,
        _headers,
        *_options,
        meta=CommandMeta(description=_help),
    )


def _argument(
    name: str,
    *alias: str,
    dest: Optional[str] = None,
    value: Optional[Any] = str,
    default: Optional[Any] = None,
    description: Optional[str] = None,
    required: bool = True,
    action: Optional[Union[ArgAction, Callable]] = None,
):
    """类似于 argparse.ArgumentParser.add_argument() 的方法"""
    opt = Option(
        name, alias=list(alias), dest=dest, help_text=description, action=action
    )
    opt.args.add_argument(
        name.strip("-"),
        value=value,
        default=default,
        flags=[] if required else [ArgFlag.OPTIONAL],
    )
    opt.nargs += 1
    return opt


AlconnaFormat = _from_format
AlconnaString = _from_string
AlconnaFire = _from_object
Argument = _argument

__all__ = [
    "AlconnaFormat",
    "AlconnaString",
    "AlconnaFire",
    "Argument",
    "AlconnaDecorate",
    "delegate",
    "Executor",
]
