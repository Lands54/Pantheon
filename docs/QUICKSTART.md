# Gods Platform 快速启动（当前版本）

## 1. 启动环境

```bash
conda activate gods_env
```

## 2. 初始化 API Key

```bash
./temple.sh init YOUR_OPENROUTER_API_KEY
```

## 3. 启动服务

```bash
./server.sh
```

服务默认地址：`http://localhost:8000`  
API 文档：`http://localhost:8000/docs`

## 4. 常用 CLI 命令

### 4.1 项目管理

```bash
./temple.sh project list
./temple.sh project create my_world
./temple.sh project switch my_world
./temple.sh project delete my_world
```

### 4.2 Agent 管理

```bash
./temple.sh list
./temple.sh activate genesis
./temple.sh deactivate genesis
./temple.sh agent view genesis
./temple.sh agent edit genesis
```

### 4.3 通信与观测

```bash
./temple.sh events submit --domain interaction --type interaction.message.sent --payload '{"to_id":"genesis","sender_id":"human.overseer","title":"任务指令","content":"请先处理收件箱","msg_type":"confession","trigger_pulse":true}'
./temple.sh events submit --domain interaction --type interaction.message.sent --payload '{"to_id":"genesis","sender_id":"human.overseer","title":"记录","content":"先记录，不要立即执行","msg_type":"confession","trigger_pulse":false}'
./temple.sh check genesis
./temple.sh inbox outbox --agent "human.overseer" --to genesis --limit 20
```

### 4.4 配置

```bash
./temple.sh config show
./temple.sh config models
./temple.sh config set agent.genesis.model stepfun/step-3.5-flash:free
./temple.sh config set all.models stepfun/step-3.5-flash:free
./temple.sh config set simulation.enabled true
./temple.sh config set simulation.min 10
./temple.sh config set simulation.max 40
```

## 5. 前端开发（可选）

```bash
cd frontend
npm install
npm run dev
```

## 6. 测试（建议）

```bash
pytest -q
```
