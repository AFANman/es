import pandas as pd
import re
from typing import Dict

def _load_events_from_excel(file_path: str) -> Dict[str, str]:
    events: Dict[str, str] = {}
    try:
        # 读取Excel文件，优先查找"活动名称"列
        df = pd.read_excel(file_path, dtype=str)
        
        # 查找活动名称列
        activity_column = None
        for col in df.columns:
            if '活动' in str(col) and '名称' in str(col):
                activity_column = col
                break
        
        if activity_column:
            print(f"找到活动列: {activity_column}")
            # 直接从活动名称列读取
            series = df[activity_column].dropna()
            for v in series:
                s = str(v).strip()
                # 匹配日期+活动名称的格式：如"10月10日　Bright me up!!スカウト Stage：宙"
                m = re.search(r"(\d{1,2}月\d{1,2}日)[　 \t]*(.+)", s)
                if m:
                    date = m.group(1)
                    event_name = m.group(2).strip()
                    if 3 <= len(event_name) <= 100:  # 放宽长度限制
                        # 存储完整的活动名称（包含日期）
                        full_event_name = f"{date}　{event_name}"
                        events[date] = full_event_name
                        # 同时存储不带前导零的日期格式
                        date_no_zero = re.sub(r"0(\d月)", r"\1", date)  # 去掉月份前导零
                        date_no_zero = re.sub(r"(\d月)0(\d日)", r"\1\2", date_no_zero)  # 去掉日期前导零
                        if date_no_zero != date:
                            events[date_no_zero] = full_event_name
            print(f"从活动名称列加载了 {len(events)} 个活动")
        else:
            # 回退到原有逻辑：扫描所有列查找包含【】的活动名称
            print("未找到活动名称列，使用原有扫描逻辑")
            xls = pd.ExcelFile(file_path)
            for sheet in xls.sheet_names:
                df = pd.read_excel(file_path, sheet_name=sheet, dtype=str)
                for col in df.columns:
                    series = df[col].dropna()
                    for v in series:
                        s = str(v)
                        m = re.search(r"(\d{1,2}月\d{1,2}日)[　 \t]*?【([^】]+)】([^【\n]*)", s)
                        if m:
                            date = m.group(1)
                            ev = f"【{m.group(2)}】{m.group(3).strip()}".strip()
                            if 5 <= len(ev) <= 80:
                                # 同时存储带前导零和不带前导零两种形式
                                events[date] = ev
                                date_no_zero = re.sub(r"^0", "", date)
                                events[date_no_zero] = ev
    except Exception as e:
        print(f"加载Excel活动数据失败: {e}")
    return events

# 测试函数
if __name__ == "__main__":
    file_path = "f:/Code/Trae/projects/es/es2 卡面名称及技能一览20251014_011423.xlsx"
    events = _load_events_from_excel(file_path)
    print(f"加载的活动数量: {len(events)}")
    for date, event in list(events.items())[:10]:  # 显示前10个
        print(f"{date}: {event}")