from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from time import sleep
from dotenv import load_dotenv
from urllib.parse import urlparse
import serial
import requests
import google.generativeai as genai
import os

load_dotenv()

app = Flask(__name__)
database_url = os.getenv('DATABASE_URL')
app.secret_key = os.getenv('APP_SECRET_KEY', 'default_key')
weather_api_key = os.getenv('WEATHER_KEY', 'default_key')
genai.configure(api_key=os.getenv('GENAI_KEY'))


lat_long = {
    'nairobi': [-1.292066, 36.821945],
    'kiambu': [-1.167240, 36.825500],
    'kisumu': [-0.091702, 34.767956],
    'mombasa': [-4.043477, 39.668206],
    'nakuru': [-0.303099, 36.080026],
    'kiambu': [-1.167240, 36.825500],
    'eldoret': [0.520000, 35.269440],
    'kakamega': [0.284722, 34.752222],
    'kisii': [-0.681400, 34.773200],
    'nyeri': [-0.417000, 36.951000],
    'meru': [0.056100, 37.647400],
    'nyahururu': [0.036600, 36.354100],
    'kericho': [-0.366667, 35.283333],
    'machakos': [-1.522222, 37.263889],
    'nanyuki': [0.016667, 37.072222],
    'embu': [-0.538889, 37.459722],
    'isiolo': [0.350000, 37.583333],
    'narok': [-1.083333, 35.866667],
    'kitale': [1.016667, 35.000000],
    'maralal': [1.100000, 36.700000],
}

parsed_url = urlparse(database_url)
db_user = parsed_url.username
db_password = parsed_url.password
db_host = parsed_url.hostname
db_name = parsed_url.path[1:] 

# Database connection
db = mysql.connector.connect(
    host=db_host,
    user=db_user,
    password=db_password,
    database=db_name
)


@app.route('/')
def home():
    if 'loggedin' in session:
        return render_template('dashboard.html', username=session['username'])
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = (request.form['firstName'] + request.form['lastName']).lower()
        email = request.form['email']
        password = request.form['password']  # Hashing should be done here
        password2 = request.form['password2']
        location = request.form['location']

        if password != password2:
            flash('Passwords do not match, please try again.')
            return redirect(url_for('register'))

        cursor = db.cursor(buffered=True)
        cursor.execute('INSERT INTO users (Username, Email, PasswordHash) VALUES (%s, %s, %s)', (username, email, password))
        db.commit()
        cursor.close()

        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    db.rollback() 
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        cursor = db.cursor(buffered=True)
        cursor.execute('SELECT * FROM users WHERE Username = %s', (username,))
        user = cursor.fetchone()
        cursor.close()

        if user:
            cursor2 = db.cursor(buffered=True)
            cursor2.execute('SELECT Name FROM farms WHERE UserID = %s', (user[0],))
            farm = cursor2.fetchone()
            session['loggedin'] = True
            session['username'] = user[1]
            session['userID'] = user[0]
            session['farm'] = farm[0][1] if farm else None
            cursor2.close()
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password, please try again.')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('username', None)
    session.pop('userID', None)
    session.pop('farm', None)
    session.clear()
    return redirect(url_for('home'))



@app.route('/reading-data/')
def moisture_data():
    try:
        ser = serial.Serial('COM8', 9600, timeout=1)
        sleep(1) 
    except serial.SerialException:
        ser = None

    while True:
        if ser and ser.in_waiting:
            soil_moisture = ser.readline().decode('utf-8').strip()
        else:
            soil_moisture = None

        return soil_moisture







# - - - - - - - - - Pages Content - - - - - - - - - - #


@app.route('/dashboard-content')
def dashboard_content():
    farms = get_farms(session['userID'])
    crop = fetch_crop(session['userID'])
    return render_template('dbc.html', username=session['username'], farms=farms)

@app.route('/soil-moisture-content')
def soil_moisture_content():
    # Fetch soil moisture data here
    sm = moisture_data()
    if sm:
        soil_moisture = round(100 - (int(sm)/1023) * 100, 2)
    else:
        soil_moisture = None
    return render_template('soil_moisture_content.html', soil_moisture=soil_moisture)

@app.route('/weather-forecast-content/', methods=['GET', 'POST'])
def weather_forecast_content():
    data = None
    if request.method == 'POST':
        city = request.form['city'].lower()
        url = "https://api.openweathermap.org/data/2.5/weather?lat={}&lon={}&appid={}&units=metric".format(lat_long[city][0], lat_long[city][1], weather_api_key)
        response = requests.get(url)
        data = response.json()
        session['city'] = city
        session['temp'] = data['main']['temp']
        session['humidity'] = data['main']['humidity']
        session['city'] = city
        return render_template('weather_forecast_content.html', data=data)
    return render_template('weather_forecast_content.html', data=data)


@app.route('/ai-recommendation-content')
def ai_recommendation_content():
    # Fetch AI recommendations here
    # Using openAI API
    model = genai.GenerativeModel('gemini-pro')
    if session['city']:
        prompt = f"What crop should I plant in {session['city']}8 with  an average temperature of {session['temp']}? Also how much water should I use on the crops? Answer in no more than 50 words and in prose form."
    else:
        prompt = f"Give me random information on how to improve the irrigation practices in my farm. Answer in no more than 50 words"
    
    response = model.generate_content(prompt)

    return render_template('ai_recommendation_content.html', response=response)

@app.route('/settings-content')
def settings_content():
    # Load settings data here
    db.rollback() 
    sql = 'SELECT * FROM farms WHERE UserID = %s'
    cursor = db.cursor(dictionary=True, buffered=True)
    cursor.execute(sql, (session['userID'],))
    farms = cursor.fetchall()

    if farms:
        cursor.close()
        return render_template('settings_content.html', farms=farms)
    cursor.close()

    return render_template('settings_content.html')



@app.route('/delete-farm/<farmID>', methods=['POST', 'GET'])
def delete_farm(farmID):
    if request.method == 'POST':
        return delete_farm(farmID)
    cursor = db.cursor(buffered=True)
    cursor.execute('DELETE FROM farms WHERE FarmID = %s', (farmID,))
    db.commit()
    cursor.close()
    return redirect(url_for('home'))


@app.route('/add-farm', methods=['POST'])
def add_farm():
    farm_name = request.form['farmName']
    farm_location = request.form['location']
    farm_acre = request.form['acres']
    try:
        cursor = db.cursor(buffered=True)
        cursor.execute('INSERT INTO farms (UserID, Name, Location, Acreage) VALUES (%s, %s, %s, %s)', (session['userID'], farm_name, farm_location, farm_acre))
        db.commit()
        cursor.close()
        return redirect(url_for('home'))
    except:
        flash('An error occurred while adding the farm. Please try again.')
        return redirect(url_for('home'))

    
def get_farms(userID):
    db.rollback() 
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute('SELECT * FROM farms WHERE UserID = %s', (userID,))
        farms = cursor.fetchall()
        cursor.close()
        return farms
    except:
        return None



@app.route('/add-crops', methods=['POST'])
def add_crops():
    farm_ID = request.form['farms']
    crop_name = request.form['crop']
    crop_plant_date = request.form['plantDate']
    crop_harvest_date = request.form['harvestDate'] if request.form['harvestDate'] else None

    cursor = db.cursor(buffered=True)
    cursor.execute('INSERT INTO crops (FarmID, CropType, PlantingDate, HarvestDate) VALUES (%s, %s, %s, %s)', (farm_ID, crop_name, crop_plant_date, crop_harvest_date))
    db.commit()
    cursor.close()
    return redirect(url_for('home'))


# sql functions
def get_soil_moisture():
    db.rollback() 
    cursor = db.cursor(buffered=True)
    cursor.execute('SELECT * FROM SoilMoisture WHERE FarmID = %s', (session['farm'],))
    data = cursor.fetchall()
    cursor.close()
    return data

def fetch_farms(userID):
    cursor = db.cursor(dictionary=True, buffered=True)
    cursor.execute('SELECT * FROM farms WHERE UserID = %s', (userID,))
    farms = cursor.fetchall()
    cursor.close()
    return farms

# fetching crop data of farms with particular userID
def fetch_crop(userID):
    db.rollback()
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute('SELECT * FROM farms WHERE UserID = %s', (userID,))
        farms = cursor.fetchone()
        cursor.close()
        farmID = farms['FarmID']
        cursor1 = db.cursor(dictionary=True)
        cursor1.execute('SELECT * FROM crops WHERE FarmID = %s', (farmID,))
        crops = cursor1.fetchone()
        cursor1.close()
        return crops['CropType']
    except:
        return None
    




if __name__ == '__main__':
    app.run()
