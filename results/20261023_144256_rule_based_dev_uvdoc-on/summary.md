### 全部(n=18)

| 难度 | n | payer_name | payee_name | amount | date | serial_no | 整单全对 | 幻觉 |
|---|---|---|---|---|---|---|---|---|
| blur | 3 | 33% | 67% | 67% | 100% | 100% | 33% | 0 |
| clean | 3 | 67% | 100% | 100% | 100% | 100% | 67% | 0 |
| lowres | 3 | 67% | 100% | 100% | 100% | 100% | 67% | 0 |
| occlusion | 3 | 33% | 67% | 33% | 67% | 67% | 0% | 0 |
| perspective | 3 | 67% | 100% | 100% | 100% | 100% | 67% | 0 |
| rotate | 3 | 67% | 100% | 100% | 100% | 100% | 67% | 0 |
| 合计 | 18 | 56% | 89% | 83% | 94% | 94% | 50% | 0 |

### 错误明细

| id | 字段 | 预测 | 标准答案 | 校验错误 |
|---|---|---|---|---|
| invoice_blur_00 | payer_name | 漏川医疗器械(杭州)有限公司 | 澜川医疗器械(杭州)有限公司 |  |
| invoice_blur_00 | payee_name | 北晨科技有限公司 | 北辰科技有限公司 |  |
| invoice_blur_00 | amount | None | 2297511.20 | 无法解析的金额: 'RM8 2,297,511.20' |
| invoice_occlusion_00 | amount | None | 118510.79 |  |
| receipt_occlusion_00 | payer_name | 云帆农业发展有限公司 | 青禾建材有限公司 |  |
| receipt_occlusion_00 | payee_name | None | 云帆农业发展有限公司 |  |
| receipt_occlusion_00 | serial_no | None | HX20250226360047 |  |
| statement_blur_00 | payer_name | None | 云帆医疗器械有限公司 |  |
| statement_clean_00 | payer_name | None | 北辰餐饮管理(杭州)有限公司 |  |
| statement_lowres_00 | payer_name | None | 云帆建材(上海)有限公司 |  |
| statement_occlusion_00 | payer_name | None | 沐阳科技有限公司 |  |
| statement_occlusion_00 | amount | None | 220957.09 | OCR 金额缺少角分,可能被拆断: 'RMB220,957' |
| statement_occlusion_00 | date | None | 2025-08-16 |  |
| statement_perspective_00 | payer_name | None | 锦程文化传媒有限公司 |  |
| statement_rotate_00 | payer_name | None | 云帆物流有限公司 |  |