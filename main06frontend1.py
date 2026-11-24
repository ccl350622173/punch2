from datetime import datetime
from urllib.parse import quote
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="打卡系統（前後端分離版）",
    page_icon="🏗️",
    layout="centered",
)

st.title("🏗️ 工地 / 辦公室 打卡（FastAPI + Streamlit）")

api_base_url = st.sidebar.text_input(
    "後端 FastAPI 位址",
    value="http://127.0.0.1:8000",
).rstrip("/")


def get_ip_location() -> dict:
    resp = requests.get(
        "https://ipapi.co/json/",
        headers={"User-Agent": "PunchFE/1.0"},
        timeout=6,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("latitude") is None or data.get("longitude") is None:
        raise RuntimeError("IP 定位未回傳經緯度")
    place = " / ".join(
        [x for x in [data.get("country_name"), data.get("region"), data.get("city")] if x]
    )
    return {
        "lat": float(data["latitude"]),
        "lng": float(data["longitude"]),
        "source": f"設備 IP ({place or '未知地區'})",
    }


if "loc" not in st.session_state:
    try:
        st.session_state.loc = get_ip_location()
    except Exception:
        st.session_state.loc = {"lat": None, "lng": None, "source": "未定位"}

if "last_result" not in st.session_state:
    st.session_state.last_result = None

qp = st.query_params
if "lat" in qp and "lng" in qp:
    try:
        lat_val = float(qp["lat"])
        lng_val = float(qp["lng"])
        st.session_state.loc = {
            "lat": lat_val,
            "lng": lng_val,
            "source": "裝置 GPS",
        }
        # 清除網址參數，避免後續手動切換 IP 定位或重新整理時被舊參數蓋掉
        st.query_params.clear()
    except ValueError:
        pass

loc = st.session_state.loc
if loc["lat"] is not None and loc["lng"] is not None:
    coord_text = f"{loc['lat']:.6f}, {loc['lng']:.6f}"
else:
    coord_text = "尚未取得"

st.info(
    f"目前時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}｜"
    f"座標：{coord_text}｜"
    f"來源：{loc['source']}"
)

gps_html = """
<div>
    <button onclick="reqGPS()" style="background:#1565C0;color:#fff;border:none;padding:8px 14px;border-radius:6px;cursor:pointer;">
        📡 嘗試 GPS 定位
    </button>
    <span id="gps_st" style="margin-left:8px;font-size:13px;"></span>
</div>
<script>
function reqGPS() {
    const s = document.getElementById("gps_st");
    if (!navigator.geolocation) {
        s.innerText = "不支援 GPS，請改用 IP 定位";
        return;
    }
    s.innerText = "定位中...";
    navigator.geolocation.getCurrentPosition(
        function(p) {
            try {
                const u = new URL(window.parent.location.href);
                u.searchParams.set("lat", p.coords.latitude.toFixed(6));
                u.searchParams.set("lng", p.coords.longitude.toFixed(6));
                window.parent.location.replace(u.toString());
            } catch (err) {
                s.innerText = "無法更新網址列座標：" + err.message;
            }
        },
        function(e) {
            s.innerText = "GPS 失敗：" + e.message;
        },
        { enableHighAccuracy: true, timeout: 6000, maximumAge: 0 }
    );
}
</script>
"""

c_gps, c_ip = st.columns([2, 1])
with c_gps:
    components.html(gps_html, height=45)
with c_ip:
    if st.button("🌐 改用設備 IP 定位", use_container_width=True):
        try:
            st.session_state.loc = get_ip_location()
            st.rerun()
        except Exception as e:
            st.error(f"IP 定位失敗：{e}")

if loc["lat"] is not None and loc["lng"] is not None:
    st.map(pd.DataFrame({"lat": [loc["lat"]], "lon": [loc["lng"]]}), zoom=14)

name = st.text_input("姓名 *")
phone = st.text_input("手機號碼")
site_type = st.radio("地點類別", ["工地", "辦公室"], horizontal=True)
site_name = st.text_input("工地 / 辦公室名稱")
work = st.text_area("施作內容（最多 100 字）", max_chars=100)


def submit_to_backend(p_type: str):
    if not name.strip():
        st.warning("請先輸入姓名")
        return
    req_body = {
        "punch_type": p_type,
        "name": name.strip(),
        "phone": phone.strip() or "未提供",
        "site_type": site_type,
        "site_name": site_name.strip() or "未填",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "lat": st.session_state.loc.get("lat"),
        "lng": st.session_state.loc.get("lng"),
        "source": st.session_state.loc.get("source", "未知"),
        "work": work.strip(),
    }
    try:
        r = requests.post(f"{api_base_url}/api/punch", json=req_body, timeout=8)
        r.raise_for_status()
        st.session_state.last_result = r.json()
        st.success(f"✅ {p_type}打卡已送達後端並儲存！")
    except Exception as e:
        st.error(f"❌ 呼叫後端 API 失敗：{e}")


b1, b2 = st.columns(2)
with b1:
    if st.button("🟢 上班打卡", type="primary", use_container_width=True):
        submit_to_backend("上班")
with b2:
    if st.button("🟠 下班打卡", use_container_width=True):
        submit_to_backend("下班")

if isinstance(st.session_state.last_result, dict):
    msg = st.session_state.last_result.get("formatted_message") or str(st.session_state.last_result)
    st.subheader("📤 打卡格式化訊息")
    st.code(msg, language="text")
    st.link_button(
        "💬 開啟 LINE 分享傳送",
        f"https://line.me/R/share?text={quote(msg)}",
        use_container_width=True,
    )

st.divider()
st.subheader("📋 後端打卡紀錄")
try:
    res = requests.get(f"{api_base_url}/api/records", params={"limit": 30}, timeout=6)
    res.raise_for_status()
    rows = res.json().get("records", [])
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("後端尚無打卡紀錄")
except Exception as e:
    st.warning(f"無法連線至後端讀取紀錄（請確認 FastAPI 是否已啟動）：{e}")