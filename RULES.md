# NPO Daily Intelligence Briefing — Standard Operating Principles (RULES.md)

本規範為 **非營利組織每日深度晨報（NPO Daily Intelligence Review）** 之核心運作準則與自動化品質保證規範。本專案由 AI 研究助手與顧問維護，每日定期檢索、核驗、分析並自動發布最新動態。

---

## 1. 每日精選原則（嚴格上限 3 篇）
* **篇數上限**：每日核心焦點嚴格收斂至 **3 篇** 主文獻（Main Articles），絕不超額收錄。
* **來源分佈（黃金三角）**：
  1. **國際／歐美（FOCUS 01）**：聚焦 SSIR、NPQ、Alliance Magazine、The Chronicle of Philanthropy 等國際智庫與前沿管理策略。
  2. **台灣在地（FOCUS 02）**：聚焦 Right Plus 多多益善、報導者、社企流、各大型倡議與社福聯盟之在地深耕實踐。
  3. **日本／東亞（FOCUS 03）**：聚焦 日本内閣府、JANPIA 休眠預金、JFRA 日本ファンドレイジング協会、公益法人協會之制度創新。
* **延伸學術文獻配置**：
  * 每篇主文獻配置 **1 篇** 深度呼應的同行評審學術文獻（Extended References）。
  * 全日總計嚴格為 **3 篇主文獻 ＋ 3 篇延伸文獻**（共 6 筆）。

---

## 2. 防幻覺雙引擎與跨日絕對去重（Zero-Hallucination Gatekeeper）
* **7 天時間窗口**：所有收錄之主文獻發布時間（Timestamp）必須在報告產出當日往前推算 7 天之內。
* **跨日絕對不重複（主文獻 ＋ 延伸文獻）**：
  * 凡是網址（URL）、學術 DOI 或原文標題曾出現在歷史紀錄庫（`reported_history.json`）過去任一天的主題報告中，**一律直接排除，絕不重複介紹**。
* **100% 實名查證**：
  * 所有學術文獻必須具備真實 DOI（`10.xxxx/...`）並經由 Crossref 實名驗證，或在單一檢索步驟中證實真實共現，嚴禁記憶拼接或捏造學者論文。

---

## 3. 本地硬性程式碼閘門（validate_report_grounding.py）
在報告發布至 GitHub Pages 或向使用者回報之前，系統必須於本地執行檢驗腳本：
```bash
python validate_report_grounding.py <path_to_html_artifact>
```
* **腳本自動驗證**：
  1. `assert len(main_articles) <= 3`（若超過 3 篇直接 Exit Code 1 報錯中斷）
  2. `assert no_cross_day_duplicates`（若出現任何重複文獻直接 Exit Code 1 報錯中斷）
  3. `assert all_references_grounded`（若有文獻未經實名驗證直接 Exit Code 1 報錯中斷）
* **只有在腳本回傳 `Exit Code 0`（🎉 100% 通過）後，才允許推送到 GitHub Pages。**

---

## 4. 閱讀體驗與知識庫同步
* **版型標準**：採用 `daily_template_v2.html`（雜誌級溫潤紙感設計、頂部 3 個重點快覽、台灣關聯度徽章、30 秒 TL;DR 摘要框、行動處方箋）。
* **知識庫一鍵同步**：整合 Zotero（學術標籤）、Notion（雙向連結）、Obsidian（`[[tag]]` 網絡），並內建儲存前新標籤確認彈窗。

---
*最後修訂日期：2026 年 11 月 02 日*
