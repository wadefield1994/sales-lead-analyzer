import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.title("🎯 销售线索分析工具测试版")

# 简单测试
uploaded_file = st.file_uploader("选择CSV文件", type=['csv'])

if uploaded_file is not None:
    try:
        data = pd.read_csv(uploaded_file)
        st.success("✅ 数据加载成功!")
        st.write("数据预览:")
        st.dataframe(data.head())
        
        st.write("数据基本信息:")
        st.write(f"总行数: {len(data)}")
        st.write(f"总列数: {len(data.columns)}")
        st.write("列名:", list(data.columns))
        
    except Exception as e:
        st.error(f"数据加载失败: {str(e)}")
        st.write("错误详情:", e)