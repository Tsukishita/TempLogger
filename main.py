import sys
from io import StringIO
import network
import time
from machine import Pin
from machine import Timer
import urequests
import json
import onewire
import ds18x20
import gc

led = Pin('LED', Pin.OUT)

#DS18B20
dat = Pin(16)
ds_sensor = ds18x20.DS18X20(onewire.OneWire(dat))

# =========================
# センサーROM ID固定
# 自分のROM IDへ変更する
# =========================
# 室温
SENSOR_1 = b'(\xff\xb7#\x00\x00\x00\xae'
# 水槽1
SENSOR_2 = b'(\xc2)"\x00\x00\x00\x93'
# 水槽2
SENSOR_3 = b'(\xf9\xa1#\x00\x00\x00\xfc'
# 水槽3
SENSOR_4 = b'(1\x9f#\x00\x00\x00\xe4'
# 予備
SENSOR_5 = b'(SD"\x00\x00\x00\xe8'

# Wi-Fi情報
SSID = "TSUKISHITA-TP"
PASSWORD = "moonlights"

#Sheets APIの設定
API_URL = "https://script.google.com/macros/s/"

# APIキー
API_ID  = "AKfycbyCckHpUljQDeL4M2Bf8lq0zrBWT9CZbBYQVKOAdI3UKhZQ5dg8Uz0BAfCH1jzhqQE"

# OTAアップデート設定
MAIN_FILE = "main.py"
BACKUP_FILE = "backup.py"

SETTINGS_FILE = "settings.json"
VERSION_FILE = "version.json"

SETTINGS_URL = "{}{}/exec?mode=settings".format(API_URL,API_ID)

CURRENT_VERSION = 1

# dataType
class UPLOAD_TYPE:
    APPEND = 1
    LOG = 2
    UPDATE_VERSION = 3

class LOG_TYPE:
    INFO = 1
    WARNING = 2
    ERROR = 3
       
def scan_ds_sensor():
    roms = ds_sensor.scan()
    if roms.count != 0:
        for rom in roms:
            print('Found DS devices: ', rom)
    else:
        raise("センサーが接続されていません。")
# =========================
# 温度取得関数
# =========================
def read_temperature(sensor_rom, calibration):
    retryCount = 0

    while True :
        temp = ds_sensor.read_temp(sensor_rom)
        if retryCount > 3:
            raise Exception("センサーから温度取得できませんでした。Sensor_Address: {}".format(sensor_rom));
        elif temp is not None and temp != 0:
            temp += calibration
            return round(temp, 2)
        
        retryCount += 1
        Timer.sleep(10)
        
def connect_wifi():
    machine.Pin(23, machine.Pin.OUT).high()
            
    # WLAN有効化
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    # Wi-Fi接続
    print("Wi-Fi接続中...")
    wlan.connect(SSID, PASSWORD)

    # 接続待機
    timeout = 10  # 秒
    while timeout > 0:
        if wlan.status() < 0 or wlan.status() >= 3:
            break
        timeout -= 1
        time.sleep(1)

    # 接続結果確認
    if wlan.status() != 3:
        raise Exception("Wifiの接続に失敗しました。")
    else:
        print("接続成功!")
        machine.Pin("LED", machine.Pin.OUT).high()
        print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.INFO, "Wifi is connected.")
    
def disconnect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.disconnect()
    wlan.active(False)
    wlan.deinit()
    del wlan
        
    machine.Pin(23, machine.Pin.OUT).low()
    
    
# =========================================================
# GASからSettings取得
# =========================================================
def load_settings_from_gas():
    settings = {}
    try:
        print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.INFO,"Loading Settings...")
        response = urequests.get(SETTINGS_URL)
        if response.status_code == 200:
            settings = response.json()

            print(settings)
            print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.INFO,"Settings Load Complete.")

        response.close()
    except Exception as e:
        output = StringIO()
        sys.print_exception(e, output)
        print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.ERROR,"Settings Load Error:{}".format(output.getvalue()))

    return settings

# =========================================================
# Flash保存
# =========================================================
def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f)
        print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.INFO, "Settings Saved.")
        return True
    except Exception as e:
        output = StringIO()
        sys.print_exception(e, output)   
        print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.ERROR, "Flash Save Error: {}".format(output.getvalue()))
        return False 

# =========================================================
# Flash読込
# =========================================================
def load_settings_flash():
    try:
        with open(SETTINGS_FILE, "r") as f:
            settings = json.load(f)

        print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.INFO, "Flash Settings Loaded")
        return settings
    except Exception as e:
        output = StringIO()
        sys.print_exception(e, output)   
        print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.ERROR, "Flash Load Error: {}".format(output.getvalue()))    
        return {}

# =========================================================
# バージョン保存
# =========================================================
def save_version(version):
    try:
        with open(VERSION_FILE, "w") as f:
            json.dump({
                "version": version
            }, f)
            print(version)
            CURRENT_VERSION = version
    except Exception as e:
        output = StringIO()
        sys.print_exception(e, output)   
        print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.ERROR, "Flash Save Error: {}".format(output.getvalue()))    


# =========================================================
# バージョン取得
# =========================================================
def load_version():
    try:
        with open(VERSION_FILE, "r") as f:
            data = json.load(f)
        return int(data["version"])
    except:
        return CURRENT_VERSION

# =========================================================
# main.pyバックアップ
# =========================================================
def backup_current_main():
    try:
        with open(MAIN_FILE, "r") as src:
            code = src.read()
        with open(BACKUP_FILE, "w") as dst:
            dst.write(code)
            print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.INFO, "Backup Created.")    
        return True
    except Exception as e:
        output = StringIO()
        sys.print_exception(e, output)   
        print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.ERROR, "Backup Error: {}".format(output.getvalue()))    
        return False

# =========================================================
# OTA更新
# =========================================================
def ota_update(settings):
    try:
        ota_flag = settings.get("OTA_UPDATE", False)
        if ota_flag is False:
            print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.INFO, "OTA Skip.")
            return False

        new_version = int(settings.get("OTA_VERSION", "1"))
        current_version = load_version()

        print("Current Version:", current_version)
        print("New Version:", new_version)

        if new_version <= current_version:
            print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.INFO, "Already Latest.")
            return False

        ota_url = settings.get("OTA_URL", "")

        if ota_url == "":
            print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.ERROR, "OTA URL Missing.")
            return False

        print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.INFO, "Downloading New Firmware...")

        response = urequests.get(ota_url)
        if response.status_code != 200:
            print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.ERROR, "Download Failed.")
            return False

        new_code = response.text
        response.close()

        # backup
        if not backup_current_main():
            return False

        # new main.py
        with open(MAIN_FILE, "w") as f:
            f.write(new_code)
        
        save_version(new_version)
        update_current_version(new_version)
        
        print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.INFO, "OTA Success. System Reboot.")

        time.sleep(3)
        machine.reset()
        return True
    except Exception as e:
        output = StringIO()
        sys.print_exception(e, output)   
        print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.ERROR, "OTA Error:{}".format(output.getvalue()))
        restore_backup()
        return False
    
# =========================================================
# backup復元
# =========================================================
def restore_backup():
    try:
        print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.INFO, "Restoring Backup...")
        with open(BACKUP_FILE, "r") as src:
            code = src.read()
        with open(MAIN_FILE, "w") as dst:
            dst.write(code)
        print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.INFO, "Restore Success")
    except Exception as e:
        output = StringIO()
        sys.print_exception(e, output)   
        print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.ERROR, "Restore Failed:{}".format(output.getvalue()))
        
# =========================================================
# OTA成功後
# GASへPOST送信して
# CURRENT_VERSION更新
# =========================================================
def update_current_version(version):
    try: 
        print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.INFO, "Updating Current Version...")
        
        url = API_URL + API_ID +  "/exec" 
        data = {
          "dataType": UPLOAD_TYPE.UPDATE_VERSION,
          "version": version,
        }

        # リクエストヘッダーを追加
        headers = {
            "Content-Type": "application/json",  # 必要に応じて設定
            "User-Agent": "Python-urequests"
        }

        # JSONデータを文字列に変換
        json_data = json.dumps(data)
        headers["Content-Length"] = str(len(json_data))  # Content-Lengthを手動で設定

        # リクエスト送信
        response = urequests.post(url,headers=headers, data=json_data)
        if response.status_code is not 200:
            raise Exception("CURRENT＿VERSIONの更新に失敗しました。Status_Code:{}, Reason:{}".format(response.status_code,response.reason))

        print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.INFO, "Updating is complete.")
        response.close()
    except Exception as e:
        print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.ERROR, "Current Version Update Error:{}".format(e))
    
def post_to_google_sheets(dataType, data1, data2, data3, data4):
    try:      
        # Google Sheets APIの設定
        API_URL = "https://script.google.com/macros/s/"

        # データのフォーマット
        value1 = "{:.2f}".format(data1)
        value2 = "{:.2f}".format(data2)
        value3 = "{:.2f}".format(data3)
        value4 = "{:.2f}".format(data4)

        url = API_URL + API_ID +  "/exec" 
        
        data = {
          "dataType": dataType,
          "data1": value1,
          "data2": value2,
          "data3": value3,
          "data4": value4
        }
        print(data)
        
        # リクエストヘッダーを追加
        headers = {
            "Content-Type": "application/json",  # 必要に応じて設定
            "User-Agent": "Python-urequests"
        }

        # JSONデータを文字列に変換
        json_data = json.dumps(data)
        headers["Content-Length"] = str(len(json_data))  # Content-Lengthを手動で設定

        # リクエスト送信
        response = urequests.post(url,headers=headers, data=json_data)
        if response.status_code is not 200:
            raise Exception("GoogleActionSprictへの送信に失敗しました。Status_Code:{}, Reason:{}".format(response.status_code,response.reason))
        
        response.close()
        
        return
    except Exception as e:
        output = StringIO()
        sys.print_exception(e, output)
        print(output.getvalue())   
        
def print_log_to_google_sheet(dataType, logType, message):
    try:
        url = API_URL + API_ID +  "/exec" 

        data = {
          "dataType": dataType,
          "data1": logType,
          "data2": message
        }
        print(data)
        
        # リクエストヘッダーを追加
        headers = {
            "Content-Type": "application/json",  # 必要に応じて設定
            "User-Agent": "Python-urequests"
        }

        # JSONデータを文字列に変換
        json_data = json.dumps(data)
        headers["Content-Length"] = str(len(json_data))  # Content-Lengthを手動で設定

        # リクエスト送信
        response = urequests.post(url,headers=headers, data=json_data)
        if response.status_code is not 200:
            raise Exception("GoogleActionSprictへの送信に失敗しました。Status_Code:{}, Reason:{}".format(response.status_code,response.reason))
        
        response.close()
        
        return
    except Exception as e:
        output = StringIO()
        sys.print_exception(e, output)
        print(output.getvalue())
        
# メインループ
try:
    ##====INIT_START====##
    connect_wifi()
    
    settings = {}
    if network.WLAN(network.STA_IF).isconnected:
        settings = load_settings_from_gas()
    if settings:
        save_settings(settings)
    else:
        settings = load_settings_flash()
        
    scan_ds_sensor()   
    ##====INIT_END====##
    
    # =========================================================
    # OTA実行
    # =========================================================
    ota_update(settings)
    
    ##====MAIN_LOOP_START====##
    while True:
        if network.WLAN(network.STA_IF).isconnected is False: connect_wifi()

        # 温度変換開始
        ds_sensor.convert_temp()
        time.sleep_ms(750)
            
        # 温度取得
        t1 = read_temperature(SENSOR_1, 0)
        t2 = read_temperature(SENSOR_2, 0)
        t3 = read_temperature(SENSOR_3, 0)
        t4 = read_temperature(SENSOR_4, 0)

        post_to_google_sheets(UPLOAD_TYPE.APPEND, t1, t2, t3, t4)
        print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.INFO, "Success to upload temperture record.")
        
        disconnect_wifi()
        gc.collect()
        time.sleep(60*5)
    ##====MAIN_LOOP_END====##
except Exception as e:
    output = StringIO()
    sys.print_exception(e, output)
    
    print(network.WLAN(network.STA_IF).status())
    if network.WLAN(network.STA_IF).isconnected() is True:
        print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.ERROR, output.getvalue())
        print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.ERROR, "PicoW is stopped.")
        print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.INFO, "Reboot at 1 min.")
    else:
        print(output.getvalue())
        print("Reboot at 1 min.")
    
    Timer().init(freq=5, mode=Timer.PERIODIC, callback=lambda _: led.toggle())

    time.sleep(60)
    machine.reset()

