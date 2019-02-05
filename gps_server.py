import serial
import logging
from Queue import Queue
import threading
import math
import datetime

_log = logging.getLogger(__name__)

class GPS_Units():
    def __init__(self):
        self._meters = 1.0
        self._feet = 3.28084
        self._cm  = 1000

    @property
    def meters(self):
        return self._meters

    @property
    def feet(self):
        return self._feet

    @property
    def cm(self):
        return self._cm

UNITS = GPS_Units()

class GPS_Coordinate():
    def __init__(self, lat = 0.00, long = 0.00, alt=0.00, time= "00:00"):
        self.latitude = lat
        self.longitude = long
        self.altitude = alt
        self.time = "00:00"
        self.velocity = 0.0
        self.heading = 0
        self.__alt_mode = GPS_Units().meters
        self.date_time = None
 
    def __str__(self):
       return self.map_api()
       """ return ("latitude = %s, longitude = %s, altitude = %s, at %s" 
                 % (self.lattitude, self.longitude, self.altitude, self.time))
       """
    def map_api(self):
        return "{ lat : %s , lng : %s  }" % (self.latitude, self.longitude)

    def distance_from(self, coordinate):
        """ distance_from 
            Calculates the great circle distance to/from the provide point
        """ 
        
        distance = 0.0
        if isinstance(coordinate, GPS_Coordinate):
            delta_lat_radians = math.radians(self.latitude - coordinate.latitude)
            delta_lng_radians = math.radians(self.longitude - coordinate.longitude)
            a = math.pow(math.sin(delta_lat_radians/2.0), 2) + \
                math.cos(math.radians(self.latitude)) * math.cos(math.radians(coordinate.latitude)) * \
                math.pow(math.sin(delta_lng_radians /2.0), 2)
            c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            distance = 6371000 * c

        else:
            _log.warning("GPS_Coordinate::distance_from: A GPS_Coordinate was not passed to function") 
        return distance
    
    def time_since(self, coordinate):
        """ time_since
            Calculates the time since the the provided point
        """
        diff = 0
	if isinstance(coordinate, GPS_Coordinate):
            diff = coordinate.date_time - self.date_time
            print diff
            diff = abs(diff.days * 1440) + int(diff.seconds / 60)
        else:
            _log.warning("GPS_Coordinate::time_since: A GPS_Coordinate was note passed to function")
        return diff
                                                                  
class GPS_Path():
    def __init__(self, min_distance = 20, stop_time = 10):
        self.active = False
        self.path = []
        self.min_distance = min_distance
        self.stop_time = stop_time
 

    def __str__(self):
        ll_list = [ x.map_api() for x in self.path ]
        return ",".join(ll_list)

    def add_point(self, point):
        if isinstance(point, GPS_Coordinate):
            path_length = len(self.path)
            if path_length > 1 and self.active:
                """ The path has been started now capture a point
                    every min_distance meters
                """
                distance = point.distance_from(self.path[-1])
                time = point.time_since(self.path[-1])
                if distance >= self.min_distance:
                    self.path.append(point)
                elif time > self.stop_time:
                    self.active = false
            elif len(self.path) == 1:
                """ The starting point is set, however we haven't travelled anywhere yet
                """
                distance = point.distance_from(self.path[0])
                if distance > (5 * self.min_distance):
                    self.path.append(point)
                    self.active = True
                    _log.info("GPS_Path::ad_point: The path has started")
            else:
                self.path = [point]

        else:
            _log.warning("GPS_Path::add_point:  New point is not a GPS_Coordinate.  Point ignored")
 


class GPS_Server(threading.Thread):
    def __init__(self, dev, q):
        """ Init the class variables
        """
        threading.Thread.__init__(self)
        self.q = q
        try:
            self.port = serial.Serial(dev, timeout = 5) 
        except:
            _log.debug("Exception while opening port {}".format(dev))

    def run(self):
        while True:
            res = ""
            try:
                line = self.port.readline()
                _log.debug("GPS Data: {}".format(line))
		data = line.split(',')
            except:
                _log.warning("Got an exception")
                break

            if "RMC" in data[0]:
                res = self.__parse_rmc(data)
            elif "VTG" in data[0]:
                res = self.__parse_vtg(data)
            
            if res:
                _log.info("resr {}".format(res))
                self.q.put(res)

    def __parse_gga(self, data):
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

    def __parse_vtg(self, data):
        return {"Vel": data[5]}

    def __parse_rmc(self, fields):
        res = GPS_Coordinate()
        res.time = self.__parse_time(fields[1])
        res.lattitude = self.__coordinate(fields[3], fields[4]) 
        res.longitude= self.__coordinate(fields[5], fields[6]) 
        if len(fields[7]) > 0:
            res.velocity = _parse_float(fields[7])
        if len(fields[8]) > 0:
            res.heading = _parse_float(fields[8])
        res.date_time = datetime.datetime(int(fields[9][-2:]), int(fields[9][-4:-2]), int(fields[9][0:2]),int(fields[1][:-7]), int(fields[1][-7:-5]), int(fields[1][-5:-3]))
        return res

    def __parse_time(self, data):
        if len(data) >= 6:
            res = data[:2] + ":" + data[2:4] + ":" + data[4:6]
        else:
            _log.warning("Invalid time string %s ")
            res = "00:00:00"
        return res

    def __coordinate(self, data, direction):
        dot = data.find(".")
        if dot > 0:
            fraction = data[dot-2:]
            deg = data[: dot-2]
            coord = _parse_float(deg) + (_parse_float(fraction)/60.0)
            if direction.upper() == "W" or direction.upper() == "S":
                coord = -coord
        else:
            coord = "0.000"
        return coord

""" Helper functions
"""

def _parse_float(number_string):
        try:
            res= float(number_string)
        except ValueError:
            _log.debug("Exception parsing float %s ", number_string)
            res = number_string
        return res

def _Test_GPS_Server():
    import time
    
    fifo = Queue()
    server_thread =  GPS_Server("/dev/ttyACM0", fifo)
    server_thread.setDaemon(True)
    server_thread.start()
    time.sleep(3)
    while not fifo.empty():
        print(fifo.get())

    server_thread.join(1)
    #server_thread.stop()

def _Test_GPS_Coordinate():
    p1 = GPS_Coordinate(lat = 38.970878, long = -104.756631)
    p2 = GPS_Coordinate(lat = 38.971303, long = -104.756905)
    assert(p1.distance_from(10.0) == 0.0)
    print p1.distance_from(p2)
    print p2.distance_from(p1)
    print p2.distance_from(p2)

def _Test_GPS_Path():
    p1 = GPS_Coordinate(lat = 38.970878, long = -104.756631)
    datetimeFormat = '%Y-%m-%d %H:%M:%S.%f'
    date1 = '2016-04-16 10:01:28.585'
    date2 = '2016-03-10 09:56:28.067'
    p1.date_time = datetime.datetime.strptime(date1, datetimeFormat)
    p2 = GPS_Coordinate(lat = 38.971303, long = -104.756905)
    p2.date_time = datetime.datetime.strptime(date2, datetimeFormat)
    print "Time p1_time_since(p2) = %s " % (p1.time_since(p2))
    a_path = GPS_Path(min_distance = 50)
    a_path.add_point(p1)
    a_path.add_point(p2)
    pl = [(38.971939, -104.755325), (38.972497, -104.754672), (38.972731, -104.754844), (38.973857, -104.757376)]
    for pt in pl:
        p1 = GPS_Coordinate(lat = pt[0], long = pt[1])
        a_path.add_point(p1)
    print a_path

if __name__ == "__main__":
    logging.basicConfig(level = logging.DEBUG)
    _Test_GPS_Server()
    _Test_GPS_Coordinate()
    _Test_GPS_Path()


