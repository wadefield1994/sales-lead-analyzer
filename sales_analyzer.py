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
    
    def calculate_sales_priority(self):
        """计算销售人员优先级评分"""
        if self.data is None:
            return pd.DataFrame()
        
        # 按销售人员统计基础数据
        sales_stats = self.data.groupby('所属销售').agg({
            '学员id': 'count',
            '是否报名': 'sum',
            '报名金额': 'sum',
            '回访次数': 'mean',
            '跟进天数': 'mean',
            '客户分级': lambda x: (x.isin(['A', 'B'])).sum()  # 高质量线索数
        }).round(2)
        
        # 只分析线索数>=10的销售
        sales_stats = sales_stats[sales_stats['学员id'] >= 10]
        
        if sales_stats.empty:
            return pd.DataFrame()
        
        # 计算各项指标
        sales_stats['转化率'] = (sales_stats['是否报名'] / sales_stats['学员id'] * 100).round(2)
        sales_stats['平均客单价'] = (sales_stats['报名金额'] / sales_stats['是否报名']).fillna(0).round(2)
        sales_stats['高质量线索率'] = (sales_stats['客户分级'] / sales_stats['学员id'] * 100).round(2)
        
        # 计算处理效率指标（跟进天数越少越好，回访次数适中最好）
        sales_stats['跟进效率'] = (1 / (sales_stats['跟进天数'] + 1) * 100).round(2)  # 转换为正向指标
        sales_stats['回访效率'] = (100 - abs(sales_stats['回访次数'] - 3) * 10).clip(0, 100).round(2)  # 3次回访为最佳
        
        # 计算优先级评分 (满分100分)
        # 转化率35%，客单价25%，跟进效率20%，回访效率10%，高质量线索率10%
        max_conversion = sales_stats['转化率'].max() if sales_stats['转化率'].max() > 0 else 1
        max_price = sales_stats['平均客单价'].max() if sales_stats['平均客单价'].max() > 0 else 1
        max_follow_eff = sales_stats['跟进效率'].max() if sales_stats['跟进效率'].max() > 0 else 1
        max_call_eff = sales_stats['回访效率'].max() if sales_stats['回访效率'].max() > 0 else 1
        max_quality = sales_stats['高质量线索率'].max() if sales_stats['高质量线索率'].max() > 0 else 1
        
        sales_stats['优先级评分'] = (
            (sales_stats['转化率'] / max_conversion * 35) +
            (sales_stats['平均客单价'] / max_price * 25) +
            (sales_stats['跟进效率'] / max_follow_eff * 20) +
            (sales_stats['回访效率'] / max_call_eff * 10) +
            (sales_stats['高质量线索率'] / max_quality * 10)
        ).round(1)
        
        # 重命名列
        sales_stats.columns = ['分配线索数', '报名数', '总收入', '平均回访次数', '平均跟进天数', '高质量线索数',
                              '转化率(%)', '平均客单价', '高质量线索率(%)', '跟进效率', '回访效率', '优先级评分']
        
        return sales_stats.sort_values('优先级评分', ascending=False)
    
    def get_sales_channel_match(self):
        """分析销售-渠道匹配度"""
        if self.data is None:
            return pd.DataFrame()
        
        # 计算每个销售在每个渠道的表现
        sales_channel_performance = []
        
        for sales in self.data['所属销售'].unique():
            sales_data = self.data[self.data['所属销售'] == sales]
            
            for channel in sales_data['学员来源'].unique():
                channel_data = sales_data[sales_data['学员来源'] == channel]
                
                if len(channel_data) >= 5:  # 至少5个线索才有统计意义
                    conversion_rate = (channel_data['是否报名'].sum() / len(channel_data) * 100)
                    avg_revenue = channel_data['报名金额'].sum() / len(channel_data) if len(channel_data) > 0 else 0
                    
                    sales_channel_performance.append({
                        '销售人员': sales,
                        '渠道': channel,
                        '线索数': len(channel_data),
                        '转化率': round(conversion_rate, 2),
                        '平均收入': round(avg_revenue, 2)
                    })
        
        if not sales_channel_performance:
            return pd.DataFrame()
        
        performance_df = pd.DataFrame(sales_channel_performance)
        
        # 计算匹配度评分
        performance_df['匹配度评分'] = (
            performance_df['转化率'] * 0.6 + 
            (performance_df['平均收入'] / performance_df['平均收入'].max() * 100) * 0.4
        ).round(1)
        
        return performance_df.sort_values('匹配度评分', ascending=False)
    
    def generate_intelligent_recommendations(self):
        """生成智能推荐建议"""
        if self.data is None:
            return {}
        
        recommendations = {
            'channel_optimization': [],
            'sales_optimization': [],
            'resource_allocation': [],
            'strategic_suggestions': []
        }
        
        # 渠道优化建议
        channel_priority = self.calculate_channel_priority()
        if not channel_priority.empty:
            # 高优先级渠道建议
            high_priority_channels = channel_priority[channel_priority['优先级评分'] >= 70]
            if not high_priority_channels.empty:
                for channel, row in high_priority_channels.iterrows():
                    recommendations['channel_optimization'].append({
                        'type': '渠道扩展',
                        'channel': channel,
                        'priority': '高',
                        'suggestion': f"建议增加{channel}渠道投入，当前转化率{row['转化率(%)']}%，优先级评分{row['优先级评分']}分",
                        'expected_impact': f"预计可提升整体转化率{row['转化率(%)'] * 0.1:.2f}%"
                    })
            
            # 低优先级渠道建议
            low_priority_channels = channel_priority[channel_priority['优先级评分'] < 50]
            if not low_priority_channels.empty:
                for channel, row in low_priority_channels.head(3).iterrows():
                    recommendations['channel_optimization'].append({
                        'type': '渠道优化',
                        'channel': channel,
                        'priority': '中',
                        'suggestion': f"{channel}渠道效果较低，转化率仅{row['转化率(%)']}%，建议优化投放策略或减少投入",
                        'expected_impact': f"优化后预计可节省成本20-30%"
                    })
        
        # 销售优化建议
        sales_priority = self.calculate_sales_priority()
        if not sales_priority.empty:
            # 优秀销售推广建议
            top_sales = sales_priority.head(3)
            for sales, row in top_sales.iterrows():
                recommendations['sales_optimization'].append({
                    'type': '经验推广',
                    'sales': sales,
                    'priority': '高',
                    'suggestion': f"{sales.split('-')[-1]}表现优秀，转化率{row['转化率(%)']}%，建议分享经验给团队",
                    'expected_impact': "预计可提升团队整体转化率10-15%"
                })
            
            # 待提升销售建议
            low_performance_sales = sales_priority[sales_priority['优先级评分'] < 50]
            for sales, row in low_performance_sales.head(3).iterrows():
                training_needs = []
                if row['转化率(%)'] < 1.0:
                    training_needs.append("转化技巧")
                if row['跟进效率'] < 50:
                    training_needs.append("时间管理")
                if row['回访效率'] < 60:
                    training_needs.append("客户沟通")
                
                recommendations['sales_optimization'].append({
                    'type': '培训提升',
                    'sales': sales,
                    'priority': '中',
                    'suggestion': f"{sales.split('-')[-1]}需要{', '.join(training_needs)}培训，当前转化率{row['转化率(%)']}%",
                    'expected_impact': f"培训后预计转化率可提升至{row['转化率(%)'] * 1.5:.1f}%"
                })
        
        # 资源分配建议
        match_data = self.get_sales_channel_match()
        if not match_data.empty:
            # 最佳匹配推荐
            top_matches = match_data.head(5)
            for _, row in top_matches.iterrows():
                recommendations['resource_allocation'].append({
                    'type': '最优匹配',
                    'combination': f"{row['销售人员'].split('-')[-1]} × {row['渠道']}",
                    'priority': '高',
                    'suggestion': f"建议将更多{row['渠道']}线索分配给{row['销售人员'].split('-')[-1]}，匹配度评分{row['匹配度评分']}",
                    'expected_impact': f"预计转化率可达{row['转化率']}%"
                })
        
        # 战略建议
        total_conversion = (self.data['是否报名'].sum() / len(self.data) * 100)
        total_revenue = self.data['报名金额'].sum()
        
        if total_conversion < 1.0:
            recommendations['strategic_suggestions'].append({
                'type': '整体优化',
                'priority': '高',
                'suggestion': f"整体转化率{total_conversion:.2f}%偏低，建议从线索质量和销售技能两方面同时提升",
                'expected_impact': "综合优化后预计转化率可提升至1.5-2.0%"
            })
        
        if not channel_priority.empty:
            high_priority_revenue_ratio = (
                channel_priority[channel_priority['优先级评分'] >= 70]['总收入'].sum() / 
                channel_priority['总收入'].sum()
            )
            if high_priority_revenue_ratio < 0.6:
                recommendations['strategic_suggestions'].append({
                    'type': '资源重分配',
                    'priority': '中',
                    'suggestion': f"高优先级渠道收入占比仅{high_priority_revenue_ratio*100:.1f}%，建议调整资源分配",
                    'expected_impact': "重分配后预计整体收入可提升15-25%"
                })
        
        return recommendations
    
    def generate_performance_report(self):
        """生成绩效报告"""
        if self.data is None:
            return {}
        
        # 基础数据统计
        total_leads = len(self.data)
        converted_leads = self.data['是否报名'].sum()
        total_revenue = self.data['报名金额'].sum()
        conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0
        
        # 渠道分析
        channel_stats = self.calculate_channel_priority()
        top_channel = channel_stats.index[0] if not channel_stats.empty else "无数据"
        top_channel_conversion = channel_stats.iloc[0]['转化率(%)'] if not channel_stats.empty else 0
        
        # 销售分析
        sales_stats = self.calculate_sales_priority()
        top_sales = sales_stats.index[0] if not sales_stats.empty else "无数据"
        top_sales_conversion = sales_stats.iloc[0]['转化率(%)'] if not sales_stats.empty else 0
        
        # 时间分析
        if '首咨时间' in self.data.columns:
            date_range = f"{self.data['首咨时间'].min().strftime('%Y-%m-%d')} 至 {self.data['首咨时间'].max().strftime('%Y-%m-%d')}"
            daily_avg = total_leads / (self.data['首咨时间'].max() - self.data['首咨时间'].min()).days if (self.data['首咨时间'].max() - self.data['首咨时间'].min()).days > 0 else 0
        else:
            date_range = "无时间数据"
            daily_avg = 0
        
        report = {
            'summary': {
                '分析时间范围': date_range,
                '总线索数': f"{total_leads:,}",
                '总转化数': f"{converted_leads:,}",
                '整体转化率': f"{conversion_rate:.2f}%",
                '总收入': f"¥{total_revenue:,.0f}",
                '日均线索': f"{daily_avg:.1f}条"
            },
            'top_performers': {
                '最佳渠道': f"{top_channel} (转化率{top_channel_conversion:.2f}%)",
                '最佳销售': f"{top_sales.split('-')[-1] if '-' in str(top_sales) else top_sales} (转化率{top_sales_conversion:.2f}%)"
            },
            'insights': []
        }
        
        # 生成洞察
        if conversion_rate > 2.0:
            report['insights'].append("✅ 整体转化率表现优秀，超过2%")
        elif conversion_rate > 1.0:
            report['insights'].append("⚠️ 整体转化率良好，但仍有提升空间")
        else:
            report['insights'].append("❌ 整体转化率偏低，需要重点优化")
        
        if not channel_stats.empty:
            high_priority_count = len(channel_stats[channel_stats['优先级评分'] >= 70])
            if high_priority_count >= 3:
                report['insights'].append(f"✅ 拥有{high_priority_count}个高优先级渠道，渠道质量良好")
            else:
                report['insights'].append(f"⚠️ 仅有{high_priority_count}个高优先级渠道，建议优化渠道策略")
        
        if not sales_stats.empty:
            excellent_sales_count = len(sales_stats[sales_stats['优先级评分'] >= 70])
            total_sales_count = len(sales_stats)
            if excellent_sales_count / total_sales_count > 0.3:
                report['insights'].append(f"✅ {excellent_sales_count}/{total_sales_count}销售表现优秀，团队整体水平较高")
            else:
                report['insights'].append(f"⚠️ 仅{excellent_sales_count}/{total_sales_count}销售表现优秀，建议加强培训")
        
        return report

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
    
    # 渠道优先级统计
    st.subheader("🎯 渠道优先级统计")
    
    priority_data = analyzer.calculate_channel_priority()
    
    if not priority_data.empty:
        # 定义优先级分级函数
        def get_priority_level(score):
            if score >= 70:
                return "高优先级"
            elif score >= 50:
                return "中优先级"
            else:
                return "低优先级"
        
        # 计算各优先级的统计数据
        priority_data['优先级等级'] = priority_data['优先级评分'].apply(get_priority_level)
        
        priority_summary = priority_data.groupby('优先级等级').agg({
            '线索数': 'sum',
            '报名数': 'sum',
            '总收入': 'sum',
            '转化率(%)': 'mean'
        }).round(2)
        
        # 计算各优先级的渠道数量
        priority_counts = priority_data['优先级等级'].value_counts()
        priority_summary['渠道数量'] = priority_counts
        priority_summary['平均转化率(%)'] = priority_summary['转化率(%)']
        
        # 重新排列列顺序
        priority_summary = priority_summary[['渠道数量', '线索数', '报名数', '总收入', '平均转化率(%)']]
        
        # 按优先级排序
        priority_order = ['高优先级', '中优先级', '低优先级']
        priority_summary = priority_summary.reindex([p for p in priority_order if p in priority_summary.index])
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # 优先级分布统计表
            st.markdown("**优先级分布统计**")
            st.dataframe(priority_summary, use_container_width=True)
        
        with col2:
            # 优先级渠道数量分布
            fig = px.pie(
                values=priority_counts.values,
                names=priority_counts.index,
                title="渠道优先级分布",
                color_discrete_map={
                    "高优先级": "#2E8B57",
                    "中优先级": "#FFD700", 
                    "低优先级": "#DC143C"
                }
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col3:
            # 各优先级转化率对比
            fig = px.bar(
                x=priority_summary.index,
                y=priority_summary['平均转化率(%)'],
                title="各优先级平均转化率",
                color=priority_summary.index,
                color_discrete_map={
                    "高优先级": "#2E8B57",
                    "中优先级": "#FFD700", 
                    "低优先级": "#DC143C"
                }
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        
        # 优先级趋势分析
        st.subheader("📈 优先级资源分配分析")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 线索数量分配
            fig = px.bar(
                x=priority_summary.index,
                y=priority_summary['线索数'],
                title="各优先级线索数量分配",
                color=priority_summary.index,
                color_discrete_map={
                    "高优先级": "#2E8B57",
                    "中优先级": "#FFD700", 
                    "低优先级": "#DC143C"
                }
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # 收入贡献分配
            fig = px.bar(
                x=priority_summary.index,
                y=priority_summary['总收入'],
                title="各优先级收入贡献",
                color=priority_summary.index,
                color_discrete_map={
                    "高优先级": "#2E8B57",
                    "中优先级": "#FFD700", 
                    "低优先级": "#DC143C"
                }
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        
        # 关键指标卡片
        st.subheader("🔑 关键优先级指标")
        
        col1, col2, col3, col4 = st.columns(4)
        
        high_priority = priority_summary.loc['高优先级'] if '高优先级' in priority_summary.index else None
        total_channels = len(priority_data)
        total_leads = priority_summary['线索数'].sum()
        total_revenue = priority_summary['总收入'].sum()
        
        with col1:
            high_channel_count = high_priority['渠道数量'] if high_priority is not None else 0
            high_channel_pct = (high_channel_count / total_channels * 100) if total_channels > 0 else 0
            st.metric(
                "高优先级渠道", 
                f"{high_channel_count}个",
                f"{high_channel_pct:.1f}% 占比"
            )
        
        with col2:
            high_leads = high_priority['线索数'] if high_priority is not None else 0
            high_leads_pct = (high_leads / total_leads * 100) if total_leads > 0 else 0
            st.metric(
                "高优先级线索", 
                f"{high_leads:,.0f}条",
                f"{high_leads_pct:.1f}% 占比"
            )
        
        with col3:
            high_revenue = high_priority['总收入'] if high_priority is not None else 0
            high_revenue_pct = (high_revenue / total_revenue * 100) if total_revenue > 0 else 0
            st.metric(
                "高优先级收入", 
                f"¥{high_revenue:,.0f}",
                f"{high_revenue_pct:.1f}% 占比"
            )
        
        with col4:
            high_conversion = high_priority['平均转化率(%)'] if high_priority is not None else 0
            avg_conversion = priority_summary['平均转化率(%)'].mean()
            conversion_diff = high_conversion - avg_conversion
            st.metric(
                "高优先级转化率", 
                f"{high_conversion:.2f}%",
                f"+{conversion_diff:.2f}% vs平均"
            )
        
        # 优化建议
        st.subheader("💡 优化建议")
        
        if high_priority is not None:
            high_leads_ratio = high_leads / total_leads if total_leads > 0 else 0
            high_revenue_ratio = high_revenue / total_revenue if total_revenue > 0 else 0
            
            suggestions = []
            
            if high_leads_ratio < 0.5:
                suggestions.append("🔄 **资源重分配**: 高优先级渠道线索占比偏低，建议增加高优先级渠道的线索分配")
            
            if high_revenue_ratio > 0.7:
                suggestions.append("⭐ **效果优秀**: 高优先级渠道贡献了大部分收入，策略执行良好")
            
            if len(priority_data[priority_data['优先级等级'] == '低优先级']) > 0:
                low_priority_channels = priority_data[priority_data['优先级等级'] == '低优先级'].index.tolist()
                suggestions.append(f"⚠️ **关注低效渠道**: {', '.join(low_priority_channels[:3])} 等渠道需要优化或减少投入")
            
            if conversion_diff > 1:
                suggestions.append("📈 **扩大优势**: 高优先级渠道转化率显著高于平均水平，建议加大投入")
            
            for suggestion in suggestions:
                st.markdown(suggestion)
        
        else:
            st.info("暂无高优先级渠道，建议优化现有渠道策略")

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
    
    # 销售人员优先级评分
    st.subheader("🎯 销售人员优先级评分")
    st.markdown("基于转化率、客单价、跟进效率、回访效率等多维度计算销售优先级评分")
    
    sales_priority_data = analyzer.calculate_sales_priority()
    
    if not sales_priority_data.empty:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # 显示优先级评分表
            display_cols = ['分配线索数', '转化率(%)', '平均客单价', '跟进效率', '回访效率', '优先级评分']
            st.dataframe(sales_priority_data[display_cols], use_container_width=True)
        
        with col2:
            # 销售优先级分布
            def get_sales_priority_level(score):
                if score >= 70:
                    return "优秀销售 (≥70分)"
                elif score >= 50:
                    return "良好销售 (50-70分)"
                else:
                    return "待提升销售 (<50分)"
            
            sales_priority_levels = sales_priority_data['优先级评分'].apply(get_sales_priority_level).value_counts()
            
            fig = px.pie(
                values=sales_priority_levels.values,
                names=sales_priority_levels.index,
                title="销售人员优先级分布",
                color_discrete_map={
                    "优秀销售 (≥70分)": "#2E8B57",
                    "良好销售 (50-70分)": "#FFD700", 
                    "待提升销售 (<50分)": "#DC143C"
                }
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # TOP5销售多维度雷达图
        st.subheader("📊 TOP5销售多维度能力对比")
        
        top5_sales = sales_priority_data.head(5)
        
        if len(top5_sales) > 0:
            # 创建雷达图数据
            categories = ['转化率', '客单价', '跟进效率', '回访效率', '线索质量']
            
            fig = go.Figure()
            
            colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7']
            
            for i, (sales, row) in enumerate(top5_sales.iterrows()):
                # 标准化数据到0-100范围
                values = [
                    min(row['转化率(%)'] * 5, 100),  # 转化率*5
                    min(row['平均客单价'] / 100, 100),  # 客单价/100
                    row['跟进效率'],
                    row['回访效率'],
                    row['高质量线索率(%)']
                ]
                
                fig.add_trace(go.Scatterpolar(
                    r=values,
                    theta=categories,
                    fill='toself',
                    name=sales.split('-')[-1] if '-' in sales else sales,  # 简化显示名称
                    line_color=colors[i % len(colors)]
                ))
            
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 100]
                    )),
                showlegend=True,
                title="TOP5销售多维度能力雷达图"
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    # 销售-渠道匹配度分析
    st.subheader("🔗 销售-渠道匹配度分析")
    st.markdown("分析每个销售在不同渠道的表现，找出最佳匹配组合")
    
    match_data = analyzer.get_sales_channel_match()
    
    if not match_data.empty:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # 显示匹配度排行
            st.markdown("**最佳销售-渠道匹配TOP20**")
            st.dataframe(match_data.head(20), use_container_width=True)
        
        with col2:
            # 选择销售查看其渠道匹配情况
            sales_list = match_data['销售人员'].unique()
            selected_sales = st.selectbox(
                "选择销售查看渠道匹配:",
                options=sales_list,
                key="sales_match_select"
            )
            
            if selected_sales:
                sales_match = match_data[match_data['销售人员'] == selected_sales].sort_values('匹配度评分', ascending=False)
                
                fig = px.bar(
                    sales_match,
                    x='渠道',
                    y='匹配度评分',
                    title=f"{selected_sales.split('-')[-1]} 渠道匹配度",
                    color='匹配度评分',
                    color_continuous_scale='viridis'
                )
                fig.update_xaxes(tickangle=45)
                st.plotly_chart(fig, use_container_width=True)
        
        # 匹配度热力图
        st.subheader("🔥 销售-渠道匹配度热力图")
        
        # 创建透视表
        pivot_data = match_data.pivot_table(
            index='销售人员',
            columns='渠道',
            values='匹配度评分',
            fill_value=0
        )
        
        # 只显示TOP10销售和TOP5渠道
        top_sales = match_data.groupby('销售人员')['匹配度评分'].max().nlargest(10).index
        top_channels = match_data.groupby('渠道')['匹配度评分'].max().nlargest(5).index
        
        filtered_pivot = pivot_data.loc[
            [s for s in top_sales if s in pivot_data.index],
            [c for c in top_channels if c in pivot_data.columns]
        ]
        
        if not filtered_pivot.empty:
            fig = px.imshow(
                filtered_pivot.values,
                x=filtered_pivot.columns,
                y=[name.split('-')[-1] if '-' in name else name for name in filtered_pivot.index],
                aspect="auto",
                title="销售-渠道匹配度热力图 (TOP10销售 × TOP5渠道)",
                labels=dict(x="渠道", y="销售人员", color="匹配度评分"),
                color_continuous_scale='RdYlGn'
            )
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)
    
    # 销售培训建议
    st.subheader("📚 销售培训建议")
    
    if not sales_priority_data.empty:
        # 分析需要培训的销售
        low_performance_sales = sales_priority_data[sales_priority_data['优先级评分'] < 50]
        
        if not low_performance_sales.empty:
            st.markdown("**需要重点关注的销售人员：**")
            
            for sales, row in low_performance_sales.iterrows():
                suggestions = []
                
                if row['转化率(%)'] < 1.0:
                    suggestions.append("转化技巧培训")
                
                if row['跟进效率'] < 50:
                    suggestions.append("时间管理培训")
                
                if row['回访效率'] < 60:
                    suggestions.append("客户沟通培训")
                
                if row['高质量线索率(%)'] < 20:
                    suggestions.append("线索识别培训")
                
                if suggestions:
                    st.markdown(f"- **{sales.split('-')[-1] if '-' in sales else sales}**: {', '.join(suggestions)}")
        
        # 优秀销售经验分享
        top_performance_sales = sales_priority_data[sales_priority_data['优先级评分'] >= 70]
        
        if not top_performance_sales.empty:
            st.markdown("**优秀销售经验可供学习：**")
            
            for sales, row in top_performance_sales.head(3).iterrows():
                strengths = []
                
                if row['转化率(%)'] >= 2.0:
                    strengths.append(f"转化率{row['转化率(%)']}%")
                
                if row['跟进效率'] >= 80:
                    strengths.append("跟进高效")
                
                if row['回访效率'] >= 80:
                    strengths.append("沟通优秀")
                
                if strengths:
                    st.markdown(f"- **{sales.split('-')[-1] if '-' in sales else sales}**: {', '.join(strengths)}")
    
    else:
        st.info("数据量不足，无法进行销售优先级分析（需要每个销售至少10个线索）")

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
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📊 总体概览", 
            "🎯 线索质量分析", 
            "📺 渠道效果分析", 
            "👥 销售团队分析", 
            "📈 时间趋势分析",
            "🤖 智能推荐"
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
            
        with tab6:
            show_intelligent_recommendations(analyzer)
    
    else:
        st.info("👆 请在左侧上传CSV数据文件开始分析")

def show_intelligent_recommendations(analyzer):
    """显示智能推荐"""
    st.header("🤖 智能推荐引擎")
    st.markdown("基于数据分析结果，为您提供个性化的优化建议和策略推荐")
    
    data = analyzer.data
    
    # 生成推荐建议
    recommendations = analyzer.generate_intelligent_recommendations()
    
    # 生成绩效报告
    performance_report = analyzer.generate_performance_report()
    
    # 绩效报告摘要
    st.subheader("📋 绩效报告摘要")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # 关键指标展示
        summary = performance_report.get('summary', {})
        
        col1_1, col1_2, col1_3 = st.columns(3)
        
        with col1_1:
            st.metric("分析时间范围", summary.get('分析时间范围', '无数据'))
            st.metric("总线索数", summary.get('总线索数', '0'))
        
        with col1_2:
            st.metric("整体转化率", summary.get('整体转化率', '0%'))
            st.metric("总收入", summary.get('总收入', '¥0'))
        
        with col1_3:
            st.metric("日均线索", summary.get('日均线索', '0条'))
            
            top_performers = performance_report.get('top_performers', {})
            st.metric("最佳渠道", top_performers.get('最佳渠道', '无数据'))
    
    with col2:
        # 关键洞察
        st.markdown("**📊 关键洞察**")
        insights = performance_report.get('insights', [])
        for insight in insights:
            st.markdown(f"- {insight}")
    
    st.markdown("---")
    
    # 智能推荐建议
    st.subheader("💡 智能优化建议")
    
    # 创建推荐类别标签页
    rec_tab1, rec_tab2, rec_tab3, rec_tab4 = st.tabs([
        "🎯 渠道优化", "👥 销售提升", "⚖️ 资源分配", "📈 战略建议"
    ])
    
    with rec_tab1:
        st.markdown("### 渠道优化建议")
        channel_recs = recommendations.get('channel_optimization', [])
        
        if channel_recs:
            for i, rec in enumerate(channel_recs):
                priority_color = {"高": "🔴", "中": "🟡", "低": "🟢"}
                
                with st.expander(f"{priority_color.get(rec['priority'], '⚪')} {rec['type']}: {rec['channel']}"):
                    st.markdown(f"**建议**: {rec['suggestion']}")
                    st.markdown(f"**预期效果**: {rec['expected_impact']}")
                    st.markdown(f"**优先级**: {rec['priority']}")
        else:
            st.info("暂无渠道优化建议")
    
    with rec_tab2:
        st.markdown("### 销售团队提升建议")
        sales_recs = recommendations.get('sales_optimization', [])
        
        if sales_recs:
            for i, rec in enumerate(sales_recs):
                priority_color = {"高": "🔴", "中": "🟡", "低": "🟢"}
                
                with st.expander(f"{priority_color.get(rec['priority'], '⚪')} {rec['type']}: {rec['sales'].split('-')[-1] if '-' in rec['sales'] else rec['sales']}"):
                    st.markdown(f"**建议**: {rec['suggestion']}")
                    st.markdown(f"**预期效果**: {rec['expected_impact']}")
                    st.markdown(f"**优先级**: {rec['priority']}")
        else:
            st.info("暂无销售优化建议")
    
    with rec_tab3:
        st.markdown("### 资源分配优化")
        resource_recs = recommendations.get('resource_allocation', [])
        
        if resource_recs:
            for i, rec in enumerate(resource_recs):
                priority_color = {"高": "🔴", "中": "🟡", "低": "🟢"}
                
                with st.expander(f"{priority_color.get(rec['priority'], '⚪')} {rec['type']}: {rec['combination']}"):
                    st.markdown(f"**建议**: {rec['suggestion']}")
                    st.markdown(f"**预期效果**: {rec['expected_impact']}")
                    st.markdown(f"**优先级**: {rec['priority']}")
        else:
            st.info("暂无资源分配建议")
    
    with rec_tab4:
        st.markdown("### 战略发展建议")
        strategic_recs = recommendations.get('strategic_suggestions', [])
        
        if strategic_recs:
            for i, rec in enumerate(strategic_recs):
                priority_color = {"高": "🔴", "中": "🟡", "低": "🟢"}
                
                with st.expander(f"{priority_color.get(rec['priority'], '⚪')} {rec['type']}"):
                    st.markdown(f"**建议**: {rec['suggestion']}")
                    st.markdown(f"**预期效果**: {rec['expected_impact']}")
                    st.markdown(f"**优先级**: {rec['priority']}")
        else:
            st.info("暂无战略建议")
    
    # 行动计划生成器
    st.subheader("📅 行动计划生成器")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("**🎯 本月重点行动项**")
        
        # 收集高优先级建议
        high_priority_actions = []
        for category, recs in recommendations.items():
            for rec in recs:
                if rec.get('priority') == '高':
                    high_priority_actions.append({
                        'category': category,
                        'action': rec.get('suggestion', ''),
                        'type': rec.get('type', ''),
                        'target': rec.get('channel', rec.get('sales', rec.get('combination', '')))
                    })
        
        if high_priority_actions:
            for i, action in enumerate(high_priority_actions[:5], 1):
                st.markdown(f"{i}. **{action['type']}**: {action['action'][:100]}...")
        else:
            st.info("当前表现良好，暂无紧急行动项")
    
    with col2:
        st.markdown("**📈 预期收益预测**")
        
        # 简单的收益预测
        current_conversion = float(performance_report['summary']['整体转化率'].replace('%', ''))
        current_revenue = float(performance_report['summary']['总收入'].replace('¥', '').replace(',', ''))
        
        if high_priority_actions:
            # 假设实施高优先级建议可提升15-25%
            predicted_conversion = current_conversion * 1.2
            predicted_revenue = current_revenue * 1.2
            
            st.metric(
                "预测转化率提升", 
                f"{predicted_conversion:.2f}%",
                f"+{predicted_conversion - current_conversion:.2f}%"
            )
            st.metric(
                "预测收入提升", 
                f"¥{predicted_revenue:,.0f}",
                f"+¥{predicted_revenue - current_revenue:,.0f}"
            )
        else:
            st.info("保持当前策略，预期稳定增长")
    
    # 导出报告功能
    st.subheader("📤 导出分析报告")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 生成PDF报告", use_container_width=True):
            st.info("PDF报告生成功能开发中...")
    
    with col2:
        if st.button("📈 导出Excel数据", use_container_width=True):
            st.info("Excel导出功能开发中...")
    
    with col3:
        if st.button("📧 发送邮件报告", use_container_width=True):
            st.info("邮件发送功能开发中...")
    
    # 定期报告设置
    st.subheader("⏰ 定期报告设置")
    
    col1, col2 = st.columns(2)
    
    with col1:
        report_frequency = st.selectbox(
            "报告频率",
            ["每日", "每周", "每月", "自定义"],
            index=1
        )
        
        report_recipients = st.text_input(
            "接收邮箱",
            placeholder="输入邮箱地址，多个邮箱用逗号分隔"
        )
    
    with col2:
        report_time = st.time_input("发送时间", value=None)
        
        if st.button("💾 保存设置", use_container_width=True):
            st.success(f"已保存设置：{report_frequency}报告，发送时间{report_time}")
    
    # 历史建议追踪
    st.subheader("📚 历史建议追踪")
    st.info("历史建议追踪功能开发中，将记录每次建议的执行情况和效果...")

if __name__ == "__main__":
    main()