import ujson as json

jsonData = {"deviceId": "1001","password":"123"}

try:
    with open('config.json', 'w') as f:
        json.dump(jsonData, f)
except:
    print("Could not save the state variable.")
