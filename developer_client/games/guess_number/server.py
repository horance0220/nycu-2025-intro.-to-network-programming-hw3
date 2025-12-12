#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
猜數字遊戲伺服器
支援 2-6 位玩家同時遊玩
"""

import socket
import threading
import json
import argparse
import random
import time

class GameState:
    def __init__(self):
        self.target = random.randint(1, 100)
        self.min_range = 1
        self.max_range = 100
        self.players = {}  # socket -> player_info
        self.player_order = []  # 玩家順序
        self.current_index = 0
        self.game_started = False
        self.winner = None
        self.min_players = 2
        self.max_players = 6

game = GameState()
lock = threading.Lock()
server_socket = None

def report_result(lobby_host, lobby_port, room_id, result):
    """回報遊戲結果給 Lobby Server"""
    if not lobby_port or not room_id:
        return
        
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((lobby_host, lobby_port))
        
        request = {
            "action": "REPORT_GAME_RESULT",
            "room_id": room_id,
            "result": result
        }
        
        data = json.dumps(request).encode('utf-8')
        sock.sendall(len(data).to_bytes(4, 'big') + data)
        sock.close()
        print(f"[Report] Result sent to lobby: {result}")
    except Exception as e:
        print(f"[Error] Failed to report result: {e}")

def send_to_client(client_socket, message):
    """發送訊息給客戶端"""
    try:
        data = json.dumps(message, ensure_ascii=False).encode('utf-8')
        client_socket.sendall(len(data).to_bytes(4, 'big') + data)
        return True
    except:
        return False

def broadcast(message, exclude=None):
    """廣播訊息給所有玩家"""
    with lock:
        for sock in game.players.keys():
            if sock != exclude:
                send_to_client(sock, message)

def get_current_player_socket():
    """取得當前玩家的 socket"""
    with lock:
        if game.player_order:
            return game.player_order[game.current_index]
    return None

def start_game():
    """開始遊戲"""
    with lock:
        game.game_started = True
        game.target = random.randint(1, 100)
        game.min_range = 1
        game.max_range = 100
        game.current_index = 0
        
        print(f"[Server] 遊戲開始！答案是: {game.target}")
    
    broadcast({
        "type": "GAME_START",
        "message": "遊戲開始！猜一個 1-100 的數字",
        "range": {"min": 1, "max": 100},
        "player_count": len(game.players)
    })
    
    notify_turn()

def notify_turn():
    """通知輪到誰"""
    current_sock = get_current_player_socket()
    if current_sock:
        with lock:
            current_player = game.players[current_sock]["name"]
            range_min = game.min_range
            range_max = game.max_range
        
        broadcast({
            "type": "TURN",
            "current_player": current_player,
            "range": {"min": range_min, "max": range_max}
        })

def handle_client(client_socket, player_name):
    """處理單一客戶端"""
    print(f"[Server] {player_name} 已連線")
    
    with lock:
        game.players[client_socket] = {"name": player_name}
        game.player_order.append(client_socket)
        player_count = len(game.players)
    
    # 發送玩家資訊
    send_to_client(client_socket, {
        "type": "JOINED",
        "player_name": player_name,
        "player_count": player_count,
        "min_players": game.min_players
    })
    
    # 通知其他玩家
    broadcast({
        "type": "PLAYER_JOINED",
        "player_name": player_name,
        "player_count": player_count
    }, exclude=client_socket)
    
    # 如果人數足夠且未開始，倒數開始
    if player_count >= game.min_players and not game.game_started:
        broadcast({
            "type": "COUNTDOWN",
            "message": "人數足夠！5 秒後開始遊戲...",
            "seconds": 5
        })
        
        # 等待更多玩家或開始
        def countdown_and_start():
            time.sleep(5)
            with lock:
                if not game.game_started and len(game.players) >= game.min_players:
                    pass
                else:
                    return
            start_game()
        
        threading.Thread(target=countdown_and_start, daemon=True).start()
    
    try:
        while True:
            header = client_socket.recv(4)
            if not header:
                break
            
            msg_len = int.from_bytes(header, 'big')
            data = b''
            while len(data) < msg_len:
                chunk = client_socket.recv(msg_len - len(data))
                if not chunk:
                    break
                data += chunk
            
            if len(data) < msg_len:
                break
            
            message = json.loads(data.decode('utf-8'))
            action = message.get("action")
            
            if action == "GUESS":
                guess = message.get("number")
                
                with lock:
                    # 檢查是否輪到此玩家
                    current_sock = game.player_order[game.current_index]
                    if client_socket != current_sock:
                        send_to_client(client_socket, {
                            "type": "ERROR",
                            "message": "還沒輪到你！"
                        })
                        continue
                    
                    # 檢查數字範圍
                    if not (game.min_range <= guess <= game.max_range):
                        send_to_client(client_socket, {
                            "type": "ERROR",
                            "message": f"請猜 {game.min_range} 到 {game.max_range} 之間的數字！"
                        })
                        continue
                    
                    result = None
                    if guess == game.target:
                        result = "correct"
                        game.winner = player_name
                    elif guess < game.target:
                        result = "higher"
                        game.min_range = guess + 1
                    else:
                        result = "lower"
                        game.max_range = guess - 1
                
                # 廣播猜測結果
                broadcast({
                    "type": "GUESS_RESULT",
                    "player": player_name,
                    "guess": guess,
                    "result": result,
                    "range": {"min": game.min_range, "max": game.max_range}
                })
                
                if result == "correct":
                    broadcast({
                        "type": "GAME_OVER",
                        "winner": player_name,
                        "answer": game.target,
                        "message": f"🎉 {player_name} 猜中了！答案是 {game.target}"
                    })
                    break
                
                # 下一位玩家
                with lock:
                    game.current_index = (game.current_index + 1) % len(game.player_order)
                
                notify_turn()
            
            elif action == "CHAT":
                broadcast({
                    "type": "CHAT",
                    "player": player_name,
                    "message": message.get("message", "")
                })
            
            elif action == "QUIT":
                break
    
    except Exception as e:
        print(f"[Error] {player_name}: {e}")
    
    finally:
        with lock:
            if client_socket in game.players:
                del game.players[client_socket]
            if client_socket in game.player_order:
                idx = game.player_order.index(client_socket)
                game.player_order.remove(client_socket)
                if game.current_index >= len(game.player_order) and game.player_order:
                    game.current_index = 0
                elif idx < game.current_index:
                    game.current_index -= 1
        
        client_socket.close()
        print(f"[Server] {player_name} 已離線")
        
        broadcast({
            "type": "PLAYER_LEFT",
            "player_name": player_name,
            "player_count": len(game.players)
        })

def main():
    global server_socket
    
    parser = argparse.ArgumentParser(description='猜數字遊戲伺服器')
    parser.add_argument('--port', type=int, default=9000, help='監聽埠號')
    parser.add_argument('--host', type=str, default='140.113.17.11', help='監聽位址')
    parser.add_argument('--lobby-port', type=int, help="Lobby Server Port")
    parser.add_argument('--room-id', type=str, help="Room ID")
    args = parser.parse_args()
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind((args.host, args.port))
        server_socket.listen(6)
        print(f"[Server] 猜數字伺服器啟動於 {args.host}:{args.port}")
        print("[Server] 等待玩家連線...")
        
        player_count = 0
        
        while True:
            # 檢查是否遊戲已結束
            with lock:
                if game.winner is not None:
                    # 回報結果
                    if args.lobby_port and args.room_id:
                        result = {
                            "winner": game.winner,
                            "reason": "normal_end"
                        }
                        report_result(args.host, args.lobby_port, args.room_id, result)
                    
                    time.sleep(3)
                    break
                if game.game_started and len(game.players) == 0:
                    break
            
            # 設定接受連線的超時
            server_socket.settimeout(1.0)
            try:
                client_socket, addr = server_socket.accept()
                
                with lock:
                    if len(game.players) >= game.max_players:
                        send_to_client(client_socket, {
                            "type": "FULL",
                            "message": "遊戲人數已滿"
                        })
                        client_socket.close()
                        continue
                    
                    if game.game_started:
                        send_to_client(client_socket, {
                            "type": "STARTED",
                            "message": "遊戲已經開始"
                        })
                        client_socket.close()
                        continue
                
                player_count += 1
                player_name = f"玩家{player_count}"
                
                thread = threading.Thread(
                    target=handle_client,
                    args=(client_socket, player_name)
                )
                thread.daemon = True
                thread.start()
            
            except socket.timeout:
                continue
    
    except KeyboardInterrupt:
        print("\n[Server] 伺服器關閉")
    finally:
        server_socket.close()

if __name__ == "__main__":
    main()
