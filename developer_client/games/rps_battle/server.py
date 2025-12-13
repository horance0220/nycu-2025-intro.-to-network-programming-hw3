#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
剪刀石頭布大戰 - Server
"""

import socket
import threading
import json
import argparse
import time

# 遊戲設定
WIN_COUNT = 3  # 搶 3 勝

class GameState:
    def __init__(self):
        self.players = {}  # socket -> {"name": str, "score": int, "move": str|None}
        self.player_sockets = [] # list of sockets to maintain order
        self.round = 1
        self.game_over = False
        self.winner = None

game = GameState()
lock = threading.RLock()

def send_json(sock, data):
    try:
        msg = json.dumps(data, ensure_ascii=False).encode('utf-8')
        sock.sendall(len(msg).to_bytes(4, 'big') + msg)
        return True
    except:
        return False

def broadcast(data):
    with lock:
        for sock in game.player_sockets:
            send_json(sock, data)

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

def determine_round_winner(move1, move2):
    # R: Rock, P: Paper, S: Scissors
    if move1 == move2:
        return 0 # Tie
    
    if (move1 == 'R' and move2 == 'S') or \
       (move1 == 'P' and move2 == 'R') or \
       (move1 == 'S' and move2 == 'P'):
        return 1 # Player 1 wins
    else:
        return 2 # Player 2 wins

def check_game_over():
    p1_sock = game.player_sockets[0]
    p2_sock = game.player_sockets[1]
    p1_score = game.players[p1_sock]["score"]
    p2_score = game.players[p2_sock]["score"]
    
    if p1_score >= WIN_COUNT:
        return game.players[p1_sock]["name"]
    elif p2_score >= WIN_COUNT:
        return game.players[p2_sock]["name"]
    return None

def process_round():
    """處理回合結算"""
    with lock:
        p1_sock = game.player_sockets[0]
        p2_sock = game.player_sockets[1]
        
        p1_move = game.players[p1_sock]["move"]
        p2_move = game.players[p2_sock]["move"]
        
        p1_name = game.players[p1_sock]["name"]
        p2_name = game.players[p2_sock]["name"]
        
        winner_idx = determine_round_winner(p1_move, p2_move)
        
        round_result = "平手"
        if winner_idx == 1:
            game.players[p1_sock]["score"] += 1
            round_result = f"{p1_name} 獲勝"
        elif winner_idx == 2:
            game.players[p2_sock]["score"] += 1
            round_result = f"{p2_name} 獲勝"
            
        # 廣播回合結果
        broadcast({
            "type": "ROUND_RESULT",
            "round": game.round,
            "p1_name": p1_name,
            "p2_name": p2_name,
            "p1_move": p1_move,
            "p2_move": p2_move,
            "result": round_result,
            "scores": {
                p1_name: game.players[p1_sock]["score"],
                p2_name: game.players[p2_sock]["score"]
            }
        })
        
        # 檢查遊戲結束
        game_winner = check_game_over()
        if game_winner:
            game.game_over = True
            game.winner = game_winner
            broadcast({
                "type": "GAME_OVER",
                "winner": game_winner,
                "message": f"恭喜 {game_winner} 獲得最終勝利！"
            })
        else:
            # 準備下一回合
            game.round += 1
            game.players[p1_sock]["move"] = None
            game.players[p2_sock]["move"] = None
            broadcast({
                "type": "NEW_ROUND",
                "round": game.round
            })

def handle_client(client_socket, player_name):
    print(f"[Server] {player_name} 已連線")
    
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
            
            if action == "MOVE":
                move = message.get("move") # R, P, S
                if move not in ['R', 'P', 'S']:
                    continue
                
                ready_to_process = False
                with lock:
                    if game.players[client_socket]["move"] is None:
                        game.players[client_socket]["move"] = move
                        send_json(client_socket, {"type": "WAITING", "message": "已出拳，等待對手..."})
                        
                        # 檢查是否雙方都出拳了
                        p1 = game.player_sockets[0]
                        p2 = game.player_sockets[1]
                        if game.players[p1]["move"] and game.players[p2]["move"]:
                            ready_to_process = True
                
                if ready_to_process:
                    process_round()
                    if game.game_over:
                        break
            
            elif action == "QUIT":
                break
                
    except Exception as e:
        print(f"[Error] {player_name}: {e}")
    finally:
        client_socket.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=9000)
    parser.add_argument('--host', type=str, default='140.113.17.11')
    parser.add_argument('--lobby-port', type=int, help="Lobby Server Port")
    parser.add_argument('--room-id', type=str, help="Room ID")
    args = parser.parse_args()
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind((args.host, args.port))
        server.listen(2)
        print(f"[Server] RPS Battle 啟動於 {args.host}:{args.port}")
        
        # 等待兩位玩家
        while len(game.player_sockets) < 2:
            client, addr = server.accept()
            
            with lock:
                player_name = f"Player{len(game.player_sockets)+1}"
                game.players[client] = {"name": player_name, "score": 0, "move": None}
                game.player_sockets.append(client)
                
                if len(game.player_sockets) == 2:
                    broadcast({
                        "type": "GAME_START",
                        "message": f"遊戲開始！搶 {WIN_COUNT} 勝",
                        "round": game.round
                    })
            
            threading.Thread(target=handle_client, args=(client, player_name), daemon=True).start()
            
        # 等待遊戲結束
        while not game.game_over:
            # 檢查連線狀態
            with lock:
                if len(game.player_sockets) < 2:
                    print("玩家斷線，遊戲終止")
                    break
            time.sleep(1)
            
        if game.winner and args.lobby_port and args.room_id:
            report_result(args.host, args.lobby_port, args.room_id, {
                "winner": game.winner,
                "reason": "normal_end"
            })
            time.sleep(2) # 等待回報完成
            
    except Exception as e:
        print(f"[Error] Server error: {e}")
    finally:
        server.close()

if __name__ == "__main__":
    main()
