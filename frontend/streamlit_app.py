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
            current_name = df_active[df_active["sku"] == sku]["name"].values[0]
            new_name = st.text_input("Tên mới", current_name)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Cập nhật"):
                    api("PUT", f"products/{sku}", json={"sku": sku, "name": new_name})
                    st.success("Đã cập nhật")

            with col2:
                confirm = st.checkbox("Xác nhận xóa")
                if st.button("🗑 Xóa"):
                    if confirm:
                        api("DELETE", f"products/{sku}")
                        st.success("Đã xóa")
                    else:
                        st.warning("Cần xác nhận")

# ===== THÊM SẢN PHẨM =====
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

# ===== KHO TỔNG =====
elif menu == "Kho tổng":
    df = to_df(api("GET", "inventory"))

    if df.empty:
        st.warning("Không có dữ liệu kho")
    else:
        for wh in df['warehouse'].unique():
            st.subheader(f"📦 {wh}")
            st.dataframe(df[df['warehouse'] == wh], use_container_width=True)

# ===== NHẬP/XUẤT =====
elif menu == "Nhập/Xuất":
    df_prod = filter_active(to_df(api("GET", "products")))
    df_wh = to_df(api("GET", "warehouses"))

    if df_prod.empty or df_wh.empty:
        st.warning("Không có dữ liệu")
    else:
        sku = select_product(df_prod)
        wh = st.selectbox("Kho", df_wh["name"])
        wh_id = get_warehouse_id(df_wh, wh)
        t = st.radio("Loại", ["Nhập", "Xuất"])
        qty = st.number_input("Số lượng", 1, step=1)

        if st.button("OK"):
            api("POST", "transaction", json={
                "sku": sku,
                "type": t,
                "quantity": qty,
                "warehouse_id": wh_id
            })
            st.success("✅ OK")

# ===== CHUYỂN KHO =====
elif menu == "Chuyển kho":
    st.subheader("🚚 Chuyển kho sản phẩm")

    df_prod = filter_active(to_df(api("GET", "products")))
    df_wh = to_df(api("GET", "warehouses"))

    if df_prod.empty or df_wh.empty:
        st.warning("Không có dữ liệu")
    else:
        sku = select_product(df_prod)
        wh_from = st.selectbox("Từ kho", df_wh["name"])
        wh_to = st.selectbox("Đến kho", df_wh["name"])
        qty = st.number_input("Số lượng chuyển", 1, step=1)

        if st.button("Chuyển"):
            if wh_from == wh_to:
                st.warning("Kho phải khác nhau")
            else:
                wh_from_id = get_warehouse_id(df_wh, wh_from)
                wh_to_id = get_warehouse_id(df_wh, wh_to)

                api("POST", "transaction", json={"sku": sku, "type": "Xuất", "quantity": qty, "warehouse_id": wh_from_id})
                api("POST", "transaction", json={"sku": sku, "type": "Nhập", "quantity": qty, "warehouse_id": wh_to_id})

                st.success("✅ Chuyển thành công")

# ===== TÌM KIẾM =====
elif menu == "Tìm kiếm":
    q = st.text_input("Tìm theo SKU hoặc tên")
    if q:
        df = to_df(api("GET", f"products/search?q={q}"))
        st.dataframe(df)

# ===== CẢNH BÁO =====
elif menu == "Cảnh báo tồn kho":
    threshold = st.number_input("Ngưỡng tồn kho", min_value=1, value=10)
    df = to_df(api("GET", f"inventory/low-stock?threshold={threshold}"))

    if df.empty:
        st.success("Không có sản phẩm dưới ngưỡng")
    else:
        st.dataframe(df)

# ===== LỊCH SỬ =====
elif menu == "Lịch sử":
    df = to_df(api("GET", "history"))
    st.dataframe(df)

# ===== PDF =====
elif menu == "PDF":
    df_prod = filter_active(to_df(api("GET", "products")))

    if not df_prod.empty:
        sku = select_product(df_prod)
        qty = st.number_input("Qty", 1)
        t = st.selectbox("Type", ["Nhập", "Xuất"])

        if st.button("Download PDF"):
            buffer = BytesIO()
            c = canvas.Canvas(buffer)
            c.drawString(100, 800, f"PHIẾU {t.upper()}")
            c.drawString(100, 780, f"SKU: {sku}")
            c.drawString(100, 760, f"Số lượng: {qty}")
            c.drawString(100, 740, f"Ngày: {pd.Timestamp.now()}")
            c.save()
            buffer.seek(0)

            st.download_button(
                label="Download PDF",
                data=buffer,
                file_name=f"invoice_{sku}.pdf",
                mime="application/pdf"
            )
    else:
        st.warning("Không có sản phẩm")
