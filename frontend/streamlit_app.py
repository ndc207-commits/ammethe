import streamlit as st
import pandas as pd
import requests
import os
from io import BytesIO
from reportlab.pdfgen import canvas

# ===== CONFIG =====
API_URL = os.getenv("API_URL", "https://quanlykho-backend1.onrender.com")
st.set_page_config(page_title="Quản lý kho", layout="wide")

# ===== API =====
@st.cache_data(ttl=5)
def api_get(endpoint):
    try:
        r = requests.get(f"{API_URL}/{endpoint}")
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

def api_post(endpoint, payload=None):
    try:
        requests.post(f"{API_URL}/{endpoint}", json=payload)
    except:
        st.error("Lỗi API")

def api_put(endpoint, payload=None):
    try:
        requests.put(f"{API_URL}/{endpoint}", json=payload)
    except:
        st.error("Lỗi API")

def api_delete(endpoint):
    try:
        requests.delete(f"{API_URL}/{endpoint}")
    except:
        st.error("Lỗi API")

# ===== HELPERS =====
def to_df(data):
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data)

def safe_df(df, cols):
    if df.empty:
        return False
    for c in cols:
        if c not in df.columns:
            return False
    return True

def filter_active(df):
    if "is_active" in df.columns:
        return df[df["is_active"] == True]
    return df

def show_df(df, msg):
    if df.empty:
        st.info(msg)
    else:
        st.dataframe(df, use_container_width=True)

# ===== UI =====
st.title("📦 Quản lý kho")

menu = st.sidebar.radio("Menu", [
    "Kho tổng", "Nhập/Xuất", "Chuyển kho",
    "Sản phẩm", "Thêm sản phẩm",
    "Cảnh báo tồn kho",
    "Lịch sử", "PDF"
])

# ===== SẢN PHẨM =====
if menu == "Sản phẩm":
    df = to_df(api_get("products"))

    if not safe_df(df, ["sku","name"]):
        st.warning("API products lỗi hoặc không có dữ liệu")
        st.stop()

    df_active = filter_active(df)
    df_deleted = df[df["is_active"] == False] if "is_active" in df.columns else pd.DataFrame()

    st.subheader("🟢 Hoạt động")
    show_df(df_active, "Chưa có sản phẩm")

    st.subheader("🔴 Đã xóa")
    if not df_deleted.empty:
        sel = st.selectbox("Phục hồi", df_deleted["sku"] + " - " + df_deleted["name"])
        sku = sel.split(" - ")[0]
        if st.button("Phục hồi"):
            api_post(f"products/{sku}/recover")
            st.rerun()
    else:
        st.info("Không có")

# ===== NHẬP/XUẤT =====
elif menu == "Nhập/Xuất":
    df_prod = filter_active(to_df(api_get("products")))
    df_wh = to_df(api_get("warehouses"))

    if not safe_df(df_prod, ["sku","name"]) or not safe_df(df_wh, ["id","name"]):
        st.warning("Thiếu dữ liệu products hoặc warehouses")
        st.stop()

    sel = st.selectbox("Sản phẩm", df_prod["sku"] + " - " + df_prod["name"])
    sku = sel.split(" - ")[0]

    wh = st.selectbox("Kho", df_wh["name"])
    wh_id = int(df_wh[df_wh["name"] == wh]["id"].values[0])

    t = st.radio("Loại", ["Nhập", "Xuất"])
    qty = st.number_input("Số lượng", 1)

    if st.button("OK"):
        api_post("transaction", {
            "sku": sku,
            "type": t,
            "quantity": qty,
            "warehouse_id": wh_id
        })
        st.success("Thành công")

# ===== CHUYỂN KHO =====
elif menu == "Chuyển kho":
    df_prod = filter_active(to_df(api_get("products")))
    df_wh = to_df(api_get("warehouses"))

    if not safe_df(df_prod, ["sku","name"]) or not safe_df(df_wh, ["id","name"]):
        st.warning("Thiếu dữ liệu")
        st.stop()

    sel = st.selectbox("Sản phẩm", df_prod["sku"] + " - " + df_prod["name"])
    sku = sel.split(" - ")[0]

    wh_from = st.selectbox("Từ", df_wh["name"], key="from")
    wh_to = st.selectbox("Đến", df_wh["name"], key="to")

    qty = st.number_input("Số lượng", 1)

    if st.button("Chuyển"):
        if wh_from == wh_to:
            st.warning("Kho phải khác nhau")
        else:
            id_from = int(df_wh[df_wh["name"] == wh_from]["id"].values[0])
            id_to = int(df_wh[df_wh["name"] == wh_to]["id"].values[0])

            api_post("transaction", {"sku": sku, "type": "Xuất", "quantity": qty, "warehouse_id": id_from})
            api_post("transaction", {"sku": sku, "type": "Nhập", "quantity": qty, "warehouse_id": id_to})

            st.success("Đã chuyển")

# ===== CẢNH BÁO =====
elif menu=="Cảnh báo tồn kho":
    threshold = st.number_input("Ngưỡng tồn kho", min_value=1, value=10)
    df = api("GET", "inventory")  # Gọi toàn bộ inventory
    if df:
        df = pd.DataFrame(df)
        low_stock = df[df["quantity"] < threshold]  # Lọc tồn kho thấp
        if not low_stock.empty:
            st.dataframe(low_stock)
        else:
            st.success("Không có sản phẩm nào dưới ngưỡng tồn kho.")

# ===== LỊCH SỬ =====
elif menu == "Lịch sử":
    df = to_df(api_get("history"))
    show_df(df, "Không có dữ liệu")

# ===== PDF =====
elif menu == "PDF":
    df = filter_active(to_df(api_get("products")))

    if not safe_df(df, ["sku","name"]):
        st.warning("Không có sản phẩm")
        st.stop()

    sel = st.selectbox("Sản phẩm", df["sku"] + " - " + df["name"])
    sku = sel.split(" - ")[0]

    qty = st.number_input("Qty", 1)
    t = st.selectbox("Type", ["Nhập","Xuất"])

    if st.button("Tạo PDF"):
        buffer = BytesIO()
        c = canvas.Canvas(buffer)
        c.drawString(100, 800, f"PHIẾU {t}")
        c.drawString(100, 780, f"SKU: {sku}")
        c.drawString(100, 760, f"Số lượng: {qty}")
        c.drawString(100, 740, pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'))
        c.save()
        buffer.seek(0)

        st.download_button("Download", buffer, f"{sku}.pdf")
