import serial
import logging
from Queue import Queue

log = logging.getLogger(__name__)

def gps_server(dev, q):
    with serial.Serial(dev, timeout=5) as port:
        while True:
            res = False
            try:
                line = port.readline()
            except:
                log.warning("Got an exception")
                break
            if "RMC" in line:
                res = parse_rmc(line)
            elif "VTG" in line:
                res = parse_vtg(line)
            if res:
                q.put(res)
        

def parse_gga(line):
    data = line.split(',')
    time = data[1][:-7]+":"+data[1][-7:-5]+":"+data[1][-5:]
    lat = data[2][:2]+" "+ data[2][2:]+" " + data[3]
    long = data[4][:3]+" "+data[4][3:]+" " + data[5]
    if int(data[6]) > 0 and int(data[6])<6:
        status = True
    else:
        status = False
    alt = float(data[9])
    return {"Time" : time, "Lat" : lat, "Long": long, "Status" : status, "Alt" : alt}

def parse_vtg(line):
    data = line.split(',')
    #log.debug("Line is %s", line)
    return {"Vel": data[5]}

def parse_rmc(line):
    res = {}
    fields = line.split(',')
    res["time"] = parse_time(fields[1])
    res["Lat"] = coordinate(fields[3]) + " " + fields[4]
    res["Long"]= coordinate(fields[5]) + " " + fields[6]
    res["Vel"] = parse_float(fields[7])
    res["Hdg"] = parse_float(fields[8])
    return res

def parse_float(number_string):
    try:
        res= float(number_string)
    except:
        log.debug("Exception parsing float %s ", number_string)
        res = number_string
    return res

def parse_time(data):
    if len(data) >= 6:
        res = data[:2] + ":" + data[2:4] + ":" + data[4:6]
    else:
        log.warning("Invalid time string %s ")
        res = "00:00:00"
    return res

def coordinate(data):
    dot = data.find(".")
    if dot > 0:
        fraction = data[dot-2:]
        deg = data[: dot-2]
        coord = deg + " " + fraction
    else:
        coord = "0 00.000"
    return coord


if __name__ == "__main__":
    import threading
    import time
    logging.basicConfig(level = logging.DEBUG)
    fifo = Queue()
    server_thread = threading.Thread(target = gps_server, 
                                     args = ("/dev/ttyACM0", fifo,))
    server_thread.setDaemon(True)
    server_thread.start()
    time.sleep(2)
    while not fifo.empty():
        log.debug("We got %s", fifo.get())

    server_thread.join(10)


