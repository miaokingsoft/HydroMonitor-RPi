# HydroMonitor-RPi 
# 闲沐智能鱼缸系统v1.2

基于树莓派的智能鱼缸监控系统，使用 Flask 构建 Web 界面，支持以下功能：

- 实时查看鱼缸视频直播画面
- 可控制灯带颜色和亮度
- 实时检测室温、水温、湿度，并记录数据可视化
- 可远程开启（关闭）气泵、风扇、灯光
- 可手动投喂鱼食或可按计划投喂，并记录入数据库
- web页面支持浏览器和手机访问，可配合Frp实现公网访问

![Web界面](/Ui12.png)
![喂食计划管理](/Ui12-2.png)
![监控数据统计](/Ui12-4.png)

## 功能特性
- 有人访问时，鱼缸led灯带亮起，并发出滴滴声（蜂鸣器提醒）
- 实时检测水位，高于或低于预警水位时会发邮件通知
- LED 灯带控制（颜色、亮度）在web页面可设置
- 投喂鱼食会记录在数据库，每次投喂间隔必须在3小时以上
- 直播画面通过识别内外网更换访问地址，保证画面流畅
- 提供【签到】功能，蜂鸣器会发出滴滴提醒
- 系统状态监控（CPU、内存）

## 硬件要求
- 树莓派（建议3B以上，我用的是4B+）
- WS2812B LED 灯带 10个灯珠较合适
- DHT11 温湿度传感器
- 4020 5V 风扇（4个，XH2.54插头)
- 水位传感器（2个）（在缸壁外侧用双面胶帖上，高低预警水位线各一个）
- 继电器模块（控制风扇和气泵，2路5V）
- 蜂鸣器 （高电平触发）
- SG90 180度舵机
- DS18B20水温监控模块（探头和板一套）
- USB摄像头（最好有自动对焦功能）
- 5V 3A电源（给风扇、气泵供电）
- PCB 洞洞板、线等等耗材（谁能帮我画PCB板呀将全部模块集成到一个小板上，求助大神）
- 
## 硬件接线板
!(智能鱼缸接线板)(https://img.alicdn.com/bao/uploaded/i1/O1CN01SVvET52HMnw9oyIbw_!!4611686018427384401-0-fleamarket.jpg_Q90.jpg)

如有需要 [点击这里](https://www.goofish.com/item?spm=a21ybx.personal.feeds.1.596b2358xB7LkT&id=965639435219&categoryId=125952002) 请访问  


## 3D打印件
- [风扇支架](https://makerworld.com.cn/zh/models/1435672-yu-gang-feng-shan-zhi-jia-x4#profileId-1559928)
- 自动喂食器 （整理中）

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
```markdown
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

