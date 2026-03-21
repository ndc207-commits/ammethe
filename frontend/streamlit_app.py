# streamlit_app.py
import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# ====== CẤU HÌNH API ======
import os

API_URL = os.getenv("API_URL", "https://quanlykho-backend1.onrender.com")

# ====== CACHE DATA ======
# ====== HÀM FETCH AN TOÀN ======
def safe_fetch(endpoint: str, params: dict = None, timeout: int = 5):
    """
    Gọi API và trả về pd.DataFrame an toàn.
    - Nếu API trả về JSON hợp lệ list/dict, chuyển sang DataFrame
    - Nếu lỗi (timeout, connection, JSONDecodeError), trả về DataFrame rỗng
    """
    try:
        response = requests.get(f"{API_URL}/{endpoint}", params=params or {}, timeout=timeout)
        response.raise_for_status()
        try:
            data = response.json()
            if not isinstance(data, (list, dict)):
                # nếu API trả về string hoặc HTML
                st.warning(f"API {endpoint} trả dữ liệu không chuẩn: {data}")
                data = []
        except ValueError:
            st.warning(f"Không thể parse JSON từ {endpoint}: {response.text[:200]}")
            data = []
    except requests.exceptions.RequestException as e:
        st.warning(f"Lỗi khi gọi API {endpoint}: {e}")
        data = []
    return pd.DataFrame(data)


# ====== HÀM FETCH RIÊNG ======
@st.cache_data(ttl=30)
def fetch_products(active=True):
    df = safe_fetch("products")
    if not df.empty and "is_active" in df.columns:
        df = df[df["is_active"] == active].copy()
    return df

@st.cache_data(ttl=30)
def fetch_inventory():
    return safe_fetch("inventory")

@st.cache_data(ttl=30)
def fetch_store_inventory():
    return safe_fetch("store_inventory")

@st.cache_data(ttl=30)
def fetch_history(limit=200):
    return safe_fetch("history", params={"limit": limit})

# ====== UI ======
st.title("📦 Quản lý kho AMME THE")
menu = st.sidebar.radio("Menu", [
    "Dashboard", "Kho tổng", "Kho cửa hàng",
    "Thêm sản phẩm", "Sửa/Xóa/Phục hồi",
    "Nhập/Xuất", "Lịch sử", "Xuất Excel"
])

# ====== DASHBOARD ======
if menu=="Dashboard":
    st.subheader("📊 Kho tổng")
    df_stock = fetch_inventory()
    if not df_stock.empty:
        st.bar_chart(df_stock.groupby("name")["quantity"].sum())
    st.subheader("🏬 Kho cửa hàng")
    df_store = fetch_store_inventory()
    if not df_store.empty:
        st.bar_chart(df_store.groupby("store")["quantity"].sum())

# ====== KHO TỔNG ======
elif menu=="Kho tổng":
    st.subheader("📦 Tồn kho tổng")
    df_stock = fetch_inventory()
    st.dataframe(df_stock, use_container_width=True)

# ====== KHO CỬA HÀNG ======
elif menu=="Kho cửa hàng":
    st.subheader("🏬 Tồn kho cửa hàng")
    df_store = fetch_store_inventory()
    st.dataframe(df_store, use_container_width=True)

# ====== THÊM SẢN PHẨM ======
elif menu=="Thêm sản phẩm":
    st.subheader("➕ Thêm sản phẩm mới")
    sku = st.text_input("SKU")
    name = st.text_input("Tên sản phẩm")
    if st.button("Thêm sản phẩm"):
        res = requests.post(f"{API_URL}/products/add", json={"sku":sku,"name":name})
        st.success(res.json()["msg"])
        st.cache_data.clear()

# ====== SỬA / XÓA / PHỤC HỒI ======
elif menu=="Sửa/Xóa/Phục hồi":
    st.subheader("✏️ Sửa / 🗑 Xóa / ♻️ Phục hồi sản phẩm")
    df_active = fetch_products(active=True)
    df_deleted = fetch_products(active=False)

    # Chọn sản phẩm đang active
    if not df_active.empty:
        sel_active = st.selectbox("Chọn sản phẩm để sửa/xóa", df_active["sku"] + " - " + df_active["name"])
        sku = sel_active.split(" - ")[0]
        new_name = st.text_input("Tên mới", df_active[df_active["sku"]==sku]["name"].values[0])
        if st.button("Cập nhật tên"):
            requests.post(f"{API_URL}/products/update", json={"sku":sku,"name":new_name})
            st.success("Đã cập nhật tên")
            st.cache_data.clear()
        if st.button("Xóa sản phẩm"):
            requests.post(f"{API_URL}/products/delete", json={"sku":sku})
            st.success("Đã xóa sản phẩm")
            st.cache_data.clear()

    # Phục hồi sản phẩm đã xóa
    if not df_deleted.empty:
        sel_deleted = st.selectbox("Chọn sản phẩm phục hồi", df_deleted["sku"] + " - " + df_deleted["name"])
        sku_recover = sel_deleted.split(" - ")[0]
        if st.button("Phục hồi sản phẩm"):
            requests.post(f"{API_URL}/products/recover", json={"sku":sku_recover})
            st.success("Đã phục hồi sản phẩm")
            st.cache_data.clear()

# ====== NHẬP / XUẤT ======
elif menu=="Nhập/Xuất":
    st.subheader("📥 Nhập / 📤 Xuất kho")
    df_prod = fetch_products()
    sku = st.selectbox("Chọn sản phẩm", df_prod["sku"] + " - " + df_prod["name"]).split(" - ")[0]

    df_stock = fetch_inventory()
    wh_list = df_stock["name"].unique() if not df_stock.empty else ["Kho 1"]
    wh = st.selectbox("Chọn kho", wh_list)

    tx_type = st.radio("Loại giao dịch", ["Nhập","Xuất"])
    qty = st.number_input("Số lượng", min_value=1)

    store_id = None
    if tx_type=="Xuất":
        df_store = fetch_store_inventory()
        store_list = df_store["store"].unique() if not df_store.empty else ["Cửa hàng 1"]
        store_name = st.selectbox("Chọn cửa hàng nhận hàng", store_list)
        # Giả sử mapping store -> id: chỉ cần thêm API lấy id nếu cần
        store_id = df_store[df_store["store"]==store_name]["store"].index[0]

    if st.button("Xác nhận giao dịch"):
        payload = {"sku":sku,"type":tx_type,"quantity":qty,"warehouse_id":1,"store_id":store_id}
        res = requests.post(f"{API_URL}/transaction", json=payload)
        if res.status_code==200:
            st.success("✅ Hoàn tất giao dịch")
            st.cache_data.clear()
        else:
            st.error(res.json()["detail"])

# ====== LỊCH SỬ ======
elif menu=="Lịch sử":
    st.subheader("📜 Lịch sử giao dịch")
    df_hist = fetch_history()
    st.dataframe(df_hist, use_container_width=True)

# ====== XUẤT EXCEL ======
elif menu=="Xuất Excel":
    st.subheader("📥 Xuất Excel lịch sử")
    df_hist = fetch_history(limit=1000)
    if st.button("Tải Excel"):
        df_hist.to_excel("history.xlsx", index=False)
        with open("history.xlsx","rb") as f:
            st.download_button("Tải xuống", f, file_name="history.xlsx")

