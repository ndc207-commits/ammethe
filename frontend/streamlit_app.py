import streamlit as st
import pandas as pd
import requests
import os
from io import BytesIO
from reportlab.pdfgen import canvas

# ===== CONFIG =====
API_URL = os.getenv("API_URL", "https://quanlykho-backend1.onrender.com")
st.set_page_config(page_title="Quản lý kho AMME THE", layout="wide")

# ===== API HELPERS =====
@st.cache_data(ttl=5)
def api_get(endpoint):
    try:
        r = requests.get(f"{API_URL}/{endpoint}")
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

def api_post(endpoint, payload=None):
    try:
        requests.post(f"{API_URL}/{endpoint}", json=payload)
    except:
        st.error("Lỗi API POST")

def api_put(endpoint, payload=None):
    try:
        requests.put(f"{API_URL}/{endpoint}", json=payload)
    except:
        st.error("Lỗi API PUT")

def api_delete(endpoint):
    try:
        requests.delete(f"{API_URL}/{endpoint}")
    except:
        st.error("Lỗi API DELETE")

# ===== DATA HELPERS =====
def to_df(data):
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data)

def safe_df(df, cols):
    if df.empty:
        return False
    for c in cols:
        if c not in df.columns:
            return False
    return True

def filter_active(df):
    if "is_active" in df.columns:
        return df[df["is_active"] == True]
    return df

def show_df(df, msg):
    if df.empty:
        st.info(msg)
    else:
        st.dataframe(df, use_container_width=True)

def get_row(df, sku):
    row = df[df["sku"] == sku]
    return row.iloc[0] if not row.empty else None

def rerun_data():
    # Reload dữ liệu mà không cần experimental_rerun
    st.session_state["reload"] = not st.session_state.get("reload", False)

# ===== UI =====
st.title("📦 Quản lý kho")

menu = st.sidebar.radio("Menu", [
    "Kho tổng", "Nhập/Xuất", "Chuyển kho",
    "Sản phẩm", "Thêm sản phẩm",
    "Cảnh báo tồn kho",
    "Lịch sử", "PDF"
])

# ===== KHO TỔNG =====
if menu == "Kho tổng":
    st.subheader("📦 Kho tổng")
    with st.spinner("Đang tải dữ liệu kho..."):
        data = api_get("inventory")
        df = to_df(data)

    if df.empty:
        st.warning("Không có dữ liệu kho")
    elif "warehouse" not in df.columns:
        st.error("Dữ liệu kho API sai, thiếu cột 'warehouse'")
    else:
        warehouses = df['warehouse'].unique()
        for wh in warehouses:
            st.subheader(f"📦 {wh}")
            df_wh = df[df['warehouse'] == wh]
            st.dataframe(df_wh, use_container_width=True)

# ===== NHẬP/XUẤT =====
elif menu == "Nhập/Xuất":
    df_prod = filter_active(to_df(api_get("products")))
    df_wh = to_df(api_get("warehouses"))

    if not safe_df(df_prod, ["sku","name"]) or not safe_df(df_wh, ["id","name"]):
        st.warning("Thiếu dữ liệu products hoặc warehouses")
        st.stop()

    sel = st.selectbox("Sản phẩm", df_prod["sku"] + " - " + df_prod["name"])
    sku = sel.split(" - ")[0]

    wh = st.selectbox("Kho", df_wh["name"])
    wh_id = int(df_wh[df_wh["name"] == wh]["id"].values[0])

    t = st.radio("Loại", ["Nhập", "Xuất"])
    qty = st.number_input("Số lượng", 1)

    if st.button("OK"):
        api_post("transaction", {
            "sku": sku,
            "type": t,
            "quantity": qty,
            "warehouse_id": wh_id
        })
        st.success("Thành công")
        rerun_data()

# ===== CHUYỂN KHO =====
elif menu == "Chuyển kho":
    df_prod = filter_active(to_df(api_get("products")))
    df_wh = to_df(api_get("warehouses"))

    if not safe_df(df_prod, ["sku","name"]) or not safe_df(df_wh, ["id","name"]):
        st.warning("Thiếu dữ liệu")
        st.stop()

    sel = st.selectbox("Sản phẩm", df_prod["sku"] + " - " + df_prod["name"])
    sku = sel.split(" - ")[0]

    wh_from = st.selectbox("Từ", df_wh["name"], key="from")
    wh_to = st.selectbox("Đến", df_wh["name"], key="to")

    qty = st.number_input("Số lượng", 1)

    if st.button("Chuyển"):
        if wh_from == wh_to:
            st.warning("Kho phải khác nhau")
        else:
            id_from = int(df_wh[df_wh["name"] == wh_from]["id"].values[0])
            id_to = int(df_wh[df_wh["name"] == wh_to]["id"].values[0])

            api_post("transaction", {"sku": sku, "type": "Xuất", "quantity": qty, "warehouse_id": id_from})
            api_post("transaction", {"sku": sku, "type": "Nhập", "quantity": qty, "warehouse_id": id_to})

            st.success("Đã chuyển")
            rerun_data()

# ===== SẢN PHẨM =====
elif menu == "Sản phẩm":
    df = to_df(api_get("products"))

    if not safe_df(df, ["sku","name"]):
        st.warning("API products lỗi hoặc không có dữ liệu")
        st.stop()

    df_active = filter_active(df)
    df_deleted = df[df["is_active"] == False] if "is_active" in df.columns else pd.DataFrame()

    # --- Hiển thị sản phẩm đang hoạt động ---
    st.subheader("🟢 Sản phẩm đang hoạt động")
    show_df(df_active, "Chưa có sản phẩm")

    # --- Hiển thị sản phẩm đã xóa ---
    st.subheader("🔴 Sản phẩm đã xóa")
    if not df_deleted.empty:
        sel_deleted = st.selectbox("Chọn sản phẩm phục hồi", df_deleted["sku"] + " - " + df_deleted["name"])
        sku_del = sel_deleted.split(" - ")[0]
        if st.button("♻️ Phục hồi sản phẩm"):
            api_post(f"products/{sku_del}/recover")
            st.success(f"Đã phục hồi {sku_del}")
            rerun_data()
    else:
        st.info("Không có sản phẩm đã xóa")

    # --- Chỉnh sửa / Xóa sản phẩm ---
    st.subheader("✏️ Sửa / 🗑 Xóa sản phẩm")
    if not df_active.empty:
        sel_active = st.selectbox("Chọn sản phẩm", df_active["sku"] + " - " + df_active["name"])
        sku = sel_active.split(" - ")[0]
        current_name = get_row(df_active, sku)["name"]

        new_name = st.text_input("Tên mới", current_name)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Cập nhật"):
                if new_name.strip() == "":
                    st.warning("Tên mới không được để trống")
                elif new_name != current_name:
                    api_put(f"products/{sku}", {"name": new_name})
                    st.success(f"Đã cập nhật {sku}")
                    rerun_data()
                else:
                    st.info("Tên không thay đổi")
        with col2:
            confirm = st.checkbox("Xác nhận xóa sản phẩm")
            if st.button("🗑 Xóa"):
                if not confirm:
                    st.warning("Cần xác nhận trước khi xóa")
                else:
                    api_delete(f"products/{sku}")
                    st.success(f"Đã xóa {sku}")
                    rerun_data()

# ===== THÊM SẢN PHẨM =====
elif menu == "Thêm sản phẩm":
    sku = st.text_input("SKU")
    name = st.text_input("Tên sản phẩm")

    if st.button("Thêm"):
        if not sku or not name:
            st.warning("Nhập đủ thông tin")
        else:
            api_post("products", {"sku": sku, "name": name})
            st.success("Đã thêm")
            rerun_data()

# ===== CẢNH BÁO TỒN KHO =====
elif menu == "Cảnh báo tồn kho":
    st.subheader("⚠️ Cảnh báo tồn kho")
    threshold = st.number_input("Ngưỡng cảnh báo", min_value=1, value=10)

    df = to_df(api_get(f"inventory/low-stock?threshold={threshold}"))

    if df.empty:
        st.success("✅ Tất cả sản phẩm đều đủ hàng")
    else:
        def highlight(row):
            if row["quantity"] <= threshold * 0.5:
                return ["background-color: red; color: white"]*len(row)
            elif row["quantity"] < threshold:
                return ["background-color: orange"]*len(row)
            return [""]*len(row)
        st.dataframe(df.style.apply(highlight, axis=1), use_container_width=True)

        for _, row in df.iterrows():
            if row["quantity"] <= threshold * 0.5:
                st.error(f"{row['sku']} - {row['name']} | {row['warehouse']} | Còn: {row['quantity']}")
            else:
                st.warning(f"{row['sku']} - {row['name']} | {row['warehouse']} | Còn: {row['quantity']}")

# ===== LỊCH SỬ =====
elif menu == "Lịch sử":
    df = to_df(api_get("history"))
    show_df(df, "Không có dữ liệu")

# ===== PDF =====
elif menu == "PDF":
    df = filter_active(to_df(api_get("products")))

    if not safe_df(df, ["sku","name"]):
        st.warning("Không có sản phẩm")
        st.stop()

    sel = st.selectbox("Sản phẩm", df["sku"] + " - " + df["name"])
    sku = sel.split(" - ")[0]

    qty = st.number_input("Qty", 1)
    t = st.selectbox("Type", ["Nhập","Xuất"])

    if st.button("Tạo PDF"):
        buffer = BytesIO()
        c = canvas.Canvas(buffer)
        c.drawString(100, 800, f"PHIẾU {t}")
        c.drawString(100, 780, f"SKU: {sku}")
        c.drawString(100, 760, f"Số lượng: {qty}")
        c.drawString(100, 740, pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'))
        c.save()
        buffer.seek(0)
        st.download_button("Download PDF", buffer, f"invoice_{sku}.pdf", mime="application/pdf")
