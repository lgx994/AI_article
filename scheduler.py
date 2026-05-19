#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时调度模块 - 7节点DAG版本
支持本地定时运行（用于测试）和生成GitHub Actions配置
"""

import os
import json
from datetime import datetime, time
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def generate_github_actions_workflow(
    cron_schedule: str = "0 12 * * *",  # UTC 12:00 = 北京时间 20:00
    python_version: str = "3.11"
) -> str:
    """
    生成GitHub Actions工作流配置 - 适配7节点DAG架构
    
    Args:
        cron_schedule: Cron表达式（UTC时间）
        python_version: Python版本
        
    Returns:
        YAML配置内容
    """
    workflow = f"""name: Daily Cognition Article - 7 Node DAG

on:
  schedule:
    - cron: '{cron_schedule}'
  workflow_dispatch:

jobs:
  generate-and-push:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '{python_version}'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install requests
      
      - name: Run 7-node DAG
        env:
          DEEPSEEK_API_KEY: ${{{{ secrets.DEEPSEEK_API_KEY }}}}
          FEISHU_WEBHOOK: ${{{{ secrets.FEISHU_WEBHOOK }}}}
          FEISHU_APP_ID: ${{{{ secrets.FEISHU_APP_ID }}}}
          FEISHU_APP_SECRET: ${{{{ secrets.FEISHU_APP_SECRET }}}}
        run: |
          python run.py --output output --prompt-dir .
      
      - name: Commit and push state
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add agent_state.json output/
          git commit -m "📚 Day $(cat agent_state.json | python -c 'import json,sys; print(json.load(sys.stdin)[\"day\"])') article generated via 7-node DAG" || echo "No changes to commit"
          git push
"""
    return workflow


def setup_scheduler(
    output_path: str = ".github/workflows/daily.yml",
    hour: int = 20,
    minute: int = 0
):
    """
    设置定时调度
    
    Args:
        output_path: GitHub Actions工作流文件路径
        hour: 小时（北京时间）
        minute: 分钟
    """
    # 转换为UTC时间
    utc_hour = (hour - 8) % 24
    cron = f"{minute} {utc_hour} * * *"
    
    workflow_content = generate_github_actions_workflow(cron_schedule=cron)
    
    # 创建目录
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 写入文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(workflow_content)
    
    logger.info(f"✅ GitHub Actions工作流已创建: {output_file}")
    logger.info(f"   定时: 每天北京时间 {hour:02d}:{minute:02d}")
    logger.info(f"   Cron: {cron} (UTC)")
    logger.info(f"   节点: 7节点DAG (Trigger->State->Variable->Planner->Writer->Reviewer->Push)")
    
    return output_file


def generate_local_scheduler_script(
    hour: int = 20,
    minute: int = 0,
    output_path: str = "run_scheduler.sh"
) -> str:
    """
    生成本地定时运行脚本（使用cron）
    
    Args:
        hour: 小时
        minute: 分钟
        output_path: 输出脚本路径
    """
    script = f"""#!/bin/bash
# 认知智能体7节点DAG定时运行脚本
# 每天 {hour:02d}:{minute:02d} 执行
#
# 节点流程:
# 1.Trigger -> 2.StateManager -> 3.VariablePool -> 4.Planner -> 5.Writer -> 6.Reviewer -> 7.Push

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查环境变量
if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "错误: 请设置 DEEPSEEK_API_KEY 环境变量"
    exit 1
fi

# 检查提示词文件
for file in planner_prompt.txt writer_prompt.txt reviewer_prompt.txt rewriter_prompt.txt; do
    if [ ! -f "$file" ]; then
        echo "错误: 缺少提示词文件 $file"
        exit 1
    fi
done

# 运行7节点DAG
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始执行7节点DAG..."
python3 run.py --output output --prompt-dir .

# 检查执行结果
if [ $? -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] DAG执行成功"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] DAG执行失败"
fi
"""
    
    with open(output_path, 'w') as f:
        f.write(script)
    
    os.chmod(output_path, 0o755)
    logger.info(f"✅ 本地运行脚本已创建: {output_path}")
    
    # 打印crontab配置建议
    print("\n📋 请添加以下crontab配置:")
    print(f"   {minute} {hour} * * * /bin/bash {Path(output_path).absolute()}")
    print("\n添加方法:")
    print("   crontab -e")
    print("   # 添加上面一行，保存退出")
    
    return output_path


def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='设置7节点DAG定时调度')
    parser.add_argument('--hour', '-H', type=int, default=20, help='小时（北京时间）')
    parser.add_argument('--minute', '-M', type=int, default=0, help='分钟')
    parser.add_argument('--local', '-l', action='store_true', help='生成本地脚本')
    parser.add_argument('--output', '-o', help='输出路径')
    
    args = parser.parse_args()
    
    if args.local:
        output = args.output or "run_scheduler.sh"
        generate_local_scheduler_script(args.hour, args.minute, output)
    else:
        output = args.output or ".github/workflows/daily.yml"
        setup_scheduler(output, args.hour, args.minute)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
