### 全部(n=72)

| 难度 | n | payer_name | payee_name | amount | date | serial_no | 整单全对 | 幻觉 |
|---|---|---|---|---|---|---|---|---|
| blur | 12 | 83% | 92% | 50% | 92% | 100% | 25% | 0 |
| clean | 12 | 100% | 100% | 100% | 100% | 100% | 100% | 0 |
| lowres | 12 | 92% | 100% | 100% | 100% | 100% | 92% | 0 |
| occlusion | 12 | 67% | 58% | 50% | 67% | 75% | 8% | 0 |
| perspective | 12 | 100% | 100% | 100% | 100% | 100% | 100% | 0 |
| rotate | 12 | 100% | 100% | 92% | 100% | 100% | 92% | 0 |
| 合计 | 72 | 90% | 92% | 82% | 93% | 96% | 69% | 0 |

### SUBSET10(与方案 B 对比)(n=10)

| 难度 | n | payer_name | payee_name | amount | date | serial_no | 整单全对 | 幻觉 |
|---|---|---|---|---|---|---|---|---|
| blur | 1 | 100% | 100% | 0% | 100% | 100% | 0% | 0 |
| lowres | 1 | 100% | 100% | 100% | 100% | 100% | 100% | 0 |
| occlusion | 3 | 67% | 67% | 67% | 33% | 67% | 0% | 0 |
| clean | 2 | 100% | 100% | 100% | 100% | 100% | 100% | 0 |
| perspective | 1 | 100% | 100% | 100% | 100% | 100% | 100% | 0 |
| rotate | 2 | 100% | 100% | 50% | 100% | 100% | 50% | 0 |
| 合计 | 10 | 90% | 90% | 70% | 80% | 90% | 50% | 0 |

### 错误明细

| id | 字段 | 预测 | 标准答案 | 校验错误 |
|---|---|---|---|---|
| invoice_blur_00 | amount | None | 3313805.85 | 无法解析的金额: '¥3.313,805.85' |
| invoice_blur_01 | payee_name | 测川文化传媒(杭州)有限公司 | 澜川文化传媒(杭州)有限公司 |  |
| invoice_blur_01 | amount | None | 7003.92 | 无法解析的金额: '¥7.003.92' |
| invoice_blur_02 | amount | None | 94131.35 | 无法解析的金额: '¥94.131.35' |
| invoice_blur_03 | amount | None | 2685241.10 | 无法解析的金额: '¥2.685,241.10' |
| invoice_occlusion_00 | amount | None | 6.09 |  |
| invoice_occlusion_00 | date | None | 2026-05-02 |  |
| invoice_occlusion_01 | amount | None | 92540.01 |  |
| invoice_occlusion_02 | payee_name | 远拓文化传媒拓武汉)有限公司 | 远拓文化传媒(武汉)有限公司 |  |
| invoice_occlusion_02 | amount | None | 225066.31 |  |
| invoice_occlusion_03 | amount | None | 6470.63 |  |
| invoice_occlusion_03 | date | None | 2025-12-04 |  |
| receipt_blur_01 | payer_name | 嘉洲建材有限公司 | 嘉澍建材有限公司 |  |
| receipt_blur_02 | payer_name | 测川文化传媒有限公司 | 澜川文化传媒有限公司 |  |
| receipt_lowres_01 | payer_name | 嘉湖信息技术(成都)有限公司 | 嘉澍信息技术(成都)有限公司 |  |
| receipt_occlusion_00 | payer_name | None | 嘉澍机械设备(杭州)有限公司 |  |
| receipt_occlusion_00 | payee_name | None | 远拓科技(成都)有限公司 |  |
| receipt_occlusion_01 | payer_name | None | 澜川机械设备(上海)有限公司 |  |
| receipt_occlusion_01 | payee_name | None | 澜川餐饮管理(苏州)有限公司 |  |
| receipt_occlusion_01 | serial_no | None | HX20240707971782 |  |
| receipt_occlusion_02 | payer_name | 远拓文化传媒有限公司 | 恒岳医疗器械(成都)有限公司 |  |
| receipt_occlusion_02 | payee_name | None | 远拓文化传媒有限公司 |  |
| receipt_occlusion_02 | serial_no | None | HX20250607745147 |  |
| receipt_occlusion_03 | payer_name | None | 星河餐饮管理(北京)有限公司 |  |
| receipt_occlusion_03 | payee_name | None | 星河餐饮管理有限公司 |  |
| receipt_occlusion_03 | amount | None | 1.07 | OCR 金额缺少角分,可能被拆断: 'RMB107' |
| receipt_occlusion_03 | serial_no | None | HX20251111368059 |  |
| statement_blur_00 | date | None | 2024-03-23 |  |
| statement_blur_01 | amount | None | 1633406.45 | 无法解析的金额: 'RMB1.633.406.45' |
| statement_blur_02 | amount | None | 15185.38 | 无法解析的金额: '¥15.185.38' |
| statement_occlusion_00 | date | None | 2024-04-14 |  |
| statement_occlusion_01 | date | None | 2025-09-21 |  |
| statement_occlusion_03 | amount | None | 2.04 | 无法解析的金额: '294银行' |
| statement_rotate_00 | amount | None | 5.78 |  |