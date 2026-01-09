#!/usr/bin/env python
"""
测试运行脚本

提供便捷的测试运行命令
"""
import sys
import subprocess


def run_command(cmd, description):
    """运行命令并显示结果"""
    print(f"\n{'='*60}")
    print(f"🧪 {description}")
    print(f"{'='*60}")
    print(f"命令: {' '.join(cmd)}\n")

    result = subprocess.run(cmd)

    if result.returncode == 0:
        print(f"\n✅ {description} - 成功")
    else:
        print(f"\n❌ {description} - 失败")

    return result.returncode == 0


def main():
    """主函数"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
    else:
        command = "all"

    if command == "all":
        # 运行所有测试
        success = run_command(
            ["pytest", "tests/", "-v"],
            "运行所有测试"
        )

    elif command == "unit":
        # 运行单元测试
        success = run_command(
            ["pytest", "tests/unit/", "-v"],
            "运行单元测试"
        )

    elif command == "integration":
        # 运行集成测试
        success = run_command(
            ["pytest", "tests/integration/", "-v"],
            "运行集成测试"
        )

    elif command == "cov":
        # 生成覆盖率报告
        success = run_command(
            ["pytest", "--cov=src", "--cov-report=html", "tests/"],
            "生成测试覆盖率报告"
        )

        if success:
            print("\n📊 覆盖率报告已生成: htmlcov/index.html")

    elif command == "fast":
        # 快速测试（跳过慢速测试）
        success = run_command(
            ["pytest", "tests/", "-m", "not slow", "-v"],
            "运行快速测试"
        )

    else:
        print(f"❌ 未知命令: {command}")
        print("\n可用命令:")
        print("  all      - 运行所有测试（默认）")
        print("  unit     - 运行单元测试")
        print("  integration - 运行集成测试")
        print("  cov      - 生成测试覆盖率报告")
        print("  fast     - 运行快速测试（跳过慢速测试）")
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
