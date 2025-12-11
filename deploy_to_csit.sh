#!/bin/bash
# 部署腳本 - 將專案上傳到 CSIT 工作站
# 使用方式: ./deploy_to_csit.sh [使用者名稱]
# 如果不提供使用者名稱，將使用預設值

# 預設設定
DEFAULT_USER="hslee0220"
HOST="linux1.cs.nycu.edu.tw"
REMOTE_DIR="~/netgame-hw3"

# 取得使用者名稱
if [ -n "$1" ]; then
    CSIT_USER="$1"
else
    CSIT_USER="$DEFAULT_USER"
fi

echo "🚀 準備部署到 $CSIT_USER@$HOST:$REMOTE_DIR"
echo "   (如果這是第一次連線，可能需要輸入密碼)"

# 檢查是否能連線並建立目錄
echo "📁 正在建立遠端目錄結構..."
ssh "${CSIT_USER}@${HOST}" "mkdir -p $REMOTE_DIR"

if [ $? -ne 0 ]; then
    echo "❌ 無法連線到主機，請檢查帳號或網路設定。"
    exit 1
fi

# 使用 rsync 上傳檔案 (推薦)
if command -v rsync >/dev/null 2>&1; then
    echo "🔄 使用 rsync 同步檔案..."
    # --exclude 排除不需要上傳的暫存檔與本地下載檔
    rsync -avz --progress \
        --exclude '.git' \
        --exclude '__pycache__' \
        --exclude '*.pyc' \
        --exclude '.vscode' \
        --exclude 'player_client/downloads/*' \
        ./ "${CSIT_USER}@${HOST}:${REMOTE_DIR}/"
else
    # 如果沒有 rsync，使用 scp (較慢且無法排除檔案)
    echo "⚠️ 未偵測到 rsync，改用 scp (會上傳所有檔案，包含暫存檔)..."
    scp -r . "${CSIT_USER}@${HOST}:${REMOTE_DIR}/"
fi

echo ""
echo "✅ 部署完成！"
echo "📋 接下來的步驟："
echo "1. SSH 連線到工作站:"
echo "   ssh ${CSIT_USER}@${HOST}"
echo ""
echo "2. 進入專案目錄:"
echo "   cd ${REMOTE_DIR}"
echo ""
echo "3. 啟動 Server:"
echo "   make server"
echo ""
echo "💡 提示: 如果遇到權限問題，請執行: chmod +x server/server_main.py"
