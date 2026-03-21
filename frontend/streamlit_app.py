import streamlit as st
import pandas as pd
import requests
import os

API_URL = os.getenv("API_URL", "http://localhost:8000")

def api(method, endpoint, **kwargs):
    return requests.request(method, f"{API_URL}/{endpoint}", **kwargs).json()

@st.cache_data(ttl=30)
def fetch(endpoint):
    res = api("GET", endpoint)
    return pd.DataFrame(res) if isinstance(res, list) else pd.DataFrame()

st.title("📦 QUẢN LÝ KHO")

menu = st.sidebar.radio("Menu", [
    "Kho tổng",
    "Nhập/Xuất",
    "Chuyển kho",
    "Tìm kiếm",
    "Cảnh báo tồn kho",
    "In phiếu"
])

# ====== KHO ======
if menu == "Kho tổng":
    st.dataframe(fetch("inventory"), use_container_width=True)

# ====== NHẬP XUẤT ======
elif menu == "Nhập/Xuất":
    df_prod = fetch("products")
    df_wh = fetch("warehouses")

    sku = st.selectbox("Sản phẩm", df_prod["sku"] + " - " + df_prod["name"])
    sku = sku.split(" - ")[0]

    wh_name = st.selectbox("Kho", df_wh["name"])
    wh_id = int(df_wh[df_wh["name"] == wh_name]["id"].values[0])

    t = st.radio("Loại", ["Nhập", "Xuất"])
    qty = st.number_input("Số lượng", min_value=1)

    if st.button("Xác nhận"):
        res = api("POST", "transaction", json={
            "sku": sku,
            "type": t,
            "quantity": qty,
            "warehouse_id": wh_id
        })
        st.success(res)

# ====== TRANSFER ======
elif menu == "Chuyển kho":
    df_prod = fetch("products")
    df_wh = fetch("warehouses")

    sku = st.selectbox("Sản phẩm", df_prod["sku"] + " - " + df_prod["name"]).split(" - ")[0]

    from_wh = st.selectbox("Từ kho", df_wh["name"])
    to_wh = st.selectbox("Đến kho", df_wh["name"])

    qty = st.number_input("Số lượng", min_value=1)

    if st.button("Chuyển"):
        res = api("POST", "transfer", json={
            "sku": sku,
            "from_warehouse_id": int(df_wh[df_wh["name"]==from_wh]["id"].values[0]),
            "to_warehouse_id": int(df_wh[df_wh["name"]==to_wh]["id"].values[0]),
            "quantity": qty
        })
        st.success(res)

# ====== SEARCH ======
elif menu == "Tìm kiếm":
    q = st.text_input("Tìm SKU / tên")
    if q:
        df = fetch(f"products/search?q={q}")
        st.dataframe(df)

# ====== LOW STOCK ======
elif menu == "Cảnh báo tồn kho":
    threshold = st.number_input("Ngưỡng", 1, 100, 10)
    df = fetch(f"inventory/low-stock?threshold={threshold}")

    if df.empty:
        st.success("OK")
    else:
        st.dataframe(df)

# ====== PDF ======
elif menu == "In phiếu":
    df_prod = fetch("products")

    sku = st.selectbox("Sản phẩm", df_prod["sku"] + " - " + df_prod["name"]).split(" - ")[0]
    qty = st.number_input("Số lượng", min_value=1)
    t = st.selectbox("Loại", ["Nhập", "Xuất"])

    if st.button("Tạo PDF"):
        url = f"{API_URL}/invoice/pdf?sku={sku}&qty={qty}&type={t}"
        st.markdown(f"[Download PDF]({url})")
