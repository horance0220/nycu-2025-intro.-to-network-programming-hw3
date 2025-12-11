import os
import json
import shutil
import sys

def create_game():
    print("=== 建立新遊戲專案 ===")
    
    # 1. 取得基本資訊
    while True:
        game_id = input("請輸入遊戲 ID (英文, 例如 my_game): ").strip()
        if game_id and game_id.isalnum() or '_' in game_id:
            break
        print("無效的 ID，請只使用英數字與底線。")
        
    game_name = input("請輸入遊戲顯示名稱 (例如 My Awesome Game): ").strip()
    description = input("請輸入遊戲簡介: ").strip()
    
    # 詢問遊戲類型
    print("\n遊戲類型:")
    print("1. CLI (命令列)")
    print("2. GUI (圖形介面)")
    while True:
        type_choice = input("請選擇 (1/2) [預設 1]: ").strip()
        if not type_choice:
            game_type = "CLI"
            break
        if type_choice == '1':
            game_type = "CLI"
            break
        elif type_choice == '2':
            game_type = "GUI"
            break
            
    # 詢問人數上限
    while True:
        max_p = input("請輸入最大遊玩人數 [預設 2]: ").strip()
        if not max_p:
            max_players = 2
            break
        if max_p.isdigit() and int(max_p) > 0:
            max_players = int(max_p)
            break
        print("請輸入有效的數字")
    
    # 2. 檢查目錄
    base_dir = os.path.dirname(os.path.abspath(__file__))
    games_dir = os.path.join(base_dir, "games")
    template_dir = os.path.join(base_dir, "template")
    target_dir = os.path.join(games_dir, game_id)
    
    if os.path.exists(target_dir):
        print(f"錯誤: 遊戲目錄 '{game_id}' 已存在於 games/ 中。")
        return

    if not os.path.exists(template_dir):
        print("錯誤: 找不到 template 目錄。")
        return

    # 3. 複製檔案
    try:
        print(f"正在建立遊戲目錄: {target_dir} ...")
        shutil.copytree(template_dir, target_dir)
        
        # 4. 更新 config.json
        config_path = os.path.join(target_dir, "config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            config['name'] = game_name if game_name else game_id
            config['description'] = description
            config['game_type'] = game_type
            config['max_players'] = max_players
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
                
        print(f"\n成功！遊戲專案已建立於: {target_dir}")
        print("接下來你可以：")
        print(f"1. 編輯 {target_dir}/server.py (遊戲伺服器邏輯)")
        print(f"2. 編輯 {target_dir}/client.py (遊戲客戶端邏輯)")
        print(f"3. 編輯 {target_dir}/config.json (調整設定)")
        print("4. 使用 Developer Client 上架此遊戲")
        
    except Exception as e:
        print(f"建立失敗: {e}")

if __name__ == "__main__":
    create_game()
