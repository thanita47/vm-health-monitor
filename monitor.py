import subprocess
import paramiko
import sqlite3
from datetime import datetime
import requests

TARGET_IP = "192.168.x.x"
SSH_USER = "your_username"
SSH_PASSWORD = "your_password"
DB_NAME = "monitor_log.db"

TELEGRAM_TOKEN = "your_telegram_bot_token"
TELEGRAM_CHAT_ID = "your_telegram_chat_id"

CPU_THRESHOLD = 80
RAM_THRESHOLD = 80

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            status TEXT,
            cpu REAL,
            ram REAL
        )
    ''')
    conn.commit()
    conn.close()

def save_log(status, cpu, ram):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO logs (timestamp, status, cpu, ram) VALUES (?, ?, ?, ?)",
        (timestamp, status, cpu, ram)
    )
    conn.commit()
    conn.close()

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=5)
    except Exception as e:
        print(f"ส่ง Telegram แจ้งเตือนไม่สำเร็จ: {e}")

def check_ping(ip):
    result = subprocess.run(['ping', '-c', '1', '-W', '2', ip], capture_output=True)
    return result.returncode == 0

def get_server_stats(ip, user, password):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(ip, username=user, password=password, timeout=5)
        cmd = "python3 -c \"import psutil; print(psutil.cpu_percent(interval=1)); print(psutil.virtual_memory().percent)\""
        stdin, stdout, stderr = client.exec_command(cmd)
        output = stdout.read().decode().strip().split('\n')
        client.close()
        if len(output) >= 2:
            return {"cpu": output[0], "ram": output[1]}
        else:
            return {"error": "อ่านค่าไม่ได้"}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    init_db()
    online = check_ping(TARGET_IP)
    status = "ONLINE" if online else "OFFLINE"
    print(f"target-server ({TARGET_IP}): {status}")

    if not online:
        save_log(status, 0, 0)
        send_telegram_alert(f"⚠️ แจ้งเตือน: target-server ({TARGET_IP}) OFFLINE!")
        print("ส่งแจ้งเตือน: server offline")
    else:
        stats = get_server_stats(TARGET_IP, SSH_USER, SSH_PASSWORD)
        if "error" in stats:
            print(f"เชื่อมต่อ SSH ไม่ได้: {stats['error']}")
            save_log(status, 0, 0)
        else:
            cpu_val = float(stats['cpu'])
            ram_val = float(stats['ram'])
            print(f"CPU Usage: {cpu_val}%")
            print(f"RAM Usage: {ram_val}%")
            save_log(status, cpu_val, ram_val)

            if cpu_val > CPU_THRESHOLD or ram_val > RAM_THRESHOLD:
                send_telegram_alert(
                    f"⚠️ แจ้งเตือน: target-server ใช้งานสูง\nCPU: {cpu_val}%\nRAM: {ram_val}%"
                )
                print("ส่งแจ้งเตือน: usage สูงเกินกำหนด")
            else:
                print("สถานะปกติ ไม่ต้องแจ้งเตือน")