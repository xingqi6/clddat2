#!/usr/bin/env python3
"""
WebDAV 数据持久化工具
功能：
1. 启动时恢复数据库 (Restore)
2. 定时备份数据库 (Backup)
3. 自动清理旧备份 (只保留最新5份)
"""
import os
import sys
import time
import tarfile
import schedule
import logging
from datetime import datetime
from webdav3.client import Client

# 配置日志输出到控制台
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class DataPersistence:
    def __init__(self):
        # 读取环境变量
        self.webdav_config = {
            'webdav_hostname': os.getenv('WEBDAV_URL'),
            'webdav_login': os.getenv('WEBDAV_USERNAME'),
            'webdav_password': os.getenv('WEBDAV_PASSWORD')
        }
        # 备份存储在 WebDAV 的哪个目录
        self.remote_dir = os.getenv('WEBDAV_BACKUP_PATH', 'cloudreve_data_backup')
        # 需要备份的本地文件
        self.local_files = ['/app/cloudreve.db', '/app/conf.ini']
        
        self.client = None
        self._connect()

    def _connect(self):
        """连接 WebDAV"""
        if not all(self.webdav_config.values()):
            logger.warning("⚠️ WebDAV 环境变量未配置，数据无法持久化！")
            return

        try:
            self.client = Client(self.webdav_config)
            # 检查连接是否可用 (列出根目录)
            self.client.list("/")
            logger.info("✅ WebDAV 连接成功")
        except Exception as e:
            logger.error(f"❌ WebDAV 连接失败: {e}")
            self.client = None

    def _ensure_remote_dir(self):
        """确保远程备份目录存在"""
        try:
            if not self.client.check(self.remote_dir):
                self.client.mkdir(self.remote_dir)
        except:
            pass

    def _cleanup_old_backups(self):
        """【核心功能】清理旧备份，只保留最新的 5 份"""
        try:
            # 获取远程目录下的所有文件
            files = self.client.list(self.remote_dir)
            
            # 筛选出我们的备份文件，并按文件名(时间戳)排序
            # 排序结果：[最旧的, 旧的, ..., 新的, 最新的]
            backups = sorted([f for f in files if f.startswith('data_') and f.endswith('.tar.gz')])
            
            keep_count = 5
            
            # 如果备份数量超过保留数
            if len(backups) > keep_count:
                # 选出需要删除的文件 (除了最后 5 个之外的全部)
                to_delete = backups[:-keep_count]
                
                for filename in to_delete:
                    remote_path = f"{self.remote_dir}/{filename}"
                    self.client.clean(remote_path)
                    logger.info(f"🗑️ 空间自动清理: 已删除旧备份 {filename}")
                    
        except Exception as e:
            logger.error(f"⚠️ 清理旧备份时出错: {e}")

    def backup(self):
        """执行备份"""
        if not self.client: return
        
        try:
            self._ensure_remote_dir()
            
            # 1. 检查本地数据库是否存在
            if not os.path.exists('/app/cloudreve.db'):
                logger.warning("⚠️ 数据库文件不存在，跳过备份")
                return

            # 2. 打包文件
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            tar_name = f"/tmp/data_{timestamp}.tar.gz"
            
            with tarfile.open(tar_name, "w:gz") as tar:
                for f in self.local_files:
                    if os.path.exists(f):
                        tar.add(f, arcname=os.path.basename(f))
            
            # 3. 上传到 WebDAV
            remote_path = f"{self.remote_dir}/{os.path.basename(tar_name)}"
            self.client.upload_sync(remote_path=remote_path, local_path=tar_name)
            logger.info(f"⬆️ 数据已备份到 WebDAV: {os.path.basename(tar_name)}")
            
            # 4. 删除本地临时压缩包
            os.remove(tar_name)
            
            # 5. 执行清理策略
            self._cleanup_old_backups()
            
        except Exception as e:
            logger.error(f"❌ 备份过程出错: {e}")

    def restore(self):
        """执行恢复 (仅在启动时调用)"""
        if not self.client: return
        
        try:
            if not self.client.check(self.remote_dir):
                logger.info("ℹ️ 远程备份目录不存在，将初始化全新环境")
                return

            # 查找最新的备份文件
            files = self.client.list(self.remote_dir)
            backups = sorted([f for f in files if f.startswith('data_') and f.endswith('.tar.gz')])
            
            if not backups:
                logger.info("ℹ️ 未在 WebDAV 发现备份文件，将初始化全新环境")
                return

            latest_backup = backups[-1]
            logger.info(f"⬇️ 发现历史数据，正在恢复: {latest_backup} ...")
            
            local_tar = f"/tmp/{latest_backup}"
            remote_path = f"{self.remote_dir}/{latest_backup}"
            
            # 下载
            self.client.download_sync(remote_path=remote_path, local_path=local_tar)
            
            # 解压覆盖
            with tarfile.open(local_tar, "r:gz") as tar:
                tar.extractall(path="/app")
                
            os.remove(local_tar)
            logger.info("✅ 数据恢复成功！")
            
        except Exception as e:
            logger.error(f"❌ 恢复数据失败: {e}")
            logger.warning("⚠️ 将使用新生成的数据库继续启动...")

    def run_daemon(self):
        """守护进程模式：定时备份"""
        if not self.client: return
        
        # 启动后等待 1 分钟执行第一次备份（确保初始化配置被保存）
        time.sleep(60)
        self.backup()
        
        # 设定定时任务：每 60 分钟备份一次
        # 你可以修改这里的 60 为其他分钟数
        interval = int(os.getenv('SYNC_INTERVAL', '60'))
        schedule.every(interval).minutes.do(self.backup)
        
        logger.info(f"⏰ 自动备份守护进程已启动 (每 {interval} 分钟)")
        
        while True:
            schedule.run_pending()
            time.sleep(60)

if __name__ == '__main__':
    agent = DataPersistence()
    
    if len(sys.argv) > 1 and sys.argv[1] == 'restore':
        # 模式: 恢复数据
        agent.restore()
    elif len(sys.argv) > 1 and sys.argv[1] == 'run':
        # 模式: 运行定时备份
        agent.run_daemon()
    else:
        print("Usage: python3 backup_manager.py [restore|run]")
