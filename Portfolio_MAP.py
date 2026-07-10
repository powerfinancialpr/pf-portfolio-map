 
import folium
import geopandas as gpd
import pandas as pd
from folium.plugins import FastMarkerCluster
from branca.element import MacroElement
from jinja2 import Template
 
import tkinter as tk
from tkinter import filedialog

root = tk.Tk()
root.withdraw()
PORTFOLIO_PATH = filedialog.askopenfilename(title = 'Select a File')
if PORTFOLIO_PATH:
    print(f"User selected: {PORTFOLIO_PATH}")
else:
    print("No file was selected")
portfolio = pd.read_csv(PORTFOLIO_PATH, encoding='utf-8-sig')
 
portfolio['latitude'] = pd.to_numeric(portfolio['latitude'], errors='coerce')
portfolio['longitude'] = pd.to_numeric(portfolio['longitude'], errors='coerce')
portfolio['installation_date'] = pd.to_datetime(portfolio['installation_date'], errors='coerce')
 
portfolio_geo = portfolio.dropna(subset=['latitude', 'longitude']).copy()
 
# ==========================================
#         Municipality Border Mode
# ==========================================
municipalities = gpd.read_file('/Users/briansalazar/Documents/Power_Financial/tl_2025_us_county/tl_2025_us_county.shp')
municipalities = municipalities[municipalities['STATEFP'] == '72']
municipalities = municipalities.to_crs(epsg=4326)
 
map_center = [municipalities.geometry.centroid.y.mean(), municipalities.geometry.centroid.x.mean()]
 
# ------------------------------------------------------------------
# KEY FIX: don't trust the raw 'installation_city' text field for
# grouping (it's full of typos, accent variants, and junk values
# like zip codes / "PR" / "UNSPECIFIED"). Instead, use each record's
# actual lat/lon and a spatial join to find which municipio polygon
# it truly falls inside. This can't be thrown off by misspellings.
# ------------------------------------------------------------------
portfolio_points = gpd.GeoDataFrame(
    portfolio_geo,
    geometry=gpd.points_from_xy(portfolio_geo['longitude'], portfolio_geo['latitude']),
    crs='EPSG:4326',
)
 
joined = gpd.sjoin(
    portfolio_points,
    municipalities[['NAME', 'geometry']],
    how='left',
    predicate='within',
)
 
unmatched_points = joined[joined['NAME'].isna()]
if len(unmatched_points):
    print(f"{len(unmatched_points)} installations fell outside any municipio polygon (likely bad coordinates):")
    print(unmatched_points[['installation_city', 'latitude', 'longitude']])
 
municipality_info = (
    joined.dropna(subset=['NAME'])
    .groupby('NAME')
    .agg(**{
        'Average Cost': ('amount', 'mean'),
        'Average System Size': ('system_size', 'mean'),
        'Average Credit Score': ('credit_score', 'mean'),
        'Number of Installations': ('NAME', 'size'),
    })
    .reset_index()
    .rename(columns={'NAME': 'Municipality'})
)
 
# credit score color association
def credit_score_color(score):
    if score is None or pd.isna(score):
        return '#999999'  # grey
    elif score > 731.8:
        return '#115e38'  # dark green 
    elif score > 727.0:
        return '#5aed99'  # light green 
    elif score > 722.4:
        return '#ffe605'  # yellow 
    elif score > 714.0:
        return '#e6710b'  # orange 
    else:
        return '#ba2922'  # red 
 
municipalities = municipalities.merge(
    municipality_info,
    left_on='NAME',
    right_on='Municipality',
    how='left',
)
 
# debugging
unmatched = municipalities[municipalities['Average Cost'].isna()]
print(unmatched[['NAME']])
 
m = folium.Map(location=map_center, zoom_start=10, tiles=None)
 
folium.TileLayer(
    tiles='CartoDB positron',
    name='Power Financial Statistics',
    control=True,
).add_to(m)
 
folium.GeoJson(
    municipalities,
    name='Municipality Border Mode',  # title of toggle
    zoom_on_click=True,  # zooms into municipality on click
    show=False,  # defaults to hidden when opening
    style_function=lambda feature: {  # default appearance
        'fillColor': credit_score_color(feature['properties']['Average Credit Score']),
        'color': 'blue',
        'weight': 1.5,
    },
    highlight_function=lambda feature: {  # hover appearance
        'fillColor': credit_score_color(feature['properties']['Average Credit Score']),
        'color': 'black',
        'weight': 3,
        'fillOpacity': 0.5,
    },
    highlight=True,  # allows hover highlight
    tooltip=folium.GeoJsonTooltip(fields=['NAME'], aliases=['Municipality:']),
    popup=folium.GeoJsonPopup(
        fields=[
            'NAME',
            'Average Cost',
            'Average System Size',
            'Average Credit Score',
            'Number of Installations',
        ],
        aliases=[
            'Municipality',
            'Average Cost',
            'Average System Size',
            'Average Credit Score',
            'Number of Installations',
        ],
        localize=True,
        labels=True,
    ),
).add_to(m)
 
# ==========================================
#          Coordinate Cluster Mode
# ==========================================
coordinates = portfolio_geo[['latitude', 'longitude']].values.tolist()
 
fg_coords = folium.FeatureGroup(name="Coordinate Cluster Mode", show=False).add_to(m)
FastMarkerCluster(data=coordinates).add_to(fg_coords)
fg_coords.add_to(m)
 
# ==========================================
#                Bubble mode
# ==========================================
# KEY FIX: installation_zip_code has ~25 malformed entries (e.g.
# "00062-3", "0063", "00") that would otherwise form spurious
# 1-record groups. Extract a clean 5-digit zip before grouping.
clean_zip = (
    portfolio_geo['installation_zip_code']
    .astype(str)
    .str.extract(r'(\d{2,5})')[0]
    .str.zfill(5)
)
portfolio_geo = portfolio_geo.assign(clean_zip=clean_zip)
 
zip_summary = (
    portfolio_geo.groupby('clean_zip')
    .agg(**{
        'Centroid Latitude': ('latitude', 'mean'),
        'Centroid Longitude': ('longitude', 'mean'),
        'Average System Size': ('system_size', 'mean'),
    })
    .reset_index()
)
 
bubbles = zip_summary[['Centroid Latitude', 'Centroid Longitude', 'Average System Size']].values.tolist()
avg_system_size_list = zip_summary['Average System Size'].tolist()
min_size = min(avg_system_size_list)
max_size = max(avg_system_size_list)
 
max_radius = 50
min_radius = 10
def scaled_radius(size, max_size, min_size, max_radius, min_radius):
    if max_size == min_size:
        return (max_radius + min_radius) / 2
    fraction = (size - min_size) / (max_size - min_size)
    return min_radius + (max_radius - min_radius) * (fraction ** 0.5)
 
fg_bubbles = folium.FeatureGroup(name="Bubble Mode", show=False).add_to(m)
 
for lat, lon, size in bubbles:
    radius = scaled_radius(size, max_size, min_size, max_radius, min_radius)
    folium.CircleMarker(
        location=[lat, lon],
        radius=radius,
        color='#2b6cb0',
        weight=1,
        fill=True,
        fill_color='#4299e1',
        fill_opacity=0.6,
        tooltip=f"Avg system size: {size:,.0f}",
    ).add_to(fg_bubbles)
 
fg_bubbles.add_to(m)
 
# ==========================================
#              TimeLapse Mode
# ==========================================
timelapse_df = portfolio_geo.dropna(subset=['installation_date'])
 
features = []
for _, row in timelapse_df.iterrows():
    features.append({
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [row['longitude'], row['latitude']],
        },
        'properties': {
            'time': row['installation_date'].strftime('%Y-%m-%d'),
            'style': {'color': '#2b6cb0'},
            'icon': 'circle',
            'iconstyle': {
                'fillColor': '#4299e1',
                'fillOpacity': 0.7,
                'stroke': 'true',
                'radius': 6,
            },
        },
    })
 
geojson_data = {
    'type': 'FeatureCollection',
    'features': features,
}
 
fg_timelapse = folium.FeatureGroup(name="Installation Timelapse Mode", show=False).add_to(m)
 
ts_geojson = folium.plugins.TimestampedGeoJson(
    geojson_data,
    period='P1D',
    duration='P5Y',
    transition_time=100,
    auto_play=False,
    loop=False,
)
ts_geojson.add_to(m)
 
 
class TimestampedGroupFix(MacroElement):
    def __init__(self, feature_group, timestamped_plugin):
        super(TimestampedGroupFix, self).__init__()
        self._feature_group = feature_group
        self._timestamped_plugin = timestamped_plugin
        self._template = Template("""
            {% macro script(this, kwargs) %}
            {{ this._feature_group.get_name() }}.on('add', function(){
                {{ this._timestamped_plugin.get_name() }}.onAdd({{ this._feature_group._parent.get_name() }});
                {{ this._feature_group._parent.get_name() }}.addControl(timeDimensionControl);
            });
            {{ this._feature_group.get_name() }}.on('remove', function(){
                {{ this._timestamped_plugin.get_name() }}.onRemove({{ this._feature_group._parent.get_name() }});
                {{ this._feature_group._parent.get_name() }}.removeControl(timeDimensionControl);
            });
            // Initial state cleanup since show=False
            {{ this._timestamped_plugin.get_name() }}.onRemove({{ this._feature_group._parent.get_name() }});
            {{ this._feature_group._parent.get_name() }}.removeControl(timeDimensionControl);
            {% endmacro %}
        """)
 
 
m.add_child(TimestampedGroupFix(fg_timelapse, ts_geojson))
 
folium.LayerControl(collapsed=False).add_to(m)
 
m.save("map.html")
 
import os
import webbrowser
filepath = os.path.abspath("map.html")
webbrowser.open("file://" + filepath)
 
print(os.getcwd())
 