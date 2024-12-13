import flet as ft
import requests
import sqlite3
import json
import os
import sys

# スクリプトのディレクトリを取得
BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))

# データベースとJSONファイルのパスを指定（相対パスに変更）
DB_FILE = os.path.join(BASE_DIR, "area.db")
AREA_JSON_FILE = os.path.join(BASE_DIR, "area.json")

# データベースのセットアップ
def setup_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 既存のテーブルを削除
    cursor.execute('DROP TABLE IF EXISTS offices')
    cursor.execute('DROP TABLE IF EXISTS regions')
    
    # 新しいテーブルを作成
    cursor.execute('''
        CREATE TABLE regions (
            id INTEGER PRIMARY KEY,
            code TEXT NOT NULL,
            name TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE offices (
            id INTEGER PRIMARY KEY,
            region_code TEXT NOT NULL,
            office_code TEXT NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY (region_code) REFERENCES regions (code)
        )
    ''')
    return conn, cursor

# データをインポート
def import_data(cursor):
    # area.jsonからデータを読み込む
    if not os.path.exists(AREA_JSON_FILE):
        print(f"{AREA_JSON_FILE} が見つかりません。")
        return

    with open(AREA_JSON_FILE, 'r', encoding='utf-8') as f:
        area_data = json.load(f)

    # 地方データとオフィスデータを挿入
    regions = []
    offices = []

    centers = area_data.get('centers', {})
    offices_data = area_data.get('offices', {})

    for region_code, region_info in centers.items():
        region_name = region_info['name']
        print(f"Adding region: {region_code} - {region_name}")
        regions.append((region_code, region_name))

        # 地方に属するオフィスのコードリストを取得
        office_codes = region_info.get('children', [])
        for office_code in office_codes:
            office_info = offices_data.get(office_code, {})
            office_name = office_info.get('name', '')
            print(f"  Adding office: {office_code} - {office_name}")
            offices.append((region_code, office_code, office_name))

    # データベースに挿入
    cursor.executemany('INSERT INTO regions (code, name) VALUES (?, ?)', regions)
    cursor.executemany('INSERT INTO offices (region_code, office_code, name) VALUES (?, ?, ?)', offices)

# データベースから地方リストを読み込む
def load_region_list_from_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT code, name FROM regions')
    regions = {row[0]: {"name": row[1], "offices": {}} for row in cursor.fetchall()}
    cursor.execute('SELECT region_code, office_code, name FROM offices')
    for row in cursor.fetchall():
        regions[row[0]]["offices"][row[1]] = {"name": row[2]}
    conn.close()
    return regions

# 天気データ取得
def load_weather_data(office_code):
    url = f"https://www.jma.go.jp/bosai/forecast/data/forecast/{office_code}.json"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None

# 天気情報フォーマット
def format_weather_info(weather_data, area_name=None):
    weather_info_list = []
    try:
        time_series = weather_data[0]["timeSeries"]
        weather_areas = time_series[0]["areas"]
        pops_areas = time_series[1]["areas"] if len(time_series) > 1 else []

        for area in weather_areas:
            if area_name and area["area"]["name"] != area_name:
                continue
            area_name_in_data = area["area"]["name"]
            forecast = area["weathers"][0]
            pop = "N/A"
            for pop_area in pops_areas:
                if pop_area["area"]["name"] == area_name_in_data:
                    pops = pop_area.get("pops", ["N/A"])
                    pop = ', '.join(pops) + '%'
                    break
            weather_info = f"【{area_name_in_data}】\n天気予報: {forecast}\n降水確率: {pop}\n"
            weather_info_list.append(weather_info)
    except (IndexError, KeyError, TypeError, ValueError) as e:
        weather_info_list.append(f"天気情報の取得に失敗しました。({e})")
    return weather_info_list

# メインアプリケーション
def main(page: ft.Page):
    page.title = "天気予報アプリ"
    page.window_width = 1000
    page.window_height = 600

    # データベースのセットアップとデータのインポート
    conn, cursor = setup_database()
    import_data(cursor)
    conn.commit()
    conn.close()

    regions = load_region_list_from_db()

    region_dropdown = ft.Dropdown(hint_text="地方を選択してください", options=[])
    prefecture_dropdown = ft.Dropdown(hint_text="府県を選択してください", options=[])
    weather_info_column = ft.Column()

    def on_region_selected(e):
        selected_region_code = region_dropdown.value
        prefecture_dropdown.options.clear()
        weather_info_column.controls.clear()

        if selected_region_code and selected_region_code in regions:
            for office_code, office_info in regions[selected_region_code]["offices"].items():
                prefecture_dropdown.options.append(ft.dropdown.Option(office_code, text=office_info["name"]))

        prefecture_dropdown.value = None
        prefecture_dropdown.update()
        weather_info_column.update()

    def on_prefecture_selected(e):
        selected_region_code = region_dropdown.value
        selected_prefecture_code = prefecture_dropdown.value
        weather_info_column.controls.clear()

        if selected_region_code and selected_prefecture_code and selected_region_code in regions:
            prefecture_info = regions[selected_region_code]["offices"][selected_prefecture_code]
            weather_data = load_weather_data(selected_prefecture_code)
            prefecture_name = prefecture_info["name"]
            if weather_data:
                weather_texts = format_weather_info(weather_data)
                weather_info_column.controls.append(ft.Text(f"【{prefecture_name}の天気】", size=20, weight="bold"))
                for weather_text in weather_texts:
                    weather_info_column.controls.append(ft.Text(weather_text, size=16))
            else:
                weather_info_column.controls.append(ft.Text(f"{prefecture_name}の天気情報の取得に失敗しました。", size=16))
        else:
            weather_info_column.controls.append(ft.Text("天気情報を取得できませんでした。", size=16))

        weather_info_column.update()

    region_dropdown.on_change = on_region_selected
    prefecture_dropdown.on_change = on_prefecture_selected

    for region_code, region_info in regions.items():
        region_dropdown.options.append(ft.dropdown.Option(region_code, text=region_info["name"]))

    page.add(
        ft.Column(
            controls=[
                ft.Text("天気予報アプリ", size=24, weight="bold"),
                ft.Row(
                    controls=[
                        ft.Column(
                            controls=[ft.Text("地方を選択:"), region_dropdown],
                            expand=1,
                        ),
                        ft.Column(
                            controls=[ft.Text("府県を選択:"), prefecture_dropdown],
                            expand=1,
                        ),
                    ],
                ),
                weather_info_column,
            ],
            expand=True,
        )
    )

if __name__ == "__main__":
    ft.app(target=main)