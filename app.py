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
page = st.sidebar.radio("เลือกหน้าต่างแสดงผล:", ["🏠 หน้าหลัก (Dashboard)", "📈 กราฟสถิติ (Statistics)"])

st.sidebar.divider()
st.sidebar.title("⚙️ ตั้งค่าระบบ")
auto_refresh = st.sidebar.toggle("🔄 อัปเดตอัตโนมัติ (ทุก 10 วินาที)", value=True)

st.sidebar.divider()
st.sidebar.subheader("⏰ ตั้งเวลาส่งรายงาน (LINE)")
alert_time = st.sidebar.time_input("เลือกเวลาส่งสรุปผล", value=dt_time(8, 0))

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

# แปลงข้อมูลทั้งหมดเป็น DataFrame เตรียมไว้
df_all = pd.DataFrame()
if all_sleep_data:
    df_all = pd.DataFrame.from_dict(all_sleep_data, orient='index')
    df_all['time'] = pd.to_datetime(df_all['time'])

# ==========================================
# 5. การแสดงผลตามหน้าที่เลือก (Routing)
# ==========================================

# ------------------------------------------
# หน้าที่ 1: หน้าหลัก (Dashboard) - ข้อมูลรายวันเสมอ
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

    # สำหรับหน้าหลัก จะบังคับดูแค่ 1 คืนเสมอ (18:00 เมื่อวาน ถึง 18:00 วันนี้)
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
            if st.session_state.last_sent_date != current_date:
                status = send_line_message(report_msg)
                if status == 200:
                    st.session_state.last_sent_date = current_date
                    st.toast(f"ส่งรายงานอัตโนมัติตามนัดตอน {alert_time.strftime('%H:%M')} สำเร็จ!", icon="✅")
    else:
        st.info("ไม่มีข้อมูลการนอนหลับในคืนวันที่คุณเลือก")

# ------------------------------------------
# หน้าที่ 2: กราฟสถิติ (Statistics) - แบบเลือกช่วงเวลาได้
# ------------------------------------------
elif page == "📈 กราฟสถิติ (Statistics)":
    st.title("📈 กราฟวิเคราะห์พฤติกรรมการนอนหลับ")
    
    # 🌟 เมนูเลือกช่วงเวลาสถิติ
    time_range = st.selectbox("📅 เลือกช่วงเวลาการดูสถิติ:", 
                              ["รายวัน (1 คืน)", "รายสัปดาห์ (7 วันย้อนหลัง)", "รายเดือน (30 วันย้อนหลัง)", "รายปี (365 วันย้อนหลัง)"])
    
    # คำนวณวันย้อนหลังตามตัวเลือก
    if time_range == "รายวัน (1 คืน)":
        days_back = 1
    elif time_range == "รายสัปดาห์ (7 วันย้อนหลัง)":
        days_back = 7
    elif time_range == "รายเดือน (30 วันย้อนหลัง)":
        days_back = 30
    else:
        days_back = 365
        
    start_time_stats = datetime.combine(selected_date - timedelta(days=days_back), dt_time(18, 0))
    end_time_stats = datetime.combine(selected_date, dt_time(18, 0))

    st.markdown(f"ข้อมูลตั้งแต่ **{start_time_stats.strftime('%d/%m/%Y')}** ถึง **{end_time_stats.strftime('%d/%m/%Y')}**")
    st.divider()

    df_stats = pd.DataFrame()
    if not df_all.empty:
        df_stats = df_all[(df_all['time'] >= start_time_stats) & (df_all['time'] <= end_time_stats)]

    if not df_stats.empty:
        col_chart1, col_chart2 = st.columns(2)
        
        # กราฟที่ 1: ความถี่ของการกรน (ปรับตามช่วงเวลาที่เลือก)
        with col_chart1:
            st.subheader("🗣️ ความถี่ของการกรน")
            snore_df = df_stats[df_stats['snore'] == "SNORING"].copy()
            if not snore_df.empty:
                # ถ้าดูรายวัน ให้กรุ๊ปข้อมูลเป็นรายชั่วโมง / ถ้าดูมากกว่านั้น ให้กรุ๊ปเป็นรายวัน
                if time_range == "รายวัน (1 คืน)":
                    snore_df['group'] = snore_df['time'].dt.strftime('%H:00')
                    st.caption("แสดงสถิติเป็นรายชั่วโมง")
                else:
                    snore_df['group'] = snore_df['time'].dt.strftime('%d/%m/%Y')
                    st.caption("แสดงสถิติรวมในแต่ละวัน")
                    
                snore_by_group = snore_df['group'].value_counts().sort_index()
                st.bar_chart(snore_by_group, color="#FF4B4B")
            else:
                st.success("ไม่พบการกรนในช่วงเวลานี้ เยี่ยมมากครับ!")

        # กราฟที่ 2: สัดส่วนท่านอนรวม
        with col_chart2:
            st.subheader("🛌 สัดส่วนท่านอน (รวมทั้งหมด)")
            st.caption("จำนวนครั้งที่ตรวจจับได้ในช่วงเวลานี้")
            pose_counts = df_stats['pose'].value_counts()
            if "WAITING" in pose_counts:
                pose_counts = pose_counts.drop("WAITING")
                
            if not pose_counts.empty:
                st.bar_chart(pose_counts, color="#1f77b4")
            else:
                st.info("ไม่มีข้อมูลท่านอนที่สมบูรณ์")
                
        # แสดงตารางข้อมูลดิบ
        st.divider()
        st.subheader("📋 ตารางข้อมูลบันทึกทั้งหมด (Log)")
        st.dataframe(
            df_stats[['time', 'snore', 'prob', 'pose']].sort_values(by='time', ascending=False),
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
