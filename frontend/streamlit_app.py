import streamlit as st
import pandas as pd
import requests
import os

# ====== CONFIG ======
API_URL = os.getenv("API_URL", "https://quanlykho-backend1.onrender.com")

# ====== API CLIENT ======
def api_request(method, endpoint, params=None, json=None):
    url = f"{API_URL}/{endpoint}"

    headers = {}
    if "token" in st.session_state:
        headers["Authorization"] = f"Bearer {st.session_state.token}"

    try:
        res = requests.request(
            method=method,
            url=url,
            params=params,
            json=json,
            headers=headers,
            timeout=10
        )

        if res.status_code >= 400:
            return {"error": res.text}

        try:
            return res.json()
        except:
            return {}

    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

# ====== FETCH ======
@st.cache_data(ttl=30)
def fetch_products():
    res = api_request("GET", "products")
    return pd.DataFrame(res) if isinstance(res, list) else pd.DataFrame()

@st.cache_data(ttl=30)
def fetch_inventory():
    res = api_request("GET", "inventory")
    return pd.DataFrame(res) if isinstance(res, list) else pd.DataFrame()

@st.cache_data(ttl=30)
def fetch_store_inventory():
    res = api_request("GET", "store_inventory")
    return pd.DataFrame(res) if isinstance(res, list) else pd.DataFrame()

@st.cache_data(ttl=30)
def fetch_history(limit=200):
    res = api_request("GET", "history", params={"limit": limit})
    return pd.DataFrame(res) if isinstance(res, list) else pd.DataFrame()

# ====== LOGIN ======
if "token" not in st.session_state:
    st.title("🔐 Đăng nhập")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        res = requests.post(f"{API_URL}/login", params={
            "username": username,
            "password": password
        }).json()

        if "access_token" in res:
            st.session_state.token = res["access_token"]
            st.success("Đăng nhập thành công")
            st.rerun()
        else:
            st.error("Sai tài khoản hoặc mật khẩu")

    st.stop()

# ====== UI ======
st.title("📦 Quản lý kho AMME THE")

menu = st.sidebar.radio("Menu", [
    "Dashboard", "Kho tổng", "Kho cửa hàng",
    "Thêm sản phẩm", "Sửa/Xóa/Phục hồi",
    "Nhập/Xuất", "Lịch sử", "Xuất Excel"
])

# ====== DASHBOARD ======
if menu == "Dashboard":
    st.subheader("📊 Dashboard")

    df_stock = fetch_inventory()
    df_store = fetch_store_inventory()

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Tổng SKU", len(fetch_products()))
        st.metric("Tồn kho dòng", df_stock["quantity"].sum() if not df_stock.empty else 0)

    with col2:
        st.metric("Kho cửa hàng", df_store["quantity"].sum() if not df_store.empty else 0)

    if not df_stock.empty:
        st.bar_chart(df_stock.groupby("name")["quantity"].sum())

# ====== KHO TỔNG ======
elif menu == "Kho tổng":
    st.subheader("📦 Tồn kho tổng")
    st.dataframe(fetch_inventory(), use_container_width=True)

# ====== KHO CỬA HÀNG ======
elif menu == "Kho cửa hàng":
    st.subheader("🏬 Tồn kho cửa hàng")
    st.dataframe(fetch_store_inventory(), use_container_width=True)

# ====== THÊM SẢN PHẨM ======
elif menu == "Thêm sản phẩm":
    st.subheader("➕ Thêm sản phẩm")

    sku = st.text_input("SKU")
    name = st.text_input("Tên sản phẩm")

    if st.button("Thêm"):
        res = api_request("POST", "products", json={"sku": sku, "name": name})

        if "msg" in res:
            st.success(res["msg"])
            st.cache_data.clear()
        else:
            st.error(res.get("error", "Lỗi"))

# ====== SỬA / XÓA / PHỤC HỒI ======
elif menu == "Sửa/Xóa/Phục hồi":
    st.subheader("✏️ Quản lý sản phẩm")

    df = fetch_products()

    if df.empty:
        st.warning("Không có sản phẩm")
    else:
        for i, row in df.iterrows():
            col1, col2, col3, col4 = st.columns([2,3,2,3])

            with col1:
                st.write(row["sku"])

            with col2:
                st.write(row["name"])

            with col3:
                st.write("🟢" if row["is_active"] else "🔴")

            with col4:
                if row["is_active"]:
                    if st.button("🗑 Xóa", key=f"del_{i}"):
                        res = api_request("DELETE", f"products/{row['sku']}")
                        st.success(res.get("msg", "Đã xóa"))
                        st.cache_data.clear()
                        st.rerun()

                    if st.button("✏️ Sửa", key=f"edit_{i}"):
                        new_name = st.text_input("Tên mới", value=row["name"], key=f"name_{i}")

                        if st.button("💾 Lưu", key=f"save_{i}"):
                            res = api_request("PUT", f"products/{row['sku']}", json={"name": new_name})
                            st.success(res.get("msg", "Đã cập nhật"))
                            st.cache_data.clear()
                            st.rerun()

                else:
                    if st.button("♻️ Phục hồi", key=f"rec_{i}"):
                        res = api_request("POST", f"products/{row['sku']}/recover")
                        st.success(res.get("msg", "Đã phục hồi"))
                        st.cache_data.clear()
                        st.rerun()

            st.divider()

# ====== NHẬP / XUẤT ======
elif menu == "Nhập/Xuất":
    st.subheader("📥📤 Giao dịch")

    df_prod = fetch_products()
    if df_prod.empty:
        st.warning("Chưa có sản phẩm")
    else:
        sel = st.selectbox("Sản phẩm", df_prod["sku"] + " - " + df_prod["name"])
        sku = sel.split(" - ")[0]

        tx_type = st.radio("Loại", ["Nhập", "Xuất"])
        qty = st.number_input("Số lượng", min_value=1)

        if st.button("Xác nhận"):
            res = api_request("POST", "transaction", json={
                "sku": sku,
                "type": tx_type,
                "quantity": qty,
                "warehouse_id": 1
            })

            if res.get("msg") == "OK":
                st.success("Thành công")
                st.cache_data.clear()
            else:
                st.error(res.get("error", "Lỗi"))

# ====== LỊCH SỬ ======
elif menu == "Lịch sử":
    st.subheader("📜 Lịch sử")
    df = fetch_history(200)
    st.dataframe(df, use_container_width=True)

# ====== XUẤT EXCEL ======
elif menu == "Xuất Excel":
    st.subheader("📥 Export")

    df = fetch_history(1000)

    if st.button("Tải Excel"):
        file = "history.xlsx"
        df.to_excel(file, index=False)

        with open(file, "rb") as f:
            st.download_button("Download", f, file_name="history.xlsx")
