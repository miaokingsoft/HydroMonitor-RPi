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

#config = load_config()
database_path = '/var/lib/fishtank/sensor_data.db'
# 确保数据库目录存在
#database_dir = os.path.dirname("/var/lib/fishtank/sensor_data.db", '/var/lib/fishtank/sensor_data.db')
#os.makedirs(database_dir, exist_ok=True)

# 初始化数据库
def init_database():
    #初始化数据库，创建传感器数据表'''
    conn = sqlite3.connect(database_path)
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
    conn = sqlite3.connect(database_path)
    c = conn.cursor()
    
    # 创建计划表
    c.execute('''
        CREATE TABLE IF NOT EXISTS feeding_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enabled BOOLEAN DEFAULT 1,
            schedule_name TEXT,
            feed_time TEXT,  -- HH:MM
            feed_days TEXT,  -- 逗号分隔的数字 0-6 (0=周日)
            portion_size INTEGER DEFAULT 1,  -- 投喂量(1-3)
            last_feed_time INTEGER,  -- 时间戳
            next_feed_time INTEGER,   -- 时间戳
            typeid INTEGER DEFAULT 0  -- 计划类型,0=喂食,1=风扇,2=气泵,3=灌溉蓄水
              
        )
    ''')
    
    # 创建自动化执行记录表
    c.execute('''
        CREATE TABLE IF NOT EXISTS feeding_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id INTEGER,
            feed_time INTEGER,  -- 时间戳
            portion_size INTEGER,
            typeid INTEGER DEFAULT 0 -- 记录类型,0=喂食,1=风扇,2=气泵,3=灌溉蓄水
            FOREIGN KEY(schedule_id) REFERENCES feeding_schedules(id)
        )
    ''')

    #创建网络访问记录表
    c.execute('''
        CREATE TABLE IF NOT EXISTS access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
            ip_address TEXT,
            action TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

# 在 main() 函数前添加数据库初始化代码
def net_db():
    conn = sqlite3.connect(database_path)
    c = conn.cursor()
    
   # 创建访问记录表（新增）
    c.execute('''
        CREATE TABLE IF NOT EXISTS access_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            path TEXT NOT NULL,
            method TEXT NOT NULL,
            user_agent TEXT,
            start_time REAL NOT NULL,
            end_time REAL,
            duration REAL,
            status_code INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 创建签到记录表（新增）
    c.execute('''
        CREATE TABLE IF NOT EXISTS signin_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            user_agent TEXT,
            signin_time REAL NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 创建索引以提高查询性能
    c.execute('CREATE INDEX IF NOT EXISTS idx_access_ip ON access_records(ip_address)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_access_time ON access_records(start_time)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_signin_time ON signin_records(signin_time)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_signin_ip ON signin_records(ip_address)')
    
    conn.commit()
    conn.close()



# 确保数据库和表已初始化
#feed_db()
net_db()

'''
字段详细说明：

access_records 表（访问记录表）：

id: 主键，自动递增的唯一标识

request_id: 使用UUID生成的请求唯一标识，用于跟踪单个请求

ip_address: 客户端的IP地址，用于识别访问来源

path: 请求的URL路径，记录访问的具体页面或API

method: HTTP请求方法（GET、POST、PUT、DELETE等）

user_agent: 客户端浏览器或设备的标识信息

start_time: 请求开始处理的时间（Unix时间戳格式）

end_time: 请求处理完成的时间（Unix时间戳格式）

duration: 请求处理总时长（end_time - start_time）

status_code: HTTP响应状态码（200成功、404未找到、500错误等）

created_at: 记录创建时间，使用数据库的当前时间

signin_records 表（签到记录表）：

id: 主键，自动递增的唯一标识

ip_address: 签到客户端的IP地址

user_agent: 签到时的浏览器或设备信息

signin_time: 签到发生的时间（Unix时间戳格式）

created_at: 记录创建时间，使用数据库的当前时间
'''