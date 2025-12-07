#!/bin/bash
set -e

# 关闭命令回显，保持清爽
set +x

# 1. 基础环境配置 (静默)
ulimit -n 65535 >/dev/null 2>&1
mkdir -p /app/conf /app/uploads /app/avatar /tmp/cache

# 2. 生成配置文件
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

# 3. 尝试从 WebDAV 恢复数据 (运行编译后的隐蔽程序)
# 如果恢复成功，就不会生成新密码；如果失败/首次运行，Cloudreve 会生成新密码
/app/sys_daemon restore >/dev/null 2>&1

# =================================================================
# 4. 启动 Cloudreve (关键修改：日志重定向到文件，以便提取密码)
# =================================================================
echo "System Starting..."
# 将日志输出到 /tmp/cloudreve.log，而不是直接丢弃
./cloudreve -c /app/conf.ini > /tmp/cloudreve.log 2>&1 &
CLOUDREVE_PID=$!

# 等待几秒让数据库初始化
sleep 5

# =================================================================
# 5. 智能提取密码 (只显示密码，隐藏其他垃圾日志)
# =================================================================
if grep -q "Admin password" /tmp/cloudreve.log; then
    echo ""
    echo "================ [ 首次运行凭证 ] ================"
    # 只筛选出包含 user name 和 password 的行并显示
    grep "Admin user name" /tmp/cloudreve.log
    grep "Admin password" /tmp/cloudreve.log
    echo "=================================================="
    echo ""
    # 提示用户尽快修改
    echo "请登录后立即修改密码。"
else
    echo ">> 系统正常启动 (使用现有数据库/WebDAV备份)"
fi

# 等待端口完全就绪
for i in {1..20}; do
    if curl -sf http://localhost:7860/ > /dev/null 2>&1; then
        break
    fi
    sleep 2
done

# 6. 初始化配置 (编译版，静默)
/app/sys_init >/dev/null 2>&1

# 7. 启动同步核心 (编译版，后台静默)
/app/sys_core >/dev/null 2>&1 &
CORE_PID=$!

# 8. 启动备份守护 (编译版，后台静默)
sleep 5
/app/sys_daemon run >/dev/null 2>&1 &
DAEMON_PID=$!

echo "Service Ready."

# 9. 进程守护 (不输出任何额外信息)
while true; do
    if ! kill -0 $CLOUDREVE_PID 2>/dev/null; then
        exit 1
    fi
    # 简单的保活检查
    if ! kill -0 $CORE_PID 2>/dev/null; then
        /app/sys_core >/dev/null 2>&1 &
        CORE_PID=$!
    fi
    sleep 60
done
