# -*- coding: utf-8 -*-
"""
Created on Tue May  5 13:49:33 2026

@author: xiaoy
"""

import requests
import streamlit as st

st.set_page_config(page_title="城市外出建议 Demo", page_icon="🌤️")
# ===== 内测密码保护 =====
password = st.text_input("🔐 输入内测邀请码", type="password")

if password != st.secrets["APP_PASSWORD"]:
    st.info("该应用处于内测阶段，请输入邀请码访问")
    st.stop()
    
st.title("🌤️ 城市天气与空气质量 Demo")

city = st.text_input("输入城市", "Bremen")

WAQI_TOKEN = st.secrets["WAQI_TOKEN"]


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
    """
    使用 WAQI 经纬度接口，获取最近地面站空气质量。
    """
    url = f"https://api.waqi.info/feed/geo:{lat};{lon}/"
    params = {"token": WAQI_TOKEN}

    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    if data.get("status") != "ok":
        return None

    return data["data"]


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


def get_iaqi_value(air, key):
    """
    从 WAQI 的 iaqi 字段里安全提取污染物数值。
    """
    try:
        return air["iaqi"][key]["v"]
    except:
        return None


def simple_advice(weather, air):
    temp = weather.get("temperature_2m")
    wind = weather.get("wind_speed_10m")

    aqi = air.get("aqi") if air else None
    pm25 = get_iaqi_value(air, "pm25") if air else None
    uv = get_iaqi_value(air, "uvi") if air else None

    advice = []

    if aqi is not None:
        try:
            if int(aqi) > 100:
                advice.append("空气质量一般，不太建议长时间户外运动。")
            else:
                advice.append("空气质量可以接受，适合一般外出。")
        except:
            advice.append("空气质量数据暂时不完整。")

    if pm25 is not None and pm25 > 75:
        advice.append("PM2.5 偏高，敏感人群建议减少户外活动。")

    if wind is not None and wind < 1.5:
        advice.append("风速较低，污染物扩散条件一般。")
    else:
        advice.append("有一定风速，通风扩散条件较好。")

    if temp is not None:
        if temp < 5:
            advice.append("气温较低，建议穿厚外套。")
        elif temp < 15:
            advice.append("建议穿外套或卫衣。")
        elif temp < 25:
            advice.append("气温舒适，适合轻便穿着。")
        else:
            advice.append("气温较高，注意补水。")

    if uv is not None and uv >= 6:
        advice.append("紫外线较强，建议防晒。")

    return " ".join(advice)


if st.button("获取今日建议"):
    loc = get_location(city)

    if loc is None:
        st.error("没有找到这个城市。")
    else:
        lat = loc["latitude"]
        lon = loc["longitude"]

        st.subheader(f"{loc['name']}, {loc.get('country', '')}")
        st.write(f"经纬度：{lat:.3f}, {lon:.3f}")

        weather = get_weather(lat, lon)
        air = get_air_quality_waqi(lat, lon)

        st.subheader("🌡️ 实时天气")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("温度", f"{weather.get('temperature_2m', '暂无')} °C")
            st.metric("体感温度", f"{weather.get('apparent_temperature', '暂无')} °C")

        with col2:
            st.metric("湿度", f"{weather.get('relative_humidity_2m', '暂无')} %")
            st.metric("降水量", f"{weather.get('precipitation', '暂无')} mm")

        with col3:
            wind_deg = weather.get("wind_direction_10m")
            wind_name = wind_direction_cn(wind_deg)
            st.metric("风速", f"{weather.get('wind_speed_10m', '暂无')} km/h")
            st.metric("风向", wind_name)

        st.subheader("🌫️ 空气质量")

        if air is None:
            st.warning("暂时无法获取 WAQI 空气质量数据，请检查 token 或该城市附近是否有监测站。")
        else:
            aqi = air.get("aqi")
            station = air.get("city", {}).get("name", "未知监测站")
            pm25 = get_iaqi_value(air, "pm25")
            pm10 = get_iaqi_value(air, "pm10")
            no2 = get_iaqi_value(air, "no2")
            o3 = get_iaqi_value(air, "o3")
            uv = get_iaqi_value(air, "uvi")

            st.write(f"最近监测站：{station}")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("AQI指数", aqi)
                st.metric("空气质量等级", aqi_level_cn(aqi))

            with col2:
                st.metric("PM2.5", "暂无" if pm25 is None else pm25)
                st.metric("PM10", "暂无" if pm10 is None else pm10)

            with col3:
                st.metric("臭氧 O₃", "暂无" if o3 is None else o3)
                st.metric("二氧化氮 NO₂", "暂无" if no2 is None else no2)

            st.metric("紫外线指数", "暂无" if uv is None else uv)

        st.subheader("✅ 初步外出建议")
        st.success(simple_advice(weather, air))
