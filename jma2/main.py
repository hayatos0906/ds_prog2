import flet as ft
import requests
import sqlite3
import json
import os
import sys
import datetime
import threading

# スクリプトのディレクトリを取得
BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))

# データベースとJSONファイルのパスを指定（相対パスに変更）
DB_FILE = os.path.join(BASE_DIR, "area.db")
AREA_JSON_FILE = os.path.join(BASE_DIR, "area.json")

# データベースのセットアップ
def setup_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # 地域とオフィスのテーブルを作成
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS regions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS offices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region_code TEXT NOT NULL,
            office_code TEXT NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY (region_code) REFERENCES regions (code)
        )
    ''')

    # 天気予報データを保存するテーブルを作成
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weather_forecasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            office_code TEXT NOT NULL,
            area_name TEXT NOT NULL,
            forecast_date TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            weather TEXT,
            pop TEXT,
            UNIQUE(office_code, area_name, forecast_date, time_slot)
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
        # 重複を避けるためにチェック
        if not cursor.execute('SELECT 1 FROM regions WHERE code = ?', (region_code,)).fetchone():
            regions.append((region_code, region_name))

        # 地方に属するオフィスのコードリストを取得
        office_codes = region_info.get('children', [])
        for office_code in office_codes:
            office_info = offices_data.get(office_code, {})
            office_name = office_info.get('name', '')
            # 重複を避けるためにチェック
            if not cursor.execute('SELECT 1 FROM offices WHERE office_code = ?', (office_code,)).fetchone():
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
def fetch_and_store_weather_data(office_code):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    url = f"https://www.jma.go.jp/bosai/forecast/data/forecast/{office_code}.json"
    response = requests.get(url)
    if response.status_code == 200:
        weather_data = response.json()
        store_weather_data(conn, office_code, weather_data)
    else:
        print(f"Failed to fetch data for office_code: {office_code}")

    conn.close()

def store_weather_data(conn, office_code, weather_data):
    cursor = conn.cursor()
    for forecast in weather_data:
        time_series = forecast.get('timeSeries', [])
        for series in time_series:
            time_defines = series.get('timeDefines', [])
            areas = series.get('areas', [])
            for area in areas:
                area_name = area.get('area', {}).get('name', '')
                weathers = area.get('weathers', [])
                pops = area.get('pops', [])
                for i in range(len(time_defines)):
                    forecast_date = datetime.datetime.strptime(time_defines[i], "%Y-%m-%dT%H:%M:%S%z")
                    date_str = forecast_date.strftime('%Y-%m-%d')
                    time_slot = forecast_date.strftime('%H:%M')
                    weather = weathers[i] if i < len(weathers) else ''
                    pop = pops[i] if i < len(pops) else ''
                    cursor.execute('''
                        INSERT OR REPLACE INTO weather_forecasts
                        (office_code, area_name, forecast_date, time_slot, weather, pop)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (office_code, area_name, date_str, time_slot, weather, pop))
    conn.commit()

# データベースから天気情報を取得
def get_weather_info_from_db(office_code):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT area_name, forecast_date, time_slot, weather, pop
        FROM weather_forecasts
        WHERE office_code = ?
        ORDER BY area_name, forecast_date, time_slot
    ''', (office_code,))
    results = cursor.fetchall()
    conn.close()
    return results

# 天気情報フォーマット
def format_weather_info_from_db(weather_data):
    weather_info_list = []
    current_area = ''
    for row in weather_data:
        area_name, forecast_date, time_slot, weather, pop = row
        if current_area != area_name:
            weather_info_list.append(f"【{area_name}】")
            current_area = area_name
        weather_info = f"{forecast_date} {time_slot}\n天気: {weather}\n降水確率: {pop}%\n"
        weather_info_list.append(weather_info)
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
            prefecture_name = prefecture_info["name"]

            # 天気データがデータベースに存在するかチェック
            weather_data = get_weather_info_from_db(selected_prefecture_code)

            if not weather_data:
                # 存在しない場合はデータを取得して保存
                def fetch_data_and_update():
                    fetch_and_store_weather_data(selected_prefecture_code)
                    # データ取得後に再度データベースから読み込む
                    weather_data_fetched = get_weather_info_from_db(selected_prefecture_code)
                    if weather_data_fetched:
                        weather_texts = format_weather_info_from_db(weather_data_fetched)
                        # メインスレッドでUIを更新
                        page.controls[-1].controls[-1].controls.append(ft.Text(f"【{prefecture_name}の天気】", size=20, weight="bold"))
                        for weather_text in weather_texts:
                            page.controls[-1].controls[-1].controls.append(ft.Text(weather_text, size=16))
                        page.update()
                    else:
                        page.controls[-1].controls[-1].controls.append(ft.Text(f"{prefecture_name}の天気情報の取得に失敗しました。", size=16))
                        page.update()
                # バックグラウンドでデータ取得
                threading.Thread(target=fetch_data_and_update, daemon=True).start()
                # データ取得中のメッセージを表示
                weather_info_column.controls.append(ft.Text("天気情報を取得しています...", size=16))
            else:
                weather_texts = format_weather_info_from_db(weather_data)
                weather_info_column.controls.append(ft.Text(f"【{prefecture_name}の天気】", size=20, weight="bold"))
                for weather_text in weather_texts:
                    weather_info_column.controls.append(ft.Text(weather_text, size=16))

            weather_info_column.update()
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
                ft.Column(
                    controls=[
                        weather_info_column
                    ],
                    scroll="adaptive",
                    expand=True,
                ),
            ],
            expand=True,
        )
    )

if __name__ == "__main__":
    ft.app(target=main)