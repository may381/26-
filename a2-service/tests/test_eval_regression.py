# -*- coding: utf-8 -*-
"""
test_eval_regression.py —— 把「改提示词必测」接入 pytest 套件
============================================================
每次改 system_prompt.txt / 护栏 / 路由后跑 pytest，若品牌规则或管线不变量被破坏，
此测试会失败，阻断回归。对应竞赛级第⑨项。
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "eval"))
from run_eval import run_all  # noqa: E402


def test_prompt_eval_regression():
    res = asyncio.run(run_all())
    assert res["total"] > 0, "测评用例为空"
    assert not res["failed"], "测评未通过: %s" % res["failed"]
