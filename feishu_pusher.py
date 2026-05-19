#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书推送模块
支持Webhook机器人和自建应用两种方式
"""

import os
import json
import requests
from typing import Optional, Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class FeishuPusher:
    """飞书消息推送器"""
    
    def __init__(
        self,
        webhook_url: Optional[str] = None,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None
    ):
        """
        初始化推送器
        
        Args:
            webhook_url: 飞书群机器人Webhook地址
            app_id: 飞书自建应用App ID（可选，用于上传文件）
            app_secret: 飞书自建应用App Secret（可选）
        """
        self.webhook_url = webhook_url or os.getenv("FEISHU_WEBHOOK")
        self.app_id = app_id or os.getenv("FEISHU_APP_ID")
        self.app_secret = app_secret or os.getenv("FEISHU_APP_SECRET")
        self._access_token: Optional[str] = None
        
    def _get_tenant_access_token(self) -> str:
        """获取飞书租户访问令牌"""
        if self._access_token:
            return self._access_token
            
        if not self.app_id or not self.app_secret:
            raise ValueError("需要提供 app_id 和 app_secret 才能获取访问令牌")
        
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json"}
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") != 0:
            raise Exception(f"获取访问令牌失败: {data}")
        
        self._access_token = data["tenant_access_token"]
        return self._access_token
    
    def upload_file(self, file_path: str, file_name: Optional[str] = None) -> str:
        """
        上传文件到飞书云文档
        
        Args:
            file_path: 本地文件路径
            file_name: 自定义文件名（可选）
            
        Returns:
            file_token: 文件令牌，用于分享
        """
        token = self._get_tenant_access_token()
        
        if not file_name:
            file_name = Path(file_path).name
        
        url = "https://open.feishu.cn/open-apis/drive/v1/files/upload_all"
        headers = {"Authorization": f"Bearer {token}"}
        
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        files = {
            'file_name': (None, file_name),
            'parent_type': (None, 'explorer'),
            'size': (None, str(len(file_content))),
            'file': (file_name, file_content)
        }
        
        response = requests.post(url, headers=headers, files=files)
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") != 0:
            raise Exception(f"上传文件失败: {data}")
        
        file_token = data["data"]["file_token"]
        logger.info(f"文件上传成功: {file_name}, token: {file_token}")
        return file_token
    
    def send_text(self, content: str) -> Dict[str, Any]:
        """
        发送纯文本消息
        
        Args:
            content: 消息内容
        """
        if not self.webhook_url:
            raise ValueError("需要提供 webhook_url")
        
        payload = {
            "msg_type": "text",
            "content": {
                "text": content
            }
        }
        
        response = requests.post(
            self.webhook_url,
            headers={"Content-Type": "application/json"},
            json=payload
        )
        response.raise_for_status()
        
        result = response.json()
        if result.get("code") != 0 and result.get("StatusCode") != 0:
            logger.error(f"发送消息失败: {result}")
        else:
            logger.info("文本消息发送成功")
        
        return result
    
    def send_rich_text(
        self,
        title: str,
        content: str,
        day: int,
        topic: str,
        file_link: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送富文本卡片消息
        
        Args:
            title: 文章标题
            content: 文章摘要/简介
            day: 第几天
            topic: 主题
            file_link: 文件链接（可选）
        """
        if not self.webhook_url:
            raise ValueError("需要提供 webhook_url")
        
        # 构建卡片内容
        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**📚 第 {day} 天 | {topic}**"
                }
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**{title}**"
                }
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": content[:200] + "..." if len(content) > 200 else content
                }
            }
        ]
        
        # 如果有文件链接，添加按钮
        if file_link:
            elements.append({
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "📖 阅读全文"
                        },
                        "type": "primary",
                        "url": file_link
                    }
                ]
            })
        
        payload = {
            "msg_type": "interactive",
            "card": {
                "config": {
                    "wide_screen_mode": True
                },
                "elements": elements
            }
        }
        
        response = requests.post(
            self.webhook_url,
            headers={"Content-Type": "application/json"},
            json=payload
        )
        response.raise_for_status()
        
        result = response.json()
        if result.get("code") != 0 and result.get("StatusCode") != 0:
            logger.error(f"发送卡片消息失败: {result}")
        else:
            logger.info("卡片消息发送成功")
        
        return result
    
    def push_article(
        self,
        article_path: str,
        day: int,
        topic: str,
        send_full_content: bool = False
    ) -> Dict[str, Any]:
        """
        推送文章到飞书
        
        Args:
            article_path: 文章文件路径
            day: 第几天
            topic: 主题
            send_full_content: 是否发送完整内容（默认只发摘要）
        """
        # 读取文章内容
        with open(article_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取标题
        title_match = content.split('\n')[0] if content.startswith('#') else "认知提升"
        title = title_match.replace('# ', '').replace('🧠 ', '')
        
        # 提取摘要（第一段）
        lines = content.split('\n')
        summary = ""
        for line in lines[1:]:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('>'):
                summary = line
                break
        
        if send_full_content:
            # 发送完整内容
            message = f"【认知】📚 Day {day}\n\n{content[:3000]}"  # 限制长度
            return self.send_text(message)
        else:
            # 上传文件并发送卡片
            try:
                file_token = self.upload_file(article_path)
                file_link = f"https://www.feishu.cn/file/{file_token}"
                return self.send_rich_text(title, summary, day, topic, file_link)
            except Exception as e:
                logger.error(f"上传文件失败，降级为发送文本: {e}")
                # 降级方案：发送文本
                message = f"【认知】📚 Day {day} | {topic}\n\n{title}\n\n{summary}"
                return self.send_text(message)


def main():
    """测试推送功能"""
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python feishu_pusher.py <文章路径> [天数] [主题]")
        sys.exit(1)
    
    article_path = sys.argv[1]
    day = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    topic = sys.argv[3] if len(sys.argv) > 3 else "认知提升"
    
    pusher = FeishuPusher()
    result = pusher.push_article(article_path, day, topic)
    print(f"推送结果: {result}")


if __name__ == "__main__":
    main()
