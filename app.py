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
        "pump_pin": 22,  # 气泵引脚 (GPIO22)
        "pump_enabled": False,  # 气泵状态
        "water_sensor_top_pin": 25,
        "water_sensor_bottom_pin": 23
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
water_level = "unknown"  # 水位状态：high/normal/low/unknown
# 在全局变量部分添加
dht_sensor = Adafruit_DHT.DHT11
current_temp = None
current_humidity = None

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
        GPIO.output(config['buzzer_pin'], GPIO.HIGH)
        # 初始化风扇引脚
        GPIO.setup(config['fan_pin'], GPIO.OUT)
        global fan_enabled
        fan_enabled = config['fan_enabled']
        # 继电器低电平触发
        GPIO.output(config['fan_pin'], GPIO.HIGH if fan_enabled else GPIO.LOW)

        # 初始化气泵引脚 (GPIO22)
        GPIO.setup(config['pump_pin'], GPIO.OUT)
        global pump_enabled
        pump_enabled = config['pump_enabled']
        # 继电器低电平触发
        GPIO.output(config['pump_pin'], GPIO.HIGH if fan_enabled else GPIO.LOW)

        # 初始化水位传感器引脚
        GPIO.setup(config['water_sensor_top_pin'], GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(config['water_sensor_bottom_pin'], GPIO.IN, pull_up_down=GPIO.PUD_UP)

        

        logger.info("GPIO初始化成功")
        return True
    except Exception as e:
        logger.error(f"GPIO初始化失败: {str(e)}")
        return False
    
# 添加水温读取函数
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

    GPIO.output(config['fan_pin'], GPIO.HIGH if enabled else GPIO.LOW)
    logger.info(f"风扇状态已设置为: {'开启' if enabled else '关闭'}")
    return True

# 新增气泵控制函数
def set_pump_state(enabled):
    """设置气泵状态"""
    global pump_enabled
    pump_enabled = enabled
    
    # 继电器高电平触发
    GPIO.output(config['pump_pin'], GPIO.HIGH if enabled else GPIO.LOW)    
    logger.info(f"气泵状态已设置为: {'开启' if enabled else '关闭'}")
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
def beep_buzzer():
    try:
        pin = config['buzzer_pin']
        duration = config['buzzer_beep_duration']
        interval = config['buzzer_beep_interval']
        
        # 滴滴两声
        for _ in range(3):
            GPIO.output(pin, GPIO.LOW)
            time.sleep(duration)
            GPIO.output(pin, GPIO.HIGH)
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
    read_dht11()        # 读取温湿度
    with lock:
        return jsonify({
            "active": is_active,
            "connections": len(active_connections),
            "last_activity": last_activity_time,
            "cpu_temp": get_cpu_temp(),
            "mem_usage": get_memory_usage(),
            #"water_temp": get_water_temp(),  # 添加水温
            "fan_enabled": fan_enabled,  # 风扇状态
            "pump_enabled": pump_enabled,  # 气泵状态
            "water_level": water_level,  # 水位状态
            "temperature": current_temp,    # 添加温度
            "humidity": current_humidity    # 添加湿度
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

@app.route('/get_config')
def get_config():
    """获取当前配置（确保格式正确）"""
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
            new_config['pump_pin'] = validate_value('pump_pin', 1, 27, 22)  # 默认GPIO22
        if 'pump_enabled' in new_config:
            new_config['pump_enabled'] = bool(new_config['pump_enabled'])

        # 更新全局配置
        config.update(new_config)

        # 应用风扇状态
        if 'fan_enabled' in new_config:
            set_fan_state(new_config['fan_enabled'])

        # 应用气泵状态
        if 'pump_enabled' in new_config:
            set_pump_state(new_config['pump_enabled'])
        
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
    if beep_buzzer():
        return jsonify({"status": "success"})
 
    return jsonify({"status": "error"}), 500

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


# ======================
# 主程序
# ======================

def main():
    """程序入口"""
    logger.info("====== 启动鱼缸监控控制系统V0.5 ======")
    
    # 初始化硬件
    init_gpio()
    init_led_strip()
    # 首次读取温湿度
    read_dht11()
    
    # 启动监控线程
    monitor_thread = threading.Thread(target=monitor_motion_connections, daemon=True)
    monitor_thread.start()
    
    # 启动Web服务
    app.run(host='0.0.0.0', port=5000, threaded=True)

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


#pip install Adafruit-DHT
#执行程序用 sudo python app.py
#水位的监控报警发邮件到7740840@qq.com,单独运行 python shui.py