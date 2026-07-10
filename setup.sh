#!/bin/bash
# 一键配置本地自动拉取
set -e

echo "📰 选题推送 - 本地配置"
echo "========================"

# 1. 赋予 pull.sh 执行权限
chmod +x "$HOME/topic-pusher/pull.sh"
echo "✅ pull.sh 已设为可执行"

# 2. 创建日志目录
mkdir -p "$HOME/Library/Logs"
echo "✅ 日志目录已就绪"

# 3. 安装 LaunchAgent
PLIST_SRC="$HOME/topic-pusher/com.topic-pusher.pull.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.topic-pusher.pull.plist"

cp "$PLIST_SRC" "$PLIST_DST"
echo "✅ LaunchAgent 已安装到 $PLIST_DST"

# 4. 加载（如果已加载则先卸载再加载）
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"
echo "✅ LaunchAgent 已加载"

echo ""
echo "🎉 配置完成！"
echo "   - Mac 唤醒时自动拉取最新选题"
echo "   - 每天早上 8:15 自动拉取"
echo "   - 日志: ~/Library/Logs/topic-pusher.log"
echo ""
echo "验证: launchctl list | grep topic-pusher"
