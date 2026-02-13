"""
工具函数定义 - Gods Platform
支持 Agent 间通信和文件操作
"""
from pathlib import Path
import json
import fcntl
import os
from langchain.tools import tool


@tool
def check_inbox(agent_id: str) -> str:
    """
    检查并读取指定 Agent 的收件箱。
    
    Args:
        agent_id: Agent 的唯一标识符
        
    Returns:
        收件箱中的所有消息（JSON 格式）
    """
    project_root = Path(__file__).parent.parent.absolute()
    buffer_path = project_root / "gods_platform" / "buffers" / f"{agent_id}.jsonl"
    
    if not buffer_path.exists():
        return json.dumps([])
    
    messages = []
    with open(buffer_path, "r+", encoding="utf-8") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX)
            for line in f:
                if line.strip():
                    messages.append(json.loads(line))
            # 读取后清空
            f.seek(0)
            f.truncate()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    
    return json.dumps(messages, ensure_ascii=False)


@tool
def send_message(from_id: str, to_id: str, message: str) -> str:
    """
    发送消息给另一个 Agent。
    
    Args:
        from_id: 发送者 ID
        to_id: 接收者 ID
        message: 消息内容
        
    Returns:
        发送状态
    """
    import time
    project_root = Path(__file__).parent.parent.absolute()
    buffer_dir = project_root / "gods_platform" / "buffers"
    buffer_dir.mkdir(parents=True, exist_ok=True)
    
    target_buffer = buffer_dir / f"{to_id}.jsonl"
    
    msg_data = {
        "timestamp": time.time(),
        "from": from_id,
        "type": "private",
        "content": message
    }
    
    with open(target_buffer, "a", encoding="utf-8") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(json.dumps(msg_data, ensure_ascii=False) + "\n")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    
    return f"消息已发送至 {to_id}"


@tool
def read_file(path: str) -> str:
    """
    读取指定文件的内容。
    
    Args:
        path: 文件路径（相对于项目根目录）
    """
    project_root = Path(__file__).parent.parent.absolute()
    file_path = (project_root / path).absolute()
    
    if not str(file_path).startswith(str(project_root)):
        return "Error: Permission denied. Access restricted to project root."
        
    if not file_path.exists():
        return f"Error: File {path} not found."
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            content = f.read()
            fcntl.flock(f, fcntl.LOCK_UN)
            return content
    except Exception as e:
        return f"Error reading file: {str(e)}"


@tool
def write_file(path: str, content: str) -> str:
    """
    向指定文件写入内容（覆盖）。
    
    Args:
        path: 文件路径（相对于项目根目录）
        content: 写入内容
    """
    project_root = Path(__file__).parent.parent.absolute()
    file_path = (project_root / path).absolute()
    
    if not str(file_path).startswith(str(project_root)):
        return "Error: Permission denied. Access restricted to project root."
    
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(content)
            fcntl.flock(f, fcntl.LOCK_UN)
            return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"


@tool
def list_dir(path: str = ".") -> str:
    """
    列出指定目录下的文件和目录。
    
    Args:
        path: 目录路径（相对于项目根目录）
    """
    project_root = Path(__file__).parent.parent.absolute()
    dir_path = (project_root / path).absolute()
    
    if not str(dir_path).startswith(str(project_root)):
        return "Error: Permission denied."
        
    if not dir_path.exists() or not dir_path.is_dir():
        return f"Error: Directory {path} not found."
        
    try:
        items = os.listdir(dir_path)
        result = []
        for item in items:
            p = dir_path / item
            if item.startswith('.'): continue
            type_str = "[DIR]" if p.is_dir() else "[FILE]"
            result.append(f"{type_str} {item}")
        return "\n".join(result)
    except Exception as e:
        return f"Error listing directory: {str(e)}"


@tool
def grep_search(pattern: str, path: str = ".") -> str:
    """
    在指定目录下搜索匹配模式的文件行。
    
    Args:
        pattern: 正则表达式模式
        path: 搜索起始目录
    """
    import re
    project_root = Path(__file__).parent.parent.absolute()
    dir_path = (project_root / path).absolute()
    
    if not str(dir_path).startswith(str(project_root)):
        return "Error: Permission denied."
        
    matches = []
    try:
        for p in dir_path.rglob("*"):
            if p.is_file() and not any(part.startswith('.') for part in p.parts):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        for i, line in enumerate(f, 1):
                            if re.search(pattern, line):
                                rel_path = p.relative_to(project_root)
                                matches.append(f"{rel_path}:{i}: {line.strip()}")
                except:
                    continue
        return "\n".join(matches) if matches else "No matches found."
    except Exception as e:
        return f"Error searching: {str(e)}"


# 导出工具列表
GODS_TOOLS = [check_inbox, send_message, read_file, write_file, list_dir, grep_search]
