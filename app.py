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
    "structure_note", "osaka_district", "last_updated",
]

# 大阪府営住宅の「地区」ごとの浸水リスクの目安。
# 大阪府公式の「洪水リスク表示図」(https://www.river.pref.osaka.jp/) による
# 数値解析ではなく、地形（高台か低地か）や過去の水害記録に基づく参考情報です。
# 実際の避難判断には、必ず公式のハザードマップを確認してください。
OSAKA_DISTRICT_RISK = [
    {"district": "堺市（南区）", "risk_level": "低", "risk_rank": 1,
     "reason": "泉北丘陵地帯に位置し、ニュータウンも高台に造成されている。"},
    {"district": "北摂西", "risk_level": "低", "risk_rank": 2,
     "reason": "千里丘陵など台地部分が多く、歴史的に「高台」とされるエリア。"},
    {"district": "泉州南部", "risk_level": "中", "risk_rank": 3,
     "reason": "丘陵地と沿岸部が混在。北部よりは内陸側に高台が多い。"},
    {"district": "泉州北部", "risk_level": "中", "risk_rank": 4,
     "reason": "沿岸の平地が中心で、高潮リスクも想定されている。"},
    {"district": "北摂東", "risk_level": "中", "risk_rank": 5,
     "reason": "高槻市街地北側は丘陵だが、摂津市や高槻南部は淀川・安威川沿いの低地。"},
    {"district": "堺市（南区を除く）", "risk_level": "高", "risk_rank": 6,
     "reason": "大和川・石津川沿いの低地。高潮浸水想定区域も含む。"},
    {"district": "北河内", "risk_level": "高", "risk_rank": 7,
     "reason": "大阪府内で最も知られた水害常襲地帯。「寝屋川流域総合治水対策」の対象エリア。"},
]

# --- 1. 関西広域の初期データ（UR団地ストック ＆ 都市型リスク） ---
initial_data = [
    {
        "name": "UR千里津雲台団地（大阪・吹田）",
        "lat": 34.8030, "lon": 135.5350,
        "type": "避難バッファ", "region": "大阪市内・近郊",
        "desc": "大規模な棟間隔と高台の構造。北千里・南千里エリアの堅固な一時退避拠点候補。",
        "operator": "UR都市機構", "total_units": 1200, "vacant_units": 85,
        "risk_level": "低", "structure_note": "RC造・高台", "osaka_district": "",
    },
    {
        "name": "UR金剛団地（大阪・富田林）",
        "lat": 34.5050, "lon": 135.5750,
        "type": "避難バッファ", "region": "大阪市内・近郊",
        "desc": "圧倒的な戸数とストックを持つ巨大団地。南大阪エリアの防災ハブとして機能。",
        "operator": "UR都市機構", "total_units": 5600, "vacant_units": 340,
        "risk_level": "低", "structure_note": "RC造・丘陵地", "osaka_district": "",
    },
    {
        "name": "UR清和台・多聞台・鈴蘭台エリア（兵庫）",
        "lat": 34.8500, "lon": 135.4100,
        "type": "避難バッファ", "region": "兵庫・阪神間",
        "desc": "川西・神戸北側の高台に位置する安定した丘陵団地。水害リスクを完全に回避。",
        "operator": "UR都市機構", "total_units": 3100, "vacant_units": 210,
        "risk_level": "低", "structure_note": "RC造・高台", "osaka_district": "",
    },
    {
        "name": "UR平城団地 / 中登美団地（奈良）",
        "lat": 34.7000, "lon": 135.7800,
        "type": "避難バッファ", "region": "奈良エリア",
        "desc": "高の原・学研奈良登美ヶ丘周辺の堅固なニュータウンストック。地盤リスク極小。",
        "operator": "UR都市機構", "total_units": 2400, "vacant_units": 150,
        "risk_level": "低", "structure_note": "RC造・台地", "osaka_district": "",
    },
    {
        "name": "住之江・南港周辺（大阪ゼロメートル低地）",
        "lat": 34.6100, "lon": 135.4500,
        "type": "水害リスク", "region": "大阪市内・近郊",
        "desc": "抽水所停止・排水不良時に内水氾濫とマンホール噴出が懸念される高リスク帯。",
        "operator": "-", "total_units": 0, "vacant_units": 0,
        "risk_level": "高", "structure_note": "ゼロメートル地帯", "osaka_district": "",
    },
    {
        "name": "淀川・大和川下流域の密集市街地",
        "lat": 34.6800, "lon": 135.4700,
        "type": "衛生リスク", "region": "大阪市内・近郊",
        "desc": "インフラ停止・ゴミ処理逼迫時に二次汚染と環境悪化が直撃する脆弱エリア。",
        "operator": "-", "total_units": 0, "vacant_units": 0,
        "risk_level": "中", "structure_note": "密集市街地", "osaka_district": "",
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


DISTRICT_RISK_MAP = {d["district"]: d for d in OSAKA_DISTRICT_RISK}


def district_risk_badge(district: str) -> str:
    """osaka_districtから浸水リスクのバッジ文字列を返す（未設定なら空文字）"""
    info = DISTRICT_RISK_MAP.get(district)
    if not info:
        return ""
    icon = {"低": "🟩", "中": "🟨", "高": "🟥"}.get(info["risk_level"], "")
    return f"{icon} 浸水リスク目安: {info['risk_level']}（{district}）"


if "df_index" not in st.session_state:
    df_loaded = load_db()
    # 古いCSVに osaka_district 列がない場合に備えて補完
    if "osaka_district" not in df_loaded.columns:
        df_loaded["osaka_district"] = ""
    st.session_state.df_index = df_loaded

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

# --- 2.5 エリア別 浸水リスクの目安（大阪府営住宅の地区区分） ---
st.divider()
with st.expander("🌊 エリア別 浸水リスクの目安（大阪府営住宅の地区区分）", expanded=False):
    st.markdown(
        "大阪府営住宅の「地区」区分ごとに、地形（高台か低地か）と過去の水害記録をもとにした"
        "**リスクの目安**です。大阪府公式の浸水シミュレーション数値ではありません。"
        "実際の避難判断には、必ず下記の公式サイトで最新のハザードマップを確認してください。"
    )
    risk_df = pd.DataFrame(OSAKA_DISTRICT_RISK).sort_values("risk_rank")
    for _, r in risk_df.iterrows():
        icon = {"低": "🟩", "中": "🟨", "高": "🟥"}.get(r["risk_level"], "")
        st.markdown(f"{icon} **{r['district']}**（目安: {r['risk_level']}） — {r['reason']}")
    st.caption(
        "出典・詳細確認: 大阪府 洪水リスク表示図 https://www.river.pref.osaka.jp/"
    )

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
        district_badge = district_risk_badge(row.get("osaka_district", ""))
        if district_badge:
            extra += f"<br>{district_badge}"
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
            district_badge = district_risk_badge(row.get("osaka_district", ""))
            if district_badge:
                st.caption(district_badge)
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

# --- 5. CSV/Excel 一括インポート機能 ---
st.divider()
st.subheader("📥 空室情報の一括インポート")
st.markdown(
    "URサイトで調べた空室情報や、自治体が公開している府営・県営住宅の募集情報を"
    "Excelにまとめたものを、一気に取り込めます。まずテンプレートをダウンロードして、"
    "同じ列構成でデータを埋めてからアップロードしてください。"
)

template_df = pd.DataFrame([{
    "name": "（例）UR〇〇団地 第2期",
    "lat": 34.7000,
    "lon": 135.5000,
    "type": "避難バッファ",
    "region": "大阪市内・近郊",
    "desc": "簡単な説明",
    "operator": "UR都市機構",
    "total_units": 500,
    "vacant_units": 20,
    "risk_level": "低",
    "structure_note": "RC造・高台",
    "osaka_district": "北摂西",
}])

col_dl, col_up = st.columns(2)

with col_dl:
    st.download_button(
        label="📄 テンプレートCSVをダウンロード",
        data=template_df.to_csv(index=False).encode("utf-8-sig"),
        file_name="buffer_grid_template.csv",
        mime="text/csv",
    )
    st.caption(
        "type列は「避難バッファ」「水害リスク」「衛生リスク」のいずれか、"
        "region列は「大阪市内・近郊」「兵庫・阪神間」「奈良エリア」「その他」のいずれかで入力してください。"
    )
    st.caption(
        "osaka_district列（任意）に「北摂西」「北摂東」「北河内」「堺市（南区）」"
        "「堺市（南区を除く）」「泉州北部」「泉州南部」のいずれかを入れると、"
        "浸水リスクの目安バッジが自動で表示されます（大阪府営住宅のみ対象）。"
    )

with col_up:
    uploaded_file = st.file_uploader(
        "記入済みのCSVまたはExcelファイルをアップロード", type=["csv", "xlsx"]
    )

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith(".xlsx"):
            new_rows = pd.read_excel(uploaded_file)
        else:
            new_rows = pd.read_csv(uploaded_file)

        optional_cols = {"last_updated", "osaka_district"}
        missing_cols = [c for c in COLUMNS if c not in new_rows.columns and c not in optional_cols]
        if missing_cols:
            st.error(f"次の列が見つかりません。テンプレートと同じ列名にしてください: {missing_cols}")
        else:
            if "osaka_district" not in new_rows.columns:
                new_rows["osaka_district"] = ""
            new_rows = new_rows[[c for c in COLUMNS if c != "last_updated"]].copy()
            new_rows["last_updated"] = datetime.now().strftime("%Y-%m-%d")

            st.markdown(f"**プレビュー（{len(new_rows)}件）**")
            st.dataframe(new_rows, use_container_width=True)

            if st.button("✅ この内容をインデックスに一括登録する"):
                st.session_state.df_index = pd.concat(
                    [st.session_state.df_index, new_rows], ignore_index=True
                )
                save_db(st.session_state.df_index)
                st.success(f"{len(new_rows)}件を一括登録しました！")
                st.rerun()
    except Exception as e:
        st.error(f"読み込み中にエラーが発生しました: {e}")

# --- 6. 新規空間インデックスの追加登録フォーム ---
st.divider()
st.subheader("📝 新しい「空間インデックス・リスク」の個別登録")
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
        in_osaka_district = st.selectbox(
            "大阪府営住宅の地区（任意・浸水リスク目安バッジ表示用）",
            ["該当なし"] + [d["district"] for d in OSAKA_DISTRICT_RISK],
        )
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
            "osaka_district": "" if in_osaka_district == "該当なし" else in_osaka_district,
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
        }])
        st.session_state.df_index = pd.concat(
            [st.session_state.df_index, new_entry], ignore_index=True
        )
        save_db(st.session_state.df_index)
        st.success(f"【追加成功】空間インデックスに「{in_name}」を登録しました！")
        st.rerun()
