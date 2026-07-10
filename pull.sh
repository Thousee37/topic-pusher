#!/bin/bash
# 在 Mac 唤醒时自动拉取最新选题
# 由 launchd 触发

REPO_DIR="$HOME/topic-pusher"
LOG_FILE="$HOME/Library/Logs/topic-pusher.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# 检查网络
if ! ping -c 1 -t 2 github.com &>/dev/null; then
    log "⏳ 网络未就绪，跳过"
    exit 0
fi

cd "$REPO_DIR" || { log "❌ 找不到仓库目录 $REPO_DIR"; exit 1; }

# 拉取
BEFORE=$(git rev-parse HEAD 2>/dev/null)
git pull --ff-only origin main 2>&1 | tee -a "$LOG_FILE"
AFTER=$(git rev-parse HEAD 2>/dev/null)

if [ "$BEFORE" != "$AFTER" ]; then
    NEW_FILE=$(git diff --name-only "$BEFORE" "$AFTER" -- '*.md' | head -1)
    if [ -n "$NEW_FILE" ]; then
        log "✅ 新选题已拉取: $NEW_FILE"
        # 显示通知
        osascript -e "display notification \"今日选题素材已就绪\" with title \"📰 选题推送\" sound name \"Glass\""
    fi
else
    log "📭 无更新"
fi
