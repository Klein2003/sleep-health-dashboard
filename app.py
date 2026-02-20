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
# 2. ตั้งค่าเชื่อมต่อ Firebase (เวอร์ชัน Cloud ปลอดภัย 100%)
# ==========================================
if not firebase_admin._apps:
    # ดึงกุญแจจาก "ตู้เซฟ (Secrets)" ของ Streamlit แทนการอ่านไฟล์ json ตรงๆ
    firebase_credentials = dict(st.secrets["firebase"])
    cred = credentials.Certificate(firebase_credentials)
    
    firebase_admin.initialize_app(cred, {
        # ⚠️ เปลี่ยนลิงก์ตรงนี้เป็น URL ของคุณเหมือนเดิมครับ
        'databaseURL': 'https://sleep-health-monitor-default-rtdb.asia-southeast1.firebasedatabase.app/'
    })

# ==========================================
# 3. หน้าตาเว็บ Dashboard (Streamlit)
# ==========================================
st.set_page_config(page_title="Sleep Health Monitor", layout="centered")
st.title("💤 AI ตรวจจับสุขภาพการนอน")

# ปุ่มสำหรับกดดึงข้อมูลล่าสุดจาก Firebase
if st.button("🔄 อัปเดตข้อมูลจากเซนเซอร์", type="primary"):
    
    # ดึงข้อมูลจากโฟลเดอร์ sleep_data
    ref = db.reference('sleep_data')
    all_data = ref.get()
    
    if all_data:
        # ข้อมูลใน Firebase ที่ใช้ .push() จะสุ่มคีย์ยาวๆ มาให้ เราต้องดึงอันล่าสุดมา (ตัวสุดท้าย)
        latest_key = list(all_data.keys())[-1]
        latest_data = all_data[latest_key]
        
        # แสดงผลบนหน้าเว็บ
        st.subheader("📊 สถานะปัจจุบัน")
        col1, col2, col3 = st.columns(3)
        col1.metric("เวลาบันทึก", latest_data.get("timestamp", "-")[:16])
        col2.metric("ท่านอน", latest_data.get("sleep_pose", "-"))
        col3.metric("เสียงกรน", "ตรวจพบ!" if latest_data.get("snoring") else "ปกติ")
        
        # ถ้าระบุว่ามีการกรน ให้ส่ง LINE แจ้งเตือน
        if latest_data.get("snoring") == True:
            st.warning(f"⚠️ {latest_data.get('warning_level')}")
            
            # ส่งแจ้งเตือน
            dashboard_url = "https://sleep-health-dashboard-3xmgjcul8ysrdk3hwazkyp.streamlit.app/" # สามารถเปลี่ยนเป็นลิงก์ที่ต้องการได้
            msg = f"\n⚠️ แจ้งเตือนจากระบบ!\nท่านอน: {latest_data.get('sleep_pose')}\nสถานะ: {latest_data.get('warning_level')}\nดูข้อมูล: {dashboard_url}"
            
            line_status = send_line_message(msg)
            if line_status == 200:
                st.success("ส่งแจ้งเตือนเข้า LINE สำเร็จ!")
            else:
                st.error("ส่ง LINE ไม่สำเร็จ")
    else:

        st.info("ยังไม่มีข้อมูลในระบบ")
