#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
鱼缸监控系统维护工具
功能：备份数据库 / 清空日志 / 数据库管理
日志文件：/var/log/fishtank_monitor.log
数据库文件：/var/lib/fishtank/sensor_data.db
"""

import os
import sys
import shutil
import logging
import sqlite3
from datetime import datetime

# 配置常量
LOG_FILE = "/var/log/fishtank_monitor.log"
DB_FILE = "/var/lib/fishtank/sensor_data.db"
DB_BACKUP_DIR = "/home/miaoking/mycode/YuGang/backup"

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def get_table_list():
    """获取数据库中的所有表名"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [table[0] for table in cursor.fetchall()]
        conn.close()
        return tables
    except Exception as e:
        logger.error(f"获取表列表失败: {str(e)}")
        return []

def show_table_data(table_name, limit=10):
    """显示指定表的数据"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 获取表结构
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]
        
        # 获取数据
        cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
        rows = cursor.fetchall()
        
        conn.close()
        
        # 显示结果
        print(f"\n表 '{table_name}' 的前 {limit} 条记录:")
        print("-" * 80)
        print(" | ".join(columns))
        print("-" * 80)
        for row in rows:
            print(" | ".join(str(item) for item in row))
        print("-" * 80)
        print(f"共显示 {len(rows)} 条记录")
        
    except Exception as e:
        logger.error(f"显示表数据失败: {str(e)}")

def clear_table(table_name):
    """清空指定表"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {table_name}")
        conn.commit()
        conn.close()
        logger.info(f"表 '{table_name}' 已清空")
        print(f"表 '{table_name}' 已成功清空")
    except Exception as e:
        logger.error(f"清空表失败: {str(e)}")

def delete_record(table_name, record_id):
    """删除指定表的指定记录"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 先检查记录是否存在
        cursor.execute(f"SELECT * FROM {table_name} WHERE id = ?", (record_id,))
        if not cursor.fetchone():
            print(f"错误: 表 '{table_name}' 中不存在 ID 为 {record_id} 的记录")
            return False
        
        # 删除记录
        cursor.execute(f"DELETE FROM {table_name} WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()
        
        logger.info(f"已从表 '{table_name}' 删除 ID 为 {record_id} 的记录")
        print(f"已成功删除记录 (ID: {record_id})")
        return True
        
    except Exception as e:
        logger.error(f"删除记录失败: {str(e)}")
        return False

def search_records(table_name, search_column, search_value, limit=20):
    """查询指定表的记录"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 获取表结构
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]
        
        # 构建查询语句
        query = f"SELECT * FROM {table_name} WHERE {search_column} LIKE ? LIMIT {limit}"
        cursor.execute(query, (f"%{search_value}%",))
        rows = cursor.fetchall()
        
        conn.close()
        
        # 显示结果
        print(f"\n表 '{table_name}' 的查询结果 (共 {len(rows)} 条记录):")
        print("-" * 80)
        print(" | ".join(columns))
        print("-" * 80)
        for row in rows:
            print(" | ".join(str(item) for item in row))
        print("-" * 80)
        
    except Exception as e:
        logger.error(f"查询记录失败: {str(e)}")

def manage_database():
    """数据库管理功能"""
    while True:
        print("\n=== 数据库管理 ===")
        tables = get_table_list()
        
        if not tables:
            print("数据库中没有找到任何表")
            return
        
        # 显示表列表
        print("可用的表:")
        for i, table in enumerate(tables, 1):
            print(f"{i}. {table}")
        print("0. 返回主菜单")
        print("=" * 20)
        
        try:
            choice = input("请选择要操作的表 (0-{}): ".format(len(tables))).strip()
            if choice == '0':
                return
                
            table_index = int(choice) - 1
            if 0 <= table_index < len(tables):
                selected_table = tables[table_index]
                table_operations(selected_table)
            else:
                print("无效的选择")
                
        except ValueError:
            print("请输入有效的数字")

def table_operations(table_name):
    """对指定表进行操作"""
    while True:
        print(f"\n=== 操作表: {table_name} ===")
        print("1. 查看表数据")
        print("2. 清空表")
        print("3. 删除指定记录")
        print("4. 查询记录")
        print("0. 返回上一级")
        print("=" * 30)
        
        try:
            choice = input("请选择操作 (0-4): ").strip()
            
            if choice == '1':
                try:
                    limit = int(input("显示多少条记录? (默认10): ") or "10")
                    show_table_data(table_name, limit)
                except ValueError:
                    print("请输入有效的数字")
                    
            elif choice == '2':
                confirm = input(f"警告：此操作将清空表 '{table_name}' 的所有数据，确认继续？(y/N): ")
                if confirm.lower() == 'y':
                    clear_table(table_name)
                else:
                    print("操作已取消")
                    
            elif choice == '3':
                try:
                    record_id = input("请输入要删除的记录ID: ").strip()
                    if record_id:
                        delete_record(table_name, record_id)
                    else:
                        print("记录ID不能为空")
                except Exception as e:
                    print(f"删除记录时出错: {e}")
                    
            elif choice == '4':
                try:
                    search_column = input("请输入要查询的列名: ").strip()
                    search_value = input("请输入要查询的值: ").strip()
                    if search_column and search_value:
                        limit = int(input("最多显示多少条记录? (默认20): ") or "20")
                        search_records(table_name, search_column, search_value, limit)
                    else:
                        print("列名和查询值不能为空")
                except ValueError:
                    print("请输入有效的数字")
                except Exception as e:
                    print(f"查询记录时出错: {e}")
                    
            elif choice == '0':
                return
                
            else:
                print("无效的选择")
                
        except ValueError:
            print("请输入有效的数字")

def backup_database():
    """
    备份数据库文件到指定目录
    """
    try:
        # 确保备份目录存在
        os.makedirs(DB_BACKUP_DIR, exist_ok=True)
        
        # 构建带时间戳的备份文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(DB_BACKUP_DIR, f"sensor_data_backup_{timestamp}.db")
        
        # 执行文件复制
        shutil.copy2(DB_FILE, backup_file)
        logger.info(f"数据库备份成功: {backup_file}")
    except Exception as e:
        logger.error(f"数据库备份失败: {str(e)}")

def clear_log():
    """
    清空日志文件内容（不删除文件）
    """
    try:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.write(f"日志清理于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        logger.info(f"日志文件已清空: {LOG_FILE}")
    except Exception as e:
        logger.error(f"日志清空失败: {str(e)}")

def show_menu():
    """
    显示操作菜单并获取用户选择
    """
    print("\n=== 鱼缸监控系统维护工具 ===")
    print("1. 备份数据库")
    print("2. 清空日志")
    print("3. 数据库管理")
    print("0. 退出")
    print("=" * 30)
    
    try:
        choice = input("请选择操作 (0-3): ").strip()
        return int(choice)
    except ValueError:
        logger.warning("无效的输入，请输入数字 0-3")
        return -1

def main():
    """
    主程序逻辑
    """
    logger.info("维护工具启动")
    
    while True:
        choice = show_menu()
        
        if choice == 1:
            backup_database()
            
        elif choice == 2:
            confirm = input("警告：此操作将清空日志文件，确认继续？(y/N): ")
            if confirm.lower() == 'y':
                clear_log()
            else:
                logger.info("日志清空操作已取消")
                
        elif choice == 3:
            manage_database()
            
        elif choice == 0:
            logger.info("维护工具退出")
            print("再见！")
            break
            
        else:
            if choice != -1:  # 避免重复打印无效输入的日志
                logger.warning(f"无效选择: {choice}")

if __name__ == "__main__":
    # 检查必要目录权限
    if not os.access("/var/log", os.W_OK):
        print("错误：没有写入日志目录的权限，请以sudo运行")
        sys.exit(1)
    if not os.access("/var/lib/fishtank", os.W_OK):
        print("错误：没有写入数据目录的权限，请以sudo运行")
        sys.exit(1)
        
    main()