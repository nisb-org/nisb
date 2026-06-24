#!/bin/bas
NISB Hebbian Pipeline Deployment Script

set -e

echo "🚀 NISB Hebbian 管道部署开始..."
Step 1: Create hebbian.py

echo "1️⃣ 创建 hebbian.py..."
cat > /opt/mcp-gateway/mcp-nisb/tools/chat/hebbian.py << 'EOF'
-- coding: utf-8 --

"""
NISB Hebbian Learning Pipeline - Reusable Middleware
Phase 3.2: Chat -> Concept Extraction -> Co-occurrence Detection -> Relations/Synapses

import os
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, '/srv')

def extract_concepts_from_content(content: str, base_path: str, top_k: int = 10) -> List[str]:
"""Extract concepts from conten

text
try:
    concepts = _extract_concepts_from_text(content, top_k=top_k, base_path=base_path)
    return concepts
except Exception as e:
    print(f"[ERROR hebbian] Concept extraction failed: {e}", file=sys.stderr)
    return []

def detect_concept_cooccurrence(concepts: List[str], window: int = 6) -> List[Tuple[str, str]]:
"""Detect concept co-occurrence pairs (window=6

text
for i, concept_a in enumerate(concepts):
    start = max(0, i - window // 2)
    end = min(len(concepts), i + window // 2 + 1)
    
    for j in range(start, end):
        if i == j:
            continue
        
        concept_b = concepts[j]
        pair = tuple(sorted([concept_a, concept_b]))
        pairs.add(pair)

return list(pairs)

def get_or_create_concept_id(base_path: str, concept_name: str) -> str:
"""Get or create concept I

text
concept_id = _generate_concept_id(concept_name)
entity_file = Path(base_path) / f"storage/entities/concepts/by_id/{concept_id}.json"

if entity_file.exists():
    return concept_id

now = datetime.now().isoformat()
entity_data = {
    "id": concept_id,
    "name": concept_name,
    "name_zh": concept_name,
    "created_at": now,
    "last_active": now,
    "activation_weight": 0.1,
    "status": "cold",
    "discussion_count": 0,
    "related_records": [],
    "tags": [],
    "category": "auto_extracted_hebbian"
}

entity_file.parent.mkdir(parents=True, exist_ok=True)
save_json(str(entity_file), entity_data)

print(f"[DEBUG hebbian] New concept: {concept_name} -> {concept_id}", file=sys.stderr)
return concept_id

def create_relation_from_pair(base_path: str, concept_a: str, concept_b: str) -> dict:
"""Create Relations or Synapses for concept pai

text
concept_a_id = get_or_create_concept_id(base_path, concept_a)
concept_b_id = get_or_create_concept_id(base_path, concept_b)

try:
    result = create_relation_or_synapse(
        base_path=base_path,
        from_id=concept_a_id,
        to_id=concept_b_id,
        relation_type="associated_with",
        source="hebbian_chat",
        evidence="Co-occurred in conversation (Hebbian learning)",
        strategy="hebbian_cooccurrence",
        bidirectional=True
    )
    return result
except Exception as e:
    print(f"[ERROR hebbian] Failed to create relation {concept_a} <-> {concept_b}: {e}", file=sys.stderr)
    return {"status": "error", "message": str(e)}

def process_conversation_hebbian(base_path: str, user_content: str, ai_content: str):
"""Process Hebbian learning for conversation (main entry point

text
print(f"[INFO hebbian] Starting Hebbian learning...", file=sys.stderr)

# 1. Extract concepts
concepts_user = extract_concepts_from_content(user_content, base_path, top_k=10)
concepts_ai = extract_concepts_from_content(ai_content, base_path, top_k=10)

all_concepts = concepts_user + concepts_ai

if len(all_concepts) == 0:
    print(f"[WARN hebbian] No concepts extracted, skipping", file=sys.stderr)
    return

print(f"[DEBUG hebbian] Extracted concepts: User={len(concepts_user)}, AI={len(concepts_ai)}", file=sys.stderr)

# 2. Detect co-occurrence
pairs = detect_concept_cooccurrence(all_concepts, window=6)

if len(pairs) == 0:
    print(f"[WARN hebbian] No co-occurrence pairs detected, skipping", file=sys.stderr)
    return

print(f"[DEBUG hebbian] Detected {len(pairs)} co-occurrence pairs", file=sys.stderr)

# 3. Create relations
created_count = 0
failed_count = 0
skipped_count = 0

for concept_a, concept_b in pairs:
    result = create_relation_from_pair(base_path, concept_a, concept_b)
    
    if result.get("status") == "success":
        created_count += 1
    elif "已存在" in result.get("message", "") or "exists" in result.get("message", "").lower():
        skipped_count += 1
    else:
        failed_count += 1

# 4. Log results
end_time = datetime.now()
duration = (end_time - start_time).total_seconds()

log_entry = {
    "timestamp": end_time.isoformat(),
    "concepts_extracted": len(all_concepts),
    "pairs_detected": len(pairs),
    "relations_created": created_count,
    "relations_skipped": skipped_count,
    "relations_failed": failed_count,
    "duration_seconds": duration
}

log_file = Path(base_path) / "logs" / f"hebbian_{datetime.now().strftime('%Y%m')}.log"
log_file.parent.mkdir(parents=True, exist_ok=True)

with open(log_file, "a", encoding="utf-8") as f:
    f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

print(f"[INFO hebbian] Done! Created {created_count}, skipped {skipped_count}, failed {failed_count}, took {duration:.2f}s", file=sys.stderr)

all = ['process_conversation_hebbian']

echo "✅ hebbian.py 已创建"
Step 2: Backup original file

echo "2️⃣ 备份原始 chat/init.py..."
cp /opt/mcp-gateway/mcp-nisb/tooinit.py
/opt/mcp-gateway/mcp-nisb/tools/chat/init.py.backup_$(date +%Y%m%d_%H%M%S)
echo "✅ 备份已创建"
Step 3: Patch chat/init.py

echo "3️⃣ 修改 chat/init.py..."
python3 << 'PYSCRIPT'

file_path = '/opt/mcp-gateway/mcp-nisb/tools/chat/init.py'

with open(file_path, 'r', encoding='utf-8') as f:
Find insertion point (before the last return in nisb_chat_send)

pattern = r'( with openmetafile,"w"metafile,"w" as f:\s+json\.dumpmeta,f,indent=2,ensureascii=Falsemeta,f,indent=2,ensureascii=False\s+)( return \{)'

hebbian_code = '''
# Hebbian learning
ipel
ne try: from tools.chat.hebbian import
rocess_conversation_hebbian process_conversation_h
bbian(user_ctx.base, content, response) print(f"[INFO
chat] Hebbian learning
triggered", file
sys.stderr) except Exception as e: import traceback

'''

replacement = r'\1' + hebbian_code + r'\2'

new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:

print("OK")
PYSC

if [ $? -eq 0 ]; then
init.py 已修改"
else
echo "❌ 修改失败，请检
文件"
e
Step 4: Restart container

echo "4️⃣ 重启 mcp-nisb 容器..."
docker restart mcp-nisb
echo "✅ 容器已重启"
Step 5: Wait for startup

echo "5️⃣ 等待容器启动（10秒）..."
sleep 10
echo "✅ 容器已就绪"

echo "🎉 部署完成！"
echo ""
echo "📋 下一步："
echo " 1. 在 Web 端发送测试对话"
echo " 2. 检查日志：docker logs mcp-nisb | grep hebbian"
echo " 3. 检查数据：ls -lh /opt/nisb-data/users/nisb_ceebc6ebbe009f09/storage/entities/synapses/by_type/"
