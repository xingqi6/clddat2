#!/bin/bash

echo "======================================"
echo "云存储系统 - 自动部署脚本"
echo "======================================"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查必要的工具
check_requirements() {
    echo -e "${YELLOW}检查系统要求...${NC}"
    
    if ! command -v git &> /dev/null; then
        echo -e "${RED}错误: 未安装 git${NC}"
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}错误: 未安装 docker${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ 系统要求检查通过${NC}"
}

# 收集配置信息
collect_config() {
    echo -e "\n${YELLOW}请输入配置信息:${NC}"
    
    read -p "WebDAV 服务器地址: " WEBDAV_URL
    read -p "WebDAV 用户名: " WEBDAV_USERNAME
    read -sp "WebDAV 密码: " WEBDAV_PASSWORD
    echo
    read -p "备份文件夹名称 [sys_backup]: " WEBDAV_BACKUP_PATH
    WEBDAV_BACKUP_PATH=${WEBDAV_BACKUP_PATH:-sys_backup}
    read -p "备份间隔(秒) [3600]: " SYNC_INTERVAL
    SYNC_INTERVAL=${SYNC_INTERVAL:-3600}
    
    read -sp "Hugging Face Token: " HF_TOKEN
    echo
    read -p "Dataset 仓库名 [storage-data]: " HF_DATASET_REPO
    HF_DATASET_REPO=${HF_DATASET_REPO:-storage-data}
    
    # 创建 .env 文件
    cat > .env <<EOF
WEBDAV_URL=$WEBDAV_URL
WEBDAV_USERNAME=$WEBDAV_USERNAME
WEBDAV_PASSWORD=$WEBDAV_PASSWORD
WEBDAV_BACKUP_PATH=$WEBDAV_BACKUP_PATH
SYNC_INTERVAL=$SYNC_INTERVAL
HF_TOKEN=$HF_TOKEN
HF_DATASET_REPO=$HF_DATASET_REPO
EOF
    
    echo -e "${GREEN}✓ 配置已保存到 .env${NC}"
}

# 构建 Docker 镜像
build_image() {
    echo -e "\n${YELLOW}开始构建 Docker 镜像...${NC}"
    
    docker build -t clddat:latest .
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ 镜像构建成功${NC}"
    else
        echo -e "${RED}✗ 镜像构建失败${NC}"
        exit 1
    fi
}

# 启动容器
start_container() {
    echo -e "\n${YELLOW}启动容器...${NC}"
    
    # 停止已存在的容器
    docker stop clddat 2>/dev/null
    docker rm clddat 2>/dev/null
    
    # 启动新容器
    docker run -d \
        --name clddat \
        -p 7860:7860 \
        --env-file .env \
        --restart unless-stopped \
        clddat:latest
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ 容器启动成功${NC}"
        echo -e "\n${GREEN}访问地址: http://localhost:7860${NC}"
    else
        echo -e "${RED}✗ 容器启动失败${NC}"
        exit 1
    fi
}

# 显示日志
show_logs() {
    echo -e "\n${YELLOW}显示容器日志...${NC}"
    echo -e "${YELLOW}按 Ctrl+C 退出日志查看${NC}\n"
    sleep 2
    docker logs -f clddat
}

# 主函数
main() {
    check_requirements
    
    if [ ! -f .env ]; then
        collect_config
    else
        echo -e "${YELLOW}发现已有配置文件 .env${NC}"
        read -p "是否重新配置? (y/N): " RECONFIG
        if [[ $RECONFIG =~ ^[Yy]$ ]]; then
            collect_config
        fi
    fi
    
    build_image
    start_container
    
    read -p "是否查看日志? (Y/n): " SHOW_LOGS
    if [[ ! $SHOW_LOGS =~ ^[Nn]$ ]]; then
        show_logs
    fi
}

# 执行主函数
main
