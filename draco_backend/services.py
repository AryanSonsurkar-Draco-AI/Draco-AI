import requests
import sympy as sp

from draco_backend.config import WEATHER_API_KEY, NEWS_API_KEY

# will be wired from main.py
speak = None


def get_weather(city):
    if not WEATHER_API_KEY:
        return "Weather feature needs an API key. Add it to WEATHER_API_KEY."

    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
        response = requests.get(url)
        data = response.json()

        if data.get("cod") != 200:
            return f"Could not find weather for '{city}'. Please check the city name."

        temp = data["main"]["temp"]
        condition = data["weather"][0]["description"].title()
        humidity = data["main"]["humidity"]
        wind_speed = data["wind"]["speed"]

        result = (
            f"Weather in {city}:\n"
            f"Temperature: {temp}°C\n"
            f"Condition: {condition}\n"
            f"Humidity: {humidity}%\n"
            f"Wind Speed: {wind_speed} m/s"
        )
        return result

    except Exception as e:
        return f"Error fetching weather: {str(e)}"


def get_news(topic="general"):
    if not NEWS_API_KEY:
        return "News feature needs an API key. Add it to NEWS_API_KEY."

    try:
        url = f"https://newsapi.org/v2/top-headlines?q={topic}&apiKey={NEWS_API_KEY}&pageSize=5"
        response = requests.get(url)
        data = response.json()

        if data.get("status") != "ok" or not data.get("articles"):
            return f"No news found for '{topic}'."

        news_list = ""
        for i, article in enumerate(data["articles"], start=1):
            title = article.get("title", "No title")
            source = article.get("source", {}).get("name", "Unknown")
            news_list += f"{i}. {title} ({source})\n"

        return f"Top news on '{topic}':\n{news_list}"

    except Exception as e:
        return f"Error fetching news: {str(e)}"


def solve_math(cmd):
    global speak
    try:
        if "calculate" in cmd.lower():
            expression = cmd.lower().replace("calculate", "").strip()
            result = eval(expression)
            if speak:
                speak(f"Result: {result}")
            return f"Result: {result}"

        elif "solve" in cmd.lower():
            equation = cmd.lower().replace("solve", "").strip()
            x = sp.symbols('x')
            solution = sp.solve(equation, x)
            if speak:
                speak(f"Solution: {solution}")
            return f"Solution: {solution}"

        else:
            if speak:
                speak("Math command not recognized.")
            return "Math command not recognized."

    except Exception as e:
        if speak:
            speak(f"Error: {str(e)}")
        return f"Error: {str(e)}"


EXCHANGE_API_KEY = "d97d653e87f3ea812b311d20"  # for currency


def convert_unit(cmd):
    global speak
    try:
        cmd_lower = cmd.lower()

        if "convert" in cmd_lower and "to" in cmd_lower:
            words = cmd_lower.replace("convert", "").strip().split(" ")
            amount = float(words[0])
            from_unit = words[1].upper()
            to_unit = words[-1].upper()

            if from_unit == "USD" and to_unit == "INR":
                rate = 82.5
                result = amount * rate
                if speak:
                    speak(f"{amount} {from_unit} = {result} {to_unit}")
                return f"{amount} {from_unit} = {result} {to_unit}"
            else:
                if speak:
                    speak(f"Conversion from {from_unit} to {to_unit} not supported yet.")
                return f"Conversion from {from_unit} to {to_unit} not supported yet."

        elif "km to miles" in cmd_lower:
            km = float(cmd_lower.split("km")[0].strip())
            miles = km * 0.621371
            if speak:
                speak(f"{km} km = {miles:.2f} miles")
            return f"{km} km = {miles:.2f} miles"

        elif "c to f" in cmd_lower:
            c = float(cmd_lower.split("c")[0].strip())
            f = (c * 9/5) + 32
            if speak:
                speak(f"{c}°C = {f:.2f}°F")
            return f"{c}°C = {f:.2f}°F"

        else:
            if speak:
                speak("Unit conversion not recognized.")
            return "Unit conversion not recognized."

    except Exception as e:
        if speak:
            speak(f"Error: {str(e)}")
        return f"Error: {str(e)}"
