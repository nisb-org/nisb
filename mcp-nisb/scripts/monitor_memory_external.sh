#!/bin/bash
# 轻量级内存监控（宿主机直接运行，不进容器）

set -e

CONTAINER_NAME="${1:-mcp-nisb}"  # 默认容器名，可通过参数传入
INTERVAL=5  # 采样间隔（秒）
DURATION=300  # 监控时长（秒）

echo "📊 Monitoring container: $CONTAINER_NAME"
echo "⏱️  Interval: ${INTERVAL}s, Duration: ${DURATION}s"
echo "🔥 Press Ctrl+C to stop early"
echo ""
echo "Time,RSS(MB),Swap(MB),VSZ(MB),CPU%"

# 获取容器内主进程 PID（在宿主机上的 PID）
get_container_pid() {
    docker inspect -f '{{.State.Pid}}' "$CONTAINER_NAME" 2>/dev/null || echo ""
}

PID=$(get_container_pid)
if [ -z "$PID" ] || [ "$PID" == "0" ]; then
    echo "❌ Container not found or not running: $CONTAINER_NAME"
    exit 1
fi

echo "✅ Found container PID: $PID"
echo ""

START_TIME=$(date +%s)
MAX_RSS=0
MAX_SWAP=0

while true; do
    NOW=$(date +%s)
    ELAPSED=$((NOW - START_TIME))
    
    if [ $ELAPSED -ge $DURATION ]; then
        break
    fi
    
    # 读取进程状态（/proc/$PID/status）
    if [ -f "/proc/$PID/status" ]; then
        RSS=$(grep "^VmRSS:" /proc/$PID/status | awk '{print $2}')  # KB
        SWAP=$(grep "^VmSwap:" /proc/$PID/status | awk '{print $2}')  # KB
        VSZ=$(grep "^VmSize:" /proc/$PID/status | awk '{print $2}')  # KB
        
        # 转换为 MB
        RSS_MB=$((RSS / 1024))
        SWAP_MB=$((SWAP / 1024))
        VSZ_MB=$((VSZ / 1024))
        
        # 获取 CPU 使用率
        CPU=$(ps -p $PID -o %cpu= 2>/dev/null || echo "0")
        
        # 记录峰值
        if [ $RSS_MB -gt $MAX_RSS ]; then
            MAX_RSS=$RSS_MB
        fi
        if [ $SWAP_MB -gt $MAX_SWAP ]; then
            MAX_SWAP=$SWAP_MB
        fi
        
        # 输出（CSV 格式）
        printf "%03d,%d,%d,%d,%.1f\n" $ELAPSED $RSS_MB $SWAP_MB $VSZ_MB $CPU
    else
        echo "⚠️  Process $PID disappeared, trying to relocate..."
        PID=$(get_container_pid)
        if [ -z "$PID" ] || [ "$PID" == "0" ]; then
            echo "❌ Container stopped"
            break
        fi
    fi
    
    sleep $INTERVAL
done

echo ""
echo "="
echo "📈 Peak Memory Usage:"
echo "   - RSS:  ${MAX_RSS} MB"
echo "   - Swap: ${MAX_SWAP} MB"
echo ""

# 检查是否有内存泄漏迹象
if [ $MAX_SWAP -gt 500 ]; then
    echo "🔥 WARNING: High swap usage detected ($MAX_SWAP MB)"
    echo "   Likely causes:"
    echo "   1. Memory leak in Python code"
    echo "   2. Large dataset caching (embedding/QA map)"
    echo "   3. Jieba dictionary loaded multiple times"
    echo ""
fi

