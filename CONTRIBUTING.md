# Contributing

Contributions are welcome!

Please ensure that your pull request passes a `mypy --strict` check, and all the tests run by `pytest` and `pytest --run-slow` pass.

If you are fixing a bug, please include a test that demonstrates the bug, which fails before your fix and passes after it.

## Setting up a development environment

```
$ git clone https://github.com/maxcutlyp/deutil.git
$ cd deutil
$ python -m venv .venv
$ source .venv/bin/activate  # On Windows, use `.venv\Scripts\activate`
$ (.venv) pip install -e .[test]
$ (.venv) mypy --strict . && pytest --run-slow
```

