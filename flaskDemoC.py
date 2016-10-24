# -*- coding:utf-8 -*-
__author__ = 'Admin'
from flask_script import Manager
from flask import Flask
import sqlite3
import string, math, threading, time
from coordconv3d import aer2geodetic
import numpy as np

app = Flask(__name__)
manager = Manager(app)


def draw_circle(center, rng):
    retstr = ""
    steps=60
    elevation = np.zeros(steps)
    azimuth = np.arange(0, 360, 360/steps)
    r = np.zeros(steps)
    r[:] = rng
    #so we're going to do this by computing a bearing angle based on the steps, and then compute the coordinate of a line extended from the center point to that range.
    [center_lat, center_lon] = center
    lat_rad, lon_rad, alt = aer2geodetic(azimuth, elevation, r*1000, center_lat, center_lon, 150)
    #esquared = (1/298.257223563)*(2-(1/298.257223563))
    #earth_radius_mi = 3963.19059

    #here we figure out the circumference of the latitude ring
    #which tells us how wide one line of longitude is at our latitude
    #lat_circ = earth_radius_mi * math.cos(center_lat)
    #the circumference of the longitude ring will be equal to the circumference of the earth
    '''
   # lat_rad = math.radians(center_lat)
   # lon_rad = math.radians(center_lon)

    #tmp0 = rng / earth_radius_mi

   # for i in range(0, steps+1):
     #   bearing = i*(2*math.pi/steps) #in radians
     #   lat_out = math.degrees(math.asin(math.sin(lat_rad)*math.cos(tmp0) + math.cos(lat_rad)*math.sin(tmp0)*math.cos(bearing)))
     #   lon_out = center_lon + math.degrees(math.atan2(math.sin(bearing)*math.sin(tmp0)*math.cos(lat_rad), math.cos(tmp0)-math.sin(lat_rad)*math.sin(math.radians(lat_out))))
     #   retstr += " %.8f,%.8f, 0" % (lon_out, lat_out,)
    '''
    for i in xrange(0, steps):
        retstr += " %.6f,%.6f,0" % (lon_rad[i], lat_rad[i])
    #retstr = string.lstrip(retstr)
    return retstr

@app.route('/')
def index():
    dbname = '/home/pi/adsb.db'
    locations = [34.23432, 112.68690]
    #first let's draw the static content
    retstr="""<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2" xmlns:kml="http://www.opengis.net/kml/2.2" xmlns:atom="http://www.w3.org/2005/Atom">\n<Document>\n\t<Style id="airplane">\n\t\t<IconStyle>\n\t\t\t<Icon><href>http://maps.google.com/mapfiles/kml/pal2/icon56.png</href></Icon>\n\t\t</IconStyle>\n\t</Style>\n\t<Style id="rangering">\n\t<LineStyle>\n\t\t<color>7d00ff00</color>\n\t\t<width>10</width>\n\t</LineStyle>\n\t</Style>\n\t<Style id="track">\n\t<LineStyle>\n\t\t<color>df007fff</color>\n\t\t<width>4</width>\n\t</LineStyle>\n\t<PolyStyle><color>6dff0000</color></PolyStyle>\n\t\t\t</Style>"""

    if locations is not None:
        retstr += """\n\t<Folder>\n\t\t<name>Range rings</name>\n\t\t<open>0</open>"""
        for rng in [50, 100, 150]:
            retstr += """\n\t\t<Placemark>\n\t\t\t<name>%inm</name>\n\t\t\t<styleUrl>#rangering</styleUrl>\n\t\t\t<LineString>\n\t\t\t\t<tessellate>0</tessellate>\n\t\t\t\t<altitudeMode>relativeToGround</altitudeMode>\n\t\t\t\t<coordinates>%s</coordinates>\n\t\t\t</LineString>\n\t\t</Placemark>""" % (rng, draw_circle(locations, rng),)
        retstr += """\t</Folder>\n"""

    retstr +=  """\t<Folder>\n\t\t<name>Aircraft locations</name>\n\t\t<open>0</open>"""
    _db = sqlite3.connect(dbname) #read from the db
     #read the database and add KML
    q = "select distinct icao from positions where seen > datetime('now', '-5 minute')"
    c = _db.cursor()
    c.execute(q)
    icaolist = c.fetchall()
    #now we have a list icaolist of all ICAOs seen in the last 5 minutes
    for icao in icaolist:
        #print "ICAO: %x" % icao
        q = "select * from positions where icao=%i and seen > datetime('now', '-2 hour') ORDER BY seen DESC" % icao
        c.execute(q)
        track = c.fetchall()
        #print "Track length: %i" % len(track)
        if len(track) != 0:
            lat = track[0][3]
            if lat is None: lat = 0
            lon = track[0][4]
            if lon is None: lon = 0
            alt = track[0][2]
            if alt is None: alt = 0

            metric_alt = alt * 0.3048 #google earth takes meters, the commie bastards

            trackstr = ""

            for pos in track:
                trackstr += " %f,%f,%f" % (pos[4], pos[3], pos[2]*0.3048)

            trackstr = string.lstrip(trackstr)
        else:
            alt = 0
            metric_alt = 0
            lat = 0
            lon = 0
            trackstr = str("")

        #now get metadata
        q = "select ident from ident where icao=%i" % icao
        c.execute(q)
        r = c.fetchall()
        if len(r) != 0:
            ident = r[0][0]
        else: ident=""
        #if ident is None: ident = ""
        #get most recent speed/heading/vertical
        q = "select seen, speed, heading, vertical from vectors where icao=%i order by seen desc limit 1" % icao
        c.execute(q)
        r = c.fetchall()
        if len(r) != 0:
            seen = r[0][0]
            speed = r[0][1]
            heading = r[0][2]
            vertical = r[0][3]

        else:
            seen = 0
            speed = 0
            heading = 0
            vertical = 0
        #now generate some KML
        retstr+= "\n\t\t<Placemark>\n\t\t\t<name>%s</name>\n\t\t\t<Style><IconStyle><heading>%i</heading></IconStyle></Style>\n\t\t\t<description>\n\t\t\t\t<![CDATA[Altitude: %s<br/>Heading: %i<br/>Speed: %i<br/>Vertical speed: %i<br/>ICAO: %x<br/>Last seen: %s]]>\n\t\t\t</description>\n\t\t\t<Model>\n\t\t\t\t<altitudeMode>absolute</altitudeMode>\n\t\t\t\t<extrude>1</extrude>\n\t\t\t\t<Location>\n\t\t\t\t<longitude>%s</longitude>\n\t\t\t\t<latitude>%s</latitude>\n\t\t\t\t<altitude>%i</altitude>\n\t\t\t</Location>\n\t\t\t<Orientation>\n\t\t\t\t<heading>%i</heading>\n\t\t\t\t<tilt>0</tilt>\n\t\t\t\t<roll>0</roll>\n\t\t\t\t</Orientation>\n\t\t\t\t<Scale>\n\t\t\t\t\t<x>1</x>\n\t\t\t\t\t<y>1</y>\n\t\t\t\t\t<z>1</z>\n\t\t\t\t</Scale>\n\t\t\t\t<Link>\n\t\t\t\t\t<href>E:/flight232.dae</href>\n\t\t\t\t</Link>\n\t\t\t</Model>\n\t\t\t</Placemark>" % (ident, heading, alt, heading, speed, vertical, icao[0], seen, lon, lat, metric_alt, heading, )

        retstr+= "\n\t\t<Placemark>\n\t\t\t<styleUrl>#track</styleUrl>\n\t\t\t<LineString>\n\t\t\t\t<extrude>1</extrude>\n\t\t\t\t<altitudeMode>absolute</altitudeMode>\n\t\t\t\t<coordinates>%s</coordinates>\n\t\t\t</LineString>\n\t\t</Placemark>" % (trackstr,)

    retstr+= '\n\t</Folder>\n</Document>\n</kml>'
    return retstr
    _db.close()




if __name__=='__main__':
    manager.run()



