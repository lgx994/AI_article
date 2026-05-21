#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能体运行入口 - 7节点DAG版本
整合文章生成和飞书推送的完整工作流
"""

import os
import sys
import argparse
from pathlib import Path
import logging
from typing import Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from agent import CognitionDAG
from feishu_pusher import FeishuPusher


def run_daily_workflow(
    api_key: str,
    webhook_url: Optional[str] = None,
    app_id: Optional[str] = None,
    app_secret: Optional[str] = None,
    output_dir: str = "output",
    prompt_dir: str = ".",
    force_day: Optional[int] = None
) -> dict:
    """
    执行每日完整工作流（7节点DAG版本）
    
    节点流程:
    1. Trigger -> 2. StateManager -> 3. VariablePool -> 4. Planner -> 5. Writer -> 6. Reviewer -> 7. Push
    
    Returns:
        执行结果字典
    """
    results = {
        "success": False,
        "article_generated": False,
        "article_path": None,
        "pushed_to_feishu": False,
        "error": None,
        "dag_info": {}
    }
    
    try:
        # === 步骤1: 初始化DAG ===
        logger.info("🚀 初始化7节点DAG...")
        dag = CognitionDAG(api_key, prompt_dir=prompt_dir)
        
        # === 步骤2: 执行DAG ===
        logger.info("▶️ 开始执行DAG...")
        result = dag.run(force_day=force_day)
        
        if result.get("skipped"):
            logger.info("⏭️ 本次执行被跳过")
            results["skipped"] = True
            return results
        
        results["article_generated"] = True
        results["day"] = result["day"]
        results["stage"] = result["stage"]
        results["topic"] = result["variables"]["topic_theme"]
        results["sub_topic"] = result["variables"]["sub_topic"]
        results["article_type"] = result["variables"]["article_type"]
        results["word_count"] = result["word_count"]
        results["retry_count"] = result.get("retry_count", 0)
        
        # DAG执行详情
        results["dag_info"] = {
            "planning_models": result.get("writing_plan", {}).get("selected_models", []),
            "review_passed": result.get("review_result", {}).get("passed", False),
            "review_conclusion": result.get("review_result", {}).get("conclusion", "未知")
        }
        
        # === 步骤3: 保存文章 ===
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        article_file = output_path / f"day{result['day']:03d}.md"
        with open(article_file, 'w', encoding='utf-8') as f:
            f.write(result["article"])
        
        results["article_path"] = str(article_file)
        logger.info(f"💾 文章已保存: {article_file}")
        
        # 保存写作规划（用于调试）
        if result.get("writing_plan"):
            plan_file = output_path / f"day{result['day']:03d}_plan.json"
            import json
            with open(plan_file, 'w', encoding='utf-8') as f:
                json.dump(result["writing_plan"], f, ensure_ascii=False, indent=2)
            logger.info(f"💾 写作规划已保存: {plan_file}")
        
        # 保存审核结果
        if result.get("review_result"):
            review_file = output_path / f"day{result['day']:03d}_review.txt"
            with open(review_file, 'w', encoding='utf-8') as f:
                f.write(result["review_result"].get("raw_response", ""))
            logger.info(f"💾 审核结果已保存: {review_file}")
        
        # === 步骤4: 推送到飞书 ===
        if webhook_url:
            logger.info("📤 推送到飞书...")
            try:
                pusher = FeishuPusher(
                    webhook_url=webhook_url,
                    app_id=app_id,
                    app_secret=app_secret
                )
                
                push_result = pusher.push_article(
                    article_path=str(article_file),
                    day=result["day"],
                    topic=result["variables"]["topic_theme"]
                )
                
                results["pushed_to_feishu"] = True
                logger.info("✅ 飞书推送成功")
                
            except Exception as e:
                logger.error(f"❌ 飞书推送失败: {e}")
                results["push_error"] = str(e)
        else:
            logger.info("⚠️ 未配置飞书Webhook，跳过推送")
        
        results["success"] = True
        
    except Exception as e:
        logger.error(f"❌ 工作流执行失败: {e}")
        results["error"] = str(e)
        raise
    
    return results


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description='认知提升文章生成智能体 - 7节点DAG版本')
    parser.add_argument('--day', '-d', type=int, help='指定天数（默认自动递增）')
    parser.add_argument('--output', '-o', default='output', help='输出目录')
    parser.add_argument('--prompt-dir', '-p', default='.', help='提示词文件所在目录')
    parser.add_argument('--no-push', action='store_true', help='不推送到飞书')
    
    args = parser.parse_args()
    
    # 读取环境变量
    api_key = os.getenv("DEEPSEEK_API_KEY")
    webhook_url = os.getenv("FEISHU_WEBHOOK")
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    
    # 检查必要配置
    if not api_key:
        logger.error("❌ 请设置环境变量 DEEPSEEK_API_KEY")
        sys.exit(1)
    
    # 检查提示词文件是否存在
    prompt_dir = Path(args.prompt_dir)
    required_prompts = ["planner_prompt.txt", "writer_prompt.txt", "reviewer_prompt.txt", "rewriter_prompt.txt"]
    missing = [p for p in required_prompts if not (prompt_dir / p).exists()]
    if missing:
        logger.error(f"❌ 缺少提示词文件: {missing}")
        logger.error(f"   请在 {prompt_dir.absolute()} 目录下放置上述文件")
        sys.exit(1)
    
    if not args.no_push and not webhook_url:
        logger.warning("⚠️ 未设置 FEISHU_WEBHOOK，将只生成文章不推送")
    
    # 执行工作流
    try:
        results = run_daily_workflow(
            api_key=api_key,
            webhook_url=webhook_url if not args.no_push else None,
            app_id=app_id,
            app_secret=app_secret,
            output_dir=args.output,
            prompt_dir=args.prompt_dir,
            force_day=args.day
        )
        
        if results.get("skipped"):
            print("\n" + "=" * 50)
            print("⏭️ 本次执行被跳过（今天已经运行过）")
            print("=" * 50)
            return
        
        # 打印结果摘要
        print("\n" + "=" * 50)
        print("📊 执行结果摘要")
        print("=" * 50)
        print(f"第 {results.get('day')} 天文章生成完成")
        print(f"主题: {results.get('topic')} - {results.get('sub_topic')}")
        print(f"类型: {results.get('article_type')}")
        print(f"字数: {results.get('word_count')}")
        print(f"重试次数: {results.get('retry_count', 0)}")
        
        dag_info = results.get("dag_info", {})
        print(f"选用模型: {', '.join(dag_info.get('planning_models', []))}")
        print(f"审核结果: {'✅ 通过' if dag_info.get('review_passed') else '⚠️ 有问题'}")
        
        print(f"文件: {results.get('article_path')}")
        print(f"飞书推送: {'✅ 成功' if results.get('pushed_to_feishu') else '❌ 未推送'}")
        print("=" * 50)
        
    except Exception as e:
        logger.error(f"执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
