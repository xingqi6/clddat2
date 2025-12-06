#!/bin/bash
set -e

echo ">>> 初始化系统..."

# 1. 尝试设置 ulimit (失败则忽略)
ulimit -n 65535 || echo "⚠️ 警告: 无法设置 ulimit，使用系统默认值"

# 创建必要目录
mkdir -p /app/conf
mkdir -p /app/uploads
mkdir -p /app/avatar
mkdir -p /tmp/cache

# 2. 生成 Cloudreve 配置文件
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

echo ">>> 启动 Cloudreve 主程序..."

# =======================================================
# 关键修复：这里必须用 -c，不能用 --conf
# =======================================================
./cloudreve -c /app/conf.ini &
CLOUDREVE_PID=$!
echo "Cloudreve PID: $CLOUDREVE_PID"

# 等待 Cloudreve 启动
echo ">>> 等待服务就绪..."
for i in {1..10}; do
    # 检查进程是否意外退出
    if ! kill -0 $CLOUDREVE_PID 2>/dev/null; then
        echo "❌ 致命错误: Cloudreve 启动失败! 进程已退出。"
        exit 1
    fi

    # 检查端口是否通
    if curl -sf http://localhost:7860/ > /dev/null 2>&1; then
        echo "✅ Cloudreve 启动成功"
        break
    fi
    sleep 2
done

# 运行配置脚本
echo ">>> 配置存储策略..."
python3 /app/storage_policy.py

# 启动大文件同步引擎
echo ">>> 启动 HF 同步引擎..."
python3 /app/hf_sync.py &
SYNC_PID=$!

# 启动备份服务
python3 /app/backup_manager.py &
BACKUP_PID=$!

echo "==================================================="
echo "✅ 服务已全部启动! 请访问: http://localhost:7860"
echo "==================================================="

# 进程守护循环
while true; do
    if ! kill -0 $CLOUDREVE_PID 2>/dev/null; then
        echo "❌ Cloudreve 意外退出!"
        exit 1
    fi
    
    if ! kill -0 $SYNC_PID 2>/dev/null; then
        echo "⚠️ 同步引擎已停止，正在重启..."
        python3 /app/hf_sync.py &
        SYNC_PID=$!
    fi
    
    sleep 60
done
