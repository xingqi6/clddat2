#!/usr/bin/env python3
import os, time, tarfile, schedule, logging
from datetime import datetime
from webdav3.client import Client

logging.basicConfig(level=logging.INFO)

def run_backup():
    url = os.getenv('WEBDAV_URL')
    user = os.getenv('WEBDAV_USERNAME')
    pwd = os.getenv('WEBDAV_PASSWORD')
    if not (url and user and pwd): return

    try:
        client = Client({'webdav_hostname': url, 'webdav_login': user, 'webdav_password': pwd})
        backup_dir = "cloudreve_conf_backup"
        if not client.check(backup_dir): client.mkdir(backup_dir)

        # 仅备份数据库和配置
        tar_name = f"/tmp/conf_{datetime.now().strftime('%Y%m%d')}.tar.gz"
        with tarfile.open(tar_name, "w:gz") as tar:
            for f in ['/app/cloudreve.db', '/app/conf.ini']:
                if os.path.exists(f): tar.add(f, arcname=os.path.basename(f))
        
        client.upload_sync(remote_path=f"{backup_dir}/{os.path.basename(tar_name)}", local_path=tar_name)
        os.remove(tar_name)
        logging.info("✅ 配置已备份")
    except Exception as e:
        logging.error(f"⚠️ 备份失败: {e}")

if __name__ == '__main__':
    if os.getenv('WEBDAV_URL'):
        schedule.every(12).hours.do(run_backup)
        run_backup()
        while True:
            schedule.run_pending()
            time.sleep(3600)
