import cv2
import firebase_admin
from firebase_admin import credentials, db
import datetime
import time
import urllib.request
import numpy as np
import mediapipe as mp
import tensorflow as tf
import librosa
import requests
import threading
import json  # 🌟 เพิ่มสำหรับอ่านไฟล์ตั้งค่า
import os    # 🌟 เพิ่มสำหรับจัดการไฟล์

# ==========================================
# 🌟 0. ระบบจัดการ IP (Config File)
# ==========================================
CONFIG_FILE = "config.json"

def load_config():
    # ถ้ามีไฟล์ตั้งค่าอยู่แล้ว ให้โหลดขึ้นมา
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # ถ้ายังไม่มี ให้สร้างไฟล์ตั้งค่าพื้นฐานขึ้นมาใหม่
        default_config = {
            "MIC_IP": "http://172.20.10.2/audio.wav",
            "CAM_IP": "http://172.20.10.4"
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4)
        print("\n" + "="*50)
        print(f"⚠️ สร้างไฟล์ตั้งค่า '{CONFIG_FILE}' ให้ใหม่แล้ว!")
        print("กรุณาเปิดไฟล์ config.json เพื่อแก้ไข IP ให้ตรงกับบอร์ดของคุณ")
        print("แล้วค่อยเปิดโปรแกรมใหม่อีกครั้งนะครับ")
        print("="*50 + "\n")
        time.sleep(5)
        exit() # ปิดโปรแกรมเพื่อให้ผู้ใช้ไปแก้ IP ก่อน

# โหลดค่า IP มาเก็บไว้ในตัวแปร
app_config = load_config()
STREAM_URL = app_config["MIC_IP"]
CAM_URL = app_config["CAM_IP"]

# ==========================================
# 1. Firebase
# ==========================================
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://sleep-health-monitor-default-rtdb.asia-southeast1.firebasedatabase.app/'
    })

# ==========================================
# 2. โหลดโมเดลเสียง
# ==========================================
print("🧠 กำลังโหลดโมเดลเสียง...")
model = tf.keras.models.load_model("snore_model.keras")
print("✅ โหลดโมเดลเสียงสำเร็จ")

# ==========================================
# 3. ตัวแปร Global (ใช้งานข้าม Thread)
# ==========================================
SAMPLE_RATE = 16000
BLOCK_SIZE = 1024

audio_buffer = np.zeros(SAMPLE_RATE, dtype=np.int16)
buffer_lock = threading.Lock()

snore_status = "WAITING"
snore_prob = 0.0
pose_text = "WAITING"

# ==========================================
# 4. รับเสียง
# ==========================================
def receive_audio_stream():
    global audio_buffer
    print(f"⏳ ต่อไมค์: {STREAM_URL}")
    try:
        with requests.get(STREAM_URL, stream=True) as r:
            if r.status_code == 200:
                print("✅ รับเสียงแล้ว")
                for chunk in r.iter_content(chunk_size=BLOCK_SIZE):
                    if chunk:
                        audio_data = np.frombuffer(chunk, dtype=np.int32)
                        audio_data = (audio_data >> 14).astype(np.int16)
                        n_frames = len(audio_data)
                        with buffer_lock:
                            audio_buffer = np.roll(audio_buffer, -n_frames)
                            audio_buffer[-n_frames:] = audio_data
            else:
                print("❌ เข้า URL ไมค์ไม่ได้")
    except Exception as e:
        print("❌ error ไมค์:", e)

# ==========================================
# 5. แปลงเสียง
# ==========================================
def process_audio(audio_array):
    signal = audio_array.astype(np.float32)
    if np.max(np.abs(signal)) > 0:
        signal = signal / (np.max(np.abs(signal)) + 1e-6)

    mfcc = librosa.feature.mfcc(y=signal, sr=SAMPLE_RATE, n_mfcc=40)
    img = cv2.resize(mfcc, (128, 128))
    img = (img - img.min()) / (img.max() - img.min() + 1e-6)
    return img.reshape(128, 128, 1)

# ==========================================
# 6. AI Loop
# ==========================================
def snore_detection_loop():
    global snore_status, snore_prob
    while True:
        with buffer_lock:
            current_audio = np.copy(audio_buffer)

        if np.max(np.abs(current_audio)) > 0:
            img = process_audio(current_audio)
            img = np.expand_dims(img, axis=0)

            pred = model.predict(img, verbose=0)
            snore_prob = float(pred[0][0])
            snore_status = "SNORING" if snore_prob > 0.6 else "NORMAL"
            print(f"😴 เสียง: {snore_status} | {snore_prob:.3f}")

        time.sleep(5)

# ==========================================
# 7. Firebase Thread 
# ==========================================
def firebase_loop():
    global snore_status, snore_prob, pose_text
    while True:
        try:
            sensor_ref = db.reference('/sensor_data').get()
            current_temp = sensor_ref.get('temperature', 0) if sensor_ref else 0
            current_hum = sensor_ref.get('humidity', 0) if sensor_ref else 0

            now = datetime.datetime.now()
            
            # 🌟 สร้างชื่อโฟลเดอร์รายวัน (เช่น 2026-03-19)
            date_folder = now.strftime("%Y-%m-%d") 
            # สร้าง Key รายวินาที
            custom_key = now.strftime("%Y-%m-%d %H:%M:%S") 
            
            data = {
                "time": str(now),
                "snore": snore_status,
                "prob": round(snore_prob, 3),
                "pose": pose_text,
                "temp": current_temp,
                "hum": current_hum
            }

            # 🌟 ส่งข้อมูลไปที่ sleep_data -> โฟลเดอร์วันที่ -> คีย์เวลา
            db.reference(f'/sleep_data/{date_folder}').child(custom_key).set(data)
            print(f"☁️ ส่ง Firebase สำเร็จ: [{date_folder} / {custom_key}]")

        except Exception as e:
            print("❌ Firebase error:", e)

        time.sleep(10)

# ==========================================
# 8. กล้อง
# ==========================================
# 🌟 ใช้ CAM_URL ที่โหลดมาจาก config แทนการเขียนตายตัว
stream = None

print(f"⏳ กำลังต่อกล้อง: {CAM_URL}")
try:
    stream = urllib.request.urlopen(CAM_URL, timeout=10) 
    print("✅ กล้องเชื่อมต่อแล้ว")
except Exception as e:
    print("❌ กล้อง error:", e)

bytes_data = b''
mp_pose = mp.solutions.pose
pose_tracker = mp_pose.Pose()
mp_drawing = mp.solutions.drawing_utils

def detect_sleep_pose(landmarks, h):
    l = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
    r = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]
    diff = abs(l.y*h - r.y*h)
    return "Face up/down" if diff < 20 else "Side"

# ==========================================
# 9. Start Thread
# ==========================================
threading.Thread(target=receive_audio_stream, daemon=True).start()
threading.Thread(target=snore_detection_loop, daemon=True).start()
threading.Thread(target=firebase_loop, daemon=True).start()

time.sleep(3)

# ==========================================
# 10. LOOP กล้อง (Main Thread)
# ==========================================
while True:
    if stream is None:
        time.sleep(1)
        continue

    try:
        chunk = stream.read(4096)
        if not chunk:
            continue
        bytes_data += chunk
    except Exception as e:
        print("❌ สตรีมภาพหลุด!")
        stream = None
        continue

    a = bytes_data.find(b'\xff\xd8')
    b = bytes_data.find(b'\xff\xd9')

    if a != -1 and b != -1:
        jpg = bytes_data[a:b+2]
        bytes_data = bytes_data[b+2:]

        frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            continue

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = pose_tracker.process(rgb)

        if result.pose_landmarks:
            pose_text = detect_sleep_pose(result.pose_landmarks.landmark, frame.shape[0])
            mp_drawing.draw_landmarks(frame, result.pose_landmarks, mp_pose.POSE_CONNECTIONS)

        cv2.putText(frame, f"Pose: {pose_text}", (20, 40), 0, 1, (0,255,0), 2)
        cv2.putText(frame, f"Snore: {snore_status}", (20, 80), 0, 1, (0,0,255), 2)

        cv2.imshow("Sleep Monitor", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cv2.destroyAllWindows()
