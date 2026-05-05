"""
Tool Registry — @tool decorator pattern.
LLM đọc docstring để biết khi nào dùng tool, không biết SQL bên dưới.
"""
from functools import wraps
from typing import Callable
import structlog

log = structlog.get_logger()

# Registry toàn cục: {tool_name: callable}
_TOOL_REGISTRY: dict[str, Callable] = {}


def tool(fn: Callable) -> Callable:
    """
    Decorator đăng ký function vào Tool Registry.
    Mỗi tool phải có docstring mô tả rõ:
    - Dùng khi nào
    - Input là gì
    - Output trả về gì
    """
    name = fn.__name__
    _TOOL_REGISTRY[name] = fn

    @wraps(fn)
    def wrapper(*args, **kwargs):
        log.info("tool_called", tool=name, args=args, kwargs=list(kwargs.keys()))
        try:
            result = fn(*args, **kwargs)
            log.info("tool_success", tool=name, result_len=len(result) if isinstance(result, list) else 1)
            return result
        except Exception as e:
            log.error("tool_error", tool=name, error=str(e))
            raise

    wrapper.__tool__ = True
    wrapper.__tool_name__ = name
    return wrapper


def get_tool(name: str) -> Callable | None:
    return _TOOL_REGISTRY.get(name)


def get_tools_for_scope(tool_names: list[str]) -> list[Callable]:
    """Trả về list tools theo tên — dùng bởi Domain Router."""
    return [_TOOL_REGISTRY[n] for n in tool_names if n in _TOOL_REGISTRY]


def list_tools() -> list[str]:
    return list(_TOOL_REGISTRY.keys())
