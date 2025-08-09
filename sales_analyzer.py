import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import seaborn as sns
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import jieba
from wordcloud import WordCloud
import re
from collections import Counter

class SalesAnalyzer:
    def __init__(self):
        self.data = None
        
    def load_data(self, file):
        """加载CSV数据"""
        try:
            self.data = pd.read_csv(file)
            # 数据预处理
            self.preprocess_data()
            return True
        except Exception as e:
            st.error(f"数据加载失败: {str(e)}")
            return False
    
    def preprocess_data(self):
        """数据预处理"""
        if self.data is None:
            return
            
        # 转换日期格式
        date_columns = ['首咨时间', '最后回访时间', '报名时间']
        for col in date_columns:
            if col in self.data.columns:
                self.data[col] = pd.to_datetime(self.data[col], errors='coerce')
        
        # 处理空值
        self.data['学员姓名'] = self.data['学员姓名'].fillna('未命名')
        self.data['报名课程'] = self.data['报名课程'].fillna('未报名')
        self.data['报名金额'] = pd.to_numeric(self.data['报名金额'], errors='coerce')
        
        # 创建衍生字段
        self.data['是否报名'] = self.data['报名时间'].notna()
        self.data['跟进天数'] = (self.data['最后回访时间'] - self.data['首咨时间']).dt.days
        
        # 提取销售部门
        self.data['销售部门'] = self.data['所属销售'].str.extract(r'创客(.*?)部')
        
    def get_basic_stats(self):
        """获取基础统计信息"""
        if self.data is None:
            return {}
            
        total_leads = len(self.data)
        converted_leads = self.data['是否报名'].sum()
        conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0
        total_revenue = self.data['报名金额'].sum()
        avg_follow_times = self.data['回访次数'].mean()
        
        return {
            '总线索数': total_leads,
            '已报名数': converted_leads,
            '转化率': f"{conversion_rate:.2f}%",
            '总收入': f"¥{total_revenue:,.0f}" if pd.notna(total_revenue) else "¥0",
            '平均回访次数': f"{avg_follow_times:.1f}"
        }
    
    def calculate_channel_priority(self):
        """计算渠道优先级评分"""
        if self.data is None:
            return pd.DataFrame()
        
        # 按渠道统计基础数据
        channel_stats = self.data.groupby('学员来源').agg({
            '学员id': 'count',
            '是否报名': 'sum',
            '报名金额': 'sum',
            '回访次数': 'mean',
            '客户分级': lambda x: (x.isin(['A', 'B'])).sum()  # 高质量线索数
        }).round(2)
        
        # 计算各项指标
        channel_stats['转化率'] = (channel_stats['是否报名'] / channel_stats['学员id'] * 100).round(2)
        channel_stats['平均客单价'] = (channel_stats['报名金额'] / channel_stats['是否报名']).fillna(0).round(2)
        channel_stats['高质量线索率'] = (channel_stats['客户分级'] / channel_stats['学员id'] * 100).round(2)
        
        # 计算优先级评分 (满分100分)
        # 转化率权重40%，平均客单价权重30%，高质量线索率权重20%，线索数量权重10%
        max_conversion = channel_stats['转化率'].max() if channel_stats['转化率'].max() > 0 else 1
        max_price = channel_stats['平均客单价'].max() if channel_stats['平均客单价'].max() > 0 else 1
        max_quality = channel_stats['高质量线索率'].max() if channel_stats['高质量线索率'].max() > 0 else 1
        max_leads = channel_stats['学员id'].max() if channel_stats['学员id'].max() > 0 else 1
        
        channel_stats['优先级评分'] = (
            (channel_stats['转化率'] / max_conversion * 40) +
            (channel_stats['平均客单价'] / max_price * 30) +
            (channel_stats['高质量线索率'] / max_quality * 20) +
            (channel_stats['学员id'] / max_leads * 10)
        ).round(1)
        
        # 重命名列
        channel_stats.columns = ['线索数', '报名数', '总收入', '平均回访次数', '高质量线索数', 
                               '转化率(%)', '平均客单价', '高质量线索率(%)', '优先级评分']
        
        return channel_stats.sort_values('优先级评分', ascending=False)
    
    def calculate_channel_weights(self):
        """计算渠道权重分配"""
        if self.data is None:
            return pd.DataFrame()
        
        # 获取渠道统计数据
        channel_stats = self.data.groupby('学员来源').agg({
            '学员id': 'count',
            '是否报名': 'sum',
            '报名金额': 'sum'
        })
        
        # 计算转化率
        channel_stats['转化率'] = (channel_stats['是否报名'] / channel_stats['学员id'] * 100).round(2)
        
        # 计算权重分配（基于转化率）
        total_conversion_rate = channel_stats['转化率'].sum()
        if total_conversion_rate > 0:
            channel_stats['建议权重(%)'] = (channel_stats['转化率'] / total_conversion_rate * 100).round(1)
        else:
            channel_stats['建议权重(%)'] = 0
        
        # 生成调整建议
        def get_adjustment_advice(row):
            if row['转化率'] >= 1.0:
                return f"高效渠道，建议增加投入 (转化率{row['转化率']}%)"
            elif row['转化率'] >= 0.5:
                return f"中等效果，保持现状 (转化率{row['转化率']}%)"
            else:
                return f"效果较低，建议优化或减少投入 (转化率{row['转化率']}%)"
        
        channel_stats['调整建议'] = channel_stats.apply(get_adjustment_advice, axis=1)
        
        # 重命名列
        channel_stats.columns = ['线索数', '报名数', '总收入', '转化率(%)', '建议权重(%)', '调整建议']
        
        return channel_stats.sort_values('建议权重(%)', ascending=False)

def show_overview(analyzer):
    """显示总体概览"""
    st.header("📊 总体概览")
    
    data = analyzer.data
    
    # 关键指标卡片
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_leads = len(data)
        st.metric("总线索数", f"{total_leads:,}")
    
    with col2:
        converted = data['是否报名'].sum()
        conversion_rate = (converted / total_leads * 100) if total_leads > 0 else 0
        st.metric("转化率", f"{conversion_rate:.2f}%")
    
    with col3:
        total_revenue = data['报名金额'].sum()
        st.metric("总收入", f"¥{total_revenue:,.0f}" if pd.notna(total_revenue) else "¥0")
    
    with col4:
        avg_follow = data['回访次数'].mean()
        st.metric("平均回访次数", f"{avg_follow:.1f}")
    
    st.markdown("---")
    
    # 图表展示
    col1, col2 = st.columns(2)
    
    with col1:
        # 客户分级分布
        grade_dist = data['客户分级'].value_counts()
        fig = px.pie(
            values=grade_dist.values, 
            names=grade_dist.index,
            title="客户分级分布"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # 线索来源分布
        source_dist = data['学员来源'].value_counts().head(10)
        fig = px.bar(
            x=source_dist.values,
            y=source_dist.index,
            orientation='h',
            title="线索来源TOP10"
        )
        fig.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig, use_container_width=True)

def show_lead_quality_analysis(analyzer):
    """线索质量分析"""
    st.header("🎯 线索质量分析")
    
    data = analyzer.data
    
    # 客户分级转化率分析
    st.subheader("📊 客户分级转化效果")
    
    grade_conversion = data.groupby('客户分级').agg({
        '学员id': 'count',
        '是否报名': 'sum',
        '回访次数': 'mean',
        '报名金额': 'sum'
    }).round(2)
    
    grade_conversion['转化率'] = (grade_conversion['是否报名'] / grade_conversion['学员id'] * 100).round(2)
    grade_conversion.columns = ['线索数', '报名数', '平均回访次数', '总收入', '转化率(%)']
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.dataframe(grade_conversion, use_container_width=True)
    
    with col2:
        # 转化率对比图
        fig = px.bar(
            x=grade_conversion.index,
            y=grade_conversion['转化率(%)'],
            title="各级别客户转化率对比",
            color=grade_conversion['转化率(%)'],
            color_continuous_scale='viridis'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # 回访次数与转化关系
    st.subheader("📞 回访次数与转化关系")
    
    follow_conversion = data.groupby('回访次数').agg({
        '学员id': 'count',
        '是否报名': 'sum'
    })
    follow_conversion['转化率'] = (follow_conversion['是否报名'] / follow_conversion['学员id'] * 100).round(2)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=follow_conversion.index,
        y=follow_conversion['学员id'],
        name='线索数',
        yaxis='y'
    ))
    fig.add_trace(go.Scatter(
        x=follow_conversion.index,
        y=follow_conversion['转化率'],
        mode='lines+markers',
        name='转化率(%)',
        yaxis='y2',
        line=dict(color='red', width=3)
    ))
    
    fig.update_layout(
        title='回访次数与转化率关系',
        xaxis_title='回访次数',
        yaxis=dict(title='线索数', side='left'),
        yaxis2=dict(title='转化率(%)', side='right', overlaying='y'),
        legend=dict(x=0.7, y=1)
    )
    
    st.plotly_chart(fig, use_container_width=True)

def show_channel_analysis(analyzer):
    """渠道效果分析"""
    st.header("📺 渠道效果分析")
    
    data = analyzer.data
    
    # 渠道整体效果
    st.subheader("🎯 渠道整体效果对比")
    
    channel_stats = data.groupby('学员来源').agg({
        '学员id': 'count',
        '是否报名': 'sum',
        '回访次数': 'mean',
        '报名金额': 'sum'
    }).round(2)
    
    channel_stats['转化率'] = (channel_stats['是否报名'] / channel_stats['学员id'] * 100).round(2)
    channel_stats['平均客单价'] = (channel_stats['报名金额'] / channel_stats['是否报名']).round(2)
    channel_stats.columns = ['线索数', '报名数', '平均回访次数', '总收入', '转化率(%)', '平均客单价']
    
    # 按线索数排序
    channel_stats = channel_stats.sort_values('线索数', ascending=False)
    
    st.dataframe(channel_stats, use_container_width=True)
    
    # 渠道效果矩阵图
    col1, col2 = st.columns(2)
    
    with col1:
        fig = px.scatter(
            channel_stats,
            x='线索数',
            y='转化率(%)',
            size='总收入',
            hover_name=channel_stats.index,
            title='渠道效果矩阵 (气泡大小=总收入)',
            labels={'线索数': '线索数量', '转化率(%)': '转化率(%)'}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # 主播效果分析
        if '主播' in data.columns:
            broadcaster_stats = data[data['主播'].notna()].groupby('主播').agg({
                '学员id': 'count',
                '是否报名': 'sum'
            })
            broadcaster_stats['转化率'] = (broadcaster_stats['是否报名'] / broadcaster_stats['学员id'] * 100).round(2)
            broadcaster_stats = broadcaster_stats[broadcaster_stats['学员id'] >= 10].sort_values('转化率', ascending=False).head(10)
            
            fig = px.bar(
                x=broadcaster_stats['转化率'],
                y=broadcaster_stats.index,
                orientation='h',
                title='主播转化率TOP10 (线索数≥10)',
                labels={'x': '转化率(%)', 'y': '主播'}
            )
            fig.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
    
    # 渠道-销售分配分析
    st.subheader("🔄 渠道线索分配分析")
    st.markdown("分析不同渠道的线索都分给了哪些销售，以及各销售在不同渠道的表现")
    
    # 创建渠道-销售交叉分析表
    channel_sales_pivot = data.pivot_table(
        index='学员来源',
        columns='所属销售',
        values='学员id',
        aggfunc='count',
        fill_value=0
    )
    
    # 只显示线索数较多的渠道和销售
    top_channels = data['学员来源'].value_counts().head(5).index
    top_sales = data['所属销售'].value_counts().head(10).index
    
    filtered_pivot = channel_sales_pivot.loc[top_channels, top_sales]
    
    # 显示热力图
    col1, col2 = st.columns([2, 1])
    
    with col1:
        fig = px.imshow(
            filtered_pivot.values,
            x=filtered_pivot.columns,
            y=filtered_pivot.index,
            aspect="auto",
            title="渠道-销售线索分配热力图 (TOP5渠道 × TOP10销售)",
            labels=dict(x="销售人员", y="线索来源", color="线索数量")
        )
        fig.update_xaxes(tickangle=45)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # 选择特定渠道查看详细分配
        selected_channel = st.selectbox(
            "选择渠道查看详细分配:",
            options=top_channels,
            key="channel_select"
        )
        
        if selected_channel:
            channel_detail = data[data['学员来源'] == selected_channel].groupby('所属销售').agg({
                '学员id': 'count',
                '是否报名': 'sum'
            })
            channel_detail['转化率(%)'] = (channel_detail['是否报名'] / channel_detail['学员id'] * 100).round(2)
            channel_detail.columns = ['线索数', '报名数', '转化率(%)']
            channel_detail = channel_detail.sort_values('线索数', ascending=False).head(10)
            
            st.markdown(f"**{selected_channel}** 渠道分配详情:")
            st.dataframe(channel_detail, use_container_width=True)
    
    # 销售在不同渠道的表现对比
    st.subheader("👤 销售人员跨渠道表现分析")
    
    # 选择销售人员
    top_sales_list = data['所属销售'].value_counts().head(8).index.tolist()
    selected_sales = st.selectbox(
        "选择销售人员查看跨渠道表现:",
        options=top_sales_list,
        key="sales_select"
    )
    
    if selected_sales:
        sales_channel_stats = data[data['所属销售'] == selected_sales].groupby('学员来源').agg({
            '学员id': 'count',
            '是否报名': 'sum',
            '回访次数': 'mean'
        }).round(2)
        
        sales_channel_stats['转化率(%)'] = (sales_channel_stats['是否报名'] / sales_channel_stats['学员id'] * 100).round(2)
        sales_channel_stats.columns = ['线索数', '报名数', '平均回访次数', '转化率(%)']
        sales_channel_stats = sales_channel_stats[sales_channel_stats['线索数'] >= 3].sort_values('转化率(%)', ascending=False)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"**{selected_sales}** 在各渠道的表现:")
            st.dataframe(sales_channel_stats, use_container_width=True)
        
        with col2:
            if len(sales_channel_stats) > 0:
                fig = px.bar(
                    x=sales_channel_stats.index,
                    y=sales_channel_stats['转化率(%)'],
                    title=f"{selected_sales} 各渠道转化率对比",
                    labels={'x': '渠道', 'y': '转化率(%)'}
                )
                fig.update_xaxes(tickangle=45)
                st.plotly_chart(fig, use_container_width=True)
    
    # 渠道优先级排序分析
    st.subheader("🎯 渠道优先级排序")
    st.markdown("基于转化率、客单价、线索质量等多维度计算渠道优先级评分")
    
    priority_data = analyzer.calculate_channel_priority()
    
    if not priority_data.empty:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # 显示优先级排序表
            st.dataframe(priority_data, use_container_width=True)
        
        with col2:
            # 优先级分布饼图
            def get_priority_level(score):
                if score >= 70:
                    return "高优先级 (≥70分)"
                elif score >= 50:
                    return "中优先级 (50-70分)"
                else:
                    return "低优先级 (<50分)"
            
            priority_levels = priority_data['优先级评分'].apply(get_priority_level).value_counts()
            
            fig = px.pie(
                values=priority_levels.values,
                names=priority_levels.index,
                title="渠道优先级分布",
                color_discrete_map={
                    "高优先级 (≥70分)": "#2E8B57",
                    "中优先级 (50-70分)": "#FFD700", 
                    "低优先级 (<50分)": "#DC143C"
                }
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # 优先级评分雷达图
        st.subheader("📊 TOP5渠道多维度对比")
        
        top5_channels = priority_data.head(5)
        
        if len(top5_channels) > 0:
            # 创建雷达图数据
            categories = ['转化率(%)', '平均客单价', '高质量线索率(%)', '线索数']
            
            fig = go.Figure()
            
            colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7']
            
            for i, (channel, row) in enumerate(top5_channels.iterrows()):
                # 标准化数据到0-100范围
                values = [
                    min(row['转化率(%)'] * 20, 100),  # 转化率*20
                    min(row['平均客单价'] / 100, 100),  # 客单价/100
                    row['高质量线索率(%)'],
                    min(row['线索数'] / top5_channels['线索数'].max() * 100, 100)  # 线索数标准化
                ]
                
                fig.add_trace(go.Scatterpolar(
                    r=values,
                    theta=categories,
                    fill='toself',
                    name=channel,
                    line_color=colors[i % len(colors)]
                ))
            
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 100]
                    )),
                showlegend=True,
                title="TOP5渠道多维度对比雷达图"
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    # 智能权重分配
    st.subheader("⚖️ 智能权重分配建议")
    st.markdown("基于转化率数据自动计算最优权重分配方案")
    
    weight_data = analyzer.calculate_channel_weights()
    
    if not weight_data.empty:
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.dataframe(weight_data, use_container_width=True)
        
        with col2:
            # 权重分配饼图
            fig = px.pie(
                values=weight_data['建议权重(%)'],
                names=weight_data.index,
                title="建议权重分配",
                hover_data=['转化率(%)']
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # 权重调整对比
        st.subheader("📈 权重调整效果预测")
        
        # 假设当前是平均分配
        current_weight = 100 / len(weight_data)
        weight_comparison = weight_data.copy()
        weight_comparison['当前权重(%)'] = current_weight
        weight_comparison['权重变化'] = weight_comparison['建议权重(%)'] - current_weight
        weight_comparison['预期收益变化'] = (weight_comparison['权重变化'] * weight_comparison['转化率(%)'] / 100).round(2)
        
        # 显示权重调整对比图
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            name='当前权重',
            x=weight_comparison.index,
            y=weight_comparison['当前权重(%)'],
            marker_color='lightblue'
        ))
        
        fig.add_trace(go.Bar(
            name='建议权重',
            x=weight_comparison.index,
            y=weight_comparison['建议权重(%)'],
            marker_color='darkblue'
        ))
        
        fig.update_layout(
            title='权重分配对比：当前 vs 建议',
            xaxis_title='渠道',
            yaxis_title='权重(%)',
            barmode='group'
        )
        fig.update_xaxes(tickangle=45)
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 显示调整建议摘要
        st.subheader("💡 调整建议摘要")
        
        high_priority = weight_data[weight_data['转化率(%)'] >= 1.0]
        low_priority = weight_data[weight_data['转化率(%)'] < 0.5]
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "高效渠道数量", 
                len(high_priority),
                f"建议权重: {high_priority['建议权重(%)'].sum():.1f}%"
            )
        
        with col2:
            st.metric(
                "低效渠道数量", 
                len(low_priority),
                f"建议权重: {low_priority['建议权重(%)'].sum():.1f}%"
            )
        
        with col3:
            total_improvement = weight_comparison['预期收益变化'].sum()
            st.metric(
                "预期收益提升", 
                f"{total_improvement:.2f}%",
                "基于权重调整"
            )

def show_sales_team_analysis(analyzer):
    """销售团队分析"""
    st.header("👥 销售团队分析")
    
    data = analyzer.data
    
    # 销售人员业绩排行
    st.subheader("🏆 销售人员业绩排行")
    
    sales_stats = data.groupby('所属销售').agg({
        '学员id': 'count',
        '是否报名': 'sum',
        '回访次数': 'mean',
        '报名金额': 'sum',
        '跟进天数': 'mean'
    }).round(2)
    
    sales_stats['转化率'] = (sales_stats['是否报名'] / sales_stats['学员id'] * 100).round(2)
    sales_stats.columns = ['分配线索数', '报名数', '平均回访次数', '总收入', '平均跟进天数', '转化率(%)']
    
    # 筛选线索数>=10的销售
    sales_stats_filtered = sales_stats[sales_stats['分配线索数'] >= 10].sort_values('转化率(%)', ascending=False)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.dataframe(sales_stats_filtered.head(15), use_container_width=True)
    
    with col2:
        # 销售部门对比
        if '销售部门' in data.columns:
            dept_stats = data[data['销售部门'].notna()].groupby('销售部门').agg({
                '学员id': 'count',
                '是否报名': 'sum'
            })
            dept_stats['转化率'] = (dept_stats['是否报名'] / dept_stats['学员id'] * 100).round(2)
            
            fig = px.pie(
                values=dept_stats['学员id'],
                names=dept_stats.index,
                title="各部门线索分配"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # 销售效率分析
    st.subheader("⚡ 销售效率分析")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 回访次数 vs 转化率
        fig = px.scatter(
            sales_stats_filtered,
            x='平均回访次数',
            y='转化率(%)',
            size='分配线索数',
            hover_name=sales_stats_filtered.index,
            title='销售效率分析 (回访次数 vs 转化率)',
            labels={'平均回访次数': '平均回访次数', '转化率(%)': '转化率(%)'}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # 跟进天数 vs 转化率
        fig = px.scatter(
            sales_stats_filtered,
            x='平均跟进天数',
            y='转化率(%)',
            size='分配线索数',
            hover_name=sales_stats_filtered.index,
            title='跟进周期 vs 转化率',
            labels={'平均跟进天数': '平均跟进天数', '转化率(%)': '转化率(%)'}
        )
        st.plotly_chart(fig, use_container_width=True)

def show_time_trend_analysis(analyzer):
    """时间趋势分析"""
    st.header("📈 时间趋势分析")
    
    data = analyzer.data
    
    # 日期范围选择
    if '首咨时间' in data.columns and data['首咨时间'].notna().any():
        min_date = data['首咨时间'].min().date()
        max_date = data['首咨时间'].max().date()
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("开始日期", min_date)
        with col2:
            end_date = st.date_input("结束日期", max_date)
        
        # 筛选数据
        mask = (data['首咨时间'].dt.date >= start_date) & (data['首咨时间'].dt.date <= end_date)
        filtered_data = data[mask]
        
        # 每日线索趋势
        st.subheader("📅 每日线索趋势")
        
        daily_stats = filtered_data.groupby(filtered_data['首咨时间'].dt.date).agg({
            '学员id': 'count',
            '是否报名': 'sum'
        })
        daily_stats['转化率'] = (daily_stats['是否报名'] / daily_stats['学员id'] * 100).round(2)
        
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        fig.add_trace(
            go.Bar(x=daily_stats.index, y=daily_stats['学员id'], name="线索数"),
            secondary_y=False,
        )
        
        fig.add_trace(
            go.Scatter(x=daily_stats.index, y=daily_stats['转化率'], 
                      mode='lines+markers', name="转化率(%)", line=dict(color='red')),
            secondary_y=True,
        )
        
        fig.update_xaxes(title_text="日期")
        fig.update_yaxes(title_text="线索数", secondary_y=False)
        fig.update_yaxes(title_text="转化率(%)", secondary_y=True)
        fig.update_layout(title_text="每日线索数量与转化率趋势")
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 星期分析
        st.subheader("📊 星期效果分析")
        
        filtered_data['星期'] = filtered_data['首咨时间'].dt.day_name()
        weekday_stats = filtered_data.groupby('星期').agg({
            '学员id': 'count',
            '是否报名': 'sum'
        })
        weekday_stats['转化率'] = (weekday_stats['是否报名'] / weekday_stats['学员id'] * 100).round(2)
        
        # 重新排序星期
        weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        weekday_stats = weekday_stats.reindex([day for day in weekday_order if day in weekday_stats.index])
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.bar(
                x=weekday_stats.index,
                y=weekday_stats['学员id'],
                title="各星期线索数量"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = px.bar(
                x=weekday_stats.index,
                y=weekday_stats['转化率'],
                title="各星期转化率",
                color=weekday_stats['转化率'],
                color_continuous_scale='viridis'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # 内容热词分析
        st.subheader("🔥 热门内容分析")
        
        if '报名意向备注' in data.columns:
            # 提取所有备注文本
            all_text = ' '.join(filtered_data['报名意向备注'].dropna().astype(str))
            
            # 使用jieba分词
            words = jieba.lcut(all_text)
            
            # 过滤停用词和短词
            stop_words = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
            words = [word for word in words if len(word) > 1 and word not in stop_words and word.isalpha()]
            
            # 统计词频
            word_freq = Counter(words)
            top_words = word_freq.most_common(20)
            
            if top_words:
                col1, col2 = st.columns(2)
                
                with col1:
                    # 词频柱状图
                    words_df = pd.DataFrame(top_words, columns=['词语', '频次'])
                    fig = px.bar(
                        words_df,
                        x='频次',
                        y='词语',
                        orientation='h',
                        title='热门关键词TOP20'
                    )
                    fig.update_layout(yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    # 显示词频表
                    st.dataframe(words_df, use_container_width=True)
    
    else:
        st.warning("数据中没有有效的时间字段，无法进行时间趋势分析")

def main():
    st.set_page_config(
        page_title="销售线索分析工具",
        page_icon="📊",
        layout="wide"
    )
    
    st.title("🎯 销售线索分析工具")
    st.markdown("### 📅 最后更新：2025年8月8日 - 新增功能演示")
    st.markdown("---")
    
    analyzer = SalesAnalyzer()
    
    # 侧边栏 - 文件上传
    with st.sidebar:
        st.header("📁 数据导入")
        uploaded_file = st.file_uploader(
            "选择CSV文件",
            type=['csv'],
            help="请上传从CRM导出的线索数据CSV文件"
        )
        
        if uploaded_file is not None:
            if analyzer.load_data(uploaded_file):
                st.success("✅ 数据加载成功!")
                
                # 显示数据基本信息
                st.subheader("📋 数据概览")
                stats = analyzer.get_basic_stats()
                for key, value in stats.items():
                    st.metric(key, value)
    
    # 主界面
    if analyzer.data is not None:
        # 创建标签页
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 总体概览", 
            "🎯 线索质量分析", 
            "📺 渠道效果分析", 
            "👥 销售团队分析", 
            "📈 时间趋势分析"
        ])
        
        with tab1:
            show_overview(analyzer)
        
        with tab2:
            show_lead_quality_analysis(analyzer)
            
        with tab3:
            show_channel_analysis(analyzer)
            
        with tab4:
            show_sales_team_analysis(analyzer)
            
        with tab5:
            show_time_trend_analysis(analyzer)
    
    else:
        st.info("👆 请在左侧上传CSV数据文件开始分析")

if __name__ == "__main__":
    main()