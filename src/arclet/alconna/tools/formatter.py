from typing import List, Dict, Any, Union, Tuple, Optional
from nepattern import Empty, AllParam, AnyOne, AnyString
from tarina import lang
from arclet.alconna.args import Args, Arg
from arclet.alconna.base import Subcommand, Option, Shortcut, Completion
from arclet.alconna.formatter import TextFormatter, Trace


class ShellTextFormatter(TextFormatter):
    """
    shell 风格的帮助文本格式化器
    """

    def format(self, trace: Trace) -> str:
        parts = trace.body  # type: ignore
        sub_names = [i.name for i in filter(lambda x: isinstance(x, Subcommand), parts)]
        opt_names = [min(i.aliases, key=len) for i in filter(lambda x: isinstance(x, Option) and x.name not in self.ignore_names, parts)]
        sub_names = f"{{{','.join(sub_names)}}}" if sub_names else ""
        opt_names = (" ".join(f"[{i}]" for i in opt_names)) if opt_names else ""
        topic = f"{lang.require('tools', 'format.ap.title')}: {trace.head['name']} {opt_names}\n {sub_names}"
        title, desc, usage, example = self.header(trace.head, trace.separators)
        param = self.parameters(trace.args)
        body = self.body(parts)
        res = topic
        if desc:
            res = f"{desc}\n\n{res}"
        if param:
            res += f"\n\n{lang.require('tools', 'format.ap.base')}: {title}{param}"
        if usage:
            res += f"\n{usage}"
        if body:
            res += f"\n\n{body}"
        if example:
            res += f"\n{example}"
        return res

    def param(self, parameter: Arg) -> str:
        name = parameter.name
        if str(parameter.value).strip("'\"") == name:
            return f"[{name}]" if parameter.optional else name
        if parameter.hidden:
            return f"[{name.upper()}]" if parameter.optional else name.upper()
        if parameter.value is AllParam:
            return f"{name.upper()}..."
        arg = f"[{name.upper()}" if parameter.optional else name.upper()
        if parameter.value not in (AnyOne, AnyString):
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
        return f"{res}\n{lang.require('tools', 'format.ap.notice')}:\n  - " + \
            "\n  - ".join(f"{v[0]}: {v[1]}" for v in notice) if notice else res

    def header(self, root: Dict[str, Any], separators: Tuple[str, ...]):
        help_string = f"{desc}" if (desc := root.get("description")) else ""
        usage = f"{lang.require('tools', 'format.ap.usage')}: {usage}" if (usage := root.get("usage")) else ""
        example = f"{lang.require('tools', 'format.ap.example')}: {example}" if (example := root.get("example")) else ""
        prefixs = f"[{''.join(map(str, prefixs))}]" if (prefixs := root.get("prefix", [])) != [] else ""
        cmd = f"{prefixs}{root.get('name', '')}"
        sep = separators[0]
        command_string = (cmd or root["name"]) + sep
        return command_string, help_string, usage, example

    def body(self, parts: List[Union[Option, Subcommand]]) -> str:
        options = []
        opt_description = []
        max_len = 1
        for opt in filter(
                lambda x: isinstance(x, Option) and not isinstance(x, (Completion, Shortcut)), parts
        ):
            alias_text = (
                (f'{{{" ".join(opt.requires)}}} ' if opt.requires else "")
                + ", ".join(sorted(opt.aliases, key=len))
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
                f"    {name}{tuple(sub.separators)[0]}{args}"
            )
            sub_topic = " ".join(f"[{i.name}]" for i in sub.options)  # type: ignore
            sub_description.append(f"{sub.help_text} {sub_topic}")
        if subcommands:
            max_len = max(max(map(lambda x: len(x), subcommands)), max_len)
        option_string = "\n".join(
            f"{i.ljust(max_len)}    {j}" for i, j in zip(options, opt_description)
        )
        subcommand_string = "\n".join(
            f"{i.ljust(max_len)}    {j}" for i, j in zip(subcommands, sub_description)
        )
        option_help = f"{lang.require('tools', 'format.ap.opt')}:\n" if option_string else ""
        subcommand_help = f"{lang.require('tools', 'format.ap.sub')}:\n" if subcommand_string else ""
        return f"{subcommand_help}{subcommand_string}\n{option_help}{option_string}\n"


class MarkdownTextFormatter(TextFormatter):
    def format(self, trace: Trace) -> str:
        """help text的生成入口"""
        """头部节点的描述"""
        root, separators = trace.head, trace.separators
        params, notice = self.parameters(trace.args)
        notice_text = (
            f"\n\n### {lang.require('format', 'notice')}:\n```\n" + "\n".join(notice) + "\n```"
        ) if notice else ""
        help_string = f"{desc}" if (desc := root.get("description")) else ""
        usage = f"{usage}" if (usage := root.get("usage")) else ""
        example = (
            f"## {lang.require('format', 'example')}:\n```shell\n{example}\n```"
            if (example := root.get("example"))
            else ""
        )

        prefixs = (
            f"&#91;{''.join(map(str, prefixs))}&#93;"
            if (prefixs := root.get("prefix", [])) and prefixs != []
            else ""
        )
        cmd = f"{prefixs}{root.get('name', '')}"
        command_string = cmd or (root["name"] + separators[0])
        body = self.body(trace.body)
        res = (
            f"## {help_string}\n\n"
            f"### {lang.require('tools', 'format.md.title')}: \n\n"
            f"**{command_string}{params}**{notice_text}"
        )
        if usage:
            res += f"\n\n{usage}"
        if body:
            res += f"\n\n{body}"
        if example:
            res += f"\n\n{example}"
        return res

    def param(self, parameter: Arg) -> str:
        """对单个参数的描述"""
        name = parameter.name
        if str(parameter.value).strip("'\"") == name:
            return f"&#91;{name}&#93;" if parameter.optional else name
        if parameter.hidden:
            return f"&#91;{name}&#93;" if parameter.optional else f"&lt;{name}&gt;"
        if parameter.value is AllParam:
            return f"&lt;...{name}&gt;"
        arg = f"&#91;{name}" if parameter.optional else f"&lt;{name}"
        if parameter.value not in (AnyOne, AnyString):
            arg += f": {parameter.value}"
        if parameter.field.display is Empty:
            arg += " = None"
        elif parameter.field.display is not None:
            arg += f" = {parameter.field.display}"
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
        return (res[:-1], [f"{v[0]}: {v[1]}" for v in notice]) if notice else (res[:-1], None)

    def opt(self, node: Option) -> str:
        alias_text = " ".join(node.requires) + (" " if node.requires else "") + "│".join(node.aliases)
        help_text = "> Unknown" if node.help_text == node.dest else f"> {node.help_text}"
        param, notice = self.parameters(node.args)
        notice_text = (
            (f"\n>\n> #### {lang.require('format', 'notice')}:\n> " + "\n> ".join(notice)) if notice else ""
        )
        return (
            f"- **{alias_text + (tuple(node.separators)[0] if param else '')}"
            f"{param.strip(' ')}**\n"
            f"{help_text}"
            f"{notice_text}\n"
        )

    def sub(self, node: Subcommand) -> str:
        """对单个子命令的描述"""
        name = " ".join(node.requires) + (" " if node.requires else "") + node.name
        opt_string = "\n".join(
            [self.opt(opt) for opt in filter(lambda x: isinstance(x, Option), node.options)]
        )
        sub_string = "".join(
            [
                self.opt(sub) # type: ignore
                for sub in filter(lambda x: isinstance(x, Subcommand), node.options)
            ]
        )
        opt_help = f"### {lang.require('format', 'subcommands.opts')}:\n" if opt_string else ""
        sub_help = f"### {lang.require('format', 'subcommands.subs')}:\n" if sub_string else ""
        param, notice = self.parameters(node.args)
        help_text = "> Unknown" if node.help_text == node.dest else f"> {node.help_text}"
        notice_text = (
            (f"\n>\n> #### {lang.require('format', 'notice')}:\n> " + "\n> ".join(notice)) if notice else ""
        )
        return (
            f"- **{name + (tuple(node.separators)[0] if param else '')}"
            f"{param}**\n"
            f"{help_text}"
            f"{notice_text}\n"
            f"{sub_help}{sub_string}"
            f"{opt_help}{opt_string}"
        )

    def body(self, parts: List[Union[Option, Subcommand]]) -> str:
        """子节点列表的描述"""
        option_string = "\n".join(
            [
                self.opt(opt) for opt in filter(lambda x: isinstance(x, Option), parts)
                if opt.name not in self.ignore_names
            ]
        )
        subcommand_string = "\n".join(
            [self.sub(sub) for sub in filter(lambda x: isinstance(x, Subcommand), parts)]
        )
        option_help = f"## {lang.require('format', 'options')}:\n" if option_string else ""
        subcommand_help = f"## {lang.require('format', 'subcommands')}:\n" if subcommand_string else ""
        return f"{subcommand_help}{subcommand_string}{option_help}{option_string}"


color_theme = {
    "msg": ("magenta", "35"),
    "warn": ("yellow", "33"),
    "info": ("blue", "34"),
    "error": ("red", "31"),
    "primary": ("cyan", "36"),
    "success": ("green", "32"),
    "req": ("bold green", "1;32")
}



class _RichTextFormatter(TextFormatter):
    csl_code: bool

    def _convert(self, content: str, style: str):
        if style not in color_theme:
            return content
        if self.csl_code:
            return f"\x1b[{color_theme[style][1]}m{content}\x1b[0m"
        content = content.replace("[", "\[")
        return f"[{color_theme[style][0]}]{content}[/]"
    def format(self, trace: Trace) -> str:
        parts = trace.body  # type: ignore
        sub_names = [i.name for i in filter(lambda x: isinstance(x, Subcommand), parts)]
        opt_names = [min(i.aliases, key=len) for i in filter(lambda x: isinstance(x, Option) and x.name not in self.ignore_names, parts)]
        sub_names = self._convert(f"{{{','.join(sub_names)}}}", "info") if sub_names else ""
        opt_names = self._convert((" ".join(f"[{i}]" for i in opt_names)), 'info') if opt_names else ""
        title = f"{lang.require('tools', 'format.ap.title')}:"
        topic = f"{self._convert(title, 'warn')} {self._convert(trace.head['name'], 'msg')} {opt_names}\n {sub_names}"
        cmd, desc, usage, example = self.header(trace.head, trace.separators)
        param = self.parameters(trace.args)
        body = self.body(parts)
        res = topic
        if desc:
            res = f"{desc}\n\n{res}"
        if param:
            _base = lang.require('tools', 'format.ap.base')
            _param = self._convert(param, 'success')
            res += f"\n\n{self._convert(_base, 'warn')}: {cmd}{param}"
        if usage:
            res += f"\n{usage}"
        if body:
            res += f"\n\n{body}"
        if example:
            res += f"\n{example}"
        return res

    def param(self, parameter: Arg) -> str:
        name = parameter.name
        if str(parameter.value).strip("'\"") == name:
            return f"[{name}]" if parameter.optional else name
        if parameter.hidden:
            return f"[{name.upper()}]" if parameter.optional else name.upper()
        if parameter.value is AllParam:
            return f"{name.upper()}..."
        arg = f"[{name.upper()}" if parameter.optional else name.upper()
        if parameter.value not in (AnyOne, AnyString):
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
        _not = self._convert(f"{lang.require('tools', 'format.ap.notice')}:", 'warn')
        return f"{res}\n{_not}\n  - " + \
            "\n  - ".join(self._convert(f"{v[0]}: {v[1]}", "success") for v in notice) if notice else res


    def header(self, root: Dict[str, Any], separators: Tuple[str, ...]):
        _usage = f"{lang.require('tools', 'format.ap.usage')}:"
        _example = f"{lang.require('tools', 'format.ap.example')}:"
        help_string = f"{desc}" if (desc := root.get("description")) else ""
        usage = f"{self._convert(_usage, 'warn')} {usage}\n" if (usage := root.get("usage")) else ""
        example = f"{self._convert(_example, 'warn')} {example}\n" if (example := root.get("example")) else ""
        prefixs = f"[{''.join(map(str, prefixs))}]" if (prefixs := root.get("prefix", [])) != [] else ""
        cmd = f"{prefixs}{root.get('name', '')}"
        sep = separators[0]
        command_string = self._convert((cmd or root["name"]) + sep, "msg")
        return command_string, help_string, usage, example

    def body(self, parts: List[Union[Option, Subcommand]]) -> str:
        options = []
        opt_description = []
        max_len = 1
        for opt in filter(
            lambda x: isinstance(x, Option) and not isinstance(x, (Completion, Shortcut)), parts
        ):
            alias_text = (
                (f'{{{" ".join(opt.requires)}}} ' if opt.requires else "")
                + ", ".join(sorted(opt.aliases, key=len))
            )
            options.append(
                self._convert(
                    f"  {alias_text}{tuple(opt.separators)[0]}{self.parameters(opt.args)}",
                    "primary"
                )
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
                self._convert(
                    f"    {name}{tuple(sub.separators)[0]}{args}",
                    "primary"
                )
            )
            sub_topic = " ".join(f"[{i.name}]" for i in sub.options)  # type: ignore
            sub_description.append(f"{sub.help_text} {sub_topic}")
        if subcommands:
            max_len = max(max(map(lambda x: len(x), subcommands)), max_len)
        option_string = "\n".join(
            f"{i.ljust(max_len)}    {j}" for i, j in zip(options, opt_description)
        )
        subcommand_string = "\n".join(
            f"{i.ljust(max_len)}    {j}" for i, j in zip(subcommands, sub_description)
        )
        _opt = f"{lang.require('tools', 'format.ap.opt')}:"
        _sub = f"{lang.require('tools', 'format.ap.sub')}:"
        option_help = f"{self._convert(_opt, 'warn')}\n" if option_string else ""
        subcommand_help = f"{self._convert(_sub, 'warn')}\n" if subcommand_string else ""
        return f"{subcommand_help}{subcommand_string}\n{option_help}{option_string}\n"

class RichTextFormatter(_RichTextFormatter):
    """argparser 风格的帮助文本格式化器, 增加 rich 的颜色标记，可用 rich.console 打印"""
    csl_code = False

class RichConsoleFormatter(_RichTextFormatter):
    """argparser 风格的帮助文本格式化器, 增加控制台颜色标记"""
    csl_code = True