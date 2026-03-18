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

if 'last_sent_date' not in st.session_state:
    st.session_state.last_sent_date = None

thai_time = datetime.utcnow() + timedelta(hours=7)
current_date = thai_time.date()

# ==========================================
# เมนูด้านข้าง (Sidebar)
# ==========================================
st.sidebar.title("📌 เมนูนำทาง")
# 🌟 สร้างปุ่มเลือกหน้า
page = st.sidebar.radio("เลือกหน้าต่างแสดงผล:", ["🏠 หน้าหลัก (Dashboard)", "📈 กราฟสถิติ (Statistics)"])

st.sidebar.divider()
st.sidebar.title("⚙️ ตั้งค่าระบบ")
auto_refresh = st.sidebar.toggle("🔄 อัปเดตอัตโนมัติ (ทุก 10 วินาที)", value=True)

st.sidebar.divider()
st.sidebar.subheader("⏰ ตั้งเวลาส่งรายงาน (LINE)")
alert_time = st.sidebar.time_input("เลือกเวลาส่งสรุปผล", value=dt_time(8, 0))

# ==========================================
# 4. ดึงข้อมูลและจัดการข้อมูล (ทำครั้งเดียวใช้ได้ทุกหน้า)
# ==========================================
ref_sensor = db.reference('sensor_data')
sensor_data = ref_sensor.get()
temp = sensor_data.get('temperature', '-') if sensor_data else '-'
hum = sensor_data.get('humidity', '-') if sensor_data else '-'

ref_sleep = db.reference('sleep_data')
all_sleep_data = ref_sleep.get()

# ให้ผู้ใช้เลือกวันที่ต้องการดูสถิติ (ย้ายมาไว้ข้างนอกเพื่อให้มีผลกับทั้ง 2 หน้า)
selected_date = st.sidebar.date_input("📅 เลือกวันที่ดึงข้อมูล", value=current_date)

df_night = pd.DataFrame() # สร้างตัวแปรว่างไว้ก่อน
start_time = datetime.combine(selected_date - timedelta(days=1), dt_time(18, 0))
end_time = datetime.combine(selected_date, dt_time(18, 0))

if all_sleep_data:
    df = pd.DataFrame.from_dict(all_sleep_data, orient='index')
    df['time'] = pd.to_datetime(df['time'])
    # กรองเอาเฉพาะข้อมูลในรอบเวลาที่กำหนด
    df_night = df[(df['time'] >= start_time) & (df['time'] <= end_time)]

# ==========================================
# 5. การแสดงผลตามหน้าที่เลือก (Routing)
# ==========================================

# ------------------------------------------
# หน้าที่ 1: หน้าหลัก (Dashboard)
# ------------------------------------------
if page == "🏠 หน้าหลัก (Dashboard)":
    st.title("💤 AI รายงานสุขภาพการนอนหลับ")
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
            
        st.write(f"ข้อมูลตั้งแต่ **{start_time.strftime('%d/%m/%Y %H:%M')}** ถึง **{end_time.strftime('%d/%m/%Y %H:%M')}**")
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
                
        # ระบบส่ง LINE อัตโนมัติ
        target_alert_datetime = datetime.combine(current_date, alert_time)
        if thai_time >= target_alert_datetime:
            if st.session_state.last_sent_date != current_date:
                status = send_line_message(report_msg)
                if status == 200:
                    st.session_state.last_sent_date = current_date
                    st.toast(f"ส่งรายงานอัตโนมัติตามนัดตอน {alert_time.strftime('%H:%M')} สำเร็จ!", icon="✅")
    else:
        st.info("ไม่มีข้อมูลการนอนหลับในคืนวันที่คุณเลือก")

# ------------------------------------------
# หน้าที่ 2: กราฟสถิติ (Statistics)
# ------------------------------------------
elif page == "📈 กราฟสถิติ (Statistics)":
    st.title("📈 กราฟวิเคราะห์พฤติกรรมการนอนหลับ")
    st.markdown(f"ข้อมูลตั้งแต่ **{start_time.strftime('%d/%m/%Y %H:%M')}** ถึง **{end_time.strftime('%d/%m/%Y %H:%M')}**")
    st.divider()

    if not df_night.empty:
        col_chart1, col_chart2 = st.columns(2)
        
        # กราฟที่ 1: ความถี่ของการกรนรายชั่วโมง
        with col_chart1:
            st.subheader("🗣️ ความถี่ของการกรน (รายชั่วโมง)")
            snore_df = df_night[df_night['snore'] == "SNORING"].copy()
            if not snore_df.empty:
                # จัดกลุ่มข้อมูลตามชั่วโมง
                snore_df['hour_str'] = snore_df['time'].dt.strftime('%H:00')
                snore_by_hour = snore_df['hour_str'].value_counts().sort_index()
                st.bar_chart(snore_by_hour, color="#FF4B4B") # กราฟแท่งสีแดง
            else:
                st.success("ไม่พบการกรนในช่วงเวลานี้ เยี่ยมมากครับ!")

        # กราฟที่ 2: สัดส่วนท่านอน
        with col_chart2:
            st.subheader("🛌 สัดส่วนท่านอน (จำนวนครั้งที่ตรวจจับได้)")
            # นับจำนวนแต่ละท่านอน
            pose_counts = df_night['pose'].value_counts()
            # กรองค่า "WAITING" ออก (ถ้ามี) จะได้ดูกราฟสวยๆ
            if "WAITING" in pose_counts:
                pose_counts = pose_counts.drop("WAITING")
                
            if not pose_counts.empty:
                st.bar_chart(pose_counts, color="#1f77b4") # กราฟแท่งสีน้ำเงิน
            else:
                st.info("ไม่มีข้อมูลท่านอนที่สมบูรณ์")
                
        # แสดงตารางข้อมูลดิบด้านล่างเผื่อต้องการดูรายละเอียด
        st.divider()
        st.subheader("📋 ตารางข้อมูลบันทึกทั้งหมด (Log)")
        st.dataframe(
            df_night[['time', 'snore', 'prob', 'pose']].sort_values(by='time', ascending=False),
            use_container_width=True
        )
    else:
        st.warning("⚠️ ไม่มีข้อมูลสำหรับการสร้างกราฟในวันและเวลาที่คุณเลือกครับ")

# ==========================================
# 6. ระบบหน่วงเวลาเพื่อ Refresh หน้าเว็บอัตโนมัติ
# ==========================================
if auto_refresh:
    time.sleep(10)
    st.rerun()
