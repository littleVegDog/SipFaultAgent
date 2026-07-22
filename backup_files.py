#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Python脚本用于备份项目中的所有Python和Markdown文件
生成一个包含所有文件内容的文本文件，使用UTF-8编码
"""

import os
import glob
from datetime import datetime

def backup_files():
    # 获取当前工作目录
    project_dir = os.path.dirname(os.path.abspath(__file__))

    # 生成带日期的文件名
    current_date = datetime.now().strftime("%Y-%m-%d")
    output_file = f"backup-{current_date}.txt"

    print(f"正在备份项目文件...")
    print(f"项目目录: {project_dir}")
    print(f"输出文件: {output_file}")

    # 打开输出文件，使用UTF-8编码
    with open(output_file, 'w', encoding='utf-8') as f:
        # 添加文件头
        f.write(f"Project Backup - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 50 + "\n\n")

        # 处理Python文件
        python_files = glob.glob(os.path.join(project_dir, "*.py"))
        print(f"找到 {len(python_files)} 个Python文件")

        for py_file in python_files:
            filename = os.path.basename(py_file)
            print(f"正在处理: {filename}")

            # 添加文件分隔符
            f.write("\n" + "=" * 60 + "\n")
            f.write(f"文件: {filename}\n")
            f.write("=" * 60 + "\n")

            # 读取并写入文件内容
            try:
                with open(py_file, 'r', encoding='utf-8') as source_file:
                    content = source_file.read()
                    f.write(content)
            except Exception as e:
                f.write(f"读取文件时出错: {e}\n")

            f.write("\n\n")

        # 处理Markdown文件
        md_files = glob.glob(os.path.join(project_dir, "*.md"))
        print(f"找到 {len(md_files)} 个Markdown文件")

        for md_file in md_files:
            filename = os.path.basename(md_file)
            print(f"正在处理: {filename}")

            # 添加文件分隔符
            f.write("\n" + "=" * 60 + "\n")
            f.write(f"文件: {filename}\n")
            f.write("=" * 60 + "\n")

            # 读取并写入文件内容
            try:
                with open(md_file, 'r', encoding='utf-8') as source_file:
                    content = source_file.read()
                    f.write(content)
            except Exception as e:
                f.write(f"读取文件时出错: {e}\n")

            f.write("\n\n")

    print(f"\n备份完成！文件已保存为: {output_file}")

if __name__ == "__main__":
    backup_files()
