"""
每天早上推送选题素材
- 抓取 IT之家、快科技 RSS
- DeepSeek 筛选 10 条最佳选题，标记前 3
- 生成 Markdown 文件
"""

import os
import re
import sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import feedparser
from openai import OpenAI


# ── 配置 ──────────────────────────────────────────────
# 北京时间
CST = timezone(timedelta(hours=8))

# 时间窗口：前一天 18:30 到今天 8:00
def get_time_window() -> tuple[datetime, datetime]:
    now = datetime.now(CST)
    today_8am = now.replace(hour=8, minute=0, second=0, microsecond=0)
    yesterday_630pm = today_8am - timedelta(hours=13, minutes=30)
    return yesterday_630pm, today_8am

# RSS 源
RSS_SOURCES = [
    ("IT之家", "https://www.ithome.com/rss/"),
    ("快科技", "https://rss.mydrivers.com/rss.aspx?Tid=1"),
]

# 输出目录（GitHub Actions 里是当前目录，本地可以改）
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", Path.home() / "Desktop"))
OUTPUT_FILE = OUTPUT_DIR / f"选题素材_{datetime.now(CST).strftime('%Y%m%d')}.md"

# DeepSeek API
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

# ── RSS 抓取 ──────────────────────────────────────────

def clean_html(raw: str) -> str:
    """去掉 HTML 标签，保留纯文本"""
    return re.sub(r"<[^>]+>", " ", raw).replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"')

def fetch_articles() -> list[dict]:
    """抓取所有 RSS 源，返回时间窗口内的文章列表"""
    start, end = get_time_window()
    print(f"⏰ 时间窗口: {start.strftime('%m-%d %H:%M')} → {end.strftime('%m-%d %H:%M')}")

    articles = []
    for source_name, url in RSS_SOURCES:
        print(f"📡 抓取 {source_name}: {url}")
        try:
            feed = feedparser.parse(url)
            print(f"   共 {len(feed.entries)} 篇")
            for entry in feed.entries:
                # 解析发布时间
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub_time = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).astimezone(CST)
                elif hasattr(entry, "published"):
                    pub_time = parsedate_to_datetime(entry.published).astimezone(CST)
                else:
                    continue

                # 时间过滤
                if not (start <= pub_time <= end):
                    continue

                # 提取摘要
                summary = ""
                if hasattr(entry, "description"):
                    summary = clean_html(entry.description)[:300]
                elif hasattr(entry, "summary"):
                    summary = clean_html(entry.summary)[:300]

                articles.append({
                    "source": source_name,
                    "title": entry.title.strip(),
                    "link": entry.link,
                    "summary": summary.strip(),
                    "time": pub_time.strftime("%H:%M"),
                })
        except Exception as e:
            print(f"   ❌ 抓取失败: {e}")

    # 按时间排序
    articles.sort(key=lambda a: a["time"])
    print(f"\n📄 过滤后共 {len(articles)} 篇")
    return articles


# ── DeepSeek 筛选 ─────────────────────────────────────

SELECTION_PROMPT = """你是一个资深内容主编，擅长从科技资讯中挖掘有深度的选题。

你的判断标准：
1. 有话题性——读者愿意点开看，愿意转发讨论
2. 有深度空间——不是纯消息，能展开写成 2000 字的稿子
3. 适合中文互联网阅读——跟国内读者有关联，或者对国内读者有启发
4. 时效性——今天不看就错过的那种

请从以下文章列表中选出 10 条最佳选题，并选出最重要的 3 条（标记为 top3）。

返回 JSON 数组，格式严格如下：
```json
[
  {
    "title": "文章标题",
    "link": "原文链接",
    "source": "来源",
    "time": "发布时间",
    "summary": "一句话摘要（你自己的话，不要复制原文）",
    "angle": "选题角度建议（一两句话，为什么要写这篇、从哪个角度切入有意思）",
    "top3": true
  }
]
```

注意：
- 必须恰好返回 10 条
- top3 必须恰好 3 条
- 按选题优先级从高到低排序
- 只返回 JSON，不要任何其他文字"""


def select_articles(articles: list[dict]) -> list[dict]:
    """用 DeepSeek 筛选并排序文章"""
    if not articles:
        print("⚠️  没有文章可筛选")
        return []

    if not DEEPSEEK_KEY:
        print("⚠️  未设置 DEEPSEEK_API_KEY，返回原始列表前 10 条")
        return [{**a, "angle": "", "top3": False} for a in articles[:10]]

    client = OpenAI(api_key=DEEPSEEK_KEY, base_url=DEEPSEEK_BASE)

    # 构建文章列表文本
    article_list = "\n\n".join([
        f"[{i+1}] {a['source']} | {a['time']}\n标题：{a['title']}\n摘要：{a['summary'][:200]}\n链接：{a['link']}"
        for i, a in enumerate(articles)
    ])

    print(f"\n🤖 发送 {len(articles)} 篇给 DeepSeek 筛选...")
    print(f"   文字量约 {len(article_list)} 字符")

    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SELECTION_PROMPT},
                {"role": "user", "content": f"今天的文章列表：\n\n{article_list}"},
            ],
            temperature=0.6,
            max_tokens=4096,
        )
        content = resp.choices[0].message.content
        print(f"   DeepSeek 返回 {len(content)} 字符")

        # 提取 JSON
        import json
        # 尝试匹配 ```json ... ``` 或直接解析
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        if match:
            json_str = match.group(1)
        else:
            json_str = content.strip()

        result = json.loads(json_str)
        print(f"   ✅ 获取到 {len(result)} 条选题")
        return result

    except Exception as e:
        print(f"   ❌ DeepSeek 调用失败: {e}")
        print("   降级：返回原始列表前 10 条")
        return [{**a, "angle": "", "top3": False} for a in articles[:10]]


# ── Markdown 生成 ─────────────────────────────────────

def generate_markdown(selected: list[dict]) -> str:
    """生成 Markdown 文件内容"""
    now = datetime.now(CST)
    date_str = now.strftime("%Y年%m月%d日")

    lines = [
        f"# 📰 选题素材 · {date_str}",
        "",
        f"> 生成时间：{now.strftime('%H:%M')} ｜ 来源：IT之家、快科技",
        f"> 时间范围：前一天 18:30 — 今日 08:00",
        "",
        "---",
        "",
        "## 🔥 重点关注",
        "",
    ]

    # Top 3
    top3 = [a for a in selected if a.get("top3")]
    for i, item in enumerate(top3, 1):
        source = item.get("source", "")
        time = item.get("time", "")
        title = item.get("title", "无标题")
        link = item.get("link", "#")
        summary = item.get("summary", "")
        angle = item.get("angle", "")

        lines.extend([
            f"### ⭐ {i}. {title}",
            "",
            f"**来源** {source} ｜ **时间** {time} ｜ [原文链接]({link})",
            "",
            f"**摘要** {summary}",
            "",
            f"**💡 选题角度** {angle}",
            "",
            "---",
            "",
        ])

    # 其余 7 条
    rest = [a for a in selected if not a.get("top3")]
    lines.append("## 📋 更多选题")
    lines.append("")

    for i, item in enumerate(rest, 1):
        source = item.get("source", "")
        time = item.get("time", "")
        title = item.get("title", "无标题")
        link = item.get("link", "#")
        summary = item.get("summary", "")
        angle = item.get("angle", "")

        lines.extend([
            f"### {i}. {title}",
            "",
            f"**来源** {source} ｜ **时间** {time} ｜ [原文链接]({link})",
            "",
            f"**摘要** {summary}",
            "",
            f"**💡 选题角度** {angle}",
            "",
            "---",
            "",
        ])

    lines.extend([
        "",
        "> 🎯 选题标准：话题性 · 深度空间 · 读者关联 · 时效性",
        "> 🤖 由 DeepSeek 筛选排序",
    ])

    return "\n".join(lines)


# ── 主函数 ────────────────────────────────────────────

def main():
    print("=" * 50)
    print("📰 选题素材推送")
    print("=" * 50)

    # 1. 抓取
    articles = fetch_articles()

    if not articles:
        print("\n😴 该时间窗口内无新文章，跳过生成。")
        return

    # 2. 筛选
    selected = select_articles(articles)

    if not selected:
        print("\n😴 筛选结果为空，跳过生成。")
        return

    # 3. 生成 Markdown
    md_content = generate_markdown(selected)
    OUTPUT_FILE.write_text(md_content, encoding="utf-8")
    print(f"\n✅ 已生成: {OUTPUT_FILE}")
    print(f"   共 {len(selected)} 条选题，其中 {sum(1 for a in selected if a.get('top3'))} 条重点")

    # 预览
    print("\n📋 预览:")
    for i, item in enumerate(selected, 1):
        star = "⭐" if item.get("top3") else "  "
        print(f"   {star} {i}. [{item.get('source','')}] {item.get('title','')[:50]}...")


if __name__ == "__main__":
    main()
