# 软件系统测试详细设计说明书

# 测试范围

## 标识

 本文档适用的软件
    a)
    b)

## 系统概述

 依据KYZW 分系统的功能需求和设计文档，测试范围涵盖以下模块：
  a）任务总线模块：负责调度和管理各类测试任务，包括 BCMI 评估数据接口适配建模等核心功能。
  b）结果复核模块：负责对测试结果进行结构化表格展示和二次校验，确保复杂表格样式的正确性和一致性。
 KYZW 分系统的研制过程与KYZW 分系统的测试过程紧密关联，测试活动将覆盖从单元测试、集成测试到系统测试的全生命周期，确保软件质量和功能实现满足预期要求。
  项目需方：
  项目承建方：
  项目监理方：

## 文档概述

    本文档详细描述了KYZW 分系统的测试设计方案，包括测试范围、测试方法、测试环境、测试用例设计和测试风险评估等内容。通过系统化的测试设计，确保KYZW 分系统在功能、性能、安全性等方面达到预期标准，为项目的成功交付提供有力保障。

# 引用文档

   KYZW 分系统    功能需求文档
   KYZW 分系统    设计文档
   KYZW 分系统    测试计划

# 测试准备

## 硬件准备

  KYZW 分系统,见下表1：

   ```json:basic_table
   {keys:
   [
    {name:"equipment_type",description:"设备类型"},
    {name:"model",description:"型号"},
    {name:"quantity",description:"数量"},
    {name:"remarks",description:"备注"}
    ],
    values:[
    {
      "equipment_type": "设备类型",
        "model": "型号",
        "quantity": "数量",
        "remarks": "备注"
    }
    ]
   }
   ```

## 软件准备

 KYZW 分系统,见下表2：

```json:basic_table
{keys:
   [
    {name:"software_name",description:"软件名称"},
    {name:"version",description:"版本"},
    {name:"quantity",description:"数量"},
    {name:"remarks",description:"备注"}
    ],
    values:[
    {
      "software_name": "软件名称",
        "version": "版本",
        "quantity": "数量",
        "remarks": "备注"
    }
    ]
   }
```

## 其他测试前准备

 表3 KYZW 分系统所需其他项

```json:basic_table
{keys:
   [
    {name:"item_name",description:"项名称"},
    {name:"description",description:"描述"}
    ],
    values:[
    {
      "item_name": "项名称",
        "description": "描述"
    }
    ]
   }
```

# 测试说明

## 文档审查

 本次测试设计阶段将对以下文档进行审查：
  功能需求文档：确保测试设计覆盖所有功能需求，并验证需求的可测试性。
  设计文档：评估设计方案的合理性和可实现性，确保测试设计与系统架构和模块划分相匹配。
  测试计划：审查测试计划的完整性和可行性，确保测试资源、时间安排和风险管理措施得到充分考虑。

## 代码审查

### 测试内容

### 测试方法

## 静态分析

 见表4 KYZW 分系统静态分析工具和规则

```json:static_analysis
{keys:[{
    name:"test_name",description:"测试项名称",isMergeKey:true
},{
    name:"test_content",description:"测试内容描述"
},{
    name:"technical_requirements",description:"技术要求"
},{
    name:"results",description:"分析结果描述"
},{
    name:"remarks",description:"备注"
},{
    name:"merge_level",description:"合并级别，默认为1，表示与下一行合并，直到遇到 merge_level 不为1 的行"
}],
}],values:[
    {
        "test_name": "测试项名称",
        "test_content": "测试内容描述",
        "technical_requirements": "技术要求",
        "results": "分析结果描述",
        "remarks": "备注",
        "merge_level": 1
    },
    {
        "test_name": "测试项名称",
        "test_content": "测试内容描述",
        "technical_requirements": "技术要求",
        "results": "分析结果描述",
        "remarks": "备注",
        "merge_level": 1
    },
    {
        "test_name": "测试项名称",
        "test_content": "测试内容描述",
        "technical_requirements": "技术要求",
        "results": "分析结果描述",
        "remarks": "备注",
        "merge_level": 2
    }
]
}
```

## 功能测试

 KYZW 分系统包含29个功能模块，共设计290个功能测试用例

```json:basic_table
{keys:
   [
    {name:"name",description:"测试项名称"},
    {name:"id",description:"测试项标识"},
    {name:"num",description:"测试用例数量"},
    {name:"remarks",description:"备注"}
    ],
    values:[
    {
      "name": "模块名称",
        "id": "测试项标识",
        "num": "测试用例数量",
        "remarks": "备注"
    }
    ]
   }
```

  表5 KYZW 分系统功能测试用例分布表

  ```json:basic_table
{keys:
   [
    {name:"use_case_id",description:"测试用例标识"},
    {name:"use_case_name",description:"测试用例名称"},
    {name:"use_case_description",description:"测试描述"}],
    values:[
    {
      "use_case_id": "测试用例标识",
        "use_case_name": "测试用例名称",
        "use_case_description": "测试描述"
    }
    ]
    }
```

### 功能项1

功能项1测试用例见表6。
   <text-center>表6 功能项1测试用例表</text-center>

```json:test_case
{
  "use_case_name": "BCMI 评估数据接口适配建模",
  "use_case_id": "GN-KYZW-XXJR-PGSJZYJR-JKS PJM",
  "test_track": "软件需求规格书",
  "preconditions": "测试环境和测试数据已准备就绪,测试网络正常.系统所有后台服务均正常启动",
  "termination_conditions": "本测试用例的全部测试步骤被执行或因某种原因导致测试步骤无法执行（异常终止）",
  "result_expectation": "测试能够验证并确保正确完成 BCMI 协议转换，将原始数据接入并完成资源映射的工作",
  "designer": "胡皓宁",
  "design_date": "2025.02.17",
  "steps":[
    {
      "no": 1,
      "input_procedure": "启动嵌训网 BCMI 代理",
      "expected_result": "代理服务正常启动，控制台无报错信息打印",
      "expectation": "代理服务正常启动，控制台无报错信息打印",
      "note": "测试前请确保 BCMI 代理已正确安装并配置"
    },
    {
      "no": 2,
      "input_procedure": "登录 KYZW 系统",
      "expected_result": "认证通过，成功进入系统主界面",
        "expectation": "认证通过，成功进入系统主界面",
        "note": "使用有效的测试账号进行登录，确保网络连接正常"
    },
    {
      "no": 3,
      "input_procedure": "启动仿真引擎",
      "expected_result": "引擎状态指示灯变绿，显示为“运行中”",
        "expectation": "引擎状态指示灯变绿，显示为“运行中”",
        "note": "确保仿真引擎已正确安装并配置，测试前请检查相关服务状态"
    },
    {
      "no": 4,
      "input_procedure": "启动共享数据库服务",
      "expected_result": "数据库连接池初始化成功"
        "expectation": "数据库连接池初始化成功",
        "note": "确保数据库服务已正确安装并配置，测试前请检查数据库连接状态"
    },
    {
      "no": 5,
      "input_procedure": "启动数据采集服务",
      "expected_result": "界面显示数据流开始接收，包数量持续上升",
        "expectation": "界面显示数据流开始接收，包数量持续上升",
        "note": "确保数据采集服务已正确安装并配置，测试前请检查相关服务状态"
    },
    {
      "no": 6,
      "input_procedure": "运行测试想定",
      "expected_result": "想定按时间轴正常推进，实体模型加载完成",
        "expectation": "想定按时间轴正常推进，实体模型加载完成",
        "note": "确保测试想定已正确配置，测试前请检查相关服务状态"
    },
    {
      "no": 7,
      "input_procedure": "观察系统二\\三维显示",
      "expected_result": "态势画面更新流畅，各类实体图标位置无明显漂移和卡顿",
        "expectation": "态势画面更新流畅，各类实体图标位置无明显漂移和卡顿",
        "note": "测试过程中请密切观察系统二\\三维显示，记录任何异常现象"
    },
    {
      "no": 8,
      "input_procedure": "使用 SYZYGL 系统查看共享数据库记录的转换后的标准数据",
      "expected_result": "字段映射完全准确，中文字符无乱码，经纬度高程数据无丢失",
        "expectation": "字段映射完全准确，中文字符无乱码，经纬度高程数据无丢失",
        "note": "确保 SYZYGL 系统已正确安装并配置，测试前请检查相关服务状态"
    },
    {
      "no": 9,
      "input_procedure": "查看数据回放文件",
      "expected_result": "回放文件（.dat）成功生成，且可被离线回放工具正常读取",
        "expectation": "回放文件（.dat）成功生成，且可被离线回放工具正常读取",
        "note": "测试前请确保离线回放工具已正确安装并配置，测试过程中请密切关注回放文件的生成情况"
    }
  ]
}
```

# 需求的可追踪性

    见表7 KYZW 分系统需求与测试用例追踪矩阵

```json:traceability_matrix_table
 {
      "header_left": "说明需求",
        "header_right": "CSCI需求",
        keys:[
          {name:"use_case_name",description:"测试用例名称",type: "header_left"},
          {name:"use_case_num",description:"测试用例章节号",type:"header_left"}
          {name:"demand_name",description:"需求名称",type:"header_right"}
          {name:"demand_num",description:"章节号",type:"header_right"}
        ],
        values:[
          {
            "use_case_name": "测试用例名称1",
            "use_case_num": "测试用例章节号1",
            "demand_name": "需求名称1",
            "demand_num": "章节号1"
          },
          {
            "use_case_name": "测试用例名称2",
            "use_case_num": "测试用例章节号2",
            "demand_name": "需求名称2",
            "demand_num": "章节号2"
          }
        ]
    }
```
