from dataclasses import asdict
from arclet.alconna import Alconna, Option, Subcommand, Args
from arclet.alconna.action import Action
from nepattern import BasePattern, AllParam, AnyOne
from typing import List

def _serialize_action(act: Action):
    data = asdict(act)
    if act.value is ...:
        data['value'] = '...'
    return data

def _serialize_args(args: Args) -> List[dict]:
    res = []
    for arg in args:
        data = asdict(arg)
        data['flag'] = list(arg.flag)
        if arg.value == AllParam:
            data['value'] = "..."
        elif arg.value == AnyOne:
            data['value'] = 'any'
        else:
            data['value'] = arg.value.alias or arg.value.origin.__name__
        res.append(data)
    return res

def _serialize_option(option: Option) -> dict:
    return {
        "name": option.name,
        "dest": option.dest,
        "args": _serialize_args(option.args),
        "aliases": list(option.aliases),
        "help_text": option.help_text,
        "requires": option.requires,
        "action": _serialize_action(option.action),
        "separators": list(option.separators),
        "priority": option.priority,
        "compact": option.compact
    }

def _serialize_subcommand(subcommand: Subcommand) -> dict:
    return {
        "name": subcommand.name,
        "dest": subcommand.dest,
        "args": _serialize_args(subcommand.args),
        "help_text": subcommand.help_text,
        "requires": subcommand.requires,
        "action": _serialize_action(subcommand.action),
        "separators": list(subcommand.separators),
        "options": [
            _serialize_subcommand(node)
            if isinstance(node, Subcommand)
            else _serialize_option(node)
            for node in subcommand.options
        ],
    }

def serialize(command: Alconna):
    res = {}
    if command.prefixes:
        headers = {"pair": isinstance(command.prefixes[0], tuple), "data": []}
        for header in command.prefixes:
            if isinstance(header, str):
                headers['data'].append(
                    {
                        'type': 'str',
                        'value': header
                    }
                )
            elif isinstance(header, type):
                headers['data'].append(
                    {
                        'type': 'type',
                        'module': header.__module__,
                        'name': header.__name__
                    }
                )
            elif isinstance(header, BasePattern):
                headers['data'].append(
                    {
                        'type': 'pattern',
                        'key': header.alias or header.origin.__name__,
                        'module': header.__module__,
                    }
                )
            elif isinstance(header, tuple):
                headers['data'].append(
                    {
                        'type': 'pair',
                        'data': [
                            {
                                'type': 'type',
                                'module': header[0].__module__,
                                'name': header[0].__name__
                            },
                            {
                                'type': 'str',
                                'value': header[1]
                            }
                        ]
                    }
                )
        res['prefixes'] = headers
    res['command'] = str(command.command)
    res['args'] = _serialize_args(command.args)
    res['options'] = [
        _serialize_subcommand(node)
        if isinstance(node, Subcommand)
        else _serialize_option(node)
        for node in command.options
    ],
    res['meta'] = asdict(command.meta)
    res['separators'] = list(command.separators)
    res['namespace'] = command.namespace
    return res

if __name__ == '__main__':
    from pprint import pprint
    import json
    alc = Alconna("test", Args["foo", str])
    pprint(serialize(alc))
    with open('test.json', 'w+', encoding='utf-8') as f:
        json.dump(serialize(alc), f, indent=2, ensure_ascii=False)