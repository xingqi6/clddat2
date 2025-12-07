#!/usr/bin/env python3
"""
存储策略配置
1. 极小分片 (2MB) 解决上传假死/超时问题
2. 保持原文件名
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
    
    for _ in range(120):
        if os.path.exists(db_path): break
        time.sleep(1)
    
    if not os.path.exists(db_path):
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # =======================================================
        # 关键修改：chunk_size 改为 2MB (2097152)
        # 小分片能显著降低网络抖动导致的“分片上传失败”
        # =======================================================
        policy_options = json.dumps({
            'sys_path': '/app/uploads/{uid}/{path}',
            'chunk_size': 2097152  # 2MB
        })
        
        cursor.execute('''
            INSERT OR REPLACE INTO policies (
                id, name, type, max_size, options, 
                dir_name_rule, file_name_rule, auto_rename, is_origin_link_enable
            ) VALUES (
                1, 'Local Storage (High Stability)', 'local', 
                10995116277760, ?, 
                'uploads/{uid}/{date}', '{originname}', 
                1, 0
            )
        ''', (policy_options,))
        
        cursor.execute("UPDATE groups SET policy_list=? WHERE id IN (1, 2)", (json.dumps([1]),))
        
        # 同时修改设置表，增加 PHP/后端 处理超时时间 (虽不是 PHP 但 Cloudreve 会参考)
        cursor.execute("INSERT OR REPLACE INTO settings (name, value, type) VALUES ('max_worker_num', '20', 'task')")
        
        conn.commit()
        conn.close()
        logger.info("✅ 存储策略更新: 2MB极小分片 (高稳定性模式)")
        
    except Exception as e:
        logger.error(f"❌ 策略配置失败: {e}")

if __name__ == '__main__':
    setup_policy()
