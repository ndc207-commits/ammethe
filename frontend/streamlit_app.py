import streamlit as st
import pandas as pd
import requests
import os

API_URL = os.getenv("API_URL", "https://quanlykho-backend1.onrender.com")

def api(method, endpoint, **kwargs):
    return requests.request(method, f"{API_URL}/{endpoint}", **kwargs).json()

@st.cache_data(ttl=30)
def fetch(ep):
    r = api("GET", ep)
    return pd.DataFrame(r) if isinstance(r, list) else pd.DataFrame()

st.title("📦 QUẢN LÝ KHO")

menu = st.sidebar.radio("Menu", [
    "Kho tổng",
    "Nhập/Xuất",
    "Chuyển kho",
    "Tìm kiếm",
    "Cảnh báo tồn kho",
    "Sửa/Xóa/Phục hồi",
    "Lịch sử",
    "Xuất Excel",
    "In PDF"
])

# ===== KHO =====
if menu == "Kho tổng":
    st.dataframe(fetch("inventory"), use_container_width=True)

# ===== NHẬP XUẤT =====
elif menu == "Nhập/Xuất":
    df_prod = fetch("products")
    df_wh = fetch("warehouses")

    sku = st.selectbox("Sản phẩm", df_prod["sku"] + " - " + df_prod["name"]).split(" - ")[0]
    wh = st.selectbox("Kho", df_wh["name"])
    wh_id = int(df_wh[df_wh["name"] == wh]["id"].values[0])

    t = st.radio("Loại", ["Nhập", "Xuất"])
    qty = st.number_input("Số lượng", 1)

    if st.button("OK"):
        res = api("POST", "transaction", json={
            "sku": sku,
            "type": t,
            "quantity": qty,
            "warehouse_id": wh_id
        })
        st.success(res)

# ===== TRANSFER =====
elif menu == "Chuyển kho":
    df_prod = fetch("products")
    df_wh = fetch("warehouses")

    sku = st.selectbox("Sản phẩm", df_prod["sku"] + " - " + df_prod["name"]).split(" - ")[0]

    fwh = st.selectbox("Từ kho", df_wh["name"])
    twh = st.selectbox("Đến kho", df_wh["name"])

    qty = st.number_input("Số lượng", 1)

    if st.button("Chuyển"):
        res = api("POST", "transfer", json={
            "sku": sku,
            "from_warehouse_id": int(df_wh[df_wh["name"]==fwh]["id"].values[0]),
            "to_warehouse_id": int(df_wh[df_wh["name"]==twh]["id"].values[0]),
            "quantity": qty
        })
        st.success(res)

# ===== SEARCH =====
elif menu == "Tìm kiếm":
    q = st.text_input("Tìm SKU / tên")
    if q:
        st.dataframe(fetch(f"products/search?q={q}"))

# ===== LOW STOCK =====
elif menu == "Cảnh báo tồn kho":
    t = st.number_input("Ngưỡng", 1, 100, 10)
    st.dataframe(fetch(f"inventory/low-stock?threshold={t}"))

# ===== CRUD =====
elif menu == "Sửa/Xóa/Phục hồi":
    df = fetch("products")

    active = df[df["is_active"] == True]
    deleted = df[df["is_active"] == False]

    st.subheader("Active")
    if not active.empty:
        sel = st.selectbox("Chọn", active["sku"] + " - " + active["name"])
        sku = sel.split(" - ")[0]

        name = st.text_input("Tên", active[active["sku"]==sku]["name"].values[0])

        if st.button("Update"):
            api("PUT", f"products/{sku}", json={"sku":sku,"name":name})
            st.success("OK")

        if st.button("Delete"):
            requests.delete(f"{API_URL}/products/{sku}")
            st.success("Deleted")

    st.subheader("Deleted")
    if not deleted.empty:
        sel2 = st.selectbox("Recover", deleted["sku"] + " - " + deleted["name"], key="r")
        sku2 = sel2.split(" - ")[0]

        if st.button("Recover"):
            requests.post(f"{API_URL}/products/{sku2}/recover")
            st.success("Recovered")

# ===== HISTORY =====
elif menu == "Lịch sử":
    st.dataframe(fetch("history"), use_container_width=True)

# ===== EXPORT EXCEL =====
elif menu == "Xuất Excel":
    df = fetch("history")

    if not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"])

    if st.button("Export"):
        file = "history.xlsx"
        with pd.ExcelWriter(file, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)

        with open(file, "rb") as f:
            st.download_button("Download", f, file_name=file)

# ===== PDF =====
elif menu == "In PDF":
    df_prod = fetch("products")

    sku = st.selectbox("Sản phẩm", df_prod["sku"] + " - " + df_prod["name"]).split(" - ")[0]
    qty = st.number_input("Số lượng", 1)
    t = st.selectbox("Loại", ["Nhập", "Xuất"])

    if st.button("Tạo PDF"):
        url = f"{API_URL}/invoice/pdf?sku={sku}&qty={qty}&type={t}"
        st.markdown(f"[Download PDF]({url})")
