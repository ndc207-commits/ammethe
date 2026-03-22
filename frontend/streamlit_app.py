import streamlit as st
import pandas as pd
import requests
import os
import time

API_URL = os.getenv("API_URL", "https://quanlykho-backend1.onrender.com")

def api(method, endpoint, **kwargs):
    try:
        r = requests.request(method, f"{API_URL}/{endpoint}", **kwargs)
        if r.status_code == 200:
            return r.json()
        return []
    except:
        return []

@st.cache_data(ttl=30)
def fetch(ep):
    r = api("GET", ep)
    return pd.DataFrame(r) if isinstance(r, list) else pd.DataFrame()

st.title("📦 QUẢN LÝ KHO")

menu = st.sidebar.radio("Menu", [
    "Kho tổng",
    "Nhập/Xuất",
    "Chuyển kho",
    "Sản phẩm",
    "Thêm sản phẩm",
    "Tìm kiếm",
    "Cảnh báo tồn kho",
    "Lịch sử",
    "PDF"
])

WAREHOUSE_LIST = ["La Pagode", "Muse", "Metz Ville", "Nancy"]

# ===== KHO =====
if menu == "Kho tổng":
    df = fetch("inventory")

    tabs = st.tabs(WAREHOUSE_LIST)

    col_name = None
    if not df.empty:
        col_name = "warehouse" if "warehouse" in df.columns else None

    for i, wh in enumerate(WAREHOUSE_LIST):
        with tabs[i]:
            st.subheader(f"Kho: {wh}")
            if df.empty or col_name is None:
                st.warning("Không có dữ liệu")
            else:
                st.dataframe(df[df[col_name] == wh], use_container_width=True)

# ===== NHẬP XUẤT =====
elif menu == "Nhập/Xuất":
    df_prod = fetch("products")
    df_wh = fetch("warehouses")

    if "is_active" in df_prod.columns:
        df_prod = df_prod[df_prod["is_active"] == True]

    if df_prod.empty or df_wh.empty:
        st.warning("Không có dữ liệu")
    else:
        options = df_prod["sku"] + " - " + df_prod["name"]

        selected = st.selectbox("Sản phẩm", options)

        if selected:
            sku = selected.split(" - ")[0]

            wh = st.selectbox("Kho", df_wh["name"])
            wh_id = int(df_wh[df_wh["name"] == wh]["id"].values[0])

            t = st.radio("Loại", ["Nhập", "Xuất"])
            qty = st.number_input("Số lượng", 1)

            if st.button("OK"):
                api("POST", "transaction", json={
                    "sku": sku,
                    "type": t,
                    "quantity": qty,
                    "warehouse_id": wh_id
                })
                st.success("OK")
                st.cache_data.clear()
                st.rerun()

# ===== CHUYỂN KHO =====
elif menu == "Chuyển kho":
    df_prod = fetch("products")
    df_wh = fetch("warehouses")

    if "is_active" in df_prod.columns:
        df_prod = df_prod[df_prod["is_active"] == True]

    if df_prod.empty or df_wh.empty:
        st.warning("Không có dữ liệu")
    else:
        options = df_prod["sku"] + " - " + df_prod["name"]
        selected = st.selectbox("Sản phẩm", options)

        if selected:
            sku = selected.split(" - ")[0]

            from_wh = st.selectbox("Từ kho", df_wh["name"])
            to_wh = st.selectbox("Đến kho", df_wh["name"])

            qty = st.number_input("Số lượng", 1)

            if st.button("Chuyển"):
                res = api("POST", "transfer", json={
                    "sku": sku,
                    "from_warehouse_id": int(df_wh[df_wh["name"] == from_wh]["id"].values[0]),
                    "to_warehouse_id": int(df_wh[df_wh["name"] == to_wh]["id"].values[0]),
                    "quantity": qty
                })
                st.success("OK")
                st.cache_data.clear()
                st.rerun()

# ===== THÊM SẢN PHẨM =====
elif menu == "Thêm sản phẩm":
    st.subheader("➕ Thêm sản phẩm mới")

    sku = st.text_input("SKU")
    name = st.text_input("Tên sản phẩm")

    if st.button("Thêm"):
        if not sku or not name:
            st.warning("⚠️ Nhập đầy đủ thông tin")
        else:
            res = requests.post(f"{API_URL}/products", json={
                "sku": sku,
                "name": name
            })

            if res.status_code == 200:
                st.success("✅ Thêm thành công")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(f"Lỗi: {res.text}")

# ===== PDF =====
elif menu == "PDF":
    df_prod = fetch("products")

    if "is_active" in df_prod.columns:
        df_prod = df_prod[df_prod["is_active"] == True]

    if not df_prod.empty:
        options = df_prod["sku"] + " - " + df_prod["name"]
        selected = st.selectbox("Sản phẩm", options)

        if selected:
            sku = selected.split(" - ")[0]

            qty = st.number_input("Qty", 1)
            t = st.selectbox("Type", ["Nhập", "Xuất"])

            if st.button("Download"):
                url = f"{API_URL}/invoice/pdf?sku={sku}&qty={qty}&type={t}"
                st.markdown(f"[Download PDF]({url})")
