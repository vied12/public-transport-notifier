# coding: utf8
import datetime
import time
import requests
import traceback
import re
from RPLCD import CharLCD
import RPi.GPIO as GPIO

OPEN_WEATHER_API_KEY = 'API KEY'
DEPARTURES_REFRESH_DELAY = 2
METEO_REFRESH_DELAY = 15
BVG_STATION_URL = 'https://realtime-bvg.herokuapp.com/station/9076101?realtime=true'  # Hetzbergplatz realtime
# BVG_STATION_URL = 'https://bvg-api.herokuapp.com/station/9076101'  # Hetzbergplatz
# BVG_STATION_URL = 'https://bvg-api.herokuapp.com/station/9013101'  # Moritzplatz
METEO_URL = 'http://api.openweathermap.org/data/2.5/weather?q=berlin,de&APPID=%s' % (OPEN_WEATHER_API_KEY)

lcd = CharLCD(cols=16, rows=2, auto_linebreaks=False)
GPIO.setmode(GPIO.BOARD)
GPIO.setup(7, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(12, GPIO.IN, pull_up_down=GPIO.PUD_UP)


index = 0
departures = []
last_update = None
last_button_pressed = None
temperature = None
last_meteo_update = None


def parse_bus_date(departure):
    date = list(reversed(departure['date'].split('.'))) + list(departure['time'].split(':'))
    date = list(map(lambda _: int(re.sub('[^0-9]', '', _)), date))
    # add century
    date[0] = int('%s%s' % (20, date[0]))
    return datetime.datetime(*date)


def print_departure_info(departure):
    now = datetime.datetime.now()
    delta = parse_bus_date(departure) - now
    time = divmod(delta.days * 86400 + delta.seconds, 60)
    lcd.clear()
    message = '%s %s' % (departure['line'].replace('Bus ', ''), departure['direction'])
    lcd.write_string(message[:15])
    lcd.cursor_pos = (1, 0)
    lcd.write_string('%s min, %s s' % (time[0], time[1]))
    return '%s min, %s s' % (time[0], time[1])


def print_time():
    lcd.clear()
    lcd.cursor_pos = (0, 5)
    timeMessage = datetime.datetime.now().strftime('%X')[:-3]
    lcd.write_string(timeMessage[:15])
    lcd.cursor_pos = (1, 6)
    try:
        temperature = get_meteo()
    except Exception:
        traceback.print_exc()
    else:
        lcd.write_string('%d C' % temperature)


def get_meteo():
    global temperature, last_meteo_update
    if temperature is None or last_meteo_update is None or (datetime.datetime.now() - last_meteo_update).total_seconds() > 60 * METEO_REFRESH_DELAY:
        req = requests.get(METEO_URL)
        data = req.json()
        temperature = int(round(data['main']['temp'] - 273.15))
        last_meteo_update = datetime.datetime.now()
    return temperature


def next_callback(pin):
    global index, departures, last_button_pressed
    if index < len(departures) - 1:
        index += 1
    last_button_pressed = datetime.datetime.now()


def previous_callback(pin):
    global index, last_button_pressed
    if index > 0:
        index -= 1
    last_button_pressed = datetime.datetime.now()


def update_departures():
    global departures, last_update, index
    if departures:
        selected_departure = departures[index]
        # keep only future bus
        departures = [d for d in departures if datetime.datetime.now() < parse_bus_date(d)]
        try:
            index = departures.index(selected_departure)
        except ValueError:
            index = 0
    if departures and last_update:
        time_delta = datetime.datetime.now() - last_update
        if time_delta.total_seconds() < 60 * DEPARTURES_REFRESH_DELAY:
            return
    req = requests.get(BVG_STATION_URL)
    data = req.json()
    departures = data[0]['departures']
    last_update = datetime.datetime.now()


if __name__ == '__main__':
    GPIO.add_event_detect(7, GPIO.FALLING)
    GPIO.add_event_detect(12, GPIO.FALLING)
    GPIO.add_event_callback(7, next_callback, bouncetime=250)
    GPIO.add_event_callback(12, previous_callback, bouncetime=250)
    while True:
        button_pressed = last_button_pressed \
            and (datetime.datetime.now() - last_button_pressed).total_seconds() < 10 \
            or False
        if button_pressed or datetime.datetime.now().second % 10 <= 5:
            try:
                update_departures()
            except Exception as e:
                lcd.clear()
                lcd.write_string('oups')
                lcd.cursor_pos = (1, 0)
                lcd.write_string(('%s' % (e))[:15])
                traceback.print_exc()
            else:
                if departures:
                    print_departure_info(departures[index])
        else:
            print_time()
        time.sleep(1)
