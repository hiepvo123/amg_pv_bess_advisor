import sqlite3
import os
import random
import datetime

DB_PATH = "local_system_data.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tạo bảng lưu thông số Inverter
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inverter_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            device_id TEXT,
            voltage REAL,
            current REAL,
            temperature REAL,
            status TEXT
        )
    ''')
    
    # Check nếu bảng rỗng thì thêm data giả lập
    cursor.execute('SELECT COUNT(*) FROM inverter_data')
    if cursor.fetchone()[0] == 0:
        print("Dang tao du lieu mau cho Inverter...")
        now = datetime.datetime.now()
        for i in range(1, 4):  # 3 Inverters
            cursor.execute('''
                INSERT INTO inverter_data (timestamp, device_id, voltage, current, temperature, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (now, f'INV_{i:02d}', round(random.uniform(700, 800), 2), round(random.uniform(10, 50), 2), round(random.uniform(40, 60), 2), 'Running'))
            
        # Thêm 1 dòng báo lỗi cho dễ test
        cursor.execute('''
            INSERT INTO inverter_data (timestamp, device_id, voltage, current, temperature, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (now, 'INV_04', 850.5, 0.0, 75.2, 'Overvoltage Fault'))
        
    conn.commit()
    conn.close()

def get_latest_device_data(device_id: str = None):
    """Truy vấn dữ liệu mới nhất của thiết bị."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if device_id:
        cursor.execute('SELECT * FROM inverter_data WHERE device_id = ? ORDER BY timestamp DESC LIMIT 1', (device_id,))
        row = cursor.fetchone()
    else:
        cursor.execute('SELECT * FROM inverter_data ORDER BY timestamp DESC LIMIT 5')
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return "Không có dữ liệu."
        
        result = []
        for r in rows:
            result.append(f"Device: {r[2]}, V: {r[3]}V, I: {r[4]}A, Temp: {r[5]}C, Status: {r[6]}")
        return "\n".join(result)
        
    conn.close()
    if row:
        return f"Device: {row[2]}, V: {row[3]}V, I: {row[4]}A, Temp: {row[5]}C, Status: {row[6]}"
    return f"Không tìm thấy dữ liệu cho thiết bị {device_id}"

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
    print("Du lieu hien tai:")
    print(get_latest_device_data())
