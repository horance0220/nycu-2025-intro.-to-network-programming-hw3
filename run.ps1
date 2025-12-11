param (
    [string]$Target = "help",
    [string]$HostIP = "140.113.17.11",
    [string]$Port = "16969"
)

# 確保在腳本所在目錄執行
if ($PSScriptRoot) {
    Set-Location $PSScriptRoot
}

function Show-Help {
    Write-Host "=== Game Store System (Windows Launcher) ==="
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  .\run.ps1 server    - 啟動伺服器"
    Write-Host "  .\run.ps1 dev       - 啟動開發者客戶端"
    Write-Host "  .\run.ps1 player    - 啟動玩家客戶端"
    Write-Host "  .\run.ps1 clean     - 清理下載的遊戲"
    Write-Host "  .\run.ps1 reset-db  - 重置資料庫"
    Write-Host ""
    Write-Host "Custom server:"
    Write-Host "  .\run.ps1 dev -HostIP 192.168.1.1 -Port 5000"
}

switch ($Target) {
    "server" {
        Set-Location server
        python server_main.py
    }
    "dev" {
        Set-Location developer_client
        python dev_client.py $HostIP $Port
    }
    "player" {
        Set-Location player_client
        python lobby_client.py $HostIP $Port
    }
    "clean" {
        Write-Host "清理下載的遊戲..."
        Remove-Item -Path "player_client\downloads\*" -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "清理完成"
    }
    "reset-db" {
        Write-Host "重置資料庫..."
        if (Test-Path "server\database.json") {
            Copy-Item "server\database.json" "server\database.json.backup" -Force
        }
        
        # 重置資料庫內容 (保留 Plugin 設定)
        $initialDb = '{"developers":{"dev1":{"password":"dev123","display_name":"Developer One","created_at":"2025-12-10T00:00:00","session_id":null},"dev2":{"password":"dev456","display_name":"Developer Two","created_at":"2025-12-10T00:00:00","session_id":null}},"players":{"player1":{"password":"pass123","display_name":"Player One","created_at":"2025-12-10T00:00:00","session_id":null,"played_games":[]},"player2":{"password":"pass456","display_name":"Player Two","created_at":"2025-12-10T00:00:00","session_id":null,"played_games":[]},"player3":{"password":"pass789","display_name":"Player Three","created_at":"2025-12-10T00:00:00","session_id":null,"played_games":[]}},"games":{},"reviews":{},"rooms":{},"plugins":{"chat_plugin":{"name":"Room Chat Plugin","description":"在遊戲房間中啟用聊天功能","version":"1.0.0","filename":"chat_plugin.json"}}}'
        Set-Content -Path "server\database.json" -Value $initialDb -Encoding UTF8
        
        # 清理 storage 但保留 plugins
        Get-ChildItem -Path "server\storage" -Exclude "plugins" | Remove-Item -Recurse -Force
        
        # 確保 plugin 檔案存在
        if (!(Test-Path "server\storage\plugins")) {
            New-Item -Path "server\storage\plugins" -ItemType Directory -Force | Out-Null
        }
        
        $pluginContent = '{
    "id": "chat_plugin",
    "name": "Room Chat Plugin",
    "version": "1.0.0",
    "features": ["chat"]
}'
        Set-Content -Path "server\storage\plugins\chat_plugin.json" -Value $pluginContent -Encoding UTF8

        Write-Host "重置完成"
    }
    "help" {
        Show-Help
    }
    Default {
        Show-Help
    }
}
