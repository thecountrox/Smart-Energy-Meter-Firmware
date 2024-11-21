from machine import I2C, Pin, Timer, RTC, UART
from time import sleep, ticks_ms
import utime
import os
import ujson as json

from libs import LCD1602
from libs.pzem import PZEM
from libs.picozero import LED

# Global Variables
debounce_time = 0  # Debounce for button presses
display_index = 0  # Index for LCD display pages
power_parameter = (0, 0, 0, 0, 0, 0)  # Placeholder for power parameters
date_flag = 0  # Date flag for scheduled updates
left_button=Pin(6,Pin.IN,Pin.PULL_UP) # Buttons have to be global for simplified irq logic
center_button=Pin(7,Pin.IN,Pin.PULL_UP)
right_button=Pin(8,Pin.IN,Pin.PULL_UP)
lcdTimer=Timer(-1) # Lcd timing

def setupHardware():

    # Initialize hardware components (UART, LEDs, RTC, and LCD power) and return them
    uart0 = machine.UART(0, tx=Pin(16), rx=Pin(17), baudrate=115200)   
    uart = machine.UART(1,tx=machine.Pin(4),rx=machine.Pin(5), baudrate=9600)
    GSM_PWR_KEY = LED(20)
    POWER_ON_OFF_PIN = LED(21)
    LCD_PWR = LED(15)
    rtc = RTC()
    rtc.datetime([2020, 1, 21, 0, 10, 32, 36, 0])

    # Power on LCD
    LCD_PWR.on()
    sleep(0.2)

    # Initialize LCD
    lcd = LCD1602.LCD1602(16, 2)
    print("Hardware Setup Complete")
    return uart0, uart, GSM_PWR_KEY, POWER_ON_OFF_PIN, LCD_PWR, rtc, lcd

# GSM MODULE INTERFACE FUNCTIONS-------------------------------------------------------/

def sendCmdWaitResp(cmd, uart, timeout=2000):
    print("CMD: " + cmd)
    uart.write(cmd)
    return waitResp(uart, timeout)


def waitResp(uart, timeout=2000):
    prvMills = utime.ticks_ms()
    resp = b""
    while (utime.ticks_ms() - prvMills) < timeout:
        if uart.any():
            resp = b"".join([resp, uart.read()])
            if resp != "":
                return resp.decode()


def sendDataAsMessage(data, uart, relay_number):
    # Set the SMS message format to text
    sendCmdWaitResp("AT+CMGF=1\r\n", uart)
    # Send the SMS message
    sendCmdWaitResp(f'AT+CMGS="{relay_number}"\r\n', uart)
    utime.sleep(2)
    sendCmdWaitResp(data, uart)
    utime.sleep(2)
    sendCmdWaitResp(chr(26), uart)
    print("Message sent")


def turnOnGSM(POWER_ON_OFF_PIN, GSM_PWR_KEY):
    POWER_ON_OFF_PIN.on()
    utime.sleep(0.5)
    POWER_ON_OFF_PIN.off()
    utime.sleep(0.5)
    GSM_PWR_KEY.on()
    utime.sleep(2)
    GSM_PWR_KEY.off()


def turnOffGSM(POWER_ON_OFF_PIN):
    POWER_ON_OFF_PIN.off()
    utime.sleep(2)
    POWER_ON_OFF_PIN.on()


def setDateTime(uart, rtc):
    #send a serial command to get date from GSM Module
    input_datetime = sendCmdWaitResp("AT+CCLK?\r\n", uart)#Feed the output of the buffer here
    datetime = input_datetime.split('"')
    datetime = datetime[1]
    datetime_list = [
        int("20" + datetime[0:2]),
        int(datetime[3:5]),
        int(datetime[6:8]),
        0,
        int(datetime[9:11]),
        int(datetime[12:14]),
        int(datetime[15:17]),
        0,
    ]
    print("Setting RTC")
    rtc.datetime(datetime_list)

    # Setting date flag for the next day
    month = f"{datetime_list[1]:02}"
    day = f"{datetime_list[2] + 1:02}"
    global date_flag
    date_flag = f"{datetime_list[0]}{month}{day}0000"
    saveDate(date_flag)


def gsmSetup(uart):
    print(sendCmdWaitResp("ATE0\r\n", uart))
    utime.sleep(5)
    print(sendCmdWaitResp('AT+CNTP="14.139.60.107",22\r\n', uart))
    utime.sleep(5)
    print(sendCmdWaitResp("AT+CNTP\r\n", uart))


# PZEM-004T POWER ANALYSER FUNCTIONS---------------------------------------------------/

def getting_values(uart):
    dev = PZEM(uart=uart)
    # Set new address
    if dev.setAddress(0x05):
        print("New device address is {}".format(dev.getAddress()))
    if dev.read():
        return (
            dev.getVoltage(),
            dev.getCurrent(),
            dev.getActivePower(),
            dev.getActiveEnergy(),
            dev.getFrequency(),
            dev.getPowerFactor(),
        )
    dev.resetEnergy()
    return (0, 0, 0, 0, 0, 0)

# USER INTERFACE CONTROL FUNCTIONS---------------------------------------------------/
def lcdOff(lcd, LCD_PWR, irqd): # irqd is passed for the sake of passing it
    left_button.irq(handler=None)
    right_button.irq(handler=None)
    LCD_PWR.off()
    lcd.clear()


def lcdOn(LCD_PWR, uart):
    global power_parameter
    print("LCD ON")
    LCD_PWR.on()
    sleep(0.2)
    lcd = LCD1602.LCD1602(16, 2)
    try:
        power_parameter = getting_values(uart)
    except:
        power_parameter = (0, 0, 0, 0, 0, 0)
    return lcd

def center_button_pressed(pin, POWER_ON_OFF_PIN, LCD_PWR, GSM_PWR_KEY, uart, rtc, relay_number, lcd):
    global display_index,debounce_time
    if (ticks_ms()-debounce_time) > 1000:
        if(display_index == 6):
            print("Sending Data")
            lcd.clear()
            lcd.setCursor(0, 0)
            lcd.printout("Sending Data ")
            lcd.setCursor(0, 1)
            lcd.printout(".....")
            lcdTimer.init(period=100000, mode=Timer.PERIODIC, callback=lcdOff)
            
            left_button.irq(handler=None)
            right_button.irq(handler=None)
            center_button.irq(handler=None)
            
            try:
                power_parameter = getting_values(uart)
            except:
                power_parameter = (0,0,0,0,0,0)
            power_parameter = str(power_parameter)
            power_parameter = power_parameter[1:-1]
            
            turnOnGSM(POWER_ON_OFF_PIN, GSM_PWR_KEY)
            sleep(20)
            gsmSetup(uart)
            sleep(5)
            
            with open('config.json', 'r') as f:
                data = json.load(f)
            
            currentdate = getCurrentDate(rtc)
            
            sendDataAsMessage(data["deviceId"] +","+data["password"]+","+currentdate+","+power_parameter, uart, relay_number)
            logData(currentdate +":"+ power_parameter+"\n")
            
            setDateTime(uart,rtc)
            turnOffGSM(POWER_ON_OFF_PIN)
            
            center_button.irq(trigger=Pin.IRQ_FALLING, handler=center_button_pressed)
            
            display_index = 1
            lcdOn(LCD_PWR, uart)
            changeLCD(lcd)
            left_button.irq(trigger=Pin.IRQ_FALLING, handler=left_button_pressed)
            right_button.irq(trigger=Pin.IRQ_FALLING, handler=right_button_pressed)
            lcdTimer.init(period=10000, mode=Timer.PERIODIC, callback=lcdOff)
            print("Center Button Pressed")
        else:    
            display_index = 1
            lcdOn(LCD_PWR, uart)
            changeLCD(lcd)
            left_button.irq(trigger=Pin.IRQ_FALLING, handler=left_button_pressed)
            right_button.irq(trigger=Pin.IRQ_FALLING, handler=right_button_pressed)
            lcdTimer.init(period=10000, mode=Timer.PERIODIC, callback=lcdOff)
            print("Center Button Pressed")
        debounce_time=ticks_ms()

def left_button_pressed(pin):
    global debounce_time
    if (ticks_ms()-debounce_time) > 1000:
        decrementIndex()
        changeLCD(lcd)
        lcdTimer.deinit()
        lcdTimer.init(period=10000, mode=Timer.PERIODIC, callback=lcdOff)
        print("Left Button Pressed")
        debounce_time=ticks_ms()

def right_button_pressed(pin):
    global debounce_time
    if (ticks_ms()-debounce_time) > 1000:
        incrementIndex()
        changeLCD(lcd)
        lcdTimer.deinit()
        lcdTimer.init(period=10000, mode=Timer.PERIODIC, callback=lcdOff)
        print("Right Button Pressed")
        debounce_time=ticks_ms()


def changeLCD(lcd):
    global display_index, power_parameter
    lcd.clear()
    if display_index == 0:
        lcd.clear()
    elif display_index == 1:
        lcd.setCursor(2, 0)
        lcd.printout("Smart Meter")
        lcd.setCursor(4, 1)
        lcd.printout("Rev 0.3")
    elif display_index == 2:
        lcd.setCursor(0, 0)
        lcd.printout("Current:")
        lcd.setCursor(0, 1)
        lcd.printout(f"{round(power_parameter[1], 4)} A")
    elif display_index == 3:
        lcd.setCursor(0, 0)
        lcd.printout("Voltage:")
        lcd.setCursor(0, 1)
        lcd.printout(f"{power_parameter[0]} V")
    elif display_index == 4:
        lcd.setCursor(0, 0)
        lcd.printout("Power:")
        lcd.setCursor(0, 1)
        lcd.printout(f"{power_parameter[2]} W")
    elif display_index == 5:
        lcd.setCursor(0, 0)
        lcd.printout("Power Factor:")
        lcd.setCursor(0, 1)
        lcd.printout(f"{power_parameter[5]}")
    elif display_index == 6:
        lcd.setCursor(0, 0)
        lcd.printout("Energy:")
        lcd.setCursor(0, 1)
        lcd.printout(f"{power_parameter[4]} Wh")
    elif display_index == 7:
        lcd.setCursor(1, 0)
        lcd.printout("Transmit Data")
        lcd.setCursor(6, 1)
        lcd.printout("Now")
    else:
        print("Invalid index")
    print(display_index)


def incrementIndex():
    global display_index
    display_index = 1 if display_index >= 7 else display_index + 1


def decrementIndex():
    global display_index
    display_index = 7 if display_index <= 1 else display_index - 1


def saveDate(date):
    with open("date.cache", "w") as file:
        file.write(date)
    print(date)


def readDate():
    with open("date.cache", "r") as file:
        return file.read()


def logData(data):
    with open("log.txt", "a") as file:
        file.write(data)
    print(data)


def getCurrentDate(rtc):
    datetime_list = rtc.datetime()
    return (
        f"{datetime_list[0]}"
        f"{datetime_list[1]:02}"
        f"{datetime_list[2]:02}"
        f"{datetime_list[4]:02}"
        f"{datetime_list[5]:02}"
    )


# MAIN CODE STARTS HERE ----------------------------------------------------------/
def main():
    global debounce_time
    # Hardware Setup
    uart0, uart, GSM_PWR_KEY, POWER_ON_OFF_PIN, LCD_PWR, rtc, lcd = setupHardware()

    # Read Configuration
    with open("config.json", "r") as f:
        data = json.load(f)
    relay_number = data["relay_number"]
    os.chdir("/")

    # Setup LCD and Buttons
    LCD_PWR.on()
    sleep(0.2)
    lcd = LCD1602.LCD1602(16, 2)
    center_button.irq(trigger=Pin.IRQ_FALLING, handler=lambda pin: center_button_pressed(pin, POWER_ON_OFF_PIN, LCD_PWR, GSM_PWR_KEY, uart, rtc, relay_number, lcd))
    turnOffGSM(POWER_ON_OFF_PIN)
    date = readDate()
    print(f"Date Found: {date}")

    try:
        lcd.clear()
        lcd.setCursor(2, 0)
        lcd.printout("Setting Up")
        lcd.setCursor(2, 1)
        lcd.printout("Please Wait")
        turnOnGSM(POWER_ON_OFF_PIN, GSM_PWR_KEY)
        sleep(20)
        gsmSetup(uart0)
        sleep(10)
        setDateTime(uart0, rtc)
        date = readDate()
        turnOffGSM(POWER_ON_OFF_PIN)
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
        turnOnGSM(POWER_ON_OFF_PIN, GSM_PWR_KEY)
        sleep(20)
        gsmSetup(uart0)
        sleep(10)
        setDateTime(uart0, rtc)
        date = readDate()
        print(date)
        turnOffGSM(POWER_ON_OFF_PIN)
        lcd.clear()
        lcd.setCursor(1, 0)
        lcd.printout("Setup Complete")
        sleep(2)

    lcd = lcdOn(LCD_PWR, uart)
    changeLCD(lcd)

    # Main Loop
    while (True):
        currentdate = getCurrentDate(rtc)
        if int(currentdate) > int(date):
            print("Date Threshold Crossed, Sending Data")
            try:
                power_parameter = getting_values(uart)
                power_parameter = str(power_parameter)[1:-1]
                turnOnGSM(POWER_ON_OFF_PIN, GSM_PWR_KEY)
                sleep(20)
                gsmSetup(uart0)
                sleep(5)
                sendDataAsMessage(
                    f"{data['deviceId']},{data['password']},{currentdate},{power_parameter}",
                    uart0,
                    relay_number,
                )
                logData(f"{currentdate} : {power_parameter}\n")
                setDateTime(uart0, rtc)
                turnOffGSM(POWER_ON_OFF_PIN)
            except:
                print("No Power")
        else:
            print(f"Date Flag : {date}")
            print(f"Current Date: {currentdate}")
        sleep(3)
