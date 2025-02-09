import time
from machine import Pin,I2C
from lcd_api import LcdApi
from pico_i2c_lcd import I2cLcd

I2C_ADDR     = 0x3e
I2C_NUM_ROWS = 2
I2C_NUM_COLS = 16

i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=400000)
lcd = I2cLcd(i2c, I2C_ADDR, I2C_NUM_ROWS, I2C_NUM_COLS)    
time.sleep(1)
lcd.clear()
lcd.move_to(0,0)
lcd.putstr("Pico LCD")
lcd.move_to(0,1)
lcd.putstr("Tutorial")