# Gods Platform 快速启动指南

## 环境激活

```bash
# 激活 conda 环境
conda activate gods_env

# 验证环境
which python
# 应该输出：/Users/qiuboyu/anaconda3/envs/gods_env/bin/python
```

## 运行辩论

```bash
# 方式 1：使用默认话题（电车难题）
python platform/workflow.py

# 方式 2：运行自定义辩论
python -c "
from platform.workflow import create_gods_workflow

workflow = create_gods_workflow()
result = workflow.invoke({
    'messages': [],
    'current_speaker': '',
    'debate_round': 0,
    'inbox': {},
    'context': '你的话题...'
})
"
```

## 环境管理

```bash
# 安装新依赖
conda activate gods_env
pip install <package_name>

# 导出环境
conda env export > environment.yml

# 删除环境（如需重建）
conda deactivate
conda env remove -n gods_env
```

## 模型管理

```bash
# 查看已下载模型
ollama list

# 下载其他量化版本
ollama pull qwen2.5-coder:7b-instruct-q8_0  # 8-bit (更高质量)
ollama pull qwen2.5-coder:14b-instruct-q4_0  # 14B (更强能力)

# 删除不用的模型
ollama rm qwen2.5-coder:7b-instruct-q4_0
```
