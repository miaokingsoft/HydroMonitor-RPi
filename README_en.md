# HydroMonitor-RPi 
# Xianmu Smart Aquarium System v1.3

[中文](README.md)

An intelligent aquarium monitoring system based on Raspberry Pi, built with Flask for the web interface, and provides a sensor connection board PCB:

## Features
- After connecting a USB camera to the Raspberry Pi, real-time video live stream of the aquarium can be viewed
- Remotely control LED strip color and brightness, configurable on the web page
- Real-time monitoring of room temperature, water temperature, humidity, and data visualization statistics
- Remotely turn on (off) air pump, water pump, fan, lights, feed fish, etc.
- Create execution plans to automatically turn on/off water pump, air pump, feeding, etc., and log execution records into the database
- When someone visits, the aquarium LED strip lights up and emits a beep sound (buzzer reminder)
- Real-time water level detection, sends email notification if above or below warning levels
- Fish feeding records are stored in the database, each feeding interval must be more than 3 hours
- The live stream switches access addresses based on internal/external network recognition to ensure smooth playback
- Provides a [Check-in] function, the buzzer will emit a beep reminder
- Automatically turn fan on or off based on high/low water temperature thresholds
- System status monitoring (CPU, memory, activity, network traffic)
- Provides network access for data visualization statistics
- Web page supports browser and mobile access, can be used with Frp for public network access

![Web Interface](/v13.png)
![Feeding Schedule Management](/Ui12-2.png)
![Monitoring Data Statistics](/Ui12-4.png)

## Hardware Requirements
- Raspberry Pi (recommended 3B or above, I use 4B+)
- WS2812B LED Strip (10 LEDs is suitable)
- DHT11 Temperature and Humidity Sensor
- 4020 5V Fan (4 pieces, XH2.54 connector)
- Water Level Sensor (2 pieces) (Attach to the outside of the tank wall with double-sided tape, one each at the high and low warning water lines)
- Relay Module (Controls fan and air pump, 4-channel 5V, low-level trigger)
- Buzzer (High-level trigger)
- SG90 180-degree Servo (Recommend using a better servo)
- DS18B20 Water Temperature Monitoring Module (Probe and board set)
- USB Camera (Preferably with autofocus)
- 5V 3A Power Supply (Powers fans, air pump)
- Smart Aquarium Connection Board ([PCB has been manufactured, visit here if needed](https://www.goofish.com/item?spm=a21ybx.personal.feeds.1.596b2358xB7LkT&id=965639435219&categoryId=125952002))
- Dupont wires and other consumables

## Hardware Connection Board
![Smart Aquarium Connection Board](/PCB.jpg)

- 4 independent DC power supply interfaces
- Buzzer 3P header
- 2-channel water level monitoring 3P header
- LED 3P pin header
- Temperature & Humidity 3P pin header
- 4-channel Relay 6p+8p pin header
- 1-channel water temperature monitoring 3P header
- Spare 5v, 3v3, 4x GPIO pin header
- 18P Pin Header (Connect to Raspberry Pi using Dupont wires)
If needed [Please click here to visit](https://www.goofish.com/item?spm=a21ybx.personal.feeds.1.596b2358xB7LkT&id=965639435219&categoryId=125952002)

## Connection Diagram with Raspberry Pi
![How to connect to Raspberry Pi](/c.png)

## 3D Printed Parts
- [Fan Bracket](https://makerworld.com.cn/zh/models/1435672-yu-gang-feng-shan-zhi-jia-x4#profileId-1559928)
- [Automatic Feeder](https://makerworld.com.cn/zh/models/1509194-zhi-neng-yu-gang-xi-tong-zu-jian-zhi-zi-dong-wei-y?from=search#profileId-1647953)
- [Adjustable Power Supply Wall Mount Bracket](https://makerworld.com.cn/zh/models/1509171-ke-diao-12vdian-yuan-bi-gua-zhi-jia#profileId-1647928)
- PCB Board Wall Mount Bracket (Organizing)
- LED Strip Mounting Components for Aquarium Wall (Organizing)
- Cable Conduit Clips (Organizing)
- 370 Water Pump Bracket (Organizing)
- Drip Irrigation Head (Organizing)

## Install Motion on Raspberry Pi
```
sudo apt update
sudo apt install motion
```
- Note: The version in the Raspbian repository might not be the latest. If you need the latest features or bug fixes, you can compile and install from source (process is slightly more complex, refer to official documentation).
- Main configuration file: /etc/motion/motion.conf This is the global configuration file, modifying it requires root privileges (sudo nano /etc/motion/motion.conf).
- Restart the service after modification to take effect:
```
sudo service motion restart
# or
sudo systemctl restart motion.service
 ```
## Basic Camera Usage Process
- Connect the camera: Plug the USB camera into the Raspberry Pi USB port, or correctly connect the CSI camera and enable it (sudo raspi-config > Interface Options > Legacy Camera or Camera > Enable).
- Start the service: sudo service motion start
- Test access: Access http://<Raspberry Pi IP>:8081 (or the port you set) from a browser on the Raspberry Pi or a computer/phone on the same local network to view the live stream.

## Software Dependencies
- Python 3.7+
- Flask
- rpi-ws281x
- RPi.GPIO
- psutil
- Adafruit_DHT
```
sudo apt-get install python3-pip python3-dev
pip install Adafruit-DHT RPi.GPIO psutil flask pytz tzlocal rpi-ws281x
pip install smtplib email
```

## Configure Hardware Pin Description (Modify config.json):
```
{
  "led_count": 10, #Number of LED beads
  "led_brightness": 230, #Brightness
  "active_color": [0, 100, 0], #Color when triggered
  "idle_color": [0, 0, 0], #Color when idle
  "buzzer_pin": 17, #Buzzer pin
  "buzzer_beep_duration": 0.2, #Beep duration
  "buzzer_beep_interval": 0.1, #Beep interval
  "fan_pin": 24,  # Fan control pin
  "fan_enabled": False,  # Fan status
  "pump_pin": 6,  # Air pump control pin originally (GPIO6)
  "pump_enabled": False,  # Air pump status
  "water_pump_pin": 19,  # Water pump control pin (GPIO19)
  "water_pump_enabled": False,  # Water pump status
  "water_sensor_top_pin": 25, #High water level pin
  "water_sensor_bottom_pin": 23, #Low water level pin
  "dht11_pin": 5, #Temperature and humidity module pin
  "database_path": "/var/lib/fishtank/sensor_data.db", #Database path
   "timezone": "Asia/Shanghai", #Timezone
  "max_temperature": 30, #High temperature threshold
  "min_temperature": 27  #Low temperature threshold
}
```

## Run

### Execute on Raspberry Pi
```
sudo python app.py
sudo python fishtank.py
```
### Client browser or mobile access: http://RaspberryPiIP:5000

## **Project Structure**
```
├── app.py               # Main program
├── config.json          # Configuration file
├── fishtank.py          # Water temperature, water level, humidity, room temperature collection and execution program
├── opendb.py          # Database initialization program
├── sg90180.py         # Servo control library, used for controlling the servo during feeding
├── requirements.txt     # Dependency list
├── README.md            # Project documentation
├── templates
│   └── index.html       # Frontend page
|   └── feeding.html     # Feeding schedule management page
|   └── charts.html     # Environmental data statistics page
└── static               # Static resources
    ├── css
    ├── js
    └── images
```

## Contact Information
- Author: MiaoKing
- Email: 7740840@qq.com
- Douyin: @闲沐工坊
- QQ: 7740840
