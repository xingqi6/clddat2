#!/usr/bin/env python3
"""
初始化存储策略：强制使用本机存储，并优化上传参数
"""
import os
import json
import sqlite3
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_policy():
    db_path = '/app/cloudreve.db'
    
    # 等待数据库文件生成
    for _ in range(120):
        if os.path.exists(db_path): break
        time.sleep(1)
    
    if not os.path.exists(db_path):
        logger.error("❌ 数据库未生成，跳过策略配置")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # ===================================================
        # 关键修复：显式设置 chunk_size 为 5MB (5242880)
        # 解决 "Client canceled upload" 和网络中断问题
        # ===================================================
        policy_options = json.dumps({
            'sys_path': '/app/uploads/{uid}/{path}',
            'chunk_size': 5242880  # 5MB 分片
        })
        
        # 强制更新 ID=1 的策略
        cursor.execute('''
            INSERT OR REPLACE INTO policies (
                id, name, type, max_size, options, 
                dir_name_rule, file_name_rule, auto_rename, is_origin_link_enable
            ) VALUES (
                1, 'Local Storage (Optimized)', 'local', 
                10995116277760, ?, 
                'uploads/{uid}/{date}', '{originname}', 
                1, 0
            )
        ''', (policy_options,))
        
        # 绑定到用户组
        cursor.execute("UPDATE groups SET policy_list=? WHERE id IN (1, 2)", (json.dumps([1]),))
        
        conn.commit()
        conn.close()
        logger.info("✅ 存储策略已更新：UTF-8路径支持 + 5MB分片优化")
        
    except Exception as e:
        logger.error(f"❌ 策略配置失败: {e}")

if __name__ == '__main__':
    setup_policy()
