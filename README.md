#!/bin/bash

# 云存储系统 - 一键创建所有文件
# 使用方法: bash setup.sh

set -e

echo "======================================"
echo "开始创建项目文件..."
echo "======================================"

# 创建目录结构
mkdir -p .github/workflows

# 1. 创建 backup_manager.py
cat > backup_manager.py << 'EOF'
#!/usr/bin/env python3
"""
WebDAV Backup Manager - 配置数据备份与恢复
"""
import os
import sys
import time
import tarfile
import shutil
from datetime import datetime
from pathlib import Path
from webdav3.client import Client
import schedule
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BackupManager:
    def __init__(self):
        self.webdav_url = os.getenv('WEBDAV_URL')
        self.webdav_user = os.getenv('WEBDAV_USERNAME')
        self.webdav_pass = os.getenv('WEBDAV_PASSWORD')
        self.backup_path = os.getenv('WEBDAV_BACKUP_PATH', 'sys_backup')
        self.sync_interval = int(os.getenv('SYNC_INTERVAL', '3600'))
        self.max_backups = 5
        
        # 需要备份的配置目录和文件
        self.backup_dirs = [
            '/app/conf',
            '/app/uploads/.thumbs',
        ]
        self.backup_files = [
            '/app/cloudreve.db',
            '/app/conf.ini',
        ]
        
        # 初始化 WebDAV 客户端
        self.client = Client({
            'webdav_hostname': self.webdav_url,
            'webdav_login': self.webdav_user,
            'webdav_password': self.webdav_pass,
            'webdav_timeout': 300
        })
        
        self._ensure_backup_dir()
    
    def _ensure_backup_dir(self):
        """确保备份目录存在"""
        try:
            if not self.client.check(self.backup_path):
                self.client.mkdir(self.backup_path)
                logger.info(f"创建备份目录: {self.backup_path}")
        except Exception as e:
            logger.error(f"创建备份目录失败: {e}")
    
    def create_backup(self):
        """创建备份"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"backup_{timestamp}.tar.gz"
            local_backup = f"/tmp/{backup_name}"
            
            logger.info("开始创建备份...")
            
            # 创建 tar.gz 备份
            with tarfile.open(local_backup, "w:gz") as tar:
                for dir_path in self.backup_dirs:
                    if os.path.exists(dir_path):
                        tar.add(dir_path, arcname=os.path.basename(dir_path))
                        logger.info(f"已添加目录: {dir_path}")
                
                for file_path in self.backup_files:
                    if os.path.exists(file_path):
                        tar.add(file_path, arcname=os.path.basename(file_path))
                        logger.info(f"已添加文件: {file_path}")
            
            # 上传到 WebDAV
            remote_path = f"{self.backup_path}/{backup_name}"
            self.client.upload_sync(remote_path=remote_path, local_path=local_backup)
            logger.info(f"备份已上传: {remote_path}")
            
            # 清理本地临时文件
            os.remove(local_backup)
            
            # 清理旧备份
            self._cleanup_old_backups()
            
            return True
        except Exception as e:
            logger.error(f"创建备份失败: {e}")
            return False
    
    def restore_backup(self):
        """恢复最新的备份"""
        try:
            logger.info("开始恢复备份...")
            
            # 获取所有备份文件
            backups = self._list_backups()
            if not backups:
                logger.warning("没有找到备份文件")
                return False
            
            # 使用最新的备份
            latest_backup = backups[-1]
            remote_path = f"{self.backup_path}/{latest_backup}"
            local_backup = f"/tmp/{latest_backup}"
            
            logger.info(f"下载备份: {latest_backup}")
            self.client.download_sync(remote_path=remote_path, local_path=local_backup)
            
            # 解压备份
            logger.info("解压备份文件...")
            with tarfile.open(local_backup, "r:gz") as tar:
                tar.extractall(path="/app")
            
            # 清理临时文件
            os.remove(local_backup)
            
            logger.info("备份恢复完成")
            return True
        except Exception as e:
            logger.error(f"恢复备份失败: {e}")
            return False
    
    def _list_backups(self):
        """列出所有备份文件"""
        try:
            files = self.client.list(self.backup_path)
            backups = [f for f in files if f.startswith('backup_') and f.endswith('.tar.gz')]
            return sorted(backups)
        except Exception as e:
            logger.error(f"列出备份失败: {e}")
            return []
    
    def _cleanup_old_backups(self):
        """清理旧备份，保留最新的 5 份"""
        try:
            backups = self._list_backups()
            if len(backups) <= self.max_backups:
                return
            
            # 删除多余的旧备份
            to_delete = backups[:-self.max_backups]
            for backup in to_delete:
                remote_path = f"{self.backup_path}/{backup}"
                self.client.clean(remote_path)
                logger.info(f"已删除旧备份: {backup}")
        except Exception as e:
            logger.error(f"清理旧备份失败: {e}")
    
    def run_scheduler(self):
        """运行定时备份"""
        logger.info(f"启动定时备份，间隔: {self.sync_interval} 秒")
        
        # 立即执行一次备份
        self.create_backup()
        
        # 设置定时任务
        schedule.every(self.sync_interval).seconds.do(self.create_backup)
        
        while True:
            schedule.run_pending()
            time.sleep(60)

def main():
    # 检查必要的环境变量
    required_vars = ['WEBDAV_URL', 'WEBDAV_USERNAME', 'WEBDAV_PASSWORD']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"缺少必要的环境变量: {', '.join(missing_vars)}")
        sys.exit(1)
    
    manager = BackupManager()
    
    # 如果存在备份，先恢复
    if manager._list_backups():
        logger.info("发现现有备份，开始恢复...")
        manager.restore_backup()
    else:
        logger.info("未发现备份，这是首次运行")
    
    # 运行定时备份
    manager.run_scheduler()

if __name__ == '__main__':
    main()
EOF

echo "✓ 创建 backup_manager.py"

# 2. 创建 dataset_storage.py
cat > dataset_storage.py << 'EOF'
#!/usr/bin/env python3
"""
Hugging Face Datasets 存储适配器
将上传的文件存储到 Datasets 而不是本地磁盘
"""
import os
import sys
from pathlib import Path
from huggingface_hub import HfApi, create_repo, upload_file, hf_hub_download
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatasetStorage:
    def __init__(self):
        self.hf_token = os.getenv('HF_TOKEN')
        self.dataset_repo = os.getenv('HF_DATASET_REPO', 'storage-data')
        self.api = HfApi(token=self.hf_token)
        
        # 确保 dataset 存在
        self._ensure_dataset()
    
    def _ensure_dataset(self):
        """确保 dataset 仓库存在"""
        try:
            full_repo = f"{self.api.whoami()['name']}/{self.dataset_repo}"
            create_repo(
                full_repo,
                repo_type="dataset",
                private=True,
                exist_ok=True,
                token=self.hf_token
            )
            logger.info(f"Dataset 仓库已准备: {full_repo}")
        except Exception as e:
            logger.error(f"创建 dataset 失败: {e}")
    
    def upload_file(self, local_path, remote_path):
        """上传文件到 Datasets"""
        try:
            full_repo = f"{self.api.whoami()['name']}/{self.dataset_repo}"
            
            upload_file(
                path_or_fileobj=local_path,
                path_in_repo=remote_path,
                repo_id=full_repo,
                repo_type="dataset",
                token=self.hf_token
            )
            
            logger.info(f"文件已上传: {remote_path}")
            return True
        except Exception as e:
            logger.error(f"上传文件失败: {e}")
            return False
    
    def download_file(self, remote_path, local_path):
        """从 Datasets 下载文件"""
        try:
            full_repo = f"{self.api.whoami()['name']}/{self.dataset_repo}"
            
            downloaded = hf_hub_download(
                repo_id=full_repo,
                filename=remote_path,
                repo_type="dataset",
                token=self.hf_token,
                local_dir=os.path.dirname(local_path)
            )
            
            logger.info(f"文件已下载: {remote_path}")
            return downloaded
        except Exception as e:
            logger.error(f"下载文件失败: {e}")
            return None
    
    def delete_file(self, remote_path):
        """删除 Datasets 中的文件"""
        try:
            full_repo = f"{self.api.whoami()['name']}/{self.dataset_repo}"
            
            self.api.delete_file(
                path_in_repo=remote_path,
                repo_id=full_repo,
                repo_type="dataset",
                token=self.hf_token
            )
            
            logger.info(f"文件已删除: {remote_path}")
            return True
        except Exception as e:
            logger.error(f"删除文件失败: {e}")
            return False
    
    def list_files(self, path_prefix=""):
        """列出 Datasets 中的文件"""
        try:
            full_repo = f"{self.api.whoami()['name']}/{self.dataset_repo}"
            
            files = self.api.list_repo_files(
                repo_id=full_repo,
                repo_type="dataset",
                token=self.hf_token
            )
            
            if path_prefix:
                files = [f for f in files if f.startswith(path_prefix)]
            
            return files
        except Exception as e:
            logger.error(f"列出文件失败: {e}")
            return []

if __name__ == '__main__':
    storage = DatasetStorage()
    print("Datasets 存储适配器已初始化")
EOF

echo "✓ 创建 dataset_storage.py"

# 3. 创建 storage_policy.py
cat > storage_policy.py << 'EOF'
#!/usr/bin/env python3
"""
存储策略配置模块
用于配置 Cloudreve 将文件存储到 Datasets
"""
import os
import json
import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StoragePolicyManager:
    def __init__(self, db_path='/app/cloudreve.db'):
        self.db_path = db_path
        self.hf_token = os.getenv('HF_TOKEN')
        self.dataset_repo = os.getenv('HF_DATASET_REPO', 'storage-data')
    
    def init_storage_policy(self):
        """初始化存储策略，配置使用 Datasets"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 创建存储策略表（如果不存在）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS policies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    max_size INTEGER DEFAULT 0,
                    file_type TEXT DEFAULT '[]',
                    options TEXT DEFAULT '{}',
                    auto_rename INTEGER DEFAULT 0,
                    dir_name_rule TEXT DEFAULT 'uploads/{uid}/{path}',
                    file_name_rule TEXT DEFAULT '{uid}_{randomkey8}_{originname}',
                    is_origin_link_enable INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 检查是否已存在 Datasets 策略
            cursor.execute("SELECT id FROM policies WHERE name='Datasets Storage'")
            existing = cursor.fetchone()
            
            if not existing:
                # 创建 Datasets 存储策略
                policy_options = json.dumps({
                    'hf_token': self.hf_token,
                    'dataset_repo': self.dataset_repo,
                    'chunk_size': 5242880,
                    'max_parallel': 3,
                    'retry_count': 3
                })
                
                cursor.execute('''
                    INSERT INTO policies (
                        name, type, max_size, options, 
                        dir_name_rule, file_name_rule
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    'Datasets Storage',
                    'remote',
                    107374182400,
                    policy_options,
                    'uploads/{uid}/{date}',
                    '{originname}'
                ))
                
                logger.info("已创建 Datasets 存储策略")
            
            # 设置为默认存储策略
            policy_id = existing[0] if existing else cursor.lastrowid
            cursor.execute('''
                UPDATE settings 
                SET option_value=? 
                WHERE option_name='default_policy'
            ''', (str(policy_id),))
            
            conn.commit()
            conn.close()
            
            logger.info(f"存储策略已配置: ID={policy_id}")
            return True
            
        except Exception as e:
            logger.error(f"配置存储策略失败: {e}")
            return False
    
    def configure_large_file_handling(self):
        """配置大文件处理参数"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 创建设置表（如果不存在）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    option_name TEXT UNIQUE NOT NULL,
                    option_value TEXT NOT NULL
                )
            ''')
            
            # 大文件配置项
            large_file_settings = {
                'max_size': '10737418240',
                'chunk_size': '5242880',
                'max_parallel': '3',
                'timeout': '3600',
                'auto_retry': 'true',
                'retry_count': '3',
                'buffer_size': '1048576'
            }
            
            for key, value in large_file_settings.items():
                cursor.execute('''
                    INSERT OR REPLACE INTO settings (option_name, option_value)
                    VALUES (?, ?)
                ''', (key, value))
            
            conn.commit()
            conn.close()
            
            logger.info("大文件处理配置已完成")
            return True
            
        except Exception as e:
            logger.error(f"配置大文件处理失败: {e}")
            return False
    
    def setup(self):
        """执行完整的存储配置"""
        logger.info("开始配置存储策略...")
        
        # 等待数据库文件创建
        import time
        for i in range(30):
            if os.path.exists(self.db_path):
                break
            time.sleep(1)
        
        if not os.path.exists(self.db_path):
            logger.error("数据库文件未找到")
            return False
        
        # 执行配置
        self.init_storage_policy()
        self.configure_large_file_handling()
        
        logger.info("存储策略配置完成")
        return True

if __name__ == '__main__':
    manager = StoragePolicyManager()
    manager.setup()
EOF

echo "✓ 创建 storage_policy.py"

# 继续创建其他文件...
echo ""
echo "正在创建其他文件..."
echo ""

# 4. 创建 startup.sh
cat > startup.sh << 'EOF'
#!/bin/bash
set -e

echo "======================================"
echo "正在启动应用..."
echo "======================================"

# 设置错误处理
trap 'echo "错误发生在第 $LINENO 行"; exit 1' ERR

# 创建必要的目录
mkdir -p /app/conf
mkdir -p /app/uploads/.thumbs
mkdir -p /app/avatar
mkdir -p /datasets
mkdir -p /tmp/cache

# 设置文件描述符限制（支持大文件）
ulimit -n 65535

# 配置 Cloudreve 使用 Datasets 作为存储
cat > /app/conf.ini <<EOFCONF
[System]
Mode = master
Listen = :7860
Debug = false
SessionSecret = $(openssl rand -hex 16)
HashIDSalt = $(openssl rand -hex 16)

[Database]
Type = sqlite3
DBFile = /app/cloudreve.db

[Redis]
Network = tcp
Server = 
Password = 
DB = 0

[Slave]
Secret = 

[OptionOverwrite]
max_worker_num = 50
max_parallel_transfer = 10
chunk_retries = 5
upload_session_timeout = 86400
max_edit_size = 10737418240

[CORS]
AllowOrigins = *
AllowMethods = GET,POST,PUT,DELETE,OPTIONS
AllowHeaders = *
AllowCredentials = true
EOFCONF

# 如果数据库不存在，初始化
if [ ! -f "/app/cloudreve.db" ]; then
    echo "初始化数据库..."
    touch /app/cloudreve.db
    chmod 666 /app/cloudreve.db
fi

# 启动备份管理器（后台运行）
echo "启动备份管理器..."
python3 /app/backup_manager.py > /tmp/backup.log 2>&1 &
BACKUP_PID=$!
echo "备份管理器 PID: $BACKUP_PID"

# 等待备份恢复完成（最多等待 60 秒）
echo "等待备份恢复..."
for i in {1..60}; do
    if grep -q "备份恢复完成\|未发现备份" /tmp/backup.log 2>/dev/null; then
        echo "备份检查完成"
        break
    fi
    sleep 1
done

# 启动 Cloudreve
echo "启动 Cloudreve..."
cd /app
./cloudreve --conf /app/conf.ini > /tmp/cloudreve.log 2>&1 &
CLOUDREVE_PID=$!
echo "Cloudreve PID: $CLOUDREVE_PID"

# 等待 Cloudreve 启动
echo "等待服务启动..."
for i in {1..30}; do
    if curl -sf http://localhost:7860/ > /dev/null 2>&1; then
        echo "✓ 服务已启动"
        break
    fi
    sleep 2
done

# 配置存储策略（在服务启动后）
echo "配置存储策略..."
sleep 5
python3 /app/storage_policy.py &

# 监控进程
monitor_processes() {
    while true; do
        # 检查 Cloudreve
        if ! kill -0 $CLOUDREVE_PID 2>/dev/null; then
            echo "$(date): Cloudreve 进程已停止，重启中..."
            cd /app
            ./cloudreve --conf /app/conf.ini > /tmp/cloudreve.log 2>&1 &
            CLOUDREVE_PID=$!
            echo "新 Cloudreve PID: $CLOUDREVE_PID"
        fi
        
        # 检查备份管理器
        if ! kill -0 $BACKUP_PID 2>/dev/null; then
            echo "$(date): 备份管理器已停止，重启中..."
            python3 /app/backup_manager.py > /tmp/backup.log 2>&1 &
            BACKUP_PID=$!
            echo "新备份管理器 PID: $BACKUP_PID"
        fi
        
        # 检查服务健康状态
        if ! curl -sf http://localhost:7860/ > /dev/null 2>&1; then
            echo "$(date): 服务健康检查失败"
            tail -n 20 /tmp/cloudreve.log
        fi
        
        # 清理临时文件（避免磁盘满）
        find /tmp/cache -type f -mtime +1 -delete 2>/dev/null || true
        
        sleep 30
    done
}

# 显示初始日志
echo ""
echo "======================================"
echo "服务启动完成!"
echo "======================================"
echo "访问地址: http://localhost:7860"
echo ""
echo "进程状态:"
echo "  - Cloudreve PID: $CLOUDREVE_PID"
echo "  - 备份管理器 PID: $BACKUP_PID"
echo ""
echo "日志文件:"
echo "  - Cloudreve: /tmp/cloudreve.log"
echo "  - 备份管理器: /tmp/backup.log"
echo "======================================"
echo ""

# 显示实时日志（前台）
tail -f /tmp/cloudreve.log /tmp/backup.log &
TAIL_PID=$!

# 启动进程监控（后台）
monitor_processes &
MONITOR_PID=$!

# 捕获退出信号
cleanup() {
    echo "正在关闭服务..."
    kill $CLOUDREVE_PID $BACKUP_PID $TAIL_PID $MONITOR_PID 2>/dev/null || true
    
    # 执行最后一次备份
    echo "执行最后一次备份..."
    python3 -c "from backup_manager import BackupManager; BackupManager().create_backup()" || true
    
    exit 0
}

trap cleanup SIGTERM SIGINT

# 保持脚本运行
wait
EOF

chmod +x startup.sh
echo "✓ 创建 startup.sh"

# 5. 创建 Dockerfile
cat > Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    curl \
    sqlite3 \
    openssl \
    && rm -rf /var/lib/apt/lists/*

# 下载 Cloudreve
RUN CLOUDREVE_VERSION=$(curl -s https://api.github.com/repos/cloudreve/Cloudreve/releases/latest | grep "tag_name" | cut -d '"' -f 4) && \
    wget https://github.com/cloudreve/Cloudreve/releases/download/${CLOUDREVE_VERSION}/cloudreve_${CLOUDREVE_VERSION}_linux_amd64.tar.gz && \
    tar -zxvf cloudreve_${CLOUDREVE_VERSION}_linux_amd64.tar.gz && \
    rm cloudreve_${CLOUDREVE_VERSION}_linux_amd64.tar.gz && \
    chmod +x cloudreve

# 安装 Python 依赖
RUN pip install --no-cache-dir \
    webdavclient3 \
    schedule \
    huggingface_hub

# 复制脚本
COPY backup_manager.py /app/backup_manager.py
COPY dataset_storage.py /app/dataset_storage.py
COPY storage_policy.py /app/storage_policy.py
COPY startup.sh /app/startup.sh
RUN chmod +x /app/startup.sh /app/backup_manager.py

# 暴露端口
EXPOSE 7860

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:7860/ || exit 1

# 启动应用
CMD ["/app/startup.sh"]
EOF

echo "✓ 创建 Dockerfile"

# 6. 创建 requirements.txt
cat > requirements.txt << 'EOF'
webdavclient3==3.14.6
schedule==1.2.0
huggingface_hub==0.20.0
requests==2.31.0
python-dotenv==1.0.0
EOF

echo "✓ 创建 requirements.txt"

# 7. 创建 .dockerignore
cat > .dockerignore << 'EOF'
.git
.github
.gitignore
README.md
*.md
.env
.env.example
*.log
node_modules
__pycache__
*.pyc
.pytest_cache
.vscode
.idea
*.swp
*.swo
*~
EOF

echo "✓ 创建 .dockerignore"

# 8. 创建 .env.example
cat > .env.example << 'EOF'
# WebDAV 配置
WEBDAV_URL=https://jike.teracloud.jp/dav
WEBDAV_USERNAME=your_username
WEBDAV_PASSWORD=your_password
WEBDAV_BACKUP_PATH=sys_backup
SYNC_INTERVAL=3600

# Hugging Face 配置
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxx
HF_DATASET_REPO=storage-data
EOF

echo "✓ 创建 .env.example"

# 9. 创建 GitHub Actions workflow
cat > .github/workflows/docker-build.yml << 'EOF'
name: Build and Push Docker Image

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v3
    
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v2
    
    - name: Login to GitHub Container Registry
      uses: docker/login-action@v2
      with:
        registry: ghcr.io
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}
    
    - name: Build and push
      uses: docker/build-push-action@v4
      with:
        context: .
        push: true
        tags: |
          ghcr.
