import streamlit as st
import requests
import json
import firebase_admin
from firebase_admin import credentials, db
import pandas as pd
from datetime import datetime, timedelta
import time

# ==========================================
# 1. ตั้งค่า LINE Messaging API
# ==========================================
def send_line_message(message):
    access_token = 'g4xuKYAB0BSdgqy+XTqtJ1JW2HHoxjMHY09ZjzBPkTnDBTH8zodJwajuupgnuyf4nkt8kDzzSApHysltS4M9nKcMZWcxHswUEm2qwG/1m04FkBuOMDaRb2TBAqzDOmZE6M04U/1En5V0SHZcw6/+WgdB04t89/1O/w1cDnyilFU='
    user_id = 'U341205cb9e832c3d5ae46a63b6f3d79e' 
    url = 'https://api.line.me/v2/bot/message/push'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {access_token}'
    }
    data = {"to": user_id, "messages": [{"type": "text", "text": message}]}
    response = requests.post(url, headers=headers, data=json.dumps(data))
    return response.status_code

# ==========================================
# 2. ตั้งค่าเชื่อมต่อ Firebase
# ==========================================
if not firebase_admin._apps:
    firebase_credentials = dict(st.secrets["firebase"])
    cred = credentials.Certificate(firebase_credentials)
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://sleep-health-monitor-default-rtdb.asia-southeast1.firebasedatabase.app/'
    })

# ==========================================
# 3. การตั้งค่าหน้าเว็บ
# ==========================================
st.set_page_config(page_title="Sleep Health Dashboard", page_icon="💤", layout="wide")

# เมนูด้านข้าง (Sidebar) สำหรับเปิด-ปิดการอัปเดตอัตโนมัติ
st.sidebar.title("⚙️ ตั้งค่าระบบ")
auto_refresh = st.sidebar.toggle("🔄 อัปเดตอัตโนมัติ (ทุก 1 นาที)", value=True)

st.title("💤 AI รายงานสุขภาพการนอนหลับ")
st.markdown("ระบบมอนิเตอร์สถานะ Real-time และสรุปสถิติการนอนหลับประจำวัน")
st.divider()

# ==========================================
# 4. ดึงข้อมูลจาก Firebase
# ==========================================
ref_sensor = db.reference('sensor_data')
sensor_data = ref_sensor.get()
temp = sensor_data.get('temperature', '-') if sensor_data else '-'
hum = sensor_data.get('humidity', '-') if sensor_data else '-'

ref_sleep = db.reference('sleep_data')
all_sleep_data = ref_sleep.get()

# ==========================================
# 5. ส่วนแสดงผล Real-time (สถานะปัจจุบัน)
# ==========================================
st.subheader("🔴 สถานะ ณ เวลานี้")
col_t, col_h, col_pose, col_snore = st.columns(4)
col_t.metric("อุณหภูมิห้อง", f"{temp} °C")
col_h.metric("ความชื้น", f"{hum} %")

if all_sleep_data:
    latest_key = list(all_sleep_data.keys())[-1]
    latest_data = all_sleep_data[latest_key]
    
    col_pose.metric("ท่านอนปัจจุบัน", latest_data.get("pose", "-"))
    
    snore_status = latest_data.get("snore", "-")
    if snore_status == "SNORING":
        col_snore.metric("เสียงรบกวน", "🔴 กำลังกรน!")
    else:
        col_snore.metric("เสียงรบกวน", "🟢 เงียบปกติ")
else:
    st.info("ยังไม่มีข้อมูลแบบ Real-time")

st.divider()

# ==========================================
# 6. ส่วนวิเคราะห์และสรุปผลประจำวัน (Morning Summary)
# ==========================================
st.subheader("📊 สรุปผลการนอนหลับ (วิเคราะห์จาก 12 ชั่วโมงที่ผ่านมา)")

if all_sleep_data:
    # แปลงข้อมูลจาก Firebase ให้อยู่ในรูปแบบตาราง (DataFrame) เพื่อคำนวณง่ายๆ
    df = pd.DataFrame.from_dict(all_sleep_data, orient='index')
    df['time'] = pd.to_datetime(df['time'])
    
    # กรองเอาเฉพาะข้อมูล "เมื่อคืน" (ย้อนหลัง 12 ชั่วโมง)
    now = datetime.now()
    last_12h = now - timedelta(hours=12)
    df_night = df[df['time'] >= last_12h]
    
    if not df_night.empty:
        total_logs = len(df_night)
        
        # แยกเฉพาะข้อมูลตอนที่ "กรน"
        snore_df = df_night[df_night['snore'] == "SNORING"].copy()
        snore_count = len(snore_df)
        
        # คำนวณเปอร์เซ็นต์
        snore_percent = (snore_count / total_logs) * 100 if total_logs > 0 else 0
        
        # หาช่วงเวลาที่กรนหนักที่สุด (Peak Hour)
        if snore_count > 0:
            snore_df['hour'] = snore_df['time'].dt.hour
            peak_hour = int(snore_df['hour'].mode()[0]) # หาชั่วโมงที่โผล่มาบ่อยสุด
            peak_time_str = f"{peak_hour:02d}:00 - {peak_hour+1:02d}:00 น."
        else:
            peak_time_str = "ไม่มีการกรนเลย (หลับสบายมาก)"
            
        # โชว์หน้าแดชบอร์ด
        col1, col2, col3 = st.columns(3)
        col1.metric("จำนวนครั้งที่ตรวจพบเสียงกรน", f"{snore_count} ครั้ง")
        col2.metric("คิดเป็นสัดส่วน (ของเวลานอน)", f"{snore_percent:.1f} %")
        col3.metric("ช่วงเวลาที่กรนบ่อยที่สุด", peak_time_str)
        
        st.write("") # เว้นบรรทัด
        
        # ปุ่มสำหรับกดส่งรายงานเข้า LINE ตอนเช้า
        if st.button("📲 ส่งสรุปผลเมื่อคืนเข้า LINE", type="primary"):
            msg = f"\n☀️ สรุปผลการนอนหลับเมื่อคืน 💤\n\n🛌 จำนวนครั้งที่กรน: {snore_count} ครั้ง\n📊 คิดเป็น: {snore_percent:.1f}% ของเวลาทั้งหมด\n⏰ ช่วงที่กรนบ่อยสุด: {peak_time_str}\n🌡️ อุณหภูมิห้อง: {temp}°C\n\nดูแลสุขภาพและดื่มน้ำเยอะๆ นะครับ!"
            status = send_line_message(msg)
            if status == 200:
                st.success("ส่งรายงานสรุปผลเข้า LINE สำเร็จ!")
            else:
                st.error("ส่ง LINE ไม่สำเร็จ")
    else:
        st.info("ไม่มีข้อมูลการนอนหลับในช่วง 12 ชั่วโมงที่ผ่านมา")

# ==========================================
# 7. ระบบหน่วงเวลาเพื่อ Refresh หน้าเว็บอัตโนมัติ
# ==========================================
if auto_refresh:
    time.sleep(60) # รอ 1 นาที
    st.rerun()     # สั่งให้เว็บโหลดตัวเองใหม่
