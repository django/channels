#!/usr/bin/env python
"""
Quick script that returns list of TOX envs, after applying pattern expansion.
Usage example:
$ toxmatch {foo,bar}-py{2,3}
foo-py2,foo-py3,bar-py2,bar-py3

Needed because of: https://github.com/tox-dev/tox/issues/318
Taken from: https://gist.github.com/eli-collins/ef91add2bc635ccaf61738cd805cb18b
"""
from __future__ import print_function
import sys
from tox.config import parseconfig, _expand_envstr


def main(pattern):
    reqs = set(frozenset(elem.split("-")) for elem in _expand_envstr(pattern))

    def match(env):
        factors = set(env.split("-"))
        return any(factors.issuperset(req) for req in reqs)
    print(",".join(env for env in parseconfig().envlist if match(env)))


if __name__ == "__main__":
    sys.exit(main('py%s%s' % sys.version_info[:2]))
