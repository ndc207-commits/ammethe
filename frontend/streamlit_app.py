import streamlit as st
import pandas as pd
import requests
import os

API_URL = os.getenv("API_URL", "https://quanlykho-backend1.onrender.com")

def api(method, endpoint, **kwargs):
    return requests.request(method, f"{API_URL}/{endpoint}", **kwargs).json()

@st.cache_data(ttl=30)
def fetch(ep):
    r = api("GET", ep)
    return pd.DataFrame(r) if isinstance(r, list) else pd.DataFrame()

st.title("📦 QUẢN LÝ KHO")

menu = st.sidebar.radio("Menu", [
    "Kho tổng",
    "Nhập/Xuất",
    "Chuyển kho",
    "Sản phẩm",
    "Tìm kiếm",
    "Cảnh báo tồn kho",
    "Lịch sử",
    "PDF"
])

# ===== KHO =====
if menu == "Kho tổng":
    df = fetch("inventory")

    warehouses = ["La Pagode", "Muse", "Metz Ville", "Nancy"]
    tabs = st.tabs(warehouses)

    for i, wh in enumerate(warehouses):
        with tabs[i]:
            st.subheader(f"Kho: {wh}")
            st.dataframe(df[df["warehouse"] == wh], use_container_width=True)

# ===== NHẬP XUẤT =====
elif menu == "Nhập/Xuất":
    df_prod = fetch("products")
    df_wh = fetch("warehouses")

    sku = st.selectbox("Sản phẩm", df_prod["sku"] + " - " + df_prod["name"]).split(" - ")[0]
    wh = st.selectbox("Kho", df_wh["name"])
    wh_id = int(df_wh[df_wh["name"] == wh]["id"].values[0])

    t = st.radio("Loại", ["Nhập", "Xuất"])
    qty = st.number_input("Số lượng", 1)

    if st.button("OK"):
        api("POST", "transaction", json={
            "sku": sku,
            "type": t,
            "quantity": qty,
            "warehouse_id": wh_id
        })
        st.success("OK")
        st.cache_data.clear()
        st.rerun()

# ===== CHUYỂN KHO =====
elif menu == "Chuyển kho":
    df_prod = fetch("products")
    df_wh = fetch("warehouses")

    sku = st.selectbox("Sản phẩm", df_prod["sku"] + " - " + df_prod["name"]).split(" - ")[0]

    from_wh = st.selectbox("Từ kho", df_wh["name"])
    to_wh = st.selectbox("Đến kho", df_wh["name"])

    qty = st.number_input("Số lượng", 1)

    if st.button("Chuyển"):
        api("POST", "transfer", json={
            "sku": sku,
            "from_warehouse_id": int(df_wh[df_wh["name"] == from_wh]["id"].values[0]),
            "to_warehouse_id": int(df_wh[df_wh["name"] == to_wh]["id"].values[0]),
            "quantity": qty
        })
        st.success("OK")
        st.cache_data.clear()
        st.rerun()

# ===== SẢN PHẨM (CRUD + RECOVER) =====
elif menu == "Sản phẩm":
    df = fetch("products")

    active = df[df["is_active"] == True]
    deleted = df[df["is_active"] == False]

    # ===== ACTIVE =====
    st.subheader("🟢 Sản phẩm đang hoạt động")
    st.dataframe(active, use_container_width=True)

    # ===== DELETED =====
    st.subheader("🔴 Sản phẩm đã xóa")

    if not deleted.empty:
        sel_deleted = st.selectbox(
            "Chọn sản phẩm phục hồi",
            deleted["sku"] + " - " + deleted["name"]
        )

        sku_del = sel_deleted.split(" - ")[0]

        if st.button("♻️ Phục hồi"):
            requests.post(f"{API_URL}/products/{sku_del}/recover")
            st.success("Đã phục hồi")
            st.cache_data.clear()
            st.rerun()

    st.divider()

    # ===== EDIT / DELETE =====
    st.subheader("✏️ Sửa / 🗑 Xóa sản phẩm")

    if not active.empty:
        sel_active = st.selectbox(
            "Chọn sản phẩm",
            active["sku"] + " - " + active["name"]
        )

        sku = sel_active.split(" - ")[0]
        current_name = active[active["sku"] == sku]["name"].values[0]

        new_name = st.text_input("Tên mới", current_name)

        col1, col2 = st.columns(2)

        with col1:
            if st.button("💾 Cập nhật"):
                requests.put(
                    f"{API_URL}/products/{sku}",
                    json={"sku": sku, "name": new_name}
                )
                st.success("Đã cập nhật")
                st.cache_data.clear()
                st.rerun()

        with col2:
            confirm = st.checkbox("Xác nhận xóa")

            if st.button("🗑 Xóa"):
                if not confirm:
                    st.warning("Cần xác nhận trước khi xóa")
                else:
                    requests.delete(f"{API_URL}/products/{sku}")
                    st.success("Đã xóa")
                    st.cache_data.clear()
                    st.rerun()

# ===== SEARCH =====
elif menu == "Tìm kiếm":
    q = st.text_input("Search")
    if q:
        st.dataframe(fetch(f"products/search?q={q}"))

# ===== LOW STOCK =====
elif menu == "Cảnh báo tồn kho":
    t = st.number_input("Threshold", 1, 100, 10)
    st.dataframe(fetch(f"inventory/low-stock?threshold={t}"))

# ===== HISTORY =====
elif menu == "Lịch sử":
    st.dataframe(fetch("history"), use_container_width=True)

# ===== PDF =====
elif menu == "PDF":
    df_prod = fetch("products")

    sku = st.selectbox("Sản phẩm", df_prod["sku"] + " - " + df_prod["name"]).split(" - ")[0]
    qty = st.number_input("Qty", 1)
    t = st.selectbox("Type", ["Nhập", "Xuất"])

    if st.button("Download"):
        url = f"{API_URL}/invoice/pdf?sku={sku}&qty={qty}&type={t}"
        st.markdown(f"[Download PDF]({url})")
