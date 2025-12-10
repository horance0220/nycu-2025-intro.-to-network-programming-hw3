#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Game Store System - Developer Client
開發者用來上架、更新、下架遊戲的客戶端
"""

import socket
import sys
import os
import json
import zipfile
import tempfile
import shutil

# 將專案根目錄加入路徑以使用 server.utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from server.utils import send_json, recv_json, send_file

# ========================= 配置 =========================
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 5000
GAMES_DIR = os.path.join(os.path.dirname(__file__), 'games')

# ========================= 全域變數 =========================
sock = None
session_id = None
username = None

# ========================= 工具函式 =========================

def clear_screen():
    """清除螢幕"""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header(title):
    """印出標題"""
    print("\n" + "=" * 50)
    print(f"  {title}")
    print("=" * 50)

def print_menu(options):
    """印出選單"""
    print()
    for i, option in enumerate(options, 1):
        print(f"  {i}. {option}")
    print()

def get_choice(prompt, max_choice):
    """取得使用者選擇"""
    while True:
        try:
            choice = input(prompt).strip()
            if choice.lower() == 'q':
                return 'q'
            num = int(choice)
            if 1 <= num <= max_choice:
                return num
            print(f"  ❌ 請輸入 1-{max_choice} 的數字")
        except ValueError:
            print("  ❌ 請輸入有效的數字")

def send_request(action, data=None):
    """發送請求到 Server"""
    global sock
    
    request = {
        "action": action,
        "client_type": "developer"
    }
    
    if session_id:
        request["session_id"] = session_id
    
    if data:
        request.update(data)
    
    if not send_json(sock, request):
        print("  ❌ 發送請求失敗")
        return None
    
    response = recv_json(sock)
    return response

# ========================= 連線管理 =========================

def connect_to_server():
    """連線到 Server"""
    global sock
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((SERVER_HOST, SERVER_PORT))
        return True
    except Exception as e:
        print(f"  ❌ 連線失敗: {e}")
        return False

def disconnect():
    """斷開連線"""
    global sock
    if sock:
        sock.close()
        sock = None

# ========================= 帳號功能 =========================

def login_menu():
    """登入/註冊選單"""
    global session_id, username
    
    while True:
        clear_screen()
        print_header("開發者平台 - 歡迎")
        print_menu(["登入", "註冊新帳號", "離開"])
        
        choice = get_choice("請選擇 (1-3): ", 3)
        
        if choice == 'q' or choice == 3:
            return False
        
        if choice == 1:
            # 登入
            print_header("登入")
            user = input("  帳號: ").strip()
            passwd = input("  密碼: ").strip()
            
            response = send_request("LOGIN", {
                "username": user,
                "password": passwd
            })
            
            if response and response.get("success"):
                session_id = response["data"]["session_id"]
                username = response["data"]["username"]
                print(f"\n  ✅ 登入成功！歡迎 {response['data']['display_name']}")
                input("  按 Enter 繼續...")
                return True
            else:
                print(f"\n  ❌ {response.get('message', '登入失敗')}")
                input("  按 Enter 繼續...")
        
        elif choice == 2:
            # 註冊
            print_header("註冊新帳號")
            user = input("  帳號 (至少3字元): ").strip()
            passwd = input("  密碼 (至少4字元): ").strip()
            display = input("  顯示名稱 (可選): ").strip() or user
            
            response = send_request("REGISTER", {
                "username": user,
                "password": passwd,
                "display_name": display
            })
            
            if response and response.get("success"):
                print(f"\n  ✅ 註冊成功！請重新登入")
            else:
                print(f"\n  ❌ {response.get('message', '註冊失敗')}")
            input("  按 Enter 繼續...")
    
    return False

# ========================= 遊戲管理功能 =========================

def list_local_games():
    """列出本地遊戲"""
    if not os.path.exists(GAMES_DIR):
        os.makedirs(GAMES_DIR)
        return []
    
    games = []
    for item in os.listdir(GAMES_DIR):
        item_path = os.path.join(GAMES_DIR, item)
        if os.path.isdir(item_path):
            config_path = os.path.join(item_path, 'config.json')
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    games.append({
                        "folder": item,
                        "path": item_path,
                        "config": config
                    })
                except:
                    games.append({
                        "folder": item,
                        "path": item_path,
                        "config": None
                    })
            else:
                games.append({
                    "folder": item,
                    "path": item_path,
                    "config": None
                })
    
    return games

def upload_game():
    """上架新遊戲"""
    print_header("上架新遊戲")
    
    # 列出本地遊戲
    local_games = list_local_games()
    
    if not local_games:
        print("  ⚠️ 本地沒有遊戲可以上架")
        print(f"  請將遊戲放到 {GAMES_DIR} 資料夾")
        input("  按 Enter 返回...")
        return
    
    print("\n  本地遊戲列表:")
    print("-" * 50)
    for i, game in enumerate(local_games, 1):
        config = game.get("config")
        if config:
            print(f"  {i}. {config.get('name', game['folder'])} (v{config.get('version', '?')})")
            print(f"     類型: {config.get('game_type', 'CLI')} | 人數: {config.get('min_players', 2)}-{config.get('max_players', 2)}")
        else:
            print(f"  {i}. {game['folder']} (無設定檔)")
    print("-" * 50)
    print(f"  {len(local_games) + 1}. 返回")
    
    choice = get_choice("\n  請選擇要上架的遊戲: ", len(local_games) + 1)
    
    if choice == 'q' or choice == len(local_games) + 1:
        return
    
    selected_game = local_games[choice - 1]
    game_path = selected_game["path"]
    config = selected_game.get("config")
    
    # 檢查設定檔
    if not config:
        print("\n  ⚠️ 此遊戲沒有 config.json 設定檔")
        print("  請先建立設定檔或使用模板建立遊戲")
        
        create_config = input("  是否要現在建立設定檔? (y/n): ").strip().lower()
        if create_config == 'y':
            config = create_config_interactive(game_path)
            if not config:
                return
        else:
            return
    
    # 顯示遊戲資訊確認
    print_header("確認上架資訊")
    print(f"  遊戲名稱: {config.get('name', '未命名')}")
    print(f"  版本: {config.get('version', '1.0.0')}")
    print(f"  類型: {config.get('game_type', 'CLI')}")
    print(f"  人數: {config.get('min_players', 2)}-{config.get('max_players', 2)} 人")
    print(f"  簡介: {config.get('description', '無')[:50]}...")
    
    confirm = input("\n  確認上架? (y/n): ").strip().lower()
    if confirm != 'y':
        print("  已取消")
        return
    
    # 打包遊戲
    print("\n  ⏳ 正在打包遊戲...")
    
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, f"{config.get('name', 'game')}.zip")
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(game_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, game_path)
                    zipf.write(file_path, arcname)
        
        # 發送上架請求
        print("  ⏳ 正在上傳...")
        
        response = send_request("UPLOAD_GAME", {
            "game_info": {
                "name": config.get("name", "未命名遊戲"),
                "description": config.get("description", "尚未提供簡介"),
                "version": config.get("version", "1.0.0"),
                "game_type": config.get("game_type", "CLI"),
                "max_players": config.get("max_players", 2),
                "min_players": config.get("min_players", 2)
            }
        })
        
        if response and response.get("success"):
            # 傳送檔案
            success, msg = send_file(sock, zip_path)
            
            if success:
                # 等待最終確認
                final_response = recv_json(sock)
                if final_response and final_response.get("success"):
                    print(f"\n  ✅ 遊戲上架成功！")
                    print(f"  遊戲 ID: {final_response['data']['game_id']}")
                else:
                    print(f"\n  ❌ {final_response.get('message', '上架失敗')}")
            else:
                print(f"\n  ❌ 檔案上傳失敗: {msg}")
        else:
            print(f"\n  ❌ {response.get('message', '上架失敗')}")
    
    except Exception as e:
        print(f"\n  ❌ 上架過程發生錯誤: {e}")
    
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    input("  按 Enter 返回...")

def create_config_interactive(game_path):
    """互動式建立設定檔"""
    print("\n  --- 建立遊戲設定檔 ---")
    
    name = input("  遊戲名稱: ").strip()
    if not name:
        print("  ❌ 名稱不可為空")
        return None
    
    description = input("  遊戲簡介: ").strip() or "尚未提供簡介"
    version = input("  版本 (預設 1.0.0): ").strip() or "1.0.0"
    
    print("\n  遊戲類型:")
    print("  1. CLI (命令列)")
    print("  2. GUI (圖形介面)")
    type_choice = get_choice("  請選擇: ", 2)
    game_type = "CLI" if type_choice == 1 else "GUI"
    
    min_players = input("  最少人數 (預設 2): ").strip()
    min_players = int(min_players) if min_players.isdigit() else 2
    
    max_players = input("  最多人數 (預設 2): ").strip()
    max_players = int(max_players) if max_players.isdigit() else 2
    
    # 找出主程式
    py_files = [f for f in os.listdir(game_path) if f.endswith('.py')]
    if py_files:
        print(f"\n  找到的 Python 檔案: {', '.join(py_files)}")
    
    server_main = input("  伺服器端主程式 (例如 server.py，無則留空): ").strip()
    client_main = input("  客戶端主程式 (例如 client.py): ").strip()
    
    config = {
        "name": name,
        "description": description,
        "version": version,
        "game_type": game_type,
        "min_players": min_players,
        "max_players": max_players,
        "server_command": ["python", server_main] if server_main else None,
        "client_command": ["python", client_main] if client_main else ["python", "game.py"]
    }
    
    # 儲存設定檔
    config_path = os.path.join(game_path, "config.json")
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    
    print(f"\n  ✅ 設定檔已建立: {config_path}")
    return config

def list_my_games():
    """列出我的遊戲"""
    print_header("我的遊戲")
    
    response = send_request("LIST_MY_GAMES")
    
    if not response or not response.get("success"):
        print(f"  ❌ {response.get('message', '查詢失敗')}")
        input("  按 Enter 返回...")
        return
    
    games = response["data"]["games"]
    
    if not games:
        print("  ⚠️ 您尚未上架任何遊戲")
        input("  按 Enter 返回...")
        return
    
    print("\n  已上架遊戲:")
    print("-" * 60)
    for i, game in enumerate(games, 1):
        status_icon = "✅" if game["status"] == "active" else "⛔"
        print(f"  {i}. {status_icon} {game['name']} (v{game['version']})")
        print(f"     狀態: {game['status']} | 下載數: {game['download_count']}")
        print(f"     ID: {game['game_id']}")
        print()
    print("-" * 60)
    
    input("  按 Enter 返回...")

def update_game():
    """更新遊戲版本"""
    print_header("更新遊戲版本")
    
    # 先取得我的遊戲列表
    response = send_request("LIST_MY_GAMES")
    
    if not response or not response.get("success"):
        print(f"  ❌ {response.get('message', '查詢失敗')}")
        input("  按 Enter 返回...")
        return
    
    games = [g for g in response["data"]["games"] if g["status"] == "active"]
    
    if not games:
        print("  ⚠️ 沒有可更新的遊戲")
        input("  按 Enter 返回...")
        return
    
    print("\n  可更新的遊戲:")
    print("-" * 50)
    for i, game in enumerate(games, 1):
        print(f"  {i}. {game['name']} (目前版本: v{game['version']})")
    print("-" * 50)
    print(f"  {len(games) + 1}. 返回")
    
    choice = get_choice("\n  請選擇要更新的遊戲: ", len(games) + 1)
    
    if choice == 'q' or choice == len(games) + 1:
        return
    
    selected_game = games[choice - 1]
    
    # 選擇本地遊戲來源
    local_games = list_local_games()
    
    if not local_games:
        print("  ⚠️ 本地沒有遊戲檔案")
        input("  按 Enter 返回...")
        return
    
    print("\n  本地遊戲列表 (作為更新來源):")
    print("-" * 50)
    for i, game in enumerate(local_games, 1):
        config = game.get("config")
        if config:
            print(f"  {i}. {config.get('name', game['folder'])} (v{config.get('version', '?')})")
        else:
            print(f"  {i}. {game['folder']}")
    print("-" * 50)
    
    local_choice = get_choice("\n  請選擇更新來源: ", len(local_games))
    
    if local_choice == 'q':
        return
    
    selected_local = local_games[local_choice - 1]
    game_path = selected_local["path"]
    
    new_version = input(f"\n  新版本號 (目前: {selected_game['version']}): ").strip()
    if not new_version:
        print("  ❌ 請輸入新版本號")
        return
    
    update_notes = input("  更新說明 (可選): ").strip()
    
    # 打包並上傳
    print("\n  ⏳ 正在打包遊戲...")
    
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "update.zip")
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(game_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, game_path)
                    zipf.write(file_path, arcname)
        
        print("  ⏳ 正在上傳更新...")
        
        response = send_request("UPDATE_GAME", {
            "game_id": selected_game["game_id"],
            "version": new_version,
            "update_notes": update_notes
        })
        
        if response and response.get("success"):
            success, msg = send_file(sock, zip_path)
            
            if success:
                final_response = recv_json(sock)
                if final_response and final_response.get("success"):
                    print(f"\n  ✅ 遊戲更新成功！")
                else:
                    print(f"\n  ❌ {final_response.get('message', '更新失敗')}")
            else:
                print(f"\n  ❌ 檔案上傳失敗: {msg}")
        else:
            print(f"\n  ❌ {response.get('message', '更新失敗')}")
    
    except Exception as e:
        print(f"\n  ❌ 更新過程發生錯誤: {e}")
    
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    input("  按 Enter 返回...")

def unpublish_game():
    """下架遊戲"""
    print_header("下架遊戲")
    
    response = send_request("LIST_MY_GAMES")
    
    if not response or not response.get("success"):
        print(f"  ❌ {response.get('message', '查詢失敗')}")
        input("  按 Enter 返回...")
        return
    
    games = [g for g in response["data"]["games"] if g["status"] == "active"]
    
    if not games:
        print("  ⚠️ 沒有可下架的遊戲")
        input("  按 Enter 返回...")
        return
    
    print("\n  可下架的遊戲:")
    print("-" * 50)
    for i, game in enumerate(games, 1):
        print(f"  {i}. {game['name']} (v{game['version']})")
        print(f"     下載數: {game['download_count']}")
    print("-" * 50)
    print(f"  {len(games) + 1}. 返回")
    
    choice = get_choice("\n  請選擇要下架的遊戲: ", len(games) + 1)
    
    if choice == 'q' or choice == len(games) + 1:
        return
    
    selected_game = games[choice - 1]
    
    print(f"\n  ⚠️ 警告：下架後玩家將無法再下載此遊戲")
    confirm = input(f"  確定要下架 {selected_game['name']}? (輸入 yes 確認): ").strip().lower()
    
    if confirm != 'yes':
        print("  已取消")
        input("  按 Enter 返回...")
        return
    
    response = send_request("UNPUBLISH_GAME", {
        "game_id": selected_game["game_id"]
    })
    
    if response and response.get("success"):
        print(f"\n  ✅ 遊戲已下架")
    else:
        print(f"\n  ❌ {response.get('message', '下架失敗')}")
    
    input("  按 Enter 返回...")

# ========================= 主選單 =========================

def main_menu():
    """主選單"""
    global session_id, username
    
    while True:
        clear_screen()
        print_header(f"開發者平台 - {username}")
        print_menu([
            "上架新遊戲",
            "我的遊戲",
            "更新遊戲版本",
            "下架遊戲",
            "登出"
        ])
        
        choice = get_choice("請選擇 (1-5): ", 5)
        
        if choice == 'q' or choice == 5:
            response = send_request("LOGOUT")
            session_id = None
            username = None
            print("\n  ✅ 已登出")
            break
        
        if choice == 1:
            upload_game()
        elif choice == 2:
            list_my_games()
        elif choice == 3:
            update_game()
        elif choice == 4:
            unpublish_game()

# ========================= 主程式 =========================

def main():
    """主程式入口"""
    global SERVER_HOST, SERVER_PORT
    
    # 支援命令列參數
    if len(sys.argv) >= 3:
        SERVER_HOST = sys.argv[1]
        SERVER_PORT = int(sys.argv[2])
    
    print_header("開發者客戶端")
    print(f"  伺服器: {SERVER_HOST}:{SERVER_PORT}")
    print("  連線中...")
    
    if not connect_to_server():
        print("\n  ❌ 無法連線到伺服器")
        return
    
    print("  ✅ 連線成功")
    
    try:
        while True:
            if login_menu():
                main_menu()
            else:
                break
    finally:
        disconnect()
        print("\n  👋 再見！")

if __name__ == "__main__":
    main()
