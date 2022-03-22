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
GOOGLE_MAPS_KEY = "AIzaSyAJiy_cEFCxdnBHlWCvnnlVBj6zcTfZfSk"

def get_darksky_features(longitude, latitude, date):
    unix_date = mktime(date.timetuple())
    URL = "https://api.darksky.net/forecast/" + DARKSKY_KEY + "/" + str(latitude) + "," + str(longitude) + "," + str(int(unix_date)) +"?exclude=daily,alerts,flags&units=ca"
    r = requests.get(URL)
    json_str = r.content.decode("utf8").replace("'", '"')
    json_object = json.loads(json_str)
    return json_object

def parse_json(json_resp):
    if json_resp['status'] == 'OK':
        all_journeys = []
        num_journeys = 0

        for i in range(len(json_resp['routes'])):
            route = json_resp['routes'][i]['legs'][0]
            if 'arrival_time' in route:
                num_journeys += 1
                walk_time = 0
                for step in route['steps']:
                    if step['travel_mode'] == 'WALKING':
                        walk_time += step['duration']['value']
                walk_time = round(walk_time / 60)

                ts_arr = int(route['arrival_time']['value'])
                arrival_time = datetime.datetime.utcfromtimestamp(ts_arr).strftime('%H:%M')
                ts_dep = int(route['departure_time']['value'])
                departure_time = datetime.datetime.utcfromtimestamp(ts_dep).strftime('%H:%M')
                # distance = route['distance']['text']
                duration = route['duration']['text']
                # start_address = route['start_address'].split(',')[0]
                # end_address = route['end_address'].split(',')[0]
                # end_location = route['end_location']
                icons = get_transport_icons(route)
                results = [departure_time, arrival_time, duration, walk_time, icons, len(icons)-1]
                all_journeys.append(results)
        all_journeys.append(num_journeys)

    else:
        all_journeys = ['No routes found']

    return all_journeys

def get_google_route(form_data):
    ORIG = form_data['from']
    DEST = form_data['to']
    form_date = form_data['date'].split('-')
    form_time = form_data['time'].split(':')
    date = datetime.datetime(int(form_date[0]), int(form_date[1]), int(form_date[2]), int(form_time[0]), int(form_time[1]))
    TIME = str(int(mktime(date.timetuple())))
    print(TIME)

    if form_data['journey_type'] == 'Departure':
        url = "https://maps.googleapis.com/maps/api/directions/json?origin=" + ORIG + "&destination=" + DEST + "&mode=transit&departure_time=" + TIME + "&key=" + GOOGLE_MAPS_KEY + "&alternatives=true"
    else:
        url = "https://maps.googleapis.com/maps/api/directions/json?origin=" + ORIG + "&destination=" + DEST + "&mode=transit&arrival_time=" + TIME + "&key=" + GOOGLE_MAPS_KEY + "&alternatives=true"
    payload={}
    headers = {}
    response = requests.request("GET", url, headers=headers, data=payload)
    json_resp = json.loads(response.text)
    results = parse_json(json_resp)

    return results

def get_transport_icons(route):
    transit_modes = []
    icons = []

    for step in route['steps']:
        if step['travel_mode'] == 'TRANSIT':
            transit_modes.append(step['transit_details']['line']['vehicle']['name'])
        else:
            if step['duration']['value'] > 60:
                transit_modes.append(step['travel_mode'])

    for mode in transit_modes:
        if mode == 'WALKING':
            icons.append('ph-person-simple-walk')
        elif mode == 'Bus':
            icons.append('ph-bus')
        elif mode == 'Train':
            icons.append('ph-train-regional')
        elif mode == 'Metro':
            icons.append('ph-train-simple')
        elif mode == 'Tram':
            icons.append('ph-train')
        else:
            icons.append('ph-question')

    return icons

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
    # print(g.city)
    # print(weather)
    icon = determine_weather_icon(weather['currently']['icon'])
    data = [weather, g.city, icon]
    return render_template('homepage.html', weather=data)

@app.route('/possiblejourneys', methods=['POST', 'GET'])
def possiblejourneys():
    if request.method == 'POST':
        result = request.form
        # print(result)
        route = get_google_route(result)
    else:
        result = []
    return render_template('possible_journeys.html', result=result, route=route)

@app.route('/journeydetails')
def journeydetails():
    journey_details = request.args.get('journey_details', None)
    g = geocoder.ip('me')
    weather = get_darksky_features(g.latlng[1], g.latlng[0], datetime.datetime.today())
    icon = determine_weather_icon(weather['currently']['icon'])
    data = [weather, g.city, icon]
    return render_template('journey_details.html', weather=data)

if __name__ == '__main__':
   app.run(debug = True)
