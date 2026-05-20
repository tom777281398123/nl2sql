#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from pathlib import Path

from dotenv import load_dotenv


def _find_project_root(identifier: str = ".env") -> Path:
    """
    动态查找项目根目录

    Args:
        identifier: 用于标识项目根目录的文件名，默认为 .env

    Returns:
        项目根目录的 Path 对象

    Raises:
        FileNotFoundError: 如果找不到项目根目录标识文件
    """
    # 第一步：优先读取环境变量（生产环境用）
    env_root = os.getenv("PROJECT_ROOT")
    if env_root and Path(env_root).absolute().exists():
        return Path(env_root).absolute()

    # 第二步：递归查找标识文件（开发环境用）
    current_dir = Path(__file__).absolute().parent
    while current_dir != current_dir.parent:
        if (current_dir / identifier).exists():
            # 加载.env文件
            load_dotenv(dotenv_path=current_dir / identifier)
            return current_dir
        current_dir = current_dir.parent

    raise FileNotFoundError(f"未找到项目根目录标识「{identifier}」，且环境变量PROJECT_ROOT未配置")


# 项目根目录常量（模块加载时计算一次）
PROJECT_ROOT = _find_project_root(".env")
