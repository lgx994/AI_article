#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
认知提升文章生成智能体 - 7节点DAG架构
基于 DeepSeek API 的多节点文章创作智能体

节点流程:
1. Trigger -> 2. StateManager -> 3. VariablePool -> 4. Planner -> 5. Writer -> 6. Reviewer -> 7. Pusher/Rewriter
"""

import os
import json
import random
import re
import requests
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict, field
from pathlib import Path
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ArticleVariables:
    """文章变量配置"""
    article_type: str
    tone_role: str
    topic_theme: str
    sub_topic: str
    opening_style: str
    ending_style: str
    model_count: int
    first_person: str
    forbidden_words: List[str]
    structure_type: str = "标准结构"
    external_anchor: Optional[str] = None


@dataclass
class WritingPlan:
    """写作规划输出"""
    structure_type: str
    selected_models: List[str]
    opening_design: str
    ending_design: str
    sections: List[str]
    special_notes: str


@dataclass
class ReviewResult:
    """审核结果"""
    passed: bool
    issues: List[Dict[str, str]]
    conclusion: str


@dataclass
class AgentState:
    """智能体状态"""
    day: int = 0
    stage: str = "认知觉察"
    last_article_type: Optional[str] = None
    last_tone_role: Optional[str] = None
    last_topic: Optional[str] = None
    history: List[Dict] = field(default_factory=list)


# ============ 变量池 (节点3) ============

class VariablePool:
    """变量池管理 - 节点3"""
    
    ARTICLE_TYPES = [
        "叙事主导型", "模型主导型", "观察笔记型",
        "书信/对话型", "场景切片型", "问答/假想对话型"
    ]
    
    TONE_ROLES = ["学长型", "观察者型", "同行者型", "反思者型", "讲述者型"]
    
    TOPICS = {
        "注意力": ["多巴胺机制", "默认模式网络", "注意力残留", "深度工作 vs 多任务"],
        "激励机制": ["可变比率强化", "外在 vs 内在动机", "上瘾设计", "即时反馈"],
        "博弈与合作": ["囚徒困境", "公地悲剧", "信任博弈", "重复博弈策略"],
        "风险与概率": ["损失厌恶", "黑天鹅", "正态分布误解", "赌徒谬误"],
        "制度与规则": ["激励相容", "科斯定理", "代理问题", "制度惯性"],
        "历史惯性": ["路径依赖", "锁定效应", "关键节点", "制度变迁"],
        "信息环境": ["算法茧房", "信息级联", "回音室", "信息过载策略"],
        "AI与人类": ["AI推理边界", "人机协作", "AI作为外脑", "替代焦虑的本质"],
        "自我与身份": ["社会比较", "自我叙事", "身份认同", "角色扮演"],
        "时间与耐心": ["双曲贴现", "延迟满足", "时间不一致", "长期主义错觉"],
        "复杂系统": ["涌现", "二阶效应", "非线性", "反馈循环"],
        "语言与认知": ["框架效应", "隐喻塑造思维", "叙事自我", "语言对情绪的影响"]
    }
    
    OPENING_STYLES = ["场景开场", "疑问开场", "引用开场", "自我暴露开场", "反常识开场", "留白开场"]
    ENDING_STYLES = ["开放式问题", "行动微调", "留白", "与开头呼应", "未来预告"]
    FIRST_PERSON_LEVELS = ["标准", "高", "低"]
    
    FORBIDDEN_WORDS = [
        "本质上", "从根本上说", "毋庸置疑", "毫无疑问",
        "在当今社会", "在当今时代", "值得注意的是", "需要指出的是",
        "首先…其次…最后…", "综上所述", "总而言之",
        "让你", "教会你", "帮你搞定", "你只需要", "你一定要",
        "简单来说", "换句话说", "而且…而且…而且…", "我们都"
    ]
    
    @classmethod
    def get_stage(cls, day: int) -> str:
        if day <= 30: return "认知觉察"
        elif day <= 90: return "现实理解"
        elif day <= 180: return "结构与文明"
        elif day <= 270: return "主体性与秩序"
        else: return "创造与风格"
    
    @classmethod
    def get_week_topic(cls, day: int) -> str:
        topics = list(cls.TOPICS.keys())
        week = (day - 1) // 7
        return topics[week % len(topics)]
    
    @classmethod
    def draw_variables(cls, day: int, last_state: Optional[AgentState] = None) -> ArticleVariables:
        """抽取文章变量 - 从课程大纲获取主题"""
        
        # === 新增：从 schedule.json 获取当天的主题 ===
        schedule = cls.load_schedule()
        day_schedule = schedule.get(str(day), {})
        
        topic_theme = day_schedule.get("topic", cls.get_week_topic(day))
        sub_topic = day_schedule.get("subtopic", random.choice(cls.TOPICS.get(topic_theme, ["认知提升"])))
        # ==========================================
        
        # 文章类型（循环轮换）
        article_type_idx = (day - 1) % len(cls.ARTICLE_TYPES)
        article_type = cls.ARTICLE_TYPES[article_type_idx]
        
        if last_state and last_state.last_article_type == article_type:
            article_type_idx = (article_type_idx + 1) % len(cls.ARTICLE_TYPES)
            article_type = cls.ARTICLE_TYPES[article_type_idx]
        
        # 语气角色（防重复）
        available_tones = [t for t in cls.TONE_ROLES if t != (last_state.last_tone_role if last_state else None)]
        tone_role = random.choice(available_tones if available_tones else cls.TONE_ROLES)
        
        # 开场/结尾
        opening_style = random.choice(cls.OPENING_STYLES)
        ending_style = random.choice(cls.ENDING_STYLES)
        
        # 模型数量
        stage = cls.get_stage(day)
        if article_type == "模型主导型":
            model_count = 2
        elif stage in ["认知觉察"]:
            model_count = random.choice([0, 1])
        elif stage in ["现实理解", "结构与文明"]:
            model_count = random.choice([1, 2])
        else:
            model_count = random.choice([0, 1, 2])
        
        first_person = random.choice(cls.FIRST_PERSON_LEVELS)
        forbidden_words = random.sample(cls.FORBIDDEN_WORDS, k=random.randint(3, 4))
        
        return ArticleVariables(
            article_type=article_type, tone_role=tone_role,
            topic_theme=topic_theme, sub_topic=sub_topic,  # 使用课程大纲的主题
            opening_style=opening_style, ending_style=ending_style,
            model_count=model_count, first_person=first_person,
            forbidden_words=forbidden_words
        )
    
    @classmethod
    def load_schedule(cls) -> Dict:
        """加载课程大纲"""
        schedule_file = Path("schedule.json")
        if schedule_file.exists():
            with open(schedule_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}


# ============ API客户端 ============

class DeepSeekClient:
    """DeepSeek API 客户端"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.url = "https://api.deepseek.com/v1/chat/completions"
    
    def call(self, prompt: str, model: str = "deepseek-chat", temperature: float = 0.7, max_tokens: int = 4000) -> str:
        """调用API"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "enable_search": True  # 启用联网搜索
        }
        
        try:
            response = requests.post(self.url, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"API调用失败: {e}")
            raise


# ============ 7个节点实现 ============

class NodeTrigger:
    """节点1: 触发器"""
    def __init__(self):
        self.name = "Trigger"
    
    def execute(self, context: Dict) -> Dict:
        logger.info(f"[{self.name}] 触发执行")
        context["should_run"] = True
        return context


class NodeStateManager:
    """节点2: 状态管理"""
    def __init__(self, state_file: str = "agent_state.json"):
        self.name = "StateManager"
        self.state_file = Path(state_file)
    
    def load_state(self) -> AgentState:
    # 读取 state.json（只有一行：{"day": 1}）
        state_file = Path("state.json")
        if state_file.exists():
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            day = data.get("day", 1)
        else:
            day = 1
    
        return AgentState(day=day, stage=VariablePool.get_stage(day))
    
    def save_state(self, state: AgentState):
        # 只保存天数到 state.json
        with open("state.json", 'w', encoding='utf-8') as f:
            json.dump({"day": state.day}, f, ensure_ascii=False)
    
    # 历史记录保存到 agent_state.json（可选）
    with open("agent_state.json", 'w', encoding='utf-8') as f:
        json.dump(asdict(state), f, ensure_ascii=False, indent=2)
    
    def execute(self, context: Dict) -> Dict:
        logger.info(f"[{self.name}] 加载状态")
        
        state = self.load_state()
        force_day = context.get("force_day")
        
        if force_day:
            state.day = force_day
        else:
            state.day = state.day + 1 if state.day > 0 else 1
        
        state.stage = VariablePool.get_stage(state.day)
        
        context["state"] = state
        context["day"] = state.day
        context["stage"] = state.stage
        
        logger.info(f"  Day {state.day}, Stage: {state.stage}")
        return context
    
    def finalize(self, context: Dict):
        """最终保存"""
        state = context.get("state")
        if state:
            state.last_article_type = context.get("variables", {}).get("article_type")
            state.last_tone_role = context.get("variables", {}).get("tone_role")
            state.last_topic = context.get("variables", {}).get("topic_theme")
            
            if context.get("article"):
                state.history.append({
                    "day": state.day,
                    "topic": context["variables"].get("topic_theme"),
                    "sub_topic": context["variables"].get("sub_topic"),
                    "article_type": context["variables"].get("article_type"),
                    "passed": context.get("review_result", {}).get("passed", False)
                })
            
            self.save_state(state)
            logger.info(f"[{self.name}] 状态已保存")


class NodeVariablePool:
    """节点3: 变量抽取"""
    def __init__(self):
        self.name = "VariablePool"
    
    def execute(self, context: Dict) -> Dict:
        logger.info(f"[{self.name}] 抽取变量")
        
        state = context.get("state")
        variables = VariablePool.draw_variables(context["day"], state)
        
        context["variables"] = asdict(variables)
        
        logger.info(f"  类型: {variables.article_type}")
        logger.info(f"  主题: {variables.topic_theme} - {variables.sub_topic}")
        logger.info(f"  语气: {variables.tone_role}")
        logger.info(f"  模型数: {variables.model_count}")
        
        return context


class NodePlanner:
    """节点4: 写作规划 - 调用planner_prompt.txt"""
    def __init__(self, client: DeepSeekClient, prompt_file: str = "planner_prompt.txt"):
        self.name = "Planner"
        self.client = client
        self.prompt_file = Path(prompt_file)
    
    def _load_prompt_template(self) -> str:
        if self.prompt_file.exists():
            with open(self.prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        raise FileNotFoundError(f"找不到规划提示词文件: {self.prompt_file}")
    
    def _build_prompt(self, context: Dict) -> str:
        template = self._load_prompt_template()
        
        # 获取明天的主题（用于预告）
        next_day = context["day"] + 1
        next_topic = VariablePool.get_week_topic(next_day)
        next_sub_topic = random.choice(VariablePool.TOPICS[next_topic])
        
        prompt = template
        prompt = prompt.replace("{{DAY}}", str(context["day"]))
        prompt = prompt.replace("{{STAGE}}", context["stage"])
        prompt = prompt.replace("{{ARTICLE_TYPE}}", context["variables"]["article_type"])
        prompt = prompt.replace("{{TONE_ROLE}}", context["variables"]["tone_role"])
        prompt = prompt.replace("{{TOPIC_THEME}}", context["variables"]["topic_theme"])
        prompt = prompt.replace("{{SUB_TOPIC}}", context["variables"]["sub_topic"])
        prompt = prompt.replace("{{OPENING_STYLE}}", context["variables"]["opening_style"])
        prompt = prompt.replace("{{ENDING_STYLE}}", context["variables"]["ending_style"])
        prompt = prompt.replace("{{MODEL_COUNT}}", str(context["variables"]["model_count"]))
        prompt = prompt.replace("{{FORBIDDEN_WORDS}}", "、".join(context["variables"]["forbidden_words"]))
        prompt = prompt.replace("{{EXTERNAL_ANCHOR}}", context["variables"].get("external_anchor") or "无")
        
        return prompt
    
    def execute(self, context: Dict) -> Dict:
        logger.info(f"[{self.name}] 生成写作规划")
        
        prompt = self._build_prompt(context)
        response = self.client.call(prompt, model="deepseek-chat")
        
        # 解析JSON响应
        try:
            # 提取JSON部分
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                plan_data = json.loads(json_match.group())
            else:
                plan_data = json.loads(response)
            
            plan = WritingPlan(**plan_data)
            context["writing_plan"] = asdict(plan)
            
            logger.info(f"  结构: {plan.structure_type}")
            logger.info(f"  模型: {plan.selected_models}")
            logger.info(f"  开场: {plan.opening_design[:30]}...")
            
        except Exception as e:
            logger.error(f"解析规划失败: {e}")
            logger.error(f"原始响应: {response[:500]}")
            raise
        
        return context


class NodeWriter:
    """节点5: 文章写作 - 调用writer_prompt.txt"""
    def __init__(self, client: DeepSeekClient, prompt_file: str = "writer_prompt.txt"):
        self.name = "Writer"
        self.client = client
        self.prompt_file = Path(prompt_file)
    
    def _load_prompt_template(self) -> str:
        if self.prompt_file.exists():
            with open(self.prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        raise FileNotFoundError(f"找不到写作提示词文件: {self.prompt_file}")
    
    def _build_prompt(self, context: Dict) -> str:
        template = self._load_prompt_template()
        
        # 获取明天的主题
        next_day = context["day"] + 1
        next_topic = VariablePool.get_week_topic(next_day)
        next_sub_topic = random.choice(VariablePool.TOPICS[next_topic])
        
        plan = context.get("writing_plan", {})
        
        prompt = template
        prompt = prompt.replace("{{DAY}}", str(context["day"]))
        prompt = prompt.replace("{{STAGE}}", context["stage"])
        prompt = prompt.replace("{{ARTICLE_TYPE}}", context["variables"]["article_type"])
        prompt = prompt.replace("{{TONE_ROLE}}", context["variables"]["tone_role"])
        prompt = prompt.replace("{{TOPIC_THEME}}", context["variables"]["topic_theme"])
        prompt = prompt.replace("{{SUB_TOPIC}}", context["variables"]["sub_topic"])
        prompt = prompt.replace("{{OPENING_STYLE}}", context["variables"]["opening_style"])
        prompt = prompt.replace("{{ENDING_STYLE}}", context["variables"]["ending_style"])
        prompt = prompt.replace("{{STRUCTURE_TYPE}}", plan.get("structure_type", "标准结构"))
        prompt = prompt.replace("{{MODEL_PLAN}}", json.dumps(plan.get("selected_models", []), ensure_ascii=False))
        prompt = prompt.replace("{{FIRST_PERSON}}", context["variables"]["first_person"])
        prompt = prompt.replace("{{FORBIDDEN_WORDS}}", "、".join(context["variables"]["forbidden_words"]))
        prompt = prompt.replace("{{EXTERNAL_ANCHOR}}", context["variables"].get("external_anchor") or "")
        prompt = prompt.replace("{{NEXT_TOPIC}}", next_topic)
        prompt = prompt.replace("{{NEXT_SUBTOPIC}}", next_sub_topic)
        
        return prompt
    
    def execute(self, context: Dict) -> Dict:
        logger.info(f"[{self.name}] 生成文章")
        
        prompt = self._build_prompt(context)
        article = self.client.call(prompt, model="deepseek-chat", max_tokens=6000)
        
        context["article"] = article
        context["word_count"] = len(article.replace(' ', '').replace('\n', ''))
        
        logger.info(f"  文章长度: {context['word_count']} 字")
        
        return context


class NodeReviewer:
    """节点6: 审核 - 调用reviewer_prompt.txt"""
    def __init__(self, client: DeepSeekClient, prompt_file: str = "reviewer_prompt.txt"):
        self.name = "Reviewer"
        self.client = client
        self.prompt_file = Path(prompt_file)
    
    def _load_prompt_template(self) -> str:
        if self.prompt_file.exists():
            with open(self.prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        raise FileNotFoundError(f"找不到审核提示词文件: {self.prompt_file}")
    
    def _build_prompt(self, context: Dict) -> str:
        template = self._load_prompt_template()
        
        # 获取明天的主题
        next_day = context["day"] + 1
        next_topic = VariablePool.get_week_topic(next_day)
        
        prompt = template
        prompt = prompt.replace("{{DAY}}", str(context["day"]))
        prompt = prompt.replace("{{TOPIC_THEME}}", context["variables"]["topic_theme"])
        prompt = prompt.replace("{{SUB_TOPIC}}", context["variables"]["sub_topic"])
        prompt = prompt.replace("{{NEXT_TOPIC}}", next_topic)
        prompt = prompt.replace("{{ARTICLE}}", context["article"])
        
        return prompt
    
    def execute(self, context: Dict) -> Dict:
        logger.info(f"[{self.name}] 审核文章")
        
        prompt = self._build_prompt(context)
        response = self.client.call(prompt, model="deepseek-chat", max_tokens=3000)
        
        # 解析审核结果
        review_result = self._parse_review(response)
        context["review_result"] = review_result
        
        if review_result["passed"]:
            logger.info(f"  ✅ 审核通过")
        else:
            logger.warning(f"  ❌ 审核不通过")
            for issue in review_result["issues"]:
                logger.warning(f"    - {issue.get('item')}: {issue.get('reason', '')}")
        
        return context
    
    def _parse_review(self, response: str) -> Dict:
        """解析审核响应"""
        issues = []
        passed = False
        
        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('-') or line.startswith('•'):
                # 解析每个审核项
                if '❌' in line or '不通过' in line:
                    # 提取项目名和原因
                    match = re.search(r'[\-•]\s*(.+?)[:：]\s*❌\s*不通过[（(](.+?)[)）]', line)
                    if match:
                        issues.append({
                            "item": match.group(1).strip(),
                            "reason": match.group(2).strip()
                        })
                    else:
                        issues.append({"item": line, "reason": ""})
        
        # 判断结论
        if "结论：通过" in response or "结论: 通过" in response:
            passed = True
        
        return {
            "passed": passed,
            "issues": issues,
            "raw_response": response,
            "conclusion": "通过" if passed else "建议修改" if issues else "必须重写"
        }


class NodeRewriter:
    """节点7b: 重写 - 调用rewriter_prompt.txt"""
    def __init__(self, client: DeepSeekClient, prompt_file: str = "rewriter_prompt.txt"):
        self.name = "Rewriter"
        self.client = client
        self.prompt_file = Path(prompt_file)
    
    def _load_prompt_template(self) -> str:
        if self.prompt_file.exists():
            with open(self.prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        raise FileNotFoundError(f"找不到重写提示词文件: {self.prompt_file}")
    
    def _build_prompt(self, context: Dict) -> str:
        template = self._load_prompt_template()
        
        review = context.get("review_result", {})
        issues_text = "\n".join([f"- {i.get('item')}: {i.get('reason', '')}" for i in review.get("issues", [])])
        
        prompt = template
        prompt = prompt.replace("{{ARTICLE}}", context["article"])
        prompt = prompt.replace("{{REVIEW_COMMENTS}}", issues_text or "无具体问题")
        
        return prompt
    
    def execute(self, context: Dict) -> Dict:
        logger.info(f"[{self.name}] 根据审核意见重写")
        
        prompt = self._build_prompt(context)
        article = self.client.call(prompt, model="deepseek-chat", max_tokens=6000)
        
        context["article"] = article
        context["word_count"] = len(article.replace(' ', '').replace('\n', ''))
        context["retry_count"] = context.get("retry_count", 0) + 1
        
        logger.info(f"  重写完成，新长度: {context['word_count']} 字")
        logger.info(f"  重试次数: {context['retry_count']}")
        
        return context


# ============ DAG编排器 ============

class CognitionDAG:
    """认知智能体DAG编排器"""
    
    def __init__(self, api_key: str, prompt_dir: str = "."):
        self.client = DeepSeekClient(api_key)
        self.prompt_dir = Path(prompt_dir)
        
        # 初始化7个节点
        self.node_trigger = NodeTrigger()
        self.node_state = NodeStateManager()
        self.node_variable = NodeVariablePool()
        self.node_planner = NodePlanner(self.client, self.prompt_dir / "planner_prompt.txt")
        self.node_writer = NodeWriter(self.client, self.prompt_dir / "writer_prompt.txt")
        self.node_reviewer = NodeReviewer(self.client, self.prompt_dir / "reviewer_prompt.txt")
        self.node_rewriter = NodeRewriter(self.client, self.prompt_dir / "rewriter_prompt.txt")
        
        self.max_retries = 3
    
    def run(self, force_day: Optional[int] = None) -> Dict:
        """执行完整DAG"""
        logger.info("=" * 60)
        logger.info("🚀 认知智能体DAG开始执行")
        logger.info("=" * 60)
        
        # 初始化上下文
        context = {"force_day": force_day, "retry_count": 0}
        
        try:
            # === 阶段1-3: 准备阶段 ===
            context = self.node_trigger.execute(context)
            if not context.get("should_run", True):
                logger.info("⏭️ 跳过本次执行")
                return {"skipped": True}
            
            context = self.node_state.execute(context)
            context = self.node_variable.execute(context)
            
            # === 阶段4: 规划 ===
            context = self.node_planner.execute(context)
            
            # === 阶段5-7: 写作-审核循环 ===
            while True:
                # 写作
                context = self.node_writer.execute(context)
                
                # 审核
                context = self.node_reviewer.execute(context)
                
                review = context.get("review_result", {})
                
                # 检查是否通过
                if review.get("passed"):
                    logger.info("✅ 文章审核通过，准备推送")
                    break
                
                # 检查重试次数
                if context.get("retry_count", 0) >= self.max_retries:
                    logger.warning(f"⚠️ 达到最大重试次数({self.max_retries})，使用当前版本")
                    break
                
                # 重写
                logger.info(f"🔄 审核不通过，开始第{context.get('retry_count', 0)+1}次重写")
                context = self.node_rewriter.execute(context)
            
            # === 保存状态 ===
            self.node_state.finalize(context)
            
            logger.info("=" * 60)
            logger.info("✅ DAG执行完成")
            logger.info("=" * 60)
            
            return {
                "success": True,
                "day": context["day"],
                "stage": context["stage"],
                "variables": context["variables"],
                "writing_plan": context.get("writing_plan"),
                "article": context["article"],
                "word_count": context.get("word_count"),
                "review_result": context.get("review_result"),
                "retry_count": context.get("retry_count", 0)
            }
            
        except Exception as e:
            logger.error(f"❌ DAG执行失败: {e}")
            raise


def main():
    """主入口"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        logger.error("请设置环境变量 DEEPSEEK_API_KEY")
        exit(1)
    
    dag = CognitionDAG(api_key)
    result = dag.run()
    
    if result.get("skipped"):
        return
    
    # 保存文章
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    article_file = output_dir / f"day{result['day']:03d}.md"
    with open(article_file, 'w', encoding='utf-8') as f:
        f.write(result["article"])
    
    logger.info(f"💾 文章已保存: {article_file}")


if __name__ == "__main__":
    main()
