import streamlit as st
import requests
import json
import firebase_admin
from firebase_admin import credentials, db
import pandas as pd
import numpy as np
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
# 3. การตั้งค่าหน้าเว็บ และ ตัวแปรเวลา
# ==========================================
st.set_page_config(page_title="Sleeping Dashboard", page_icon="💤", layout="wide")

# จัดการ Timezone ให้เป็นเวลาประเทศไทย (UTC+7) เสมอ
thai_time = datetime.utcnow() + timedelta(hours=7)
current_date = thai_time.date()

# ==========================================
# เมนูด้านข้าง (Sidebar)
# ==========================================
st.sidebar.title("📌 เมนูนำทาง")
page = st.sidebar.radio("เลือกหน้าต่างแสดงผล:", ["🏠 หน้าหลัก (Dashboard)", "📈 กราฟสถิติ (Statistics)"])

st.sidebar.divider()
st.sidebar.title("⚙️ ตั้งค่าระบบ")
auto_refresh = st.sidebar.toggle("🔄 อัปเดตอัตโนมัติ (ทุก 10 วินาที)", value=True)

st.sidebar.divider()
st.sidebar.subheader("⏰ ตั้งเวลาส่งรายงาน (LINE)")

# ระบบจำเวลาแจ้งเตือนผ่าน Firebase
alert_time_ref = db.reference('system_status/alert_time')
saved_time_str = alert_time_ref.get()

if saved_time_str:
    h, m = map(int, saved_time_str.split(':'))
    default_alert_time = dt_time(h, m)
else:
    default_alert_time = dt_time(8, 0)

alert_time = st.sidebar.time_input("เลือกเวลาส่งสรุปผล", value=default_alert_time)

if alert_time.strftime('%H:%M') != saved_time_str:
    alert_time_ref.set(alert_time.strftime('%H:%M'))

selected_date = st.sidebar.date_input("📅 เลือกวันที่อ้างอิง", value=current_date)

# ==========================================
# 4. ดึงข้อมูลและจัดการข้อมูล 
# ==========================================
ref_sensor = db.reference('sensor_data')
sensor_data = ref_sensor.get()
temp = sensor_data.get('temperature', '-') if sensor_data else '-'
hum = sensor_data.get('humidity', '-') if sensor_data else '-'

ref_sleep = db.reference('sleep_data')
all_sleep_data = ref_sleep.get()

df_all = pd.DataFrame()
if all_sleep_data:
    df_all = pd.DataFrame.from_dict(all_sleep_data, orient='index')
    df_all['time'] = pd.to_datetime(df_all['time'])

# ==========================================
# 5. การแสดงผลตามหน้าที่เลือก (Routing)
# ==========================================

# ------------------------------------------
# หน้าที่ 1: หน้าหลัก (Dashboard)
# ------------------------------------------
if page == "🏠 หน้าหลัก (Dashboard)":
    st.title("💤 AI รายงานการนอนหลับ")
    st.markdown("ระบบมอนิเตอร์สถานะ Real-time และสรุปสถิติการนอนหลับประจำวัน")
    st.divider()

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
    st.subheader("📊 สรุปผลการนอนหลับเบื้องต้น")

    start_time_daily = datetime.combine(selected_date - timedelta(days=1), dt_time(18, 0))
    end_time_daily = datetime.combine(selected_date, dt_time(18, 0))
    
    df_night = pd.DataFrame()
    if not df_all.empty:
        df_night = df_all[(df_all['time'] >= start_time_daily) & (df_all['time'] <= end_time_daily)]

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
            
        st.write(f"ข้อมูลตั้งแต่ **{start_time_daily.strftime('%d/%m/%Y %H:%M')}** ถึง **{end_time_daily.strftime('%d/%m/%Y %H:%M')}**")
        col1, col2, col3 = st.columns(3)
        col1.metric("จำนวนครั้งที่ตรวจพบเสียงกรน", f"{snore_count} ครั้ง")
        col2.metric("คิดเป็นสัดส่วน (ของเวลานอน)", f"{snore_percent:.1f} %")
        col3.metric("ช่วงเวลาที่กรนบ่อยที่สุด", peak_time_str)
        
        report_msg = f"\n☀️ สรุปผลการนอนหลับเช้านี้ ({selected_date.strftime('%d/%m/%Y')}) 💤\n\n🛌 จำนวนครั้งที่กรน: {snore_count} ครั้ง\n📊 สัดส่วนการกรน: {snore_percent:.1f}%\n⏰ ช่วงที่กรนบ่อยสุด: {peak_time_str}\n🌡️ อุณหภูมิห้อง: {temp}°C\n\nอย่าลืมดื่มน้ำเยอะๆ นะครับ!"
        
        st.write("") 
        
        if st.button("🚀 บังคับส่งรายงานนี้เข้า LINE ทันที", type="primary"):
            status = send_line_message(report_msg)
            if status == 200:
                st.success("ส่งรายงานเข้า LINE สำเร็จ!")
            else:
                st.error("ส่ง LINE ไม่สำเร็จ")
                
        target_alert_datetime = datetime.combine(current_date, alert_time)
        if thai_time >= target_alert_datetime:
            last_sent_ref = db.reference('system_status/last_sent_date')
            if last_sent_ref.get() != str(current_date):
                if send_line_message(report_msg) == 200:
                    last_sent_ref.set(str(current_date))
                    st.toast(f"ส่งรายงานอัตโนมัติตามนัดตอน {alert_time.strftime('%H:%M')} สำเร็จ!", icon="✅")
    else:
        st.info("ไม่มีข้อมูลการนอนหลับในคืนวันที่คุณเลือก")

# ------------------------------------------
# หน้าที่ 2: กราฟสถิติ (Statistics)
# ------------------------------------------
elif page == "📈 กราฟสถิติ (Statistics)":
    st.title("📈 ไทม์ไลน์พฤติกรรมการนอนหลับ (Time-Series)")
    


        
    start_time_stats = datetime.combine(selected_date - timedelta(days=days_back), dt_time(18, 0))
    end_time_stats = datetime.combine(selected_date, dt_time(18, 0))

    st.markdown(f"ข้อมูลตั้งแต่ **{start_time_stats.strftime('%d/%m/%Y %H:%M')}** ถึง **{end_time_stats.strftime('%d/%m/%Y %H:%M')}**")
    st.divider()

    df_stats = pd.DataFrame()
    if not df_all.empty:
        df_stats = df_all[(df_all['time'] >= start_time_stats) & (df_all['time'] <= end_time_stats)].copy()

    if not df_stats.empty:
        # 🌟 ตั้งค่าให้แกน X เป็น "เวลา" สำหรับกราฟเส้น
        df_stats.set_index('time', inplace=True)
        
        # กราฟชั้นที่ 1: ความถี่และความหนักของการกรน
        st.subheader("🗣️ ความน่าจะเป็นของการกรน (Snoring Probability)")
        st.line_chart(df_stats[['prob']], color="#FF4B4B")
        
        # กราฟชั้นที่ 2: การพลิกตัว/ท่านอน
        st.subheader("🛌 การเปลี่ยนท่านอนระหว่างคืน (Sleep Pose)")
        # แปลงข้อความท่านอนให้เป็นตัวเลขเพื่อวาดกราฟเส้นได้
        def pose_to_num(p):
            if p == "Face up/down": return 1.0
            elif p == "Side": return 2.0
            else: return None
            
        df_stats['pose_num'] = df_stats['pose'].apply(pose_to_num)
        pose_chart_df = df_stats.dropna(subset=['pose_num'])
        
        if not pose_chart_df.empty:
            st.line_chart(pose_chart_df[['pose_num']], color="#1f77b4")
            st.caption("💡 แกน Y: 1.0 = นอนหงาย/คว่ำ (Face up/down)  |  2.0 = นอนตะแคง (Side)")
        
        # กราฟชั้นที่ 3: อุณหภูมิและความชื้น
        st.subheader("🌡️ สภาพแวดล้อมห้องนอน (อุณหภูมิ & ความชื้น)")
        # ตรวจสอบว่ามีคอลัมน์ temp และ hum ในฐานข้อมูลแล้วหรือยัง
        if 'temp' in df_stats.columns and 'hum' in df_stats.columns:
            st.line_chart(df_stats[['temp', 'hum']])
        else:
            st.info("⏳ ไม่พบประวัติอุณหภูมิและความชื้น (กำลังรอรับข้อมูลรูปแบบใหม่ที่คุณเพิ่งอัปเดตครับ)")

        # แสดงตารางข้อมูลดิบ
        st.divider()
        st.subheader("📋 ตารางข้อมูลบันทึกทั้งหมด (Log)")
        st.dataframe(
            df_stats[['snore', 'prob', 'pose', 'temp', 'hum'] if 'temp' in df_stats.columns else ['snore', 'prob', 'pose']].sort_index(ascending=False),
            use_container_width=True
        )
    else:
        st.warning("⚠️ ไม่มีข้อมูลสำหรับการสร้างกราฟในช่วงเวลาที่คุณเลือกครับ")

# ==========================================
# 6. ระบบหน่วงเวลาเพื่อ Refresh หน้าเว็บอัตโนมัติ
# ==========================================
if auto_refresh:
    time.sleep(10)
    st.rerun()
