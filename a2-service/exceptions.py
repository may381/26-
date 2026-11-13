# -*- coding: utf-8 -*-
"""
exceptions.py —— A2 服务的错误码与统一异常（方案 B）
===================================================
对应《Agent 统一交互协议 v3.0》的响应码约定：外层信封 code 用 OK / 语义错误码。
这里集中维护「HTTP 状态 -> 协议错误码」的映射，main.py 路由统一引用，避免散落硬编码。
"""
from typing import Optional

# HTTP 状态 -> 协议错误码（与 P2 / 协议约定的语义一致）
ERROR_CODES = {
    400: "INVALID_ARGUMENT",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "UNPROCESSABLE_ENTITY",
    500: "INTERNAL_ERROR",
    502: "UPSTREAM_ERROR",
    503: "SERVICE_UNAVAILABLE",
    504: "UPSTREAM_TIMEOUT",
}

# 协议层错误码全集（与《Agent 统一交互协议 v3.0》对齐，供校验/文档引用）。
# 其中 UNSUPPORTED_PROTOCOL_VERSION 由 main.py 以 HTTP 400 直接返回（不占用独立状态码）。
PROTOCOL_ERROR_CODES = {
    "INVALID_ARGUMENT", "UNSUPPORTED_PROTOCOL_VERSION", "UNAUTHORIZED",
    "FORBIDDEN", "NOT_FOUND", "CONFLICT", "UNPROCESSABLE_ENTITY",
    "INTERNAL_ERROR", "UPSTREAM_ERROR", "UPSTREAM_TIMEOUT",
}


class A2Error(Exception):
    """业务异常：携带 HTTP 状态码与面向协议的错误码。"""

    def __init__(self, status: int, message: str, code: Optional[str] = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code or ERROR_CODES.get(status, "INTERNAL_ERROR")


def code_of(status: int) -> str:
    return ERROR_CODES.get(status, "INTERNAL_ERROR")
