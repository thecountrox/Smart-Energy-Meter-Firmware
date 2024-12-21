import machine
from machine import UART,Pin
from picozero import LED
import time
import re

# init uart
uart = machine.UART(0, tx=Pin(16), rx=Pin(17), baudrate=115200)

# power and status pins
GSM_PWR_KEY = LED(20)
POWER_ON_OFF_PIN  = LED(21)

# turn on gsm
def turnOnGSM():
    POWER_ON_OFF_PIN.on()
    time.sleep(0.5)
    POWER_ON_OFF_PIN.off()
    time.sleep(0.5)
    GSM_PWR_KEY.on()
    time.sleep(2)
    GSM_PWR_KEY.off()

# turn off gsm
def turnOffGSM():
    POWER_ON_OFF_PIN.off()
    time.sleep(2)
    POWER_ON_OFF_PIN.on()


# send cmds to gms and read with delay 
def send_command(cmd, delay=2):
    uart.write(cmd.encode('utf-8') + b'\r\n')
    time.sleep(delay)
    return uart.read()

def send_raw(cmd, delay=1):
    # Send an AT command and return the response.
    uart.write(cmd + b'\r\n')
    time.sleep(delay)
    return uart.read()

def initGsm():
    # tell gsm module to not talk back to its creator
    # print (send_command('ATE0'))
    print(send_command('AT+CMEE=2'))
    print(send_command('AT'))
    print(send_command('AT+CGATT=1')) # connect gprs
    print(send_command('AT+CGDCONT=1,"IP","airtelgprs.com"')) # config pdp airtel apn
    # set 4g and gprs
    
def set_network_mode(mode):
    if mode == '4g':
        return send_command('AT+CNMP=38')
    elif mode == 'gprs':
        return send_command('AT+CNMP=13')

    
# send http request
def send_request(url):
    send_command('AT+HTTPINIT')
    send_raw(f'AT+HTTPPARA="URL","{url}"'.encode())
    response = send_command('AT+HTTPACTION=0')
    time.sleep(1)
    print('response: ',response.decode('utf-8', 'ignore'))
    data = get_content(getsize(response))
    return data

def getsize(response):
    # Search for the response code and size
    match = re.search(r'HTTPACTION: \d+,200,(\d+)', response)
    
    if match:
        # Extract the size from the match and convert it to an integer
        size = int(match.group(1))
        print(f"Buffer size set to: {size}")
        return size
    else:
        print("No 200 response found.")
        return 0

def get_content(total_size, chunk_size=200):
    """Read the HTTP response in chunks and clean the data."""
    offset = 0
    data = ""

    while offset < total_size:
        # Send AT+HTTPREAD command with the current offset and chunk size
        cmd = f'AT+HTTPREAD={offset},{chunk_size}'
        response = send_raw(f'AT+HTTPREAD={offset},{chunk_size}'.encode(),0.1)
        if response:
            # Decode response and split into lines
            lines = response.decode('utf-8', 'ignore').split("\r\n")
            
            for i, line in enumerate(lines):
                 # Remove carriage returns that occur between GSM metadata lines
                if line.startswith("AT+HTTPREAD"):
                     line = line.replace("\r", "")  # Clean only GSM metadata lines
                 
                 # Skip GSM metadata completely
                if line.startswith("AT+HTTPREAD") or line.startswith("+HTTPREAD") or line == "OK":
                    continue
                
                # Append valid data lines
                data += line
        
            print(f"Processed {len(data)} bytes so far at offset {offset}.")
        else:
            print(f"No response for offset {offset}.")
            break

        offset += chunk_size
    send_command('AT+HTTPTERM')
    return data


def save_to_file(data, filename):
    try:
        cleaned_data = data.replace("\r", "")
        with open(filename, 'wb') as file:
            file.write(cleaned_data.encode('utf-8'))
        print(f"Data saved to {filename}")
    except Exception as e:
        print(f"Error saving file: {e}") 

def send_request_save_file(url,filename):
    print('switching to 4g')
    set_network_mode('4g')
    data = send_request(url)
    save_to_file(data,filename)
    print('switching to gprs')
    set_network_mode('gprs')

def pdp_state(flag):
    if flag==1:
        print('enabling pdp')
        print(send_command('AT+CGACT=1,1'))
        time.sleep(5)
    elif flag==0:
        print('disabling pdp')
        print(send_command('AT+CGATT=0'))
        time.sleep(1)
def cleanup_resources():
    #Release GPIO and UART resources.
    POWER_ON_OFF_PIN.close()
    GSM_PWR_KEY.close()
    uart.deinit()  # Deinitialize the UART
    print("Resources cleaned up.")
        
turnOnGSM()
time.sleep(5)
initGsm()
# activate pdp context
pdp_state(0)
pdp_state(1)

send_request_save_file('http://13.48.26.58/smartmeter.py','UPDATE_smartmeter.py')
pdp_state(0)
turnOffGSM()
cleanup_resources()
# check pdp
# send_command('AT+CGACT?')
# send_command('AT+CGDCONT?')
# check address
# send_command('AT+CGPADDR=1')
# check registration
# send_command('AT+CREG?')
# check network mode
# send_command('AT+CPSI?')
