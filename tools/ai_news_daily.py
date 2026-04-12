from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime
import feedparser
import httpx
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from llm.helpers import get_llm_model


RSS_SOURCES = {
    "TechCrunch": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "The Verge": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "Hacker News": "https://news.ycombinator.com/rss"
}


@dataclass
class NewsArticle:
    title: str
    url: str
    published_at: str
    source: str
    points: Optional[int] = None
    summary: str = ""


class AiNewsDailyTool:
    def fetch_rss(self, source: str, limit: int = 10) -> List[NewsArticle]:
        url = RSS_SOURCES.get(source)
        if not url:
            return []

        articles = []
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url)
                response.raise_for_status()
                feed = feedparser.parse(response.text)

                for entry in feed.entries[:limit]:
                    article = NewsArticle(
                        title=entry.get("title", "无标题"),
                        url=entry.get("link", ""),
                        published_at=entry.get("published", ""),
                        source=source
                    )

                    if source == "Hacker News" and hasattr(entry, 'score'):
                        article.points = entry.score

                    articles.append(article)
        except Exception as e:
            print(f"获取 {source} RSS 失败: {str(e)}")

        return articles

    def fetch_all(self) -> List[NewsArticle]:
        all_articles = []
        for source in RSS_SOURCES.keys():
            articles = self.fetch_rss(source, 10)
            all_articles.extend(articles)
        return all_articles

    def dedupe(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        seen_urls = set()
        unique_articles = []
        for article in articles:
            if article.url not in seen_urls:
                seen_urls.add(article.url)
                unique_articles.append(article)
        return unique_articles

    def format_time_ago(self, published_at: str) -> str:
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(published_at)
            now = datetime.now(dt.tzinfo)
            diff = now - dt

            if diff.days > 0:
                return f"{diff.days}天前"
            elif diff.seconds >= 3600:
                return f"{diff.seconds // 3600}小时前"
            elif diff.seconds >= 60:
                return f"{diff.seconds // 60}分钟前"
            else:
                return "刚刚"
        except:
            return published_at

    def generate_summary(self, article: NewsArticle) -> str:
        prompt = f"""请为以下新闻生成一段简洁的中文摘要（50-100字）：

标题：{article.title}
来源：{article.source}
链接：{article.url}

要求：
- 一段话概括核心内容
- 用中文
- 不要复述标题"""

        try:
            llm = get_llm_model(temperature=0.3)
            response = llm.invoke([
                SystemMessage(content="你是一个新闻摘要助手。"),
                HumanMessage(content=prompt)
            ])

            content = response.content
            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get('type') == 'text':
                        text_parts.append(part.get('text', ''))
                    elif isinstance(part, str):
                        text_parts.append(part)
                content = ''.join(text_parts)

            return content.strip() if content else "摘要生成失败"
        except Exception as e:
            print(f"生成摘要失败: {str(e)}")
            return "摘要生成失败"

    def generate_summaries(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        for article in articles:
            article.summary = self.generate_summary(article)
        return articles

    def format_report(self, articles: List[NewsArticle]) -> str:
        if not articles:
            return "未获取到任何新闻"

        today = datetime.now().strftime("%Y-%m-%d")
        lines = [
            f"📰 AI 新闻日报 | {today}",
            "═" * 60,
            ""
        ]

        for i, article in enumerate(articles, 1):
            time_str = self.format_time_ago(article.published_at)
            points_str = f" | {article.points} points" if article.points else ""

            lines.append(f"{i}. {article.title}")
            lines.append(f"   {article.url}")
            lines.append(f"   ⏰ {time_str}{points_str} | 来源: {article.source}")

            if article.summary:
                lines.append(f"   📝 {article.summary}")
            else:
                lines.append(f"   📝 摘要生成中...")

            lines.append("")

        lines.append(f"（共{len(articles)}条）")

        return "\n".join(lines)


ai_news_tool = AiNewsDailyTool()


@tool
def get_ai_news_daily() -> str:
    """获取 AI 新闻日报

    抓取 TechCrunch AI、The Verge AI、Hacker News 三个 RSS 源，
    每个源抓取 10 条新闻，使用 LLM 生成中文摘要，返回格式化的新闻日报。
    """
    try:
        articles = ai_news_tool.fetch_all()

        if not articles:
            return "获取新闻失败，请稍后重试"

        articles = ai_news_tool.dedupe(articles)

        articles = ai_news_tool.generate_summaries(articles)

        report = ai_news_tool.format_report(articles)

        return report
    except Exception as e:
        return f"获取 AI 新闻日报失败: {str(e)}"
