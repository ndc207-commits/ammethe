import streamlit as st
import pandas as pd
import requests
import os
from io import BytesIO
from reportlab.pdfgen import canvas

# ===== CONFIG =====
API_URL = os.getenv("API_URL", "https://quanlykho-backend1.onrender.com")

st.set_page_config(page_title="Quản lý kho AMME THE", layout="wide")

# ===== API =====
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
    return requests.post(f"{API_URL}/{endpoint}", json=payload)

def api_put(endpoint, payload=None):
    return requests.put(f"{API_URL}/{endpoint}", json=payload)

def api_delete(endpoint):
    return requests.delete(f"{API_URL}/{endpoint}")

# ===== HELPERS =====
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

def show_df(df, msg):
    if df.empty:
        st.info(msg)
    else:
        st.dataframe(df, use_container_width=True)

def get_row(df, sku):
    row = df[df["sku"] == sku]
    return row.iloc[0] if not row.empty else None

# ===== UI =====
st.title("📦 Quản lý kho AMME THE")

menu = st.sidebar.radio("Menu", [
    "Kho tổng", "Nhập/Xuất", "Chuyển kho",
    "Sản phẩm", "Thêm sản phẩm",
    "Cảnh báo tồn kho",   # 👈 thêm dòng này
    "Lịch sử", "PDF"
])

# ===== SẢN PHẨM =====
if menu == "Sản phẩm":
    with st.spinner("Đang tải..."):
        df = to_df(api_get("products"))

    if df.empty:
        st.warning("Không có dữ liệu")
        st.stop()

    df_active = filter_active(df)
    df_deleted = filter_deleted(df)

    st.subheader("🟢 Hoạt động")
    show_df(df_active, "Chưa có sản phẩm")

    st.subheader("🔴 Đã xóa")
    if not df_deleted.empty:
        sel = st.selectbox("Phục hồi", df_deleted["sku"] + " - " + df_deleted["name"], key="recover")
        sku = sel.split(" - ")[0]
        if st.button("♻️ Phục hồi"):
            api_post(f"products/{sku}/recover")
            st.toast("Đã phục hồi", icon="✅")
            st.rerun()
    else:
        st.info("Không có")

    st.subheader("✏️ Sửa / 🗑 Xóa")
    if not df_active.empty:
        sel = st.selectbox("Chọn", df_active["sku"] + " - " + df_active["name"], key="edit")
        sku = sel.split(" - ")[0]

        row = get_row(df_active, sku)
        if row is None:
            st.error("Không tìm thấy")
            st.stop()

        new_name = st.text_input("Tên mới", row["name"])

        col1, col2 = st.columns(2)

        with col1:
            if st.button("💾 Cập nhật"):
                api_put(f"products/{sku}", {"sku": sku, "name": new_name})
                st.toast("Đã cập nhật", icon="✅")
                st.rerun()

        with col2:
            confirm = st.checkbox("Xác nhận", key="confirm")
            if st.button("🗑 Xóa"):
                if confirm:
                    api_delete(f"products/{sku}")
                    st.toast("Đã xóa", icon="🗑")
                    st.rerun()
                else:
                    st.warning("Cần xác nhận")

# ===== THÊM =====
elif menu == "Thêm sản phẩm":
    sku = st.text_input("SKU")
    name = st.text_input("Tên")

    if st.button("Thêm"):
        if not sku or not name:
            st.warning("Nhập đủ")
        else:
            api_post("products", {"sku": sku, "name": name})
            st.toast("Đã thêm", icon="✅")
            st.rerun()

# ===== KHO =====
elif menu == "Kho tổng":
    df = to_df(api_get("inventory"))
    if df.empty:
        st.warning("Không có dữ liệu")
    else:
        for wh in df['warehouse'].unique():
            st.subheader(f"📦 {wh}")
            st.dataframe(df[df['warehouse'] == wh], use_container_width=True)

# ===== NHẬP/XUẤT =====
elif menu == "Nhập/Xuất":
    df_prod = filter_active(to_df(api_get("products")))
    df_wh = to_df(api_get("warehouses"))

    if df_prod.empty or df_wh.empty:
        st.warning("Thiếu dữ liệu")
        st.stop()

    sku = st.selectbox("Sản phẩm", df_prod["sku"] + " - " + df_prod["name"])
    sku = sku.split(" - ")[0]

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
        st.toast("Thành công", icon="✅")

# ===== CHUYỂN =====
elif menu == "Chuyển kho":
    df_prod = filter_active(to_df(api_get("products")))
    df_wh = to_df(api_get("warehouses"))

    sku = st.selectbox("Sản phẩm", df_prod["sku"] + " - " + df_prod["name"])
    sku = sku.split(" - ")[0]

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

            st.toast("Đã chuyển", icon="🚚")

# ===== CẢNH BÁO TỒN KHO =====
elif menu == "Cảnh báo tồn kho":
    st.title("⚠️ Cảnh báo tồn kho")

    col1, col2 = st.columns([1,2])

    with col1:
        threshold = st.number_input("Ngưỡng cảnh báo", min_value=1, value=10)

    with col2:
        st.info("Hiển thị sản phẩm có tồn kho dưới ngưỡng")

    # ===== LOAD DATA =====
    with st.spinner("Đang kiểm tra tồn kho..."):
        data = api_get(f"inventory/low-stock?threshold={threshold}")

    df = to_df(data)

    if df.empty:
        st.success("✅ Tất cả sản phẩm đều đủ hàng")
        st.stop()

    # ===== KPI =====
    st.subheader("📊 Tổng quan")

    col1, col2, col3 = st.columns(3)

    col1.metric("Sản phẩm sắp hết", len(df))
    col2.metric("Kho bị ảnh hưởng", df["warehouse"].nunique())
    col3.metric("Số lượng thấp nhất", df["quantity"].min())

    # ===== FILTER =====
    st.subheader("🔎 Lọc theo kho")

    warehouses = ["Tất cả"] + sorted(df["warehouse"].unique().tolist())
    selected_wh = st.selectbox("Chọn kho", warehouses)

    if selected_wh != "Tất cả":
        df = df[df["warehouse"] == selected_wh]

    # ===== HIGHLIGHT TABLE =====
    st.subheader("📋 Danh sách cảnh báo")

    def highlight(row):
        if row["quantity"] <= threshold * 0.5:
            return ["background-color: red; color: white"] * len(row)
        elif row["quantity"] < threshold:
            return ["background-color: orange"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df.style.apply(highlight, axis=1),
        use_container_width=True
    )

    # ===== LIST WARNING =====
    st.subheader("🚨 Cảnh báo chi tiết")

    for _, row in df.iterrows():
        if row["quantity"] <= threshold * 0.5:
            st.error(f"{row['sku']} - {row['name']} | {row['warehouse']} | Còn: {row['quantity']}")
        else:
            st.warning(f"{row['sku']} - {row['name']} | {row['warehouse']} | Còn: {row['quantity']}")

    # ===== QUICK ACTION =====
    st.subheader("⚡ Nhập hàng nhanh")

    sku_list = df["sku"] + " - " + df["name"]
    selected = st.selectbox("Chọn sản phẩm cần nhập", sku_list)

    sku = selected.split(" - ")[0]

    qty = st.number_input("Số lượng nhập thêm", min_value=1, value=10)

    if st.button("➕ Nhập ngay"):
        # tìm warehouse đầu tiên
        wh = df[df["sku"] == sku].iloc[0]["warehouse"]
        df_wh = to_df(api_get("warehouses"))
        wh_id = int(df_wh[df_wh["name"] == wh]["id"].values[0])

        api_post("transaction", {
            "sku": sku,
            "type": "Nhập",
            "quantity": qty,
            "warehouse_id": wh_id
        })

        st.toast("✅ Đã nhập hàng", icon="📦")
        st.rerun()
# ===== LỊCH SỬ =====
elif menu == "Lịch sử":
    df = to_df(api_get("history"))
    show_df(df, "Không có dữ liệu")

# ===== PDF =====
elif menu == "PDF":
    df = filter_active(to_df(api_get("products")))
    if df.empty:
        st.warning("Không có sản phẩm")
        st.stop()

    sku = st.selectbox("Sản phẩm", df["sku"] + " - " + df["name"])
    sku = sku.split(" - ")[0]

    qty = st.number_input("Qty", 1)
    t = st.selectbox("Type", ["Nhập", "Xuất"])

    if st.button("Tạo PDF"):
        buffer = BytesIO()
        c = canvas.Canvas(buffer)
        c.drawString(100, 800, f"PHIẾU {t.upper()}")
        c.drawString(100, 780, f"SKU: {sku}")
        c.drawString(100, 760, f"Số lượng: {qty}")
        c.drawString(100, 740, pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'))
        c.save()
        buffer.seek(0)

        st.download_button("Download", buffer, f"{sku}.pdf")
