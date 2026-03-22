import os
import sys
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional
from langchain_core.tools import tool


PROJECT_ROOT = Path(__file__).parent.resolve()
ALLOWED_DIRS = [
    PROJECT_ROOT / "skills",
    PROJECT_ROOT / "workspace",
    PROJECT_ROOT / "conversations",
    PROJECT_ROOT / "output",
]


def _validate_path(path: str) -> Path:
    p = Path(path).resolve()
    for allowed in ALLOWED_DIRS:
        if str(p).startswith(str(allowed)):
            return p
    raise PermissionError(f"Access denied: {path} is outside allowed directories")


@tool
def Read(path: str, encoding: str = "utf-8") -> str:
    """读取文件内容

    Args:
        path: 文件路径（必须是绝对路径或相对于项目目录的路径）
        encoding: 文件编码，默认 utf-8
    """
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / path

    validated = _validate_path(str(p))

    if not validated.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not validated.is_file():
        raise IsADirectoryError(f"Expected file, got directory: {path}")

    try:
        return validated.read_text(encoding=encoding)
    except UnicodeDecodeError:
        return f"[Binary file: {path}]"


@tool
def Write(path: str, content: str, encoding: str = "utf-8") -> str:
    """写入文件内容

    Args:
        path: 文件路径
        content: 文件内容
        encoding: 文件编码，默认 utf-8
    """
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / path

    validated = _validate_path(str(p))
    validated.parent.mkdir(parents=True, exist_ok=True)

    validated.write_text(content, encoding=encoding)
    return f"Successfully wrote to {path}"


@tool
def Bash(command: str, timeout: int = 60) -> str:
    """执行 Shell 命令

    Args:
        command: 要执行的命令
        timeout: 超时时间（秒），默认 60
    """
    if not command or not command.strip():
        raise ValueError("Command cannot be empty")

    if any(blocked in command for blocked in ["rm -rf /", "mkfs", ":(){ :|:& };:"]):
        raise PermissionError(f"Command not allowed: potentially dangerous command detected")

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT)
        )

        if result.returncode != 0:
            return f"Command failed with exit code {result.returncode}:\n{result.stderr}"

        return result.stdout if result.stdout else "Command executed successfully"

    except subprocess.TimeoutExpired:
        return f"Command timeout after {timeout} seconds"
    except Exception as e:
        return f"Command execution failed: {str(e)}"


@tool
def Glob(pattern: str) -> List[str]:
    """按模式搜索文件

    Args:
        pattern: 文件匹配模式，如 "*.py", "**/*.md"
    """
    results = []

    for base_dir in ALLOWED_DIRS:
        if base_dir.exists():
            for f in base_dir.glob(pattern):
                if f.is_file():
                    results.append(str(f.relative_to(PROJECT_ROOT)))

    return results if results else [f"No files matching pattern: {pattern}"]


@tool
def Grep(pattern: str, path: str = "./", encoding: str = "utf-8") -> str:
    """在文件中搜索文本

    Args:
        pattern: 要搜索的文本
        path: 搜索的目录或文件路径
        encoding: 文件编码
    """
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / path

    validated = _validate_path(str(p))

    if not validated.exists():
        return f"Path not found: {path}"

    matches = []
    search_paths = [validated] if validated.is_file() else list(validated.rglob("*"))

    for f in search_paths:
        if f.is_file() and f.match("*.py"):
            try:
                content = f.read_text(encoding=encoding)
                for i, line in enumerate(content.splitlines(), 1):
                    if pattern in line:
                        matches.append(f"{f.relative_to(PROJECT_ROOT)}:{i}: {line.strip()}")
            except Exception:
                pass

    if not matches:
        return f"No matches found for: {pattern}"

    return "\n".join(matches[:50])


def get_skill_tools():
    return [Read, Write, Bash, Glob, Grep]
