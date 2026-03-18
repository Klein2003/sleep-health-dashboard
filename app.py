import streamlit as st
import requests
import json
import firebase_admin
from firebase_admin import credentials, db
import pandas as pd
from datetime import datetime, timedelta, time as dt_time
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
# 3. การตั้งค่าหน้าเว็บ และ ตัวแปรความจำ
# ==========================================
st.set_page_config(page_title="Sleep Health Dashboard", page_icon="💤", layout="wide")

# สร้างตัวความจำว่า "วันนี้ส่ง LINE ไปหรือยัง?"
if 'last_sent_date' not in st.session_state:
    st.session_state.last_sent_date = None

# 🌟 จัดการ Timezone ให้เป็นเวลาประเทศไทย (UTC+7) เสมอ
thai_time = datetime.utcnow() + timedelta(hours=7)
current_date = thai_time.date()

# ==========================================
# เมนูด้านข้าง (Sidebar) สำหรับตั้งค่าเวลา
# ==========================================
st.sidebar.title("⚙️ ตั้งค่าระบบ")
auto_refresh = st.sidebar.toggle("🔄 อัปเดตอัตโนมัติ (ทุก 10 วินาที)", value=True)

st.sidebar.divider()
st.sidebar.subheader("⏰ ตั้งเวลาส่งรายงาน (LINE)")
alert_time = st.sidebar.time_input("เลือกเวลาส่งสรุปผล", value=dt_time(8, 0))

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
# 6. ส่วนวิเคราะห์และสรุปผลประจำวัน
# ==========================================
st.subheader("📊 สรุปผลการนอนหลับ")

selected_date = st.date_input("เลือกวันที่ต้องการดูรายงาน", value=current_date)

if all_sleep_data:
    df = pd.DataFrame.from_dict(all_sleep_data, orient='index')
    df['time'] = pd.to_datetime(df['time'])
    
    # กำหนดรอบการนอน: 18:00 ของเมื่อวาน ถึง 12:00 ของวันที่เลือก
    start_time = datetime.combine(selected_date - timedelta(days=1), dt_time(18, 0))
    end_time = datetime.combine(selected_date, dt_time(18, 0))

    df_night = df[(df['time'] >= start_time) & (df['time'] <= end_time)]
    
    if not df_night.empty:
        total_logs = len(df_night)
        
        snore_df = df_night[df_night['snore'] == "SNORING"].copy()
        snore_count = len(snore_df)
        
        snore_percent = (snore_count / total_logs) * 100 if total_logs > 0 else 0
        
        if snore_count > 0:
            snore_df['hour'] = snore_df['time'].dt.hour
            peak_hour = int(snore_df['hour'].mode()[0])
            peak_time_str = f"{peak_hour:02d}:00 - {peak_hour+1:02d}:00 น."
        else:
            peak_time_str = "ไม่มีการกรน (หลับสบาย)"
            
        st.write(f"ข้อมูลการนอนตั้งแต่ **{start_time.strftime('%d/%m/%Y %H:%M')}** ถึง **{end_time.strftime('%d/%m/%Y %H:%M')}**")
        col1, col2, col3 = st.columns(3)
        col1.metric("จำนวนครั้งที่ตรวจพบเสียงกรน", f"{snore_count} ครั้ง")
        col2.metric("คิดเป็นสัดส่วน (ของเวลานอน)", f"{snore_percent:.1f} %")
        col3.metric("ช่วงเวลาที่กรนบ่อยที่สุด", peak_time_str)
        
        report_msg = f"\n☀️ สรุปผลการนอนหลับเช้านี้ ({selected_date.strftime('%d/%m/%Y')}) 💤\n\n🛌 จำนวนครั้งที่กรน: {snore_count} ครั้ง\n📊 สัดส่วนการกรน: {snore_percent:.1f}%\n⏰ ช่วงที่กรนบ่อยสุด: {peak_time_str}\n🌡️ อุณหภูมิห้อง: {temp}°C\n\nอย่าลืมดื่มน้ำเยอะๆ นะครับ!"
        
        st.write("") 
        
        # 🌟 ปุ่มบังคับส่ง (Manual Force Send)
        if st.button("🚀 บังคับส่งรายงานนี้เข้า LINE ทันที", type="primary"):
            status = send_line_message(report_msg)
            if status == 200:
                st.success("ส่งรายงานเข้า LINE สำเร็จ!")
            else:
                st.error("ส่ง LINE ไม่สำเร็จ")
                
        # ---------------------------------
        # 🌟 ระบบเช็คเวลาส่ง LINE อัตโนมัติ (ฉบับแก้บั๊กแล้ว แม่นยำ 100%)
        # ---------------------------------
        # สร้างเวลาเป้าหมายของวันนี้ (เอาวันที่ปัจจุบัน + เวลาที่ตั้งไว้ใน Sidebar)
        target_alert_datetime = datetime.combine(current_date, alert_time)
        
        # ลอจิกใหม่: ถ้าเวลาปัจจุบัน "เลยหรือเท่ากับ" เวลาที่ตั้งไว้ และ "วันนี้ยังไม่ได้ส่ง"
        if thai_time >= target_alert_datetime:
            if st.session_state.last_sent_date != current_date:
                status = send_line_message(report_msg)
                if status == 200:
                    st.session_state.last_sent_date = current_date # เมมไว้ว่าวันนี้ส่งไปแล้ว
                    st.toast(f"ส่งรายงานอัตโนมัติตามนัดตอน {alert_time.strftime('%H:%M')} สำเร็จ!", icon="✅")
                    
    else:
        st.info("ไม่มีข้อมูลการนอนหลับในคืนวันที่คุณเลือก")

# ==========================================
# 7. ระบบหน่วงเวลาเพื่อ Refresh หน้าเว็บอัตโนมัติ (แก้เป็น 10 วินาที)
# ==========================================
if auto_refresh:
    time.sleep(10) # 🌟 รอ 10 วินาที
    st.rerun()     # สั่งให้เว็บโหลดตัวเองใหม่

