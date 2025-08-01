"""
鱼缸智能监控系统 (FishTank Monitor System)

功能概述：
1. 环境数据监测：
   - 每分钟记录空气温湿度(DHT11传感器)
   - 每分钟记录水温(DS18B20传感器)
   - 数据存储到SQLite数据库
   
2. 水位监控：
   - 实时监测两个水位传感器状态(顶部和底部)
   - 水位异常时发送邮件警报(过高/过低)
   - 水位恢复正常时发送恢复通知
   
3. 报警系统：
   - 邮件通知功能(SMTP_SSL)
   - 避免重复报警机制
   - 系统启动通知

4. 配置管理：
   - 通过config.json文件集中管理所有设置
   - 支持自定义传感器引脚、数据库路径、邮件设置等

运行方式：
1. 安装依赖：
   sudo apt-get install python3-pip
   pip3 install Adafruit_DHT pytz RPi.GPIO tzlocal

2. 创建配置文件(config.json):
   {
     "dht11_pin": 5,
     "database_path": "/var/lib/fishtank/sensor_data.db",
     "timezone": "Asia/Shanghai",
     "top_sensor_pin": 25,
     "bottom_sensor_pin": 23,
     "email_sender": "your@email.com",
     "email_password": "your_password",
     "email_receiver": "alert@email.com",
     "smtp_server": "smtp.example.com",
     "smtp_port": 465
   }

3. 设置系统服务(可选)：
   sudo nano /etc/systemd/system/fishtank-monitor.service
   [Unit]
   Description=FishTank Monitor Service
   After=network.target
   
   [Service]
   ExecStart=/usr/bin/python3 /path/to/fishtank_monitor.py
   WorkingDirectory=/path/to/
   StandardOutput=inherit
   StandardError=inherit
   Restart=always
   User=pi
   
   [Install]
   WantedBy=multi-user.target
   
   sudo systemctl enable fishtank-monitor
   sudo systemctl start fishtank-monitor

4. 手动运行：
   python3 fishtank_monitor.py

文件结构说明：
- 日志系统：/var/log/fishtank_monitor.log
- 数据库存储：/var/lib/fishtank/sensor_data.db
- 配置文件：同目录下的config.json
"""

import sqlite3
import time
import logging
from datetime import datetime
import Adafruit_DHT
import glob
import os
import json
import pytz
import RPi.GPIO as GPIO
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import threading

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/fishtank_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('FishTankMonitor')

# 配置文件路径
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config_fishtank.json')

# 加载配置
def load_config():
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载配置失败: {str(e)}")
        return {
            "dht11_pin": 5,
            "database_path": "/var/lib/fishtank/sensor_data.db",
            "timezone": "Asia/Shanghai",
            "top_sensor_pin": 25,
            "bottom_sensor_pin": 23,
            "email_sender": "my@qiwen.cn",
            "email_password": "########",
            "email_receiver": "7740840@qq.com",
            "smtp_server": "smtp.qiye.aliyun.com",
            "smtp_port": 465
        }

config = load_config()

# 确保数据库目录存在
database_dir = os.path.dirname(config.get('database_path', '/var/lib/fishtank/sensor_data.db'))
os.makedirs(database_dir, exist_ok=True)


# 读取水温传感器
def get_water_temp():
    try:
        base_dir = '/sys/bus/w1/devices/'
        device_folder = glob.glob(base_dir + '28*')[0]
        device_file = device_folder + '/w1_slave'
        
        with open(device_file, 'r') as f:
            lines = f.readlines()
            if lines[0].strip()[-3:] == 'YES':
                temp_line = lines[1].find('t=')
                if temp_line != -1:
                    temp = float(lines[1][temp_line+2:]) / 1000.0
                    return temp
        return None
    except Exception as e:
        logger.error(f"读取水温失败: {str(e)}")
        return None

# 读取温湿度
def read_dht11():
    try:
        humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.DHT11, config['dht11_pin'])
        return temperature, humidity
    except Exception as e:
        logger.error(f"读取温湿度传感器失败: {str(e)}")
        return None, None

# 获取本地时间字符串
def get_local_time():
    tz = pytz.timezone(config.get('timezone', 'Asia/Shanghai'))
    return datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

# 记录传感器数据
def record_sensor_data():
    logger.info("启动传感器数据记录服务...")
    
    while True:
        try:
            air_temp, humidity = read_dht11()
            water_temp = get_water_temp()
            local_time = get_local_time()
            
            conn = sqlite3.connect(config.get('database_path', '/var/lib/fishtank/sensor_data.db'))
            c = conn.cursor()
            
            c.execute('''
                INSERT INTO sensor_data (timestamp, air_temp, humidity, water_temp)
                VALUES (?, ?, ?, ?)
            ''', (local_time, air_temp, humidity, water_temp))
            
            conn.commit()
            conn.close()
            
            logger.info(f"记录数据 [{local_time}]: 气温={air_temp}°C, 湿度={humidity}%, 水温={water_temp}°C")
        except Exception as e:
            logger.error(f"记录数据时出错: {str(e)}")
        
        time.sleep(300)

# 水位监控部分
def send_email(subject, content):
    try:
        message = MIMEText(content, 'plain', 'utf-8')
        message['From'] = Header("Miaoking", 'utf-8')
        message['To'] = Header(config['email_receiver'], 'utf-8')
        message['Subject'] = Header(subject, 'utf-8')

       
        with smtplib.SMTP_SSL(config['smtp_server'], config['smtp_port']) as server:
            server.login(config['email_sender'], config['email_password'])
            server.sendmail(config['email_sender'], [config['email_receiver']], message.as_string())
        logger.info("邮件发送成功")
    except Exception as e:
        logger.error(f"发送邮件失败: {str(e)}")

class WaterMonitor:
    def __init__(self):
        self.last_alert_status = {"high": False, "low": False}
        GPIO.setmode(GPIO.BCM)
        self.top_pin = config.get('top_sensor_pin', 25)
        self.bottom_pin = config.get('bottom_sensor_pin', 23)
        
        GPIO.setup(self.top_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.bottom_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        logger.info("水位传感器初始化完成")

    def check_and_alert(self, water_level):
        if water_level == "high" and not self.last_alert_status["high"]:
            subject = "【紧急】鱼缸水位过高警报"
            content = "鱼缸水位已达到过高位置，请立即检查！当前水位状态：高"
            threading.Thread(target=send_email, args=(subject, content)).start()
            self.last_alert_status["high"] = True
            self.last_alert_status["low"] = False
            
        elif water_level == "low" and not self.last_alert_status["low"]:
            subject = "【紧急】鱼缸水位过低警报"
            content = "鱼缸水位已降至过低位置，请立即检查！当前水位状态：低"
            threading.Thread(target=send_email, args=(subject, content)).start()
            self.last_alert_status["low"] = True
            self.last_alert_status["high"] = False
            
        elif water_level == "normal":
            if self.last_alert_status["high"] or self.last_alert_status["low"]:
                subject = "【恢复】鱼缸水位恢复正常"
                content = "鱼缸水位已恢复正常水平"
                threading.Thread(target=send_email, args=(subject, content)).start()
            self.last_alert_status["high"] = False
            self.last_alert_status["low"] = False

    def get_water_level(self):
        try:
            top_sensor = GPIO.input(self.top_pin)
            bottom_sensor = GPIO.input(self.bottom_pin)
            
            if top_sensor == GPIO.LOW and bottom_sensor == GPIO.LOW:
                return "high"
            elif bottom_sensor == GPIO.LOW and top_sensor == GPIO.HIGH:
                return "normal"
            elif top_sensor == GPIO.HIGH and bottom_sensor == GPIO.HIGH:
                return "low"
            else:
                return "unknown"
                
        except Exception as e:
            logger.error(f"读取传感器错误: {str(e)}")
            return "error"

    def monitor_water_level(self):
        logger.info("启动水位监控服务...")
        try:
            # 发送启动通知
            subject = "鱼缸水位监控系统开始工作"
            content = "水位监控系统已启动，开始监控鱼缸水位状态。"
            send_email(subject, content)
            
            while True:
                water_level = self.get_water_level()
                self.check_and_alert(water_level)
                
                status_msg = {
                    "high": "\033[91m水位过高\033[0m",
                    "normal": "\033[92m水位正常\033[0m",
                    "low": "\033[93m水位过低\033[0m",
                    "error": "\033[91m传感器错误\033[0m",
                    "unknown": "\033[90m未知状态\033[0m"
                }.get(water_level, "\033[90m未知状态\033[0m")
                
                logger.info(
                    f"顶部传感器: {'有水' if GPIO.input(self.top_pin) == GPIO.LOW else '无水'} | "
                    f"底部传感器: {'有水' if GPIO.input(self.bottom_pin) == GPIO.LOW else '无水'} | "
                    f"状态: {status_msg}"
                )
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("水位监控服务停止")
        finally:
            GPIO.cleanup()
            logger.info("GPIO资源已清理")

def main():
    # 初始化数据库
    #init_database()
    
    # 确保时区正确
    try:
        import tzlocal
        local_tz = tzlocal.get_localzone()
        logger.info(f"当前系统时区: {local_tz}")
    except ImportError:
        logger.warning("未安装 tzlocal 包，无法验证系统时区")
    
    # 创建水位监控器
    water_monitor = WaterMonitor()
    
    # 启动传感器记录线程
    sensor_thread = threading.Thread(target=record_sensor_data, daemon=True)
    sensor_thread.start()
    
    # 启动水位监控（主线程）
    water_monitor.monitor_water_level()

if __name__ == '__main__':
    main()