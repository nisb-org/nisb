#!/bin/bash
# NISB Phase 3.0 部署脚本
# Relations + Synapses 混合模式一键部署

set -e  # 遇到错误立即退出

echo "=========================================="
echo "  NISB Phase 3.0 部署脚本"
echo "  Relations + Synapses 混合模式"
echo "=========================================="
echo ""

NISB_DIR="/opt/mcp-gateway/mcp-nisb"
DATA_DIR="/opt/nisb-data"

# 1. 检查文件是否存在
echo "🔍 [1/7] 检查文件..."

required_files=(
    "$NISB_DIR/core/classifier.py"
    "$NISB_DIR/core/synapses.py"
    "$NISB_DIR/tools/relations/unified.py"
)

for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ 缺少文件：$file"
        echo "请先创建所有必需文件"
        exit 1
    fi
done

echo "✅ 所有必需文件存在"
echo ""

# 2. 语法验证
echo "🔍 [2/7] 验证Python语法..."

cd "$NISB_DIR"

python3 -m py_compile core/classifier.py
python3 -m py_compile core/synapses.py
python3 -m py_compile core/relations.py
python3 -m py_compile tools/relations/unified.py
python3 -m py_compile tools/relations/discover.py
python3 -m py_compile nisb_mcp.py

echo "✅ 语法验证通过"
echo ""

# 3. 创建目录结构
echo "📁 [3/7] 创建Synapses目录结构..."

# 为每个用户创建Synapses目录
for user_dir in "$DATA_DIR/users"/*; do
    if [ -d "$user_dir" ]; then
        SYNAPSES_DIR="$user_dir/documents/storage/entities/synapses"
        mkdir -p "$SYNAPSES_DIR/by_type"
        mkdir -p "$SYNAPSES_DIR/index"
        echo "  创建：$SYNAPSES_DIR"
    fi
done

echo "✅ 目录结构创建完成"
echo ""

# 4. 备份现有数据
echo "💾 [4/7] 备份现有Relations数据..."

BACKUP_DIR="/root/nisb-phase3-backup-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

for user_dir in "$DATA_DIR/users"/*; do
    if [ -d "$user_dir/documents/storage/entities/relations" ]; then
        user_id=$(basename "$user_dir")
        cp -r "$user_dir/documents/storage/entities/relations" "$BACKUP_DIR/$user_id/"
        echo "  备份：$user_id"
    fi
done

echo "✅ 备份完成：$BACKUP_DIR"
echo ""

# 5. 测试分类器
echo "🧪 [5/7] 测试分类器..."

python3 << 'EOF'
import sys
sys.path.insert(0, '/opt/mcp-gateway/mcp-nisb')

from core.classifier import classify_relation, get_default_strength

# 测试1：静态关系
result1 = classify_relation('康德', '哲学家', 'is_a')
assert result1 == 'relation', f"测试1失败：期望relation，得到{result1}"

# 测试2：动态关系
result2 = classify_relation('康德', '先验', 'associated_with')
assert result2 == 'synapse', f"测试2失败：期望synapse，得到{result2}"

# 测试3：默认强度
strength1 = get_default_strength('relation', 'is_a')
assert strength1 == 0.95, f"测试3失败：期望0.95，得到{strength1}"

print("✅ 分类器测试通过")
EOF

echo ""

# 6. 测试Synapses
echo "🧪 [6/7] 测试Synapses模块..."

python3 << 'EOF'
import sys
sys.path.insert(0, '/opt/mcp-gateway/mcp-nisb')

from core.synapses import Synapse

# 创建测试Synapse
synapse = Synapse('syn_test', 'c_kant', 'c_a_priori', 'associated_with', 0.70)

# 测试激活
old_strength = synapse.strength
synapse.activate('query', 'test')
assert synapse.strength > old_strength, "Hebbian学习失败"
assert synapse.activation_count == 1, "激活计数错误"

print("✅ Synapses模块测试通过")
EOF

echo ""

# 7. 重启服务
echo "🔄 [7/7] 重启NISB服务..."

cd /opt/mcp-gateway
docker-compose restart mcp-nisb

echo "⏳ 等待服务启动..."
sleep 5

# 检查服务状态
if docker ps | grep -q mcp-nisb; then
    echo "✅ NISB服务已启动"
else
    echo "❌ NISB服务启动失败"
    echo "查看日志：docker logs mcp-nisb"
    exit 1
fi

echo ""
echo "=========================================="
echo "  🎉 Phase 3.0 部署完成！"
echo "=========================================="
echo ""
echo "📊 部署总结："
echo "  ✅ 分类器：core/classifier.py"
echo "  ✅ 动态突触：core/synapses.py"
echo "  ✅ 统一接口：tools/relations/unified.py"
echo "  ✅ 批次发现：已支持自动分类"
echo "  ✅ 数据备份：$BACKUP_DIR"
echo ""
echo "🎯 下一步："
echo "  1. 在LibreChat中测试新工具：nisb_query_all"
echo "  2. 运行数据迁移分析：nisb_migrate_to_hybrid (dry_run=True)"
echo "  3. 批次发现关系（自动分类）：nisb_discover_relations_batch"
echo ""
echo "📚 新工具列表："
echo "  - nisb_query_all：统一查询（Relations+Synapses）"
echo "  - nisb_create_unified：统一创建（自动分类）"
echo "  - nisb_migrate_to_hybrid：数据迁移分析"
echo "  - nisb_synapse_decay：突触衰减"
echo ""
echo "查看日志：docker logs mcp-nisb --tail 50"
echo ""

