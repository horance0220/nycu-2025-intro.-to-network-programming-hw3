#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Game Store System - Lobby Client (Player)
玩家用來瀏覽商城、下載遊戲、建立房間的客戶端
"""

import socket
import sys
import os
import json
import zipfile
import subprocess
import threading
import time

# 將專案根目錄加入路徑以使用 server.utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from server.utils import send_json, recv_json, recv_file_with_metadata

# ========================= 配置 =========================
SERVER_HOST = '140.113.17.11'
SERVER_PORT = 16969
DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), 'downloads')

# ========================= 全域變數 =========================
sock = None
session_id = None
username = None
player_download_dir = None
current_room = None
game_process = None

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
        "client_type": "player"
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
    global session_id, username, player_download_dir
    
    while True:
        clear_screen()
        print_header("遊戲大廳 - 歡迎")
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
                player_download_dir = os.path.join(DOWNLOADS_DIR, username)
                os.makedirs(player_download_dir, exist_ok=True)
                
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

# ========================= 大廳功能 =========================

def show_lobby_info():
    """顯示大廳資訊"""
    print_header("大廳狀態")
    
    response = send_request("GET_LOBBY_INFO")
    
    if not response or not response.get("success"):
        print(f"  ❌ {response.get('message', '查詢失敗')}")
        input("  按 Enter 返回...")
        return
    
    data = response["data"]
    
    print(f"\n  📊 大廳統計")
    print(f"  ├─ 線上玩家: {data['online_count']} 人")
    print(f"  ├─ 進行中房間: {data['room_count']} 間")
    print(f"  └─ 上架遊戲: {data['active_games']} 款")
    
    print(f"\n  👥 線上玩家:")
    if data['online_players']:
        for player in data['online_players'][:10]:
            marker = "⭐ " if player == username else "   "
            print(f"  {marker}{player}")
        if len(data['online_players']) > 10:
            print(f"  ...還有 {len(data['online_players']) - 10} 人")
    else:
        print("     (無)")
    
    print(f"\n  🎮 房間列表:")
    if data['rooms']:
        for room in data['rooms']:
            status_icon = "🎲" if room['status'] == 'playing' else "⏳"
            print(f"  {status_icon} [{room['room_id']}] {room['game_name']}")
            print(f"     房主: {room['host']} | 人數: {room['player_count']}/{room['max_players']}")
    else:
        print("     (目前沒有房間)")
    
    input("\n  按 Enter 返回...")

# ========================= 商城功能 =========================

def browse_store():
    """瀏覽商城"""
    while True:
        clear_screen()
        print_header("遊戲商城")
        
        response = send_request("LIST_GAMES")
        
        if not response or not response.get("success"):
            print(f"  ❌ {response.get('message', '查詢失敗')}")
            input("  按 Enter 返回...")
            return
        
        games = response["data"]["games"]
        
        if not games:
            print("  ⚠️ 目前沒有可遊玩的遊戲")
            input("  按 Enter 返回...")
            return
        
        print("\n  可用遊戲:")
        print("-" * 60)
        for i, game in enumerate(games, 1):
            stars = "⭐" * int(game['avg_rating']) + "☆" * (5 - int(game['avg_rating']))
            print(f"  {i}. 🎮 {game['name']} (v{game['version']})")
            print(f"     {stars} ({game['review_count']} 則評論)")
            print(f"     類型: {game['game_type']} | 人數: {game['min_players']}-{game['max_players']} | 下載: {game['download_count']}")
            print()
        print("-" * 60)
        print(f"  {len(games) + 1}. 返回")
        
        choice = get_choice("\n  選擇遊戲查看詳情: ", len(games) + 1)
        
        if choice == 'q' or choice == len(games) + 1:
            return
        
        show_game_detail(games[choice - 1]["game_id"])

def show_game_detail(game_id):
    """顯示遊戲詳情"""
    response = send_request("GET_GAME_DETAIL", {"game_id": game_id})
    
    if not response or not response.get("success"):
        print(f"  ❌ {response.get('message', '查詢失敗')}")
        input("  按 Enter 返回...")
        return
    
    game = response["data"]
    
    while True:
        clear_screen()
        print_header(f"遊戲詳情 - {game['name']}")
        
        stars = "⭐" * int(game['avg_rating']) + "☆" * (5 - int(game['avg_rating']))
        
        print(f"\n  📌 基本資訊")
        print(f"  ├─ 名稱: {game['name']}")
        print(f"  ├─ 作者: {game['developer']}")
        print(f"  ├─ 版本: v{game['version']}")
        print(f"  ├─ 類型: {game['game_type']}")
        print(f"  ├─ 人數: {game['min_players']}-{game['max_players']} 人")
        print(f"  └─ 下載數: {game['download_count']}")
        
        print(f"\n  📝 簡介")
        print(f"  {game['description']}")
        
        print(f"\n  ⭐ 評分: {stars} ({game['avg_rating']}/5)")
        
        if game['reviews']:
            print(f"\n  💬 最新評論:")
            for review in game['reviews'][-3:]:
                print(f"  ┌─ {review['username']} - {'⭐' * review['rating']}")
                if review['comment']:
                    print(f"  │  {review['comment'][:50]}...")
                print(f"  └─ {review['created_at'][:10]}")
        
        # 檢查本地版本
        local_version = get_local_version(game_id)
        print(f"\n  📁 本地版本: {local_version or '未下載'}")
        if local_version and local_version != game['version']:
            print(f"     ⚠️ 有新版本可更新！")
        
        print_menu([
            "下載/更新此遊戲",
            "建立房間遊玩",
            "撰寫評論",
            "返回"
        ])
        
        choice = get_choice("請選擇: ", 4)
        
        if choice == 'q' or choice == 4:
            return
        
        if choice == 1:
            download_game(game_id, game['name'], game['version'])
        elif choice == 2:
            create_room(game_id)
        elif choice == 3:
            write_review(game_id)

def get_local_version(game_id):
    """取得本地遊戲版本"""
    if not player_download_dir:
        return None
    
    game_dir = os.path.join(player_download_dir, game_id)
    config_path = os.path.join(game_dir, 'config.json')
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config.get('version')
        except:
            pass
    return None

def download_game(game_id, game_name, server_version):
    """下載遊戲"""
    print_header(f"下載遊戲 - {game_name}")
    
    local_version = get_local_version(game_id)
    
    if local_version:
        if local_version == server_version:
            print(f"  ✅ 您已擁有最新版本 (v{local_version})")
            confirm = input("  要重新下載嗎? (y/n): ").strip().lower()
            if confirm != 'y':
                return
        else:
            print(f"  📦 目前本地版本: v{local_version}")
            print(f"  📦 伺服器版本: v{server_version}")
            confirm = input("  確定要更新? (y/n): ").strip().lower()
            if confirm != 'y':
                return
    
    print("\n  ⏳ 正在下載...")
    
    response = send_request("DOWNLOAD_GAME", {"game_id": game_id})
    
    if not response or not response.get("success"):
        print(f"\n  ❌ {response.get('message', '下載失敗')}")
        input("  按 Enter 返回...")
        return
    
    # 準備接收檔案
    send_json(sock, {"status": "READY"})
    
    # 接收檔案 metadata
    file_meta = recv_json(sock)
    if not file_meta or file_meta.get("type") != "FILE_TRANSFER":
        print(f"\n  ❌ 未收到檔案")
        input("  按 Enter 返回...")
        return
    
    # 建立臨時目錄接收
    import tempfile
    temp_dir = tempfile.mkdtemp()
    
    success, msg, file_path = recv_file_with_metadata(sock, file_meta, temp_dir)
    
    if not success:
        print(f"\n  ❌ 下載失敗: {msg}")
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        input("  按 Enter 返回...")
        return
    
    # 解壓縮到遊戲目錄
    game_dir = os.path.join(player_download_dir, game_id)
    
    # 清除舊版本
    if os.path.exists(game_dir):
        import shutil
        shutil.rmtree(game_dir)
    
    os.makedirs(game_dir)
    
    try:
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(game_dir)
        print(f"\n  ✅ 下載完成！")
        print(f"  📁 路徑: {game_dir}")
    except Exception as e:
        print(f"\n  ❌ 解壓縮失敗: {e}")
    
    # 清理臨時目錄
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)
    
    input("  按 Enter 返回...")

# ========================= 房間功能 =========================

def rooms_menu():
    """房間選單"""
    while True:
        clear_screen()
        print_header("遊戲房間")
        print_menu([
            "建立新房間",
            "加入房間",
            "查看房間列表",
            "返回"
        ])
        
        choice = get_choice("請選擇: ", 4)
        
        if choice == 'q' or choice == 4:
            return
        
        if choice == 1:
            create_room_flow()
        elif choice == 2:
            join_room_flow()
        elif choice == 3:
            show_rooms()

def create_room_flow():
    """建立房間流程"""
    # 先選擇遊戲
    response = send_request("LIST_GAMES")
    
    if not response or not response.get("success"):
        print(f"  ❌ {response.get('message', '查詢失敗')}")
        input("  按 Enter 返回...")
        return
    
    games = response["data"]["games"]
    
    if not games:
        print("  ⚠️ 目前沒有可遊玩的遊戲")
        input("  按 Enter 返回...")
        return
    
    print_header("選擇遊戲")
    print("\n  可用遊戲:")
    for i, game in enumerate(games, 1):
        local_ver = get_local_version(game['game_id'])
        status = "✅" if local_ver == game['version'] else ("⬆️" if local_ver else "📥")
        print(f"  {i}. {status} {game['name']} (v{game['version']})")
    print(f"  {len(games) + 1}. 返回")
    
    choice = get_choice("\n  選擇遊戲: ", len(games) + 1)
    
    if choice == 'q' or choice == len(games) + 1:
        return
    
    game = games[choice - 1]
    create_room(game['game_id'])

def create_room(game_id):
    """建立房間"""
    # 檢查是否已下載
    local_version = get_local_version(game_id)
    
    if not local_version:
        print("  ⚠️ 您尚未下載此遊戲")
        confirm = input("  要先下載嗎? (y/n): ").strip().lower()
        if confirm == 'y':
            # 取得遊戲資訊
            response = send_request("GET_GAME_DETAIL", {"game_id": game_id})
            if response and response.get("success"):
                game = response["data"]
                download_game(game_id, game['name'], game['version'])
            else:
                print("  ❌ 無法取得遊戲資訊")
                return
        else:
            return
    
    print("\n  ⏳ 正在建立房間...")
    
    response = send_request("CREATE_ROOM", {"game_id": game_id})
    
    if not response or not response.get("success"):
        print(f"  ❌ {response.get('message', '建立失敗')}")
        input("  按 Enter 返回...")
        return
    
    data = response["data"]
    print(f"\n  ✅ 房間建立成功！")
    print(f"  房間 ID: {data['room_id']}")
    print(f"  遊戲: {data['game_name']} v{data['game_version']}")
    
    enter_room(data['room_id'])

def join_room_flow():
    """加入房間流程"""
    response = send_request("LIST_ROOMS")
    
    if not response or not response.get("success"):
        print(f"  ❌ {response.get('message', '查詢失敗')}")
        input("  按 Enter 返回...")
        return
    
    rooms = [r for r in response["data"]["rooms"] if r['status'] == 'waiting']
    
    if not rooms:
        print("  ⚠️ 目前沒有可加入的房間")
        input("  按 Enter 返回...")
        return
    
    print_header("選擇房間")
    for i, room in enumerate(rooms, 1):
        print(f"  {i}. [{room['room_id']}] {room['game_name']}")
        print(f"     房主: {room['host']} | 人數: {room['player_count']}/{room['max_players']}")
    print(f"  {len(rooms) + 1}. 返回")
    
    choice = get_choice("\n  選擇房間: ", len(rooms) + 1)
    
    if choice == 'q' or choice == len(rooms) + 1:
        return
    
    room = rooms[choice - 1]
    
    print("\n  ⏳ 正在加入房間...")
    
    response = send_request("JOIN_ROOM", {"room_id": room['room_id']})
    
    if not response or not response.get("success"):
        print(f"  ❌ {response.get('message', '加入失敗')}")
        input("  按 Enter 返回...")
        return
    
    print(f"  ✅ 加入成功！")
    enter_room(room['room_id'])

def show_rooms():
    """顯示房間列表"""
    print_header("房間列表")
    
    response = send_request("LIST_ROOMS")
    
    if not response or not response.get("success"):
        print(f"  ❌ {response.get('message', '查詢失敗')}")
        input("  按 Enter 返回...")
        return
    
    rooms = response["data"]["rooms"]
    
    if not rooms:
        print("  ⚠️ 目前沒有房間")
    else:
        print("\n  所有房間:")
        print("-" * 50)
        for room in rooms:
            status_icon = "🎲" if room['status'] == 'playing' else "⏳"
            print(f"  {status_icon} [{room['room_id']}] {room['game_name']}")
            print(f"     房主: {room['host']} | 人數: {room['player_count']}/{room['max_players']}")
            print(f"     玩家: {', '.join(room['players'])}")
            print()
        print("-" * 50)
    
    input("  按 Enter 返回...")

def enter_room(room_id):
    """進入房間等待"""
    global current_room, game_process
    current_room = room_id
    
    while True:
        clear_screen()
        print_header(f"房間 {room_id}")
        
        # 取得房間狀態
        response = send_request("LIST_ROOMS")
        
        if not response or not response.get("success"):
            print("  ❌ 無法取得房間資訊")
            current_room = None
            input("  按 Enter 返回...")
            return
        
        room = None
        for r in response["data"]["rooms"]:
            if r['room_id'] == room_id:
                room = r
                break
        
        if not room:
            print("  ⚠️ 房間已解散")
            current_room = None
            input("  按 Enter 返回...")
            return
        
        # 檢查遊戲版本
        game_id = room.get('game_id')
        latest_version = None
        local_version = None
        can_play = True
        version_msg = ""
        
        if game_id:
            local_version = get_local_version(game_id)
            
            # 取得 Server 最新版本
            g_resp = send_request("GET_GAME_DETAIL", {"game_id": game_id})
            if g_resp and g_resp.get("success"):
                latest_version = g_resp["data"]["version"]
            
            if not local_version:
                can_play = False
                version_msg = f"⚠️ 您尚未下載此遊戲 (v{latest_version})"
            elif latest_version and local_version != latest_version:
                can_play = False
                version_msg = f"⚠️ 有新版本可用 (v{latest_version})，請先更新！"
        
        print(f"\n  🎮 遊戲: {room['game_name']}")
        print(f"  👥 人數: {room['player_count']}/{room['max_players']}")
        print(f"  📊 狀態: {room['status']} (更新於 {time.strftime('%H:%M:%S')})")
        if version_msg:
            print(f"  {version_msg}")
            
        print(f"\n  玩家列表:")
        for player in room['players']:
            marker = "⭐ " if player == room['host'] else "   "
            you = " (你)" if player == username else ""
            print(f"  {marker}{player}{you}")
            
        # ===== Plugin: Chat =====
        chat_plugin_ver = get_local_plugin_version("chat_plugin")
        if chat_plugin_ver:
            print(f"\n  💬 聊天室 (Plugin v{chat_plugin_ver}):")
            print("  " + "-" * 40)
            
            # 取得聊天紀錄
            chat_resp = send_request("GET_ROOM_CHAT", {"room_id": room_id})
            if chat_resp and chat_resp.get("success"):
                history = chat_resp["data"]["chat_history"]
                if not history:
                    print("  (無訊息)")
                else:
                    # 顯示最近 5 則
                    for msg in history[-5:]:
                        print(f"  [{msg['time']}] {msg['username']}: {msg['message']}")
            else:
                print("  (無法取得聊天紀錄)")
            print("  " + "-" * 40)
        # ========================
        
        is_host = room['host'] == username
        
        options = []
        actions = []
        
        if room['status'] == 'waiting':
            if can_play:
                options.append("開始遊戲 (Start / Play Again)")
                actions.append("START")
            else:
                options.append("下載/更新遊戲")
                actions.append("UPDATE")
        elif room['status'] == 'playing':
            if can_play:
                options.append("加入遊戲 (Join Game)")
                actions.append("JOIN_GAME")
            else:
                options.append("下載/更新遊戲")
                actions.append("UPDATE")
            
        options.append("離開房間")
        actions.append("LEAVE")
        
        if chat_plugin_ver:
            options.append("發送聊天訊息")
            actions.append("SEND_CHAT")
        
        options.append("重新整理")
        actions.append("REFRESH")
        
        print_menu(options)
        
        choice = get_choice("請選擇: ", len(options))
        
        if choice == 'q':
            action = "LEAVE"
        else:
            action = actions[choice - 1]
            
        if action == "START":
            start_game(room_id, room['game_name'])
        elif action == "JOIN_GAME":
            join_started_game(room_id, game_id, room.get('port'))
        elif action == "UPDATE":
            download_game(game_id, room['game_name'], latest_version)
        elif action == "LEAVE":
            send_request("LEAVE_ROOM", {"room_id": room_id})
            current_room = None
            return
        elif action == "SEND_CHAT":
            msg = input("\n  輸入訊息: ").strip()
            if msg:
                send_request("SEND_CHAT", {"room_id": room_id, "message": msg})
        elif action == "REFRESH":
            pass

def launch_game_client(game_id, port, client_cmd=None):
    """啟動遊戲客戶端"""
    global game_process
    
    print(f"  ✅ 遊戲已啟動！")
    print(f"  連線 Port: {port}")
    
    # 啟動遊戲客戶端
    game_dir = os.path.join(player_download_dir, game_id)
    
    # 讀取本地 config
    config_path = os.path.join(game_dir, 'config.json')
    
    if not os.path.exists(config_path):
        print("  ⚠️ 找不到遊戲設定檔，請手動啟動遊戲")
        print(f"  遊戲目錄: {game_dir}")
        return
        
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        cmd = config.get("client_command", client_cmd)
        if cmd:
            # 加入連線參數
            full_cmd = cmd + ["--host", SERVER_HOST, "--port", str(port)]
            print(f"  啟動指令: {' '.join(full_cmd)}")
            
            try:
                game_process = subprocess.Popen(
                    full_cmd,
                    cwd=game_dir,
                    creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
                )
                print("  ✅ 遊戲視窗已開啟")
            except FileNotFoundError:
                print("  ⚠️ 找不到遊戲執行檔，請手動啟動")
            except Exception as e:
                print(f"  ❌ 啟動失敗: {e}")
    except Exception as e:
        print(f"  ❌ 讀取設定檔失敗: {e}")

def start_game(room_id, game_name):
    """開始遊戲 (房主)"""
    global game_process
    
    print("\n  ⏳ 正在啟動遊戲...")
    
    response = send_request("START_GAME", {"room_id": room_id})
    
    if not response or not response.get("success"):
        print(f"  ❌ {response.get('message', '啟動失敗')}")
        input("  按 Enter 返回...")
        return
    
    data = response["data"]
    port = data["port"]
    client_cmd = data.get("client_command", [])
    game_id = data.get("game_id", room_id.split('-')[0]) # Fallback for old server
    
    launch_game_client(game_id, port, client_cmd)
    
    print("\n  遊戲進行中... (關閉遊戲視窗以返回)")
    
    if game_process:
        try:
            game_process.wait()
        except KeyboardInterrupt:
            pass
        game_process = None
    
    # 遊戲結束，不發送 END_GAME，因為 Game Server 會回報結果並將房間設為 waiting
    # 除非是強制結束... 但這裡假設正常流程
    print("\n  遊戲已結束")
    
    # 詢問是否評分
    prompt_review_after_game(game_id)

def join_started_game(room_id, game_id, port):
    """加入已開始的遊戲 (非房主)"""
    global game_process
    
    print("\n  ⏳ 正在啟動遊戲客戶端...")
    launch_game_client(game_id, port)
    
    print("\n  遊戲進行中... (關閉遊戲視窗以返回)")
    
    if game_process:
        try:
            game_process.wait()
        except KeyboardInterrupt:
            pass
        game_process = None
    
    print("\n  遊戲已結束")
    
    # 詢問是否評分
    prompt_review_after_game(game_id)

# ========================= 評論功能 =========================

def prompt_review_after_game(game_id):
    """遊戲結束後詢問是否評分"""
    print("\n" + "=" * 50)
    print("  遊戲結束！")
    print("  您想要對這款遊戲進行評分嗎？")
    print("  1. 評分並返回房間")
    print("  2. 直接返回房間")
    print("=" * 50)
    
    choice = get_choice("請選擇 (1-2): ", 2)
    
    if choice == 1:
        write_review(game_id)

def write_review(game_id):
    """撰寫評論"""
    print_header("撰寫評論")
    
    print("\n  請為此遊戲評分 (1-5 星):")
    print("  1 ⭐ - 非常差")
    print("  2 ⭐⭐ - 差")
    print("  3 ⭐⭐⭐ - 普通")
    print("  4 ⭐⭐⭐⭐ - 好")
    print("  5 ⭐⭐⭐⭐⭐ - 非常好")
    
    rating = get_choice("\n  評分: ", 5)
    
    if rating == 'q':
        return
    
    comment = input("  評論內容 (可選，最多 500 字): ").strip()
    
    while True:
        print("\n  ⏳ 正在送出...")
        
        response = send_request("ADD_REVIEW", {
            "game_id": game_id,
            "rating": rating,
            "comment": comment
        })
        
        if response and response.get("success"):
            print("  ✅ 評論成功！")
            break
        elif response is None:
            print("  ❌ 連線失敗，無法送出評論。")
            retry = input("  要重試嗎? (y/n): ").strip().lower()
            if retry != 'y':
                print("  ⚠️ 評論未送出。")
                break
        else:
            print(f"  ❌ {response.get('message', '評論失敗')}")
            break
    
    input("  按 Enter 返回...")

def plugin_menu():
    """Plugin 管理選單"""
    while True:
        clear_screen()
        print_header("Plugin 管理")
        print_menu([
            "查看可用 Plugin",
            "已安裝 Plugin",
            "返回主選單"
        ])
        
        choice = get_choice("請選擇 (1-3): ", 3)
        
        if choice == 3 or choice == 'q':
            break
        
        if choice == 1:
            browse_plugins()
        elif choice == 2:
            show_installed_plugins()

def get_local_plugin_version(plugin_id):
    """取得本地 Plugin 版本"""
    if not player_download_dir:
        return None
        
    record_path = os.path.join(player_download_dir, 'plugins', 'installed.json')
    if not os.path.exists(record_path):
        return None
        
    try:
        with open(record_path, 'r', encoding='utf-8') as f:
            record = json.load(f)
        val = record.get(plugin_id)
        if isinstance(val, dict):
            return val.get('version')
        return val
    except:
        return None

def get_local_plugin_filename(plugin_id):
    """取得本地 Plugin 檔名"""
    if not player_download_dir:
        return None
        
    record_path = os.path.join(player_download_dir, 'plugins', 'installed.json')
    if not os.path.exists(record_path):
        return None
        
    try:
        with open(record_path, 'r', encoding='utf-8') as f:
            record = json.load(f)
        val = record.get(plugin_id)
        if isinstance(val, dict):
            return val.get('filename')
        return None
    except:
        return None

def update_local_plugin_record(plugin_id, version, filename):
    """更新本地 Plugin 紀錄"""
    if not player_download_dir:
        return
        
    plugins_dir = os.path.join(player_download_dir, 'plugins')
    os.makedirs(plugins_dir, exist_ok=True)
    
    record_path = os.path.join(plugins_dir, 'installed.json')
    record = {}
    
    if os.path.exists(record_path):
        try:
            with open(record_path, 'r', encoding='utf-8') as f:
                record = json.load(f)
        except:
            pass
            
    record[plugin_id] = {
        "version": version,
        "filename": filename
    }
    
    with open(record_path, 'w', encoding='utf-8') as f:
        json.dump(record, f, indent=4)

def remove_local_plugin(plugin_id):
    """移除本地 Plugin"""
    if not player_download_dir:
        return False, "未登入"
        
    filename = get_local_plugin_filename(plugin_id)
    if not filename:
        # 嘗試從舊格式或直接猜測? 不，如果沒有紀錄就無法安全刪除
        # 但如果是舊格式(只存版本字串)，我們不知道檔名。
        # 這裡假設都已經是新格式，或者無法刪除舊格式的殘留檔案(除非手動)。
        return False, "找不到 Plugin 檔案紀錄"
        
    plugins_dir = os.path.join(player_download_dir, 'plugins')
    file_path = os.path.join(plugins_dir, filename)
    
    # 刪除檔案
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            return False, f"刪除檔案失敗: {e}"
            
    # 更新紀錄
    record_path = os.path.join(plugins_dir, 'installed.json')
    if os.path.exists(record_path):
        try:
            with open(record_path, 'r', encoding='utf-8') as f:
                record = json.load(f)
            
            if plugin_id in record:
                del record[plugin_id]
                
            with open(record_path, 'w', encoding='utf-8') as f:
                json.dump(record, f, indent=4)
        except Exception as e:
            return False, f"更新紀錄失敗: {e}"
            
    return True, "移除成功"

def browse_plugins():
    """瀏覽並安裝 Plugin"""
    while True:
        clear_screen()
        print_header("可用 Plugin")
        
        response = send_request("LIST_PLUGINS")
        if not response or not response.get("success"):
            print(f"  ❌ 取得列表失敗: {response.get('message') if response else 'Unknown'}")
            input("  按 Enter 返回...")
            return
            
        plugins = response.get("data", {})
        if not plugins:
            print("  ⚠️ 目前沒有可用的 Plugin")
            input("  按 Enter 返回...")
            return
            
        plugin_ids = list(plugins.keys())
        
        print(f"  {'ID':<12} {'名稱':<15} {'狀態':<15} {'描述'}")
        print("  " + "-" * 65)
        
        for i, pid in enumerate(plugin_ids, 1):
            p = plugins[pid]
            server_ver = p['version']
            local_ver = get_local_plugin_version(pid)
            
            status = "未安裝"
            if local_ver:
                if local_ver == server_ver:
                    status = f"已安裝 (v{local_ver})"
                else:
                    status = f"可更新 (v{local_ver} -> v{server_ver})"
            
            print(f"  {i}. {p['name']:<15} {status:<15} {p['description']}")
        
        print("  " + "-" * 65)
        print(f"  {len(plugin_ids) + 1}. 返回")
        
        choice = get_choice("\n  選擇 Plugin 查看詳情或管理: ", len(plugin_ids) + 1)
        
        if choice == 'q' or choice == len(plugin_ids) + 1:
            return
            
        selected_pid = plugin_ids[choice - 1]
        manage_plugin_interaction(selected_pid, plugins[selected_pid])

def manage_plugin_interaction(pid, plugin_info):
    """管理單一 Plugin 的互動介面"""
    while True:
        clear_screen()
        print_header(f"Plugin 詳情 - {plugin_info['name']}")
        
        server_ver = plugin_info['version']
        local_ver = get_local_plugin_version(pid)
        
        status = "未安裝"
        if local_ver:
            if local_ver == server_ver:
                status = f"已安裝 (v{local_ver})"
            else:
                status = f"可更新 (v{local_ver} -> v{server_ver})"
        
        print(f"\n  📌 基本資訊")
        print(f"  ├─ ID: {pid}")
        print(f"  ├─ 名稱: {plugin_info['name']}")
        print(f"  ├─ 最新版本: v{server_ver}")
        print(f"  └─ 狀態: {status}")
        
        print(f"\n  📝 描述")
        print(f"  {plugin_info['description']}")
        
        options = []
        actions = []
        
        if not local_ver:
            options.append("安裝此 Plugin")
            actions.append("INSTALL")
        else:
            if local_ver != server_ver:
                options.append("更新此 Plugin")
                actions.append("INSTALL")
            
            options.append("移除此 Plugin")
            actions.append("REMOVE")
            
        options.append("返回列表")
        actions.append("BACK")
        
        print_menu(options)
        
        choice = get_choice("請選擇: ", len(options))
        
        if choice == 'q':
            return
            
        action = actions[choice - 1]
        
        if action == "BACK":
            return
            
        elif action == "INSTALL":
            print(f"\n  ⬇️ 正在下載 {plugin_info['name']} ...")
            
            # 確保 plugin 目錄存在
            plugins_dir = os.path.join(player_download_dir, 'plugins')
            if not os.path.exists(plugins_dir):
                os.makedirs(plugins_dir)
                
            # 發送下載請求
            req = {
                "action": "DOWNLOAD_PLUGIN",
                "client_type": "player",
                "session_id": session_id,
                "plugin_id": pid
            }
            send_json(sock, req)
            
            # 接收檔案
            file_path = os.path.join(plugins_dir, plugin_info['filename'])
            success, msg = recv_file_with_metadata(sock, file_path)
            
            if success:
                update_local_plugin_record(pid, plugin_info['version'], plugin_info['filename'])
                print(f"  ✅ 安裝/更新成功！")
            else:
                print(f"  ❌ 安裝失敗: {msg}")
            
            input("  按 Enter 繼續...")
            
        elif action == "REMOVE":
            confirm = input(f"\n  確定要移除 {plugin_info['name']} 嗎? (y/n): ").strip().lower()
            if confirm == 'y':
                success, msg = remove_local_plugin(pid)
                if success:
                    print(f"  ✅ {msg}")
                else:
                    print(f"  ❌ {msg}")
                input("  按 Enter 繼續...")

def show_installed_plugins():
    """顯示已安裝 Plugin"""
    print_header("已安裝 Plugin")
    
    if not player_download_dir:
        print("  ⚠️ 未登入")
        input("  按 Enter 返回...")
        return

    plugins_dir = os.path.join(player_download_dir, 'plugins')
    record_path = os.path.join(plugins_dir, 'installed.json')
    
    record = {}
    if os.path.exists(record_path):
        try:
            with open(record_path, 'r', encoding='utf-8') as f:
                record = json.load(f)
        except:
            pass
            
    if not record:
        print("  ⚠️ 尚未安裝任何 Plugin")
        input("  按 Enter 返回...")
        return
        
    print(f"  {'ID':<15} {'版本':<10}")
    print("  " + "-" * 30)
    for pid, ver in record.items():
        v_str = ver.get('version') if isinstance(ver, dict) else ver
        print(f"  {pid:<15} v{v_str:<10}")
    print("  " + "-" * 30)
    
    print("\n  輸入 Plugin ID 進行移除，或按 Enter 返回")
    choice = input("  > ").strip()
    
    if choice and choice in record:
        confirm = input(f"  確定要移除 {choice} 嗎? (y/n): ").strip().lower()
        if confirm == 'y':
            success, msg = remove_local_plugin(choice)
            if success:
                print(f"  ✅ {msg}")
            else:
                print(f"  ❌ {msg}")
            input("  按 Enter 繼續...")
    elif choice:
        print("  ❌ 無效的 ID")
        time.sleep(1)

# ========================= 主選單 =========================

def main_menu():
    """主選單"""
    global session_id, username, current_room
    
    while True:
        clear_screen()
        print_header(f"遊戲大廳 - {username}")
        print_menu([
            "大廳狀態",
            "遊戲商城",
            "遊戲房間",
            "我的遊戲 (已下載)",
            "我的紀錄 (評分)",
            "Plugin 管理",
            "登出"
        ])
        
        choice = get_choice("請選擇 (1-7): ", 7)
        
        if choice == 'q' or choice == 7:
            if current_room:
                send_request("LEAVE_ROOM", {"room_id": current_room})
                current_room = None
            response = send_request("LOGOUT")
            session_id = None
            username = None
            print("\n  ✅ 已登出")
            break
        
        if choice == 1:
            show_lobby_info()
        elif choice == 2:
            browse_store()
        elif choice == 3:
            rooms_menu()
        elif choice == 4:
            show_my_games()
        elif choice == 5:
            show_my_history()
        elif choice == 6:
            plugin_menu()

def show_my_history():
    """顯示我的遊玩紀錄並允許評分"""
    print_header("我的遊玩紀錄")
    
    response = send_request("GET_PLAYER_PROFILE")
    
    if not response or not response.get("success"):
        print(f"  ❌ {response.get('message', '查詢失敗')}")
        input("  按 Enter 返回...")
        return
    
    played_games = response["data"]["played_games"]
    
    if not played_games:
        print("  ⚠️ 尚未遊玩過任何遊戲")
        input("  按 Enter 返回...")
        return
        
    print("\n  您玩過的遊戲:")
    print("-" * 50)
    for i, game in enumerate(played_games, 1):
        print(f"  {i}. {game['name']} (ID: {game['game_id']})")
    print("-" * 50)
    print(f"  {len(played_games) + 1}. 返回")
    
    choice = get_choice("\n  選擇遊戲進行評分: ", len(played_games) + 1)
    
    if choice == 'q' or choice == len(played_games) + 1:
        return
        
    selected_game = played_games[choice - 1]
    write_review(selected_game["game_id"])

def show_my_games():
    """顯示我的已下載遊戲"""
    print_header("我的遊戲")
    
    if not player_download_dir or not os.path.exists(player_download_dir):
        print("  ⚠️ 尚未下載任何遊戲")
        input("  按 Enter 返回...")
        return
    
    games = []
    for item in os.listdir(player_download_dir):
        item_path = os.path.join(player_download_dir, item)
        if os.path.isdir(item_path):
            config_path = os.path.join(item_path, 'config.json')
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    games.append({
                        "game_id": item,
                        "name": config.get("name", item),
                        "version": config.get("version", "?")
                    })
                except:
                    games.append({
                        "game_id": item,
                        "name": item,
                        "version": "?"
                    })
    
    if not games:
        print("  ⚠️ 尚未下載任何遊戲")
    else:
        print("\n  已下載的遊戲:")
        print("-" * 50)
        for game in games:
            print(f"  📁 {game['name']} (v{game['version']})")
            print(f"     ID: {game['game_id']}")
        print("-" * 50)
    
    input("  按 Enter 返回...")

# ========================= 主程式 =========================

def main():
    """主程式入口"""
    global SERVER_HOST, SERVER_PORT
    
    # 支援命令列參數
    if len(sys.argv) >= 3:
        SERVER_HOST = sys.argv[1]
        SERVER_PORT = int(sys.argv[2])
    
    print_header("遊戲大廳客戶端")
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
