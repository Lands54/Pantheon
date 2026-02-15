# 与 Agent 对话指南

## 方式 1: 广播（Broadcast）- 多 Agent 讨论

向所有活跃的 agent 广播消息，触发公开讨论：

```bash
./temple.sh broadcast "你好！请介绍一下自己"
```

**特点**：
- ✅ 所有活跃 agent 都会参与
- ✅ 实时流式输出对话
- ✅ 适合需要多个视角的讨论
- ✅ 可以看到 agent 之间的互动

**示例**：
```bash
# 请求帮助
./temple.sh broadcast "我需要帮助设计一个数据库schema"

# 头脑风暴
./temple.sh broadcast "让我们讨论一下如何优化系统性能"

# 代码审查
./temple.sh broadcast "请审查这段代码: def hello(): print('hi')"
```

## 方式 2: 私密消息（Confess）- 单 Agent 对话

向特定 agent 发送私密消息：

```bash
./temple.sh confess genesis "你好，我有个问题想请教"
```

**特点**：
- ✅ 一对一私密对话
- ✅ 消息进入 agent 的收件箱
- ✅ Agent 在下次"脉冲"时处理
- ✅ 适合需要特定 agent 专长的任务

**示例**：
```bash
# 向 genesis 咨询
./temple.sh confess genesis "请帮我分析一下这个错误日志"

# 向 coder 请求代码
./temple.sh confess coder "请写一个Python函数来排序列表"
```

## 方式 3: Web UI（推荐用于长对话）

启动服务器后，在浏览器中访问：

```bash
# 1. 启动服务器
./server.sh

# 2. 打开浏览器
# 访问 http://localhost:8000
```

**特点**：
- ✅ 图形化界面
- ✅ 实时对话流
- ✅ 可视化 agent 状态
- ✅ 更好的交互体验

## 激活多个 Agent

要让多个 agent 参与讨论，需要先激活它们：

```bash
# 查看可用 agent
./temple.sh list

# 激活 agent
./temple.sh activate coder
./temple.sh activate analyst

# 现在广播会有多个 agent 响应
./temple.sh broadcast "大家好！"

# 取消激活
./temple.sh deactivate coder
```

## 创建自定义 Agent

```bash
# 1. 创建新 agent
./temple.sh project switch my_world  # 切换到你的项目
mkdir -p projects/my_world/agents/my_agent
mkdir -p projects/my_world/mnemosyne/agent_profiles

# 2. 编写 Agent Profile
cat > projects/my_world/mnemosyne/agent_profiles/my_agent.md << 'EOF'
# My Custom Agent

You are a helpful assistant specialized in data analysis.
Your goal is to help users understand their data through clear visualizations and insights.

## Skills
- Data analysis
- Statistical modeling
- Visualization recommendations

## Personality
- Analytical and precise
- Patient and educational
- Enthusiastic about data
EOF

# 3. 激活新 agent
./temple.sh activate my_agent

# 4. 与新 agent 对话
./temple.sh confess my_agent "请帮我分析这组数据: [1,2,3,4,5]"
```

## 常见问题

### Q: Agent 没有响应？
A: 检查以下几点：
1. API Key 是否设置：`./temple.sh list`
2. Agent 是否激活：`./temple.sh list`
3. 服务器是否运行：`./server.sh`

### Q: 如何查看 Agent 的历史对话？
A: 查看 Mnemosyne chronicle 文件：
```bash
cat projects/test_cli/mnemosyne/chronicles/genesis.md
```

### Q: 如何更改 Agent 使用的模型？
A: 使用 config 命令：
```bash
./temple.sh config set agent.genesis.model anthropic/claude-3.5-sonnet
```

## 完整工作流示例

```bash
# 1. 设置 API Key
./temple.sh init YOUR_API_KEY

# 2. 启动服务器
./server.sh

# 3. 在另一个终端，激活多个 agent
./temple.sh activate genesis
./temple.sh activate coder

# 4. 开始对话
./temple.sh broadcast "大家好！我需要帮助设计一个Web应用"

# 5. 查看状态
./temple.sh list

# 6. 私密咨询特定 agent
./temple.sh confess coder "请写一个登录页面的HTML"
```
