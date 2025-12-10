import socket
import json
import struct
import os
import hashlib

# 通訊協定格式:
# [Header: 4 bytes (Big Endian) 資料長度] + [Body: JSON UTF-8 bytes]

# ========================= 基本 JSON 傳輸 =========================

def send_json(sock, data_dict):
    """
    將 Python Dictionary 轉成 JSON 並發送
    """
    try:
        # 1. 轉成 JSON 字串
        json_str = json.dumps(data_dict)
        # 2. 編碼成 bytes
        json_bytes = json_str.encode('utf-8')
        # 3. 計算長度並打包 Header (4 bytes, big-endian)
        header = struct.pack('>I', len(json_bytes))
        
        # 4. 發送 (Header + Body)
        sock.sendall(header + json_bytes)
        return True
    except Exception as e:
        print(f"[Send Error] {e}")
        return False

def recv_json(sock):
    """
    從 Socket 接收完整的一個 JSON 封包
    """
    try:
        # 1. 先讀取 Header (4 bytes) 知道資料有多長
        header = recv_all(sock, 4)
        if not header:
            return None # 對方關閉連線
            
        # 解包取得資料長度
        data_len = struct.unpack('>I', header)[0]
        
        # 2. 根據長度讀取 Body
        body_bytes = recv_all(sock, data_len)
        if not body_bytes:
            return None
            
        # 3. 解碼並轉回 Python Dictionary
        json_str = body_bytes.decode('utf-8')
        return json.loads(json_str)
        
    except Exception as e:
        print(f"[Recv Error] {e}")
        return None

def recv_all(sock, n):
    """
    輔助函式：確保一定讀滿 n 個 bytes 才會返回
    解決 TCP 斷包問題
    """
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data

# ========================= 檔案傳輸功能 =========================

def send_file(sock, file_path):
    """
    發送檔案：先傳 metadata (JSON)，再傳檔案內容 (binary)
    """
    try:
        if not os.path.exists(file_path):
            return False, "檔案不存在"
        
        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)
        
        # 計算檔案 MD5 用於驗證
        md5_hash = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                md5_hash.update(chunk)
        file_md5 = md5_hash.hexdigest()
        
        # 1. 先發送 metadata
        metadata = {
            "type": "FILE_TRANSFER",
            "filename": file_name,
            "filesize": file_size,
            "md5": file_md5
        }
        send_json(sock, metadata)
        
        # 2. 等待對方準備好
        response = recv_json(sock)
        if not response or response.get("status") != "READY":
            return False, "對方未準備好接收"
        
        # 3. 發送檔案內容
        with open(file_path, 'rb') as f:
            sent = 0
            while sent < file_size:
                chunk = f.read(8192)
                if not chunk:
                    break
                sock.sendall(chunk)
                sent += len(chunk)
        
        # 4. 等待確認
        ack = recv_json(sock)
        if ack and ack.get("status") == "SUCCESS":
            return True, "檔案傳輸成功"
        else:
            return False, ack.get("message", "傳輸失敗")
            
    except Exception as e:
        return False, str(e)

def recv_file(sock, save_dir):
    """
    接收檔案：先收 metadata，再收檔案內容
    回傳 (成功與否, 訊息, 檔案路徑)
    """
    try:
        # 1. 接收 metadata (已經由呼叫者收到並傳入)
        # 這裡假設已經收到 metadata，等待後續呼叫
        pass
    except Exception as e:
        return False, str(e), None

def recv_file_with_metadata(sock, metadata, save_dir):
    """
    根據已收到的 metadata 接收檔案
    """
    try:
        filename = metadata.get("filename")
        filesize = metadata.get("filesize")
        expected_md5 = metadata.get("md5")
        
        # 確保目錄存在
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, filename)
        
        # 1. 回覆準備好了
        send_json(sock, {"status": "READY"})
        
        # 2. 接收檔案內容
        received = 0
        md5_hash = hashlib.md5()
        
        with open(save_path, 'wb') as f:
            while received < filesize:
                remaining = filesize - received
                chunk_size = min(8192, remaining)
                chunk = recv_all(sock, chunk_size)
                if not chunk:
                    return False, "傳輸中斷", None
                f.write(chunk)
                md5_hash.update(chunk)
                received += len(chunk)
        
        # 3. 驗證 MD5
        actual_md5 = md5_hash.hexdigest()
        if actual_md5 != expected_md5:
            os.remove(save_path)
            send_json(sock, {"status": "FAILED", "message": "MD5 驗證失敗"})
            return False, "MD5 驗證失敗", None
        
        # 4. 回覆成功
        send_json(sock, {"status": "SUCCESS"})
        return True, "檔案接收成功", save_path
        
    except Exception as e:
        send_json(sock, {"status": "FAILED", "message": str(e)})
        return False, str(e), None

# ========================= 輔助函式 =========================

def create_response(success, message, data=None):
    """建立標準回應格式"""
    response = {
        "success": success,
        "message": message
    }
    if data:
        response["data"] = data
    return response