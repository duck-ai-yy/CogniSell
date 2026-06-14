# CogniSell 黑客松前端完全重做 — 实现计划 v2

## 目标

将现有后端 + 简陋前端，升级为**黑客松可演示的 premium demo**。设计语言对标 Perplexity / Claude 亮色极简风。

---

## 核心设计决策

### 布局

```
┌──────────────────────────────────────────────────────────────────────┐
│  CogniSell · Relationship OS                        Watching 5 rels │
├───────────────────────────┬──────────────────────────────────────────┤
│                           │                                          │
│  LEFT: 人脉网络            │  RIGHT: 对话 + 任务流                    │
│                           │                                          │
│  ┌─────────────────────┐  │  ┌────────────────────────────────────┐  │
│  │                     │  │  │ Agent Activity (Perplexity 风格)   │  │
│  │   Cytoscape.js      │  │  │  ✓ Scout: Read Andreas Vogel       │  │
│  │   头像做节点         │  │  │  ● Enricher: Pulling profiles...   │  │
│  │   点击 → 详情卡      │  │  │  ⏳ Strategist: Debating...        │  │
│  │                     │  │  └────────────────────────────────────┘  │
│  │   ┌──────────────┐  │  │                                          │
│  │   │ 详情卡 (浮层) │  │  │  ┌────────────────────────────────────┐  │
│  │   │ 头像/名/职位  │  │  │  │ Decision Cards                    │  │
│  │   │ 公司/温度     │  │  │  │  Confirm company for Andreas...   │  │
│  │   │ 关系摘要      │  │  │  │  Signal: Nordic Drives tender...  │  │
│  │   └──────────────┘  │  │  └────────────────────────────────────┘  │
│  │                     │  │                                          │
│  └─────────────────────┘  │  ┌────────────────────────────────────┐  │
│                           │  │ 🎙 输入栏 (语音/文字/📷拍照)       │  │
│                           │  └────────────────────────────────────┘  │
└───────────────────────────┴──────────────────────────────────────────┘
```

### 视觉风格：亮色极简（Perplexity / Claude register）

- **配色**：暖白底 `#fafaf8`，纯白卡片 `#ffffff`，墨色文字 `#1a1a1a`
- **强调色**：teal `#0d9488`（确认/主操作），amber `#d97706`（corrected），淡灰 `#9ca3af`（proposed）
- **字体**：Inter (Google Fonts CDN)，hairline 字重对比
- **卡片**：纯白 + 细边框 `1px solid #e5e5e5` + 微阴影，圆角 `14px`
- **Agent Activity**：类 Perplexity 的 source-card 行列，左侧彩色 agent 圆点 + 名字 + 流式打字文字 + 右侧状态

### 图谱节点视觉

| 类型 | 节点样式 |
|---|---|
| Person | 圆形，DiceBear Initials 头像（`https://api.dicebear.com/7.x/initials/svg?seed=Name`），离线 fallback = CSS 首字母圆 |
| Company | 圆角方形，深色背景 + 白色首字母 |
| Project / Topic | 小圆形，浅色 |

### 视觉状态

| 状态 | 视觉效果 |
|---|---|
| 90+ 天未联系 | 头像变灰色 `filter: grayscale(1)` |
| Agent 自动更新了信息 | 头像右上角 🔴 红点（统一标识"有新变化需 review"） |
| Proposed 边 | 虚线 + 半透明 |
| Confirmed 边 | 实线 + 全色 |
| Corrected 边 | 实线 + amber 高亮 |

---

## Proposed Changes

### 1. HTML 重构

#### [MODIFY] [index.html](file:///Users/gloriayin/projects/second-brain-crm/web/index.html)

完全重写结构：

- **Topbar**：品牌名 CogniSell + 状态数字
- **左区**：满铺关系图谱（Cytoscape.js），点击节点弹出详情卡（overlay 在图谱上）
- **右区**：Agent Activity 流 → Decision Cards → 底部输入栏
- 引入 Google Fonts Inter + DiceBear

---

### 2. CSS 完全重写

#### [MODIFY] [style.css](file:///Users/gloriayin/projects/second-brain-crm/web/static/style.css)

全新亮色设计系统：

```css
--bg: #fafaf8;
--surface: #ffffff;
--surface-2: #f5f5f3;
--border: #e5e5e5;
--ink: #1a1a1a;
--ink-2: #6b7280;
--ink-3: #9ca3af;
--accent: #0d9488;
--accent-soft: #ccfbf1;
--corrected: #d97706;
--proposed: #9ca3af;
--danger: #ef4444;         /* 红点 */
```

关键样式：
- Agent activity 行：圆形彩色 agent dot + 名字（600 weight）+ 描述文字 + spinner/✓
- Decision card：白卡 + 细边 + hover 微升 `transform: translateY(-1px)`
- 详情卡浮层：位于左区右侧，滑入动画，半透明背景
- 温度指示器：在详情卡中以文字颜色（🟢 Hot / 🟡 Warm / ⚫ Cold）展示
- Avatar 红点：`::after` 伪元素绝对定位右上角

---

### 3. JavaScript 重写

#### [MODIFY] [app.js](file:///Users/gloriayin/projects/second-brain-crm/web/static/app.js)

**a) 头像图谱**
- Person 节点使用 DiceBear `background-image`，大尺寸（48px）
- Company 节点用颜色块 + 白色首字母
- 90 天未联系的 person → Cytoscape 样式 `filter: grayscale(1)`
- Agent 自动更新的节点 → 前端维护一个 `updatedNodes: Set`，渲染时加红点 overlay

**b) 点击 → 详情卡**
- 点击 person/company 节点 → 左区弹出详情卡浮层
- 详情卡内容：头像大图、姓名、职位、公司、邮箱、温度状态、关系摘要（当前 edge 列表）、认知变迁历史
- 点击空白处关闭

**c) Agent Activity 流式展示（Perplexity 风格）**
- 每个 agent 有颜色编码（Scout=蓝, Enricher=绿, Strategist=紫, Outreach=橙, Digest=teal, Relationship=粉, Signals=金）
- 流式打字效果：文字逐字显示（15ms/char），模拟 agent 正在思考
- 完成态：spinner → ✓（带 scale 弹跳动画）
- 折叠推理：可选展开 agent 的推理过程

**d) 完整 Demo 流程**

**场景 ①：名片扫描**
```
用户点击 📷 → 
  Activity: Scout "Reading business card (OCR)…" [streaming]
  Activity: Scout "Found: Andreas Vogel · Head of Procurement · Stahlwerk Nord" ✓
  Activity: Enricher "Matching company & pulling public profiles…" [streaming]
  Activity: Enricher "Linked to Stahlwerk Nord GmbH · Steel manufacturing · ~1200 employees" ✓
  → 图谱出现 Andreas 节点（头像）+ 虚线边 → Stahlwerk Nord
  → 右侧出 Decision Card: "Confirm company for Andreas"
  → 用户点 Confirm → 虚线边动画变实线 → 图谱刷新
  → 出 "Add details" 卡（when/where met）→ 保存
```

**场景 ②：社媒信号 + 策略 + 邮件**
```
自动触发 →
  Activity: Social Monitor "Scanning tracked contacts' feeds…" [streaming]
  Activity: Social Monitor "Detected: Nordic Drives AB may be going to tender" ✓
  → Signal 卡出现
  → 同时：Strategist debate（Champion/Skeptic/Closer 三角色依次出现在 Activity）
  → Outreach "Drafting follow-up email using graph context…" → 邮件草拟卡
```

**场景 ③：90 天 warm-up**
```
  Activity: Relationship "Scanning your book for cooling relationships…"
  Activity: Relationship "Found: Markus Brandt — 92 days since last contact" ✓
  → Markus 头像变灰色
  → Warm-up 卡出现，含 catch-up 建议
  → 用户可纠正 title → 建议重算
```

**场景 ④：客户跳槽（Agent 自动更新）**
```
  Activity: Social Monitor "Detected job change: Henrik Sørensen"
  Activity: Social Monitor "Henrik moved from Aalborg Maskin → Siemens AG" ✓
  → 图谱边动画更新（旧边消失，新边出现）
  → Henrik 头像出现 🔴 红点（= 有 agent 自动更新，待 review）
  → 用户点击头像看详情 → 看到新旧公司变迁
```

**e) 输入栏**
- Claude 风格：圆角大输入框 + 左侧麦克风 icon + 右侧发送按钮
- 支持语音（Web Speech API，fallback 到文字）
- 📷 按钮触发 scan 流程

---

### 4. 后端微调

#### [MODIFY] [main.py](file:///Users/gloriayin/projects/second-brain-crm/api/main.py)

- 新增 `POST /api/signals/job-change`：接收 `{contact_id, new_company_name}`，correct works_at 边
- 新增 `GET /api/contact/{contact_id}`：返回联系人详情 + 所有 active 边
- 新增启动参数 `DEMO_RESET=1` 时删除 graph_store.json 重新 seed

#### [MODIFY] [seed_data.py](file:///Users/gloriayin/projects/second-brain-crm/seed/seed_data.py)

- 给所有 noise 联系人补充 props（title, email），让详情卡有内容

---

## Verification Plan

### Manual Verification (鸭鸭走查清单)

1. 删除 `graph_store.json`，`uvicorn api.main:app --reload`
2. 打开 `http://127.0.0.1:8000`，确认亮色极简界面
3. 左区看到种子联系人头像图谱，Markus 头像是灰色的（92 天未联系）
4. 点击 📷 Scan → Agent Activity 流式展示 → Andreas 头像出现 → 虚线边
5. 点 Confirm → 虚线变实线动画
6. 社媒信号卡出现 → 策略 debate activity → 邮件草拟
7. Warm-up 卡出现（Markus 相关）
8. Henrik 跳槽 → 红点出现 → 点击看变迁
9. 全程无 console error，失败路径有 toast 提示
