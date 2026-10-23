### 全部(n=18)

| 难度 | n | payer_name | payee_name | amount | date | serial_no | 整单全对 | 静默错 | 幻觉 |
|---|---|---|---|---|---|---|---|---|---|
| blur | 3 | 67% | 67% | 67% | 100% | 100% | 67% | 2 | 0 |
| clean | 3 | 100% | 100% | 100% | 100% | 100% | 100% | 0 | 0 |
| lowres | 3 | 100% | 100% | 100% | 100% | 100% | 100% | 0 | 0 |
| occlusion | 3 | 67% | 67% | 33% | 67% | 67% | 0% | 0 | 0 |
| perspective | 3 | 100% | 100% | 100% | 100% | 100% | 100% | 0 | 0 |
| rotate | 3 | 100% | 100% | 100% | 100% | 100% | 100% | 0 | 0 |
| 合计 | 18 | 89% | 89% | 83% | 94% | 94% | 78% | 2 | 0 |

### 错误明细

| id | 字段 | 预测 | 标准答案 | 校验错误 |
|---|---|---|---|---|
| invoice_blur_00 | payer_name | 漏川医疗器械(杭州)有限公司 | 澜川医疗器械(杭州)有限公司 |  |
| invoice_blur_00 | payee_name | 北晨科技有限公司 | 北辰科技有限公司 |  |
| invoice_blur_00 | amount | None | 2297511.20 | 无法解析的金额: 'RM8 2,297,511.20' |
| invoice_occlusion_00 | amount | None | 118510.79 |  |
| receipt_occlusion_00 | payer_name | None | 青禾建材有限公司 |  |
| receipt_occlusion_00 | payee_name | None | 云帆农业发展有限公司 |  |
| receipt_occlusion_00 | serial_no | None | HX20250226360047 |  |
| statement_occlusion_00 | amount | None | 220957.09 | OCR 金额缺少角分,可能被拆断: 'RMB220,957' |
| statement_occlusion_00 | date | None | 2025-08-16 |  |