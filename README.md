# Alconna Tools

Provider various tools for Alconna

Extensions:

- `actions`: `exclusion`, `cooldown`, `inclusion`
- `checker`: `simple_type`
- `constrcut`: ` AlconnaDecorate`, `AlconnaFormat`, `AlconnaString`, `AlconnaFire`
- `formatter`: `Shell`, `Markdown`, `RichText`, `RichConsole`
- `pattern`: `ObjectPattern`

## Example:

`AlconnString`:

```python
#constrcut.py
from arclet.alconna.tools import AlconnaString

alc = (
    AlconnaString('constrcut')
    .option('alpha', '-a')          
    .option('beta', '-b [beta]')
    .option('gamma', '-c <gamma>')
    .build()
)

if __name__ == '__main__':
    alc()
```

```shell
$ python constrcut.py -a -b -c abc
{"alpha": ..., "beta": {}, "gamma": "abc"}
```
