import streamlit as st
import pandas as pd
import requests
import os
import time
from io import BytesIO
from reportlab.pdfgen import canvas

# ===== CONFIG =====
API_URL = os.getenv("API_URL", "https://quanlykho-backend1.onrender.com")
st.set_page_config(page_title="Quản lý kho AMME THE", layout="wide")

# ===== API HELPERS (FIX RENDER) =====
def wake_server():
    try:
        requests.get(API_URL, timeout=5)
        time.sleep(2)
    except:
        pass

@st.cache_data(ttl=5)
def api_get(endpoint):
    wake_server()
    for _ in range(3):
        try:
            r = requests.get(f"{API_URL}/{endpoint}", timeout=10)
            if r.status_code == 200:
                return r.json()
        except:
            time.sleep(2)
    return None

def api_post(endpoint, payload=None):
    wake_server()
    try:
        requests.post(f"{API_URL}/{endpoint}", json=payload, timeout=10)
    except:
        st.error("Lỗi API POST")

def api_put(endpoint, payload=None):
    wake_server()
    try:
        requests.put(f"{API_URL}/{endpoint}", json=payload, timeout=10)
    except:
        st.error("Lỗi API PUT")

def api_delete(endpoint):
    wake_server()
    try:
        requests.delete(f"{API_URL}/{endpoint}", timeout=10)
    except:
        st.error("Lỗi API DELETE")

# ===== DATA HELPERS =====
def to_df(data):
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data)

def safe_df(df, cols):
    return not df.empty and all(c in df.columns for c in cols)

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
    with st.spinner("🔄 Đang tải sản phẩm..."):
        df = to_df(api_get("products"))
        df_inv = to_df(api_get("inventory"))  # để lấy warehouse

    # ===== FIX API =====
    if df.empty:
        st.warning("⚠️ Không có dữ liệu (server có thể đang sleep)")
        st.stop()

    if "sku" not in df.columns or "name" not in df.columns:
        st.error(f"❌ Sai format API: {df.columns}")
        st.stop()

    # ===== GỘP WAREHOUSE =====
    if not df_inv.empty and "sku" in df_inv.columns:
        df = df.merge(df_inv[["sku", "warehouse"]], on="sku", how="left")

    # ===== FILTER UI =====
    col1, col2 = st.columns(2)

    # 🔍 SEARCH REALTIME
    with col1:
        keyword = st.text_input("🔍 Tìm kiếm (realtime)")

    # 🏬 FILTER WAREHOUSE
    with col2:
        if "warehouse" in df.columns:
            warehouses = ["Tất cả"] + sorted(df["warehouse"].dropna().unique().tolist())
            selected_wh = st.selectbox("🏬 Lọc theo kho", warehouses)
        else:
            selected_wh = "Tất cả"

    # ===== APPLY FILTER =====
    if keyword:
        df = df[
            df["name"].str.contains(keyword, case=False, na=False) |
            df["sku"].str.contains(keyword, case=False, na=False)
        ]

    if selected_wh != "Tất cả" and "warehouse" in df.columns:
        df = df[df["warehouse"] == selected_wh]

    df_active = filter_active(df)
    df_deleted = df[df["is_active"] == False] if "is_active" in df.columns else pd.DataFrame()

    # ===== HIỂN THỊ =====
    st.subheader("🟢 Sản phẩm đang hoạt động")
    show_df(df_active, "Chưa có sản phẩm")

    st.subheader("🔴 Sản phẩm đã xóa")
    if not df_deleted.empty:
        sel_deleted = st.selectbox(
            "Chọn sản phẩm phục hồi",
            df_deleted["sku"] + " - " + df_deleted["name"]
        )
        sku_del = sel_deleted.split(" - ")[0]

        if st.button("♻️ Phục hồi sản phẩm"):
            api_post(f"products/{sku_del}/recover")
            st.success(f"Đã phục hồi {sku_del}")
            time.sleep(1)
            st.rerun()
    else:
        st.info("Không có sản phẩm đã xóa")

    # ===== EDIT / DELETE =====
    st.subheader("✏️ Sửa / 🗑 Xóa sản phẩm")

    if not df_active.empty:
        sel_active = st.selectbox(
            "Chọn sản phẩm",
            df_active["sku"] + " - " + df_active["name"]
        )
        sku = sel_active.split(" - ")[0]

        row = get_row(df_active, sku)
        if row is None:
            st.error("Không tìm thấy sản phẩm")
            st.stop()

        current_name = row["name"]
        new_name = st.text_input("Tên mới", current_name)

        col1, col2 = st.columns(2)

        # UPDATE
        with col1:
            if st.button("💾 Cập nhật"):
                if new_name.strip() == "":
                    st.warning("Tên mới không được để trống")
                elif new_name != current_name:
                    api_put(f"products/{sku}", {"name": new_name})
                    st.success(f"Đã cập nhật {sku}")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.info("Tên không thay đổi")

        # DELETE
        with col2:
            confirm = st.checkbox("Xác nhận xóa sản phẩm")
            if st.button("🗑 Xóa"):
                if not confirm:
                    st.warning("Cần xác nhận trước khi xóa")
                else:
                    api_delete(f"products/{sku}")
                    st.success(f"Đã xóa {sku}")
                    time.sleep(1)
                    st.rerun()
                    
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
    st.subheader("📜 Lịch sử giao dịch")

    # ===== CHỌN KHOẢNG NGÀY =====
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Từ ngày", pd.Timestamp.now() - pd.Timedelta(days=30))
    with col2:
        end_date = st.date_input("Đến ngày", pd.Timestamp.now())

    # ===== LẤY DỮ LIỆU =====
    df = to_df(api_get("history"))

    # ===== LỌC THEO NGÀY =====
    if not df.empty and "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        mask = (df["timestamp"].dt.date >= start_date) & (df["timestamp"].dt.date <= end_date)
        df = df.loc[mask]

    show_df(df, "Không có dữ liệu")

# ===== PDF =====
elif menu == "PDF":
    df = filter_active(to_df(api_get("products")))

    if not safe_df(df, ["sku","name"]):
        st.warning("Không có sản phẩm")
        st.stop()

    # ===== CHỌN NHIỀU SẢN PHẨM =====
    selected_products = st.multiselect(
        "Chọn sản phẩm", df["sku"] + " - " + df["name"]
    )

    qty = st.number_input("Số lượng", 1)
    t = st.selectbox("Type", ["Nhập","Xuất"])

    if st.button("Tạo PDF") and selected_products:
        buffer = BytesIO()
        c = canvas.Canvas(buffer)
        y = 800

        c.drawString(100, y, f"PHIẾU {t}")
        y -= 20
        c.drawString(100, y, pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'))
        y -= 40

        for sel in selected_products:
            sku = sel.split(" - ")[0]
            name = sel.split(" - ")[1]
            c.drawString(100, y, f"SKU: {sku} | Tên: {name} | Số lượng: {qty}")
            y -= 20
            if y < 50:  # nếu gần hết trang, tạo trang mới
                c.showPage()
                y = 800

        c.save()
        buffer.seek(0)
        st.download_button("Download PDF", buffer, f"invoice_multi.pdf", mime="application/pdf")
