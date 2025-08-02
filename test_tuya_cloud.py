import tinytuya

# 🔑 Replace these with your real Tuya Cloud project info
ACCESS_ID = "your-access-id"
ACCESS_SECRET = "your-access-secret"
DEVICE_ID = "bf1fb51a6032098478au4s"   # Already known
API_REGION = "ap"  # Use "ap" for Asia, "eu", "us", or "cn" as needed

# 🌐 Cloud connection
cloud = tinytuya.Cloud(
    apiRegion=API_REGION,
    apiKey=ACCESS_ID,
    apiSecret=ACCESS_SECRET,
    apiDeviceID=DEVICE_ID
)

# ✅ Test 1: List Devices
devices = cloud.getdevices()
print("📡 Your Devices:\n", devices)

# ✅ Test 2: Get current status
status = cloud.getstatus(DEVICE_ID)
print("🔌 Current Device Status:\n", status)

# ✅ Test 3: Turn ON
print("✅ Turning ON...")
cloud.sendcommand(DEVICE_ID, [{"code": "switch_1", "value": True}])

# ✅ Test 4: Turn OFF
# print("⛔ Turning OFF...")
# cloud.sendcommand(DEVICE_ID, [{"code": "switch_1", "value": False}])
