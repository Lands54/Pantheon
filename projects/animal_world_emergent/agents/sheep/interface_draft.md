# 羊群模块接口草案

## 职责
- 管理羊群行为、摄食、繁衍和种群稳定
- 响应捕食压力
- 与草地和地面交互

## 输入接口

### 从 ground 接收
```json
{
  "timestamp": "模拟时间",
  "grass_grid": [
    {
      "position": {"x": float, "y": float},
      "biomass": float,  // 草的生物量
      "nutrient_level": float,  // 土壤养分水平
      "regrowth_rate": float  // 恢复速率
    }
  ],
  "terrain": [
    {
      "position": {"x": float, "y": float},
      "elevation": float,
      "slope": float,
      "walkability": float  // 0-1，越容易行走
    }
  ]
}
```

### 从 tiger 接收
```json
{
  "timestamp": "模拟时间",
  "tiger_positions": [
    {
      "position": {"x": float, "y": float},
      "hunting_radius": float,  // 捕食影响半径
      "danger_level": float  // 危险等级 0-1
    }
  ]
}
```

## 输出接口

### 向 ground 提供
```json
{
  "timestamp": "模拟时间",
  "sheep_positions": [
    {
      "position": {"x": float, "y": float},
      "size": float,  // 羊的大小
      "age": int,  // 年龄
      "health": float  // 健康状态 0-1
    }
  ],
  "grazing_impact": [
    {
      "position": {"x": float, "y": float},
      "biomass_consumed": float  // 该位置被消耗的草量
    }
  ],
  "nutrient_return": [
    {
      "position": {"x": float, "y": float},
      "nutrient_amount": float  // 粪便归还的养分量
    }
  ]
}
```

### 向 tiger 提供（可选，如果虎群需要实时羊群位置）
```json
{
  "timestamp": "模拟时间",
  "sheep_density_grid": [
    {
      "position": {"x": float, "y": float},
      "density": float  // 该位置的羊群密度
    }
  ]
}
```

## 内部状态
- 羊群列表（每只羊的状态）
- 种群统计数据（总数、年龄分布、性别比例等）
- 行为模式（游牧、聚集、躲避等）

## 更新频率
建议与主模拟循环同步，每 tick 执行一次更新

## 待协商事项
1. 坐标系统（是否需要统一？）
2. 数据精度要求
3. 错误处理和边界情况
4. 性能考虑（网格大小、羊群数量限制等）