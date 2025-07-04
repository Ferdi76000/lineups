#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jul  4 10:28:11 2025

@author: ferdinandclayes
"""

import streamlit as st
import pandas as pd
import pydeck as pdk
from geopy.geocoders import Nominatim

# --- Load Data ---
@st.cache_data
def load_data():
    df = pd.read_excel("Database.xlsx", sheet_name="BASE_LINEUP")
    df.columns = df.columns.str.strip().str.replace(" ", "_").str.lower()
    df['produit_brut'] = df['produit_brut'].fillna("UNKNOWN").astype(str)
    df['pays'] = df['pays'].astype(str)
    df['shipper_brut'] = df['shipper_brut'].fillna("UNKNOWN").astype(str)
    df['destination_brute'] = df['destination_brute'].fillna("UNKNOWN").astype(str)
    return df

df = load_data()
st.sidebar.title("🔍 Filters")
countries = st.sidebar.multiselect("Select Load Country (Pays)", sorted(df['pays'].dropna().unique()))
products = st.sidebar.multiselect("Select Product(s)", sorted(df['produit_brut'].dropna().unique()))
shippers = st.sidebar.multiselect("Select Shipper(s)", sorted(df['shipper_brut'].dropna().unique()))

filtered = df.copy()
if countries:
    filtered = filtered[filtered['pays'].isin(countries)]
if products:
    filtered = filtered[filtered['produit_brut'].isin(products)]
if shippers:
    filtered = filtered[filtered['shipper_brut'].isin(shippers)]


@st.cache_data
def geocode_destinations(destinations):
    geolocator = Nominatim(user_agent="lineup_app")
    coords = []
    for dest in destinations:
        try:
            location = geolocator.geocode(dest)
            if location:
                coords.append((dest, location.latitude, location.longitude))
        except:
            continue
    return pd.DataFrame(coords, columns=["destination_brute", "lat", "lon"])

unique_destinations = filtered['destination_brute'].dropna().unique()
dest_df = geocode_destinations(unique_destinations)

# --- Merge Coordinates ---
filtered = filtered.merge(dest_df, on="destination_brute", how="left")



# --- Map Display ---
st.subheader("🌍 Shipment Destinations Map")
# Group shipments per destination
grouped = (
    filtered.dropna(subset=["lat", "lon"])
    .groupby(["destination_brute", "lat", "lon"], as_index=False)
    .agg({"tonnage": "sum"})
)
map_data = grouped

def assign_radius(tonnage):
    if tonnage < 30000:
        return 50000
    elif tonnage < 100000:
        return 100000
    elif tonnage < 150000:
        return 150000
    elif tonnage < 250000:
        return 200000
    elif tonnage < 500000:
        return 250000
    else:
        return 300000

map_data["radius"] = map_data["tonnage"].apply(assign_radius)

layer = pdk.Layer(
    "ScatterplotLayer",
    data=map_data,
    get_position='[lon, lat]',
    get_radius='radius',  # Adjusted to better reflect size
    get_fill_color="""
    [
        tonnage < 30000 ? 255 :
        tonnage < 100000 ? 255 :
        tonnage < 150000 ? 255 :
        tonnage < 250000 ? 255 :
        tonnage < 500000 ? 255 : 200,

        tonnage < 30000 ? 255 :
        tonnage < 100000 ? 220 :
        tonnage < 150000 ? 180 :
        tonnage < 250000 ? 120 :
        tonnage < 500000 ? 60 : 0,

        tonnage < 30000 ? 180 :
        tonnage < 100000 ? 100 :
        tonnage < 150000 ? 60 :
        tonnage < 250000 ? 20 :
        tonnage < 500000 ? 0 : 0,

        160
    ]
    """,
    pickable=True
)



view_state = pdk.ViewState(
    latitude=map_data["lat"].mean(),
    longitude=map_data["lon"].mean(),
    zoom=2
)

deck = pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    tooltip={"text": "Destination: {destination_brute}\nTonnage: {tonnage}"}
)

st.pydeck_chart(deck)

# c'est la legende

st.markdown("### 🗺️ Tonnage Color Scale")
st.markdown("""
<div style='display: flex; flex-direction: column; gap: 6px;'>
  <div style='display: flex; align-items: center; gap: 8px;'>
    <div style='width: 20px; height: 20px; background-color: rgb(255,255,180); border: 1px solid #000'></div>
    <span>< 30,000 t</span>
  </div>
  <div style='display: flex; align-items: center; gap: 8px;'>
    <div style='width: 20px; height: 20px; background-color: rgb(255,220,100); border: 1px solid #000'></div>
    <span>30,000 – 100,000 t</span>
  </div>
  <div style='display: flex; align-items: center; gap: 8px;'>
    <div style='width: 20px; height: 20px; background-color: rgb(255,180,60); border: 1px solid #000'></div>
    <span>100,000 – 150,000 t</span>
  </div>
  <div style='display: flex; align-items: center; gap: 8px;'>
    <div style='width: 20px; height: 20px; background-color: rgb(255,120,20); border: 1px solid #000'></div>
    <span>150,000 – 250,000 t</span>
  </div>
  <div style='display: flex; align-items: center; gap: 8px;'>
    <div style='width: 20px; height: 20px; background-color: rgb(255,60,0); border: 1px solid #000'></div>
    <span>250,000 – 500,000 t</span>
  </div>
  <div style='display: flex; align-items: center; gap: 8px;'>
    <div style='width: 20px; height: 20px; background-color: rgb(200,0,0); border: 1px solid #000'></div>
    <span>> 500,000 t</span>
  </div>
</div>
""", unsafe_allow_html=True)


# --- Stats & Table ---
st.subheader("📊 Country Statistics & Shipments")

import altair as alt

for destination in filtered['destination_brute'].dropna().unique():
    sub_df = filtered[filtered['destination_brute'] == destination]
    if not sub_df.empty:
        st.markdown(f"### {destination}")
        st.write(f"**⚖️ Total Volume (t)**: {sub_df['tonnage'].sum():,.0f}")

        # Regrouper par mois et sommer le tonnage
        sub_df['month'] = pd.to_datetime(sub_df['date_départ']).dt.to_period('M').dt.to_timestamp()
        monthly_tonnage = (
            sub_df
            .groupby('month')['tonnage']
            .sum()
            .reset_index()
            .sort_values('month')
        )

        # Afficher le graphique
        st.markdown("**📊 Monthly Total Tonnage**")
        chart = alt.Chart(monthly_tonnage).mark_bar(size=20).encode(
            x=alt.X('month:T', title='Month'),
            y=alt.Y('tonnage:Q', title='Total Tonnage'),
            tooltip=['month:T', 'tonnage']
        ).properties(height=300)

        st.altair_chart(chart, use_container_width=True)

        # Tableau des shipments
        st.markdown("**🧾 Shipment Details**")
        st.dataframe(
            sub_df[["date_départ", "navire", "port", "produit_brut", "tonnage", "shipper_brut"]]
            .sort_values(by="date_départ", ascending=False)
        )

