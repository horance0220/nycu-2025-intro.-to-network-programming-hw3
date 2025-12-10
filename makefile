# Game Store System - Makefile
# 快速啟動腳本

.PHONY: all server dev player clean install help

# 預設目標
help:
	@echo "=== Game Store System ==="
	@echo ""
	@echo "Usage:"
	@echo "  make server    - 啟動伺服器"
	@echo "  make dev       - 啟動開發者客戶端"
	@echo "  make player    - 啟動玩家客戶端"
	@echo "  make install   - 安裝依賴"
	@echo "  make clean     - 清理下載的遊戲"
	@echo ""
	@echo "Server default: 127.0.0.1:5000"
	@echo ""
	@echo "Custom server:"
	@echo "  make dev HOST=192.168.1.1 PORT=5000"
	@echo "  make player HOST=192.168.1.1 PORT=5000"

# 變數設定
HOST ?= 127.0.0.1
PORT ?= 5000

# 安裝依賴
install:
	pip install -r requirements.txt

# 啟動伺服器
server:
	cd server && python server_main.py

# 啟動開發者客戶端
dev:
	cd developer_client && python dev_client.py $(HOST) $(PORT)

# 啟動玩家客戶端
player:
	cd player_client && python lobby_client.py $(HOST) $(PORT)

# 啟動玩家客戶端 (player1)
player1:
	cd player_client && python lobby_client.py $(HOST) $(PORT)

# 啟動玩家客戶端 (player2)
player2:
	cd player_client && python lobby_client.py $(HOST) $(PORT)

# 清理
clean:
	@echo "清理下載的遊戲..."
	rm -rf player_client/downloads/*/
	@echo "清理完成"

# 重置資料庫
reset-db:
	@echo "重置資料庫..."
	cp server/database.json server/database.json.backup
	@echo '{"developers":{"dev1":{"password":"dev123","display_name":"Developer One","created_at":"2025-12-10T00:00:00","session_id":null},"dev2":{"password":"dev456","display_name":"Developer Two","created_at":"2025-12-10T00:00:00","session_id":null}},"players":{"player1":{"password":"pass123","display_name":"Player One","created_at":"2025-12-10T00:00:00","session_id":null,"played_games":[]},"player2":{"password":"pass456","display_name":"Player Two","created_at":"2025-12-10T00:00:00","session_id":null,"played_games":[]},"player3":{"password":"pass789","display_name":"Player Three","created_at":"2025-12-10T00:00:00","session_id":null,"played_games":[]}},"games":{},"reviews":{},"rooms":{}}' > server/database.json
	rm -rf server/storage/*
	@echo "重置完成"

# 完整重置 (資料庫 + 下載)
reset-all: reset-db clean
	@echo "完整重置完成"
