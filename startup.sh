#!/bin/bash
set -e

echo ">>> 初始化系统..."

# 系统优化：增加文件描述符上限 (防止大文件并发报错)
ulimit -n 65535

# 创建必要目录
mkdir -p /app/conf
mkdir -p /app/uploads
mkdir -p /app/avatar
mkdir -p /tmp/cache

# 生成 Cloudreve 配置文件 (conf.ini)
# 关键修改：设置 100GB 大小限制和 48小时超时
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

[OptionOverwrite]
# 最大文件大小: 100GB (单位字节 107374182400)
max_edit_size = 107374182400
# 上传超时时间: 48小时 (单位秒 172800) - 防止慢速网络断连
upload_session_timeout = 172800
# 禁用缩略图生成 (大文件生成缩略图极耗内存)
thumb_width = 0
thumb_height = 0

[CORS]
AllowOrigins = *
AllowMethods = GET,POST,PUT,DELETE,OPTIONS
AllowHeaders = *
AllowCredentials = true
EOFCONF

echo ">>> 启动 Cloudreve 主程序..."
./cloudreve --conf /app/conf.ini > /tmp/cloudreve.log 2>&1 &
CLOUDREVE_PID=$!

# 等待 Cloudreve 启动完毕
echo ">>> 等待服务就绪..."
for i in {1..30}; do
    if curl -sf http://localhost:7860/ > /dev/null 2>&1; then
        echo "✅ Cloudreve 启动成功"
        break
    fi
    sleep 2
done

# 运行配置脚本 (设置存储策略)
echo ">>> 配置存储策略..."
python3 /app/storage_policy.py

# 启动大文件同步引擎
echo ">>> 启动 HF 同步引擎..."
python3 /app/hf_sync.py > /tmp/hf_sync.log 2>&1 &
SYNC_PID=$!

# 启动备份服务
echo ">>> 启动配置备份..."
python3 /app/backup_manager.py > /tmp/backup.log 2>&1 &
BACKUP_PID=$!

echo "==================================================="
echo "✅ 服务已全部启动! 请访问: http://localhost:7860"
echo "管理员账号密码请查看下方日志"
echo "==================================================="

# 进程守护循环
while true; do
    if ! kill -0 $CLOUDREVE_PID 2>/dev/null; then
        echo "⚠️ Cloudreve 已停止，正在重启..."
        ./cloudreve --conf /app/conf.ini > /tmp/cloudreve.log 2>&1 &
        CLOUDREVE_PID=$!
    fi
    
    if ! kill -0 $SYNC_PID 2>/dev/null; then
        echo "⚠️ 同步引擎已停止，正在重启..."
        python3 /app/hf_sync.py > /tmp/hf_sync.log 2>&1 &
        SYNC_PID=$!
    fi

    # 输出最新日志以便在 Docker 控制台查看账号密码
    tail -n 10 /tmp/cloudreve.log
    
    sleep 60
done
