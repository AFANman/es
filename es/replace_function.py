#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 读取原文件
with open('crawl_es2.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到函数开始和结束的行号
start_line = None
end_line = None
indent_level = None

for i, line in enumerate(lines):
    if 'def _load_events_from_excel(file_path: str) -> Dict[str, str]:' in line:
        start_line = i
        indent_level = len(line) - len(line.lstrip())
        break

if start_line is not None:
    # 找到函数结束位置
    for i in range(start_line + 1, len(lines)):
        line = lines[i]
        # 如果是空行，跳过
        if line.strip() == '':
            continue
        # 如果缩进级别回到函数定义级别或更少，说明函数结束了
        current_indent = len(line) - len(line.lstrip())
        if current_indent <= indent_level and line.strip():
            end_line = i
            break
    
    if end_line is None:
        end_line = len(lines)

    # 新的函数内容
    new_function_lines = [
        ' ' * indent_level + 'def _load_events_from_excel(file_path: str) -> Dict[str, str]:\n',
        ' ' * (indent_level + 4) + 'events: Dict[str, str] = {}\n',
        ' ' * (indent_level + 4) + 'try:\n',
        ' ' * (indent_level + 8) + '# 读取Excel文件，优先查找"活动名称"列\n',
        ' ' * (indent_level + 8) + 'df = pd.read_excel(file_path, dtype=str)\n',
        ' ' * (indent_level + 8) + '\n',
        ' ' * (indent_level + 8) + '# 查找活动名称列\n',
        ' ' * (indent_level + 8) + 'activity_column = None\n',
        ' ' * (indent_level + 8) + 'for col in df.columns:\n',
        ' ' * (indent_level + 12) + 'if \'活动\' in str(col) and \'名称\' in str(col):\n',
        ' ' * (indent_level + 16) + 'activity_column = col\n',
        ' ' * (indent_level + 16) + 'break\n',
        ' ' * (indent_level + 8) + '\n',
        ' ' * (indent_level + 8) + 'if activity_column:\n',
        ' ' * (indent_level + 12) + 'print(f"找到活动列: {activity_column}")\n',
        ' ' * (indent_level + 12) + '# 直接从活动名称列读取\n',
        ' ' * (indent_level + 12) + 'series = df[activity_column].dropna()\n',
        ' ' * (indent_level + 12) + 'for v in series:\n',
        ' ' * (indent_level + 16) + 's = str(v).strip()\n',
        ' ' * (indent_level + 16) + '# 匹配日期+活动名称的格式：如"10月10日　Bright me up!!スカウト Stage：宙"\n',
        ' ' * (indent_level + 16) + 'm = re.search(r"(\\d{1,2}月\\d{1,2}日)[　 \\t]*(.+)", s)\n',
        ' ' * (indent_level + 16) + 'if m:\n',
        ' ' * (indent_level + 20) + 'date = m.group(1)\n',
        ' ' * (indent_level + 20) + 'event_name = m.group(2).strip()\n',
        ' ' * (indent_level + 20) + 'if 3 <= len(event_name) <= 100:  # 放宽长度限制\n',
        ' ' * (indent_level + 24) + '# 存储完整的活动名称（包含日期）\n',
        ' ' * (indent_level + 24) + 'full_event_name = f"{date}　{event_name}"\n',
        ' ' * (indent_level + 24) + 'events[date] = full_event_name\n',
        ' ' * (indent_level + 24) + '# 同时存储不带前导零的日期格式\n',
        ' ' * (indent_level + 24) + 'date_no_zero = re.sub(r"0(\\d月)", r"\\1", date)  # 去掉月份前导零\n',
        ' ' * (indent_level + 24) + 'date_no_zero = re.sub(r"(\\d月)0(\\d日)", r"\\1\\2", date_no_zero)  # 去掉日期前导零\n',
        ' ' * (indent_level + 24) + 'if date_no_zero != date:\n',
        ' ' * (indent_level + 28) + 'events[date_no_zero] = full_event_name\n',
        ' ' * (indent_level + 12) + 'print(f"从活动名称列加载了 {len(events)} 个活动")\n',
        ' ' * (indent_level + 8) + 'else:\n',
        ' ' * (indent_level + 12) + '# 回退到原有逻辑：扫描所有列查找包含【】的活动名称\n',
        ' ' * (indent_level + 12) + 'print("未找到活动名称列，使用原有扫描逻辑")\n',
        ' ' * (indent_level + 12) + 'xls = pd.ExcelFile(file_path)\n',
        ' ' * (indent_level + 12) + 'for sheet in xls.sheet_names:\n',
        ' ' * (indent_level + 16) + 'df = pd.read_excel(file_path, sheet_name=sheet, dtype=str)\n',
        ' ' * (indent_level + 16) + 'for col in df.columns:\n',
        ' ' * (indent_level + 20) + 'series = df[col].dropna()\n',
        ' ' * (indent_level + 20) + 'for v in series:\n',
        ' ' * (indent_level + 24) + 's = str(v)\n',
        ' ' * (indent_level + 24) + 'm = re.search(r"(\\d{1,2}月\\d{1,2}日)[　 \\t]*?【([^】]+)】([^【\\n]*)", s)\n',
        ' ' * (indent_level + 24) + 'if m:\n',
        ' ' * (indent_level + 28) + 'date = m.group(1)\n',
        ' ' * (indent_level + 28) + 'ev = f"【{m.group(2)}】{m.group(3).strip()}".strip()\n',
        ' ' * (indent_level + 28) + 'if 5 <= len(ev) <= 80:\n',
        ' ' * (indent_level + 32) + '# 同时存储带前导零和不带前导零两种形式\n',
        ' ' * (indent_level + 32) + 'events[date] = ev\n',
        ' ' * (indent_level + 32) + 'date_no_zero = re.sub(r"^0", "", date)\n',
        ' ' * (indent_level + 32) + 'events[date_no_zero] = ev\n',
        ' ' * (indent_level + 4) + 'except Exception as e:\n',
        ' ' * (indent_level + 8) + 'print(f"加载Excel活动数据失败: {e}")\n',
        ' ' * (indent_level + 4) + 'return events\n',
        '\n'
    ]

    # 替换函数
    new_lines = lines[:start_line] + new_function_lines + lines[end_line:]

    # 写入新文件
    with open('crawl_es2.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print(f"函数替换完成，从第{start_line+1}行到第{end_line}行")
else:
    print("未找到函数定义")