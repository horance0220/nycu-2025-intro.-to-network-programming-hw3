#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
遊戲伺服器端範本
此檔案用於處理多個客戶端連線與遊戲邏輯
"""

import socket
import threading
import json
import argparse

# 遊戲狀態
game_state = {
    "players": [],
    "current_turn": 0,
    "board": None,
    "status": "waiting"
}

clients = []
lock = threading.Lock()

def broadcast(message):
    """廣播訊息給所有客戶端"""
    data = json.dumps(message).encode('utf-8')
    with lock:
        for client in clients:
            try:
                client.sendall(len(data).to_bytes(4, 'big') + data)
            except:
                pass

def handle_client(client_socket, player_id):
    """處理單一客戶端"""
    global game_state
    
    try:
        while True:
            # 接收訊息
            header = client_socket.recv(4)
            if not header:
                break
            
            msg_len = int.from_bytes(header, 'big')
            data = client_socket.recv(msg_len)
            message = json.loads(data.decode('utf-8'))
            
            action = message.get("action")
            
            if action == "MOVE":
                # 處理玩家移動
                # 在此實作遊戲邏輯
                pass
            
            elif action == "QUIT":
                break
    
    except Exception as e:
        print(f"[Error] Player {player_id}: {e}")
    
    finally:
        with lock:
            if client_socket in clients:
                clients.remove(client_socket)
        client_socket.close()
        print(f"[Disconnect] Player {player_id}")

def report_result(lobby_host, lobby_port, room_id, result):
    """回報遊戲結果給 Lobby Server"""
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
        
        # 接收回應 (可選)
        header = sock.recv(4)
        if header:
            length = int.from_bytes(header, 'big')
            resp_data = sock.recv(length)
            print(f"[Report] Lobby response: {resp_data.decode('utf-8')}")
            
        sock.close()
    except Exception as e:
        print(f"[Error] Failed to report result: {e}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=9000)
    parser.add_argument('--host', type=str, default='0.0.0.0')
    parser.add_argument('--lobby-port', type=int, help="Lobby Server Port")
    parser.add_argument('--room-id', type=str, help="Room ID")
    args = parser.parse_args()
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.host, args.port))
    server.listen(5)
    
    print(f"[Server] 遊戲伺服器啟動於 {args.host}:{args.port}")
    
    player_count = 0
    
    while True:
        client_socket, addr = server.accept()
        player_count += 1
        
        with lock:
            clients.append(client_socket)
        
        print(f"[Connect] Player {player_count} from {addr}")
        
        thread = threading.Thread(
            target=handle_client,
            args=(client_socket, player_count)
        )
        thread.daemon = True
        thread.start()

if __name__ == "__main__":
    main()
