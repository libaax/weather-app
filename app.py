from flask import Flask, render_template, request
import requests

app = Flask(__name__)

# Open-Meteo API endpoints (free, no API key required)
GEOCODING_URL = 'https://geocoding-api.open-meteo.com/v1/search'
WEATHER_URL = 'https://api.open-meteo.com/v1/forecast'

# Map Open-Meteo weather codes to icons
WEATHER_ICONS = {
    0: '☀️', 1: '🌤️', 2: '⛅', 3: '☁️', 45: '🌫️', 48: '🌫️',
    51: '🌧️', 53: '🌧️', 55: '🌧️', 61: '🌧️', 63: '⛈️', 65: '⛈️',
    71: '❄️', 73: '❄️', 75: '❄️', 77: '❄️', 80: '🌧️', 81: '⛈️', 82: '⛈️',
    85: '❄️', 86: '❄️', 95: '⛈️', 96: '⛈️', 99: '⛈️'
}

# Map weather codes to descriptions
WEATHER_DESCRIPTIONS = {
    0: 'Clear sky', 1: 'Mainly clear', 2: 'Partly cloudy', 3: 'Overcast', 45: 'Foggy', 48: 'Depositing rime fog',
    51: 'Light drizzle', 53: 'Moderate drizzle', 55: 'Dense drizzle', 61: 'Slight rain', 63: 'Moderate rain', 65: 'Heavy rain',
    71: 'Slight snow', 73: 'Moderate snow', 75: 'Heavy snow', 77: 'Snow grains', 80: 'Slight rain showers', 
    81: 'Moderate rain showers', 82: 'Violent rain showers', 85: 'Slight snow showers', 86: 'Heavy snow showers',
    95: 'Thunderstorm', 96: 'Thunderstorm with slight hail', 99: 'Thunderstorm with heavy hail'
}


def get_city_coordinates(city_name):
    """Get latitude and longitude for a city using Open-Meteo geocoding."""
    try:
        params = {'name': city_name, 'count': 1, 'language': 'en', 'format': 'json'}
        response = requests.get(GEOCODING_URL, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('results'):
                result = data['results'][0]
                return {
                    'latitude': result['latitude'],
                    'longitude': result['longitude'],
                    'city': result['name'],
                    'country': result.get('country', ''),
                }
            else:
                return None
        return None
    except Exception:
        return None


def get_weather_data(latitude, longitude, city_name, country, unit='celsius'):
    """Get weather data from Open-Meteo API."""
    try:
        params = {
            'latitude': latitude,
            'longitude': longitude,
            'current': 'temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,apparent_temperature',
            'temperature_unit': 'celsius',
            'wind_speed_unit': 'ms'
        }
        response = requests.get(WEATHER_URL, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            current = data['current']
            weather_code = current['weather_code']
            
            temp = current['temperature_2m']
            feels_like = current['apparent_temperature']
            
            # Convert to Fahrenheit if requested
            if unit.lower() == 'fahrenheit':
                temp = round((temp * 9/5) + 32)
                feels_like = round((feels_like * 9/5) + 32)
                unit_symbol = '°F'
            else:
                temp = round(temp)
                feels_like = round(feels_like)
                unit_symbol = '°C'
            
            return {
                'city': city_name,
                'country': country,
                'temperature': temp,
                'feels_like': feels_like,
                'humidity': current['relative_humidity_2m'],
                'wind_speed': round(current['wind_speed_10m'], 1),
                'description': WEATHER_DESCRIPTIONS.get(weather_code, 'Unknown'),
                'icon': WEATHER_ICONS.get(weather_code, '🌡️'),
                'unit': unit_symbol,
            }
        return None
    except Exception:
        return None


@app.route('/', methods=['GET', 'POST'])
def index():
    """Handle both displaying the form and processing city searches."""
    weather_data = None
    error_message = None
    unit = request.form.get('unit', 'celsius') if request.method == 'POST' else 'celsius'

    if request.method == 'POST':
        city = request.form.get('city', '').strip()

        if not city:
            error_message = 'Please enter a city name.'
        else:
            try:
                # Get city coordinates
                city_info = get_city_coordinates(city)
                if city_info:
                    # Get weather data with selected unit
                    weather = get_weather_data(
                        city_info['latitude'],
                        city_info['longitude'],
                        city_info['city'],
                        city_info['country'],
                        unit
                    )
                    if weather:
                        weather_data = weather
                    else:
                        error_message = "Unable to fetch weather data. Please try again later."
                else:
                    error_message = f"City '{city}' not found. Please check the spelling and try again."

            except requests.exceptions.Timeout:
                error_message = "Request timed out. Please try again later."
            except requests.exceptions.ConnectionError:
                error_message = "Connection error. Please check your internet connection."
            except Exception as e:
                error_message = f"An unexpected error occurred: {str(e)}"

    return render_template('index.html', weather_data=weather_data, error_message=error_message, selected_unit=unit)


if __name__ == '__main__':
    app.run(debug=True)
