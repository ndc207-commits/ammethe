import streamlit as st
import pandas as pd
import requests
import os

# ====== URL backend ======
API_URL = os.getenv("API_URL", "https://quanlykho-backend1.onrender.com")

# ====== Hàm gọi API với token ======
def api(method, endpoint, token=None, **kwargs):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        r = requests.request(method, f"{API_URL}/{endpoint}", headers=headers, **kwargs)
        if r.status_code in [200, 201]:
            return r.json()
        else:
            st.error(f"Lỗi API {r.status_code}: {r.text}")
            return []
    except Exception as e:
        st.error(f"Lỗi kết nối API: {e}")
        return []

# ====== Token ======
def get_token():
    return st.session_state.get("token", None)

# ====== Login ======
def login():
    st.subheader("Đăng nhập")
    username = st.text_input("Tên người dùng")
    password = st.text_input("Mật khẩu", type="password")
    if st.button("Đăng nhập"):
        res = requests.post(f"{API_URL}/token", data={"username": username, "password": password})
        if res.status_code in [200,201]:
            st.session_state["token"] = res.json().get("access_token")
            st.success("Đăng nhập thành công!")
            st.experimental_rerun()
        else:
            st.error("Đăng nhập thất bại!")

# ====== Main ======
if "token" not in st.session_state:
    login()
else:
    token = get_token()
    menu = st.sidebar.radio("Menu", [
        "Kho tổng", "Nhập/Xuất", "Sản phẩm", "Thêm sản phẩm",
        "Tìm kiếm", "Cảnh báo tồn kho", "Lịch sử", "PDF"
    ])

    # ====== SẢN PHẨM ======
    if menu == "Sản phẩm":
        df = pd.DataFrame(api("GET", "products", token=token))
        if df.empty:
            st.warning("Không có dữ liệu sản phẩm")
        else:
            df["sku"] = df["sku"].astype(str)
            df["name"] = df["name"].astype(str)
            active = df[df["is_active"]==True]
            deleted = df[df["is_active"]==False]

            st.subheader("🟢 Sản phẩm đang hoạt động")
            if not active.empty:
                st.dataframe(active, use_container_width=True)
            else:
                st.info("Chưa có sản phẩm nào")

            st.subheader("🔴 Sản phẩm đã xóa")
            if not deleted.empty:
                sel_deleted = st.selectbox("Chọn sản phẩm phục hồi",
                                           deleted["sku"] + " - " + deleted["name"])
                sku_del = sel_deleted.split(" - ")[0]
                if st.button("♻️ Phục hồi"):
                    api("POST", f"products/{sku_del}/recover", token=token)
                    st.success("Đã phục hồi")
                    st.experimental_rerun()
            else:
                st.info("Không có sản phẩm đã xóa")

            st.subheader("✏️ Sửa / 🗑 Xóa sản phẩm")
            if not active.empty:
                sel_active = st.selectbox("Chọn sản phẩm",
                                          active["sku"] + " - " + active["name"])
                sku = sel_active.split(" - ")[0]
                current_name = active[active["sku"]==sku]["name"].values[0]
                new_name = st.text_input("Tên mới", current_name)

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 Cập nhật"):
                        api("PUT", f"products/{sku}", token=token, json={"sku": sku, "name": new_name})
                        st.success("Đã cập nhật")
                        st.experimental_rerun()
                with col2:
                    confirm = st.checkbox("Xác nhận xóa")
                    if st.button("🗑 Xóa"):
                        if not confirm:
                            st.warning("Cần xác nhận")
                        else:
                            api("DELETE", f"products/{sku}", token=token)
                            st.success("Đã xóa")
                            st.experimental_rerun()

    # ====== Thêm sản phẩm ======
    elif menu == "Thêm sản phẩm":
        st.subheader("➕ Thêm sản phẩm mới")
        sku = st.text_input("SKU")
        name = st.text_input("Tên sản phẩm")
        if st.button("Thêm"):
            if not sku or not name:
                st.warning("Nhập đầy đủ thông tin")
            else:
                api("POST", "products", token=token, json={"sku": sku, "name": name})
                st.success("✅ Thêm thành công")
                st.experimental_rerun()

    # ====== Kho tổng ======
    elif menu == "Kho tổng":
        df = pd.DataFrame(api("GET", "inventory", token=token))
        if df.empty:
            st.warning("Không có dữ liệu kho")
        else:
            warehouses = df['warehouse'].unique()
            tabs = st.tabs(warehouses)
            for i, wh in enumerate(warehouses):
                with tabs[i]:
                    st.dataframe(df[df['warehouse']==wh], use_container_width=True)

    # ====== Nhập / Xuất ======
    elif menu == "Nhập/Xuất":
        df_prod = pd.DataFrame(api("GET","products",token=token))
        df_wh = pd.DataFrame(api("GET","warehouses",token=token))
        if df_prod.empty or df_wh.empty:
            st.warning("Không có dữ liệu")
        else:
            df_prod = df_prod[df_prod["is_active"]==True]
            sel = st.selectbox("Sản phẩm", df_prod["sku"] + " - " + df_prod["name"])
            sku = sel.split(" - ")[0]
            wh = st.selectbox("Kho", df_wh["name"])
            wh_id = int(df_wh[df_wh["name"]==wh]["id"].values[0])
            t = st.radio("Loại", ["Nhập", "Xuất"])
            qty = st.number_input("Số lượng", 1, step=1)
            if st.button("OK"):
                api("POST","transaction",token=token,json={
                    "sku":sku,"type":t,"quantity":qty,"warehouse_id":wh_id
                })
                st.success("✅ OK")
                st.experimental_rerun()

    # ====== Tìm kiếm ======
    elif menu=="Tìm kiếm":
        q = st.text_input("Tìm theo SKU hoặc tên")
        if q:
            df = pd.DataFrame(api("GET", f"products/search?q={q}", token=token))
            if not df.empty:
                st.dataframe(df)
            else:
                st.info("Không tìm thấy sản phẩm nào")

    # ====== Cảnh báo tồn kho ======
    elif menu=="Cảnh báo tồn kho":
        threshold = st.number_input("Ngưỡng tồn kho", min_value=1,value=10)
        df = pd.DataFrame(api("GET", f"inventory/low-stock?threshold={threshold}", token=token))
        if not df.empty:
            st.dataframe(df)
        else:
            st.info("Không có sản phẩm nào dưới ngưỡng tồn kho")

    # ====== Lịch sử ======
    elif menu=="Lịch sử":
        df = pd.DataFrame(api("GET","history",token=token))
        if not df.empty:
            st.dataframe(df)
        else:
            st.info("Không có lịch sử giao dịch")

    # ====== PDF ======
    elif menu=="PDF":
        df_prod = pd.DataFrame(api("GET","products",token=token))
        if df_prod.empty:
            st.warning("Không có sản phẩm nào")
        else:
            # kiểm tra tồn tại cột
            if "sku" in df_prod.columns and "name" in df_prod.columns:
                sel = st.selectbox("Sản phẩm", df_prod["sku"] + " - " + df_prod["name"])
                sku = sel.split(" - ")[0]
                qty = st.number_input("Số lượng",1,min_value=1)
                t = st.selectbox("Loại", ["Nhập","Xuất"])
                if st.button("Download PDF"):
                    url = f"{API_URL}/invoice/pdf?sku={sku}&qty={qty}&type={t}"
                    st.markdown(f"[Download PDF]({url})")
            else:
                st.error(f"Data sản phẩm không đúng: cột 'sku' hoặc 'name' bị thiếu. Có cột: {df_prod.columns.tolist()}")
