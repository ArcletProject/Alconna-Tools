from typing import Optional
from arclet.alconna import Alconna, Args, Option
from src.arclet.alconna.tools import (
    AlconnaString,
    AlconnaFormat,
    AlconnaFire,
    AlconnaDecorate,
    ObjectPattern,
    delegate,
    exclusion,
    cool_down,
    simple_type,
    ArgParserTextFormatter,
    MarkdownTextFormatter
)


def test_koishi_like():
    con = AlconnaString("con <url:url>")
    assert con.parse("con https://www.example.com").matched is True
    con_1 = AlconnaString("con_1", "--foo <foo:str:123> [bar:bool]", "--bar &True")
    assert con_1.parse("con_1 --bar").query("bar.value") is True
    assert con_1.parse("con_1 --foo").query("foo.args") == {"foo": "123"}
    con_2 = AlconnaString("[!con_2|/con_2] <foo:str> <...bar>")
    assert con_2.parse("!con_2 112 334").matched is True
    assert con_2.parse("con_2 112 334").matched is False


def test_format_like():
    con1 = AlconnaFormat("con1 {artist} {title:str} singer {name:str}")
    print('')
    print(repr(con1.get_help()))
    assert con1.parse("con1 Nameless MadWorld").artist == "Nameless"
    con1_1 = AlconnaFormat("con1_1 user {target}", {"target": str})
    assert con1_1.parse("con1_1 user Nameless").query("user.target") == "Nameless"
    con1_2 = AlconnaFormat(
        "con1_2 user {target} perm set {perm} {default}",
        {"target": str, "perm": str, "default": Args["default", bool, True]},
    )
    print(repr(con1_2.get_help()))
    assert con1_2.parse("con1_2 user Nameless perm set Admin.set True").query("perm_set.default") is True


def test_fire_like_class():
    class MyClass:
        """测试从类中构建对象"""

        def __init__(self, sender: Optional[str]):
            """Constructor"""
            self.sender = sender

        def talk(self, name="world"):
            """Test Function"""
            print(f"Hello {name} from {self.sender}")

        class Repo:
            def set(self, name):
                print(f"set {name}")

            class SubConfig:
                description = "sub-test"

        class Config:
            command = "con2"
            description = "测试"
            extra = "reject"
            get_subcommand = True

    con2 = AlconnaFire(MyClass)
    assert con2.parse("con2 Alc talk Repo set hhh").matched is True
    assert con2.parse("con2 talk Friend").query("talk.name") == "Friend"
    print('')
    print(repr(con2.get_help()))
    print(con2.instance)


def test_fire_like_object():
    class MyClass:
        def __init__(self, action=sum):
            self.action = action

        def calculator(self, a, b, c, *nums: int, **kwargs: str):
            """calculator"""
            print(a, b, c)
            print(nums, kwargs)
            print(self.action(nums))

        def test(self, a: str, b: int, *, c: bool, d: str):
            print(a, b, c, d)

        class Config:
            command = "con3"

    con3 = AlconnaFire(MyClass(sum))
    print('')
    print(con3.get_help())
    assert con3.parse("con3 calculator 1 2 3 4 5 d=6 f=7")
    assert con3.parse("con3 test abc 123 -c -d foo")


def test_fire_like_func():
    def my_function(name="world"):
        """测试从函数中构建对象"""

        class Config:
            command = "con4"
            description = "测试"

        print(f"Hello {name}!")

    con4 = AlconnaFire(my_function)
    assert con4.parse("con4 Friend").matched is True


def test_delegate():
    @delegate
    class con5:
        """hello"""
        prefix = "!"

    print(repr(con5.get_help()))


def test_click_like():
    con6 = AlconnaDecorate()

    @con6.build_command("con6")
    @con6.option("--count", Args["num", int], help="Test Option Count")
    @con6.option("--foo", Args["bar", str], help="Test Option Foo")
    def hello(bar: str, num: int = 1):
        """测试DOC"""
        print(bar * num)

    assert hello("con6 --foo John --count 2").matched is True


def test_object_pattern():
    class A:
        def __init__(self, username: str, userid: int):
            self.name = username
            self.id = userid

    pat11 = ObjectPattern(A, flag='urlget')

    assert pat11.validate("username=abcd&userid=123").success


def test_checker():
    @simple_type()
    def hello(num: int):
        return num

    assert hello(123) == 123
    assert hello("123") == 123  # type: ignore

    @simple_type()
    def test(foo: 'bar'):  # type: ignore
        return foo

    assert test("bar") == "bar"
    assert test("foo") is None


def test_exclusion():
    com2 = Alconna(
        "comp2",
        Option("foo"),
        Option("bar"),
        behaviors=[exclusion(target_path="options.foo", other_path="options.bar")]
    )
    assert com2.parse("comp2 foo").matched is True
    assert com2.parse("comp2 bar").matched is True
    assert com2.parse("comp2 foo bar").matched is False


def test_cooldown():
    import time
    com3 = Alconna("comp3", Args["bar", int], behaviors=[cool_down(0.3)])
    print('')
    for i in range(4):
        time.sleep(0.2)
        print(com3.parse(f"comp3 {i}"))


def test_formatter():
    from arclet.alconna import Alconna, Args, Option, Subcommand, CommandMeta

    alc = Alconna(
        "test1", ["!"], Args["foo#abcd", int],
        Option("--foo", Args["bar;?", str]),
        Option("aaa baz|bar|baf"),
        Option("aaa fox"),
        Option("aaa bbb fire"),
        Subcommand("--qux", [Option("aaa"), Option("bbb", Args["ccc#ddd", bool])]),
        formatter_type=MarkdownTextFormatter,
        meta=CommandMeta("text1111", "text2222", "text3333")
    )
    alc.parse("!test1 bbb --help")
    alc1 = Alconna(
        "test2", ["!"], Args["foo#3322", int],
        Option("--foo", Args["bar;?", str]),
        Option("aaa baz|bar|baf"),
        Option("aaa fox"),
        Option("aaa bbb fire"),
        Subcommand("--qux", [Option("aaa"), Option("bbb", Args["ccc#ddd", bool])], Args["a"]),
        formatter_type=ArgParserTextFormatter,
        meta=CommandMeta("text1111", "text2222", "text3333")
    )
    alc1.parse("!test2 bbb --help")