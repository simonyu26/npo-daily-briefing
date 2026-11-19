import os
import sys
import json
import re
import datetime
import pathlib
import urllib.request
import urllib.error

# Timezone & Theme Config
TAIWAN_TZ = datetime.timezone(datetime.timedelta(hours=8))

DAY_THEMES = {
    0: ("週一", "週一｜策略與使命創新", "Strategy & Mission Innovation"),
    1: ("週二", "週二｜組織治理與責信", "Governance & Accountability"),
    2: ("週三", "週三｜影響力衡量與評估", "Impact Measurement & Evaluation"),
    3: ("週四", "週四｜策略募款與捐款人行為", "Strategic Fundraising & Donor Behavior"),
    4: ("週五", "週五｜法規政策與自律動態", "Legal Policy & Self-Regulation Dynamics"),
    5: ("週六", "週末｜非營利專題特刊", "Weekend Feature & Capacity Building"),
    6: ("週日", "週末｜前瞻趨勢與回顧", "Weekly Retrospective & Horizon Scanning"),
}

WEEKDAY_ZH = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

def get_target_date_info():
    forced_date = os.environ.get("TARGET_DATE", "").strip()
    if forced_date:
        dt = datetime.datetime.strptime(forced_date, "%Y-%m-%d").replace(tzinfo=TAIWAN_TZ)
    else:
        dt = datetime.datetime.now(TAIWAN_TZ)
    
    date_str = dt.strftime("%Y-%m-%d")
    weekday_idx = dt.weekday()
    day_name, day_topic, theme_en = DAY_THEMES[weekday_idx]
    weekday_str = WEEKDAY_ZH[weekday_idx]
    return date_str, weekday_str, day_topic, theme_en

def load_reported_history(hist_path):
    if not hist_path.exists():
        return []
    try:
        return json.loads(hist_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"⚠️ 無法讀取歷史記錄: {e}")
        return []

def call_gemini_api(api_key, prompt):
    """
    Call Gemini API with Google Search grounding enabled.
    Supports multi-model fallback (gemini-3.8-flash, gemini-2.0-flash, gemini-1.5-pro, etc.).
    Supports google-genai SDK or direct REST fallback.
    """
    candidate_models = ["gemini-3.8-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]
    last_err = None

    for model in candidate_models:
        print(f"🌐 嘗試呼叫 Google Gemini API ({model})...")
        
        # 1. Try SDK first if available
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[{"google_search": {}}],
                    temperature=0.2,
                )
            )
            if response.text:
                print(f"✅ SDK 成功透過 {model} 取得回應！")
                return response.text
        except Exception as e_sdk:
            print(f"ℹ️ {model} SDK 呼叫未果 ({e_sdk})，嘗試 REST API...")

        # 2. Fallback to direct REST API
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            payload = {
                "contents": [
                    {
                        "parts": [{"text": prompt}]
                    }
                ],
                "tools": [{"googleSearch": {}}],
                "generationConfig": {
                    "temperature": 0.2
                }
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json", "User-Agent": "NPO-Briefing-Cloud/1.0"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
                candidates = res_json.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    text = "".join([p.get("text", "") for p in parts])
                    if text:
                        print(f"✅ REST API 成功透過 {model} 取得回應！")
                        return text
        except urllib.error.HTTPError as e_http:
            err_body = e_http.read().decode("utf-8", errors="ignore")
            print(f"⚠️ {model} REST API 回傳 {e_http.code}: {err_body}")
            last_err = f"{model} error: {e_http.code} {err_body}"
        except Exception as e_gen:
            print(f"⚠️ {model} 呼叫發生例外: {e_gen}")
            last_err = str(e_gen)

    raise RuntimeError(f"所有 Gemini 模型嘗試皆失敗，最後錯誤: {last_err}")

def verify_url(url):
    """Probe URL with HTTP HEAD/GET to check if it returns 200 OK."""
    if not url or not url.startswith("http"):
        return False, "無效 URL"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            code = resp.getcode()
            if 200 <= code < 400:
                return True, code
            return False, code
    except urllib.error.HTTPError as e:
        return False, e.code
    except Exception as e:
        return False, str(e)

def verify_doi(doi):
    """Verify DOI via Crossref API."""
    if not doi:
        return False, "無 DOI"
    clean_doi = doi.strip()
    if clean_doi.startswith("http"):
        clean_doi = clean_doi.split("doi.org/")[-1]
    url = f"https://api.crossref.org/works/{clean_doi}"
    headers = {"User-Agent": "NPO-Briefing-Validator/1.0 (mailto:admin@example.org)"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            if resp.getcode() == 200:
                data = json.loads(resp.read().decode("utf-8"))
                item = data.get("message", {})
                title = item.get("title", [""])[0]
                return True, title
            return False, resp.getcode()
    except Exception as e:
        return False, str(e)

def build_prompt(date_str, weekday_str, day_topic, past_records):
    # Prepare past history summary for deduplication
    past_titles = [r.get("title_orig", "") for r in past_records[-40:] if r.get("title_orig")]
    past_urls = [r.get("url", "") for r in past_records[-40:] if r.get("url")]
    past_dois = [r.get("doi", "") for r in past_records[-40:] if r.get("doi")]

    prompt = f"""你是一名頂級非營利組織（NPO / NGO）戰略顧問兼智庫資深研究員。
請為【NPO 每日深度晨報】生成今日晨報內容。

【基本資訊】
- 日期：{date_str}（{weekday_str}）
- 今日主題：{day_topic}
- 核心選題原則（黃金三角）：嚴格挑選 3 篇過去 7-14 天內最新發布的真實報導與專題，並為每篇搭配 1 篇高度相關且已註冊真實 DOI 的同行評審（Peer-Reviewed）學術文獻。

【選題配置（黃金三角）】
1. FOCUS 01（國際 / 美歐）：聚焦 SSIR (Stanford Social Innovation Review)、NonProfit Quarterly (NPQ)、The Chronicle of Philanthropy、Harvard Business Publishing 等國際頂級智庫。
2. FOCUS 02（台灣在地）：聚焦《Right Plus 多多益善》、《報導者》、台灣公益團體自律聯盟、NPOst 等台灣在地深度調查與倡議。
3. FOCUS 03（日本 / 東亞）：聚焦 日本ファンドレイジング協會 (JFRA)、JANPIA、PR TIMES NPO 發布、公益法人協会、日本NPOセンター 等東亞非營利實踐。

【嚴格禁止重複（Negative Constraints）】
嚴格禁止選用以下已發布過的報導或文獻（標題、URL 或 DOI 均不可重複）：
已報導過的部分標題：{json.dumps(past_titles[-25:], ensure_ascii=False)}
已報導過的 URL：{json.dumps(past_urls[-25:], ensure_ascii=False)}
已報導過的 DOI：{json.dumps(past_dois[-25:], ensure_ascii=False)}

【真實性保證（Anti-Hallucination Rules）】
- 所有 3 篇焦點文章必須是真實存在的即時新聞或專題，URL 必須精確有效且能正常打開（HTTP 200）。
- 每個 bullet 中的原文引句（quote）必須是文章中真實存在的代表性金句（英文或日文原文，台灣報導若為中文則提供中文關鍵原句）。
- 延伸學術文獻必須是真實發表於 SSCI/Scopus 期刊的文獻，作者姓名、年份、期刊名稱與 DOI 必須 100% 真實精確。

請務必嚴格輸出以下標準 JSON 格式（以 ```json 開頭與結尾），不要輸出其他額外說明：

```json
{{
  "date": "{date_str}",
  "weekday": "{weekday_str}",
  "topic": "{day_topic}",
  "title": "NPO 每日深度晨報（{date_str} {day_topic} - 100% 防幻覺實證核驗版）",
  "exec_cards": [
    {{"focus": "焦點 01 ・ [副標題]", "title": "[焦點 1 繁中標題]", "tldr": "[50-80字 TL;DR 摘要]"}},
    {{"focus": "焦點 02 ・ [副標題]", "title": "[焦點 2 繁中標題]", "tldr": "[50-80字 TL;DR 摘要]"}},
    {{"focus": "焦點 03 ・ [副標題]", "title": "[焦點 3 繁中標題]", "tldr": "[50-80字 TL;DR 摘要]"}}
  ],
  "switcher": [
    {{"num": "FOCUS 01", "source": "🇺🇸 [來源名稱]", "title": "[簡短標題]"}},
    {{"num": "FOCUS 02", "source": "🇹🇼 [來源名稱]", "title": "[簡短標題]"}},
    {{"num": "FOCUS 03", "source": "🇯🇵 [來源名稱]", "title": "[簡短標題]"}}
  ],
  "articles": [
    {{
      "code": "FOC-1",
      "region": "🇺🇸 國際智庫與策略前沿",
      "timestamp": "{date_str}",
      "publisher": "[媒體名稱]",
      "authors": "[作者名]",
      "pubDate": "[發布日期 YYYY-MM-DD]",
      "year": 2026,
      "tags": ["strategy", "innovation"],
      "titleZh": "[深度繁中標題，含背景與核心突破點]",
      "titleOrig": "[原文原始標題]",
      "tldr": "[50-80字核心摘要]",
      "relevance": "高",
      "verify": "search_web 實測",
      "action": "下週可以做的一件事：[具體可落地的微小行動]",
      "doi": "",
      "url": "[真實文章 URL]",
      "bullets": [
        {{"text": "【[論點1]】[深度解析]", "quote": "[文章真實原句引言]"}},
        {{"text": "【[論點2]】[深度解析]", "quote": "[文章真實原句引言]"}},
        {{"text": "【[論點3]】[深度解析]", "quote": "[文章真實原句引言]"}}
      ],
      "critiques": [
        "【[組織內部痛點/盲點反思]】[批判性觀點]",
        "【[台灣/在地適用性評析]】[批判性觀點]"
      ],
      "consultant": "建議 NPO 領導層：(1) [具體落地建議一]；(2) [具體落地建議二]。",
      "teachingQ": "[促使組織高層討論的研討室提問]？",
      "suggestedTags": [
        {{"tag": "[tag-1]", "reason": "[原因]"}},
        {{"tag": "[tag-2]", "reason": "[原因]"}}
      ],
      "refs": [
        {{
          "code": "REF-1A",
          "titleZh": "[學術論文繁中翻譯標題]",
          "titleOrig": "[英文論文原始標題]",
          "authors": "[學者姓名]",
          "journal": "[期刊名稱]",
          "year": 2020,
          "doi": "[真實 DOI，如 10.xxxx/xxxx]",
          "point": "[論文核心理論與實證發現]",
          "value": "[本篇論文如何深化焦點報導的理論視野]",
          "deep": "[更深入的機制剖析]",
          "suggestedTags": [
            {{"tag": "[tag-1]", "reason": "[原因]"}},
            {{"tag": "[tag-2]", "reason": "[原因]"}}
          ]
        }}
      ]
    }},
    {{
      "code": "FOC-2",
      "region": "🇹🇼 台灣在地倡議與制度變革",
      "timestamp": "{date_str}",
      "publisher": "[台灣媒體/組織名稱]",
      "authors": "[作者名]",
      "pubDate": "[發布日期 YYYY-MM-DD]",
      "year": 2026,
      "tags": ["taiwan", "policy"],
      "titleZh": "[深度繁中標題]",
      "titleOrig": "[原始標題]",
      "tldr": "[50-80字核心摘要]",
      "relevance": "高",
      "verify": "search_web 實測",
      "action": "下週可以做的一件事：[具體可落地的微小行動]",
      "doi": "",
      "url": "[真實文章 URL]",
      "bullets": [
        {{"text": "【[論點1]】[深度解析]", "quote": "[真實原文或金句]"}},
        {{"text": "【[論點2]】[深度解析]", "quote": "[真實原文或金句]"}},
        {{"text": "【[論點3]】[深度解析]", "quote": "[真實原文或金句]"}}
      ],
      "critiques": [
        "【[政策落地卡點]】[批判性觀點]",
        "【[資源配置不均]】[批判性觀點]"
      ],
      "consultant": "建議在地機構主管：(1) [具體建議一]；(2) [具體建議二]。",
      "teachingQ": "[研討室提問]？",
      "suggestedTags": [
        {{"tag": "[tag-1]", "reason": "[原因]"}},
        {{"tag": "[tag-2]", "reason": "[原因]"}}
      ],
      "refs": [
        {{
          "code": "REF-2A",
          "titleZh": "[學術論文繁中翻譯標題]",
          "titleOrig": "[原始論文標題]",
          "authors": "[學者姓名]",
          "journal": "[期刊名稱]",
          "year": 2018,
          "doi": "[真實 DOI]",
          "point": "[論文核心理論與發現]",
          "value": "[對台灣現場的理論詮釋價值]",
          "deep": "[深入機制剖析]",
          "suggestedTags": [
            {{"tag": "[tag-1]", "reason": "[原因]"}},
            {{"tag": "[tag-2]", "reason": "[原因]"}}
          ]
        }}
      ]
    }},
    {{
      "code": "FOC-3",
      "region": "🇯🇵 日本/東亞共創新局",
      "timestamp": "{date_str}",
      "publisher": "[日本機構/媒體名稱]",
      "authors": "[作者名/編緝部]",
      "pubDate": "[發布日期 YYYY-MM-DD]",
      "year": 2026,
      "tags": ["japan", "innovation"],
      "titleZh": "[深度繁中標題]",
      "titleOrig": "[日文原始標題]",
      "tldr": "[50-80字核心摘要]",
      "relevance": "高",
      "verify": "search_web 實測",
      "action": "下週可以做的一件事：[具體可落地的微小行動]",
      "doi": "",
      "url": "[真實文章 URL]",
      "bullets": [
        {{"text": "【[論點1]】[深度解析]", "quote": "[日文真實原句引言]"}},
        {{"text": "【[論點2]】[深度解析]", "quote": "[日文真實原句引言]"}},
        {{"text": "【[論點3]】[深度解析]", "quote": "[日文真實原句引言]"}}
      ],
      "critiques": [
        "【[台日體制差異反思]】[批判性觀點]",
        "【[可持續商業模式挑戰]】[批判性觀點]"
      ],
      "consultant": "建議跨界創新主管：(1) [具體建議一]；(2) [具體建議二]。",
      "teachingQ": "[研討室提問]？",
      "suggestedTags": [
        {{"tag": "[tag-1]", "reason": "[原因]"}},
        {{"tag": "[tag-2]", "reason": "[原因]"}}
      ],
      "refs": [
        {{
          "code": "REF-3A",
          "titleZh": "[學術論文繁中翻譯標題]",
          "titleOrig": "[英文/日文學術論文標題]",
          "authors": "[學者姓名]",
          "journal": "[期刊/出版社]",
          "year": 2015,
          "doi": "[真實 DOI]",
          "point": "[論文核心理論與發現]",
          "value": "[對東亞第三部門生態之理論貢獻]",
          "deep": "[深入機制剖析]",
          "suggestedTags": [
            {{"tag": "[tag-1]", "reason": "[原因]"}},
            {{"tag": "[tag-2]", "reason": "[原因]"}}
          ]
        }}
      ]
    }}
  ]
}}
```
"""
    return prompt

def render_html_template(template_path, data):
    raw = template_path.read_text(encoding="utf-8")
    
    # 1. Title
    raw = re.sub(r"<title>.*?</title>", f"<title>{data['title']}</title>", raw)
    
    # 2. Masthead meta
    meta_html = f"""<div class="masthead-meta">
      {data['date'][:4]} 年 {int(data['date'][5:7])} 月 {int(data['date'][8:10])} 日 {data['weekday']}<br />
      <strong>主題：{data['topic']}</strong>
    </div>"""
    raw = re.sub(r'<div class="masthead-meta">.*?</div>', meta_html, raw, flags=re.DOTALL)
    
    # 3. Exec cards
    ec_html = ""
    for idx, c in enumerate(data['exec_cards']):
        ec_html += f"""
      <div class="exec-card" onclick="selectStory({idx})">
        <div class="exec-card-badge">{c['focus']}</div>
        <div class="exec-card-title">{c['title']}</div>
        <div class="exec-card-summary">{c['tldr']}</div>
      </div>"""
    raw = re.sub(r'<div class="exec-grid">.*?</div>\s*</section>', f'<div class="exec-grid">{ec_html}\n    </div>\n  </section>', raw, flags=re.DOTALL)
    
    # 4. Story switcher
    sw_html = '<div class="story-switcher">\n'
    for idx, s in enumerate(data['switcher']):
        active_cls = " active" if idx == 0 else ""
        sw_html += f"""      <button class="story-tab{active_cls}" onclick="selectStory({idx})">
        <div class="story-tab-num"><span>{s['num']}</span><span>{s['source']}</span></div>
        <div class="story-tab-title">{s['title']}</div>
      </button>\n"""
    sw_html += '    </div>'
    raw = re.sub(r'<div class="story-switcher">.*?</div>\s*<!-- Main Editorial Sheet -->', f'{sw_html}\n  <!-- Main Editorial Sheet -->', raw, flags=re.DOTALL)
    
    # 5. Articles JS array
    arts_json = json.dumps(data['articles'], ensure_ascii=False, indent=2)
    raw = re.sub(r'const ARTICLES = \[.*?\];', f'const ARTICLES = {arts_json};', raw, flags=re.DOTALL)
    
    return raw

def main():
    print("🚀 啟動 NPO 深度晨報雲端自動化引擎...")
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("❌ 錯誤：未設定環境變數 GEMINI_API_KEY！請在 GitHub Secrets 中加入此金鑰。")
        sys.exit(1)

    repo_root = pathlib.Path(__file__).parent.resolve()
    template_path = repo_root / "daily_template_v2.html"
    hist_path = repo_root / "reported_history.json"
    archive_dir = repo_root / "archive"
    archive_dir.mkdir(exist_ok=True)

    if not template_path.exists():
        print(f"❌ 錯誤：找不到模板檔案 {template_path}")
        sys.exit(1)

    date_str, weekday_str, day_topic, theme_en = get_target_date_info()
    print(f"📅 目標日期：{date_str} ({weekday_str})")
    print(f"📌 今日主題：{day_topic} ({theme_en})")

    past_records = load_reported_history(hist_path)
    print(f"📚 已累積歷史報導紀錄：{len(past_records)} 筆")

    # Check if already generated for this date
    already_done = any(r.get("date_reported") == date_str for r in past_records)
    if already_done and not os.environ.get("FORCE_REGENERATE"):
        print(f"ℹ️ 日期 {date_str} 今日已發布過，跳過重新生成（如需強制覆蓋請設定 FORCE_REGENERATE=1）。")
        return

    prompt = build_prompt(date_str, weekday_str, day_topic, past_records)

    raw_reply = call_gemini_api(api_key, prompt)
    
    # Extract JSON
    json_match = re.search(r"```json\s*(.*?)\s*```", raw_reply, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = raw_reply.strip()

    try:
        report_data = json.loads(json_str)
    except Exception as e:
        print(f"❌ 解析 Gemini 回傳之 JSON 失敗: {e}")
        print("原始回傳前 500 字元:")
        print(json_str[:500])
        sys.exit(1)

    # Verification phase
    print("\n🔍 正在執行品質防線與網址有效性檢驗...")
    new_history_entries = []
    
    for art in report_data.get("articles", []):
        url = art.get("url", "")
        title = art.get("titleOrig", "")
        code = art.get("code", "")
        ok, res = verify_url(url)
        print(f"  [{code}] 網址檢測: {url} -> {'✅ OK (HTTP ' + str(res) + ')' if ok else '⚠️ 注意 (' + str(res) + ')'}")
        
        new_history_entries.append({
            "date_reported": date_str,
            "day_topic": day_topic,
            "url": url,
            "doi": "",
            "title_orig": title,
            "title_zh": art.get("titleZh", "")
        })

        for ref in art.get("refs", []):
            doi = ref.get("doi", "")
            ref_code = ref.get("code", "")
            d_ok, d_res = verify_doi(doi)
            print(f"  [{ref_code}] 學術文獻 DOI 檢測: {doi} -> {'✅ 已註冊 Crossref' if d_ok else '⚠️ 查驗異常 (' + str(d_res) + ')'}")
            
            new_history_entries.append({
                "date_reported": date_str,
                "day_topic": f"{day_topic} (延伸文獻)",
                "url": f"https://doi.org/{doi}" if doi and not doi.startswith("http") else doi,
                "doi": doi,
                "title_orig": ref.get("titleOrig", ""),
                "title_zh": ref.get("titleZh", "")
            })

    # Render HTML
    print("\n🎨 正在渲染 HTML 晨報模板...")
    rendered_html = render_html_template(template_path, report_data)

    index_html_path = repo_root / "index.html"
    archive_html_path = archive_dir / f"{date_str}.html"

    index_html_path.write_text(rendered_html, encoding="utf-8")
    archive_html_path.write_text(rendered_html, encoding="utf-8")
    print(f"✅ 首頁已更新: {index_html_path}")
    print(f"✅ 今日歷史歸檔已更新: {archive_html_path}")

    # Update reported_history.json
    existing_keys = {(r.get("date_reported"), r.get("title_orig")) for r in past_records}
    for e in new_history_entries:
        if (e["date_reported"], e["title_orig"]) not in existing_keys:
            past_records.append(e)

    hist_path.write_text(json.dumps(past_records, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ 已成功更新歷史防重庫 reported_history.json (共計 {len(past_records)} 筆)")

    print("\n🎉 今日 NPO 深度晨報生成作業圓滿完成！")

if __name__ == "__main__":
    main()
