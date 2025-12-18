# Game Store System - 遊戲商城系統

## 📁 專案結構

```
netgame-hw3/
├── server/                    # 伺服器端
│   ├── server_main.py        # 主程式
│   ├── utils.py              # 通訊協定工具
│   ├── database.json         # 資料庫
│   └── storage/              # 上架遊戲存放區
├── developer_client/          # 開發者客戶端
│   ├── dev_client.py         # 主程式
│   ├── games/                # 本地遊戲開發區
│   │   ├── guess_number/    # 猜數字遊戲
│   │   └── rps_battle/      # 剪刀石頭布對戰 (New!)
│   └── template/             # 遊戲範本
├── player_client/             # 玩家客戶端
│   ├── lobby_client.py       # 主程式
│   └── downloads/            # 下載的遊戲
│       ├── player1/
│       ├── player2/
│       └── ...
├── makefile                   # 快速啟動腳本 (Linux/Mac)
├── run.ps1                    # 快速啟動腳本 (Windows)
├── requirements.txt           # Python 依賴
└── readme.md                  # 本檔案
```

## 快速開始 (Quick Start)

### 1. 環境準備

確保已安裝 Python 3.8+。

### 2. 啟動客戶端 (Windows)

**啟動開發者客戶端 (Developer Client):**
```powershell
.\run.ps1 dev
```

**啟動玩家客戶端 (Lobby Client):**
```powershell
.\run.ps1 player
```

*(註：請開啟多個 PowerShell 視窗分別執行上述指令)*

### 3. 啟動客戶端 (Linux/Mac)

**啟動開發者客戶端 (Developer Client):**
```bash
make dev
```

**啟動玩家客戶端 (Lobby Client):**
```bash
make player
```

## 3. 測試帳號

### 開發者帳號
| 帳號 | 密碼 |
|------|------|
| dev1 | dev123 |
| dev2 | dev456 |

### 玩家帳號
| 帳號 | 密碼 |
|------|------|
| player1 | pass123 |
| player2 | pass456 |
| player3 | pass789 |

也可以自行註冊新帳號。

## 使用流程

### 開發者流程

1. 啟動 Developer Client
2. 登入開發者帳號
3. 選擇「上架新遊戲」
4. 選擇本地遊戲目錄
5. 確認上架資訊後上傳

### 玩家流程

1. 啟動 Lobby Client
2. 登入玩家帳號
3. 進入「遊戲商城」瀏覽遊戲
4. 選擇遊戲並下載
5. 進入「遊戲房間」建立或加入房間
6. 人數足夠後由房主開始遊戲
7. 遊戲結束後可撰寫評論

## 內建示範遊戲

### 猜拳（rps_battle）
- 類型：雙人 CLI 遊戲
- 人數：2 人
- 說明：搶三分制，先贏三把獲勝

### 猜數字大戰（guess_number）
- 類型：多人 GUI 遊戲  
- 人數：2-6 人
- 說明：回合制輪流猜 1-100 的隱藏數字，猜中者獲勝(內建聊天系統)

##  遊戲開發指南

### 遊戲規格

每個遊戲目錄需包含 `config.json`：

```json
{
    "name": "遊戲名稱",
    "description": "遊戲簡介",
    "version": "1.0.0",
    "game_type": "GUI",
    "min_players": 2,
    "max_players": 2,
    "server_command": ["python", "server.py"],
    "client_command": ["python", "client.py"]
}
```

### 如何開發新遊戲

本系統提供了一個標準化的遊戲開發框架，您可以依照以下步驟開發自己的多人連線遊戲：

1. **建立專案目錄**
   - 在 `\developer_client`資料夾下執行
   ```powershell
      #Windows
      python create_game_template.py
   ```

   ```bash
      #Mac/Linux
      python3 create_game_template.py
   ```

2. **設定 Config**
   - 編輯 `config.json`，設定遊戲名稱、描述、人數限制等。
   - `server_command` 與 `client_command` 指定了啟動遊戲的指令，通常不需要修改。

3. **實作 Server 端 (`server.py`)**
   - 系統會自動啟動 Server 並傳入 Port 參數。
   - 需實作 Socket 監聽與多執行緒處理。
   - 核心邏輯：接收玩家動作 -> 更新遊戲狀態 -> 廣播給所有玩家。
   - 建議使用 JSON 格式進行通訊。

4. **實作 Client 端 (`client.py`)**
   - 系統會自動啟動 Client 並傳入 Server IP 與 Port。
   - 需實作連線與介面顯示 (CLI 或 GUI)。
   - 核心邏輯：監聽使用者輸入 -> 發送動作給 Server -> 接收 Server 廣播 -> 更新畫面。

5. **測試與上架**
   - 使用 Developer Client 登入。
   - 選擇「上架新遊戲」並選擇您的遊戲目錄。
   - 上架成功後，即可切換到 Lobby Client 進行下載與遊玩。

## 故障排除

### 連線失敗
1. 確認伺服器已啟動
2. 確認 IP 和 Port 正確
3. 檢查防火牆設定

### 遊戲無法啟動
1. 確認已下載遊戲
2. 確認遊戲版本與伺服器一致
3. 檢查 `config.json` 格式

### GUI 遊戲問題
1. 確認已安裝 tkinter
2. Windows: 通常已內建
3. Linux: `sudo apt install python3-tk`

## 📄 License

MIT License
