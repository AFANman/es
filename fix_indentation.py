#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def fix_function_indentation():
    """修复 find_cards_by_date_with_dynamic_event_names 函数的缩进"""
    
    file_path = "es/crawl_es2.py"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 找到函数开始和结束的行号
    start_line = None
    end_line = None
    
    for i, line in enumerate(lines):
        if 'def find_cards_by_date_with_dynamic_event_names(' in line:
            start_line = i
        elif start_line is not None and line.strip() == 'return cards':
            end_line = i
            break
    
    if start_line is None or end_line is None:
        print(f"❌ 无法找到函数边界: start={start_line}, end={end_line}")
        return
    
    print(f"找到函数: 行 {start_line+1} 到 {end_line+1}")
    
    # 修复缩进：将所有函数内容的缩进减少4个空格
    for i in range(start_line, end_line + 1):
        if i == start_line:
            # 函数定义行，确保没有缩进
            lines[i] = lines[i].lstrip()
        else:
            # 函数体，减少4个空格的缩进
            if lines[i].startswith('        '):  # 8个空格变成4个
                lines[i] = '    ' + lines[i][8:]
            elif lines[i].startswith('    '):  # 4个空格变成0个
                lines[i] = lines[i][4:]
    
    # 写回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print("✅ 函数缩进修复完成")

if __name__ == "__main__":
    fix_function_indentation()