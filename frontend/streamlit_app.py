import streamlit as st
import pandas as pd
import requests
import os
from io import BytesIO
from reportlab.pdfgen import canvas

# ===== URL backend =====
API_URL = os.getenv("API_URL", "https://quanlykho-backend1.onrender.com")

# ===== Hàm gọi API =====
def api(method, endpoint, **kwargs):
    try:
        r = requests.request(method, f"{API_URL}/{endpoint}", **kwargs)
        if r.status_code in [200,201]:
            return r.json()
        return []
    except Exception as e:
        st.error(f"Lỗi kết nối API: {e}")
        return []

# ===== Main =====
st.title("Quản lý kho")

menu = st.sidebar.radio("Menu", [
    "Kho tổng", "Nhập/Xuất", "Chuyển kho", "Sản phẩm", "Thêm sản phẩm",
    "Tìm kiếm", "Cảnh báo tồn kho", "Lịch sử", "PDF"
])

# ====== SẢN PHẨM =====
if menu == "Sản phẩm":
    df = pd.DataFrame(api("GET", "products"))
    if df.empty:
        st.warning("Không có dữ liệu sản phẩm")
    else:
        df_active = df[df.get("is_active", True)==True]
        df_deleted = df[df.get("is_active", True)==False]

        st.subheader("🟢 Sản phẩm đang hoạt động")
        if not df_active.empty:
            st.dataframe(df_active, use_container_width=True)
        else:
            st.info("Chưa có sản phẩm nào")

        st.subheader("🔴 Sản phẩm đã xóa")
        if not df_deleted.empty:
            sel_deleted = st.selectbox("Chọn sản phẩm phục hồi",
                                       df_deleted["sku"] + " - " + df_deleted["name"])
            sku_del = sel_deleted.split(" - ")[0]
            if st.button("♻️ Phục hồi"):
                api("POST", f"products/{sku_del}/recover")
                st.success("Đã phục hồi")
        else:
            st.info("Không có sản phẩm đã xóa")

        st.subheader("✏️ Sửa / 🗑 Xóa sản phẩm")
        if not df_active.empty:
            sel_active = st.selectbox("Chọn sản phẩm",
                                      df_active["sku"] + " - " + df_active["name"])
            sku = sel_active.split(" - ")[0]
            current_name = df_active[df_active["sku"]==sku]["name"].values[0]
            new_name = st.text_input("Tên mới", current_name)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Cập nhật"):
                    api("PUT", f"products/{sku}", json={"sku": sku, "name": new_name})
                    st.success("Đã cập nhật")
            with col2:
                confirm = st.checkbox("Xác nhận xóa")
                if st.button("🗑 Xóa"):
                    if not confirm:
                        st.warning("Cần xác nhận")
                    else:
                        api("DELETE", f"products/{sku}")
                        st.success("Đã xóa")

# ====== Thêm sản phẩm =====
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

# ====== Kho tổng =====
elif menu == "Kho tổng":
    df = pd.DataFrame(api("GET", "inventory"))
    if df.empty:
        st.warning("Không có dữ liệu kho")
    else:
        warehouses = df['warehouse'].unique()
        tabs = st.tabs(warehouses)
        for i, wh in enumerate(warehouses):
            with tabs[i]:
                st.dataframe(df[df['warehouse']==wh], use_container_width=True)

# ====== Nhập/Xuất =====
elif menu == "Nhập/Xuất":
    df_prod = pd.DataFrame(api("GET","products"))
    df_prod = df_prod[df_prod.get("is_active", True)==True]
    df_wh = pd.DataFrame(api("GET","warehouses"))
    if df_prod.empty or df_wh.empty:
        st.warning("Không có dữ liệu")
    else:
        sel = st.selectbox("Sản phẩm", df_prod["sku"] + " - " + df_prod["name"])
        sku = sel.split(" - ")[0]
        wh = st.selectbox("Kho", df_wh["name"])
        wh_id = int(df_wh[df_wh["name"]==wh]["id"].values[0])
        t = st.radio("Loại", ["Nhập", "Xuất"])
        qty = st.number_input("Số lượng", 1, step=1)
        if st.button("OK"):
            api("POST","transaction",json={"sku":sku,"type":t,"quantity":qty,"warehouse_id":wh_id})
            st.success("✅ OK")

# ====== Chuyển kho =====
elif menu == "Chuyển kho":
    st.subheader("🚚 Chuyển kho sản phẩm")
    df_inv = pd.DataFrame(api("GET","inventory"))
    df_prod = pd.DataFrame(api("GET","products"))
    df_prod = df_prod[df_prod.get("is_active", True)==True]
    df_wh = pd.DataFrame(api("GET","warehouses"))
    if df_inv.empty or df_prod.empty or df_wh.empty:
        st.warning("Không có dữ liệu")
    else:
        sel_prod = st.selectbox("Chọn sản phẩm", df_prod["sku"] + " - " + df_prod["name"])
        sku = sel_prod.split(" - ")[0]
        wh_from = st.selectbox("Từ kho", df_wh["name"])
        wh_to = st.selectbox("Đến kho", df_wh["name"])
        qty = st.number_input("Số lượng chuyển", 1, step=1)

        if st.button("Chuyển"):
            if wh_from == wh_to:
                st.warning("Kho đi và kho đến phải khác nhau")
            else:
                wh_from_id = int(df_wh[df_wh["name"]==wh_from]["id"].values[0])
                wh_to_id = int(df_wh[df_wh["name"]==wh_to]["id"].values[0])
                # Xử lý trừ kho đi
                api("POST","transaction",json={"sku":sku,"type":"Xuất","quantity":qty,"warehouse_id":wh_from_id})
                # Xử lý cộng kho đến
                api("POST","transaction",json={"sku":sku,"type":"Nhập","quantity":qty,"warehouse_id":wh_to_id})
                st.success(f"✅ Chuyển {qty} sản phẩm từ {wh_from} sang {wh_to}")

# ====== Tìm kiếm =====
elif menu=="Tìm kiếm":
    q = st.text_input("Tìm theo SKU hoặc tên")
    if q:
        df = pd.DataFrame(api("GET", f"products/search?q={q}"))
        st.dataframe(df)

# ====== Cảnh báo tồn kho =====
elif menu=="Cảnh báo tồn kho":
    threshold = st.number_input("Ngưỡng tồn kho", min_value=1,value=10)
    df = pd.DataFrame(api("GET", f"inventory/low-stock?threshold={threshold}"))
    if df.empty:
        st.success("Không có sản phẩm dưới ngưỡng tồn kho")
    else:
        st.dataframe(df)

# ====== Lịch sử =====
elif menu=="Lịch sử":
    df = pd.DataFrame(api("GET","history"))
    st.dataframe(df)

# ====== PDF =====
elif menu=="PDF":
    df_prod = pd.DataFrame(api("GET","products"))
    df_prod = df_prod[df_prod.get("is_active", True)==True]
    sel = st.selectbox("Sản phẩm", df_prod["sku"] + " - " + df_prod["name"])
    sku = sel.split(" - ")[0]
    qty = st.number_input("Qty",1)
    t = st.selectbox("Type", ["Nhập","Xuất"])
    if st.button("Download PDF"):
        buffer = BytesIO()
        c = canvas.Canvas(buffer)
        c.drawString(100, 800, f"PHIẾU {t.upper()}")
        c.drawString(100, 780, f"SKU: {sku}")
        c.drawString(100, 760, f"Số lượng: {qty}")
        c.drawString(100, 740, f"Ngày: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
        c.save()
        buffer.seek(0)
        st.download_button(label="Download PDF", data=buffer, file_name=f"invoice_{sku}.pdf", mime="application/pdf")
