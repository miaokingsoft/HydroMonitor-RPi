#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
鱼缸监控系统维护工具
功能：备份数据库 / 清空日志
日志文件：/var/log/fishtank_monitor.log
数据库文件：/var/lib/fishtank/sensor_data.db
"""

import os
import sys
import shutil
import logging
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
    print("0. 退出")
    print("=" * 30)
    
    try:
        choice = input("请选择操作 (0-2): ").strip()
        return int(choice)
    except ValueError:
        logger.warning("无效的输入，请输入数字 0-2")
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