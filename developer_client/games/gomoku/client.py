#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
五子棋遊戲客戶端 (GUI 版本)
使用 tkinter 實現圖形介面
"""

import socket
import threading
import json
import argparse
import tkinter as tk
from tkinter import messagebox, scrolledtext
import sys
import os

# 棋盤大小
BOARD_SIZE = 15
CELL_SIZE = 35
MARGIN = 30
STONE_RADIUS = 15

class GomokuClient:
    def __init__(self, host='127.0.0.1', port=9000):
        self.host = host
        self.port = port
        self.sock = None
        self.player_id = None
        self.my_turn = False
        self.game_over = False
        self.running = True
        
        # 建立 GUI
        self.root = tk.Tk()
        self.root.title("五子棋對戰")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.setup_gui()
        
    def check_plugin(self):
        """檢查是否安裝聊天 Plugin"""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # 假設 client.py 在 downloads/PlayerX/game_id/client.py
        # plugins 在 downloads/PlayerX/plugins/
        # 所以是 ../../plugins/chat_plugin.json
        # 但如果是開發者模式，可能在 developer_client/games/gomoku/client.py
        # 此時 plugins 可能不存在，所以要小心
        
        # 嘗試路徑 1: 玩家下載目錄
        plugin_path = os.path.join(base_dir, '..', '..', 'plugins', 'chat_plugin.json')
        if os.path.exists(plugin_path):
            return True
            
        # 嘗試路徑 2: 開發者測試 (假設開發者也有 plugins 目錄?)
        # 這裡簡單起見，如果找不到就不顯示
        return False

    def setup_gui(self):
        """設定 GUI"""
        # 主框架
        main_frame = tk.Frame(self.root)
        main_frame.pack(padx=10, pady=10)
        
        # 左側：棋盤
        left_frame = tk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT)
        
        # 狀態列
        self.status_label = tk.Label(
            left_frame, 
            text="連線中...", 
            font=('Microsoft JhengHei', 14),
            fg='blue'
        )
        self.status_label.pack(pady=5)
        
        # 棋盤畫布
        canvas_size = BOARD_SIZE * CELL_SIZE + 2 * MARGIN
        self.canvas = tk.Canvas(
            left_frame,
            width=canvas_size,
            height=canvas_size,
            bg='#DEB887'
        )
        self.canvas.pack()
        self.canvas.bind('<Button-1>', self.on_canvas_click)
        
        # 玩家資訊
        self.player_label = tk.Label(
            left_frame,
            text="玩家: --",
            font=('Microsoft JhengHei', 12)
        )
        self.player_label.pack(pady=5)
        
        # 檢查 Plugin
        if self.check_plugin():
            # 右側：聊天
            right_frame = tk.Frame(main_frame)
            right_frame.pack(side=tk.RIGHT, padx=10)
            
            tk.Label(
                right_frame,
                text="聊天室 (Plugin)",
                font=('Microsoft JhengHei', 12, 'bold'),
                fg='green'
            ).pack()
            
            self.chat_text = scrolledtext.ScrolledText(
                right_frame,
                width=25,
                height=20,
                font=('Microsoft JhengHei', 10),
                state='disabled'
            )
            self.chat_text.pack(pady=5)
            
            # 聊天輸入
            chat_input_frame = tk.Frame(right_frame)
            chat_input_frame.pack(fill=tk.X)
            
            self.chat_entry = tk.Entry(
                chat_input_frame,
                font=('Microsoft JhengHei', 10)
            )
            self.chat_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
            self.chat_entry.bind('<Return>', self.send_chat)
            
            tk.Button(
                chat_input_frame,
                text="發送",
                command=self.send_chat
            ).pack(side=tk.RIGHT)
        else:
            self.chat_text = None
            self.chat_entry = None
        
        # 繪製棋盤
        self.draw_board()
        
    def draw_board(self):
        """繪製棋盤"""
        self.canvas.delete('all')
        
        # 繪製棋盤格線
        for i in range(BOARD_SIZE):
            # 水平線
            y = MARGIN + i * CELL_SIZE
            self.canvas.create_line(
                MARGIN, y,
                MARGIN + (BOARD_SIZE - 1) * CELL_SIZE, y,
                fill='black'
            )
            # 垂直線
            x = MARGIN + i * CELL_SIZE
            self.canvas.create_line(
                x, MARGIN,
                x, MARGIN + (BOARD_SIZE - 1) * CELL_SIZE,
                fill='black'
            )
        
        # 繪製星位點
        star_points = [(3, 3), (3, 11), (7, 7), (11, 3), (11, 11)]
        for row, col in star_points:
            x = MARGIN + col * CELL_SIZE
            y = MARGIN + row * CELL_SIZE
            self.canvas.create_oval(
                x - 4, y - 4, x + 4, y + 4,
                fill='black'
            )
    
    def draw_stone(self, row, col, player):
        """繪製棋子"""
        x = MARGIN + col * CELL_SIZE
        y = MARGIN + row * CELL_SIZE
        
        color = 'black' if player == 1 else 'white'
        outline = 'black'
        
        self.canvas.create_oval(
            x - STONE_RADIUS, y - STONE_RADIUS,
            x + STONE_RADIUS, y + STONE_RADIUS,
            fill=color,
            outline=outline,
            width=2
        )
    
    def on_canvas_click(self, event):
        """處理棋盤點擊"""
        if not self.my_turn or self.game_over:
            return
        
        # 計算點擊的格子
        col = round((event.x - MARGIN) / CELL_SIZE)
        row = round((event.y - MARGIN) / CELL_SIZE)
        
        if 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE:
            self.send_move(row, col)
    
    def send_move(self, row, col):
        """發送落子請求"""
        self.send_message({
            "action": "MOVE",
            "row": row,
            "col": col
        })
    
    def send_chat(self, event=None):
        """發送聊天訊息"""
        if not self.chat_entry:
            return
            
        message = self.chat_entry.get().strip()
        if message:
            self.send_message({
                "action": "CHAT",
                "message": message
            })
            self.chat_entry.delete(0, tk.END)
    
    def add_chat_message(self, text):
        """添加聊天訊息"""
        if not self.chat_text:
            return
            
        self.chat_text.config(state='normal')
        self.chat_text.insert(tk.END, text + '\n')
        self.chat_text.see(tk.END)
        self.chat_text.config(state='disabled')
    
    def send_message(self, message):
        """發送訊息到伺服器"""
        try:
            data = json.dumps(message, ensure_ascii=False).encode('utf-8')
            self.sock.sendall(len(data).to_bytes(4, 'big') + data)
            return True
        except Exception as e:
            print(f"發送失敗: {e}")
            return False
    
    def receive_messages(self):
        """接收伺服器訊息"""
        while self.running:
            try:
                header = self.sock.recv(4)
                if not header:
                    break
                
                msg_len = int.from_bytes(header, 'big')
                data = b''
                while len(data) < msg_len:
                    chunk = self.sock.recv(msg_len - len(data))
                    if not chunk:
                        break
                    data += chunk
                
                if len(data) < msg_len:
                    break
                
                message = json.loads(data.decode('utf-8'))
                self.root.after(0, self.handle_message, message)
            
            except Exception as e:
                if self.running:
                    print(f"接收錯誤: {e}")
                break
        
        self.running = False
    
    def handle_message(self, message):
        """處理伺服器訊息"""
        msg_type = message.get("type")
        
        if msg_type == "PLAYER_ID":
            self.player_id = message["player_id"]
            color = message["color"]
            self.player_label.config(text=f"你是: {color} (玩家 {self.player_id})")
            self.root.title(f"五子棋對戰 - {color}")
        
        elif msg_type == "WAITING":
            self.status_label.config(text=message["message"], fg='orange')
        
        elif msg_type == "GAME_START":
            self.status_label.config(text="遊戲開始！", fg='green')
            self.add_chat_message("=== 遊戲開始 ===")
        
        elif msg_type == "TURN":
            current = message["current_player"]
            self.my_turn = (current == self.player_id)
            
            if self.my_turn:
                self.status_label.config(text="輪到你下棋！", fg='green')
            else:
                self.status_label.config(text="等待對手...", fg='gray')
        
        elif msg_type == "MOVE":
            row = message["row"]
            col = message["col"]
            player = message["player"]
            self.draw_stone(row, col, player)
        
        elif msg_type == "ERROR":
            self.status_label.config(text=message["message"], fg='red')
        
        elif msg_type == "GAME_OVER":
            self.game_over = True
            winner = message["winner"]
            msg = message["message"]
            
            if winner == self.player_id:
                self.status_label.config(text="🎉 你贏了！", fg='green')
            elif winner == 0:
                self.status_label.config(text="平手！", fg='blue')
            else:
                self.status_label.config(text="你輸了...", fg='red')
            
            self.add_chat_message(f"=== {msg} ===")
            messagebox.showinfo("遊戲結束", msg)
        
        elif msg_type == "CHAT":
            player = message["player"]
            text = message["message"]
            self.add_chat_message(f"玩家 {player}: {text}")
        
        elif msg_type == "PLAYER_LEFT":
            self.add_chat_message(f"--- {message['message']} ---")
            self.status_label.config(text="對手已離線", fg='red')
            self.game_over = True
    
    def connect(self):
        """連線到伺服器"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            
            # 啟動接收執行緒
            recv_thread = threading.Thread(target=self.receive_messages)
            recv_thread.daemon = True
            recv_thread.start()
            
            return True
        except Exception as e:
            messagebox.showerror("連線失敗", f"無法連線到伺服器:\n{e}")
            return False
    
    def on_closing(self):
        """關閉視窗"""
        self.running = False
        
        if self.sock:
            try:
                self.send_message({"action": "QUIT"})
                self.sock.close()
            except:
                pass
        
        self.root.destroy()
    
    def run(self):
        """執行客戶端"""
        if self.connect():
            self.root.mainloop()

def main():
    parser = argparse.ArgumentParser(description='五子棋遊戲客戶端')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='伺服器位址')
    parser.add_argument('--port', type=int, default=9000, help='伺服器埠號')
    args = parser.parse_args()
    
    client = GomokuClient(args.host, args.port)
    client.run()

if __name__ == "__main__":
    main()
