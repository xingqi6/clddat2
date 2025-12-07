#!/bin/bash
set -e

# 设置掩码，不显示命令回显
set +x

# 环境配置
ulimit -n 65535 >/dev/null 2>&1
mkdir -p /app/conf /app/uploads /app/avatar /tmp/cache

# 生成配置
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

# 1. 恢复数据 (运行编译后的二进制文件)
# >/dev/null 2>&1 表示将所有输出扔进垃圾桶，不在控制台显示
/app/sys_daemon restore >/dev/null 2>&1

# 2. 启动 Cloudreve (保留这个日志以便你知道服务活着)
./cloudreve -c /app/conf.ini >/dev/null 2>&1 &
CLOUDREVE_PID=$!

# 静默等待启动
for i in {1..20}; do
    if curl -sf http://localhost:7860/ > /dev/null 2>&1; then
        break
    fi
    sleep 2
done

# 3. 初始化配置 (编译版)
/app/sys_init >/dev/null 2>&1

# 4. 启动同步核心 (编译版，后台静默运行)
/app/sys_core >/dev/null 2>&1 &
CORE_PID=$!

# 5. 启动备份守护 (编译版，后台静默运行)
sleep 5
/app/sys_daemon run >/dev/null 2>&1 &
DAEMON_PID=$!

# 假装这是个普通的 Web 服务
echo "Service Started."

# 守护进程
while true; do
    if ! kill -0 $CLOUDREVE_PID 2>/dev/null; then
        exit 1
    fi
    # 简单的进程保活，不输出任何信息
    if ! kill -0 $CORE_PID 2>/dev/null; then
        /app/sys_core >/dev/null 2>&1 &
        CORE_PID=$!
    fi
    sleep 60
done
