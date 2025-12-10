#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
遊戲客戶端範本
此檔案用於連線到遊戲伺服器並顯示遊戲介面
"""

import socket
import threading
import json
import argparse

# 全域變數
sock = None
running = True

def send_message(message):
    """發送訊息到伺服器"""
    global sock
    try:
        data = json.dumps(message).encode('utf-8')
        sock.sendall(len(data).to_bytes(4, 'big') + data)
        return True
    except:
        return False

def receive_messages():
    """接收伺服器訊息的執行緒"""
    global sock, running
    
    while running:
        try:
            header = sock.recv(4)
            if not header:
                break
            
            msg_len = int.from_bytes(header, 'big')
            data = sock.recv(msg_len)
            message = json.loads(data.decode('utf-8'))
            
            # 處理伺服器訊息
            handle_server_message(message)
        
        except Exception as e:
            if running:
                print(f"[Error] {e}")
            break
    
    running = False

def handle_server_message(message):
    """處理伺服器訊息"""
    msg_type = message.get("type")
    
    if msg_type == "GAME_STATE":
        # 更新遊戲狀態
        pass
    elif msg_type == "TURN":
        # 輪到你了
        pass
    elif msg_type == "GAME_OVER":
        # 遊戲結束
        pass

def main():
    global sock, running
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=str, default='127.0.0.1')
    parser.add_argument('--port', type=int, default=9000)
    args = parser.parse_args()
    
    # 連線到伺服器
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        sock.connect((args.host, args.port))
        print(f"[Connected] 已連線到 {args.host}:{args.port}")
    except Exception as e:
        print(f"[Error] 無法連線: {e}")
        return
    
    # 啟動接收執行緒
    recv_thread = threading.Thread(target=receive_messages)
    recv_thread.daemon = True
    recv_thread.start()
    
    # 主遊戲迴圈
    print("遊戲開始！輸入 'quit' 離開")
    
    while running:
        try:
            cmd = input("> ").strip()
            
            if cmd == 'quit':
                send_message({"action": "QUIT"})
                break
            
            # 在此處理玩家輸入
            # send_message({"action": "MOVE", "data": cmd})
        
        except (EOFError, KeyboardInterrupt):
            break
    
    running = False
    sock.close()
    print("已離開遊戲")

if __name__ == "__main__":
    main()
