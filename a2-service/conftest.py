# -*- coding: utf-8 -*-
"""
conftest.py（a2_service 根目录）—— pytest 全局配置
====================================================
1) 把本目录加入 sys.path，使测试文件能 `import main / agent_logic / schemas` 等模块；
2) 在导入任何业务模块【之前】注入测试环境变量（A2_API_KEY / 临时 DB 路径等），
   否则 settings 模块在导入时会因缺少密钥而 SystemExit。
"""
import os
import sys
import tempfile

# 必须在 import 业务模块前设置
os.environ["A2_API_KEY"] = "test-key-0000000000000000"
os.environ["A2_LLM_ENABLED"] = "true"
os.environ["A2_DB_PATH"] = os.path.join(tempfile.gettempdir(), "a2_test_receipts.db")

sys.path.insert(0, os.path.dirname(__file__))
