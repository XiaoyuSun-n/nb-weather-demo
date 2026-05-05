# -*- coding: utf-8 -*-
"""
Created on Tue May  5 15:30:36 2026

@author: xiaoy
"""

# -*- coding: utf-8 -*-
import requests
import streamlit as st
from datetime import date,datetime

st.set_page_config(page_title="城市外出建议 Demo", page_icon="🌤️")

# ===== 内测密码保护 =====
# password = st.text_input("🔐 输入内测邀请码", type="password")

# if password != st.secrets["APP_PASSWORD"]:
#     st.info("该应用处于内测阶段，请输入邀请码访问")
#     st.stop()

st.title("🌤️ 城市天气与空气质量 Demo")

city = st.text_input("输入城市", "Bremen")
WAQI_TOKEN = "cabc6501aa8f1cd650603aa5d56183cb1e08ef1b"
# WAQI_TOKEN = st.secrets["WAQI_TOKEN"]


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
            "precipitation"
        ),
        "timezone": "auto"
    }

    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()["current"]


def get_air_quality_waqi(lat, lon):
    url = f"https://api.waqi.info/feed/geo:{lat};{lon}/"
    params = {"token": WAQI_TOKEN}

    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    if data.get("status") != "ok":
        return None

    return data["data"]


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


def get_forecast_aqi_3days(air):
    """
    从 WAQI forecast.daily 中提取今天起未来3天空气质量风险。
    用 pm25 / pm10 / o3 的 daily max 最大值近似代表当天空气质量风险。
    自动过滤旧日期和异常日期。
    """
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

            # 过滤掉今天以前的旧日期
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


def temp_feeling_advice(background_temp, station_temp):
    """
    Open-Meteo = 背景温度
    WAQI station t = 监测站局地温度
    """
    if background_temp is None or station_temp is None:
        return ""

    diff = station_temp - background_temp

    if diff >= 2:
        return "局地温度比背景温度偏高，体感可能会有点热，建议轻便穿衣。"
    elif diff <= -2:
        return "局地温度比背景温度偏低，体感可能会有点冷，建议增添一件外套。"
    else:
        return "局地温度和背景温度接近，穿衣按正常体感即可。"


def main_advice(weather, air):
    advice = []

    aqi = air.get("aqi") if air else None
    wind = weather.get("wind_speed_10m")
    background_temp = weather.get("temperature_2m")
    station_temp = get_iaqi_value(air, "t") if air else None

    # 今日空气质量
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

    # 明后天空气质量提醒
    forecast3 = get_forecast_aqi_3days(air)

    if len(forecast3) >= 2:
        tomorrow = forecast3[1]
        if tomorrow["aqi_pred"] > 100:
            advice.append("明天空气质量可能转差，如果今天状态不错，建议今天抓紧出门活动。")
        elif tomorrow["aqi_pred"] > 50:
            advice.append("明天空气质量可能一般，敏感人群可以优先选择今天外出。")

    # 温度偏差建议
    temp_advice = temp_feeling_advice(background_temp, station_temp)
    if temp_advice:
        advice.append(temp_advice)

    # 风速扩散
    if wind is not None:
        if wind < 1.5:
            advice.append("风速较低，污染物扩散条件一般。")
        else:
            advice.append("有一定风速，通风扩散条件较好。")

    return " ".join(advice)


if st.button("获取今日建议"):
    loc = get_location(city)

    if loc is None:
        st.error("没有找到这个城市。")
    else:
        lat = loc["latitude"]
        lon = loc["longitude"]

        weather = get_weather(lat, lon)
        air = get_air_quality_waqi(lat, lon)

        st.subheader(f"{loc['name']}, {loc.get('country', '')}")

        if air is None:
            st.warning("暂时无法获取 WAQI 空气质量数据，请检查tocken或该城市附近是否有监测站。")
            st.stop()

        # ===== 顶部建议 =====
        st.subheader("✅ 今日外出建议")
        st.success(main_advice(weather, air))

        # ===== 核心数据显示 =====
        st.subheader("📍 当前状态")

        aqi = air.get("aqi")
        station = air.get("city", {}).get("name", "未知监测站")

        background_temp = weather.get("temperature_2m")
        apparent_temp = weather.get("apparent_temperature")
        station_temp = get_iaqi_value(air, "t")

        wind_deg = weather.get("wind_direction_10m")
        wind_name = wind_direction_cn(wind_deg)
        wind_speed = weather.get("wind_speed_10m")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("背景温度", f"{background_temp} °C")
            st.metric("体感温度", f"{apparent_temp} °C")

        with col2:
            st.metric("局地站点温度", "暂无" if station_temp is None else f"{station_temp} °C")
            st.metric("风向", wind_name)

        with col3:
            st.metric("AQI指数", aqi)
            st.metric("空气质量等级", aqi_level_cn(aqi))

        st.caption(f"最近空气质量监测站：{station}")

        # ===== 未来3天空气质量预判 =====
        st.subheader("🌫️ 未来3天空气质量预判")

        forecast3 = get_forecast_aqi_3days(air)

        if not forecast3:
            st.info("暂无未来空气质量预报。")
        else:
            cols = st.columns(len(forecast3))

            for col, item in zip(cols, forecast3):
                with col:
                    st.metric(
                        label=item["day"],
                        value=item["aqi_pred"],
                        delta=item["level"]
                    )