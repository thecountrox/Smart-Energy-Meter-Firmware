import os
import sys
import ujson as json
import gc
from errorclass import NewUpdateTime
from sys import modules

def reload(module_name):
    if module_name in sys.modules:
        del sys.modules[module_name]  # Remove the cached module
    return __import__(module_name)
    
def backup():
    print('backing up')
    with open('smartmeter.py', 'rt') as file:
        buffer = file.read()
        with open('/backup/smartmeter.py', 'wt') as backup:
            backup.write(buffer)
            
def update():
    import gsm_update #This runs the update file
    current = getcode('smartmeter.py')
    try:
        new = getcode('UPDATE_smartmeter.py')
    except Exception as e:
        new = '0000'
    print('current:',current,'new:',new)
    
    with open('bad', 'rt') as badfile:
        bad = badfile.read()
    bad = int(bad)
    if os.stat('UPDATE_smartmeter.py')[6]==0:
        print('update did not download properly')
        os.remove('UPDATE_smartmeter.py')
    else:
        with open('config.json', 'rt') as f:
            data = json.load(f)
            data['hasUpdated'] = '1'
        with open('config.json', 'wt') as w:
            json.dump(data,w)
        if int(new) > int(current) and not new == bad:
            print('downloaded file is newer')
            
            os.rename('UPDATE_smartmeter.py','smartmeter.py')
            
        elif int(new) == int(current):
            print('downloaded file is same version')
            os.remove('UPDATE_smartmeter.py')
        machine.reset()

def getcode(filename,offset=2):
    with open(filename, 'r') as file:
        first_line = file.readline().strip()  # Read the first line and remove trailing spaces
    code = first_line.split(' ')[offset]
    return code

def rollback():
    bad = getcode('smartmeter.py')
    
    with open('bad', 'wt') as badfile:
        badfile.write(bad)
    
    with open('/backup/smartmeter.py', 'rt') as file:
        buffer = file.read()
        with open('smartmeter.py', 'wt') as backup:
            backup.write(buffer)
    machine.reset()

def main():
    try:
        import smartmeter
    except NewUpdateTime:
        update()
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt detected. Exiting gracefully.")
    except Exception as e:
        print('error detected rolling back: ',e)
        rollback()
    
if __name__ == '__main__':
    main()