# -*- coding: utf-8 -*-
import requests
import streamlit as st
from datetime import date, datetime, timedelta

st.set_page_config(page_title="城市外出建议 Demo", page_icon="🌤️")

st.title("🌤️ 城市天气与空气质量 Demo")

city = st.text_input("输入城市", "Bremen")

WAQI_TOKEN = "cabc6501aa8f1cd650603aa5d56183cb1e08ef1b"
# WAQI_TOKEN = st.secrets["WAQI_TOKEN"]


# =====================
# 基础数据获取
# =====================
def get_location(city):
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city, "count": 1, "language": "zh", "format": "json"}

    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    if "results" not in data:
        return None

    return data["results"][0]


def get_weather(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": lat,
        "longitude": lon,
        "current": (
            "temperature_2m,"
            "apparent_temperature,"
            "relative_humidity_2m,"
            "wind_speed_10m,"
            "wind_direction_10m,"
            "precipitation,"
            "weather_code"
        ),
        "hourly": (
            "temperature_2m,"
            "apparent_temperature,"
            "precipitation_probability,"
            "precipitation,"
            "wind_speed_10m,"
            "wind_direction_10m,"
            "uv_index"
        ),
        "daily": (
            "temperature_2m_max,"
            "temperature_2m_min,"
            "precipitation_sum,"
            "precipitation_probability_max,"
            "uv_index_max"
        ),
        "forecast_days": 3,
        "timezone": "auto"
    }

    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def get_air_quality_waqi(lat, lon):
    url = f"https://api.waqi.info/feed/geo:{lat};{lon}/"
    params = {"token": WAQI_TOKEN}

    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    if data.get("status") != "ok":
        return None

    return data["data"]


# =====================
# 工具函数
# =====================
def get_iaqi_value(air, key):
    try:
        return air["iaqi"][key]["v"]
    except:
        return None


def wind_direction_cn(deg):
    if deg is None:
        return "未知"

    directions = [
        "北风", "东北风", "东风", "东南风",
        "南风", "西南风", "西风", "西北风"
    ]
    idx = round(deg / 45) % 8
    return directions[idx]


def aqi_level_cn(aqi):
    if aqi is None:
        return "未知"

    try:
        aqi = int(aqi)
    except:
        return "未知"

    if aqi <= 50:
        return "优"
    elif aqi <= 100:
        return "良"
    elif aqi <= 150:
        return "轻度污染"
    elif aqi <= 200:
        return "中度污染"
    elif aqi <= 300:
        return "重度污染"
    else:
        return "严重污染"


def temp_feeling_advice(background_temp, station_temp):
    if background_temp is None or station_temp is None:
        return ""

    diff = station_temp - background_temp

    if diff >= 2:
        return "局地温度比背景温度偏高，体感可能会有点热，建议轻便穿衣。"
    elif diff <= -2:
        return "局地温度比背景温度偏低，体感可能会有点冷，建议增添一件衣物。"
    else:
        return "局地温度和背景温度接近，穿衣按正常体感即可。"


def get_forecast_aqi_3days(air):
    if not air:
        return []

    daily = air.get("forecast", {}).get("daily", {})
    pollutants = ["pm25", "pm10", "o3"]

    today = date.today()
    day_dict = {}

    for pol in pollutants:
        for item in daily.get(pol, []):
            d_str = item.get("day")
            v = item.get("max")

            if d_str is None or v is None:
                continue

            try:
                d_obj = datetime.strptime(d_str, "%Y-%m-%d").date()
            except:
                continue

            if d_obj < today:
                continue

            if d_str not in day_dict:
                day_dict[d_str] = []

            day_dict[d_str].append(v)

    result = []

    for d in sorted(day_dict.keys())[:3]:
        risk_index = max(day_dict[d])
        result.append({
            "day": d,
            "aqi_pred": risk_index,
            "level": aqi_level_cn(risk_index)
        })

    return result


# =====================
# 建议生成
# =====================
def rain_advice(weather):
    hourly = weather.get("hourly", {})
    times = hourly.get("time", [])
    probs = hourly.get("precipitation_probability", [])
    precs = hourly.get("precipitation", [])

    if not times or not probs:
        return ""

    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    after_tomorrow = (date.today() + timedelta(days=2)).isoformat()

    rain_hours = {
        today: [],
        tomorrow: [],
        after_tomorrow: []
    }

    for t, p, rain in zip(times, probs, precs):
        day = t[:10]
        hour = int(t[11:13])

        if day not in rain_hours:
            continue

        if p is None:
            continue

        is_rain = (p >= 40) or (rain is not None and rain > 0.2)

        if is_rain:
            rain_hours[day].append(hour)

    if rain_hours[today]:
        h1 = min(rain_hours[today])
        h2 = max(rain_hours[today])
        return f"今天约 {h1}:00–{h2}:00 有降水风险，出门建议带伞。"

    if rain_hours[tomorrow]:
        h1 = min(rain_hours[tomorrow])
        h2 = max(rain_hours[tomorrow])
        return f"今天基本不下雨；明天约 {h1}:00–{h2}:00 有降水风险，建议优先今天安排户外活动。"

    if rain_hours[after_tomorrow]:
        h1 = min(rain_hours[after_tomorrow])
        h2 = max(rain_hours[after_tomorrow])
        return f"今天和明天降水风险较低；后天约 {h1}:00–{h2}:00 可能有降水。"

    return "未来三天降水风险整体较低，适合安排户外活动。"


def best_outdoor_window(weather):
    hourly = weather.get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    probs = hourly.get("precipitation_probability", [])
    winds = hourly.get("wind_speed_10m", [])
    uvis = hourly.get("uv_index", [])

    if not times:
        return ""

    today = date.today().isoformat()
    candidates = []

    for t, temp, rain_prob, wind, uvi in zip(times, temps, probs, winds, uvis):
        day = t[:10]
        hour = int(t[11:13])

        if day != today:
            continue

        if hour < 8 or hour > 20:
            continue

        score = 0

        if temp is not None:
            if 12 <= temp <= 22:
                score += 2
            elif 8 <= temp < 12 or 22 < temp <= 26:
                score += 1

        if rain_prob is not None:
            if rain_prob < 20:
                score += 2
            elif rain_prob < 40:
                score += 1
            else:
                score -= 2

        if wind is not None:
            if 1 <= wind <= 6:
                score += 1
            elif wind > 9:
                score -= 1

        if uvi is not None:
            if uvi <= 5:
                score += 1
            else:
                score -= 1

        candidates.append((score, hour))

    if not candidates:
        return ""

    candidates = sorted(candidates, reverse=True)
    best_hour = candidates[0][1]

    start_hour = max(8, best_hour - 1)
    end_hour = min(21, best_hour + 2)

    return f"今天 {start_hour}:00–{end_hour}:00 最适合散步。"


def main_advice(weather, air):
    advice = []

    current = weather.get("current", {})
    aqi = air.get("aqi") if air else None

    background_temp = current.get("temperature_2m")
    station_temp = get_iaqi_value(air, "t") if air else None
    wind = current.get("wind_speed_10m")

    best_window = best_outdoor_window(weather)
    if best_window:
        advice.append(best_window)

    rain_text = rain_advice(weather)
    if rain_text:
        advice.append(rain_text)

    if aqi is not None:
        try:
            aqi_int = int(aqi)

            if aqi_int <= 50:
                advice.append("今天空气质量很好，适合出门走走。")
            elif aqi_int <= 100:
                advice.append("今天空气质量可以接受，适合一般外出。")
            else:
                advice.append("今天空气质量一般，不建议长时间户外运动。")
        except:
            advice.append("今天空气质量数据不完整，建议谨慎参考。")

    forecast3 = get_forecast_aqi_3days(air)

    if len(forecast3) >= 2:
        tomorrow = forecast3[1]

        if tomorrow["aqi_pred"] > 100:
            advice.append("明天空气质量可能转差，建议今天完成户外活动。")
        elif tomorrow["aqi_pred"] > 50:
            advice.append("明天空气质量可能一般，敏感人群可以优先选择今天外出。")

    temp_text = temp_feeling_advice(background_temp, station_temp)
    if temp_text:
        advice.append(temp_text)

    if wind is not None:
        if wind < 1.5:
            advice.append("风速较低，污染物扩散条件一般。")
        else:
            advice.append("有一定风速，通风扩散条件较好。")

    return advice


# =====================
# 页面主体
# =====================
if st.button("获取今日建议"):

    loc = get_location(city)

    if loc is None:
        st.error("没有找到这个城市。")
        st.stop()

    lat = loc["latitude"]
    lon = loc["longitude"]

    weather = get_weather(lat, lon)
    air = get_air_quality_waqi(lat, lon)

    st.subheader(f"📍 {loc['name']}, {loc.get('country', '')}")

    if air is None:
        st.warning("暂时无法获取 WAQI 空气质量数据，请检查 token 或该城市附近是否有监测站。")
        st.stop()

    current = weather.get("current", {})

    aqi = air.get("aqi")
    station = air.get("city", {}).get("name", "未知监测站")

    background_temp = current.get("temperature_2m")
    apparent_temp = current.get("apparent_temperature")
    humidity = current.get("relative_humidity_2m")
    precipitation = current.get("precipitation")

    wind_deg = current.get("wind_direction_10m")
    wind_name = wind_direction_cn(wind_deg)
    wind_speed = current.get("wind_speed_10m")

    station_temp = get_iaqi_value(air, "t")
    pm25 = get_iaqi_value(air, "pm25")
    pm10 = get_iaqi_value(air, "pm10")
    o3 = get_iaqi_value(air, "o3")

    # =====================
    # 顶部建议
    # =====================
    st.subheader("✅ 今日外出建议")

    for item in main_advice(weather, air):
        st.success(f"• {item}")

    # =====================
    # 模块1：当前综合状态
    # =====================
    st.subheader("📍 当前综合状态")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("背景温度", f"{background_temp} °C")
        st.metric("体感温度", f"{apparent_temp} °C")

    with col2:
        st.metric("当前降水", f"{precipitation} mm")
        st.metric("相对湿度", f"{humidity} %")

    with col3:
        st.metric("风速", f"{wind_speed} m/s")
        st.metric("风向", wind_name)

    with col4:
        st.metric("AQI指数", aqi)
        st.metric("空气质量", aqi_level_cn(aqi))

    with col5:
        hourly = weather.get("hourly", {})
        uvis = hourly.get("uv_index", [])
        uvi_now = uvis[0] if len(uvis) > 0 else None
        st.metric("紫外线", "暂无" if uvi_now is None else f"{uvi_now}")
        st.metric("局地站温", "暂无" if station_temp is None else f"{station_temp} °C")

    st.caption(f"最近空气质量监测站：{station}")

    # =====================
    # 模块2：主要污染物
    # =====================
    st.subheader("🌫️ 当前空气质量细节")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("PM2.5", "暂无" if pm25 is None else pm25)

    with col2:
        st.metric("PM10", "暂无" if pm10 is None else pm10)

    with col3:
        st.metric("O₃", "暂无" if o3 is None else o3)

    # =====================
    # 模块3：未来3天天气预报
    # =====================
    st.subheader("🌦️ 未来3天天气预报")

    daily = weather.get("daily", {})
    days = daily.get("time", [])

    if not days:
        st.info("暂无天气预报数据。")
    else:
        cols = st.columns(len(days))

        for i, col in enumerate(cols):
            with col:
                tmax = daily["temperature_2m_max"][i]
                tmin = daily["temperature_2m_min"][i]
                rain_sum = daily["precipitation_sum"][i]
                rain_prob = daily["precipitation_probability_max"][i]
                uvi_max = daily["uv_index_max"][i]

                st.markdown(f"**{days[i]}**")
                st.metric("温度", f"{tmin}–{tmax} °C")
                st.metric("降水概率", f"{rain_prob} %")
                st.metric("降水量", f"{rain_sum} mm")
                st.metric("紫外线", f"{uvi_max}")

    # =====================
    # 模块4：未来3天空气质量预判
    # =====================
    st.subheader("🌫️ 未来3天空气质量预判")

    forecast3 = get_forecast_aqi_3days(air)

    if not forecast3:
        st.info("暂无未来空气质量预报。")
    else:
        cols = st.columns(len(forecast3))

        for col, item in zip(cols, forecast3):
            with col:
                st.markdown(f"**{item['day']}**")
                st.metric(
                    label="空气质量风险指数",
                    value=item["aqi_pred"],
                    delta=item["level"]
                )