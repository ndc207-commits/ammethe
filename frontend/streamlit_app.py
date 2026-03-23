import streamlit as st
import pandas as pd
import requests
import os
from io import BytesIO
from reportlab.pdfgen import canvas

# ===== CONFIG =====
API_URL = os.getenv("API_URL", "https://quanlykho-backend1.onrender.com")

# ===== API HELPER =====
def api(method, endpoint, **kwargs):
    try:
        r = requests.request(method, f"{API_URL}/{endpoint}", **kwargs)
        if r.status_code in (200, 201):
            return r.json()
        st.error(f"API lỗi: {r.status_code}")
        return None
    except Exception as e:
        st.error(f"Lỗi kết nối API: {e}")
        return None

# ===== DATA HELPERS =====
def to_df(data):
    return pd.DataFrame(data) if data else pd.DataFrame()


def filter_active(df):
    if "is_active" in df.columns:
        return df[df["is_active"] == True]
    return df


def filter_deleted(df):
    if "is_active" in df.columns:
        return df[df["is_active"] == False]
    return pd.DataFrame()

# ===== UI HELPERS =====
def select_product(df, label="Chọn sản phẩm"):
    sel = st.selectbox(label, df["sku"] + " - " + df["name"])
    return sel.split(" - ")[0]


def get_warehouse_id(df_wh, name):
    return int(df_wh[df_wh["name"] == name]["id"].values[0])

# ===== MAIN =====
st.title("Quản lý kho")

menu = st.sidebar.radio("Menu", [
    "Kho tổng", "Nhập/Xuất", "Chuyển kho", "Sản phẩm", "Thêm sản phẩm",
    "Tìm kiếm", "Cảnh báo tồn kho", "Lịch sử", "PDF"
])

# ===== SẢN PHẨM =====
if menu == "Sản phẩm":
    df = to_df(api("GET", "products"))

    if df.empty:
        st.warning("Không có dữ liệu sản phẩm")
    else:
        df_active = filter_active(df)
        df_deleted = filter_deleted(df)

        st.subheader("🟢 Sản phẩm đang hoạt động")
        st.dataframe(df_active, use_container_width=True) if not df_active.empty else st.info("Chưa có sản phẩm")

        st.subheader("🔴 Sản phẩm đã xóa")
        if not df_deleted.empty:
            sku = select_product(df_deleted, "Chọn sản phẩm phục hồi")
            if st.button("♻️ Phục hồi"):
                api("POST", f"products/{sku}/recover")
                st.success("Đã phục hồi")
        else:
            st.info("Không có sản phẩm đã xóa")

        st.subheader("✏️ Sửa / 🗑 Xóa sản phẩm")
        if not df_active.empty:
            sku = select_product(df_active)
