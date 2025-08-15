#!/usr/bin/env python3
"""
App Commands测试运行器

运行App Commands模块的所有测试用例
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path


def setup_python_path():
    """设置Python路径"""
    # 添加项目根目录到Python路径
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))


def run_tests(test_path=None, verbose=False, coverage=False, markers=None):
    """
    运行测试

    Args:
        test_path: 测试路径，如果为None则运行所有测试
        verbose: 是否显示详细输出
        coverage: 是否生成覆盖率报告
        markers: 测试标记过滤器
    """
    setup_python_path()

    # 构建pytest命令
    cmd = ["python", "-m", "pytest"]

    # 添加测试路径
    if test_path:
        cmd.append(test_path)
    else:
        cmd.append("tests/app_commands/")

    # 添加选项
    if verbose:
        cmd.append("-v")

    if coverage:
        cmd.extend([
            "--cov=similubot.app_commands",
            "--cov-report=html",
            "--cov-report=term-missing"
        ])

    if markers:
        cmd.extend(["-m", markers])

    # 添加其他有用的选项
    cmd.extend([
        "--tb=short",  # 简短的traceback
        "--strict-markers",  # 严格的标记检查
        "-ra",  # 显示所有测试结果摘要
    ])

    print(f"运行命令: {' '.join(cmd)}")
    print("-" * 50)

    # 运行测试
    try:
        result = subprocess.run(cmd, cwd=Path(__file__).parent.parent.parent)
        return result.returncode
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        return 1
    except Exception as e:
        print(f"运行测试时发生错误: {e}")
        return 1


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="运行App Commands测试")

    parser.add_argument(
        "test_path",
        nargs="?",
        help="要运行的测试路径（可选）"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细输出"
    )

    parser.add_argument(
        "-c", "--coverage",
        action="store_true",
        help="生成覆盖率报告"
    )

    parser.add_argument(
        "-m", "--markers",
        help="按标记过滤测试（例如：unit, integration, slow）"
    )

    parser.add_argument(
        "--core",
        action="store_true",
        help="只运行核心组件测试"
    )

    parser.add_argument(
        "--music",
        action="store_true",
        help="只运行音乐命令测试"
    )

    args = parser.parse_args()

    # 确定测试路径
    test_path = args.test_path

    if args.core:
        test_path = "tests/app_commands/test_core.py"
    elif args.music:
        test_path = "tests/app_commands/test_music_commands.py"

    # 运行测试
    exit_code = run_tests(
        test_path=test_path,
        verbose=args.verbose,
        coverage=args.coverage,
        markers=args.markers
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()