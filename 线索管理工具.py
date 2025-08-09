#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
销售线索优先级评分与异常预警系统
专为销售经理设计的线索管理工具
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class LeadScoringSystem:
    def __init__(self):
        self.channel_scores = {
            '抖音短视频平台': 35,
            '直播平台': 30,
            '创客网络销售': 25
        }
        
        self.grade_scores = {
            'A': 30, 'B': 25, 'C': 20, 
            'D': 15, 'E': 10, '其他': 5
        }
        
        self.followup_scores = {
            0: 0,
            1: 15,
            2: 15,
            3: 20,
            4: 20,
            5: 20,
            6: 15,
            7: 15,
            8: 10,
            9: 10,
            10: 5
        }
    
    def calculate_time_decay(self, first_consult_date):
        """计算时间衰减分数"""
        if pd.isna(first_consult_date):
            return 0
        
        try:
            if isinstance(first_consult_date, str):
                consult_date = pd.to_datetime(first_consult_date)
            else:
                consult_date = first_consult_date
            
            days_diff = (datetime.now() - consult_date).days
            
            if days_diff == 0:
                return 10
            elif days_diff <= 3:
                return 8
            elif days_diff <= 7:
                return 5
            else:
                return 0
        except:
            return 0
    
    def calculate_lead_score(self, row):
        """计算线索优先级分数"""
        score = 0
        
        # 渠道分数
        channel = str(row.get('学员来源', ''))
        score += self.channel_scores.get(channel, 20)
        
        # 客户分级分数
        grade = str(row.get('客户分级', ''))
        score += self.grade_scores.get(grade, 5)
        
        # 回访次数分数
        followup = row.get('回访次数', 0)
        if pd.isna(followup):
            followup = 0
        followup = min(int(followup), 10)
        score += self.followup_scores.get(followup, 0)
        
        # 时间衰减分数
        first_consult = row.get('首咨时间', '')
        score += self.calculate_time_decay(first_consult)
        
        return min(score, 100)
    
    def get_priority_level(self, score):
        """根据分数获取优先级等级"""
        if score >= 90:
            return "紧急跟进"
        elif score >= 70:
            return "优先跟进"
        elif score >= 50:
            return "常规跟进"
        else:
            return "低优先级"

class AlertSystem:
    def __init__(self):
        self.red_alerts = []
        self.orange_alerts = []
        self.yellow_alerts = []
    
    def check_high_value_no_followup(self, df):
        """检查高价值未回访线索"""
        high_value_grades = ['A', 'B', 'C']
        
        for _, row in df.iterrows():
            if (str(row.get('客户分级', '')) in high_value_grades and 
                (pd.isna(row.get('回访次数')) or row.get('回访次数', 0) == 0)):
                
                alert = {
                    '类型': '高价值未回访',
                    '级别': '红色预警',
                    '学员ID': row.get('学员id', ''),
                    '学员姓名': row.get('学员姓名', ''),
                    '客户分级': row.get('客户分级', ''),
                    '首咨时间': row.get('首咨时间', ''),
                    '所属销售': row.get('所属销售', ''),
                    '处理建议': '立即安排首次回访'
                }
                self.red_alerts.append(alert)
    
    def check_cold_leads(self, df):
        """检查冷却线索"""
        cutoff_date = datetime.now() - timedelta(days=3)
        
        for _, row in df.iterrows():
            last_followup = row.get('最后回访时间', '')
            followup_count = row.get('回访次数', 0)
            
            if (not pd.isna(followup_count) and followup_count > 0 and 
                not pd.isna(last_followup)):
                
                try:
                    last_date = pd.to_datetime(last_followup)
                    if last_date < cutoff_date:
                        alert = {
                            '类型': '热线索冷却',
                            '级别': '红色预警',
                            '学员ID': row.get('学员id', ''),
                            '学员姓名': row.get('学员姓名', ''),
                            '回访次数': followup_count,
                            '最后回访时间': last_followup,
                            '所属销售': row.get('所属销售', ''),
                            '处理建议': '立即重新激活跟进'
                        }
                        self.red_alerts.append(alert)
                except:
                    pass
    
    def check_unnamed_ratio(self, df):
        """检查未命名客户比例"""
        total_leads = len(df)
        unnamed_count = len(df[df['学员姓名'] == '未命名'])
        
        if total_leads > 0:
            ratio = (unnamed_count / total_leads) * 100
            if ratio > 30:
                alert = {
                    '类型': '命名异常',
                    '级别': '黄色预警',
                    '未命名比例': f"{ratio:.1f}%",
                    '影响分析': '影响后续精准跟进和客户体验',
                    '处理建议': '要求销售在首次沟通时获取真实姓名'
                }
                self.yellow_alerts.append(alert)
    
    def check_grade_distribution(self, df):
        """检查客户分级分布"""
        total_leads = len(df)
        other_count = len(df[df['客户分级'] == '其他'])
        
        if total_leads > 0:
            ratio = (other_count / total_leads) * 100
            if ratio > 30:
                alert = {
                    '类型': '分级异常',
                    '级别': '橙色预警',
                    '其他分级占比': f"{ratio:.1f}%",
                    '处理建议': '重新评估客户分级标准，加强销售培训'
                }
                self.orange_alerts.append(alert)
    
    def check_zombie_leads(self, df):
        """检查僵尸线索"""
        cutoff_date = datetime.now() - timedelta(days=7)
        
        for _, row in df.iterrows():
            last_update = row.get('最后回访时间', '') or row.get('首咨时间', '')
            
            if not pd.isna(last_update):
                try:
                    last_date = pd.to_datetime(last_update)
                    if last_date < cutoff_date and pd.isna(row.get('报名时间')):
                        alert = {
                            '类型': '僵尸线索',
                            '级别': '黄色预警',
                            '学员ID': row.get('学员id', ''),
                            '学员姓名': row.get('学员姓名', ''),
                            '最后更新': last_update,
                            '所属销售': row.get('所属销售', ''),
                            '处理建议': '评估是否放弃或重新激活'
                        }
                        self.yellow_alerts.append(alert)
                except:
                    pass
    
    def generate_all_alerts(self, df):
        """生成所有预警"""
        self.red_alerts.clear()
        self.orange_alerts.clear()
        self.yellow_alerts.clear()
        
        self.check_high_value_no_followup(df)
        self.check_cold_leads(df)
        self.check_unnamed_ratio(df)
        self.check_grade_distribution(df)
        self.check_zombie_leads(df)
        
        return {
            '红色预警': self.red_alerts,
            '橙色预警': self.orange_alerts,
            '黄色预警': self.yellow_alerts
        }

def analyze_leads(csv_file_path):
    """主分析函数"""
    print("🚀 开始分析销售线索数据...")
    
    # 读取数据
    try:
        df = pd.read_csv(csv_file_path)
        print(f"✅ 成功读取 {len(df)} 条线索数据")
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return
    
    # 初始化系统
    scoring_system = LeadScoringSystem()
    alert_system = AlertSystem()
    
    # 计算优先级分数
    print("📊 计算线索优先级分数...")
    df['优先级分数'] = df.apply(scoring_system.calculate_lead_score, axis=1)
    df['优先级等级'] = df['优先级分数'].apply(scoring_system.get_priority_level)
    
    # 生成预警
    print("⚠️  检查异常预警...")
    alerts = alert_system.generate_all_alerts(df)
    
    # 生成分析报告
    print("📈 生成分析报告...")
    
    # 优先级分布
    priority_stats = df['优先级等级'].value_counts()
    
    # 渠道分析
    channel_stats = df.groupby('学员来源').agg({
        '学员id': 'count',
        '优先级分数': 'mean'
    }).round(2)
    channel_stats.columns = ['线索数量', '平均分数']
    
    # 销售个人表现
    sales_stats = df.groupby('所属销售').agg({
        '学员id': 'count',
        '优先级分数': 'mean'
    }).round(2)
    sales_stats.columns = ['负责线索数', '平均线索质量']
    
    return {
        'data': df,
        'priority_stats': priority_stats,
        'channel_stats': channel_stats,
        'sales_stats': sales_stats,
        'alerts': alerts
    }

def generate_report(results, output_file='线索分析报告.xlsx'):
    """生成Excel报告"""
    print("💾 生成Excel报告...")
    
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # 线索数据（带分数）
        results['data'].to_excel(writer, sheet_name='线索数据', index=False)
        
        # 按优先级排序
        sorted_data = results['data'].sort_values('优先级分数', ascending=False)
        sorted_data.to_excel(writer, sheet_name='按优先级排序', index=False)
        
        # 预警信息
        for level, alerts in results['alerts'].items():
            if alerts:
                alert_df = pd.DataFrame(alerts)
                alert_df.to_excel(writer, sheet_name=f'{level}清单', index=False)
        
        # 统计分析
        results['priority_stats'].to_excel(writer, sheet_name='优先级统计')
        results['channel_stats'].to_excel(writer, sheet_name='渠道分析')
        results['sales_stats'].to_excel(writer, sheet_name='销售表现')
    
    print(f"✅ 报告已生成: {output_file}")

if __name__ == "__main__":
    # 使用示例
    csv_file = "/Users/wade/Documents/Claude/8月csv_副本.csv"
    
    # 运行分析
    results = analyze_leads(csv_file)
    
    if results:
        # 显示优先级统计
        print("\n" + "="*50)
        print("📊 线索优先级分布")
        print("="*50)
        print(results['priority_stats'])
        
        # 显示预警信息
        print("\n" + "="*50)
        print("⚠️  预警信息汇总")
        print("="*50)
        
        for level, alerts in results['alerts'].items():
            if alerts:
                print(f"\n{level}: {len(alerts)}条")
                for alert in alerts[:3]:  # 显示前3条
                    print(f"  - {alert.get('类型', '')}: {alert.get('处理建议', '')}")
        
        # 生成报告
        generate_report(results)
        
        # 显示前10个高优先级线索
        print("\n" + "="*50)
        print("🔥 前10个高优先级线索")
        print("="*50)
        top_leads = results['data'].nlargest(10, '优先级分数')[['学员id', '学员姓名', '学员来源', '客户分级', '回访次数', '优先级分数', '优先级等级']]
        print(top_leads.to_string(index=False))