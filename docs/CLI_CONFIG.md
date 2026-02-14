# CLI 配置管理指南

## 查看当前配置

```bash
./temple.sh config show
```

显示当前项目的所有配置，包括：
- API Key 状态
- 当前项目
- 模拟参数
- 内存管理参数
- 活跃代理
- 代理模型设置

## 修改配置

### 1. 模拟参数

启用/禁用自动模拟：
```bash
./temple.sh config set simulation.enabled true
./temple.sh config set simulation.enabled false
```

设置模拟间隔（秒）：
```bash
./temple.sh config set simulation.min 5
./temple.sh config set simulation.max 30
```

### 2. 内存管理

设置对话摘要阈值（消息数量）：
```bash
./temple.sh config set memory.threshold 20
```

设置保留消息数量：
```bash
./temple.sh config set memory.keep 10
```

### 3. 代理模型

查看可用模型：
```bash
./temple.sh config models
```

为特定代理设置模型：
```bash
# 使用免费模型
./temple.sh config set agent.genesis.model google/gemini-2.0-flash-exp:free

# 使用高级模型
./temple.sh config set agent.genesis.model anthropic/claude-3.5-sonnet
```

## 可用模型列表

### 📦 免费模型
- `google/gemini-2.0-flash-exp:free` - 最新 Gemini Flash（推荐）
- `google/gemini-flash-1.5:free` - Gemini Flash 1.5
- `meta-llama/llama-3.2-3b-instruct:free` - Llama 3.2 3B
- `qwen/qwen-2-7b-instruct:free` - Qwen 2 7B

### 💎 高级模型
- `anthropic/claude-3.5-sonnet` - Claude 3.5 Sonnet
- `openai/gpt-4-turbo` - GPT-4 Turbo
- `google/gemini-pro-1.5` - Gemini Pro 1.5

## 配置键参考

| 配置键 | 类型 | 说明 | 示例值 |
|--------|------|------|--------|
| `simulation.enabled` | boolean | 启用自动模拟 | true/false |
| `simulation.min` | integer | 最小模拟间隔（秒） | 5 |
| `simulation.max` | integer | 最大模拟间隔（秒） | 30 |
| `memory.threshold` | integer | 触发摘要的消息数 | 20 |
| `memory.keep` | integer | 摘要后保留的消息数 | 10 |
| `agent.<id>.model` | string | 代理使用的模型 | google/gemini-2.0-flash-exp:free |

## 完整示例

```bash
# 1. 查看当前配置
./temple.sh config show

# 2. 启用模拟并设置间隔
./temple.sh config set simulation.enabled true
./temple.sh config set simulation.min 10
./temple.sh config set simulation.max 40

# 3. 调整内存管理
./temple.sh config set memory.threshold 15
./temple.sh config set memory.keep 8

# 4. 为不同代理设置不同模型
./temple.sh config set agent.genesis.model google/gemini-2.0-flash-exp:free
./temple.sh config set agent.coder.model anthropic/claude-3.5-sonnet

# 5. 验证配置
./temple.sh config show
```

## 项目特定配置

使用 `-p` 参数为特定项目配置：

```bash
# 为 my_world 项目配置
./temple.sh -p my_world config set simulation.enabled true
./temple.sh -p my_world config show
```
