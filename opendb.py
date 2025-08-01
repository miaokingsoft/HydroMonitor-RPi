'''
启动时初始化数据库和表
1. 创建传感器数据表
2. 创建喂食计划表
'''
import sqlite3
import os
import json
import logging


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
            "database_path": "/var/lib/fishtank/sensor_data.db"           
        }

config = load_config()

# 确保数据库目录存在
database_dir = os.path.dirname(config.get('database_path', '/var/lib/fishtank/sensor_data.db'))
os.makedirs(database_dir, exist_ok=True)

# 初始化数据库
def init_database():
    #初始化数据库，创建传感器数据表'''
    conn = sqlite3.connect(config.get('database_path', '/var/lib/fishtank/sensor_data.db'))
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS sensor_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
        air_temp REAL,
        humidity REAL,
        water_temp REAL
    )''')
    
    c.execute('''CREATE INDEX IF NOT EXISTS idx_timestamp ON sensor_data (timestamp)''')
    
    conn.commit()
    conn.close()
    logger.info("数据库初始化完成")

# 在 main() 函数前添加数据库初始化代码
def feed_db():
    conn = sqlite3.connect(config['database_path'])
    c = conn.cursor()
    
    # 创建喂食计划表
    c.execute('''
        CREATE TABLE IF NOT EXISTS feeding_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enabled BOOLEAN DEFAULT 1,
            schedule_name TEXT,
            feed_time TEXT,  -- HH:MM
            feed_days TEXT,  -- 逗号分隔的数字 0-6 (0=周日)
            portion_size INTEGER DEFAULT 1,  -- 投喂量(1-3)
            last_feed_time INTEGER,  -- 时间戳
            next_feed_time INTEGER   -- 时间戳
        )
    ''')
    
    # 创建喂食记录表
    c.execute('''
        CREATE TABLE IF NOT EXISTS feeding_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id INTEGER,
            feed_time INTEGER,  -- 时间戳
            portion_size INTEGER,
            FOREIGN KEY(schedule_id) REFERENCES feeding_schedules(id)
        )
    ''')
    
    conn.commit()
    conn.close()


# 确保数据库和表已初始化
feed_db()