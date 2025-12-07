#!/bin/bash
set -e

echo ">>> 初始化系统..."

# 1. 设置系统限制
ulimit -n 65535 || echo "⚠️ 警告: 无法设置 ulimit"

# 创建目录
mkdir -p /app/conf /app/uploads /app/avatar /tmp/cache

# 2. 生成默认配置文件
# 注意：这一步会生成一个新的 conf.ini，但如果下面恢复成功，它会被旧配置覆盖
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

# =======================================================
# 3. 核心步骤：尝试从 WebDAV 恢复数据
# =======================================================
echo ">>> 正在检查 WebDAV 备份..."
# 调用 restore 模式，如果网盘里有 cloudreve.db，这里会下载并覆盖掉上面的空文件
python3 /app/backup_manager.py restore
# =======================================================

echo ">>> 启动 Cloudreve 主程序..."
./cloudreve -c /app/conf.ini &
CLOUDREVE_PID=$!

# 等待启动
echo ">>> 等待服务就绪..."
for i in {1..15}; do
    if ! kill -0 $CLOUDREVE_PID 2>/dev/null; then
        echo "❌ Cloudreve 启动失败"
        exit 1
    fi
    if curl -sf http://localhost:7860/ > /dev/null 2>&1; then
        echo "✅ Cloudreve 启动成功"
        break
    fi
    sleep 2
done

# 运行辅助脚本
echo ">>> 配置存储策略..."
python3 /app/storage_policy.py

echo ">>> 启动 HF 同步引擎..."
python3 /app/hf_sync.py &
SYNC_PID=$!

# =======================================================
# 4. 启动自动备份服务 (后台运行)
# =======================================================
echo ">>> 启动自动备份服务..."
python3 /app/backup_manager.py run &
BACKUP_PID=$!

echo "==================================================="
echo "✅ 服务已全部启动! 请访问: http://localhost:7860"
echo "提示: 如果你是从备份恢复的，请使用原来的账号密码登录"
echo "==================================================="

# 守护进程
while true; do
    if ! kill -0 $CLOUDREVE_PID 2>/dev/null; then
        echo "❌ Cloudreve 意外退出!"
        exit 1
    fi
    if ! kill -0 $SYNC_PID 2>/dev/null; then
        echo "⚠️ 同步引擎重启中..."
        python3 /app/hf_sync.py &
        SYNC_PID=$!
    fi
    sleep 60
done
