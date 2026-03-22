import streamlit as st
import pandas as pd
import requests
import io
from reportlab.pdfgen import canvas
import os

# ====== URL backend ======
API_URL = os.getenv("API_URL", "https://quanlykho-backend1.onrender.com")

# ====== Hàm gọi API ======
def api(method, endpoint, **kwargs):
    try:
        r = requests.request(method, f"{API_URL}/{endpoint}", **kwargs)
        if r.status_code in [200, 201]:
            return r.json()
        else:
            st.error(f"Lỗi API {r.status_code}: {r.text}")
            return []
    except Exception as e:
        st.error(f"Lỗi kết nối API: {e}")
        return []

# ====== Menu ======
menu = st.sidebar.radio("Menu", [
    "Kho tổng", "Nhập/Xuất", "Sản phẩm", "Thêm sản phẩm",
    "Tìm kiếm", "Cảnh báo tồn kho", "Lịch sử", "PDF"
])

# ====== SẢN PHẨM ======
if menu == "Sản phẩm":
    df = pd.DataFrame(api("GET", "products"))
    if df.empty:
        df = pd.DataFrame(columns=["sku", "name", "is_active"])
    if "is_active" not in df.columns:
        df["is_active"] = True
    active = df[df["is_active"]==True]
    deleted = df[df["is_active"]==False]

    st.subheader("🟢 Sản phẩm đang hoạt động")
    st.dataframe(active if not active.empty else pd.DataFrame(columns=["sku","name","is_active"]))

    st.subheader("🔴 Sản phẩm đã xóa")
    if not deleted.empty:
        sel_deleted = st.selectbox("Chọn sản phẩm phục hồi",
                                   deleted["sku"] + " - " + deleted["name"])
        sku_del = sel_deleted.split(" - ")[0]
        if st.button("♻️ Phục hồi"):
            api("POST", f"products/{sku_del}/recover")
            st.success("Đã phục hồi")
            st.experimental_rerun()
    else:
        st.info("Không có sản phẩm đã xóa")

# ====== Thêm sản phẩm ======
elif menu == "Thêm sản phẩm":
    st.subheader("➕ Thêm sản phẩm mới")
    sku = st.text_input("SKU")
    name = st.text_input("Tên sản phẩm")
    if st.button("Thêm"):
        if not sku or not name:
            st.warning("Nhập đầy đủ thông tin")
        else:
            api("POST", "products", json={"sku": sku, "name": name})
            st.success("✅ Thêm thành công")
            st.experimental_rerun()

# ====== Kho tổng ======
elif menu == "Kho tổng":
    df = pd.DataFrame(api("GET", "inventory"))
    if df.empty:
        df = pd.DataFrame(columns=["warehouse","sku","name","quantity"])
    warehouses = df["warehouse"].unique() if not df.empty else ["Kho 1"]
    tabs = st.tabs(warehouses)
    for i, wh in enumerate(warehouses):
        with tabs[i]:
            df_wh = df[df["warehouse"]==wh] if not df.empty else pd.DataFrame(columns=["sku","name","quantity"])
            st.dataframe(df_wh)

# ====== Nhập/Xuất ======
elif menu == "Nhập/Xuất":
    df_prod = pd.DataFrame(api("GET", "products"))
    df_wh = pd.DataFrame(api("GET", "warehouses"))
    if df_prod.empty or df_wh.empty:
        st.warning("Không có dữ liệu")
    else:
        if "is_active" not in df_prod.columns:
            df_prod["is_active"] = True
        df_prod = df_prod[df_prod["is_active"]==True]
        sel = st.selectbox("Sản phẩm", df_prod["sku"] + " - " + df_prod["name"])
        sku = sel.split(" - ")[0]
        wh = st.selectbox("Kho", df_wh["name"])
        wh_id = int(df_wh[df_wh["name"]==wh]["id"])
        t = st.radio("Loại", ["Nhập", "Xuất"])
        qty = st.number_input("Số lượng", 1, step=1)
        if st.button("OK"):
            api("POST", "transaction", json={
                "sku": sku, "type": t, "quantity": qty, "warehouse_id": wh_id
            })
            st.success("✅ OK")
            st.experimental_rerun()

# ====== Tìm kiếm ======
elif menu=="Tìm kiếm":
    q = st.text_input("Tìm theo SKU hoặc tên")
    if q:
        df = pd.DataFrame(api("GET", f"products/search?q={q}"))
        if df.empty:
            df = pd.DataFrame(columns=["sku","name","is_active"])
        st.dataframe(df)

# ====== Cảnh báo tồn kho ======
elif menu=="Cảnh báo tồn kho":
    threshold = st.number_input("Ngưỡng tồn kho", min_value=1,value=10)
    df = pd.DataFrame(api("GET", f"inventory/low-stock?threshold={threshold}"))
    if df.empty:
        df = pd.DataFrame(columns=["warehouse","sku","name","quantity"])
    st.dataframe(df)

# ====== Lịch sử ======
elif menu=="Lịch sử":
    df = pd.DataFrame(api("GET", "history"))
    if df.empty:
        df = pd.DataFrame(columns=["sku","type","quantity","warehouse","created_at","note"])
    st.dataframe(df)

# ====== PDF ======
elif menu=="PDF":
    df_prod = pd.DataFrame(api("GET", "products"))
    if df_prod.empty:
        df_prod = pd.DataFrame(columns=["sku","name"])
    sel = st.selectbox("Sản phẩm", df_prod["sku"] + " - " + df_prod["name"] if not df_prod.empty else [""])
    sku = sel.split(" - ")[0] if sel else ""
    qty = st.number_input("Qty",1)
    t = st.selectbox("Type", ["Nhập","Xuất"])
    if st.button("Download PDF") and sku:
        url = f"{API_URL}/invoice/pdf?sku={sku}&qty={qty}&type={t}"
        st.markdown(f"[Download PDF]({url})")
