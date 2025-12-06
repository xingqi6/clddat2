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
cat > /app/conf.ini <<EOF
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
EOF

# 如果数据库不存在，初始化
if [ ! -f "/app/cloudreve.db" ]; then
    echo "初始化数据库..."
    touch /app/cloudreve.db
fi

# 启动备份管理器（后台运行）
echo "启动备份管理器..."
python3 /app/backup_manager.py &
BACKUP_PID=$!

# 等待备份恢复完成
sleep 10

# 启动 Cloudreve
echo "启动 Cloudreve..."
cd /app
./cloudreve --conf /app/conf.ini &
CLOUDREVE_PID=$!

# 监控进程
monitor_processes() {
    while true; do
        if ! kill -0 $CLOUDREVE_PID 2>/dev/null; then
            echo "Cloudreve 进程已停止，重启中..."
            cd /app
            ./cloudreve --conf /app/conf.ini &
            CLOUDREVE_PID=$!
        fi
        
        if ! kill -0 $BACKUP_PID 2>/dev/null; then
            echo "备份管理器已停止，重启中..."
            python3 /app/backup_manager.py &
            BACKUP_PID=$!
        fi
        
        sleep 30
    done
}

# 启动进程监控
monitor_processes &

# 保持脚本运行
wait
