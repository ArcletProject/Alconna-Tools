from typing import List, Dict, Any, Union, Tuple, Optional
from nepattern import Empty, AllParam, BasePattern

from arclet.alconna.args import Args, Arg
from arclet.alconna.base import Subcommand, Option
from arclet.alconna.components.output import TextFormatter, Trace


class ArgParserTextFormatter(TextFormatter):
    """
    argparser 风格的帮助文本格式化器
    """

    def format(self, trace: Trace) -> str:
        parts = trace.body  # type: ignore
        sub_names = [i.name for i in filter(lambda x: isinstance(x, Subcommand), parts)]
        opt_names = [i.name for i in filter(lambda x: isinstance(x, Option), parts)]
        sub_names = f"{{{','.join(sub_names)}}}" if sub_names else ""
        opt_names = (" ".join(f"[{i}]" for i in opt_names)) if opt_names else ""
        topic = f"{trace.head['name']} {opt_names}\n {sub_names}"
        header = self.header(trace.head, trace.separators)
        param = self.parameters(trace.args)
        body = self.body(parts)
        return f"{topic}\n{header % (param, body)}"

    def param(self, parameter: Arg) -> str:
        name = parameter.name
        arg = f"[{name.upper()}" if parameter.optional else name.upper()
        if not parameter.hidden:
            if parameter.value is AllParam:
                return f"{name.upper()}..."
            if isinstance(parameter.value, BasePattern):
                arg += f":{parameter.value}"
            if parameter.field.display is Empty:
                arg += "=None"
            elif parameter.field.display is not None:
                arg += f"={parameter.field.display}"
        return f"{arg}]" if parameter.optional else arg

    def parameters(self, args: Args) -> str:
        res = ""
        for arg in args.argument:
            if arg.name.startswith('_key_'):
                continue
            if len(arg.separators) == 1:
                sep = ' ' if arg.separators[0] == ' ' else f' {arg.separators[0]!r} '
            else:
                sep = f"[{'|'.join(arg.separators)!r}]"
            res += self.param(arg) + sep
        notice = [(arg.name, arg.notice) for arg in args.argument if arg.notice]
        return f"{res}\n  内容:\n  " + "\n  ".join(f"{v[0]}: {v[1]}" for v in notice) if notice else res

    def header(self, root: Dict[str, Any], separators: Tuple[str, ...]) -> str:
        help_string = f"\n描述: {desc}\n" if (desc := root.get("description")) else ""
        usage = f"\n用法: {usage}\n" if (usage := root.get("usage")) else ""
        example = f"\n样例: {example}\n" if (example := root.get("example")) else ""
        header_text = (
            f"[{''.join(map(str, headers))}]"
            if (headers := root.get("header", [])) and headers != [""]
            else ""
        )
        cmd = f"{header_text}{root.get('name', '')}"
        sep = separators[0]
        command_string = (cmd or root["name"]) + sep
        return f"\n命令: {command_string}%s{help_string}{usage}%s{example}"

    def part(self, node: Union[Subcommand, Option]) -> str:
        ...

    def body(self, parts: List[Union[Option, Subcommand]]) -> str:
        options = []
        opt_description = []
        max_len = 1
        for opt in filter(
            lambda x: isinstance(x, Option) and (x.name not in self.ignore_names or not x.nargs), parts
        ):
            alias_text = (
                (f'<{" ".join(opt.requires)}> ' if opt.requires else "")
                + ", ".join(opt.aliases)
            )
            options.append(
                f"  {alias_text}{tuple(opt.separators)[0]}{self.parameters(opt.args)}"
            )
            opt_description.append(opt.help_text)
        if options:
            max_len = max(max(map(lambda x: len(x), options)), max_len)
        subcommands = []
        sub_description = []
        for sub in filter(lambda x: isinstance(x, Subcommand), parts):
            name = " ".join(sub.requires) + (" " if sub.requires else "") + sub.name
            args = self.parameters(sub.args)
            subcommands.append(
                f"  {name}{tuple(sub.separators)[0]}{args}"
            )
            sub_topic = " ".join(f"[{i.name}]" for i in sub.options)  # type: ignore
            sub_description.append(f"{sub.help_text} {sub_topic}")
        if subcommands:
            max_len = max(max(map(lambda x: len(x), subcommands)), max_len)
        option_string = "\n".join(
            f"{i.ljust(max_len)} {j}" for i, j in zip(options, opt_description)
        )
        subcommand_string = "\n".join(
            f"{i.ljust(max_len)} {j}" for i, j in zip(subcommands, sub_description)
        )
        option_help = "选项:\n" if option_string else ""
        subcommand_help = "子命令:\n" if subcommand_string else ""
        return f"{subcommand_help}{subcommand_string}\n{option_help}{option_string}\n"


class MarkdownTextFormatter(TextFormatter):
    def format(self, trace: Trace) -> str:
        """help text的生成入口"""
        """头部节点的描述"""
        root, separators = trace.head, trace.separators
        params, notice = self.parameters(trace.args)
        notice_text = ("### 注释:\n```\n" + "\n".join(notice) + "\n```") if notice else ""
        help_string = f"{desc}" if (desc := root.get("description")) else ""
        usage = f"\n{usage}" if (usage := root.get("usage")) else ""
        example = (
            f"\n## 使用示例:\n```shell\n{example}\n```"
            if (example := root.get("example"))
            else ""
        )

        headers = (
            f"&#91;{''.join(map(str, headers))}&#93;"
            if (headers := root.get("header", [])) and headers != [""]
            else ""
        )
        cmd = f"{headers}{root.get('name', '')}"
        command_string = (cmd or root["name"]) + (
            tuple(separators)[0] if params else ""
        )
        body = self.body(trace.body)

        return (
            f"## {help_string}\n\n"
            f"指令: \n\n"
            f"**{command_string}{params}**\n"
            f"{notice_text}"
            f"{usage}\n\n"
            f"{body}"
            f"{example}"
        )

    def param(self, parameter: Arg) -> str:
        """对单个参数的描述"""
        name = parameter.name
        arg = f"&#91;{name}" if parameter.optional else f"&lt;{name}"
        if not parameter.hidden:
            if parameter.value is AllParam:
                return f"&lt;...{name}&gt;"
            if not isinstance(parameter.value, BasePattern) or parameter.value.pattern != name:
                arg += f":{parameter.value}"
            if parameter.field.display is Empty:
                arg += " = None"
            elif parameter.field.display is not None:
                arg += f" = {parameter.field.display} "
        return f"{arg}&#93;" if parameter.optional else f"{arg}&gt;"

    def parameters(self, args: Args) -> Tuple[str, Optional[List[str]]]:
        """参数列表的描述"""
        res = ""
        for arg in args.argument:
            if arg.name.startswith('_key_'):
                continue
            if len(arg.separators) == 1:
                sep = ' ' if arg.separators[0] == ' ' else f' {arg.separators[0]!r} '
            else:
                sep = f"[{'|'.join(arg.separators)!r}]"
            res += self.param(arg) + sep
        notice = [(arg.name, arg.notice) for arg in args.argument if arg.notice]
        return (res[:-1], [f"{v[0]}: {v[1]}" for v in notice]) if notice else (res, None)

    def part(self, node: Union[Subcommand, Option]) -> str:
        """每个子节点的描述"""
        if isinstance(node, Subcommand):
            name = " ".join(node.requires) + (" " if node.requires else "") + node.name
            option_string = "\n".join(self.part(i) for i in node.options)
            option_help = "### 该子命令内可用的选项有:\n " if option_string else ""
            param, notice = self.parameters(node.args)
            help_text = "> Unknown" if node.help_text == node.dest else f"> {node.help_text}"
            notice_text = (
                (f"\n>\n> #### 注释:\n> " + "\n> ".join(notice)) if notice else ""
            )
            return (
                f"- **{name + (tuple(node.separators)[0] if param else '')}"
                f"{param}**\n"
                f"{help_text}"
                f"{notice_text}\n"
                f"{option_help}{option_string}"
            )
        elif isinstance(node, Option):
            alias_text = (
                " ".join(node.requires)
                + (" " if node.requires else "")
                + (
                    f"&#91;{'|'.join(node.aliases)}&#93;"
                    if len(node.aliases) >= 2
                    else "".join(node.aliases)
                )
            )
            help_text = "> Unknown" if node.help_text == node.dest else f"> {node.help_text}"
            param, notice = self.parameters(node.args)
            notice_text = (
                (f"\n>\n> #### 注释:\n> " + "\n> ".join(notice)) if notice else ""
            )
            return (
                f"- **{alias_text + (tuple(node.separators)[0] if param else '')}"
                f"{param.strip(' ')}**\n"
                f"{help_text}"
                f"{notice_text}\n"
            )
        else:
            raise TypeError(f"{node} is not a valid node")

    def body(self, parts: List[Union[Option, Subcommand]]) -> str:
        """子节点列表的描述"""
        option_string = "\n".join(
            self.part(opt)
            for opt in filter(lambda x: isinstance(x, Option), parts)
            if opt.name not in self.ignore_names
        )
        subcommand_string = "\n".join(
            self.part(sub) for sub in filter(lambda x: isinstance(x, Subcommand), parts)
        )
        option_help = "## 可用的选项有:\n" if option_string else ""
        subcommand_help = "## 可用的子命令有:\n" if subcommand_string else ""
        return f"{subcommand_help}{subcommand_string}{option_help}{option_string}"
