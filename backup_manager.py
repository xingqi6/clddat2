#!/usr/bin/env python3
"""
WebDAV 数据持久化工具 (v3)
1. 修正时间间隔单位为秒 (Seconds)
2. 保留最新 5 份备份
"""
import os
import sys
import time
import tarfile
import schedule
import logging
from datetime import datetime
from webdav3.client import Client

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - [Backup] %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class DataPersistence:
    def __init__(self):
        self.webdav_config = {
            'webdav_hostname': os.getenv('WEBDAV_URL'),
            'webdav_login': os.getenv('WEBDAV_USERNAME'),
            'webdav_password': os.getenv('WEBDAV_PASSWORD')
        }
        self.remote_dir = os.getenv('WEBDAV_BACKUP_PATH', 'cloudreve_data_backup')
        self.local_files = ['/app/cloudreve.db', '/app/conf.ini']
        self.client = None

    def connect(self):
        if not all(self.webdav_config.values()):
            logger.error("❌ 环境变量未配置 (WEBDAV_URL/USERNAME/PASSWORD)")
            return False
        try:
            self.client = Client(self.webdav_config)
            self.client.list("/")
            return True
        except Exception as e:
            logger.error(f"❌ WebDAV 连接失败: {e}")
            return False

    def _cleanup(self):
        """只保留最新的 5 份备份"""
        try:
            if not self.client.check(self.remote_dir): return
            files = self.client.list(self.remote_dir)
            backups = [f for f in files if f.startswith('data_') and f.endswith('.tar.gz')]
            backups.sort() # 按文件名时间排序
            
            if len(backups) > 5:
                to_delete = backups[:-5]
                for f in to_delete:
                    self.client.clean(f"{self.remote_dir}/{f}")
                    logger.info(f"🗑️ 自动清理旧备份: {f}")
        except Exception as e:
            logger.error(f"⚠️ 清理失败: {e}")

    def backup(self):
        """执行一次备份"""
        if not self.client and not self.connect(): return
        
        try:
            if not self.client.check(self.remote_dir):
                self.client.mkdir(self.remote_dir)

            if not os.path.exists('/app/cloudreve.db'):
                return

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            tar_name = f"/tmp/data_{timestamp}.tar.gz"
            
            with tarfile.open(tar_name, "w:gz") as tar:
                for f in self.local_files:
                    if os.path.exists(f):
                        tar.add(f, arcname=os.path.basename(f))
            
            remote_path = f"{self.remote_dir}/{os.path.basename(tar_name)}"
            self.client.upload_sync(remote_path=remote_path, local_path=tar_name)
            logger.info(f"✅ 备份成功: {os.path.basename(tar_name)}")
            
            os.remove(tar_name)
            self._cleanup()
            
        except Exception as e:
            logger.error(f"❌ 备份出错: {e}")

    def restore(self):
        """启动时恢复"""
        if not self.client and not self.connect(): return

        try:
            if not self.client.check(self.remote_dir):
                logger.info("ℹ️ 远程备份目录不存在，跳过恢复")
                return

            files = self.client.list(self.remote_dir)
            backups = sorted([f for f in files if f.startswith('data_') and f.endswith('.tar.gz')])
            
            if not backups:
                logger.info("ℹ️ 未找到历史备份，跳过恢复")
                return

            latest = backups[-1]
            logger.info(f"⬇️ 正在恢复备份: {latest}")
            
            local_path = f"/tmp/{latest}"
            self.client.download_sync(remote_path=f"{self.remote_dir}/{latest}", local_path=local_path)
            
            with tarfile.open(local_path, "r:gz") as tar:
                tar.extractall(path="/app")
            
            os.remove(local_path)
            logger.info("✅ 数据恢复完成")
            
        except Exception as e:
            logger.error(f"❌ 恢复失败: {e}")

    def start_daemon(self):
        """定时任务守护进程"""
        if not self.client and not self.connect(): return

        # 1. 解析时间间隔 (默认 3600 秒)
        try:
            interval_seconds = int(os.getenv('SYNC_INTERVAL', '3600'))
        except ValueError:
            interval_seconds = 3600
            
        logger.info(f"⏰ 备份守护进程已启动，间隔: {interval_seconds} 秒")
        
        # 2. 启动后立即备一次
        self.backup()
        
        # 3. 设置定时任务 (单位：秒)
        schedule.every(interval_seconds).seconds.do(self.backup)
        
        while True:
            schedule.run_pending()
            time.sleep(10)

if __name__ == '__main__':
    agent = DataPersistence()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'restore':
            agent.restore()
        elif sys.argv[1] == 'run':
            agent.start_daemon()
    else:
        print("Args: restore | run")
