from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

# Open-Meteo API endpoints (free, no API key required)
GEOCODING_URL = 'https://geocoding-api.open-meteo.com/v1/search'
REVERSE_GEOCODING_URL = 'https://geocoding-api.open-meteo.com/v1/reverse'
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


def get_city_from_coordinates(latitude, longitude):
    """Get city name from coordinates using reverse geocoding."""
    try:
        params = {
            'latitude': latitude,
            'longitude': longitude,
            'language': 'en',
            'format': 'json'
        }
        response = requests.get(REVERSE_GEOCODING_URL, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('results') and len(data['results']) > 0:
                result = data['results'][0]
                city = result.get('name') or result.get('admin1', 'Unknown')
                country = result.get('country', '')
                
                # If we still don't have a city name, try admin2 or admin3
                if not city or city == 'Unknown':
                    city = result.get('admin2') or result.get('admin3') or 'Unknown Location'
                
                return {
                    'city': city,
                    'country': country,
                    'latitude': latitude,
                    'longitude': longitude
                }
            else:
                # No results found from reverse geocoding
                return None
        else:
            print(f"Reverse geocoding API error: {response.status_code}")
            return None
    except requests.exceptions.Timeout:
        print("Reverse geocoding timeout")
        return None
    except Exception as e:
        print(f"Reverse geocoding exception: {str(e)}")
        return None


def get_weather_data(latitude, longitude, city_name, country, unit='celsius'):
    """Get weather data from Open-Meteo API."""
    try:
        params = {
            'latitude': latitude,
            'longitude': longitude,
            'current': 'temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,apparent_temperature',
            'daily': 'weather_code,temperature_2m_max,temperature_2m_min',
            'temperature_unit': 'celsius',
            'wind_speed_unit': 'ms',
            'timezone': 'auto'
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
            
            # Process forecast data (5 days)
            forecast = []
            if 'daily' in data:
                daily = data['daily']
                for i in range(min(5, len(daily['time']))):
                    day_code = daily['weather_code'][i]
                    max_temp = daily['temperature_2m_max'][i]
                    min_temp = daily['temperature_2m_min'][i]
                    
                    if unit.lower() == 'fahrenheit':
                        max_temp = round((max_temp * 9/5) + 32)
                        min_temp = round((min_temp * 9/5) + 32)
                    else:
                        max_temp = round(max_temp)
                        min_temp = round(min_temp)
                    
                    forecast.append({
                        'date': daily['time'][i],
                        'max_temp': max_temp,
                        'min_temp': min_temp,
                        'description': WEATHER_DESCRIPTIONS.get(day_code, 'Unknown'),
                        'icon': WEATHER_ICONS.get(day_code, '🌡️'),
                    })
            
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
                'forecast': forecast,
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


@app.route('/api/weather-from-location', methods=['POST'])
def weather_from_location():
    """API endpoint for geolocation-based weather."""
    try:
        data = request.get_json()
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        unit = data.get('unit', 'celsius')
        
        if not latitude or not longitude:
            return jsonify({'success': False, 'error': 'Missing coordinates'}), 400
        
        print(f"Geolocation request: lat={latitude}, lon={longitude}, unit={unit}")
        
        # Get city from coordinates
        city_info = get_city_from_coordinates(latitude, longitude)
        if not city_info:
            print("Failed to get city from coordinates")
            return jsonify({'success': False, 'error': 'Unable to determine your location. Please try searching for a city instead.'}), 400
        
        print(f"City detected: {city_info['city']}")
        
        # Get weather data
        weather = get_weather_data(
            latitude,
            longitude,
            city_info['city'],
            city_info['country'],
            unit
        )
        
        if weather:
            print(f"Weather data retrieved successfully for {city_info['city']}")
            return jsonify({'success': True, 'weather': weather})
        else:
            print("Failed to get weather data")
            return jsonify({'success': False, 'error': 'Unable to fetch weather data. Please try again.'}), 500
            
    except Exception as e:
        error_msg = str(e)
        print(f"Geolocation endpoint error: {error_msg}")
        return jsonify({'success': False, 'error': error_msg}), 500


if __name__ == '__main__':
    app.run(debug=True)
