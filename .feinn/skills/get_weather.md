---
id: get_weather
summary: 根据城市名称获取实时天气信息
activators: ["/weather", "天气"]
tools: ["WebFetch"]
param-guide: "[城市名]"
param-names: ["city"]
---

根据城市名称，获取对应城市的实时天气信息。

## 执行步骤

1. 提取城市名: $CITY
2. 调用天气 API 获取数据
3. 返回结构化天气信息

用户输入: $PARAMS
