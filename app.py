import requests
import json
import datetime
from time import mktime
import calendar
import numpy as np
import pandas as pd
import geocoder

from flask import Flask, redirect, url_for, request, render_template
app = Flask(__name__)

DARKSKY_KEY = "d07fa9b030dfc7ae1a1897828f0e01de"

def get_darksky_features(longitude, latitude, date):
    unix_date = mktime(date.timetuple())
    URL = "https://api.darksky.net/forecast/" + DARKSKY_KEY + "/" + str(latitude) + "," + str(longitude) + "," + str(int(unix_date)) +"?exclude=minutely,hourly,daily,alerts,flags&units=ca"
    r = requests.get(URL)
    json_str = r.content.decode("utf8").replace("'", '"')
    json_object = json.loads(json_str)
    return json_object

def determine_weather_icon(icon):
    if icon == 'clear-day':
        return "ph-sun"
    elif icon == "clear-night":
        return "ph-moon"
    elif icon == "rain":
        return "ph-cloud-rain"
    elif icon == "snow" or icon == "sleet":
        return "ph-cloud-snow"
    elif icon == "wind":
        return  "ph-wind"
    elif icon == "fog":
        return "ph-cloud-fog"
    elif icon == "cloudy":
        return "ph-cloud"
    elif icon == "partly-cloudy-day":
        return "ph-cloud-sun"
    elif icon == "partly-cloudy-night":
        return "ph-cloud-moon"
    else:
        return "ph-question"

@app.route('/')
def index():
    g = geocoder.ip('me')
    weather = get_darksky_features(g.latlng[1], g.latlng[0], datetime.datetime.today())
    print(g.city)
    print(weather)
    icon = determine_weather_icon(weather['currently']['icon'])
    data = [weather, g.city, icon]
    return render_template('homepage.html', weather=data)

@app.route('/possiblejourneys', methods=['POST', 'GET'])
def possiblejourneys():
    if request.method == 'POST':
        result = request.form
        print(result)
    else:
        result = []
    return render_template('possible_journeys.html', result=result)

@app.route('/journeydetails')
def journeydetails():
    return render_template('journey_details.html')

if __name__ == '__main__':
   app.run(debug = True)
