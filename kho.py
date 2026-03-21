import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# ================= CẤU HÌNH ==========
API_URL="https://quanlykho-backend.onrender.com" # Thay bằng URL FastAPI đã deploy

# ================= CACHE =================
@st.cache_data(ttl=30)
def get_products():
    r = requests.get(f"{API_URL}/products")
    return pd.DataFrame(r.json()) if r.status_code==200 else pd.DataFrame()

@st.cache_data(ttl=30)
def get_stock():
    r = requests.get(f"{API_URL}/stock")
    return pd.DataFrame(r.json()) if r.status_code==200 else pd.DataFrame()

# ================= LOGIN =================
if "user" not in st.session_state: st.session_state.user=None

if not st.session_state.user:
    st.title("🔐 Đăng nhập")
    u = st.text_input("Tên đăng nhập")
    p = st.text_input("Mật khẩu", type="password")
    if st.button("Đăng nhập"):
        # Demo: bạn có thể gọi API login sau
        if u=="admin" and p=="admin123":
            st.session_state.user={"username":u,"role":"admin"}
        else:
            st.error("Sai tài khoản")
    st.stop()

user = st.session_state.user
role = user["role"]

# ================= MENU =================
st.sidebar.title("📦 QUẢN LÝ KHO AMME THE")
menu = st.sidebar.radio("Menu", ["Dashboard","Kho tổng","Kho cửa hàng","Thêm sản phẩm",
                                 "Sửa / Xóa / Phục hồi","Nhập / Xuất","Lịch sử","Xuất Excel"])

# ================= DASHBOARD =================
if menu=="Dashboard":
    st.subheader("📊 Kho tổng")
    df_stock = get_stock()
    if not df_stock.empty:
        st.bar_chart(df_stock.groupby("warehouse")["quantity"].sum())
    st.subheader("📊 Kho cửa hàng")
    df_store = get_stock()  # bạn có thể gọi API riêng cho store
    if not df_store.empty:
        st.bar_chart(df_store.groupby("store_id")["quantity"].sum())

# ================= KHO TỔNG =================
elif menu=="Kho tổng":
    st.subheader("📦 Tồn kho tổng")
    df = get_stock()
    st.dataframe(df, use_container_width=True)

# ================= KHO CỬA HÀNG =================
elif menu=="Kho cửa hàng":
    st.subheader("🏬 Tồn kho cửa hàng")
    df = get_stock()  # Thay bằng API kho cửa hàng
    st.dataframe(df, use_container_width=True)

# ================= THÊM SẢN PHẨM =================
elif menu=="Thêm sản phẩm":
    st.subheader("➕ Thêm sản phẩm")
    sku = st.text_input("SKU")
    name = st.text_input("Tên sản phẩm")
    if st.button("Thêm sản phẩm"):
        r = requests.post(f"{API_URL}/products", json={"sku":sku,"name":name})
        if r.status_code==200: st.success("Đã thêm sản phẩm"); st.experimental_rerun()
        else: st.error("Lỗi thêm sản phẩm")

# ================= SỬA / XÓA / PHỤC HỒI =================
elif menu=="Sửa / Xóa / Phục hồi":
    st.subheader("✏️ Sửa / 🗑 Xóa / ♻️ Phục hồi sản phẩm")
    df = get_products()
    if df.empty: st.info("Chưa có sản phẩm"); st.stop()
    df["display"] = df["sku"] + " - " + df["name"]
    sel = st.selectbox("Chọn sản phẩm", df["display"])
    sku = df[df["display"]==sel]["sku"].values[0]

    new_name = st.text_input("Tên mới", value=df[df["sku"]==sku]["name"].values[0])
    if st.button("Cập nhật tên"):
        r = requests.put(f"{API_URL}/products", json={"sku":sku,"name":new_name})
        if r.status_code==200: st.success("Đã cập nhật tên"); st.experimental_rerun()
        else: st.error("Lỗi cập nhật")

    if st.button("Xóa sản phẩm"):
        r = requests.delete(f"{API_URL}/products/{sku}")
        if r.status_code==200: st.success("Đã xóa sản phẩm"); st.experimental_rerun()
        else: st.error("Lỗi xóa")

    # Phục hồi
    r_del = requests.get(f"{API_URL}/products")
    df_deleted = pd.DataFrame([p for p in r_del.json() if not p["is_active"]])
    if not df_deleted.empty:
        df_deleted["display"] = df_deleted["sku"]+" - "+df_deleted["name"]
        recover_sel = st.selectbox("Chọn sản phẩm phục hồi", df_deleted["display"])
        sku_recover = df_deleted[df_deleted["display"]==recover_sel]["sku"].values[0]
        if st.button("Phục hồi sản phẩm"):
            r = requests.post(f"{API_URL}/products/recover/{sku_recover}")
            if r.status_code==200: st.success("Đã phục hồi"); st.experimental_rerun()
            else: st.error("Lỗi phục hồi")

# ================= NHẬP / XUẤT =================
elif menu=="Nhập / Xuất":
    st.subheader("🔄 Nhập / Xuất hàng")
    df = get_products()
    df["display"]=df["sku"]+" - "+df["name"]
    sel = st.selectbox("Chọn sản phẩm", df["display"])
    sku = df[df["display"]==sel]["sku"].values[0]

    wh_id = st.number_input("ID kho", min_value=1)
    qty = st.number_input("Số lượng", min_value=1)
    type_tx = st.radio("Loại", ["Nhập","Xuất"])
    store_id = None
    if type_tx=="Xuất":
        store_id = st.number_input("ID cửa hàng", min_value=1)

    if st.button("Xác nhận"):
        payload = {"sku":sku,"warehouse_id":wh_id,"quantity":qty,"type_tx":type_tx,"store_id":store_id}
        r = requests.post(f"{API_URL}/stock", json=payload)
        if r.status_code==200: st.success("✅ Hoàn tất"); st.experimental_rerun()
        else: st.error(r.json().get("detail","Lỗi giao dịch"))

# ================= LỊCH SỬ =================
elif menu=="Lịch sử":
    st.subheader("📜 Lịch sử giao dịch")
    r = requests.get(f"{API_URL}/history")
    df = pd.DataFrame(r.json()) if r.status_code==200 else pd.DataFrame()
    st.dataframe(df, use_container_width=True)

# ================= XUẤT EXCEL =================
elif menu=="Xuất Excel":
    r = requests.get(f"{API_URL}/history")
    df = pd.DataFrame(r.json()) if r.status_code==200 else pd.DataFrame()
    if not df.empty:
        df.to_excel("export.xlsx", index=False)
        with open("export.xlsx","rb") as f:
            st.download_button("Tải xuống Excel", f, file_name="export.xlsx")
