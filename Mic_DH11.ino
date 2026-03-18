#include <WiFi.h>
#include <WebServer.h>
#include <driver/i2s.h>
#include <Firebase_ESP_Client.h>

// นำเข้า Add-on สำหรับ Firebase
#include <addons/TokenHelper.h>
#include <addons/RTDBHelper.h>

// นำเข้าไลบรารีเซนเซอร์ DHT
#include "DHT.h"

// ==========================================
// 1. ตั้งค่า Wi-Fi และ Firebase (⚠️ แก้ไขตรงนี้)
// ==========================================
#define WIFI_SSID "Lazylife"
#define WIFI_PASSWORD "Lazy12345678"

#define DATABASE_URL "https://sleep-health-monitor-default-rtdb.asia-southeast1.firebasedatabase.app/"
#define DATABASE_SECRET "to2OzPEKzr8x7d7OjyEz7o9EwnGHaBohR4k2MdZX"

// ==========================================
// 2. ตั้งค่าเซนเซอร์ DHT11
// ==========================================
#define DHTPIN 4  // ต่อสาย DATA ของ DHT11 เข้าขา D4
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);

// ==========================================
// 3. ตั้งค่าไมโครโฟน INMP441 (I2S)
// ==========================================
#define I2S_WS 15   // L/R Clock (WS)
#define I2S_SD 32   // Serial Data (SD)
#define I2S_SCK 14  // Serial Clock (SCK)
#define I2S_PORT I2S_NUM_0

// ==========================================
// ตัวแปรระบบต่างๆ
// ==========================================
WebServer server(80);
FirebaseData fbdo;
FirebaseAuth auth;
FirebaseConfig config;

unsigned long previousMillis = 0;
const long interval = 5000;  // ส่งข้อมูลขึ้น Firebase ทุกๆ 5 วินาที

// ==========================================
// ฟังก์ชัน: ตั้งค่าไมโครโฟน
// ==========================================
void setupI2S() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = 16000,                          // สุ่มตัวอย่างเสียง 16kHz
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,  // ความละเอียด 16-bit
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,   // รับเสียงช่องซ้าย
    .communication_format = i2s_comm_format_t(I2S_COMM_FORMAT_I2S | I2S_COMM_FORMAT_I2S_MSB),
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 1024,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };
  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_SD
  };
  i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_PORT, &pin_config);
}

// ==========================================
// ฟังก์ชัน: ส่งค่า DHT11 ขึ้น Firebase
// ==========================================
void sendSensorDataToFirebase() {
  float h = dht.readHumidity();
  float t = dht.readTemperature();

  if (isnan(h) || isnan(t)) {
    Serial.println("⚠️ อ่านค่าจากเซนเซอร์ DHT ล้มเหลว!");
    return;
  }

  Serial.printf("🌡️ อุณหภูมิ: %.1f °C | 💧 ความชื้น: %.1f %%\n", t, h);

  FirebaseJson json;
  json.set("temperature", t);
  json.set("humidity", h);

  if (Firebase.RTDB.setJSON(&fbdo, "/sensor_data", &json)) {
    Serial.println("☁️ อัปโหลดข้อมูลอุณหภูมิสำเร็จ!");
  } else {
    Serial.println("❌ อัปโหลดพลาด: " + fbdo.errorReason());
  }
}

// ==========================================
// ฟังก์ชัน: สตรีมเสียงผ่านเว็บ
// ==========================================
void handleAudioStream() {
  WiFiClient client = server.client();

  // ส่ง Header บอกคอมพิวเตอร์ว่านี่คือสตรีมเสียงแบบสด
  client.println("HTTP/1.1 200 OK");
  client.println("Content-Type: application/octet-stream");
  client.println("Connection: keep-alive");
  client.println();

  Serial.println("🔗 คอมพิวเตอร์เชื่อมต่อเพื่อดึงเสียงแล้ว!");

  const int BLOCK_SIZE = 1024;
  uint8_t audioBuffer[BLOCK_SIZE];
  size_t bytes_read;

  // วนลูปส่งเสียงตราบใดที่คอมพิวเตอร์ยังเชื่อมต่ออยู่
  while (client.connected()) {
    // 1. อ่านเสียงจากไมค์
    i2s_read(I2S_PORT, audioBuffer, BLOCK_SIZE, &bytes_read, portMAX_DELAY);

    // 2. ส่งเสียงออกไปทาง Wi-Fi
    if (bytes_read > 0) {
      client.write(audioBuffer, bytes_read);
    }

    // 3. แทรกการทำงาน: ตรวจสอบเวลาเพื่อส่งอุณหภูมิขึ้น Firebase แบบไม่ให้เสียงสะดุด
    if (millis() - previousMillis >= interval) {
      previousMillis = millis();
      sendSensorDataToFirebase();
    }

    yield();  // ป้องกัน ESP32 ค้าง
  }
  Serial.println("🔌 คอมพิวเตอร์ตัดการเชื่อมต่อสตรีมเสียง");
}

void handleRoot() {
  server.send(200, "text/html;charset=utf-8", "<h1>สวัสดีจาก ESP32! นี่คือจากหน้าแรก</h1>");
}

// ==========================================
// Setup & Loop
// ==========================================
void setup() {
  Serial.begin(115200);

  // เริ่มต้นเซนเซอร์และไมค์
  dht.begin();
  setupI2S();

  // เชื่อมต่อ Wi-Fi
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("กำลังเชื่อมต่อ Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print(".");
    delay(300);
  }
  Serial.println("\n✅ เชื่อมต่อสำเร็จ! IP ของบอร์ดคือ: ");
  Serial.println(WiFi.localIP());

  // เริ่มต้น Firebase
  config.database_url = DATABASE_URL;
  config.signer.tokens.legacy_token = DATABASE_SECRET;
  Firebase.reconnectWiFi(true);
  Firebase.begin(&config, &auth);

  // ตั้งค่า URL สำหรับสตรีมเสียง (เช่น http://172.20.10.2//audio.wav)
  server.on("/audio.wav", handleAudioStream);
  server.on("/", handleRoot);
  server.begin();

  Serial.println("🎧 Audio Stream Server พร้อมทำงานแล้ว!");
}

void loop() {
  // รอรับการเชื่อมต่อจาก Python เพื่อสตรีมเสียง
  server.handleClient();

  // ทำงานในกรณีที่ไม่มีคอมพิวเตอร์มาเชื่อมต่อสตรีมเสียง
  // (บอร์ดก็ยังคงต้องส่งค่าอุณหภูมิขึ้น Firebase ทุก 5 วินาที)
  if (millis() - previousMillis >= interval) {
    previousMillis = millis();
    sendSensorDataToFirebase();
  }
}