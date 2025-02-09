### VERSION 0001 ***DO NOT REMOVE THIS LINE***

import machine
from machine import I2C, Pin,Timer,RTC,UART
from picozero import LED
from time import sleep,ticks_ms
import utime
import os
import LCD1602
import ujson as json
from errorclass import NewUpdateTime

from pzem import PZEM

os.chdir("/")
 

uart0 = machine.UART(0, tx=Pin(16), rx=Pin(17), baudrate=115200)   

uart = machine.UART(1,tx=machine.Pin(4),rx=machine.Pin(5), baudrate=9600)




GSM_PWR_KEY = LED(20)
POWER_ON_OFF_PIN  = LED(21)
GSM_STATUS_PIN = Pin(14, Pin.IN)

LCD_PWR = LED(15)

left_button=Pin(6,Pin.IN,Pin.PULL_UP)
center_button=Pin(7,Pin.IN,Pin.PULL_UP)
right_button=Pin(8,Pin.IN,Pin.PULL_UP)

rtc = RTC()

rtc.datetime([2020, 1, 21, 0, 10, 32, 36, 0])

print(rtc.datetime())

lcdTimer=Timer(-1)

debounce_time=0

display_index=0

date_flag = 0

power_parameter = (0,0,0,0,0,0)

# CLEANUP FUNCTION-----------/

def cleanup_resources():
    # Release GPIO and UART resources.
    POWER_ON_OFF_PIN.close()
    GSM_PWR_KEY.close()  # Properly deinitialize the LED object
    LCD_PWR.close()
    uart.deinit()
    uart0.deinit()# Deinitialize the UART
    sleep(5)
    print("Resources cleaned up.")
    
# GSM MODULE INTERFACE FUNCTIONS-------------------------------------------------------/

def sendCMD_waitResp(cmd, uart=uart0, timeout=2000):
    print("CMD: " + cmd)
    uart.write(cmd)
    return waitResp(uart, timeout)
    
    
def waitResp(uart=uart0, timeout=2000):
    prvMills = utime.ticks_ms()
    resp = b""
    while (utime.ticks_ms()-prvMills)<timeout:
        if uart.any():
            resp = b"".join([resp, uart.read()])
            if resp != '':
                ret_str = resp.decode()
                return(ret_str)

def send_data_as_message(data,uart=uart0):
    # Set the SMS message format to text
    sendCMD_waitResp('AT+CMGF=1\r\n')
    # Send the SMS message
    sendCMD_waitResp('AT+CMGS="7200382080"\r\n')
    utime.sleep(2)
    sendCMD_waitResp(data)
    utime.sleep(2)
    sendCMD_waitResp(chr(26))
    print("message sent")

def turnOnGSM():
    POWER_ON_OFF_PIN.on()
    utime.sleep(0.5)
    POWER_ON_OFF_PIN.off()
    utime.sleep(0.5)
    GSM_PWR_KEY.on()
    utime.sleep(2)
    GSM_PWR_KEY.off()

def turnOffGSM():
    POWER_ON_OFF_PIN.off()
    utime.sleep(2)
    POWER_ON_OFF_PIN.on()
    

def setDateTime():
    #send a serial command to get date from GSM Module
    input_datatime = sendCMD_waitResp('AT+CCLK?\r\n')#Feed the output of the buffer here
    datetime = input_datatime.split('"')
    input_datatime = sendCMD_waitResp('AT+CCLK?\r\n')#Feed the output of the buffer here
    datetime = input_datatime.split('"')
    datetime = datetime[1]
    datetime_list = [int("20" + datetime[0:2]),int(datetime[3:5]),int(datetime[6:8]),0,int(datetime[9:11]),int(datetime[12:14]),int(datetime[15:17]),0]
    print("Setting RTC")
    print(datetime_list)
    rtc.datetime(datetime_list)
    datetime_list = rtc.datetime()
    
    # Setting the date flag for the next day
    month = datetime_list[1]
    day = datetime_list[2] +1
    
    if(month<10):
        month = "0"+str(month)
    else:
        month = str(month)
    
    if(day<10):
        day = "0"+str(day)
    else:
        day = str(day)
          
    date_flag = str(datetime_list[0])+month+day+"00"+"00"
    
    
    saveDate(date_flag)

def gsmSetup():
    print(sendCMD_waitResp('ATE0\r\n'))
    utime.sleep(5)
    print(sendCMD_waitResp('AT+CNTP="14.139.60.107",22\r\n'))
    utime.sleep(5)
    print(sendCMD_waitResp('AT+CNTP\r\n'))
    
    
# PZEM-004T POWER ANALYSER FUNCTIONS---------------------------------------------------/


def getting_values():
   dev = PZEM(uart=uart)

# Set new address
   if dev.setAddress(0x05):
       print("New device address is {}".format(dev.getAddress()))
   if dev.read():
        voltage=str(dev.getVoltage())
        current=str(dev.getCurrent())
        power=str(dev.getActivePower())
        energy=str(dev.getActiveEnergy())
        frequency=str(dev.getFrequency())
        pf=str(dev.getPowerFactor())
        power_list = (voltage,current,power,energy,frequency,pf)
        dev.resetEnergy()
        return power_list
        

# USER INTERFACE CONTROL FUNCTIONS---------------------------------------------------/
def lcd_off(irqd):
    left_button.irq(handler=None)
    right_button.irq(handler=None)
    LCD_PWR.off()

def lcd_on():
    global power_parameter
    print("LCD ON")
    LCD_PWR.on()
    sleep(0.2)
    lcd=LCD1602.LCD1602(16,2)
    try:
        power_parameter = getting_values()
    except:
        power_parameter = (0,0,0,0,0,0)

def incrementIndex():
    global display_index
    if display_index >= 7:
        display_index = 1
    else:
        display_index += 1;
def decrementIndex():
    global display_index
    if display_index <= 1:
        display_index = 7
    else:
        display_index -= 1;

def center_button_pressed(pin):
    global display_index,debounce_time
    if (ticks_ms()-debounce_time) > 1000:
        if(display_index == 7):
            print("Sending Data")
            lcd.clear()
            lcd.setCursor(0, 0)
            lcd.printout("Sending Data ")
            lcd.setCursor(0, 1)
            lcd.printout(".....")
            lcdTimer.init(period=100000, mode=Timer.PERIODIC, callback=lcd_off)
            
            left_button.irq(handler=None)
            right_button.irq(handler=None)
            center_button.irq(handler=None)
            
            try:
                power_parameter = getting_values()
            except:
                power_parameter = (0,0,0,0,0,0)
            power_parameter = str(power_parameter)
            power_parameter = power_parameter[1:-1]
            
            turnOnGSM()
            sleep(20)
            gsmSetup()
            sleep(5)
            
            with open('config.json', 'r') as f:
                data = json.load(f)
            
            currentdate = getCurrentDate()
            
            send_data_as_message(data["deviceId"] +","+data["password"]+","+currentdate+","+power_parameter)
            logData(currentdate +":"+ power_parameter+"\n")
            
            setDateTime()
            turnOffGSM()
            
            center_button.irq(trigger=Pin.IRQ_FALLING, handler=center_button_pressed)
            
            display_index = 1
            lcd_on()
            changeLCD()
            left_button.irq(trigger=Pin.IRQ_FALLING, handler=left_button_pressed)
            right_button.irq(trigger=Pin.IRQ_FALLING, handler=right_button_pressed)
            lcdTimer.init(period=10000, mode=Timer.PERIODIC, callback=lcd_off)
            print("Center Button Pressed")
        else:    
            display_index = 1
            lcd_on()
            changeLCD()
            left_button.irq(trigger=Pin.IRQ_FALLING, handler=left_button_pressed)
            right_button.irq(trigger=Pin.IRQ_FALLING, handler=right_button_pressed)
            lcdTimer.init(period=10000, mode=Timer.PERIODIC, callback=lcd_off)
            print("Center Button Pressed")
        debounce_time=ticks_ms()

def left_button_pressed(pin):
    global debounce_time
    if (ticks_ms()-debounce_time) > 1000:
        decrementIndex()
        changeLCD()
        lcdTimer.deinit()
        lcdTimer.init(period=10000, mode=Timer.PERIODIC, callback=lcd_off)
        print("Left Button Pressed")
        debounce_time=ticks_ms()

def right_button_pressed(pin):
    global debounce_time
    if (ticks_ms()-debounce_time) > 1000:
        incrementIndex()
        changeLCD()
        lcdTimer.deinit()
        lcdTimer.init(period=10000, mode=Timer.PERIODIC, callback=lcd_off)
        print("Right Button Pressed")
        debounce_time=ticks_ms()

def checkTime():
    datetime_list = rtc.datetime()
    datetime = int(str(datetime_list[0])+str(datetime_list[1])+str(datetime_list[2]))
    if(datetime > date_flag):
        print("Sending Update")

def changeLCD():
    
    if(display_index == 0):
        lcd_off(1)
    elif(display_index == 1):
        lcd.clear()
        lcd.setCursor(2, 0)
        lcd.printout("Smart Meter")
        lcd.setCursor(4, 1)
        lcd.printout("Rev 0.3")
    elif(display_index == 2):
        lcd.clear()
        lcd.setCursor(0, 0)
        lcd.printout("Current:")
        lcd.setCursor(0, 1)
        lcd.printout(str(round(power_parameter[1],4))+" A")
    elif(display_index == 3):
        lcd.clear()
        lcd.setCursor(0, 0)
        lcd.printout("Voltage:")
        lcd.setCursor(0, 1)
        lcd.printout(str(power_parameter[0])+ " V")
    elif(display_index == 4):
        lcd.clear()
        lcd.setCursor(0, 0)
        lcd.printout("Power: ")
        lcd.setCursor(0, 1)
        lcd.printout(str(power_parameter[2])+ " W")
    elif(display_index == 5):
        lcd.clear()
        lcd.setCursor(0, 0)
        lcd.printout("Power Factor: ")
        lcd.setCursor(0, 1)
        lcd.printout(str(power_parameter[5]))
    elif(display_index == 6):
        lcd.clear()
        lcd.setCursor(0, 0)
        lcd.printout("Energy: ")
        lcd.setCursor(0, 1)
        lcd.printout(str(power_parameter[4])+ " Wh")
    elif(display_index == 7):
        lcd.clear()
        lcd.setCursor(1, 0)
        lcd.printout("Transmit Data ")
        lcd.setCursor(6, 1)
        lcd.printout("Now")
    else:
        print("Invalid index")  
    print(display_index)

# SYSTEM FUNCTIONS-----------------------------------------------------------/

def saveDate(date):
    file = open("date.cache", "w")
    file.write(date)
    file.close()
    print(date)
    
def readDate():
    f = open('date.cache')
    date = f.read()
    f.close()
    return date

def logData(data):
    file = open("log.txt", "a")
    file.write(data)
    file.close()
    print(date)

def getCurrentDate():
    datetime_list = rtc.datetime()
    
    if(datetime_list[1]<10):
        month = "0"+str(datetime_list[1])
    else:
        month = str(datetime_list[1])
    
    if(datetime_list[2]<10):
        day = "0"+str(datetime_list[2])
    else:
        day = str(datetime_list[2])

    if(datetime_list[4]<10):
        hour = "0"+str(datetime_list[4])
    else:
        hour = str(datetime_list[4])

    if(datetime_list[5]<10):
        minute = "0"+str(datetime_list[5])
    else:
        minute = str(datetime_list[5])
        
    date_flag = str(datetime_list[0])+month+day+hour+minute
    return date_flag
    

# MAIN CODE STARTS HERE ----------------------------------------------------------/
LCD_PWR.on()
sleep(0.2)
lcd=LCD1602.LCD1602(16,2)


center_button.irq(trigger=Pin.IRQ_FALLING, handler=center_button_pressed)

turnOffGSM()


try:
    date = readDate()
    print("Date Found: ")
    print(int(date))
    lcd.clear()
    lcd.setCursor(2, 0)
    lcd.printout("Setting Up")
    lcd.setCursor(2, 1)
    lcd.printout("Please Wait")
    turnOnGSM()
    sleep(20)
    gsmSetup()
    sleep(10)
    setDateTime()
    date = readDate()
    turnOffGSM()
    print(date)
    lcd.clear()
    lcd.setCursor(1, 0)
    lcd.printout("Setup Complete")
    sleep(2)

except:
    print("Date not set")
    print("Setting Date")
    lcd.clear()
    lcd.setCursor(2, 0)
    lcd.printout("Setting Up")
    lcd.setCursor(2, 1)
    lcd.printout("Please Wait")
    turnOnGSM()
    sleep(20)
    gsmSetup()
    sleep(10)
    setDateTime()
    date = readDate()
    print(date)
    turnOffGSM()
    lcd.clear()
    lcd.setCursor(1, 0)
    lcd.printout("Setup Complete")
    sleep(2)


changeLCD()

while(True):
    
    date = readDate()
    currentdate = getCurrentDate()
    
    if(int(currentdate) > int(date)):
        print("Date Threshold Crossed, Sending Data")
        try:
            power_parameter = getting_values()
            power_parameter = str(power_parameter)
            power_parameter = power_parameter[1:-1]
            turnOnGSM()
            sleep(20)
            gsmSetup()
            sleep(5)
            with open('config.json', 'r') as f:
                data = json.load(f)
            send_data_as_message(data["deviceId"] +","+data["password"]+","+currentdate+","+power_parameter)
            logData(currentdate +" : "+ power_parameter+"\n")
            setDateTime()
            turnOffGSM()
        except:
            print("No Power")
    else:
        print("Date Flag : "+ date)
        print("Current Date: "+currentdate)
        print("today is:"+currentdate[6:8])
        with open('config.json', 'rt') as file:
            data = json.load(file)
            file.close()
        updateflag = int(data["hasUpdated"])
        print('update flag is',updateflag)
        if updateflag==0:
            cleanup_resources()
            raise NewUpdateTime('update time has come')
        elif int(currentdate[6:8])%7!=0:
            updateflag==0
            with open('config.json', 'rt') as file:
                data = json.load(file)
                file.close()
            data['hasUpdated']=0
            with open('config.json', 'wt') as write:
                json.dump(data, write)
                write.close()
    sleep(3)
        
        


