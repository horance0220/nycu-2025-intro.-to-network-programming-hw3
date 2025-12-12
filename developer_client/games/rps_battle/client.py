#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
剪刀石頭布大戰 - Client
"""

import socket
import json
import argparse
import sys
import threading

class RPSClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = None
        self.running = True
        self.my_turn = False
        
    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            print(f"已連線到 {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"連線失敗: {e}")
            return False

    def send_json(self, data):
        try:
            msg = json.dumps(data).encode('utf-8')
            self.sock.sendall(len(msg).to_bytes(4, 'big') + msg)
        except:
            pass

    def receive_loop(self):
        try:
            while self.running:
                header = self.sock.recv(4)
                if not header:
                    break
                msg_len = int.from_bytes(header, 'big')
                data = self.sock.recv(msg_len)
                message = json.loads(data.decode('utf-8'))
                
                msg_type = message.get("type")
                
                if msg_type == "GAME_START":
                    print("\n" + "="*30)
                    print(f" {message['message']}")
                    print("="*30)
                    self.my_turn = True
                    self.print_prompt()
                    
                elif msg_type == "NEW_ROUND":
                    print(f"\n--- 第 {message['round']} 回合 ---")
                    self.my_turn = True
                    self.print_prompt()
                    
                elif msg_type == "WAITING":
                    print(f"\n[系統] {message['message']}")
                    
                elif msg_type == "ROUND_RESULT":
                    print("\n" + "-"*30)
                    print(f"第 {message['round']} 回合結果:")
                    print(f"Player 1: {self.get_move_name(message['p1_move'])}")
                    print(f"Player 2: {self.get_move_name(message['p2_move'])}")
                    print(f"結果: {message['result']}")
                    print(f"目前比分: {message['scores']}")
                    print("-"*30)
                    
                elif msg_type == "GAME_OVER":
                    print("\n" + "="*30)
                    print(f"遊戲結束！")
                    print(f"{message['message']}")
                    print("="*30)
                    self.running = False
                    print("\n請按 Enter 離開...")
                    
        except Exception as e:
            if self.running:
                print(f"\n連線中斷: {e}")
            self.running = False

    def get_move_name(self, move):
        mapping = {'R': '石頭 (Rock)', 'P': '布 (Paper)', 'S': '剪刀 (Scissors)'}
        return mapping.get(move, move)

    def print_prompt(self):
        print("\n請出拳 (R:石頭, P:布, S:剪刀, Q:離開): ", end='', flush=True)

    def run(self):
        if not self.connect():
            return

        # 啟動接收執行緒
        recv_thread = threading.Thread(target=self.receive_loop, daemon=True)
        recv_thread.start()

        print("等待對手連線中...")

        try:
            while self.running:
                if self.my_turn:
                    # 這裡使用 input 會阻塞，但因為是 CLI 簡單實作，
                    # 我們假設玩家會乖乖輸入。
                    # 為了避免 input 卡住接收執行緒的輸出，
                    # 實際的 CLI 遊戲通常需要更複雜的 UI 庫 (如 curses)，
                    # 但這裡我們用簡單的方式：
                    # 只有輪到自己時才 input
                    
                    choice = input().strip().upper()
                    
                    if not self.running: break
                    
                    if choice in ['R', 'P', 'S']:
                        self.send_json({"action": "MOVE", "move": choice})
                        self.my_turn = False # 等待結果
                    elif choice == 'Q':
                        self.send_json({"action": "QUIT"})
                        self.running = False
                        break
                    else:
                        print("無效輸入，請輸入 R, P, 或 S")
                        self.print_prompt()
                else:
                    # 簡單的 sleep 避免 CPU 滿載
                    import time
                    time.sleep(0.1)
                    
        except KeyboardInterrupt:
            self.running = False
        finally:
            if self.sock:
                self.sock.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=9000)
    args = parser.parse_args()
    
    client = RPSClient(args.host, args.port)
    client.run()
