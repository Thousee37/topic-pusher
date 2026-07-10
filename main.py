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
# 设置 TEST_MODE=1 时扩大为过去 24 小时，方便测试
TEST_MODE = os.environ.get("TEST_MODE", "")

def get_time_window() -> tuple[datetime, datetime]:
    now = datetime.now(CST)
    if TEST_MODE:
        # 测试模式：过去 24 小时
        return now - timedelta(hours=24), now
    today_8am = now.replace(hour=8, minute=0, second=0, microsecond=0)
    yesterday_630pm = today_8am - timedelta(hours=13, minutes=30)
    return yesterday_630pm, today_8am

# RSS 源
RSS_SOURCES = [
    ("IT之家", "https://www.ithome.com/rss/"),
    ("快科技", "https://rss.mydrivers.com/rss.aspx?Tid=1"),
]

# 输出目录（GitHub Actions 里是当前目录，本地可以改）
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", Path.home() / "Desktop" / "选题"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / f"选题素材_{datetime.now(CST).strftime('%Y%m%d')}.md"

# DeepSeek API
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

# ── 过滤规则 ──────────────────────────────────────────

# 标题命中这些关键词 → 直接丢弃（不进入 DeepSeek 筛选）
SKIP_TITLE_KEYWORDS = [
    # 广告/促销
    "大促", "券后", "限今日", "半价", "包邮", "特价", "清仓",
    "白菜价", "白菜", "手慢无", "漏价", "神价", "狂促",
    # 食品/衣物
    "零食", "鸭脖", "鸡爪", "螺蛳粉", "牛肉干", "坚果",
    "T恤", "POLO", "短袖", "衬衫", "休闲裤", "运动鞋",
    "跑鞋", "板鞋", "双肩包", "洗发水", "牙线", "牙膏",
    "牛奶", "酸奶", "巧克力", "矿泉水", "饮料",
    # 纯产品发布（手机/笔记本）
    "开售", "开卖", "首发", "上架", "预售",
]

# 标题命中这些 → 必须同时命中 FOCUS_KEYWORDS 才保留
REQUIRE_FOCUS_KEYWORDS = [
    "手机", "笔记本", "游戏本", "轻薄本", "电竞本",
    "平板", "手表", "耳机", "路由器",
]

# 一旦命中这些 → 即使被上面规则拦掉，也保留
FOCUS_KEYWORDS = [
    "华为", "小米", "马斯克", "特斯拉", "SpaceX",
    "大模型", "人工智能", "GPT", "ChatGPT", "DeepSeek", "OpenAI",
    "AI模型", "AI行业", "AI应用", "AI智能体", "AI监管",
    "争议", "翻车", "质疑", "吐槽", "维权", "曝光",
    "突破性", "首次", "革命性", "颠覆性",
]

# 纯游戏资讯
SKIP_GAME_KEYWORDS = [
    "Steam", "Epic", "Xbox", "PlayStation", "Switch",
    "游戏本", "电竞", "FPS", "RPG", "3A",
]


def should_skip(title: str) -> bool:
    """判断是否应该跳过这篇文章"""
    t = title.lower()

    # 重点关注关键词 → 绝不跳过
    for kw in FOCUS_KEYWORDS:
        if kw.lower() in t:
            return False

    # 屏蔽词直接跳过
    for kw in SKIP_TITLE_KEYWORDS:
        if kw.lower() in t:
            return True

    # 产品类必须搭配关注词
    has_product_kw = any(kw.lower() in t for kw in REQUIRE_FOCUS_KEYWORDS)
    has_focus_kw = any(kw.lower() in t for kw in FOCUS_KEYWORDS)
    if has_product_kw and not has_focus_kw:
        return True

    return False


# ── RSS 抓取 ──────────────────────────────────────────

def clean_html(raw: str) -> str:
    """去掉 HTML 标签，保留纯文本"""
    return re.sub(r"<[^>]+>", " ", raw).replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"')

def fetch_articles(start: datetime, end: datetime) -> list[dict]:
    """抓取所有 RSS 源，返回时间窗口内的文章列表"""
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

                # 关键词过滤
                title = entry.title.strip()
                if should_skip(title):
                    continue

                # 提取摘要
                summary = ""
                if hasattr(entry, "description"):
                    summary = clean_html(entry.description)[:300]
                elif hasattr(entry, "summary"):
                    summary = clean_html(entry.summary)[:300]

                articles.append({
                    "source": source_name,
                    "title": title,
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

以下类型直接跳过，不要选：
- 单独的手机、笔记本产品发布/开售（除非涉及 华为/小米）
- 宏观政策、政府会议、官方通告
- 促销、食品、衣物等广告软文
- 纯游戏资讯（电竞本评测除外）

以下方向优先选择：
- 华为、小米相关
- 马斯克、特斯拉、SpaceX
- 大模型、AI 行业动态（GPT、DeepSeek、OpenAI 等）
- 有争议性、话题性的事件（翻车、质疑、曝光、维权）
- 重大技术突破（首次、突破性的成果）

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

def generate_markdown(selected: list[dict], time_start: datetime, time_end: datetime) -> str:
    """生成 Markdown 文件内容"""
    now = datetime.now(CST)
    date_str = now.strftime("%Y年%m月%d日")
    time_range = f"{time_start.strftime('%m/%d %H:%M')} — {time_end.strftime('%m/%d %H:%M')}"

    lines = [
        f"# 📰 选题素材 · {date_str}",
        "",
        f"> 生成时间：{now.strftime('%H:%M')} ｜ 来源：IT之家、快科技",
        f"> 时间范围：{time_range}",
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

    # 时间窗口
    time_start, time_end = get_time_window()

    # 1. 抓取
    articles = fetch_articles(time_start, time_end)

    if not articles:
        print("\n😴 该时间窗口内无新文章，跳过生成。")
        return

    # 2. 筛选
    selected = select_articles(articles)

    if not selected:
        print("\n😴 筛选结果为空，跳过生成。")
        return

    # 3. 生成 Markdown
    md_content = generate_markdown(selected, time_start, time_end)
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
