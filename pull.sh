#!/bin/bash
# 在 Mac 唤醒时自动拉取最新选题
# 由 launchd 触发

REPO_DIR="$HOME/topic-pusher"
DESKTOP_DIR="$HOME/Desktop/选题"
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
    # 复制新生成的 md 文件到桌面/选题/
    mkdir -p "$DESKTOP_DIR"
    for f in $(git diff --name-only "$BEFORE" "$AFTER" -- '*.md'); do
        cp "$REPO_DIR/$f" "$DESKTOP_DIR/"
        log "✅ 新选题已复制: $f → 桌面/选题/"
    done
    osascript -e "display notification \"今日选题素材已就绪\" with title \"📰 选题推送\" sound name \"Glass\""
else
    log "📭 无更新"
fi
