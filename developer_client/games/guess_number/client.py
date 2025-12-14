#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
猜數字遊戲客戶端 (GUI 版本)
"""

import socket
import threading
import json
import argparse
import tkinter as tk
from tkinter import messagebox, scrolledtext

class GuessNumberClient:
    def __init__(self, host='127.0.0.1', port=9000):
        self.host = host
        self.port = port
        self.sock = None
        self.player_name = None
        self.my_turn = False
        self.game_over = False
        self.running = True
        self.min_range = 1
        self.max_range = 100
        
        # 建立 GUI
        self.root = tk.Tk()
        self.root.title("Guess Number Battle")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 選擇字體 (使用通用無襯線字體)
        self.font_family = 'Arial'
        self.setup_gui()
    
    def setup_gui(self):
        """設定 GUI"""
        main_frame = tk.Frame(self.root, padx=20, pady=20)
        main_frame.pack()
        
        # 標題
        tk.Label(
            main_frame,
            text="🎲 Guess Number Battle 🎲",
            font=(self.font_family, 20, 'bold')
        ).pack(pady=10)
        
        # 狀態
        self.status_label = tk.Label(
            main_frame,
            text="Connecting...",
            font=(self.font_family, 14),
            fg='blue'
        )
        self.status_label.pack(pady=5)
        
        # 範圍提示
        self.range_label = tk.Label(
            main_frame,
            text="Range: 1 ~ 100",
            font=(self.font_family, 16, 'bold'),
            fg='#333'
        )
        self.range_label.pack(pady=10)
        
        # 輸入區域
        input_frame = tk.Frame(main_frame)
        input_frame.pack(pady=10)
        
        tk.Label(
            input_frame,
            text="Your Guess:",
            font=(self.font_family, 12)
        ).pack(side=tk.LEFT)
        
        self.guess_entry = tk.Entry(
            input_frame,
            font=(self.font_family, 14),
            width=10,
            justify='center'
        )
        self.guess_entry.pack(side=tk.LEFT, padx=10)
        self.guess_entry.bind('<Return>', self.send_guess)
        
        self.guess_button = tk.Button(
            input_frame,
            text="Guess!",
            font=(self.font_family, 12),
            command=self.send_guess,
            state='disabled'
        )
        self.guess_button.pack(side=tk.LEFT)
        
        # 玩家列表
        tk.Label(
            main_frame,
            text="Players:",
            font=(self.font_family, 10)
        ).pack(pady=(20, 5))
        
        self.players_label = tk.Label(
            main_frame,
            text="--",
            font=(self.font_family, 10),
            fg='gray'
        )
        self.players_label.pack()
        
        # 遊戲記錄
        tk.Label(
            main_frame,
            text="Game Log:",
            font=(self.font_family, 10)
        ).pack(pady=(20, 5))
        
        self.log_text = scrolledtext.ScrolledText(
            main_frame,
            width=40,
            height=10,
            font=(self.font_family, 10),
            state='disabled'
        )
        self.log_text.pack()
        
        # 聊天輸入
        chat_frame = tk.Frame(main_frame)
        chat_frame.pack(pady=10, fill=tk.X)
        
        self.chat_entry = tk.Entry(
            chat_frame,
            font=(self.font_family, 10)
        )
        self.chat_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.chat_entry.bind('<Return>', self.send_chat)
        
        tk.Button(
            chat_frame,
            text="Send",
            command=self.send_chat
        ).pack(side=tk.RIGHT)
    
    def add_log(self, text, color='black'):
        """添加記錄"""
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, text + '\n')
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
    
    def send_message(self, message):
        """發送訊息"""
        try:
            data = json.dumps(message, ensure_ascii=False).encode('utf-8')
            self.sock.sendall(len(data).to_bytes(4, 'big') + data)
            return True
        except:
            return False
    
    def send_guess(self, event=None):
        """發送猜測"""
        if not self.my_turn or self.game_over:
            return
        
        try:
            guess = int(self.guess_entry.get().strip())
            self.send_message({
                "action": "GUESS",
                "number": guess
            })
            self.guess_entry.delete(0, tk.END)
        except ValueError:
            self.status_label.config(text="Please enter a valid number!", fg='red')
    
    def send_chat(self, event=None):
        """發送聊天"""
        message = self.chat_entry.get().strip()
        if message:
            self.send_message({
                "action": "CHAT",
                "message": message
            })
            self.chat_entry.delete(0, tk.END)
    
    def receive_messages(self):
        """接收訊息"""
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
                    print(f"Receive Error: {e}")
                break
        
        self.running = False
    
    def handle_message(self, message):
        """處理訊息"""
        msg_type = message.get("type")
        
        if msg_type == "JOINED":
            self.player_name = message["player_name"]
            self.status_label.config(
                text=f"You are: {self.player_name} | Waiting for players...",
                fg='blue'
            )
            self.add_log(f"=== You joined the game ({self.player_name}) ===")
        
        elif msg_type == "PLAYER_JOINED":
            self.add_log(f"✨ {message['player_name']} joined ({message['player_count']} players)")
        
        elif msg_type == "PLAYER_LEFT":
            self.add_log(f"❌ {message['player_name']} left")
        
        elif msg_type == "COUNTDOWN":
            self.status_label.config(text=message["message"], fg='orange')
            self.add_log(message["message"])
        
        elif msg_type == "GAME_START":
            self.add_log("=== 🎮 Game Start! ===")
            self.range_label.config(text=f"Range: {message['range']['min']} ~ {message['range']['max']}")
        
        elif msg_type == "TURN":
            current = message["current_player"]
            self.min_range = message["range"]["min"]
            self.max_range = message["range"]["max"]
            
            self.range_label.config(text=f"Range: {self.min_range} ~ {self.max_range}")
            
            if current == self.player_name:
                self.my_turn = True
                self.guess_button.config(state='normal')
                self.status_label.config(text="⏰ Your Turn!", fg='green')
            else:
                self.my_turn = False
                self.guess_button.config(state='disabled')
                self.status_label.config(text=f"Waiting for {current}...", fg='gray')
        
        elif msg_type == "GUESS_RESULT":
            player = message["player"]
            guess = message["guess"]
            result = message["result"]
            
            if result == "higher":
                self.add_log(f"📈 {player} guessed {guess}, too small!")
            elif result == "lower":
                self.add_log(f"📉 {player} guessed {guess}, too big!")
            elif result == "correct":
                self.add_log(f"🎯 {player} guessed {guess}, Correct!")
            
            self.min_range = message["range"]["min"]
            self.max_range = message["range"]["max"]
            self.range_label.config(text=f"Range: {self.min_range} ~ {self.max_range}")
        
        elif msg_type == "GAME_OVER":
            self.game_over = True
            self.guess_button.config(state='disabled')
            
            winner = message["winner"]
            answer = message["answer"]
            
            if winner == self.player_name:
                self.status_label.config(text="🎉 You Win!", fg='green')
            else:
                self.status_label.config(text=f"{winner} Wins! Answer: {answer}", fg='blue')
            
            self.add_log(f"=== {message['message']} ===")
            messagebox.showinfo("Game Over", message["message"])
        
        elif msg_type == "CHAT":
            self.add_log(f"💬 {message['player']}: {message['message']}")
        
        elif msg_type == "ERROR":
            self.status_label.config(text=message["message"], fg='red')
        
        elif msg_type in ["FULL", "STARTED"]:
            messagebox.showerror("Cannot Join", message["message"])
            self.root.destroy()
    
    def connect(self):
        """連線"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            
            recv_thread = threading.Thread(target=self.receive_messages)
            recv_thread.daemon = True
            recv_thread.start()
            
            return True
        except Exception as e:
            messagebox.showerror("Connection Failed", f"Cannot connect:\n{e}")
            return False
    
    def on_closing(self):
        """關閉"""
        self.running = False
        if self.sock:
            try:
                self.send_message({"action": "QUIT"})
                self.sock.close()
            except:
                pass
        self.root.destroy()
    
    def run(self):
        """執行"""
        if self.connect():
            self.root.mainloop()

def main():
    parser = argparse.ArgumentParser(description='猜數字遊戲客戶端')
    parser.add_argument('--host', type=str, default='127.0.0.1')
    parser.add_argument('--port', type=int, default=9000)
    args = parser.parse_args()
    
    client = GuessNumberClient(args.host, args.port)
    client.run()

if __name__ == "__main__":
    main()
