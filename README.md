# 软件工程实验一：个人编程技能和 Git 操作

本仓库实现 HJ212-2017 单帧解析器，并提交实验报告与自动化回归用例。

- 公开仓库：https://github.com/qianrui1006/202380010733-software-engineering-lab1
- 实验报告：[`docs/202380010733-钱锐-软件工程实验一.docx`](docs/202380010733-钱锐-软件工程实验一.docx)
- 实验日期：2026年10月5日

## 目录

- `hj212_parser.py`：`HJ212Parser` 类、报文构造、CRC、结构化解析和监测因子提取。
- `test_hj212_parser.py`：协议帧、官方 CRC 样例、字段和边界回归用例。
- `docs/`：按课程模板填写的实验报告。

## 功能

- `is_valid_message(message)`：校验 `## + 4位长度 + 数据段 + 4位CRC + CRLF` 的完整帧。
- `validate_crc(message)`：按 HJ 212-2017 附录 A 对 ASCII 数据段计算 CRC16。
- `parse_data_segment(message)`：将外层字段解析为字典，同时保留 `CP=&&...&&` 中的内部字段。
- `extract_monitoring_data(message)`：提取 CP 数据区中的监测因子编码、类别和值。

CRC 使用初值 `0xFFFF`，每字节执行 `(crc >> 8) ^ byte`，随后右移 8 轮并使用多项式 `0xA001`。以标准附录 A 样例帧（CRC `1C80`）作为固定校验向量。

## 运行

需要 Python 3.10 或更高版本，不依赖第三方包。

```bash
python -m unittest -v
```

验证环境 Python 3.14.3；11 项自动化回归用例全部通过。

单帧示例：

```python
from hj212_parser import HJ212Parser

segment = (
    "QN=20160801085857223;ST=32;CN=2061;PW=123456;"
    "MN=010000A8900016F000169DC0;Flag=5;"
    "CP=&&DataTime=20160801080000;w01001-Avg=7.5&&"
)
message = HJ212Parser.build_message(segment)
assert HJ212Parser.is_valid_message(message)
print(HJ212Parser.parse_data_segment(message))
print(HJ212Parser.extract_monitoring_data(message))
```

此实现处理单条完整 ASCII 报文，不负责 TCP 粘包/拆包、加密报文或 HJ 212 分包合并。
