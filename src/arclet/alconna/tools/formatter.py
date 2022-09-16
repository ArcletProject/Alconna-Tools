from typing import List, Dict, Any, Union, Set
from nepattern import Empty, AllParam, BasePattern

from arclet.alconna.args import Args, ArgUnit
from arclet.alconna.base import Subcommand, Option
from arclet.alconna.components.output import AbstractTextFormatter, Trace


class ArgParserTextFormatter(AbstractTextFormatter):
    """
    argparser 风格的帮助文本格式化器
    """
    def format(self, trace: Trace) -> str:
        parts = trace.body  # type: ignore
        sub_names = [i.name for i in filter(lambda x: isinstance(x, Subcommand), parts)]
        opt_names = [i.name for i in filter(lambda x: isinstance(x, Option), parts)]
        sub_names = (
            " ".join(f"[{i}]" for i in sub_names) if len(sub_names) < 5 else " [COMMANDS]"
        ) if sub_names else ""

        opt_names = (
            " ".join(f"[{i}]" for i in opt_names) if len(opt_names) < 6 else " [OPTIONS]"
        ) if opt_names else ""
        topic = f"{trace.head['name']} {sub_names} {opt_names}"
        header = self.header(trace.head, trace.separators)
        param = self.parameters(trace.args)
        body = self.body(parts)
        return f"{topic}\n{header % (param, body)}"

    def param(self, name: str, parameter: ArgUnit) -> str:
        arg = f"[{name.upper()}" if parameter['optional'] else name.upper()
        if not parameter['hidden']:
            if parameter['value'] is AllParam:
                return f"{name.upper()}..."
            if not isinstance(parameter['value'], BasePattern) or parameter['value'].pattern != name:
                arg += f"=[{parameter['value']}]" if parameter['kwonly'] else f"[{parameter['value']}]"
            if parameter['field'].display is Empty:
                arg += "=None"
            elif parameter['field'].display is not None:
                arg += f"={parameter['field'].display}"
        return f"{arg}]" if parameter['optional'] else arg

    def parameters(self, args: Args) -> str:
        param_texts = [self.param(k, param) for k, param in args.argument.items()]
        if len(args.separators) == 1:
            separator = tuple(args.separators)[0]
            res = separator.join(param_texts)
        else:
            res = " ".join(param_texts) + ", USED SPLIT:" + "/".join(args.separators)
        notice = [(k, param['notice']) for k, param in args.argument.items() if param['notice']]
        if not notice:
            return res
        return f"{res}\n  内容:\n  " + "\n  ".join(f"{v[0]}: {v[1]}" for v in notice)

    def header(self, root: Dict[str, Any], separators: Set[str]) -> str:
        help_string = f"\n描述: {desc}\n" if (desc := root.get('description')) else ""
        usage = f"\n用法:{usage}\n" if (usage := root.get('usage')) else ""
        example = f"\n样例:{example}\n" if (example := root.get('example')) else ""
        header_text = f"/{''.join(map(str, headers))}/" if (headers := root.get('header', [''])) != [''] else ""
        cmd = f"{header_text}{root.get('name', '')}"
        sep = tuple(separators)[0]
        command_string = cmd or (root['name'] + sep)
        return f"\n命令: {command_string}%s{help_string}{usage}%s{example}"

    def part(self, node: Union[Subcommand, Option]) -> str:
        ...

    def body(self, parts: List[Union[Option, Subcommand]]) -> str:
        option_string = ""
        options = []
        opt_description = []
        for opt in filter(lambda x: isinstance(x, Option) and x.name != "--shortcut", parts):
            alias_text = " ".join(opt.requires) + (' ' if opt.requires else '') + ", ".join(opt.aliases)
            options.append(f"  {alias_text}{tuple(opt.separators)[0]}{self.parameters(opt.args)}")
            opt_description.append(opt.help_text)
        if options:
            max_len = max(map(lambda x: len(x), options))
            option_string = "\n".join(f"{i.ljust(max_len)} {j}" for i, j in zip(options, opt_description))
        subcommand_string = ""
        subcommands = []
        sub_description = []
        for sub in filter(lambda x: isinstance(x, Subcommand), parts):
            name = " ".join(sub.requires) + (' ' if sub.requires else '') + sub.name
            sub_topic = " ".join(f"[{i.name}]" for i in sub.options)  # type: ignore
            args = self.parameters(sub.args)
            subcommands.append(f"  {name} {tuple(sub.separators)[0].join([args, sub_topic])}")
            sub_description.append(sub.help_text)
        if subcommands:
            max_len = max(map(lambda x: len(x), subcommands))
            subcommand_string = "\n".join(f"{i.ljust(max_len)} {j}" for i, j in zip(subcommands, sub_description))
        option_help = "选项:\n" if option_string else ""
        subcommand_help = "子命令:\n" if subcommand_string else ""
        return f"{subcommand_help}{subcommand_string}\n{option_help}{option_string}\n"
