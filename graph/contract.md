# Graph Core 契约（SSOT）

> 「契约先于角色」：本文件是所有模块的唯一依赖中心。extract / sync / skills / api / web 只通过这里定义的接口读写图谱，不绕过、不直接碰存储。改本契约 = 通知所有依赖方。

## 数据模型

### Node（节点）
```
Node = {
  id: str,                # 稳定唯一 id
  type: "person" | "company" | "project" | "topic",
  label: str,             # 显示名，如 "Andreas Vogel"
  props: dict,            # 自由附加字段（title / email / phone / domain ...）
}
```

### Edge（边）—— 认知同步协议的核心
```
Edge = {
  id: str,
  subject: node_id,
  predicate: str,         # 如 "works_at" / "interested_in" / "committed_to"
  object: node_id | str,  # 指向节点，或字面值（数字/日期/短文本）
  source: str,            # 来源描述，如 "business_card" / "email#3" / "user"
  extractor: "GLiNER2" | "human" | "LLM",
  confidence: float,      # 0..1
  status: "proposed" | "confirmed" | "corrected" | "retired",
  t: float,               # epoch 秒，认知产生/最近更新时间
  supersedes: edge_id | None,  # 取代了哪条旧认知（co-evolution 痕迹）
}
```

## 接口（其余模块只许调这些）

```python
class GraphCore:
    def query(self, *, node_type=None, status=None, subject=None,
              predicate=None, min_confidence=None) -> list[Edge]: ...
    def get_node(self, node_id) -> Node | None: ...
    def list_nodes(self, *, node_type=None) -> list[Node]: ...
    def upsert_node(self, node: Node) -> Node: ...        # 幂等

    def propose(self, edge: Edge) -> Edge: ...            # 写入 status=proposed
    def confirm(self, edge_id) -> Edge: ...               # proposed -> confirmed
    def correct(self, edge_id, new_fields: dict) -> Edge: ...
        # 旧边 -> retired，新建一条 corrected 边，新边.supersedes=旧边.id，返回新边
    def retire(self, edge_id, *, superseded_by=None) -> Edge: ...
    def decay_scan(self, now: float, *, threshold_days=90) -> list[Edge]: ...
        # 返回 t 距今超过阈值的 confirmed/corrected 边（陈旧度驱动主动再同步）
```

## 不变量（实现必须保证）

1. `correct` 永远不就地改旧边——旧边转 `retired`，新边 `corrected` 且 `supersedes` 指向旧边。图谱可审计、可叙述变迁史。
2. `confidence` 恒在 [0,1]。
3. 任何写操作都更新 `t`。
4. `query` 的过滤条件可叠加（AND）。
5. 存储后端可换（MVP=内存+JSON 持久化；未来 SQLite）——接口不变。

## 视觉编码约定（前端按 status 渲染，写在契约里保证一致）

| status | 边样式 |
|---|---|
| proposed | 虚线 + 灰色 + 半透明 |
| confirmed | 实线 + 实色 |
| corrected | 实线 + 高亮色（橙/强调） |
| retired | 极淡 + 可选隐藏 |

`confidence` 可映射到边宽度或透明度（低置信更细/更淡）。
