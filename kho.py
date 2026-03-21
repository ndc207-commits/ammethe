import streamlit as st
import pandas as pd
import requests

API_URL = "https://ammethe-backend.onrender.com"  # Thay URL FastAPI

@st.cache_data(ttl=30)
def get_products(): return pd.DataFrame(requests.get(f"{API_URL}/products").json())

@st.cache_data(ttl=30)
def get_deleted_products(): return pd.DataFrame(requests.get(f"{API_URL}/deleted_products").json())

@st.cache_data(ttl=30)
def get_stock(): return pd.DataFrame(requests.get(f"{API_URL}/stock").json())

@st.cache_data(ttl=30)
def get_store_stock(): return pd.DataFrame(requests.get(f"{API_URL}/store_stock").json())

@st.cache_data(ttl=60)
def get_warehouses(): return pd.DataFrame(requests.get(f"{API_URL}/warehouses").json())

@st.cache_data(ttl=60)
def get_stores(): return pd.DataFrame(requests.get(f"{API_URL}/stores").json())

@st.cache_data(ttl=60)
def get_history(): return pd.DataFrame(requests.get(f"{API_URL}/history").json())

st.title("📦 Quản lý kho AMME THE")
menu = st.sidebar.radio("Menu", ["Kho tổng","Kho cửa hàng","Sản phẩm","Nhập / Xuất","Lịch sử","Xuất Excel"])

if menu=="Kho tổng":
    df=get_stock()
    st.subheader("📦 Kho tổng")
    st.dataframe(df)
    st.bar_chart(df.groupby("kho")["so_luong"].sum())

elif menu=="Kho cửa hàng":
    df=get_store_stock()
    st.subheader("🏬 Kho cửa hàng")
    st.dataframe(df)
    st.bar_chart(df.groupby("cua_hang")["so_luong"].sum())

elif menu=="Sản phẩm":
    df=get_products()
    st.subheader("✏️ Sửa / 🗑 Xóa / ♻️ Phục hồi sản phẩm")
    if not df.empty:
        df["display"]=df["sku"]+" - "+df["name"]
        sel=st.selectbox("Chọn sản phẩm",df["display"])
        sku=df[df["display"]==sel]["sku"].values[0]

elif menu=="Nhập / Xuất":
    st.info("Dùng API FastAPI để xử lý nhập/xuất")

elif menu=="Lịch sử":
    df=get_history()
    st.subheader("📜 Lịch sử giao dịch")
    st.dataframe(df,use_container_width=True)

elif menu=="Xuất Excel":
    st.subheader("📥 Xuất lịch sử Excel")
    if st.button("Tải Excel"):
        r=requests.get(f"{API_URL}/export_history")
        with open("history.xlsx","wb") as f: f.write(r.content)
        with open("history.xlsx","rb") as f:
            st.download_button("Tải xuống",f,file_name="history.xlsx")
