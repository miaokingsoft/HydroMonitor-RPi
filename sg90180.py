import RPi.GPIO as GPIO
import time

class SG90Servo:
    def __init__(self, gpio_pin=26, frequency=50):
        self.gpio_pin = gpio_pin
        self.frequency = frequency
        self._initialized = False
        
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.gpio_pin, GPIO.OUT)
            self.pwm = GPIO.PWM(self.gpio_pin, self.frequency)
            self.pwm.start(0)
            self._initialized = True            
        except Exception as e:           
            raise
        
    def set_angle(self, angle):
        """
        设置舵机角度
        :param angle: 目标角度 (0-180度)
        """
        if angle < 0:
            angle = 0
        elif angle > 180:
            angle = 180
            
        # SG90舵机角度与占空比转换公式
        duty_cycle = (angle / 18)+2
        self.pwm.ChangeDutyCycle(duty_cycle)
        time.sleep(0.3)  # 给舵机时间转动到指定位置
    
    def sweep(self, start_angle=0, end_angle=180, step=5, delay=0.05):
        """
        舵机扫动函数
        :param start_angle: 起始角度
        :param end_angle: 结束角度
        :param step: 步进角度
        :param delay: 每步延迟时间(秒)
        """
        if start_angle < end_angle:
            for angle in range(start_angle, end_angle + 1, step):
                self.set_angle(angle)
                time.sleep(delay)
        else:
            for angle in range(start_angle, end_angle - 1, -step):
                self.set_angle(angle)
                time.sleep(delay)

    def touwei(self): 
        print("舵机回位准备投喂")
        self.set_angle(180)
        print("舵机到180度")
        time.sleep(2)        
        print("设置舵机回位")
        self.set_angle(0)
        time.sleep(2) 
        print("投喂结束")
        self.pwm.ChangeDutyCycle(0) # 关闭PWM信号，防止舵机抖动

        

    

    
    def cleanup(self):
        """安全的资源清理"""
        if self._initialized:
            try:
                self.pwm.stop()
                GPIO.cleanup(self.gpio_pin)
                self._initialized = False
                
            except Exception as e:
                print(f"清理资源时出错: {e}")





# 演示程序
if __name__ == "__main__":
    try:
         # 创建舵机实例，使用GPIO18
        servo = SG90Servo(gpio_pin=26)
        time.sleep(10)
        #for _ in range(3):
        #    servo.touwei()
        #    time.sleep(5)
        
        #print("舵机扫动演示 (0-180度)")
        #servo.sweep(0, 180)
        
        #print("舵机扫动演示 (180-0度)")
        #servo.sweep(180, 0)
        
        #print("设置舵机回到中间位置 (90度)")
        #servo.set_angle(180)
        
    except KeyboardInterrupt:
        print("程序被用户中断")
    finally:
        # 确保清理GPIO资源
        servo.cleanup()
        print("程序结束，GPIO已清理")