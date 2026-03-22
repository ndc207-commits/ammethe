import streamlit as st
import pandas as pd
import requests
import os

API_URL = os.getenv("API_URL", "https://quanlykho-backend1.onrender.com")

# Hàm gọi API với token (JWT)
def api(method, endpoint, token=None, **kwargs):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        r = requests.request(method, f"{API_URL}/{endpoint}", headers=headers, **kwargs)
        if r.status_code == 200:
            return r.json()
        return []
    except:
        return []

# ====== Hàm lấy token từ session ======
def get_token():
    token = st.session_state.get("token", None)
    return token

# ====== Hàm đăng nhập và lấy token ======
def login():
    st.subheader("Đăng nhập")
    username = st.text_input("Tên người dùng")
    password = st.text_input("Mật khẩu", type="password")

    if st.button("Đăng nhập"):
        res = requests.post(f"{API_URL}/token", data={"username": username, "password": password})
        if res.status_code == 200:
            st.session_state["token"] = res.json().get("access_token")
            st.success("Đăng nhập thành công!")
            st.experimental_rerun()  # Reload lại ứng dụng
        else:
            st.error("Đăng nhập thất bại!")

# ====== Nếu chưa có token, yêu cầu đăng nhập ======
if "token" not in st.session_state:
    login()  # Nếu chưa đăng nhập, hiển thị trang đăng nhập
else:
    # Sau khi đăng nhập thành công, hiển thị các menu
    menu = st.sidebar.radio("Menu", [
        "Kho tổng",
        "Nhập/Xuất",
        "Chuyển kho",
        "Sản phẩm",
        "Thêm sản phẩm",
        "Tìm kiếm",
        "Cảnh báo tồn kho",
        "Lịch sử",
        "PDF"
    ])

    token = get_token()  # Lấy token từ session

    # ====== SẢN PHẨM (CRUD + Recover) =====
    if menu == "Sản phẩm":
        df = api("GET", "products", token=token)
        
        # Sản phẩm đang hoạt động
        active = [prod for prod in df if prod["is_active"] == True]
        # Sản phẩm đã bị xóa
        deleted = [prod for prod in df if prod["is_active"] == False]
        
        st.subheader("🟢 Sản phẩm đang hoạt động")
        if active:
            active_df = pd.DataFrame(active)
            st.dataframe(active_df, use_container_width=True)
        else:
            st.warning("Không có sản phẩm nào.")

        st.subheader("🔴 Sản phẩm đã xóa")
        if deleted:
            deleted_df = pd.DataFrame(deleted)
            sel_deleted = st.selectbox("Chọn sản phẩm phục hồi", deleted_df["sku"] + " - " + deleted_df["name"])

            sku_del = sel_deleted.split(" - ")[0]

            if st.button("♻️ Phục hồi"):
                requests.post(f"{API_URL}/products/{sku_del}/recover")
                st.success("Đã phục hồi")
                st.cache_data.clear()
                st.rerun()
        else:
            st.warning("Không có sản phẩm đã xóa.")

        st.divider()

        # ====== Sửa / Xóa sản phẩm ======
        st.subheader("✏️ Sửa / 🗑 Xóa sản phẩm")
        if active:
            sel_active = st.selectbox("Chọn sản phẩm", active_df["sku"] + " - " + active_df["name"])
            sku = sel_active.split(" - ")[0]
            current_name = active_df[active_df["sku"] == sku]["name"].values[0]

            new_name = st.text_input("Tên mới", current_name)

            col1, col2 = st.columns(2)

            with col1:
                if st.button("💾 Cập nhật"):
                    requests.put(f"{API_URL}/products/{sku}", json={"sku": sku, "name": new_name})
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

    # ====== THÊM SẢN PHẨM =====
    elif menu == "Thêm sản phẩm":
        st.subheader("➕ Thêm sản phẩm mới")

        sku = st.text_input("SKU")
        name = st.text_input("Tên sản phẩm")

        if st.button("Thêm"):
            if not sku or not name:
                st.warning("⚠️ Nhập đầy đủ thông tin")
            else:
                res = requests.post(f"{API_URL}/products", json={"sku": sku, "name": name})

                if res.status_code == 200:
                    st.success("✅ Thêm thành công")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"Lỗi: {res.text}")

    # ====== KHO =====
    elif menu == "Kho tổng":
        df = api("GET", "inventory", token=token)
        warehouses = ["La Pagode", "Muse", "Metz Ville", "Nancy"]
        tabs = st.tabs(warehouses)

        for i, wh in enumerate(warehouses):
            with tabs[i]:
                st.subheader(f"Kho: {wh}")
                if df:
                    st.dataframe(pd.DataFrame(df)[df['warehouse'] == wh], use_container_width=True)
                else:
                    st.warning("Không có dữ liệu")

    # ====== NHẬP XUẤT =====
    elif menu == "Nhập/Xuất":
        df_prod = api("GET", "products", token=token)
        df_wh = api("GET", "warehouses", token=token)

        if "is_active" in df_prod:
            df_prod = pd.DataFrame(df_prod)[df_prod["is_active"] == True]

        if not df_prod or not df_wh:
            st.warning("Không có dữ liệu")
        else:
            options = df_prod["sku"] + " - " + df_prod["name"]
            selected = st.selectbox("Sản phẩm", options)

            if selected:
                sku = selected.split(" - ")[0]
                wh = st.selectbox("Kho", [wh["name"] for wh in df_wh])
                wh_id = df_wh[df_wh["name"] == wh].iloc[0]["id"]

                t = st.radio("Loại", ["Nhập", "Xuất"])
                qty = st.number_input("Số lượng", 1)

                if st.button("OK"):
                    api("POST", "transaction", token=token, json={
                        "sku": sku,
                        "type": t,
                        "quantity": qty,
                        "warehouse_id": wh_id
                    })
                    st.success("OK")
                    st.cache_data.clear()
                    st.rerun()

    # ====== TÌM KIẾM =====
    elif menu == "Tìm kiếm":
        q = st.text_input("Tìm kiếm theo SKU hoặc tên sản phẩm")
        if q:
            df = api("GET", f"products/search?q={q}", token=token)
            st.dataframe(pd.DataFrame(df))

    # ====== CẢNH BÁO TỒN KHO =====
    elif menu == "Cảnh báo tồn kho":
        threshold = st.number_input("Ngưỡng tồn kho", min_value=1, max_value=100, value=10)
        df = api("GET", f"inventory/low-stock?threshold={threshold}", token=token)
        if df:
            st.dataframe(pd.DataFrame(df))
        else:
            st.success("Không có sản phẩm nào dưới ngưỡng tồn kho.")

    # ====== LỊCH SỬ =====
    elif menu == "Lịch sử":
        df = api("GET", "history", token=token)
        st.dataframe(pd.DataFrame(df))

    # ====== PDF =====
    elif menu == "PDF":
        df_prod = api("GET", "products", token=token)

        options = df_prod["sku"] + " - " + df_prod["name"]
        selected = st.selectbox("Sản phẩm", options)

        if selected:
            sku = selected.split(" - ")[0]

            qty = st.number_input("Qty", 1)
            t = st.selectbox("Type", ["Nhập", "Xuất"])

            if st.button("Download"):
                url = f"{API_URL}/invoice/pdf?sku={sku}&qty={qty}&type={t}"
                st.markdown(f"[Download PDF]({url})")
