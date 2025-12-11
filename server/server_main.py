#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Game Store System - Main Server
支援 Developer Client 和 Lobby Client 的連線
"""

import socket
import threading
import json
import os
import sys
import uuid
import shutil
import zipfile
import subprocess
from datetime import datetime

# 導入自定義的通訊協定
from utils import send_json, recv_json, recv_file_with_metadata, create_response, send_file

# ========================= 配置 =========================
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
STORAGE_DIR = os.path.join(os.path.dirname(__file__), 'storage')
DATABASE_FILE = os.path.join(os.path.dirname(__file__), 'database.json')

# ========================= 全域變數 =========================
db_lock = threading.Lock()
active_sessions = {}  # session_id -> {"username": ..., "type": ..., "socket": ...}
rooms = {}  # room_id -> {"game_id": ..., "players": [...], "status": ..., "port": ...}
game_servers = {}  # room_id -> subprocess

# 動態分配的 Port 範圍
GAME_PORT_START = 9000
GAME_PORT_END = 9100
used_ports = set()

# ========================= 資料庫操作 =========================

def load_database():
    """載入資料庫"""
    with db_lock:
        try:
            with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "developers": {},
                "players": {},
                "games": {},
                "reviews": {},
                "rooms": {}
            }
        except json.JSONDecodeError:
            print("[Error] Database JSON 格式錯誤")
            try:
                import shutil
                shutil.copy(DATABASE_FILE, DATABASE_FILE + ".corrupted")
                print(f"[Info] Corrupted database backed up to {DATABASE_FILE}.corrupted")
            except:
                pass
            
            return {
                "developers": {},
                "players": {},
                "games": {},
                "reviews": {},
                "rooms": {}
            }

def save_database(db):
    """儲存資料庫"""
    with db_lock:
        with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=4, ensure_ascii=False)

# ========================= 帳號系統 =========================

def handle_register(request, user_type):
    """處理註冊請求"""
    username = request.get("username", "").strip()
    password = request.get("password", "").strip()
    display_name = request.get("display_name", username)
    
    if not username or not password:
        return create_response(False, "帳號和密碼不可為空")
    
    if len(username) < 3:
        return create_response(False, "帳號長度至少 3 個字元")
    
    if len(password) < 4:
        return create_response(False, "密碼長度至少 4 個字元")
    
    db = load_database()
    users = db.get(user_type, {})
    
    if username in users:
        return create_response(False, "帳號已被使用")
    
    users[username] = {
        "password": password,
        "display_name": display_name,
        "created_at": datetime.now().isoformat(),
        "session_id": None
    }
    
    if user_type == "players":
        users[username]["played_games"] = []
    
    db[user_type] = users
    save_database(db)
    
    print(f"[Register] New {user_type[:-1]}: {username}")
    return create_response(True, "註冊成功")

def handle_login(request, user_type, client_socket):
    """處理登入請求"""
    username = request.get("username", "").strip()
    password = request.get("password", "").strip()
    
    if not username or not password:
        return create_response(False, "帳號和密碼不可為空")
    
    db = load_database()
    users = db.get(user_type, {})
    
    if username not in users:
        return create_response(False, "帳號不存在，請先註冊")
    
    if users[username]["password"] != password:
        return create_response(False, "密碼錯誤")
    
    # 檢查是否已有 session（踢掉舊的）
    old_session = users[username].get("session_id")
    if old_session and old_session in active_sessions:
        old_socket = active_sessions[old_session].get("socket")
        if old_socket:
            try:
                send_json(old_socket, {
                    "type": "FORCE_LOGOUT",
                    "message": "您的帳號已在其他裝置登入"
                })
                old_socket.close()
            except:
                pass
        del active_sessions[old_session]
    
    # 產生新 session
    session_id = str(uuid.uuid4())
    users[username]["session_id"] = session_id
    db[user_type] = users
    save_database(db)
    
    active_sessions[session_id] = {
        "username": username,
        "type": user_type,
        "socket": client_socket
    }
    
    print(f"[Login] {user_type[:-1]} logged in: {username}")
    
    return create_response(True, "登入成功", {
        "session_id": session_id,
        "username": username,
        "display_name": users[username]["display_name"]
    })

def handle_logout(request, user_type):
    """處理登出請求"""
    session_id = request.get("session_id")
    
    if session_id in active_sessions:
        username = active_sessions[session_id]["username"]
        del active_sessions[session_id]
        
        db = load_database()
        if username in db.get(user_type, {}):
            db[user_type][username]["session_id"] = None
            save_database(db)
        
        print(f"[Logout] {user_type[:-1]} logged out: {username}")
        return create_response(True, "登出成功")
    
    return create_response(False, "Session 不存在")

def verify_session(session_id, user_type):
    """驗證 Session"""
    if session_id not in active_sessions:
        return None
    session = active_sessions[session_id]
    if session["type"] != user_type:
        return None
    return session["username"]

# ========================= 遊戲管理 (Developer) =========================

def handle_upload_game(request, client_socket):
    """處理遊戲上架請求"""
    session_id = request.get("session_id")
    username = verify_session(session_id, "developers")
    
    if not username:
        return create_response(False, "請先登入")
    
    game_info = request.get("game_info", {})
    game_name = game_info.get("name", "").strip()
    
    if not game_name:
        return create_response(False, "遊戲名稱不可為空")
    
    db = load_database()
    
    # 檢查遊戲名稱是否已存在
    for gid, game in db.get("games", {}).items():
        if game["name"] == game_name and game.get("status") == "active":
            return create_response(False, "遊戲名稱已存在")
    
    # 產生遊戲 ID
    game_id = str(uuid.uuid4())[:8]
    
    # 準備儲存目錄
    game_storage = os.path.join(STORAGE_DIR, game_id)
    os.makedirs(game_storage, exist_ok=True)
    
    # 通知 Client 可以開始傳送檔案
    send_json(client_socket, create_response(True, "準備接收檔案", {"game_id": game_id}))
    
    # 接收檔案
    file_meta = recv_json(client_socket)
    if not file_meta or file_meta.get("type") != "FILE_TRANSFER":
        shutil.rmtree(game_storage, ignore_errors=True)
        return create_response(False, "未收到檔案")
    
    success, msg, file_path = recv_file_with_metadata(client_socket, file_meta, game_storage)
    
    if not success:
        shutil.rmtree(game_storage, ignore_errors=True)
        return create_response(False, f"檔案傳輸失敗: {msg}")
    
    # 如果是 zip 檔，解壓縮
    if file_path.endswith('.zip'):
        try:
            extract_dir = os.path.join(game_storage, 'game')
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            os.remove(file_path)
        except Exception as e:
            shutil.rmtree(game_storage, ignore_errors=True)
            return create_response(False, f"解壓縮失敗: {e}")
    
    # 驗證遊戲檔案結構
    extract_dir = os.path.join(game_storage, 'game')
    config_path = os.path.join(extract_dir, 'config.json')
    if not os.path.exists(config_path):
        shutil.rmtree(game_storage, ignore_errors=True)
        return create_response(False, "缺少 config.json 設定檔")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
        required_fields = ["name", "version", "server_command", "client_command"]
        missing = [field for field in required_fields if field not in config]
        
        if missing:
            shutil.rmtree(game_storage, ignore_errors=True)
            return create_response(False, f"config.json 缺少必要欄位: {', '.join(missing)}")
            
        if not isinstance(config.get("server_command"), list) or not isinstance(config.get("client_command"), list):
             shutil.rmtree(game_storage, ignore_errors=True)
             return create_response(False, "server_command 與 client_command 必須是列表 (List)")

    except json.JSONDecodeError:
        shutil.rmtree(game_storage, ignore_errors=True)
        return create_response(False, "config.json 格式錯誤")
    except Exception as e:
        shutil.rmtree(game_storage, ignore_errors=True)
        return create_response(False, f"驗證失敗: {e}")

    # 儲存遊戲資訊到資料庫
    db["games"][game_id] = {
        "name": game_name,
        "description": game_info.get("description", "尚未提供簡介"),
        "developer": username,
        "version": game_info.get("version", "1.0.0"),
        "game_type": game_info.get("game_type", "CLI"),
        "max_players": game_info.get("max_players", 2),
        "min_players": game_info.get("min_players", 2),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "status": "active",
        "storage_path": game_storage,
        "download_count": 0
    }
    
    save_database(db)
    
    print(f"[Upload] Game uploaded: {game_name} by {username}")
    return create_response(True, "遊戲上架成功", {"game_id": game_id})

def handle_update_game(request, client_socket):
    """處理遊戲更新請求"""
    session_id = request.get("session_id")
    username = verify_session(session_id, "developers")
    
    if not username:
        return create_response(False, "請先登入")
    
    game_id = request.get("game_id")
    new_version = request.get("version", "").strip()
    
    db = load_database()
    
    if game_id not in db.get("games", {}):
        return create_response(False, "遊戲不存在")
    
    game = db["games"][game_id]
    
    if game["developer"] != username:
        return create_response(False, "無權限更新此遊戲")
    
    if game["status"] != "active":
        return create_response(False, "遊戲已下架，無法更新")
    
    if not new_version:
        return create_response(False, "請提供新版本號")
    
    if new_version == game["version"]:
        return create_response(False, "版本號不可與目前版本相同")
    
    # 準備儲存目錄
    game_storage = game["storage_path"]
    
    # 清除舊檔案
    game_dir = os.path.join(game_storage, 'game')
    if os.path.exists(game_dir):
        shutil.rmtree(game_dir)
    
    # 通知 Client 可以開始傳送檔案
    send_json(client_socket, create_response(True, "準備接收檔案"))
    
    # 接收檔案
    file_meta = recv_json(client_socket)
    if not file_meta or file_meta.get("type") != "FILE_TRANSFER":
        return create_response(False, "未收到檔案")
    
    success, msg, file_path = recv_file_with_metadata(client_socket, file_meta, game_storage)
    
    if not success:
        return create_response(False, f"檔案傳輸失敗: {msg}")
    
    # 如果是 zip 檔，解壓縮
    if file_path.endswith('.zip'):
        try:
            extract_dir = os.path.join(game_storage, 'game')
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            os.remove(file_path)
        except Exception as e:
            return create_response(False, f"解壓縮失敗: {e}")
    
    # 驗證遊戲檔案結構
    extract_dir = os.path.join(game_storage, 'game')
    config_path = os.path.join(extract_dir, 'config.json')
    if not os.path.exists(config_path):
        return create_response(False, "缺少 config.json 設定檔")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
        required_fields = ["name", "version", "server_command", "client_command"]
        missing = [field for field in required_fields if field not in config]
        
        if missing:
            return create_response(False, f"config.json 缺少必要欄位: {', '.join(missing)}")
            
        if not isinstance(config.get("server_command"), list) or not isinstance(config.get("client_command"), list):
             return create_response(False, "server_command 與 client_command 必須是列表 (List)")

    except json.JSONDecodeError:
        return create_response(False, "config.json 格式錯誤")
    except Exception as e:
        return create_response(False, f"驗證失敗: {e}")

    # 更新版本資訊
    game["version"] = new_version
    game["updated_at"] = datetime.now().isoformat()
    
    if "update_notes" in request:
        if "update_history" not in game:
            game["update_history"] = []
        game["update_history"].append({
            "version": new_version,
            "notes": request["update_notes"],
            "date": datetime.now().isoformat()
        })
    
    db["games"][game_id] = game
    save_database(db)
    
    print(f"[Update] Game updated: {game['name']} to version {new_version}")
    return create_response(True, "遊戲更新成功")

def handle_unpublish_game(request):
    """處理遊戲下架請求"""
    session_id = request.get("session_id")
    username = verify_session(session_id, "developers")
    
    if not username:
        return create_response(False, "請先登入")
    
    game_id = request.get("game_id")
    
    db = load_database()
    
    if game_id not in db.get("games", {}):
        return create_response(False, "遊戲不存在")
    
    game = db["games"][game_id]
    
    if game["developer"] != username:
        return create_response(False, "無權限下架此遊戲")
    
    if game["status"] != "active":
        return create_response(False, "遊戲已經是下架狀態")
    
    # 檢查是否有進行中的房間
    for room_id, room in rooms.items():
        if room["game_id"] == game_id and room["status"] == "playing":
            return create_response(False, "有進行中的遊戲房間，無法下架")
    
    game["status"] = "unpublished"
    game["unpublished_at"] = datetime.now().isoformat()
    db["games"][game_id] = game
    save_database(db)
    
    print(f"[Unpublish] Game unpublished: {game['name']} by {username}")
    return create_response(True, "遊戲已下架")

def handle_list_my_games(request):
    """列出開發者自己的遊戲"""
    session_id = request.get("session_id")
    username = verify_session(session_id, "developers")
    
    if not username:
        return create_response(False, "請先登入")
    
    db = load_database()
    my_games = []
    
    for game_id, game in db.get("games", {}).items():
        if game["developer"] == username:
            my_games.append({
                "game_id": game_id,
                "name": game["name"],
                "version": game["version"],
                "status": game["status"],
                "created_at": game["created_at"],
                "updated_at": game["updated_at"],
                "download_count": game.get("download_count", 0)
            })
    
    return create_response(True, "查詢成功", {"games": my_games})

# ========================= 遊戲商城 (Player) =========================

def handle_list_games(request):
    """列出所有上架的遊戲"""
    db = load_database()
    games_list = []
    
    for game_id, game in db.get("games", {}).items():
        if game["status"] == "active":
            # 計算平均評分
            reviews = db.get("reviews", {}).get(game_id, [])
            avg_rating = 0
            if reviews:
                avg_rating = sum(r["rating"] for r in reviews) / len(reviews)
            
            games_list.append({
                "game_id": game_id,
                "name": game["name"],
                "description": game["description"],
                "developer": game["developer"],
                "version": game["version"],
                "game_type": game["game_type"],
                "max_players": game["max_players"],
                "min_players": game["min_players"],
                "avg_rating": round(avg_rating, 1),
                "review_count": len(reviews),
                "download_count": game.get("download_count", 0)
            })
    
    return create_response(True, "查詢成功", {"games": games_list})

def handle_get_game_detail(request):
    """取得遊戲詳細資訊"""
    game_id = request.get("game_id")
    
    db = load_database()
    
    if game_id not in db.get("games", {}):
        return create_response(False, "遊戲不存在")
    
    game = db["games"][game_id]
    reviews = db.get("reviews", {}).get(game_id, [])
    
    avg_rating = 0
    if reviews:
        avg_rating = sum(r["rating"] for r in reviews) / len(reviews)
    
    game_detail = {
        "game_id": game_id,
        "name": game["name"],
        "description": game["description"],
        "developer": game["developer"],
        "version": game["version"],
        "game_type": game["game_type"],
        "max_players": game["max_players"],
        "min_players": game["min_players"],
        "created_at": game["created_at"],
        "updated_at": game["updated_at"],
        "status": game["status"],
        "avg_rating": round(avg_rating, 1),
        "reviews": reviews[-10:],  # 只回傳最新 10 則評論
        "download_count": game.get("download_count", 0)
    }
    
    return create_response(True, "查詢成功", game_detail)

def handle_download_game(request, client_socket):
    """處理遊戲下載請求"""
    session_id = request.get("session_id")
    username = verify_session(session_id, "players")
    
    if not username:
        return create_response(False, "請先登入")
    
    game_id = request.get("game_id")
    
    db = load_database()
    
    if game_id not in db.get("games", {}):
        return create_response(False, "遊戲不存在")
    
    game = db["games"][game_id]
    
    if game["status"] != "active":
        return create_response(False, "遊戲已下架，無法下載")
    
    game_storage = game["storage_path"]
    game_dir = os.path.join(game_storage, 'game')
    
    if not os.path.exists(game_dir):
        return create_response(False, "遊戲檔案不存在")
    
    # 將遊戲目錄打包成 zip
    zip_path = os.path.join(game_storage, f'{game_id}.zip')
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(game_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, game_dir)
                    zipf.write(file_path, arcname)
    except Exception as e:
        return create_response(False, f"打包失敗: {e}")
    
    # 傳送檔案資訊給 Client
    from utils import send_file
    
    send_json(client_socket, create_response(True, "準備傳送檔案", {
        "game_id": game_id,
        "game_name": game["name"],
        "version": game["version"]
    }))
    
    # 等待 Client 確認
    ack = recv_json(client_socket)
    if not ack or ack.get("status") != "READY":
        return create_response(False, "Client 未準備好")
    
    success, msg = send_file(client_socket, zip_path)
    
    if success:
        # 更新下載次數
        game["download_count"] = game.get("download_count", 0) + 1
        db["games"][game_id] = game
        save_database(db)
        print(f"[Download] {username} downloaded {game['name']}")
    
    # 清理臨時 zip 檔
    try:
        os.remove(zip_path)
    except:
        pass
    
    return None  # 回應已在 send_file 中處理

# ========================= 房間管理 =========================

def allocate_port():
    """分配一個可用的 Port"""
    for port in range(GAME_PORT_START, GAME_PORT_END):
        if port not in used_ports:
            used_ports.add(port)
            return port
    return None

def release_port(port):
    """釋放 Port"""
    used_ports.discard(port)

def handle_create_room(request):
    """建立遊戲房間"""
    session_id = request.get("session_id")
    username = verify_session(session_id, "players")
    
    if not username:
        return create_response(False, "請先登入")
    
    game_id = request.get("game_id")
    
    db = load_database()
    
    if game_id not in db.get("games", {}):
        return create_response(False, "遊戲不存在")
    
    game = db["games"][game_id]
    
    if game["status"] != "active":
        return create_response(False, "遊戲已下架，無法建立房間")
    
    # 檢查玩家是否已在其他房間
    for room_id, room in rooms.items():
        if username in room["players"]:
            return create_response(False, "您已在其他房間中")
    
    # 建立房間
    room_id = str(uuid.uuid4())[:8]
    port = allocate_port()
    
    if not port:
        return create_response(False, "伺服器繁忙，請稍後再試")
    
    rooms[room_id] = {
        "game_id": game_id,
        "game_name": game["name"],
        "game_version": game["version"],
        "host": username,
        "players": [username],
        "max_players": game["max_players"],
        "min_players": game["min_players"],
        "status": "waiting",
        "port": port,
        "created_at": datetime.now().isoformat(),
        "chat_history": []
    }
    
    print(f"[Room] Room created: {room_id} for {game['name']} by {username}")
    
    return create_response(True, "房間建立成功", {
        "room_id": room_id,
        "port": port,
        "game_name": game["name"],
        "game_version": game["version"]
    })

def handle_join_room(request):
    """加入遊戲房間"""
    session_id = request.get("session_id")
    username = verify_session(session_id, "players")
    
    if not username:
        return create_response(False, "請先登入")
    
    room_id = request.get("room_id")
    
    if room_id not in rooms:
        return create_response(False, "房間不存在")
    
    room = rooms[room_id]
    
    if room["status"] != "waiting":
        return create_response(False, "遊戲已經開始")
    
    if len(room["players"]) >= room["max_players"]:
        return create_response(False, "房間已滿")
    
    if username in room["players"]:
        return create_response(False, "您已在此房間中")
    
    # 檢查玩家是否已在其他房間
    for rid, r in rooms.items():
        if rid != room_id and username in r["players"]:
            return create_response(False, "您已在其他房間中")
    
    room["players"].append(username)
    
    print(f"[Room] {username} joined room {room_id}")
    
    return create_response(True, "加入房間成功", {
        "room_id": room_id,
        "port": room["port"],
        "game_name": room["game_name"],
        "game_version": room["game_version"],
        "players": room["players"],
        "player_count": len(room["players"]),
        "max_players": room["max_players"]
    })

def handle_leave_room(request):
    """離開遊戲房間"""
    session_id = request.get("session_id")
    username = verify_session(session_id, "players")
    
    if not username:
        return create_response(False, "請先登入")
    
    room_id = request.get("room_id")
    
    if room_id not in rooms:
        return create_response(False, "房間不存在")
    
    room = rooms[room_id]
    
    if username not in room["players"]:
        return create_response(False, "您不在此房間中")
    
    room["players"].remove(username)
    
    # 如果房間空了，刪除房間
    if not room["players"]:
        release_port(room["port"])
        del rooms[room_id]
        print(f"[Room] Room {room_id} deleted (empty)")
    # 如果是房主離開，轉移房主
    elif room["host"] == username:
        room["host"] = room["players"][0]
        print(f"[Room] Host transferred to {room['host']} in room {room_id}")
    
    print(f"[Room] {username} left room {room_id}")
    return create_response(True, "已離開房間")

def handle_send_chat(request):
    """發送聊天訊息"""
    session_id = request.get("session_id")
    username = verify_session(session_id, "players")
    
    if not username:
        return create_response(False, "請先登入")
    
    room_id = request.get("room_id")
    message = request.get("message", "").strip()
    
    if not message:
        return create_response(False, "訊息不能為空")
        
    if room_id not in rooms:
        return create_response(False, "房間不存在")
        
    room = rooms[room_id]
    
    if username not in room["players"]:
        return create_response(False, "您不在此房間中")
        
    chat_entry = {
        "username": username,
        "message": message,
        "time": datetime.now().strftime("%H:%M:%S")
    }
    
    if "chat_history" not in room:
        room["chat_history"] = []
        
    room["chat_history"].append(chat_entry)
    # 保留最近 50 則
    if len(room["chat_history"]) > 50:
        room["chat_history"] = room["chat_history"][-50:]
        
    return create_response(True, "發送成功")

def handle_get_room_chat(request):
    """取得房間聊天紀錄"""
    session_id = request.get("session_id")
    username = verify_session(session_id, "players")
    
    if not username:
        return create_response(False, "請先登入")
        
    room_id = request.get("room_id")
    
    if room_id not in rooms:
        return create_response(False, "房間不存在")
        
    room = rooms[room_id]
    
    # 只有房間內的人可以看到聊天 (或大廳也可以? 這裡限制房間內)
    if username not in room["players"]:
        return create_response(False, "您不在此房間中")
        
    return create_response(True, "查詢成功", {
        "chat_history": room.get("chat_history", [])
    })

def handle_list_rooms(request):
    """列出所有房間"""
    rooms_list = []
    
    for room_id, room in rooms.items():
        rooms_list.append({
            "room_id": room_id,
            "game_id": room["game_id"],
            "game_name": room["game_name"],
            "host": room["host"],
            "players": room["players"],
            "player_count": len(room["players"]),
            "max_players": room["max_players"],
            "status": room["status"],
            "port": room.get("port")
        })
    
    return create_response(True, "查詢成功", {"rooms": rooms_list})

def handle_start_game(request):
    """開始遊戲"""
    session_id = request.get("session_id")
    username = verify_session(session_id, "players")
    
    if not username:
        return create_response(False, "請先登入")
    
    room_id = request.get("room_id")
    
    if room_id not in rooms:
        return create_response(False, "房間不存在")
    
    room = rooms[room_id]
    
    if room["host"] != username:
        return create_response(False, "只有房主可以開始遊戲")
    
    if len(room["players"]) < room["min_players"]:
        return create_response(False, f"人數不足，至少需要 {room['min_players']} 人")
    
    if room["status"] != "waiting":
        return create_response(False, "遊戲已經開始")
    
    # 啟動遊戲伺服器
    db = load_database()
    game = db["games"][room["game_id"]]
    game_dir = os.path.join(game["storage_path"], 'game')
    config_path = os.path.join(game_dir, 'config.json')
    
    if not os.path.exists(config_path):
        return create_response(False, "遊戲配置檔不存在")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        return create_response(False, f"讀取配置檔失敗: {e}")
    
    server_cmd = config.get("server_command")
    
    if server_cmd:
        try:
            # 啟動遊戲 Server
            cmd = server_cmd.copy()
            cmd.extend([
                "--port", str(room["port"]),
                "--lobby-port", str(SERVER_PORT),
                "--room-id", room_id
            ])
            
            process = subprocess.Popen(
                cmd,
                cwd=game_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            game_servers[room_id] = process
            print(f"[Game] Game server started on port {room['port']} for room {room_id}")
        except Exception as e:
            return create_response(False, f"啟動遊戲伺服器失敗: {e}")
    
    room["status"] = "playing"
    print(f"[Room] Room {room_id} status changed to 'playing'")
    
    # 記錄玩家已玩過此遊戲
    for player in room["players"]:
        if player in db["players"]:
            if room["game_id"] not in db["players"][player].get("played_games", []):
                db["players"][player].setdefault("played_games", []).append(room["game_id"])
    save_database(db)
    
    return create_response(True, "遊戲開始", {
        "room_id": room_id,
        "game_id": room["game_id"],
        "port": room["port"],
        "game_name": room["game_name"],
        "players": room["players"],
        "client_command": config.get("client_command", [])
    })

def handle_report_game_result(request):
    """處理遊戲結果回報"""
    # 這裡不驗證 session，因為是 Game Server 呼叫的
    # 但為了安全，應該要驗證來源 IP (必須是 localhost 或信任的 IP)
    # 或是檢查 room_id 對應的 process 是否存在
    
    room_id = request.get("room_id")
    result = request.get("result")
    
    if room_id not in rooms:
        return create_response(False, "房間不存在")
    
    room = rooms[room_id]
    
    # 驗證是否為該房間的 Game Server (簡單驗證：狀態必須是 playing)
    if room["status"] != "playing":
        return create_response(False, "房間不在遊戲中")
    
    # 更新房間狀態
    room["status"] = "waiting"
    print(f"[Game] Game over in room {room_id}. Result: {result}")
    
    # 移除 Game Server Process 記錄 (因為它即將結束)
    if room_id in game_servers:
        # 不用 terminate，因為是它自己回報結束的
        del game_servers[room_id]
    
    # 這裡可以處理戰績更新 (如果 result 包含詳細資訊)
    # ...
    
    return create_response(True, "結果已接收")

def handle_end_game(request):
    """結束遊戲"""
    session_id = request.get("session_id")
    username = verify_session(session_id, "players")
    
    if not username:
        return create_response(False, "請先登入")
    
    room_id = request.get("room_id")
    
    if room_id not in rooms:
        return create_response(False, "房間不存在")
    
    room = rooms[room_id]
    
    # 停止遊戲伺服器
    if room_id in game_servers:
        try:
            game_servers[room_id].terminate()
            game_servers[room_id].wait(timeout=5)
        except:
            game_servers[room_id].kill()
        del game_servers[room_id]
    
    # 釋放 Port 並刪除房間
    release_port(room["port"])
    del rooms[room_id]
    
    print(f"[Game] Game ended in room {room_id}")
    return create_response(True, "遊戲結束")

# ========================= 評分評論 =========================

def handle_add_review(request):
    """新增評論"""
    session_id = request.get("session_id")
    username = verify_session(session_id, "players")
    
    if not username:
        return create_response(False, "請先登入")
    
    game_id = request.get("game_id")
    rating = request.get("rating")
    comment = request.get("comment", "").strip()
    
    db = load_database()
    
    if game_id not in db.get("games", {}):
        return create_response(False, "遊戲不存在")
    
    # 檢查是否玩過
    player = db["players"].get(username, {})
    if game_id not in player.get("played_games", []):
        return create_response(False, "您尚未玩過此遊戲，無法評分")
    
    # 驗證評分
    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            raise ValueError()
    except:
        return create_response(False, "評分必須是 1-5 的整數")
    
    # 檢查評論長度
    if len(comment) > 500:
        return create_response(False, "評論不可超過 500 字")
    
    # 建立評論
    if "reviews" not in db:
        db["reviews"] = {}
    if game_id not in db["reviews"]:
        db["reviews"][game_id] = []
    
    # 檢查是否已評論過（可選擇允許或不允許重複評論）
    for review in db["reviews"][game_id]:
        if review["username"] == username:
            return create_response(False, "您已經評論過此遊戲")
    
    db["reviews"][game_id].append({
        "username": username,
        "rating": rating,
        "comment": comment,
        "created_at": datetime.now().isoformat()
    })
    
    save_database(db)
    
    print(f"[Review] {username} reviewed {game_id} with rating {rating}")
    return create_response(True, "評論成功")

def handle_get_player_profile(request):
    """取得玩家個人資料（包含遊玩紀錄）"""
    session_id = request.get("session_id")
    username = verify_session(session_id, "players")
    
    if not username:
        return create_response(False, "請先登入")
    
    db = load_database()
    player = db["players"].get(username, {})
    
    played_game_ids = player.get("played_games", [])
    played_games_details = []
    
    for gid in played_game_ids:
        if gid in db["games"]:
            game = db["games"][gid]
            played_games_details.append({
                "game_id": gid,
                "name": game["name"],
                "version": game["version"]
            })
            
    return create_response(True, "查詢成功", {
        "username": username,
        "played_games": played_games_details
    })

# ========================= 大廳資訊 =========================

def handle_get_lobby_info(request):
    """取得大廳狀態資訊"""
    session_id = request.get("session_id")
    username = verify_session(session_id, "players")
    
    # 線上玩家
    online_players = []
    for sid, session in active_sessions.items():
        if session["type"] == "players":
            online_players.append(session["username"])
    
    # 房間列表
    rooms_list = []
    for room_id, room in rooms.items():
        rooms_list.append({
            "room_id": room_id,
            "game_name": room["game_name"],
            "host": room["host"],
            "player_count": len(room["players"]),
            "max_players": room["max_players"],
            "status": room["status"]
        })
    
    # 遊戲數量
    db = load_database()
    active_games = sum(1 for g in db.get("games", {}).values() if g["status"] == "active")
    
    return create_response(True, "查詢成功", {
        "online_players": online_players,
        "online_count": len(online_players),
        "rooms": rooms_list,
        "room_count": len(rooms_list),
        "active_games": active_games
    })

def handle_list_plugins(request):
    """列出所有 Plugin"""
    session_id = request.get("session_id")
    if not verify_session(session_id, "players"):
        return create_response(False, "未登入或 Session 無效")
        
    db = load_database()
    plugins = db.get("plugins", {})
    
    return create_response(True, "查詢成功", plugins)

def handle_download_plugin(request, client_socket):
    """下載 Plugin"""
    session_id = request.get("session_id")
    plugin_id = request.get("plugin_id")
    
    if not verify_session(session_id, "players"):
        send_json(client_socket, create_response(False, "未登入或 Session 無效"))
        return

    db = load_database()
    plugins = db.get("plugins", {})
    
    if plugin_id not in plugins:
        send_json(client_socket, create_response(False, "Plugin 不存在"))
        return
        
    plugin_info = plugins[plugin_id]
    filename = plugin_info.get("filename")
    file_path = os.path.join(STORAGE_DIR, "plugins", filename)
    
    if not os.path.exists(file_path):
        send_json(client_socket, create_response(False, "Plugin 檔案遺失"))
        return
        
    # 傳送檔案
    try:
        send_file(client_socket, file_path)
        print(f"[Download] Plugin {plugin_id} sent to client")
    except Exception as e:
        print(f"[Error] Failed to send plugin: {e}")

# ========================= Client 處理 =========================

def handle_client(client_socket, client_address):
    """處理單一 Client 連線"""
    print(f"[Connect] New connection from {client_address}")
    
    current_session = None
    
    try:
        while True:
            request = recv_json(client_socket)
            
            if not request:
                break
            
            action = request.get("action", "")
            client_type = request.get("client_type", "")
            
            response = None
            
            # ===== 開發者操作 =====
            if client_type == "developer":
                if action == "REGISTER":
                    response = handle_register(request, "developers")
                elif action == "LOGIN":
                    response = handle_login(request, "developers", client_socket)
                    if response.get("success"):
                        current_session = response["data"]["session_id"]
                elif action == "LOGOUT":
                    response = handle_logout(request, "developers")
                    current_session = None
                elif action == "UPLOAD_GAME":
                    response = handle_upload_game(request, client_socket)
                elif action == "UPDATE_GAME":
                    response = handle_update_game(request, client_socket)
                elif action == "UNPUBLISH_GAME":
                    response = handle_unpublish_game(request)
                elif action == "LIST_MY_GAMES":
                    response = handle_list_my_games(request)
                else:
                    response = create_response(False, "未知的操作")
            
            # ===== 玩家操作 =====
            elif client_type == "player":
                if action == "REGISTER":
                    response = handle_register(request, "players")
                elif action == "LOGIN":
                    response = handle_login(request, "players", client_socket)
                    if response.get("success"):
                        current_session = response["data"]["session_id"]
                elif action == "LOGOUT":
                    response = handle_logout(request, "players")
                    current_session = None
                elif action == "LIST_GAMES":
                    response = handle_list_games(request)
                elif action == "GET_GAME_DETAIL":
                    response = handle_get_game_detail(request)
                elif action == "DOWNLOAD_GAME":
                    handle_download_game(request, client_socket)
                    continue  # 回應已在函式內處理
                elif action == "CREATE_ROOM":
                    response = handle_create_room(request)
                elif action == "JOIN_ROOM":
                    response = handle_join_room(request)
                elif action == "SEND_CHAT":
                    response = handle_send_chat(request)
                elif action == "GET_ROOM_CHAT":
                    response = handle_get_room_chat(request)
                elif action == "LEAVE_ROOM":
                    response = handle_leave_room(request)
                elif action == "LIST_ROOMS":
                    response = handle_list_rooms(request)
                elif action == "START_GAME":
                    response = handle_start_game(request)
                elif action == "REPORT_GAME_RESULT":
                    response = handle_report_game_result(request)
                elif action == "END_GAME":
                    response = handle_end_game(request)
                elif action == "ADD_REVIEW":
                    response = handle_add_review(request)
                elif action == "GET_PLAYER_PROFILE":
                    response = handle_get_player_profile(request)
                elif action == "GET_LOBBY_INFO":
                    response = handle_get_lobby_info(request)
                elif action == "LIST_PLUGINS":
                    response = handle_list_plugins(request)
                elif action == "DOWNLOAD_PLUGIN":
                    handle_download_plugin(request, client_socket)
                    continue
                else:
                    response = create_response(False, "未知的操作")
            
            else:
                response = create_response(False, "請指定 client_type (developer/player)")
            
            if response:
                send_json(client_socket, response)
    
    except Exception as e:
        print(f"[Error] Error handling client {client_address}: {e}")
    
    finally:
        # 清理 Session
        if current_session and current_session in active_sessions:
            username = active_sessions[current_session]["username"]
            user_type = active_sessions[current_session]["type"]
            del active_sessions[current_session]
            
            db = load_database()
            if username in db.get(user_type, {}):
                db[user_type][username]["session_id"] = None
                save_database(db)
        
        client_socket.close()
        print(f"[Disconnect] Connection closed: {client_address}")

# ========================= 主程式 =========================

def main():
    """啟動 Server"""
    # 確保儲存目錄存在
    os.makedirs(STORAGE_DIR, exist_ok=True)
    
    # 初始化資料庫（如果不存在）
    if not os.path.exists(DATABASE_FILE):
        save_database({
            "developers": {},
            "players": {},
            "games": {},
            "reviews": {},
            "rooms": {}
        })
    
    # 建立 Server Socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind((SERVER_HOST, SERVER_PORT))
        server_socket.listen(10)
        print(f"=" * 50)
        print(f"  Game Store Server 啟動")
        print(f"  監聽位址: {SERVER_HOST}:{SERVER_PORT}")
        print(f"=" * 50)
        
        while True:
            client_socket, client_address = server_socket.accept()
            client_thread = threading.Thread(
                target=handle_client,
                args=(client_socket, client_address)
            )
            client_thread.daemon = True
            client_thread.start()
    
    except KeyboardInterrupt:
        print("\n[Server] 正在關閉...")
    finally:
        # 清理所有遊戲伺服器
        for room_id, process in game_servers.items():
            try:
                process.terminate()
            except:
                pass
        server_socket.close()
        print("[Server] 已關閉")

if __name__ == "__main__":
    main()
