# HydroMonitor-RPi 
# 鱼缸监控系统

基于树莓派的智能鱼缸监控系统，使用 Flask 构建 Web 界面，支持远程监控和控制鱼缸设备。

![Web界面](/Ui.png)

## 功能特性
- 实时监控鱼缸温度、湿度
- 水位检测与报警
- LED 灯带控制（颜色、亮度）
- 风扇控制（温度调节）
- 气泵控制（增氧）
- 蜂鸣器提醒
- 系统状态监控（CPU、内存）

## 硬件要求
- 树莓派（任何型号）
- WS2812B LED 灯带
- DHT11 温湿度传感器
- 水位传感器（2个）
- 继电器模块（控制风扇和气泵）
- 蜂鸣器
- USB摄像头

## 软件依赖
- Python 3.7+
- Flask
- rpi-ws281x
- RPi.GPIO
- psutil
- Adafruit_DHT
- 
## 安装依赖：
pip install -r requirements.txt

## 配置硬件引脚（修改 config.json）：

{
  "led_count": 10,
  "led_brightness": 230,
  "buzzer_pin": 17,
  "fan_pin": 24,
  "pump_pin": 22,
  "water_sensor_top_pin": 25,
  "water_sensor_bottom_pin": 23,
  "dht11_pin": 5
}

## 配置硬件引脚
```markdown
sudo python app.py
web访问： http://树莓派IP:5000


## **项目结构**
```markdown
├── app.py               # 主程序
├── config.json          # 配置文件
├── requirements.txt     # 依赖列表
├── README.md            # 项目文档
├── templates
│   └── index.html       # 前端页面
└── static               # 静态资源
    ├── css
    ├── js
    └── images



