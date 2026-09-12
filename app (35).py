import os
import math
from datetime import datetime

import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

st.set_page_config(
    page_title="関西空間インデックス - Buffer Grid", layout="wide"
)

st.title("🛡️ 関西サバイバル・空間インデックス (Buffer Grid)")
st.markdown(
    "行政・インフラの空白地帯を突く、住民自衛のための「安全な空間・リスク」目録"
)

DB_PATH = os.path.join(os.path.dirname(__file__), "buffer_grid_db.csv")

COLUMNS = [
    "name", "lat", "lon", "type", "region", "desc",
    "operator", "total_units", "vacant_units", "risk_level",
    "structure_note", "last_updated",
]

# --- 1. 関西広域の初期データ（UR団地ストック ＆ 都市型リスク） ---
initial_data = [
    {
        "name": "UR千里津雲台団地（大阪・吹田）",
        "lat": 34.8030, "lon": 135.5350,
        "type": "避難バッファ", "region": "大阪市内・近郊",
        "desc": "大規模な棟間隔と高台の構造。北千里・南千里エリアの堅固な一時退避拠点候補。",
        "operator": "UR都市機構", "total_units": 1200, "vacant_units": 85,
        "risk_level": "低", "structure_note": "RC造・高台",
    },
    {
        "name": "UR金剛団地（大阪・富田林）",
        "lat": 34.5050, "lon": 135.5750,
        "type": "避難バッファ", "region": "大阪市内・近郊",
        "desc": "圧倒的な戸数とストックを持つ巨大団地。南大阪エリアの防災ハブとして機能。",
        "operator": "UR都市機構", "total_units": 5600, "vacant_units": 340,
        "risk_level": "低", "structure_note": "RC造・丘陵地",
    },
    {
        "name": "UR清和台・多聞台・鈴蘭台エリア（兵庫）",
        "lat": 34.8500, "lon": 135.4100,
        "type": "避難バッファ", "region": "兵庫・阪神間",
        "desc": "川西・神戸北側の高台に位置する安定した丘陵団地。水害リスクを完全に回避。",
        "operator": "UR都市機構", "total_units": 3100, "vacant_units": 210,
        "risk_level": "低", "structure_note": "RC造・高台",
    },
    {
        "name": "UR平城団地 / 中登美団地（奈良）",
        "lat": 34.7000, "lon": 135.7800,
        "type": "避難バッファ", "region": "奈良エリア",
        "desc": "高の原・学研奈良登美ヶ丘周辺の堅固なニュータウンストック。地盤リスク極小。",
        "operator": "UR都市機構", "total_units": 2400, "vacant_units": 150,
        "risk_level": "低", "structure_note": "RC造・台地",
    },
    {
        "name": "住之江・南港周辺（大阪ゼロメートル低地）",
        "lat": 34.6100, "lon": 135.4500,
        "type": "水害リスク", "region": "大阪市内・近郊",
        "desc": "抽水所停止・排水不良時に内水氾濫とマンホール噴出が懸念される高リスク帯。",
        "operator": "-", "total_units": 0, "vacant_units": 0,
        "risk_level": "高", "structure_note": "ゼロメートル地帯",
    },
    {
        "name": "淀川・大和川下流域の密集市街地",
        "lat": 34.6800, "lon": 135.4700,
        "type": "衛生リスク", "region": "大阪市内・近郊",
        "desc": "インフラ停止・ゴミ処理逼迫時に二次汚染と環境悪化が直撃する脆弱エリア。",
        "operator": "-", "total_units": 0, "vacant_units": 0,
        "risk_level": "中", "structure_note": "密集市街地",
    },
]


def load_db() -> pd.DataFrame:
    """CSVファイルからDBを読み込む。なければ初期データで新規作成する。"""
    if os.path.exists(DB_PATH):
        return pd.read_csv(DB_PATH)
    df = pd.DataFrame(initial_data)
    df["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    df.to_csv(DB_PATH, index=False)
    return df


def save_db(df: pd.DataFrame) -> None:
    df.to_csv(DB_PATH, index=False)


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """2地点間の距離を km で計算（避難候補の近さ判定に使用）"""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


if "df_index" not in st.session_state:
    st.session_state.df_index = load_db()

df_all = st.session_state.df_index

# --- 2. サイドバー：フィルター機能 ---
st.sidebar.header("🔍 インデックス絞り込み")
selected_region = st.sidebar.selectbox(
    "エリア選択",
    ["すべて", "大阪市内・近郊", "兵庫・阪神間", "奈良エリア", "その他"],
)
selected_type = st.sidebar.selectbox(
    "種別選択", ["すべて", "避難バッファ", "水害リスク", "衛生リスク"]
)
only_vacant = st.sidebar.checkbox("空き戸数ありのバッファのみ表示", value=False)

st.sidebar.divider()
st.sidebar.metric("登録総数", f"{len(df_all)} 件")
st.sidebar.metric("高リスク地点数", f"{(df_all['risk_level'] == '高').sum()} 件")
st.sidebar.metric(
    "空き戸数の合計（バッファ）",
    f"{int(df_all.loc[df_all['type'] == '避難バッファ', 'vacant_units'].sum())} 戸",
)

# データのフィルタリング
df_filtered = df_all
if selected_region != "すべて":
    df_filtered = df_filtered[df_filtered["region"] == selected_region]
if selected_type != "すべて":
    df_filtered = df_filtered[df_filtered["type"] == selected_type]
if only_vacant:
    df_filtered = df_filtered[
        (df_filtered["type"] != "避難バッファ") | (df_filtered["vacant_units"] > 0)
    ]

# --- 3. メイン画面：マップ ＆ 一覧の2カラムレイアウト ---
col_map, col_list = st.columns([3, 2])

with col_map:
    st.subheader("📍 空間インデックス・マップ")

    if selected_region == "兵庫・阪神間":
        center = [34.83, 135.41]
    elif selected_region == "奈良エリア":
        center = [34.69, 135.78]
    elif selected_region == "大阪市内・近郊":
        center = [34.68, 135.50]
    else:
        center = [34.72, 135.55]

    m = folium.Map(location=center, zoom_start=10)

    for _, row in df_filtered.iterrows():
        color = (
            "green" if "バッファ" in row["type"]
            else ("red" if "水害" in row["type"] else "orange")
        )
        if row["type"] == "避難バッファ":
            extra = f"<br><b>運営:</b> {row['operator']}<br><b>空き戸数:</b> {row['vacant_units']} / {row['total_units']}戸"
        else:
            extra = f"<br><b>リスク度:</b> {row['risk_level']}"
        popup_html = (
            f"<b>{row['name']}</b><br><b>種別:</b> {row['type']}"
            f"<br><b>エリア:</b> {row['region']}<br>{row['desc']}{extra}"
        )
        folium.Marker(
            location=[row["lat"], row["lon"]],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=row["name"],
            icon=folium.Icon(color=color, icon="info-sign"),
        ).add_to(m)

    st_folium(m, width=550, height=450)

with col_list:
    st.subheader("📋 登録スペース・リスク一覧")
    st.markdown(f"該当件数: **{len(df_filtered)}件**")
    for _, row in df_filtered.iterrows():
        badge_color = (
            "🟢" if "バッファ" in row["type"]
            else ("🔴" if "水害" in row["type"] else "🟠")
        )
        with st.expander(f"{badge_color} {row['name']}"):
            st.write(f"**エリア:** {row['region']}")
            st.write(f"**種別:** {row['type']}")
            st.write(f"**詳細:** {row['desc']}")
            if row["type"] == "避難バッファ":
                st.write(f"**運営主体:** {row['operator']}")
                st.write(f"**総戸数:** {row['total_units']} 戸")
                st.write(f"**空き戸数:** {row['vacant_units']} 戸")
                st.write(f"**構造:** {row['structure_note']}")
            else:
                st.write(f"**リスク度:** {row['risk_level']}")
            st.caption(f"最終更新: {row.get('last_updated', '-')}")
            st.caption(f"緯度: {row['lat']} / 経度: {row['lon']}")

# --- 4. 高リスク地点 → 避難バッファ候補の自動マッチング ---
st.divider()
st.subheader("🧭 高リスク地点 × 最寄り避難バッファ 候補マッチング")
st.markdown("各リスク地点から直線距離が近い順に、空き戸数のあるバッファ候補を提示します。")

risk_rows = df_all[df_all["type"] != "避難バッファ"]
buffer_rows = df_all[(df_all["type"] == "避難バッファ") & (df_all["vacant_units"] > 0)]

if risk_rows.empty or buffer_rows.empty:
    st.info("マッチングに必要なリスク地点またはバッファ情報がまだ十分ではありません。")
else:
    for _, risk in risk_rows.iterrows():
        distances = buffer_rows.copy()
        distances["distance_km"] = distances.apply(
            lambda b: haversine_km(risk["lat"], risk["lon"], b["lat"], b["lon"]), axis=1
        )
        top3 = distances.sort_values("distance_km").head(3)

        badge = "🔴" if risk["risk_level"] == "高" else "🟠"
        st.markdown(f"**{badge} {risk['name']}**（リスク度: {risk['risk_level']}）")
        cols = st.columns(len(top3))
        for col, (_, cand) in zip(cols, top3.iterrows()):
            with col:
                st.write(f"🟢 {cand['name']}")
                st.caption(f"距離: 約 {cand['distance_km']:.1f} km")
                st.caption(f"空き戸数: {cand['vacant_units']} / {cand['total_units']} 戸")

# --- 5. 新規空間インデックスの追加登録フォーム ---
st.divider()
st.subheader("📝 新しい「空間インデックス・リスク」の追加登録")
st.markdown(
    "現地やネットで見つけたURの空き棟・気になる団地ストック、あるいは新たな危険箇所をここから即座に追加できます。"
    "登録内容はCSVファイルに保存され、アプリを再起動しても消えません。"
)

with st.form("add_index_form"):
    c1, c2, c3 = st.columns(3)
    with c1:
        in_name = st.text_input("名称（例: 〇〇団地 □号棟ストック / 〇〇の冠水注意地点）")
        in_type = st.selectbox("種別", ["避難バッファ", "水害リスク", "衛生リスク"])
        in_region = st.selectbox("エリア", ["大阪市内・近郊", "兵庫・阪神間", "奈良エリア", "その他"])
    with c2:
        in_desc = st.text_input("簡単な説明・メモ")
        in_operator = st.text_input("運営主体（UR/府営/民間など。リスク地点は空欄でOK）")
        in_structure = st.text_input("構造・特記事項（例: RC造・高台）")
    with c3:
        in_lat = st.number_input("緯度 (Latitude)", value=34.8400, format="%.4f")
        in_lon = st.number_input("経度 (Longitude)", value=135.4200, format="%.4f")
        in_total_units = st.number_input("総戸数（バッファのみ）", min_value=0, value=0, step=1)
        in_vacant_units = st.number_input("空き戸数（バッファのみ）", min_value=0, value=0, step=1)
        in_risk_level = st.selectbox("リスク度（リスク地点のみ）", ["低", "中", "高"])

    submitted = st.form_submit_button("インデックスに追加する")

    if submitted and in_name:
        new_entry = pd.DataFrame([{
            "name": in_name,
            "lat": in_lat,
            "lon": in_lon,
            "type": in_type,
            "region": in_region,
            "desc": in_desc,
            "operator": in_operator if in_operator else "-",
            "total_units": in_total_units,
            "vacant_units": in_vacant_units,
            "risk_level": in_risk_level,
            "structure_note": in_structure,
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
        }])
        st.session_state.df_index = pd.concat(
            [st.session_state.df_index, new_entry], ignore_index=True
        )
        save_db(st.session_state.df_index)
        st.success(f"【追加成功】空間インデックスに「{in_name}」を登録しました！")
        st.rerun()
