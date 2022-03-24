import requests
import json
import datetime
from time import mktime
import calendar
import numpy as np
import pandas as pd
import geocoder
import os
import gather_keys_oauth2 as Oauth2
import fitbit

from flask import Flask, redirect, url_for, request, render_template, session
app = Flask(__name__)
app.secret_key = '1648030020'

DARKSKY_KEY = "d07fa9b030dfc7ae1a1897828f0e01de"
GOOGLE_MAPS_KEY = "AIzaSyAJiy_cEFCxdnBHlWCvnnlVBj6zcTfZfSk"
CLIENT_ID='2388K5'
CLIENT_SECRET='b49da8eef0b5aa709bfafef69d68ae9c'

def get_goal(auth2_client):
    auth2_client.activities_daily_goal(active_minutes=30)
    fitbit_goal = auth2_client.activities_daily_goal()['goals']['activeMinutes']
    return fitbit_goal

def go_walk(last_departure_stop, last_departure_time, last_arrival_stop, last_arrival_time, final_destination, final_arrival_time, walking_time, last_walking_time):

    # read to use the csv of line 40
    df = pd.read_csv('lijn40_ordered.csv')

    # the orderlocation of the busstop where the last leg starts
    A = df[df['haltenaam'].str.contains(last_departure_stop)].index.values[0]

    # the order location of the arrival stop
    B = df[df['haltenaam'].str.contains(last_arrival_stop)].index.values[0]

    # get all stops in between the start and arrival of the last leg and order them correctly
    if A < B:
        stoplist = df[A:B+1]['haltenaam']
    if B < A:
        stoplist = df[B:A+1]['haltenaam'][::-1]

    # get the walking time and distance from each stop to the final destination
    results = []
    for stop in stoplist[:-1]:
        url = "https://maps.googleapis.com/maps/api/directions/json?origin={origin}&destination={destination}&mode=walking&key=".format(origin=stop, destination=final_destination) + GOOGLE_MAPS_KEY
        payload={}
        headers = {}
        response = requests.request("GET", url, headers=headers, data=payload)
        response = json.loads(response.text)

        # get duration and distance
        duration = response['routes'][0]['legs'][0]['duration']['text']
        distance = response['routes'][0]['legs'][0]['distance']['text']

        # get start address (for control if it picked the right lcoation)
        start_address = response['routes'][0]['legs'][0]['start_address'].split(',')[0]

        duration_int = int(duration.split(' ')[0])
        duration = duration_int - last_walking_time
        final_walk_time = duration_int + walking_time - last_walking_time

        # order results that are returened
        results.append([start_address, duration, distance, final_walk_time])

    return results


def get_darksky_features(longitude, latitude, date):
    unix_date = mktime(date.timetuple())
    URL = "https://api.darksky.net/forecast/" + DARKSKY_KEY + "/" + str(latitude) + "," + str(longitude) + "," + str(int(unix_date)) +"?exclude=daily,alerts,flags&units=ca"
    r = requests.get(URL)
    json_str = r.content.decode("utf8").replace("'", '"')
    json_object = json.loads(json_str)
    return json_object

def get_journey_details(route):
    journey_details = []

    for i in range(len(route['steps'])):
        step = route['steps'][i]

        if step['travel_mode'] == 'WALKING':
            if step['duration']['value'] > 60:
                step_duration = step['duration']['text']
                step_distance = step['distance']['text']

                if i == 0:
                    step_start = route['start_address'].split(',')[0]
                    step_end = route['steps'][i+1]['transit_details']['departure_stop']['name']
                elif i == len(route['steps']) - 1:
                    step_start = route['steps'][i-1]['transit_details']['arrival_stop']['name']
                    step_end = route['end_address'].split(',')[0]
                else:
                    step_start = route['steps'][i-1]['transit_details']['arrival_stop']['name']
                    step_end = route['steps'][i+1]['transit_details']['departure_stop']['name']

                step_travel_mode = step['travel_mode']

                if i == len(route['steps']) - 1:
                    ts_dep = int(route['steps'][i-1]['transit_details']['arrival_time']['value'])
                    step_dep_time = datetime.datetime.utcfromtimestamp(ts_dep).strftime('%H:%M')
                    ts_arr = int(route['steps'][i-1]['transit_details']['arrival_time']['value']) + int(step['duration']['value'])
                    step_arr_time = datetime.datetime.utcfromtimestamp(ts_arr).strftime('%H:%M')
                else:
                    ts_dep = int(route['steps'][i+1]['transit_details']['departure_time']['value']) - int(step['duration']['value'])
                    step_dep_time = datetime.datetime.utcfromtimestamp(ts_dep).strftime('%H:%M')
                    ts_arr = int(route['steps'][i+1]['transit_details']['departure_time']['value'])
                    step_arr_time = datetime.datetime.utcfromtimestamp(ts_arr).strftime('%H:%M')

                step_details = [step_duration, step_distance, step_start, step_dep_time, step_end, step_arr_time, step_travel_mode]
                journey_details.append(step_details)

        if step['travel_mode'] == 'TRANSIT':
            step_duration = step['duration']['text']
            step_distance = step['distance']['text']
            step_dep_stop = step['transit_details']['departure_stop']['name']
            ts_dep = int(step['transit_details']['departure_time']['value'])
            step_dep_time = datetime.datetime.utcfromtimestamp(ts_dep).strftime('%H:%M')
            step_arr_stop = step['transit_details']['arrival_stop']['name']
            ts_arr = int(step['transit_details']['arrival_time']['value'])
            step_arr_time = datetime.datetime.utcfromtimestamp(ts_arr).strftime('%H:%M')
            step_travel_mode = step['travel_mode']
            step_headsign = step['transit_details']['headsign']
            step_shortname = step['transit_details']['line']['short_name']
            step_num_stops = step['transit_details']['num_stops']
            step_details = [step_duration, step_distance, step_dep_stop, step_dep_time, step_arr_stop, step_arr_time, step_headsign, step_shortname, step_num_stops, step_travel_mode]
            journey_details.append(step_details)

    journey_details.append(len(journey_details))

    return journey_details

def parse_json(json_resp, date):
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
                        if step['duration']['value'] > 60:
                            walk_time += step['duration']['value']

                walk_time = round(walk_time / 60)

                ts_arr = int(route['arrival_time']['value'])
                arrival_time = datetime.datetime.utcfromtimestamp(ts_arr).strftime('%H:%M')
                ts_dep = int(route['departure_time']['value'])
                departure_time = datetime.datetime.utcfromtimestamp(ts_dep).strftime('%H:%M')

                distance = route['distance']['text']
                duration = route['duration']['text']

                start_address = route['start_address'].split(',')[0]
                end_address = route['end_address'].split(',')[0]

                end_weather = get_darksky_features(route['end_location']['lng'], route['end_location']['lat'], date)
                weather_icon = determine_weather_icon(end_weather['hourly']['icon'])
                weather_result = [end_weather['hourly']['summary'],  end_weather['currently']['precipProbability'], end_weather['currently']['temperature'], weather_icon]

                icons = get_transport_icons(route)
                route_details = get_journey_details(route)

                results = [departure_time, arrival_time, duration, walk_time, icons, len(icons)-1, distance, start_address, end_address, weather_result, route_details]
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
    date = datetime.datetime(int(form_date[0]), int(form_date[1]), int(form_date[2]), int(form_time[0]) + 1, int(form_time[1]))
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
    results = parse_json(json_resp, date)

    return results

def get_transport_icons(route):
    transit_modes = []
    icons = []

    for step in route['steps']:
        if step['travel_mode'] == 'TRANSIT':
            mode = step['transit_details']['line']['vehicle']['name']
            if mode == 'Bus':
                icons.append('ph-bus')
            elif mode == 'Train':
                icons.append('ph-train-regional')
            elif mode == 'Metro':
                icons.append('ph-train-simple')
            elif mode == 'Tram':
                icons.append('ph-train')
            else:
                icons.append('ph-question')
        else:
            if step['duration']['value'] > 60:
                icons.append('ph-person-simple-walk')

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
    icon = determine_weather_icon(weather['currently']['icon'])
    data = [weather, g.city, icon]

    return render_template('homepage.html', weather=data)

@app.route('/possiblejourneys', methods=['POST', 'GET'])
def possiblejourneys():
    if request.method == 'POST':
        result = request.form
        route = get_google_route(result)
        session['route'] = route
        session['result'] = result
    else:
        if session.get('result') == None:
            result = []
            route = ['No routes found']
        else:
            route = session.get('route', None)
            result = session.get('result', None)

    return render_template('possible_journeys.html', result=result, route=route)

@app.route('/journeydetails')
def journeydetails():
    route = session.get('route', None)
    result = session.get('result', None)
    route_num = int(request.args.get('route_num', None))
    fitbit_goal = get_goal(auth2_client)

    weather = route[0][-2]

    last_departure_stop = route[route_num][-1][-3][2]
    last_departure_time = route[route_num][-1][-3][3]
    last_arrival_stop = route[route_num][-1][-3][4]
    last_arrival_time = route[route_num][-1][-3][5]
    final_destination = route[route_num][8]
    final_arrival_time = route[route_num][1]
    walking_time = route[route_num][3]
    last_walking_time = int(route[route_num][-1][-2][0].split(' ')[0])

    walking_options = go_walk(last_departure_stop, last_departure_time, last_arrival_stop, last_arrival_time, final_destination, final_arrival_time, walking_time, last_walking_time)

    print(result)
    print('\n')
    print(route[route_num])
    return render_template('journey_details.html', result=result, weather=weather, route=route, route_num=route_num, fitbit_goal=fitbit_goal, walking_options=walking_options)

if __name__ == '__main__':
    server=Oauth2.OAuth2Server(CLIENT_ID, CLIENT_SECRET)
    server.browser_authorize()
    ACCESS_TOKEN=str(server.fitbit.client.session.token['access_token'])
    REFRESH_TOKEN=str(server.fitbit.client.session.token['refresh_token'])
    auth2_client=fitbit.Fitbit(CLIENT_ID,CLIENT_SECRET,oauth2=True,access_token=ACCESS_TOKEN,refresh_token=REFRESH_TOKEN)
    app.run(debug = True)
