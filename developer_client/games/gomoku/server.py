#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
五子棋遊戲伺服器
處理兩位玩家的連線與遊戲邏輯
"""

import socket
import threading
import json
import argparse

# 棋盤大小
BOARD_SIZE = 15

# 遊戲狀態
class GameState:
    def __init__(self):
        self.board = [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        self.current_player = 1  # 1 = 黑子, 2 = 白子
        self.players = {}  # socket -> player_id
        self.player_sockets = {}  # player_id -> socket
        self.winner = None
        self.game_started = False

game = GameState()
lock = threading.Lock()

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
        for pid, sock in game.player_sockets.items():
            if sock != exclude:
                send_to_client(sock, message)

def check_winner(row, col, player):
    """檢查是否有人獲勝"""
    directions = [
        (0, 1),   # 水平
        (1, 0),   # 垂直
        (1, 1),   # 右下對角
        (1, -1)   # 左下對角
    ]
    
    for dr, dc in directions:
        count = 1
        
        # 正向檢查
        r, c = row + dr, col + dc
        while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and game.board[r][c] == player:
            count += 1
            r += dr
            c += dc
        
        # 反向檢查
        r, c = row - dr, col - dc
        while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and game.board[r][c] == player:
            count += 1
            r -= dr
            c -= dc
        
        if count >= 5:
            return True
    
    return False

def handle_client(client_socket, player_id):
    """處理單一客戶端"""
    print(f"[Server] 玩家 {player_id} 已連線")
    
    with lock:
        game.players[client_socket] = player_id
        game.player_sockets[player_id] = client_socket
    
    # 發送玩家 ID
    send_to_client(client_socket, {
        "type": "PLAYER_ID",
        "player_id": player_id,
        "color": "黑子" if player_id == 1 else "白子"
    })
    
    # 等待另一位玩家
    with lock:
        player_count = len(game.players)
    
    if player_count < 2:
        send_to_client(client_socket, {
            "type": "WAITING",
            "message": "等待另一位玩家加入..."
        })
    
    # 如果兩位玩家都連線，開始遊戲
    if player_count == 2:
        with lock:
            game.game_started = True
        
        broadcast({
            "type": "GAME_START",
            "message": "遊戲開始！黑子先行"
        })
        
        broadcast({
            "type": "TURN",
            "current_player": 1,
            "message": "輪到黑子下棋"
        })
    
    try:
        while True:
            # 接收訊息
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
                row = message.get("row")
                col = message.get("col")
                
                with lock:
                    # 檢查是否輪到此玩家
                    if game.current_player != player_id:
                        send_to_client(client_socket, {
                            "type": "ERROR",
                            "message": "還沒輪到你！"
                        })
                        continue
                    
                    # 檢查位置是否合法
                    if not (0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE):
                        send_to_client(client_socket, {
                            "type": "ERROR",
                            "message": "位置超出範圍！"
                        })
                        continue
                    
                    if game.board[row][col] != 0:
                        send_to_client(client_socket, {
                            "type": "ERROR",
                            "message": "此位置已有棋子！"
                        })
                        continue
                    
                    # 落子
                    game.board[row][col] = player_id
                    
                    # 廣播更新
                    broadcast({
                        "type": "MOVE",
                        "row": row,
                        "col": col,
                        "player": player_id
                    })
                    
                    # 檢查獲勝
                    if check_winner(row, col, player_id):
                        game.winner = player_id
                        broadcast({
                            "type": "GAME_OVER",
                            "winner": player_id,
                            "message": f"{'黑子' if player_id == 1 else '白子'}獲勝！"
                        })
                        continue
                    
                    # 檢查平手
                    is_draw = all(
                        game.board[r][c] != 0 
                        for r in range(BOARD_SIZE) 
                        for c in range(BOARD_SIZE)
                    )
                    if is_draw:
                        game.winner = 0  # 0 表示平手
                        broadcast({
                            "type": "GAME_OVER",
                            "winner": 0,
                            "message": "平手！"
                        })
                        continue
                    
                    # 切換玩家
                    game.current_player = 2 if player_id == 1 else 1
                    
                    broadcast({
                        "type": "TURN",
                        "current_player": game.current_player,
                        "message": f"輪到{'黑子' if game.current_player == 1 else '白子'}下棋"
                    })
            
            elif action == "CHAT":
                broadcast({
                    "type": "CHAT",
                    "player": player_id,
                    "message": message.get("message", "")
                })
            
            elif action == "QUIT":
                break
    
    except Exception as e:
        print(f"[Error] 玩家 {player_id}: {e}")
    
    finally:
        with lock:
            if client_socket in game.players:
                del game.players[client_socket]
            if player_id in game.player_sockets:
                del game.player_sockets[player_id]
        
        client_socket.close()
        print(f"[Server] 玩家 {player_id} 已離線")
        
        # 通知另一位玩家
        broadcast({
            "type": "PLAYER_LEFT",
            "player": player_id,
            "message": f"玩家 {player_id} 已離線"
        })

def main():
    parser = argparse.ArgumentParser(description='五子棋遊戲伺服器')
    parser.add_argument('--port', type=int, default=9000, help='監聽埠號')
    parser.add_argument('--host', type=str, default='140.113.17.11', help='監聽位址')
    parser.add_argument('--lobby-port', type=int, help="Lobby Server Port")
    parser.add_argument('--room-id', type=str, help="Room ID")
    args = parser.parse_args()
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind((args.host, args.port))
        server.listen(2)
        print(f"[Server] 五子棋伺服器啟動於 {args.host}:{args.port}")
        print("[Server] 等待玩家連線...")
        
        player_count = 0
        
        while player_count < 2:
            client_socket, addr = server.accept()
            player_count += 1
            
            thread = threading.Thread(
                target=handle_client,
                args=(client_socket, player_count)
            )
            thread.daemon = True
            thread.start()
        
        # 保持伺服器運行
        while True:
            with lock:
                if len(game.players) == 0:
                    print("[Server] 所有玩家已離線，伺服器關閉")
                    break
                if game.winner is not None:
                    # 回報結果
                    if args.lobby_port and args.room_id:
                        result = {
                            "winner": game.winner,
                            "reason": "normal_end"
                        }
                        report_result(args.host, args.lobby_port, args.room_id, result)
                    
                    # 給一點時間讓訊息傳送完畢
                    import time
                    time.sleep(2)
                    break
            import time
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n[Server] 伺服器關閉")
    finally:
        server.close()

if __name__ == "__main__":
    main()
