# HydroMonitor-RPi 
# 闲沐智能鱼缸系统v1.3

基于树莓派的智能鱼缸监控系统，使用 Flask 构建 Web 界面，并提供传感器接线板PCB：

## 功能特性
- usb摄像头连接树莓派后，可实时查看鱼缸视频直播画面
- 可远程控制灯带颜色和亮度，在web页面可设置
- 实时检测室温、水温、湿度，并记录数据可视化统计
- 可远程开启（关闭）气泵、水泵、风扇、灯光、喂鱼食等
- 可制定执行计划，自动执行水泵、气泵、喂食等开启和关闭，并把执行记录入数据库- 
- 有人访问时，鱼缸led灯带亮起，并发出滴滴声（蜂鸣器提醒）
- 实时检测水位，高于或低于预警水位时会发邮件通知- 
- 投喂鱼食会记录在数据库，每次投喂间隔必须在3小时以上
- 直播画面通过识别内外网更换访问地址，保证画面流畅
- 提供【签到】功能，蜂鸣器会发出滴滴提醒
- 按水温高低阈值，可自动开启或关闭风扇
- 系统状态监控（CPU、内存、活动、流量）
- 提供网络访问数据可视化统计
- web页面支持浏览器和手机访问，可配合Frp实现公网访问

![Web界面](/Ui12.png)
![喂食计划管理](/Ui12-2.png)
![监控数据统计](/Ui12-4.png)




## 硬件要求
- 树莓派（建议3B以上，我用的是4B+）
- WS2812B LED 灯带 10个灯珠较合适
- DHT11 温湿度传感器
- 4020 5V 风扇（4个，XH2.54插头)
- 水位传感器（2个）（在缸壁外侧用双面胶帖上，高低预警水位线各一个）
- 继电器模块（控制风扇和气泵，4路5V，低电平触发）
- 蜂鸣器 （高电平触发）
- SG90 180度舵机（建议用更好的舵机）
- DS18B20水温监控模块（探头和板一套）
- USB摄像头（最好有自动对焦功能）
- 5V 3A电源（给风扇、气泵供电）
- 智能鱼缸接线板 （[PCB已打板，需要请访问这里](https://www.goofish.com/item?spm=a21ybx.personal.feeds.1.596b2358xB7LkT&id=965639435219&categoryId=125952002)）
- 杜邦线等等耗材
  
## 硬件接线板
![智能鱼缸接线板](/PCB.jpg)

- 4路单独DC供电接口
- 蜂鸣器3P排母
- 2路水位监测 3P排母
- led 3P 排针
- 温湿度 3P排针
- 4路继电器 6p+8p排针
- 1路水温监测 3P排母
- 备用 5v、3v3、4个GPIO 排针
- 18P 排针（用杜邦线连接树莓派）
如有需要  [请点击这里访问](https://www.goofish.com/item?spm=a21ybx.personal.feeds.1.596b2358xB7LkT&id=965639435219&categoryId=125952002)
  

  ## 与树莓派连线图
  
  ![如何接树莓派](/c.png)


  


## 3D打印件
- [风扇支架](https://makerworld.com.cn/zh/models/1435672-yu-gang-feng-shan-zhi-jia-x4#profileId-1559928)
- [自动喂食器](https://makerworld.com.cn/zh/models/1509194-zhi-neng-yu-gang-xi-tong-zu-jian-zhi-zi-dong-wei-y?from=search#profileId-1647953)
- [可调电源壁挂支架](https://makerworld.com.cn/zh/models/1509171-ke-diao-12vdian-yuan-bi-gua-zhi-jia#profileId-1647928)
- PCB板壁挂架 （整理中）
- led灯带贴合鱼缸壁组件（整理中）
- 理线管卡（整理中）
- 370水泵支架（整理中）
- 滴灌头（整理中）

## 在树莓派上安装 Motion
```markdown
sudo apt update
sudo apt install motion
```
- 注意： Raspbian 仓库中的版本可能不是最新的。如果需要最新特性或 bug 修复，可以从源代码编译安装（过程稍复杂，需查阅官方文档）。
- 主配置文件： /etc/motion/motion.conf 这是全局配置文件，修改它需要 root 权限 (sudo nano /etc/motion/motion.conf)。
- 修改后重启服务生效：
```markdown
sudo service motion restart
# 或者
sudo systemctl restart motion.service
 ```
## 摄像头基本使用流程
- 连接摄像头： 将 USB 摄像头插入树莓派 USB 口，或正确连接 CSI 摄像头并启用（sudo raspi-config > Interface Options > Legacy Camera 或 Camera > Enable）。
- 启动服务： sudo service motion start
- 测试访问： 在树莓派或同一局域网内的电脑/手机浏览器访问 http://<树莓派IP>:8081 (或你设置的端口) 查看实时流。

  
## 软件依赖
- Python 3.7+
- Flask
- rpi-ws281x
- RPi.GPIO
- psutil
- Adafruit_DHT
```markdown
sudo apt-get install python3-pip python3-dev
pip install Adafruit-DHT RPi.GPIO psutil flask pytz tzlocal rpi-ws281x
pip install smtplib email
```

## 配置硬件引脚说明（修改 config.json）：
```markdown
{
  "led_count": 10, #led灯珠数量
  "led_brightness": 230, #亮度
  "active_color": [0, 100, 0], #触发时颜色
  "idle_color": [0, 0, 0], #闲置时颜色
  "buzzer_pin": 17, #蜂鸣器引脚
  "buzzer_beep_duration": 0.2, #间隔时间
  "buzzer_beep_interval": 0.1, #间隔时间
  "fan_pin": 24,  # 风扇控制引脚
  "fan_enabled": False,  # 风扇状态
  "pump_pin": 6,  # 气泵控制引脚原来是 (GPIO6)
  "pump_enabled": False,  # 气泵状态
  "water_pump_pin": 19,  # 水泵控制引脚 (GPIO19)
  "water_pump_enabled": False,  # 水泵状态
  "water_sensor_top_pin": 25, #高水位引脚
  "water_sensor_bottom_pin": 23, #低水位引脚
  "dht11_pin": 5, #温湿度度模块引脚
  "database_path": "/var/lib/fishtank/sensor_data.db", #数据库地址
   "timezone": "Asia/Shanghai", #时区
  "max_temperature": 30, #高温度阈值
  "min_temperature": 27  #低温度阈值
}
```

## 运行

### 树莓派上执行  
```markdown
sudo python app.py
sudo python fishtank.py
```
### 客户端浏览器或手机访问： http://树莓派IP:5000


## **项目结构**
```markdown
├── app.py               # 主程序
├── config.json          # 配置文件
├── fishtank.py          # 水温、水位、湿度、室温采集执行程序
├── opendb.py          # 数据库初始化程序
├── sg90180.py         # 舵机控制库，用于喂食时控制舵机
├── requirements.txt     # 依赖列表
├── README.md            # 项目文档
├── templates
│   └── index.html       # 前端页面
|   └── feeding.html     # 喂食计划管理页面
|   └── charts.html     # 环境数据统计页面
└── static               # 静态资源
    ├── css
    ├── js
    └── images

```
## 联系方式
- 作者：MiaoKing
- 邮箱：7740840@qq.com
- 抖音：@闲沐工坊
- QQ：7740840

