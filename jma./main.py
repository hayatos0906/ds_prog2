import flet as ft
import json
import requests

# 地域データを読み込む関数
def load_region_list():
    with open("jma./area.json", "r", encoding="utf-8") as file:
        return json.load(file)

# 地域データを階層的に整理
def parse_region_data(data):
    regions = {}
    for center_code, center_info in data["centers"].items():
        regions[center_code] = {
            "name": center_info["name"],
            "offices": {}
        }
        for office_code in center_info["children"]:
            if office_code in data["offices"]:
                regions[center_code]["offices"][office_code] = {
                    "name": data["offices"][office_code]["name"],
                    "class10s": {}
                }
                for class10_code in data["offices"][office_code]["children"]:
                    if class10_code in data["class10s"]:
                        regions[center_code]["offices"][office_code]["class10s"][class10_code] = {
                            "name": data["class10s"][class10_code]["name"],
                            "class15s": data["class10s"][class10_code].get("children", [])
                        }
    return regions

# 天気データ取得
def load_weather_data(region_code):
    url = f"https://www.jma.go.jp/bosai/forecast/data/forecast/{region_code}.json"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None

# 天気情報フォーマット
def format_weather_info(weather_data, area_name=None):
    weather_info_list = []
    try:
        # 天気予報と降水確率
        time_series = weather_data[0]["timeSeries"]
        
        # 天気予報
        weather_areas = time_series[0]["areas"]
        
        # 降水確率
        pops_areas = time_series[1]["areas"] if len(time_series) > 1 else []
        
        for area in weather_areas:
            if area_name and area["area"]["name"] != area_name:
                continue  # 指定された地域名と一致しない場合はスキップ
            area_name_in_data = area["area"]["name"]
            
            # 天気予報
            forecast = area["weathers"][0]
            
            # 降水確率を取得
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
    page.title = "詳細な天気予報"
    page.window_width = 1000
    page.window_height = 600

    data = load_region_list()
    regions = parse_region_data(data)

    # UI要素
    region_dropdown = ft.Dropdown(hint_text="地方を選択してください", options=[])
    prefecture_dropdown = ft.Dropdown(hint_text="県を選択してください", options=[])
    weather_info_column = ft.Column()

    # 地方が選択された時
    def on_region_selected(e):
        selected_region_code = region_dropdown.value
        prefecture_dropdown.options.clear()
        weather_info_column.controls.clear()

        if selected_region_code and selected_region_code in regions:
            # 県のドロップダウンを更新
            for office_code, office_info in regions[selected_region_code]["offices"].items():
                prefecture_dropdown.options.append(ft.dropdown.Option(office_code, text=office_info["name"]))

        prefecture_dropdown.value = None
        region_dropdown.update()
        prefecture_dropdown.update()
        weather_info_column.update()

    # 県が選択された時
    def on_prefecture_selected(e):
        selected_region_code = region_dropdown.value
        selected_prefecture_code = prefecture_dropdown.value
        weather_info_column.controls.clear()

        if selected_region_code and selected_prefecture_code and selected_region_code in regions:
            # 選択された県の天気情報を表示
            prefecture_info = regions[selected_region_code]["offices"][selected_prefecture_code]
            # 天気データを取得する
            weather_data = load_weather_data(selected_prefecture_code)
            prefecture_name = prefecture_info["name"]
            if weather_data:
                weather_texts = format_weather_info(weather_data)
                weather_info_column.controls.append(ft.Text(f"【{prefecture_name}の天気】", size=20, weight="bold"))
                for weather_text in weather_texts:
                    weather_info_column.controls.append(ft.Text(weather_text, size=16))
            else:
                weather_info_column.controls.append(ft.Text(f"{prefecture_name}の天気情報の取得に失敗しました。", size=16))

        weather_info_column.update()

    # イベントハンドラをドロップダウンに設定
    region_dropdown.on_change = on_region_selected
    prefecture_dropdown.on_change = on_prefecture_selected

    # 地方ドロップダウンにデータを設定
    for region_code, region_info in regions.items():
        region_dropdown.options.append(ft.dropdown.Option(region_code, text=region_info["name"]))

    # レイアウト
    page.add(
        ft.Column(
            controls=[
                ft.Text("詳細な天気予報", size=24, weight="bold"),
                ft.Row(
                    controls=[
                        ft.Column(
                            controls=[ft.Text("地方を選択:"), region_dropdown],
                            expand=1,
                        ),
                        ft.Column(
                            controls=[ft.Text("県を選択:"), prefecture_dropdown],
                            expand=1,
                        ),
                    ],
                ),
                ft.Text("天気情報", size=20, weight="bold"),
                weather_info_column,
            ],
            expand=True,
        )
    )

if __name__ == "__main__":
    ft.app(target=main)