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
API_ID  = "AKfycbwnagEE7HmRv6nlqFeDHkEM08-uXxF8iWRqqeQ7fhTxOJzvK8hMn5VQ5rJwis1O36tA"

# dataType
class UPLOAD_TYPE:
    APPEND = 1
    LOG = 2

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
        print_log_to_google_sheet(UPLOAD_TYPE.LOG, LOG_TYPE.INFO, "Wifi is connected.")
    
def disconnect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.disconnect()
    wlan.active(False)
    wlan.deinit()
    del wlan
        
    machine.Pin(23, machine.Pin.OUT).low()
    
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
    scan_ds_sensor()   
    ##====INIT_END====##

    ##====MAIN_LOOP_START====##
    while True:
        if network.WLAN(network.STA_IF).isconnected is False: connect_wifi()

        # 温度変換開始
        ds_sensor.convert_temp()
        time.sleep_ms(750)
            
        # 温度取得
        #t1 = read_temperature(SENSOR_1, 0)
        #t2 = read_temperature(SENSOR_2, 0)
        #t3 = read_temperature(SENSOR_3, 0)
        #t4 = read_temperature(SENSOR_4, 0)
        
        t1 = read_temperature(SENSOR_5, 0)
        t2 = read_temperature(SENSOR_5, 0)
        t3 = read_temperature(SENSOR_5, 0)
        t4 = read_temperature(SENSOR_5, 0)


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
