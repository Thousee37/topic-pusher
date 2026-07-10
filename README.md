# 📰 选题推送

每天早上自动推送 10 条选题素材，来源 IT之家 + 快科技，DeepSeek 筛选排序。

## 工作流程

```
GitHub Actions（云端）         你的 Mac（本地）
─────────────────────        ──────────────
每天 8:00 跑脚本             8:15 / 唤醒时
抓 RSS → DeepSeek 筛选       git pull
→ 生成 md → 推送到仓库       → 文件出现在仓库目录
```

## 配置步骤

### 1. 推送到 GitHub

```bash
cd ~/topic-pusher
git init
git add .
git commit -m "init"
git remote add origin git@github.com:你的用户名/topic-pusher.git
git push -u origin main
```

### 2. 设置 GitHub Secret

在仓库 Settings → Secrets and variables → Actions 添加：
- `DEEPSEEK_API_KEY`: 你的 DeepSeek API Key

### 3. 本地克隆 + 配置

```bash
cd ~/topic-pusher
chmod +x setup.sh
./setup.sh
```

## 输出

每天生成 `选题素材_YYYYMMDD.md`，格式：

```
📰 选题素材 · 2026年07月10日

🔥 重点关注
⭐ 1. 某某新闻标题
   来源 | 时间 | 链接
   摘要 | 选题角度

📋 更多选题
1. 另一条新闻
   ...
```

## 手动运行

```bash
# GitHub Actions 手动触发：仓库 → Actions → 每日选题推送 → Run workflow

# 本地测试：
export DEEPSEEK_API_KEY=sk-xxx
python main.py
```
