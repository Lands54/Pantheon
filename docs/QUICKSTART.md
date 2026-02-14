# Gods Platform 快速启动指南

## 环境激活

```bash
# 激活 conda 环境
conda activate gods_env

# 验证环境
which python
# 应该输出：/Users/qiuboyu/anaconda3/envs/gods_env/bin/python
```

## 启动神殿服务 (Server)

```bash
# 启动 FastAPI 后端
python server.py
```

## 使用 Sacred Command (CLI)

`temple.py` 是管理众神平台的主要入口。

### 1. 初始化设置
```bash
# 设置 API Key
python temple.py init YOUR_OPENROUTER_API_KEY
```

### 2. 世界（项目）管理
```bash
# 列出所有世界
python temple.py project list

# 创建新世界
python temple.py project create new_world --name "新纪元"

# 切换当前激活的世界
python temple.py project switch new_world
```

### 3. 众神（代理）管理
```bash
# 查看当前世界的众神状态
python temple.py list

# 激活/休眠代理
python temple.py activate coder
python temple.py deactivate genesis

# 查看/编辑代理指令
python temple.py agent view genesis
```

### 4. 发布神谕 & 辩论
```bash
# 发布广播指令（触发辩论）
python temple.py broadcast "讨论一下 AI 伦理"

# 运行自动化集成测试
python temple.py test --cleanup
```

## 运行离线脚本

如果你想绕过服务器直接运行：

```bash
# 在指定世界运行单次任务
python index.py "你的任务..." --project default

# 运行代理能力测试脚本
python test_divine_manifestation.py --agent coder --project default
```

## 前端开发

```bash
cd frontend
npm run dev
```
