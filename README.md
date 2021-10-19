# 挖财数据导入 Beancount

本脚本实现了解析挖财导出文件并转换为 Beancount 账本的功能。基本保留了挖财导出文件的全部内容细节。

功能:
- 一次性处理收入、支出、转账、借贷往来全部记录
- 时间信息以 Transaction 的 metadata 形式保留（例如 `time: "11:22:33"`）
- 成员消费以 Posting 的 metadata 形式保留（例如 `member: "阿猫"`）
- 账本信息以 tags 的形式保留
- 项目信息以 tags 的形式保留
- 报销记录以 links 的形式保留（统一为 `Reimburse`），记录为与指定账户（`account_reimburse` 参数）的转账，同时保留原始消费类别（添加总额为 0  的 Posting）以便查询
- 借贷往来统一记录到两个账户中（`account_debt` 与 `account_credit` 参数），以 `payee` 区分外部账户或人员
- 借贷往来中增加利息支出 Posting，记录到统一账户（`expenses_interest` 参数）中
- 为无备注的借贷与转账自动添加备注

TODO:
- [ ] 转换余额调整记录为 pad & balance 语句（暂无可用的数据来源）
- [ ] 借款项支持非 CNY 的货币（挖财中无相关记录的货币信息）
- [ ] 多人账本（目前没有参考文件格式）
- [ ] 增加利息收入记录到统一账户的配置参数
- [ ] 替换 `xlwings`

已知的问题与说明：
- 挖财中，跨在不同币种账户间转账（如：人民币还信用卡美元欠款）的记录不准确，目前统一以转出账户的货币为准。需要手动确认 Beancount 记录（已经打 `!` Flag），比如一张双币信用卡的主货币是正的，而其他货币是负的。
- 挖财中的`项目`一般为中文，而 Beancount 不支持中文 tag，目前已转换为拼音（如：`公司` -> `gong1-si1`），如有修改需要请使用批量替换工具处理。
- 挖财导出文件中不包含余额调整信息，导入后各账户的余额不准确需要手动对账一次；历史余额准确度取决于在挖财中是否事无巨细全部记录。

## 使用方式

### 安装
因为使用了 `xlwings` 包，所以需要 Windows 系统或 macOS 系统，并且安装了 Excel。
```python
pip3 install beancount-wacai
```
### 配置
请参考 `example.bean` 中的内容，预先开一些常用账户。然后参考 `example.import` 配置 `.import` 文件：
```python
from beancount_wacai import WacaiImporter

CONFIG = [
    WacaiImporter(
        {
            '招商卡': 'Assets:CN:CMB',
            '招商卡信用卡': 'Liabilities:CN:CMB',
             # ...
        },
        {
            '工资薪水': 'Income:Salary',
            '其他': 'Income:Other',
             # ...
        }, {
            '衣服鞋帽': 'Expenses:Shopping:Clothing',
            '软件服务': 'Expenses:Shopping:Software',
             # ...
        },
        account_debt='Liabilities:Payable',#债权
        account_credit='Assets:Receivables',#债务
        account_reimburse='Assets:Reimburse',#报销
        account_ufo='Equity:Opening-Balances',
    )
]
### 导出挖财
```
在挖财网页版中，导出各个账本（导出为收费功能，最便宜的档位是 **50 元季度会员**）。解压后获得 `.xlsx`文件。验证脚本是否能处理这些文件：
```python
# 假设文件都位于相对目录 wacai_example_file 中
bean-identify example.import wacai_example_file
```
将输出：
> **** wacai_example_file\wacai_日常账本_202101011200001_123.xlsx  
> Importer:    wacai  
> Account:     None  

### 导入
如无问题，可继续执行 `bean-extract`

```python
bean-extract example.import wacai_example_file\wacai_日常账本_202101011200001_123.xlsx > result.bean

#或
bean-extract example.import wacai_example_file > result.bean
```
执行过程中，会输出未识别的账户，例如：
> Unknown accounts:  
> Assets:Unknown:北京银行卡  
> Assets:Unknown:招商信用卡-美元  
> Assets:Unknown:招商信用卡  
> Assets:Unknown:交行信用卡  
> Income:Unknown:利息  
> Expenses:Unknown:手机电话  
> Expenses:Unknown:数码产品  
> Expenses:Unknown:购物其他  
> Expenses:Unknown:对帐  
> Expenses:Unknown:代付款  
> Expenses:Unknown:求医买药  
> Expenses:Unknown:花鸟宠物  

可据此手动在主账本中，使用 `open` 补齐这些账户，如有修改需要请使用批量替换工具处理。输出结果可参考 `result.bean`。

最后在主账本中引入：

```beancount
include "result.bean"
```

**注意** 在 Windows CMD 中，最终输出的文件可能是 GBK 编码，这将需要你手动转换文件编码。