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

def cleanup_resources():
    # Release GPIO and UART resources.
    POWER_ON_OFF_PIN.close()
    GSM_PWR_KEY.close()  # Properly deinitialize the LED object
    uart.deinit()
    uart0.deinit()# Deinitialize the UART
    print("Resources cleaned up.")
    
def sendCMD_waitResp(cmd, uart=uart0, timeout=2000):
    print("CMD: " + cmd)
    uart.write(cmd)
    return waitResp(uart, timeout)
    
def sendCMD(cmd,uart=uart0, timeout=2000):
    print("CMD: " + cmd)
    uart.write(cmd)
    
def waitResp(uart=uart0, timeout=6000):
    prvMills = utime.ticks_ms()
    resp = b""
    while (utime.ticks_ms()-prvMills)<timeout:
        if uart.any():
            resp = b"".join([resp, uart.read()])
            if resp != '':
                ret_str = resp.decode()
                return(ret_str)


def set_sms_text_mode(uart=uart0, max_retries=5, delay=1):
    for attempt in range(max_retries):
        response = sendCMD_waitResp('AT+CMGF=1', uart)
        if 'OK' in response:
            print("SMS text mode enabled successfully.")
            return True
        else:
            print(f"Attempt {attempt + 1} failed. Retrying in {delay} seconds...")
            utime.sleep(delay)
    print("Failed to set SMS text mode after multiple attempts.")
    return False

def waitResp_Valid(expected_response, uart=uart0, timeout=6000):
    start_time = utime.ticks_ms()
    resp = b""

    while (utime.ticks_ms() - start_time) < timeout:
        if uart.any():
            resp += uart.read()
            # Decode and check for the expected response
            decoded_resp = resp.decode('utf-8', 'ignore')
            if expected_response in decoded_resp:
                return decoded_resp

    # Return None if the response wasn't received within the timeout
    print(f"Timed out waiting for: {expected_response}")
    return None

def send_data_as_message(message, uart=uart0):
    # Set the SMS message format to text
    sendCMD_waitResp('AT+CMGF=1\r\n')
    
    # Load phone number from config.json
    try:
        with open('config.json', 'rt') as f:
            data1 = json.load(f)
            phone = str(data1['phoneNumber']).strip()  # Convert to string and strip whitespace
    except Exception as e:
        print(f"Error loading phone number: {e}")
        return

    # Validate phone number format
    if not phone.isdigit() and not (phone.startswith('+') and phone[1:].isdigit()):
        print(f"Invalid phone number format: '{phone}'")
        return

    # Debug phone number
    print(f"Sending SMS to: {phone}")

    # Send the SMS message
    response = sendCMD(f'AT+CMGS="{phone}"\r\n')
    waitResp_Valid('>')
    res = sendCMD_waitResp(message)  # Send the message
    print(res)
    res = sendCMD_waitResp(chr(26))  # Send Ctrl+Z to finish
    print(res)
    print("Message sent.")

    
send_data_as_message('1001,123,202502081738,0,0,0,0,0,0')
