#!/bin/bash
set -e

echo ">>> 初始化系统..."
ulimit -n 65535 || echo "⚠️ 警告: ulimit 设置失败"

mkdir -p /app/conf /app/uploads /app/avatar /tmp/cache

# 生成配置文件
cat > /app/conf.ini <<EOFCONF
[System]
Mode = master
Listen = :7860
Debug = true
SessionSecret = $(openssl rand -hex 16)
HashIDSalt = $(openssl rand -hex 16)

[Database]
Type = sqlite3
DBFile = /app/cloudreve.db

[OptionOverwrite]
max_edit_size = 107374182400
upload_session_timeout = 172800
thumb_width = 0
thumb_height = 0

[CORS]
AllowOrigins = *
AllowMethods = GET,POST,PUT,DELETE,OPTIONS
AllowHeaders = *
AllowCredentials = true
EOFCONF

# 1. 启动前恢复数据
echo ">>> [1/5] 检查 WebDAV 备份..."
python3 /app/backup_manager.py restore

# 2. 启动 Cloudreve
echo ">>> [2/5] 启动 Cloudreve..."
./cloudreve -c /app/conf.ini &
CLOUDREVE_PID=$!

# 等待 Cloudreve 就绪
for i in {1..20}; do
    if curl -sf http://localhost:7860/ > /dev/null 2>&1; then
        echo "✅ Cloudreve 启动成功"
        break
    fi
    sleep 2
done

# 3. 应用存储策略 (改文件名规则)
echo ">>> [3/5] 应用存储策略..."
python3 /app/storage_policy.py

# 4. 启动同步引擎
echo ">>> [4/5] 启动 HF 同步..."
python3 /app/hf_sync.py &
SYNC_PID=$!

# 5. 启动自动备份 (延迟10秒，避开启动高峰)
echo ">>> [5/5] 启动自动备份守护进程..."
sleep 10
python3 /app/backup_manager.py run &
BACKUP_PID=$!

echo "==================================================="
echo "✅ 全部服务已就绪: http://localhost:7860"
echo "==================================================="

# 守护循环
while true; do
    if ! kill -0 $CLOUDREVE_PID 2>/dev/null; then
        echo "❌ Cloudreve 退出"
        exit 1
    fi
    if ! kill -0 $BACKUP_PID 2>/dev/null; then
        echo "⚠️ 备份服务挂了，重启中..."
        python3 /app/backup_manager.py run &
        BACKUP_PID=$!
    fi
    sleep 60
done
