import streamlit as st
import requests
import json
import firebase_admin
from firebase_admin import credentials, db

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
    data = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}]
    }
    response = requests.post(url, headers=headers, data=json.dumps(data))
    return response.status_code

# ==========================================
# 2. ตั้งค่าเชื่อมต่อ Firebase (รันบน Streamlit Cloud)
# ==========================================
if not firebase_admin._apps:
    # 🌟 ดึงกุญแจจาก "ตู้เซฟ (Secrets)" ของ Streamlit 
    firebase_credentials = dict(st.secrets["firebase"])
    cred = credentials.Certificate(firebase_credentials)
    
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://sleep-health-monitor-default-rtdb.asia-southeast1.firebasedatabase.app/'
    })

# ==========================================
# 3. หน้าตาเว็บ Dashboard (Streamlit)
# ==========================================
st.set_page_config(page_title="Sleep Health Dashboard", page_icon="💤", layout="centered")

st.title("💤 AI ตรวจจับสุขภาพการนอน")
st.markdown("มอนิเตอร์สภาพแวดล้อมและพฤติกรรมการนอนหลับแบบ Real-time")

st.divider()

# ปุ่มสำหรับกดดึงข้อมูลล่าสุดจาก Firebase
if st.button("🔄 อัปเดตข้อมูลล่าสุด", type="primary", use_container_width=True):
    
    # ---------------------------------
    # ดึงข้อมูลอุณหภูมิ/ความชื้น
    # ---------------------------------
    ref_sensor = db.reference('sensor_data')
    sensor_data = ref_sensor.get()
    
    temp = sensor_data.get('temperature', '-') if sensor_data else '-'
    hum = sensor_data.get('humidity', '-') if sensor_data else '-'

    st.subheader("🌡️ สภาพแวดล้อมห้องนอน")
    col_t, col_h = st.columns(2)
    col_t.metric("อุณหภูมิ", f"{temp} °C")
    col_h.metric("ความชื้นสัมพัทธ์", f"{hum} %")
    
    st.divider()

    # ---------------------------------
    # ดึงข้อมูลการนอน
    # ---------------------------------
    ref_sleep = db.reference('sleep_data')
    all_sleep_data = ref_sleep.get()
    
    if all_sleep_data:
        # ดึงข้อมูลก้อนล่าสุด (ตัวสุดท้ายใน Dictionary)
        latest_key = list(all_sleep_data.keys())[-1]
        latest_data = all_sleep_data[latest_key]
        
        # ดึงค่าต่างๆ ออกมา
        db_time = latest_data.get("time", "-")[:19] # ตัดเศษวินาทีออก
        db_pose = latest_data.get("pose", "-")
        db_snore = latest_data.get("snore", "-")
        db_prob = latest_data.get("prob", 0.0)
        
        st.subheader("🛌 สถานะการนอนหลับล่าสุด")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("เวลาบันทึก", db_time)
        col2.metric("ท่านอน", db_pose)
        
        # ตกแต่งสีให้สถานะการกรน
        if db_snore == "SNORING":
            col3.metric("เสียงกรน", "🔴 ตรวจพบ!")
        elif db_snore == "NORMAL":
            col3.metric("เสียงกรน", "🟢 ปกติ")
        else:
            col3.metric("เสียงกรน", "⏳ รอวิเคราะห์")

        # แถบแสดงความน่าจะเป็นในการกรน
        st.progress(min(db_prob, 1.0), text=f"ความน่าจะเป็นที่กำลังกรน: {db_prob*100:.1f}%")
        
        # ---------------------------------
        # ระบบส่ง LINE แจ้งเตือน
        # ---------------------------------
        if db_snore == "SNORING":
            st.error("⚠️ ผู้ใช้งานกำลังกรนเสียงดัง ระบบกำลังแจ้งเตือนไปยัง LINE!")
            
            # จัดฟอร์แมตข้อความส่ง LINE
            msg = f"\n⚠️ แจ้งเตือนจากระบบ!\n🛌 ท่านอน: {db_pose}\n🗣️ สถานะ: มีอาการกรน ({db_prob*100:.1f}%)\n🌡️ อุณหภูมิห้อง: {temp}°C"
            
            line_status = send_line_message(msg)
            if line_status == 200:
                st.toast("ส่งแจ้งเตือนเข้า LINE สำเร็จ!", icon="✅")
            else:
                st.toast("ส่ง LINE ไม่สำเร็จ", icon="❌")
    else:
        st.info("ยังไม่มีข้อมูลการนอนในระบบ")
