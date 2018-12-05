import serial
import logging
from Queue import Queue
import threading


class GPSServer(threading.Thread):
    def __init__(self, dev, q):
        """ Init the class variables
        """
        threading.Thread.__init__(self)
        self.q = q
        self.log = logging.getLogger(__name__)
        try:
            self.port = serial.Serial(dev, timeout = 5) 
        except:
            self.log.debug("Exception while opening port {}".format(dev))

    def run(self):
        while True:
            res = ""
            try:
                line = self.port.readline()
                self.log.debug("GPS Data: {}".format(line))
		data = line.split(',')
            except:
                self.log.warning("Got an exception")
                break

            if "RMC" in data[0]:
                res = self._parse_rmc(data)
            elif "VTG" in data[0]:
                res = self._parse_vtg(data)
            
            if res:
                self.log.info("resr {}".format(res))
                self.q.put(res)
        

    def _parse_gga(self, data):
        """Parses the GPS GGA message with the following format
          Type  Time       Lat          Long          
        $GPGGA,191117.00,3858.16005,N,10445.70181,W,2,05,2.34,2105.9,M,-22.1,M,,0000*5F
        """
        if not len(data) == 14:
            return
        time = data[1][:-7]+":"+data[1][-7:-5]+":"+data[1][-5:]
        lat = data[2][:2]+" "+ data[2][2:]+" " + data[3]
        long = data[4][:3]+" "+data[4][3:]+" " + data[5]
        if int(data[6]) > 0 and int(data[6])<6:
            status = True
        else:
            status = False
        alt = float(data[9])
        return {"Time" : time, "Lat" : lat, "Long": long, "Status" : status, "Alt" : alt}

    def _parse_vtg(self, data):
        return {"Vel": data[5]}

    def _parse_rmc(self, fields):
        res = {}
        res["time"] = self._parse_time(fields[1])
        res["Lat"] = self._coordinate(fields[3]) + " " + fields[4]
        res["Long"]= self._coordinate(fields[5]) + " " + fields[6]
        if len(fields[7]) > 0:
            res["Vel"] = self._parse_float(fields[7])
        if len(fields[8]) > 0:
            res["Hdg"] = self._parse_float(fields[8])
        return res

    def _parse_float(self, number_string):
        try:
            res= float(number_string)
        except ValueError:
            self.log.debug("Exception parsing float %s ", number_string)
            res = number_string
        return res

    def _parse_time(self, data):
        if len(data) >= 6:
            res = data[:2] + ":" + data[2:4] + ":" + data[4:6]
        else:
            self.log.warning("Invalid time string %s ")
            res = "00:00:00"
        return res

    def _coordinate(self, data):
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
    #logging.basicConfig(level = logging.DEBUG)
    fifo = Queue()
    server_thread =  GPSServer("/dev/ttyACM0", fifo)
    server_thread.setDaemon(True)
    server_thread.start()
    time.sleep(5)
    while not fifo.empty():
        print(fifo.get())

    server_thread.join(1)


