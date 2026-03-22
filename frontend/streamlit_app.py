import streamlit as st
import pandas as pd
import requests
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

st.title("📦 QUẢN LÝ KHO")

menu = st.sidebar.radio("Menu", [
    "Kho tổng", "Nhập/Xuất", "Sản phẩm", "Thêm sản phẩm",
    "Tìm kiếm", "Cảnh báo tồn kho", "Lịch sử", "PDF"
])

# ====== SẢN PHẨM ======
if menu == "Sản phẩm":
    df = api("GET", "products")
    if df:
        df = pd.DataFrame(df)
        if 'sku' not in df.columns:
            df['sku'] = ""
        if 'name' not in df.columns:
            df['name'] = ""
        if 'is_active' not in df.columns:
            df['is_active'] = True

        active = df[df["is_active"]==True]
        deleted = df[df["is_active"]==False]

        st.subheader("🟢 Sản phẩm đang hoạt động")
        if not active.empty:
            st.dataframe(active[["sku","name"]], use_container_width=True)
        else:
            st.info("Chưa có sản phẩm nào")

        st.subheader("🔴 Sản phẩm đã xóa")
        if not deleted.empty:
            sel_deleted = st.selectbox("Chọn sản phẩm phục hồi",
                                       deleted["sku"].fillna('') + " - " + deleted["name"].fillna(''))
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
    df = api("GET", "inventory")
    if df:
        df = pd.DataFrame(df)
        if not df.empty:
            warehouses = df['warehouse'].dropna().unique()
            tabs = st.tabs(warehouses)
            for i, wh in enumerate(warehouses):
                with tabs[i]:
                    st.dataframe(df[df['warehouse']==wh][["sku","name","quantity"]], use_container_width=True)
        else:
            st.warning("Không có dữ liệu kho")
    else:
        st.warning("Không có dữ liệu kho")

# ====== Nhập / Xuất ======
elif menu == "Nhập/Xuất":
    df_prod = pd.DataFrame(api("GET","products"))
    df_prod = df_prod[df_prod.get("is_active", True)==True]
    df_wh = pd.DataFrame(api("GET","warehouses"))

    if df_prod.empty or df_wh.empty:
        st.warning("Không có dữ liệu")
    else:
        sel = st.selectbox("Sản phẩm", df_prod.get("sku", pd.Series()) + " - " + df_prod.get("name", pd.Series()))
        sku = sel.split(" - ")[0] if sel else ""
        wh = st.selectbox("Kho", df_wh.get("name", pd.Series()))
        wh_id = int(df_wh[df_wh["name"]==wh]["id"].values[0])
        t = st.radio("Loại", ["Nhập", "Xuất"])
        qty = st.number_input("Số lượng", 1, step=1)
        if st.button("OK"):
            api("POST","transaction", json={"sku":sku,"type":t,"quantity":qty,"warehouse_id":wh_id})
            st.success("✅ OK")
            st.experimental_rerun()

# ====== Tìm kiếm ======
elif menu=="Tìm kiếm":
    q = st.text_input("Tìm theo SKU hoặc tên")
    if q:
        df = api("GET", f"products/search?q={q}")
        if df:
            df = pd.DataFrame(df)
            st.dataframe(df[["sku","name","is_active"]])
        else:
            st.info("Không tìm thấy sản phẩm")

# ====== Cảnh báo tồn kho ======
elif menu=="Cảnh báo tồn kho":
    threshold = st.number_input("Ngưỡng tồn kho", min_value=1,value=10)
    df = api("GET", f"inventory/low-stock?threshold={threshold}")
    if df:
        df = pd.DataFrame(df)
        st.dataframe(df[["warehouse","sku","name","quantity"]])
    else:
        st.success("Không có sản phẩm nào dưới ngưỡng tồn kho.")

# ====== Lịch sử ======
elif menu=="Lịch sử":
    df = api("GET","history")
    if df:
        df = pd.DataFrame(df)
        st.dataframe(df)
    else:
        st.info("Không có dữ liệu lịch sử")

# ====== PDF ======
elif menu=="PDF":
    df_prod = pd.DataFrame(api("GET","products"))
    if not df_prod.empty:
        sel = st.selectbox("Sản phẩm", df_prod.get("sku", pd.Series()) + " - " + df_prod.get("name", pd.Series()))
        sku = sel.split(" - ")[0] if sel else ""
        qty = st.number_input("Qty",1)
        t = st.selectbox("Type", ["Nhập","Xuất"])
        if st.button("Download PDF") and sku:
            url = f"{API_URL}/invoice/pdf?sku={sku}&qty={qty}&type={t}"
            st.markdown(f"[Download PDF]({url})")
