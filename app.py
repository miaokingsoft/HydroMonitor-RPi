'''

pip install Adafruit-DHT
执行程序用 sudo python app.py
水位的监控报警发邮件到7740840@qq.com,单独运行 python shui.py

sudo python fishtank.py
包含水温、室温、湿度记录、水位的监控异常发邮件

V1.1 新增投喂按钮，投喂间隔2小时，投喂后会记录日志，调用舵机进行投喂
V1.2 新增喂食计划管理，支持多计划设置，自动喂食
'''

import os
import json
import time
import threading
import logging
import traceback
import socket
import psutil
from flask import Flask, render_template, jsonify, request
from rpi_ws281x import PixelStrip, Color
import RPi.GPIO as GPIO
import glob
import Adafruit_DHT
from datetime import datetime, timedelta
import sqlite3
import atexit

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
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')

# 加载配置
# 增强的配置加载函数
def load_config():
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
            
            # 确保颜色是数组格式
            def ensure_color_format(color, default):
                if isinstance(color, dict):
                    return [color.get('r', default[0]), 
                            color.get('g', default[1]), 
                            color.get('b', default[2])]
                if isinstance(color, list) and len(color) == 3:
                    return color
                return default
            
            # 修复颜色格式
            config['active_color'] = ensure_color_format(
                config.get('active_color'), [0, 100, 0]
            )
            config['idle_color'] = ensure_color_format(
                config.get('idle_color'), [0, 0, 0]
            )
            
            # 设置默认值
            config.setdefault('led_count', 10)
            config.setdefault('led_brightness', 230)
            config.setdefault('buzzer_pin', 17)
            config.setdefault('buzzer_beep_duration', 0.2)
            config.setdefault('buzzer_beep_interval', 0.1)
            config.setdefault('fan_pin', 24)  # 添加风扇引脚
            config.setdefault('fan_enabled', False)  # 添加风扇状态
            
            logger.info(f"加载配置: {config}")
            return config
    except FileNotFoundError:
        return create_default_config()
    except Exception as e:
        logger.error(f"加载配置失败: {str(e)}，使用默认配置")
        return create_default_config()

def create_default_config():
    """创建默认配置"""
    default_config = {
        "led_count": 10,
        "led_brightness": 230,
        "active_color": [0, 100, 0],
        "idle_color": [0, 0, 0],
        "buzzer_pin": 17,
        "buzzer_beep_duration": 0.2,
        "buzzer_beep_interval": 0.1,
        "fan_pin": 24,  # 风扇引脚
        "fan_enabled": False,  # 风扇状态
        "pump_pin": 6,  # 气泵引脚原来是 (GPIO22)
        "pump_enabled": False,  # 气泵状态
        "water_pump_pin": 19,  # 水泵引脚 (GPIO19)
        "water_pump_enabled": False,  # 水泵状态
        "water_sensor_top_pin": 25,
        "water_sensor_bottom_pin": 23,
        "dht11_pin": 5,
        "database_path": "/var/lib/fishtank/sensor_data.db"
    }
    try:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(default_config, f, indent=4)
    except Exception as e:
        logger.error(f"创建默认配置失败: {str(e)}")
    return default_config

# 全局变量
config = load_config()
strip = None
is_active = False
last_activity_time = 0
active_connections = set()
lock = threading.Lock()
fan_enabled = False  # 风扇状态
pump_enabled = False  # 气泵状态
water_pump_enabled = False  # 水泵状态
water_pump_timer = None #执行时间（秒）
water_level = "unknown"  # 水位状态：high/normal/low/unknown
dht_sensor = Adafruit_DHT.DHT11
current_temp = None #室温
current_humidity = None #湿度
current_water_temp = None #鱼缸水温

last_feed_time = 0  # 记录上次投喂时间（时间戳）
feed_lock = threading.Lock()  # 投喂操作锁

# 在全局配置中添加数据库路径
config.setdefault('database_path', '/var/lib/fishtank/sensor_data.db')

# 确保数据库目录存在
database_dir = os.path.dirname(config.get('database_path'))
os.makedirs(database_dir, exist_ok=True)

# 创建 Flask 应用
app = Flask(__name__, 
            template_folder='templates',
            static_folder='static',
            static_url_path='/static')

# 初始化GPIO
def init_gpio():
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(config['buzzer_pin'], GPIO.OUT)
        GPIO.output(config['buzzer_pin'], GPIO.LOW)
        # 初始化风扇引脚
        GPIO.setup(config['fan_pin'], GPIO.OUT)
        global fan_enabled
        fan_enabled = config['fan_enabled']
        # 继电器低电平触发
        #GPIO.output(config['fan_pin'], GPIO.HIGH if fan_enabled else GPIO.LOW)
        GPIO.output(config['fan_pin'], GPIO.LOW if fan_enabled else GPIO.HIGH)
        # 继电器高电平触发
       
        #GPIO.output(config['pump_pin'], GPIO.LOW if fan_enabled else GPIO.HIGH)

        # 初始化气泵引脚 (GPIO6)
        GPIO.setup(config['pump_pin'], GPIO.OUT)
        global pump_enabled
        pump_enabled = config['pump_enabled']
        #GPIO.output(config['pump_pin'], GPIO.HIGH if fan_enabled else GPIO.LOW)
        GPIO.output(config['pump_pin'], GPIO.LOW if fan_enabled else GPIO.HIGH)

        # 初始化水泵引脚 (GPIO19)
        GPIO.setup(config['water_pump_pin'], GPIO.OUT)
        global water_pump_enabled
        water_pump_enabled = config['water_pump_enabled']
        GPIO.output(config['water_pump_pin'], GPIO.LOW if water_pump_enabled else GPIO.HIGH)
   

        # 初始化水位传感器引脚
        GPIO.setup(config['water_sensor_top_pin'], GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(config['water_sensor_bottom_pin'], GPIO.IN, pull_up_down=GPIO.PUD_UP)

        logger.info("GPIO初始化成功")
        return True
    except Exception as e:
        logger.error(f"GPIO初始化失败: {str(e)}")
        return False

def init_servo():
    """初始化舵机"""
    try:
        from sg90180 import SG90Servo
        global servo
        servo = SG90Servo(gpio_pin=26)
        logger.info("舵机初始化成功")
        return True
    except Exception as e:
        logger.error(f"舵机初始化失败: {str(e)}")
        return False    

# 水温读取函数
def get_water_temp():
    """读取DS18B20水温传感器"""
    try:
        # 查找传感器设备
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

# 风扇控制函数
def set_fan_state(enabled):
    """设置风扇状态"""
    global fan_enabled
    fan_enabled = enabled

    #GPIO.output(config['fan_pin'], GPIO.HIGH if enabled else GPIO.LOW)
    GPIO.output(config['fan_pin'], GPIO.LOW if enabled else GPIO.HIGH)
    logger.info(f"风扇状态已设置为: {'开启' if enabled else '关闭'}")
    return True

# 新增气泵控制函数
def set_pump_state(enabled):
    """设置气泵状态"""
    global pump_enabled
    pump_enabled = enabled
    
    # 继电器低电平触发
    #GPIO.output(config['pump_pin'], GPIO.HIGH if enabled else GPIO.LOW) 
    # 继电器高电平触发    
    GPIO.output(config['pump_pin'], GPIO.LOW if enabled else GPIO.HIGH)   
    logger.info(f"气泵状态已设置为: {'开启' if enabled else '关闭'}")
    return True

# 水泵控制函数 20250815
def set_water_pump_state(enabled):
    """设置水泵状态"""
    global water_pump_enabled
    water_pump_enabled = enabled
    GPIO.output(config['water_pump_pin'], GPIO.LOW if enabled else GPIO.HIGH)
    logger.info(f"水泵状态已设置为: {'开启' if enabled else '关闭'}")
    return True

# 水泵定时控制函数 20250816
def run_water_pump_for_seconds(seconds):
    """运行水泵指定秒数后自动关闭"""
    global water_pump_timer
    
    # 先取消之前的定时器（如果有）
    if water_pump_timer is not None:
        water_pump_timer.cancel()
    
    # 开启水泵
    set_water_pump_state(True)
    
    # 设置定时器关闭水泵
    def turn_off_pump():
        set_water_pump_state(False)
        logger.info(f"水泵已运行{seconds}秒，自动关闭")
    
    water_pump_timer = threading.Timer(seconds, turn_off_pump)
    water_pump_timer.start()
    logger.info(f"水泵已开启，将在{seconds}秒后自动关闭")
    return True

# 水位检测函数
def check_water_level():
    global water_level
    try:
        # 读取传感器状态（传感器无水输出高电平，有水输出低电平）
        top_sensor = GPIO.input(config['water_sensor_top_pin'])
        bottom_sensor = GPIO.input(config['water_sensor_bottom_pin'])
        
        # 逻辑判断：
        # - 两个传感器都有水：水位过高
        # - 底部传感器有水，顶部无水：水位正常
        # - 两个传感器都无水：水位过低
        if top_sensor == GPIO.LOW and bottom_sensor == GPIO.LOW:
            water_level = "high"
        elif top_sensor == GPIO.HIGH and bottom_sensor == GPIO.LOW:
            water_level = "normal"
        elif top_sensor == GPIO.HIGH and bottom_sensor == GPIO.HIGH:
            water_level = "low"
        else:
            water_level = "unknown"
            
    except Exception as e:
        logger.error(f"检测水位失败: {str(e)}")
        water_level = "error"

def read_dht11():
    """读取DHT11温湿度传感器"""
    global current_temp, current_humidity
    try:
        humidity, temperature = Adafruit_DHT.read_retry(dht_sensor, config['dht11_pin'])
        if humidity is not None and temperature is not None:
            current_temp = temperature
            current_humidity = humidity
            logger.info(f"温湿度读取成功: {temperature}°C, {humidity}%")
        else:
            logger.warning("读取温湿度失败")
    except Exception as e:
        logger.error(f"读取温湿度传感器失败: {str(e)}")

# 初始化LED灯带
def init_led_strip():
    global strip
    try:
        logger.info("初始化LED灯带...")
        
        # 从配置获取参数
        led_count = config.get('led_count', 10)
        led_brightness = config.get('led_brightness', 200)
        
        strip = PixelStrip(
            led_count, 
            18,           # GPIO引脚 (PWM0)
            800000,       # LED信号频率 (通常800kHz)
            10,           # DMA通道
            False,        # 信号反转
            led_brightness,
            0             # 通道
        )
        strip.begin()
        set_all_leds(Color(*config.get('idle_color', [0, 0, 0])))
        logger.info(f"LED灯带初始化成功: {led_count}个灯珠, 亮度{led_brightness}")
        return True
    except Exception as e:
        logger.error(f"LED灯带初始化失败: {str(e)}")
        strip = None
        return False

# 设置所有LED颜色
def set_all_leds(color):
    if strip is None:
        return
    
    try:
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, color)
        strip.show()
    except Exception as e:
        logger.error(f"设置LED时出错: {str(e)}")

# 控制蜂鸣器
def beep_buzzer(num=2):
    try:
        pin = config['buzzer_pin']
        duration = config['buzzer_beep_duration']
        interval = config['buzzer_beep_interval']
        
        # 默认滴滴两声
        for _ in range(num):
            GPIO.output(pin,GPIO.HIGH)
            time.sleep(duration)
            GPIO.output(pin,GPIO.LOW)
            time.sleep(interval)
        
        logger.info("蜂鸣器已触发")
        return True
    except Exception as e:
        logger.error(f"蜂鸣器控制失败: {str(e)}")
        return False

# 监控Motion连接
def monitor_motion_connections():
    global active_connections, is_active, last_activity_time
    
    logger.info("开始监控Motion服务连接...")
    
    while True:
        try:
            current_connections = set()
            
            # 查找所有连接到8081端口的连接
            for conn in psutil.net_connections(kind='inet'):
                if conn.status == 'ESTABLISHED' and conn.laddr.port == 8081:
                    ident = f"{conn.raddr.ip}:{conn.raddr.port}"
                    current_connections.add(ident)
            
            # 使用线程锁保护共享变量
            with lock:
                # 检测新连接
                new_connections = current_connections - active_connections
                if new_connections:
                    logger.info(f"新连接: {', '.join(new_connections)}")
                    last_activity_time = time.time()
                    
                    # 激活灯带
                    if not is_active:
                        is_active = True
                        threading.Thread(target=activate_leds, daemon=True).start()
                    
                    # 触发蜂鸣器
                    threading.Thread(target=beep_buzzer, daemon=True).start()
                
                # 检测断开连接
                lost_connections = active_connections - current_connections
                if lost_connections:
                    logger.info(f"断开连接: {', '.join(lost_connections)}")
                
                # 更新连接集合并检查超时
                active_connections = current_connections
                
                # 检查超时
                if is_active and time.time() - last_activity_time > 60:
                    is_active = False
                    threading.Thread(target=deactivate_leds, daemon=True).start()
                    logger.info("活动超时，关闭灯带")
        
        except Exception as e:
            logger.error(f"监控连接时出错: {str(e)}")
        
        time.sleep(1)

# 激活灯带
def activate_leds():
    logger.info("激活LED灯带")
    if strip is not None:
        set_all_leds(Color(*config.get('active_color', [0, 100, 0])))

# 关闭灯带
def deactivate_leds():
    logger.info("关闭LED灯带")
    if strip is not None:
        set_all_leds(Color(*config.get('idle_color', [0, 0, 0])))

# 获取本机IP
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "192.168.0.216"

# 获取CPU温度
def get_cpu_temp():
    try:
        temp = os.popen("vcgencmd measure_temp").readline()
        return float(temp.replace("temp=", "").replace("'C\n", ""))
    except:
        return None

# 获取内存使用率
def get_memory_usage():
    try:
        return psutil.virtual_memory().percent
    except:
        return None


def sensor_reading_task():
    """每30秒读取一次传感器数据的任务"""
    global current_temp, current_humidity, current_water_temp
    logger.info("启动传感器读取任务...")
    
    while True:
        try:
            # 读取室温湿度
            humidity, temperature = Adafruit_DHT.read_retry(dht_sensor, config['dht11_pin'])
            if humidity is not None and temperature is not None:
                current_temp = temperature
                current_humidity = humidity
                #logger.info(f"温湿度读取成功: {temperature}°C, {humidity}%")
            else:
                logger.warning("读取温湿度失败")
            
            # 读取水温
            water_temp = get_water_temp()
            if water_temp is not None:
                current_water_temp = water_temp
                #logger.info(f"水温读取成功: {water_temp}°C")
            else:
                logger.warning("读取水温失败")
                
        except Exception as e:
            logger.error(f"读取传感器数据时出错: {str(e)}")
        
        # 每10秒读取一次
        time.sleep(30)

# 定时任务检查
def check_feeding_schedules():
    """检查并执行喂食计划的定时任务"""
    while True:
        logger.info(f"定时喂食任务检查！")
        conn = None
        try:
            conn = sqlite3.connect(config['database_path'])
            c = conn.cursor()
            
            # 确保所有需要的表都存在
            c.execute('''
                CREATE TABLE IF NOT EXISTS feeding_schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    enabled INTEGER DEFAULT 1,
                    schedule_name TEXT NOT NULL,
                    feed_time TEXT NOT NULL,  -- 存储格式 HH:MM
                    feed_days TEXT NOT NULL,  -- 存储格式 0,1,2,3,4,5,6 (0=周日)
                    portion_size INTEGER DEFAULT 1,
                    last_feed_time INTEGER   -- 存储时间戳
                )
            ''')
            
            c.execute('''
                CREATE TABLE IF NOT EXISTS feeding_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schedule_id INTEGER,
                    feed_time INTEGER NOT NULL,
                    portion_size INTEGER NOT NULL,
                    FOREIGN KEY(schedule_id) REFERENCES feeding_schedules(id)
                )
            ''')
            
            now = datetime.now()
            current_time = now.strftime('%H:%M')
            current_weekday = str((now.weekday() + 1) % 7)  # 转换为 0=周日, 1=周一, ..., 6=周六  # 0=周日, 6=周六
            logger.info(f"当前时间: {current_time}, 当前星期: {current_weekday}")  # 新增日志
            
            # 获取所有启用的计划
            c.execute('''
                SELECT id, portion_size, last_feed_time 
                FROM feeding_schedules
                WHERE enabled=1 AND feed_time=? AND feed_days LIKE ?
            ''', (current_time, f'%{current_weekday}%'))
            
            for schedule in c.fetchall():
                print(schedule)
                schedule_id, portion_size, last_feed_time_ = schedule
                current_timestamp = int(time.time())

                #last_feed_time_ 为该计划的最后喂食时间 ，last_feed_time为全局变量喂食时间 测试时请注意！
                
                # 检查冷却时间（至少3小时），如果从未喂食则last_feed_time_为None
                if last_feed_time_ is None or (current_timestamp - last_feed_time) >= 10800:
                    logger.info(f"执行喂食计划 {schedule_id}，投喂量 {portion_size}")
                    
                    try:
                        # 执行喂食
                        if 'servo' in globals():
                            for _ in range(portion_size):
                                servo.touwei()
                                time.sleep(2)  # 每次投喂间隔2秒
                        
                        # 更新最后喂食时间
                        c.execute('''
                            UPDATE feeding_schedules
                            SET last_feed_time=?
                            WHERE id=?
                        ''', (current_timestamp, schedule_id))
                        
                        # 记录喂食日志
                        c.execute('''
                            INSERT INTO feeding_logs 
                            (schedule_id, feed_time, portion_size)
                            VALUES (?, ?, ?)
                        ''', (schedule_id, current_timestamp, portion_size))
                        
                        conn.commit()
                        logger.info(f"自动喂食完成: 计划ID {schedule_id}")
                        
                    except Exception as e:
                        logger.error(f"自动喂食失败: {str(e)}")
                        conn.rollback()
                else:
                   print("最后的投喂时间不符合要求！")
                   logger.info(f"执行喂食计划 {schedule_id}，时间差 {current_timestamp - last_feed_time}") 
        
        except Exception as e:
            logger.error(f"检查喂食计划失败: {str(e)}")
            if conn:
                conn.rollback()
        
        finally:
            if conn:
                conn.close()
        
        time.sleep(60)  # 每分钟检查一次

# ======================
# Flask 路由
# ======================

@app.route('/')
def index():
    """主控制界面"""
    return render_template('index.html', 
                           ip=get_local_ip(), 
                           port=5000)

@app.route('/status')
def status():
    """系统状态API"""
    check_water_level()  # 每次请求时检测水位
    #read_dht11()        # 读取温湿度
    feed_hours_ago = (time.time() - last_feed_time) / 3600.0 if last_feed_time > 0 else None
    with lock:
        return jsonify({
            "active": is_active,
            "connections": len(active_connections),
            "last_activity": last_activity_time,
            "cpu_temp": get_cpu_temp(),
            "mem_usage": get_memory_usage(),
            "water_temp": current_water_temp,  # 水温
            "fan_enabled": fan_enabled,  # 风扇状态
            "pump_enabled": pump_enabled,  # 气泵状态
            "water_pump_enabled": water_pump_enabled, #水泵状态
            "water_level": water_level,  # 水位状态
            "temperature": current_temp,    # # 使用后台线程更新的温度
            "humidity": current_humidity,    # 使用后台线程更新的湿度
            "feed_hours_ago": feed_hours_ago
        })

# 添加风扇控制路由
@app.route('/fan/<state>')
def control_fan(state):
    """控制风扇API"""
    if state == 'on':
        success = set_fan_state(True)
        return jsonify({"status": "success" if success else "error"})
    elif state == 'off':
        success = set_fan_state(False)
        return jsonify({"status": "success" if success else "error"})
    else:
        return jsonify({"status": "error", "message": "无效的指令"}), 400

# 气泵控制路由
@app.route('/pump/<state>')
def control_pump(state):
    """控制气泵API"""
    if state == 'on':
        success = set_pump_state(True)
        return jsonify({"status": "success" if success else "error"})
    elif state == 'off':
        success = set_pump_state(False)
        return jsonify({"status": "success" if success else "error"})
    else:
        return jsonify({"status": "error", "message": "无效的指令"}), 400


# 添加水泵控制路由
@app.route('/water_pump/<state>')
def control_water_pump(state):
    """控制水泵API"""
    if state == 'on':
        success = set_water_pump_state(True)
        return jsonify({"status": "success" if success else "error"})
    elif state == 'off':
        success = set_water_pump_state(False)
        return jsonify({"status": "success" if success else "error"})
    else:
        return jsonify({"status": "error", "message": "无效的指令"}), 400

# 添加水泵定时控制路由
@app.route('/water_pump/timer/<int:seconds>')
def control_water_pump_timer(seconds):
    """控制水泵运行指定秒数API"""
    if seconds <= 0:
        return jsonify({"status": "error", "message": "时间必须大于0"}), 400    
    try:
        success = run_water_pump_for_seconds(seconds)
        return jsonify({"status": "success" if success else "error"})
    except Exception as e:
        logger.error(f"水泵定时控制失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    

# 获取配置路由 - 添加颜色格式兼容处理
@app.route('/get_config')
def get_config():
    # 确保颜色是对象格式，便于前端处理
    safe_config = config.copy()
    safe_config['active_color'] = {
        "r": config['active_color'][0],
        "g": config['active_color'][1],
        "b": config['active_color'][2]
    }
    safe_config['idle_color'] = {
        "r": config['idle_color'][0],
        "g": config['idle_color'][1],
        "b": config['idle_color'][2]
    }
    return jsonify(safe_config)


# 更新配置路由 - 添加颜色格式兼容处理
@app.route('/update_config', methods=['POST'])
def update_config():
    """更新配置并处理颜色格式"""
    global config
    try:
        new_config = request.json
        logger.info(f"接收新配置: {new_config}")
        
        # 处理颜色格式 - 兼容对象和数组格式
        def normalize_color(color):
            """将颜色数据标准化为[r, g, b]格式"""
            if isinstance(color, dict):
                return [color.get('r', 0), color.get('g', 0), color.get('b', 0)]
            elif isinstance(color, list) and len(color) >= 3:
                return color[:3]
            return [0, 0, 0]  # 默认黑色
        
        # 处理active_color
        if 'active_color' in new_config:
            new_config['active_color'] = normalize_color(new_config['active_color'])
        
        # 处理idle_color
        if 'idle_color' in new_config:
            new_config['idle_color'] = normalize_color(new_config['idle_color'])
        
        # 验证配置值
        def validate_value(key, min_val, max_val, default):
            """验证配置值是否在有效范围内"""
            value = new_config.get(key, default)
            try:
                value = type(default)(value)
                if value < min_val or value > max_val:
                    raise ValueError(f"{key}值超出范围({min_val}-{max_val})")
                return value
            except (TypeError, ValueError):
                return default
        
        # 验证数值型配置
        #new_config['led_count'] = validate_value('led_count', 1, 100, 7)
        new_config['led_brightness'] = validate_value('led_brightness', 0, 255, 200)
        
        # 验证蜂鸣器配置
        if 'buzzer_pin' in new_config:
            new_config['buzzer_pin'] = validate_value('buzzer_pin', 1, 27, 17)
        if 'buzzer_beep_duration' in new_config:
            new_config['buzzer_beep_duration'] = validate_value('buzzer_beep_duration', 0.05, 2.0, 0.2)
        if 'buzzer_beep_interval' in new_config:
            new_config['buzzer_beep_interval'] = validate_value('buzzer_beep_interval', 0.05, 2.0, 0.1)

        # 验证风扇配置
        if 'fan_pin' in new_config:
            new_config['fan_pin'] = validate_value('fan_pin', 1, 27, 24)
        if 'fan_enabled' in new_config:
            new_config['fan_enabled'] = bool(new_config['fan_enabled'])
        
        # 验证气泵配置
        if 'pump_pin' in new_config:
            new_config['pump_pin'] = validate_value('pump_pin', 1, 27, 6)  # 默认GPIO22
        if 'pump_enabled' in new_config:
            new_config['pump_enabled'] = bool(new_config['pump_enabled'])

        # 验证水泵配置
        if 'water_pump_pin' in new_config:
            new_config['water_pump_pin'] = validate_value('water_pump_pin', 1, 27,19)  # 默认GPIO19
        if 'water_pump_enabled' in new_config:
            new_config['water_pump_enabled'] = bool(new_config['water_pump_enabled'])
        
        # 更新全局配置
        config.update(new_config)

        # 应用风扇状态
        if 'fan_enabled' in new_config:
            set_fan_state(new_config['fan_enabled'])

        # 应用气泵状态
        if 'pump_enabled' in new_config:
            set_pump_state(new_config['pump_enabled'])

        # 应用水泵状态
        if 'water_pump_enabled' in new_config:
            set_pump_state(new_config['water_pump_enabled'])
        
        # 保存到文件
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=4)
        
        logger.info(f"配置更新成功: {config}")
        return jsonify({"status": "success", "config": config})
    
    except Exception as e:
        logger.error(f"更新配置失败: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "received_config": request.json,
            "current_config": config
        }), 400

@app.route('/reinit_leds')
def reinit_leds():
    """重新初始化LED灯带"""
    global strip
    if strip is not None:
        try:
            strip._cleanup()  # 清理现有灯带
        except:
            pass
    
    init_led_strip()
    if is_active:
        activate_leds()
    else:
        deactivate_leds()
    
    return jsonify({"status": "success"})

@app.route('/activate')
def web_activate():
    """激活灯带API"""
    with lock:
        global is_active, last_activity_time
        is_active = True
        last_activity_time = time.time()
        threading.Thread(target=activate_leds, daemon=True).start()
        return jsonify({"status": "activated"})

@app.route('/deactivate')
def web_deactivate():
    """关闭灯带API"""
    with lock:
        global is_active
        is_active = False
        threading.Thread(target=deactivate_leds, daemon=True).start()
        return jsonify({"status": "deactivated"})

@app.route('/test_buzzer')
def test_buzzer():
    """测试蜂鸣器API"""
    if beep_buzzer(5):
        return jsonify({"status": "success"})
 
    return jsonify({"status": "error"}), 500



@app.route('/charts')
def charts():
    """数据统计页面"""
    return render_template('charts.html', 
                           ip=get_local_ip(), 
                           port=5000)

# 喂食计划管理API
@app.route('/api/feeding/schedules', methods=['GET', 'POST', 'DELETE'])
def manage_schedules():
    try:
        conn = sqlite3.connect(config['database_path'])
        c = conn.cursor()
        
        # 确保表存在
        c.execute('''
            CREATE TABLE IF NOT EXISTS feeding_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                enabled INTEGER DEFAULT 1,
                schedule_name TEXT NOT NULL,
                feed_time TEXT NOT NULL,
                feed_days TEXT NOT NULL,
                portion_size INTEGER DEFAULT 1,
                last_feed_time INTEGER,
                next_feed_time INTEGER
            )
        ''')
        
        if request.method == 'GET':
            # 获取所有喂食计划
            c.execute('SELECT id, enabled, schedule_name, feed_time, feed_days, portion_size FROM feeding_schedules ORDER BY feed_time')
            schedules = []
            for row in c.fetchall():
                schedules.append({
                    'id': row[0],
                    'enabled': bool(row[1]),
                    'schedule_name': row[2],
                    'feed_time': row[3],
                    'feed_days': [int(d) for d in row[4].split(',') if d],
                    'portion_size': row[5]
                })
            return jsonify(schedules)
        
        elif request.method == 'POST':
            data = request.get_json()
            if not data:
                return jsonify({"status": "error", "message": "无效的请求数据"}), 400
            
            # 验证必要字段
            required_fields = ['schedule_name', 'feed_time', 'feed_days', 'portion_size']
            if not all(field in data for field in required_fields):
                return jsonify({"status": "error", "message": "缺少必要字段"}), 400
            
            # 处理feed_days格式
            feed_days = data['feed_days']
            if isinstance(feed_days, list):
                feed_days = ','.join(str(day) for day in feed_days)
            
            if 'id' in data:
                # 更新现有计划
                c.execute('''
                    UPDATE feeding_schedules SET
                    enabled=?, schedule_name=?, feed_time=?, feed_days=?, portion_size=?
                    WHERE id=?
                ''', (
                    int(data.get('enabled', True)),
                    data['schedule_name'],
                    data['feed_time'],
                    feed_days,
                    int(data['portion_size']),
                    data['id']
                ))
                schedule_id = data['id']
            else:
                # 创建新计划
                c.execute('''
                    INSERT INTO feeding_schedules 
                    (enabled, schedule_name, feed_time, feed_days, portion_size)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    int(data.get('enabled', True)),
                    data['schedule_name'],
                    data['feed_time'],
                    feed_days,
                    int(data['portion_size'])
                ))
                schedule_id = c.lastrowid
            
            conn.commit()
            return jsonify({'status': 'success', 'id': schedule_id})
    
    except Exception as e:
        logger.error(f"喂食计划管理错误: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/feeding/schedules/toggle', methods=['POST'])
def toggle_schedule():
    try:
        data = request.get_json()
        schedule_id = data.get('id')
        enabled = data.get('enabled', 0)
        
        if not schedule_id:
            return jsonify({"status": "error", "message": "缺少计划ID"}), 400
        
        conn = sqlite3.connect(config['database_path'])
        c = conn.cursor()
        
        c.execute('''
            UPDATE feeding_schedules 
            SET enabled = ?
            WHERE id = ?
        ''', (enabled, schedule_id))
        
        if c.rowcount == 0:
            return jsonify({"status": "error", "message": "计划不存在"}), 404
        
        conn.commit()
        return jsonify({"status": "success", "id": schedule_id, "enabled": enabled})
    
    except Exception as e:
        logger.error(f"切换计划状态失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()

#手动喂食
@app.route('/feed', methods=['POST'])
def feed_fish():
    """立即投喂接口（带完整错误处理）"""
    global last_feed_time
    
    try:
        # 1. 验证请求数据
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "无效的请求数据"}), 400
        
        # 2. 获取并验证投喂量
        try:
            portion_size = int(data.get('portion_size', 1))
            portion_size = max(1, min(portion_size, 3))  # 限制1-3次
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "投喂量必须是1-3的整数"}), 400

        # 3. 检查舵机状态
        if 'servo' not in globals():
            if not init_servo():
                return jsonify({"status": "error", "message": "舵机初始化失败"}), 500

        # 4. 检查冷却时间（带容错处理）
        current_time = time.time()
        if last_feed_time > 0 and (current_time - last_feed_time) < 3 * 3600:
            remaining = (3 * 3600 - (current_time - last_feed_time)) / 60
            return jsonify({
                "status": "error",
                "message": f"距离上次投喂不足3小时，请{remaining:.1f}分钟后再试"
            }), 429

        # 5. 执行投喂（带线程锁）
        with feed_lock:
            # 执行投喂动作
            for _ in range(portion_size):
                try:
                    servo.touwei()
                    time.sleep(1)  # 每次投喂间隔1秒
                except Exception as e:
                    logger.error(f"投喂动作执行失败: {str(e)}")
                    return jsonify({
                        "status": "error", 
                        "message": f"投喂动作执行失败: {str(e)}"
                    }), 500

            # 6. 记录投喂日志
            conn = None
            try:
                conn = sqlite3.connect(config['database_path'])
                c = conn.cursor()
                c.execute('''
                    INSERT INTO feeding_logs 
                    (feed_time, portion_size)
                    VALUES (?, ?)
                ''', (int(current_time), portion_size))
                conn.commit()
            except Exception as e:
                logger.error(f"记录投喂日志失败: {str(e)}")
                if conn:
                    conn.rollback()
                return jsonify({
                    "status": "error",
                    "message": "记录投喂日志失败"
                }), 500
            finally:
                if conn:
                    conn.close()

            # 7. 更新最后投喂时间
            last_feed_time = current_time
            
            return jsonify({
                "status": "success",
                "message": f"成功投喂{portion_size}次",
                "last_feed_time": last_feed_time
            })

    except Exception as e:
        logger.error(f"投喂处理严重错误: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            "status": "error",
            "message": "服务器内部错误"
        }), 500

#删除喂食计划
@app.route('/api/feeding/schedules/<int:schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id):
    
    try:
        conn = sqlite3.connect(config['database_path'])
        c = conn.cursor()
        
        # 先检查计划是否存在
        c.execute('SELECT id FROM feeding_schedules WHERE id = ?', (schedule_id,))
        if not c.fetchone():
            return jsonify({"status": "error", "message": "计划不存在"}), 404
        
        # 删除计划
        c.execute('DELETE FROM feeding_schedules WHERE id = ?', (schedule_id,))
        conn.commit()
        
        logger.info(f"成功删除喂食计划: ID {schedule_id}")
        return jsonify({"status": "success", "id": schedule_id})
    
    except sqlite3.Error as e:
        logger.error(f"数据库错误: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
        return jsonify({"status": "error", "message": "数据库错误"}), 500
    except Exception as e:
        logger.error(f"删除计划失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()


# 获取喂食记录
@app.route('/api/feeding/logs', methods=['GET'])
def get_feeding_logs():
    limit = request.args.get('limit', 10)
    conn = sqlite3.connect(config['database_path'])
    c = conn.cursor()
    
    c.execute('''
        SELECT l.id, l.feed_time, l.portion_size, 
               s.schedule_name, s.id as schedule_id
        FROM feeding_logs l
        LEFT JOIN feeding_schedules s ON l.schedule_id = s.id
        ORDER BY l.feed_time DESC
        LIMIT ?
    ''', (limit,))
    
    logs = []
    for row in c.fetchall():
        logs.append({
            'id': row[0],
            'feed_time': row[1],
            'portion_size': row[2],
            'schedule_name': row[3],
            'schedule_id': row[4]
        })
    
    return jsonify(logs)





@app.route('/api/feeding/logs/<int:log_id>', methods=['DELETE'])
def delete_feeding_log(log_id):
    try:
        conn = sqlite3.connect(config['database_path'])
        c = conn.cursor()
        
        # 检查记录是否存在
        c.execute('SELECT id FROM feeding_logs WHERE id = ?', (log_id,))
        if not c.fetchone():
            return jsonify({"status": "error", "message": "记录不存在"}), 404
        
        # 删除记录
        c.execute('DELETE FROM feeding_logs WHERE id = ?', (log_id,))
        conn.commit()
        
        return jsonify({"status": "success", "id": log_id})
    
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/feeding')
def feeding():
    """喂食管理页面"""
    return render_template('feeding.html', 
                         ip=get_local_ip(), 
                         port=5000)

@app.route('/sensor_data')
def get_sensor_data():
    """获取传感器历史数据"""
    time_range = request.args.get('range', 'day')  # day, week, month
    
    # 计算时间范围
    now = datetime.now()
    if time_range == 'day':
        start_time = now - timedelta(days=1)
    elif time_range == 'week':
        start_time = now - timedelta(weeks=1)
    elif time_range == 'month':
        start_time = now - timedelta(days=30)
    else:
        start_time = now - timedelta(days=1)
    
    try:
        conn = sqlite3.connect(config['database_path'])
        c = conn.cursor()
        
        # 查询数据
        c.execute('''
            SELECT strftime('%Y-%m-%d %H:%M', timestamp) as time,
                   air_temp, humidity, water_temp
            FROM sensor_data
            WHERE timestamp >= ?
            ORDER BY timestamp
        ''', (start_time.strftime('%Y-%m-%d %H:%M:%S'),))
        
        data = c.fetchall()
        conn.close()
        
        # 格式化数据
        times = [row[0] for row in data]
        air_temps = [row[1] for row in data]
        humidities = [row[2] for row in data]
        water_temps = [row[3] for row in data]
        
        return jsonify({
            "times": times,
            "air_temps": air_temps,
            "humidities": humidities,
            "water_temps": water_temps
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/check_network')
def check_network():
    """检查当前是否是内网访问"""
    client_ip = request.remote_addr
    is_local = (client_ip == '127.0.0.1' or 
               client_ip.startswith('192.168.') or               
               client_ip.startswith('172.'))
    
    return jsonify({
        "is_local": is_local,
        "client_ip": client_ip
    })

# ======================
# 主程序
# ======================

def main():
    """程序入口"""
    logger.info("====== 启动鱼缸监控控制系统V1.2 ======")
    
    # 初始化硬件
    init_gpio()
    init_led_strip()
    # 首次读取温湿度
    #read_dht11()
    # 初始化舵机
    init_servo()
     # 注册退出清理函数
    atexit.register(cleanup_resources)


    # 启动传感器读取线程
    sensor_thread = threading.Thread(target=sensor_reading_task, daemon=True)
    sensor_thread.start()
    
    # 启动监控线程
    monitor_thread = threading.Thread(target=monitor_motion_connections, daemon=True)
    monitor_thread.start()

    # 启动喂食计划检查线程
    feeding_thread = threading.Thread(target=check_feeding_schedules, daemon=True)
    feeding_thread.start()
    
    # 启动Web服务
    app.run(host='0.0.0.0', port=5000, threaded=True)

def cleanup_resources():
    """清理资源"""
    if 'servo' in globals():
        try:
            servo.cleanup()
            logger.info("舵机资源已清理")
        except:
            pass

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("程序终止")
    finally:
        # 清理资源
        if strip is not None:
            set_all_leds(Color(0, 0, 0))
        GPIO.cleanup()



        