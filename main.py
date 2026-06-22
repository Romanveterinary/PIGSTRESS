import flet as ft
import os
import sys
import time
import datetime
import json
import base64
import urllib.request
import threading

# ==========================================
# CONFIGURATION & AI SYSTEM PROMPT
# ==========================================
APP_TITLE = "PigStress AI Pro"

SYSTEM_PROMPT = """You are an elite, OBJECTIVE and REALISTIC veterinary/legal AI for SWINE diagnostics. Analyze the image and CURRENT DATE.
Rule 1: ZERO HALLUCINATIONS. Do not invent stress, pests, or injuries if they are not clearly visible. Normal farm dust is NOT a violation.
Rule 2: Natural curiosity, looking at the camera, or mild natural grouping is completely NORMAL and [RISK_1]. Do not flag this as anxiety.
Rule 3: Be strict on blood/injuries. If you see actual red blood or active fighting, assign [RISK_5].

CRITICAL Sequential Evaluation:
STEP 0: COUNTING -> Estimate the number of pigs visible (e.g., "~12 heads" or "1").
STEP 1: FIGHT/INJURY -> [RISK_5] (ONLY if active fighting or fresh red blood is clearly visible).
STEP 2: HIGH STRESS -> [RISK_4] (ONLY if severe panic huddling, freeze response, or explicit thermal vasoconstriction is seen).
STEP 3: MODERATE STRESS -> [RISK_3] (Tense handling, visibly fleeing, visible temp readings > 39.5C).
STEP 4: MILD ANXIETY -> [RISK_2] (Restlessness, active avoidance of humans, tense body language but no full panic).
STEP 5: NORMAL (CALM) -> [RISK_1] (Resting, walking normally, natural curiosity, looking at the camera, mild natural grouping, sleeping).

LOCATION-SPECIFIC RULES:
- Slaughter/Transport: Look for severe overcrowding or fight wounds.
- Farm (Rearing): Assess general hygiene and fatness.
- Farm (Piglets): Look for diarrhea, heat lamps, severe huddling (cold).

ACTIONABLE RECOMMENDATIONS:
In the final section of the report, you MUST act as an expert farm manager. Provide specific, practical, physical interventions based on the season and visual findings. Suggest actions like: building sunshades, adding extra feeders/waterers, moving animals indoors (if cold), turning on ventilation/sprinklers, cleaning manure, providing enrichment (toys/straw), or separating injured pigs.

You MUST output the report strictly using the exact Markdown TABLE format provided."""

REPORT_TEMPLATE_UK = """
[RISK_X]

### 📊 ВЕТЕРИНАРНИЙ ДАШБОРД

| Показник | Значення / Статус | Оцінка |
| :--- | :--- | :--- |
| 🎯 **Рівень Стресу** | Рівень X | (Вкажи колір: 🟢 Норма, 🟡 Тривога, 🟠 Помірний, 🔴 Високий/Критичний) |
| 🌡️ **Тіло (Термограма)** | (Опиши дельту, цифри або "Візуально - Норма") | (Норма/Підвищена/Критична) |
| 🌦️ **Сезонний Ризик** | (Вкажи поточну пору року) | (Спека / Холод / Коливання) |
| ⚖️ **Кондиція / Тип** | (Вага / Кондиція АБО тип: Порося-відлученець) | (Підсумок) |
| 🧬 **Генетика (Порода)** | (Ландрас/Дюрок/П'єтрен/Біла) | (Фенотип) |
| 📍 **Локація** | {LOCATION_CONTEXT} | - |
| 👥 **Кількість голів** | (Обов'язково вкажи цифру: 1 АБО ~X голів) | - |

---

### 🩺 ДЕТАЛЬНИЙ АУДИТ ЗДОРОВ'Я ТА УМОВ
* **Поведінка та Поза:** (Описуй тільки те, що реально бачиш. Допитливість = норма).
* **Травми та Хвости:** (Кров, подряпини, хвостогризіння).
* **Умови та Біобезпека:** (Освітлення. Мухи/гризуни/бруд - тільки якщо їх чітко видно).
* **Дефекти:** (Грижі, набряки суглобів, кульгавість).

### ⚖️ ВИСНОВОК ТА РЕКОМЕНДАЦІЇ: 
(Короткий підсумок стану. ДАЛІ ОБОВ'ЯЗКОВО напиши маркований список конкретних фізичних дій для персоналу: наприклад, прибрати гній, зробити навіс від сонця, додати годівниці/воду, загнати в хлів, увімкнути вентиляцію, ізолювати слабких тощо, спираючись на сезон та фото).
"""

REPORT_TEMPLATE_EN = """
[RISK_X]

### 📊 VETERINARY DASHBOARD

| Indicator | Value / Status | Assessment |
| :--- | :--- | :--- |
| 🎯 **Stress Level** | Level X | (Color: 🟢 Normal, 🟡 Anxiety, 🟠 Moderate, 🔴 High/Critical) |
| 🌡️ **Body (Thermal)** | (Describe delta, numbers, or "Visual - Normal") | (Normal/Elevated/Critical) |
| 🌦️ **Seasonal Risk** | (State current season) | (Assess risk: Heat / Cold / Fluctuations) |
| ⚖️ **Condition / Type**| (Weight / Fatness OR type: Weaner piglet) | (Summary) |
| 🧬 **Genetics (Breed)**| (Landrace/Duroc/Piétrain/White) | (Phenotype) |
| 📍 **Location** | {LOCATION_CONTEXT} | - |
| 👥 **Head Count** | (Must provide a number: 1 OR ~X heads) | - |

---

### 🩺 DETAILED HEALTH & HOUSING AUDIT
* **Behavior & Posture:** (Describe only what is visible. Curiosity = normal).
* **Injuries & Tails:** (Presence of blood, scratches, tail biting).
* **Housing & Biosecurity:** (Assess lighting. Flies/rodents/dirt only if clearly visible).
* **Defects:** (Hernias, swollen joints, lameness).

### ⚖️ CONCLUSION & RECOMMENDATIONS: 
(Brief summary. YOU MUST THEN provide a bulleted list of specific, physical actions for the staff: e.g., clean manure, build a sunshade, add feeders/water, move indoors, turn on ventilation, isolate weak pigs, based on the season and photo).
"""

LANG = {
    "uk": {
        "wait": "ОЧІКУВАННЯ", "analyzing": "АНАЛІЗ...", "no_photo": "❌ Завантажте фото!",
        "settings": "⚙️ Налаштування", "save": "Зберегти", "saved": "✅ Збережено!",
        "key_hint": "API ключ:", "photo_hint": "Зробіть фото...",
        "api_error": "❌ Введіть ключ в налаштуваннях!", "report_saved": "📁 Звіт успішно збережено!",
        "no_report": "❌ Немає даних для збереження!",
        "quality_title": "🔍 ПЕРЕВІРКА ЯКОСТІ ФОТО",
        "quality_hint": "Ваше фото має відповідати силуету:\n1. Тварина в центрі.\n2. Термограма в кутку чітка.\n3. Знімок не змазаний.",
        "confirm": "✅ ПІДТВЕРДИТИ", "retake": "🔄 ПЕРЕРОБИТИ", "analyze_ready": "🤖 ГОТОВИЙ ДО АНАЛІЗУ",
        "legal_check": "⚖️ Юридичний аудит (Закони України)",
        "location_label": "📍 Оберіть локацію та вік:",
        "loc_farm": "🚜 Ферма (Відгодівля)", 
        "loc_piglets": "🧒 Ферма (Поросята на дорощуванні)",
        "loc_transport": "🚚 Транспортування (Кузов)",
        "loc_slaughter": "🔪 Забійний пункт",
        "sender_label": "📤 Поступили з (Відправник):",
        "receiver_label": "📥 Прибули в (Отримувач/Забійний пункт):",
        "not_specified": "Не вказано",
        "levels": {
            "RISK_1": "1: НОРМА", "RISK_2": "2: ТРИВОГА", "RISK_3": "3: ПОМІРНИЙ",
            "RISK_4": "4: ВИСОКИЙ", "RISK_5": "5: КРИТИЧНО", "UNKNOWN": "ПОМИЛКА"
        }
    },
    "en": {
        "wait": "WAITING", "analyzing": "ANALYZING...", "no_photo": "❌ Upload photo!",
        "settings": "⚙️ Settings", "save": "Save", "saved": "✅ Saved!",
        "key_hint": "API key:", "photo_hint": "Take photo...",
        "api_error": "❌ Enter API key in settings!", "report_saved": "📁 Report saved successfully!",
        "no_report": "❌ No data to save!",
        "quality_title": "🔍 PHOTO QUALITY CHECK",
        "quality_hint": "Your photo must match the silhouette:\n1. Animal is centered.\n2. Thermal map is clear.\n3. Image is not blurred.",
        "confirm": "✅ CONFIRM", "retake": "🔄 RETAKE", "analyze_ready": "🤖 READY TO ANALYZE",
        "legal_check": "⚖️ Legal Audit (Laws of Ukraine)",
        "location_label": "📍 Select Location & Age:",
        "loc_farm": "🚜 Farm (Rearing Finishers)", 
        "loc_piglets": "🧒 Farm (Weaner Piglets)",
        "loc_transport": "🚚 Transport (Truck)",
        "loc_slaughter": "🔪 Slaughterhouse",
        "sender_label": "📤 Received from (Sender):",
        "receiver_label": "📥 Arrived at (Receiver/Slaughterhouse):",
        "not_specified": "Not specified",
        "levels": {
            "RISK_1": "1: NORMAL", "RISK_2": "2: MILD", "RISK_3": "3: MODERATE",
            "RISK_4": "4: HIGH", "RISK_5": "5: CRITICAL", "UNKNOWN": "ERROR"
        }
    }
}

def main(page: ft.Page):
    page.title = APP_TITLE
    page.theme_mode = "light"
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

    current_lang = ["uk"]
    current_img_path = [None]
    last_report_text = [""]

    if getattr(sys, 'frozen', False):
        SAFE_DIR = os.path.dirname(sys.executable)
    else:
        SAFE_DIR = os.path.dirname(os.path.abspath(__file__))

    KEY_FILE = os.path.join(SAFE_DIR, "pig_api_key.txt")

    def get_saved_key():
        try:
            if os.path.exists(KEY_FILE):
                with open(KEY_FILE, "r") as f: return f.read().strip()
        except: pass
        return ""

    def save_key(key):
        try:
            with open(KEY_FILE, "w") as f: f.write(key)
        except: pass

    tf_settings_key = ft.TextField(label="Gemini API Key", value=get_saved_key(), password=True, can_reveal_password=True)
    def on_save_settings(e):
        save_key(tf_settings_key.value)
        dlg_settings.open = False
        page.snack_bar = ft.SnackBar(ft.Text(LANG[current_lang[0]]["saved"], color="white"), bgcolor="green")
        page.snack_bar.open = True
        page.update()

    dlg_settings = ft.AlertDialog(
        title=ft.Text("⚙️ Settings"),
        content=ft.Column([ft.Text("API Key:"), tf_settings_key], tight=True),
        actions=[ft.ElevatedButton("Save", on_click=on_save_settings)]
    )
    page.overlay.append(dlg_settings)

    fp_picker = ft.FilePicker()
    page.overlay.append(fp_picker)
    
    save_picker = ft.FilePicker()
    page.overlay.append(save_picker)

    def on_file_picked(e):
        if e.files and len(e.files) > 0:
            path = e.files[0].path
            current_img_path[0] = path
            
            img_quality_check.src = path
            quality_check_panel.visible = True
            
            top_bar.visible = False
            img_preview.visible = False
            img_placeholder.visible = False
            risk_circle.visible = False
            main_buttons_row.visible = False
            options_panel.visible = False
            report_container.visible = False
            page.update()
    fp_picker.on_result = on_file_picked

    # ФУНКЦІЯ ГЕНЕРАЦІЇ HTML
    def get_html_content():
        with open(current_img_path[0], "rb") as img_f:
            b64_img = base64.b64encode(img_f.read()).decode("utf-8")
        header_txt = "PIGSTRESS AI PRO - ОФІЦІЙНИЙ ЗВІТ" if current_lang[0] == "uk" else "PIGSTRESS AI PRO - OFFICIAL REPORT"
        
        # Отримуємо значення підприємств для звіту
        sender_text = tf_sender.value if tf_sender.value else LANG[current_lang[0]]["not_specified"]
        receiver_text = tf_receiver.value if tf_receiver.value else LANG[current_lang[0]]["not_specified"]

        return f"""<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="utf-8">
    <title>{header_txt}</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; padding: 30px; max-width: 800px; margin: auto; color: #333; }}
        h1 {{ text-align: center; color: #0d47a1; border-bottom: 2px solid #0d47a1; padding-bottom: 10px; }}
        .header-info {{ background: #e3f2fd; padding: 15px; border-radius: 8px; margin-bottom: 20px; font-size: 16px; border-left: 5px solid #0d47a1; line-height: 1.5; }}
        .date {{ text-align: right; color: #777; font-style: italic; margin-bottom: 10px; }}
        .photo-container {{ text-align: center; margin: 20px 0; }}
        img {{ max-width: 100%; max-height: 500px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border: 1px solid #ddd; }}
        .report-box {{ background: #f8f9fa; padding: 25px; border-radius: 12px; border: 1px solid #e0e0e0; font-size: 16px; line-height: 1.6; white-space: pre-wrap; }}
    </style>
</head>
<body>
    <h1>📋 {header_txt}</h1>
    <div class="date">Дата генерації: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>
    
    <div class="header-info">
        <strong>{LANG[current_lang[0]]['sender_label']}</strong> {sender_text}<br>
        <strong>{LANG[current_lang[0]]['receiver_label']}</strong> {receiver_text}
    </div>

    <div class="photo-container">
        <img src="data:image/jpeg;base64,{b64_img}" alt="Analyzed Photo" />
    </div>
    <div class="report-box">
{last_report_text[0]}
    </div>
</body>
</html>"""

    def on_save_result(e: ft.FilePickerResultEvent):
        if e.path:
            try:
                html_data = get_html_content()
                with open(e.path, "w", encoding="utf-8") as f:
                    f.write(html_data)
                page.snack_bar = ft.SnackBar(ft.Text(LANG[current_lang[0]]['report_saved']), bgcolor="green")
                page.snack_bar.open = True
            except Exception as ex: 
                print("Помилка збереження:", ex)
            page.update()
    save_picker.on_result = on_save_result

    # === БЛОК ПІДПРИЄМСТВ ТА КЕШУВАННЯ ===
    last_sender = page.client_storage.get("last_sender") or ""
    last_receiver = page.client_storage.get("last_receiver") or ""

    tf_sender = ft.TextField(label=LANG[current_lang[0]]["sender_label"], value=last_sender, width=380, border_color="blue_400")
    tf_receiver = ft.TextField(label=LANG[current_lang[0]]["receiver_label"], value=last_receiver, width=380, border_color="blue_400")

    dd_location = ft.Dropdown(
        label=LANG[current_lang[0]]["location_label"],
        options=[
            ft.dropdown.Option("slaughter", LANG[current_lang[0]]["loc_slaughter"]),
            ft.dropdown.Option("farm", LANG[current_lang[0]]["loc_farm"]),
            ft.dropdown.Option("piglets", LANG[current_lang[0]]["loc_piglets"]),
            ft.dropdown.Option("transport", LANG[current_lang[0]]["loc_transport"]),
        ],
        value="slaughter",
        width=380,
        border_color="blue_400"
    )
    
    cb_legal_audit = ft.Checkbox(label=LANG[current_lang[0]]["legal_check"], value=False, fill_color="blue_900")
    options_panel = ft.Column([tf_sender, tf_receiver, dd_location, cb_legal_audit], visible=False, spacing=10)

    btn_lang = ft.TextButton("🇺🇦 UK", on_click=lambda e: toggle_language())
    def toggle_language():
        current_lang[0] = "en" if current_lang[0] == "uk" else "uk"
        btn_lang.text = "🇬🇧 EN" if current_lang[0] == "en" else "🇺🇦 UK"
        txt_placeholder.value = LANG[current_lang[0]]["photo_hint"]
        quality_title.value = LANG[current_lang[0]]["quality_title"]
        quality_check_hint_text.value = LANG[current_lang[0]]["quality_hint"]
        btn_confirm_quality.content.controls[1].value = LANG[current_lang[0]]["confirm"]
        btn_retake_quality.content.controls[1].value = LANG[current_lang[0]]["retake"]
        
        # Переклад нових полів
        tf_sender.label = LANG[current_lang[0]]["sender_label"]
        tf_receiver.label = LANG[current_lang[0]]["receiver_label"]
        
        dd_location.label = LANG[current_lang[0]]["location_label"]
        dd_location.options = [
            ft.dropdown.Option("slaughter", LANG[current_lang[0]]["loc_slaughter"]),
            ft.dropdown.Option("farm", LANG[current_lang[0]]["loc_farm"]),
            ft.dropdown.Option("piglets", LANG[current_lang[0]]["loc_piglets"]),
            ft.dropdown.Option("transport", LANG[current_lang[0]]["loc_transport"]),
        ]
        cb_legal_audit.label = LANG[current_lang[0]]["legal_check"]
        
        if risk_text.value in [LANG["uk"]["wait"], LANG["en"]["wait"]]:
            risk_text.value = LANG[current_lang[0]]["wait"]
        page.update()

    top_bar = ft.Row([
        btn_lang,
        ft.Text(APP_TITLE, size=22, weight="bold", color="blue_900"),
        ft.IconButton(icon=ft.Icons.SETTINGS, on_click=lambda e: (setattr(dlg_settings, 'open', True), page.update()), icon_size=28)
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    img_preview = ft.Image(src="", width=380, height=220, fit=ft.ImageFit.CONTAIN, visible=False, border_radius=10)
    txt_placeholder = ft.Text(LANG[current_lang[0]]["photo_hint"], color="grey")
    img_placeholder = ft.Container(
        content=ft.Column([ft.Icon(ft.Icons.CAMERA_ALT, size=40, color="grey"), txt_placeholder], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER),
        width=380, height=220, bgcolor="#EEEEEE", border_radius=10, alignment=ft.alignment.center, visible=True
    )

    risk_text = ft.Text(LANG[current_lang[0]]["wait"], color="white", weight="bold", size=13, text_align="center")
    progress_ring = ft.ProgressRing(color="white", visible=False, width=60, height=60)
    
    risk_circle = ft.Container(
        width=160, height=160, border_radius=80, 
        bgcolor="grey", alignment=ft.alignment.center,
        content=ft.Column([
            ft.Icon(ft.Icons.MONITOR_HEART, color="white", size=30, visible=True),
            progress_ring,
            risk_text
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=5),
        shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.BLACK26)
    )

    level_bars = [ft.Container(height=12, expand=True, bgcolor="grey_300", border_radius=5) for _ in range(5)]
    stress_meter = ft.Container(
        content=ft.Column([
            ft.Text("РІВЕНЬ РИЗИКУ", size=12, weight="bold", color="grey_700"),
            ft.Row(level_bars, spacing=4)
        ]),
        visible=False,
        padding=10
    )

    ai_answer = ft.Markdown(value="", selectable=True, extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED)
    
    report_container = ft.Container(
        content=ft.Column([stress_meter, ai_answer], scroll=ft.ScrollMode.AUTO),
        padding=15, bgcolor="#F5F5F5", border_radius=10, height=380, visible=False
    )

    silhouette_overlay = ft.Container(
        content=ft.Icon(ft.Icons.SAVINGS, color="red", size=180, opacity=0.3),
        width=380, height=220, alignment=ft.alignment.center
    )
    
    img_quality_check = ft.Image(src="", width=380, height=220, fit=ft.ImageFit.CONTAIN)
    
    quality_title = ft.Text(LANG[current_lang[0]]["quality_title"], size=18, weight="bold", color="blue_900")
    quality_check_hint_text = ft.Text(LANG[current_lang[0]]["quality_hint"], color="grey_800", text_align="center")

    btn_confirm_quality = ft.ElevatedButton(
        content=ft.Row([ft.Icon(ft.Icons.CHECK), ft.Text(LANG[current_lang[0]]["confirm"])]),
        bgcolor="green_700", color="white",
        on_click=lambda _: confirm_photo_quality()
    )
    btn_retake_quality = ft.OutlinedButton(
        content=ft.Row([ft.Icon(ft.Icons.AUTORENEW), ft.Text(LANG[current_lang[0]]["retake"])]),
        on_click=lambda _: fp_picker.pick_files()
    )

    quality_check_panel = ft.Container(
        content=ft.Column([
            quality_title,
            ft.Stack([img_quality_check, silhouette_overlay], alignment=ft.alignment.center),
            ft.Container(height=5),
            quality_check_hint_text,
            ft.Container(height=5),
            ft.Row([btn_retake_quality, btn_confirm_quality], alignment=ft.MainAxisAlignment.SPACE_EVENLY),
            ft.Divider()
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        visible=False, border_radius=10, bgcolor="#F5F5F5", padding=15
    )

    def process_analysis():
        current_date = datetime.datetime.now().strftime("%B %Y")
        
        # ЗБЕРЕЖЕННЯ В КЕШ: запам'ятовуємо введені дані
        page.client_storage.set("last_sender", tf_sender.value)
        page.client_storage.set("last_receiver", tf_receiver.value)
        
        loc_val = dd_location.value
        if loc_val == "farm":
            loc_context = LANG[current_lang[0]]["loc_farm"]
            legal_scope = "утримання та відгодівлі ДОРОСЛИХ свиней на фермах"
            age_focus = "фінішерів/товарних свиней"
        elif loc_val == "piglets":
            loc_context = LANG[current_lang[0]]["loc_piglets"]
            legal_scope = "утримання та благополуччя ПОРОСЯТ (відлученців/поросят на дорощуванні)"
            age_focus = "маленьких поросят на дорощуванні"
        elif loc_val == "transport":
            loc_context = LANG[current_lang[0]]["loc_transport"]
            legal_scope = "транспортування тварин"
            age_focus = "тварин у кузові"
        else:
            loc_context = LANG[current_lang[0]]["loc_slaughter"]
            legal_scope = "передзабійного утримання, транспортування та забою"
            age_focus = "забійних тварин"

        legal_instruction = f"\nКонтекст локації: Фото зроблено ({loc_context}). Оцінюй відповідні ветеринарні ризики саме для {age_focus}."
        
        if cb_legal_audit.value:
            legal_instruction += f"\n\n[LEGAL MODULE]: Додай в кінець звіту розділ '🏛️ ПОРУШЕННЯ ЗАКОНОДАВСТВА УКРАЇНИ'. УВАГА: Запит юридичного аудиту НЕ ПОВИНЕН впливати на твою базову ветеринарну оцінку та Рівень Ризику! Спочатку об'єктивно оціни стан, а потім, ТІЛЬКИ ЯКЩО є реальні проблеми (Рівень 3-5), вкажи статті Закону щодо {legal_scope}. Якщо все добре (Рівень 1-2), просто напиши 'Порушень законодавства не виявлено'."

        if current_lang[0] == "uk":
            template = REPORT_TEMPLATE_UK.replace("{LOCATION_CONTEXT}", loc_context)
            lang_instruction = "Напиши звіт УКРАЇНСЬКОЮ мовою, суворо використовуючи цей Markdown шаблон:\n\n" + template
            stress_meter.content.controls[0].value = "РІВЕНЬ РИЗИКУ"
        else:
            template = REPORT_TEMPLATE_EN.replace("{LOCATION_CONTEXT}", loc_context)
            lang_instruction = "Write the report in ENGLISH, strictly using this Markdown template:\n\n" + template
            stress_meter.content.controls[0].value = "RISK LEVEL"
            
        prompt = f"Today's date is {current_date}. Оціни кількість, стрес, вгодованість, дефекти. БУДЬ АДЕКВАТНИМ ТА РЕАЛІСТИЧНИМ, не вигадуй паніку чи мух, якщо їх немає. Фото зверху без бійки = НОРМА. {legal_instruction} \n\n{lang_instruction}"
        
        api_key = get_saved_key()
        if not api_key: 
            risk_text.value = LANG[current_lang[0]]["api_error"]
            risk_circle.content.controls[0].visible = True
            progress_ring.visible = False
            page.update()
            return

        try:
            with open(current_img_path[0], "rb") as img_f:
                b64_img = base64.b64encode(img_f.read()).decode("utf-8")
        except: 
            risk_text.value = "❌ Photo read error."
            risk_circle.content.controls[0].visible = True
            progress_ring.visible = False
            page.update()
            return

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        
        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}}
                ]
            }],
            "generationConfig": {
                "temperature": 0.0 
            }
        }
        
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                response_text = res_data['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            response_text = f"❌ Connection error: {e}"

        last_report_text[0] = response_text
        
        risk_level = 0
        if "[RISK_1]" in response_text: risk_level = 1; risk_circle.bgcolor = "green"; risk_text.value = LANG[current_lang[0]]["levels"]["RISK_1"]
        elif "[RISK_2]" in response_text: risk_level = 2; risk_circle.bgcolor = "lightgreen"; risk_text.value = LANG[current_lang[0]]["levels"]["RISK_2"]
        elif "[RISK_3]" in response_text: risk_level = 3; risk_circle.bgcolor = "orange"; risk_text.value = LANG[current_lang[0]]["levels"]["RISK_3"]
        elif "[RISK_4]" in response_text: risk_level = 4; risk_circle.bgcolor = "deeporange"; risk_text.value = LANG[current_lang[0]]["levels"]["RISK_4"]
        elif "[RISK_5]" in response_text: risk_level = 5; risk_circle.bgcolor = "red"; risk_text.value = LANG[current_lang[0]]["levels"]["RISK_5"]
        else: risk_circle.bgcolor = "grey"; risk_text.value = LANG[current_lang[0]]["levels"]["UNKNOWN"]

        active_colors = ["green", "lightgreen", "orange", "deeporange", "red"]
        for i in range(5): level_bars[i].bgcolor = active_colors[i] if i < risk_level else "grey_300"
        stress_meter.visible = True

        for i in range(1, 6): response_text = response_text.replace(f"[RISK_{i}]", "")
        
        ai_answer.value = response_text.strip()
        report_container.visible = True
        progress_ring.visible = False
        risk_circle.content.controls[0].visible = True
        risk_text.visible = True
        
        btn_pick.disabled = False
        btn_analyze.disabled = False
        btn_save.visible = True 
        dd_location.disabled = False
        cb_legal_audit.disabled = False 
        
        # Залишаємо поля активними, щоб можна було виправити помилку, якщо лікар одруківся
        tf_sender.disabled = False
        tf_receiver.disabled = False
        
        page.update()

    def on_analyze(e):
        risk_circle.bgcolor = "blue_700"
        risk_circle.content.controls[0].visible = False 
        risk_text.visible = False
        stress_meter.visible = False
        progress_ring.visible = True
        btn_pick.disabled = True
        btn_analyze.disabled = True
        btn_save.visible = False
        dd_location.disabled = True
        cb_legal_audit.disabled = True 
        
        # Блокуємо поля під час аналізу
        tf_sender.disabled = True
        tf_receiver.disabled = True
        
        ai_answer.value = ""
        report_container.visible = False
        page.update()
        threading.Thread(target=process_analysis).start()

    def confirm_photo_quality():
        img_preview.src = current_img_path[0]
        img_preview.visible = True
        img_placeholder.visible = False
        
        quality_check_panel.visible = False
        top_bar.visible = True
        risk_circle.visible = True
        risk_circle.bgcolor = "grey"
        risk_text.value = LANG[current_lang[0]]["analyze_ready"]
        
        main_buttons_row.visible = True
        btn_analyze.visible = True
        btn_pick.disabled = False
        btn_analyze.disabled = False
        options_panel.visible = True 
        report_container.visible = False
        page.update()

    # 🔥 РОЗУМНА КНОПКА ЗБЕРЕЖЕННЯ ДЛЯ ANDROID / WINDOWS
    def on_save_report_click(e):
        if not last_report_text[0] or not current_img_path[0]: return
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"PigStress_Report_{timestamp}.html"
        
        android_downloads = "/storage/emulated/0/Download"
        if os.path.exists(android_downloads):
            # Якщо це Android, автоматично кидаємо в Завантаження
            try:
                html_data = get_html_content()
                filepath = os.path.join(android_downloads, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(html_data)
                page.snack_bar = ft.SnackBar(ft.Text(f"✅ Збережено у папку 'Download' (Завантаження)!\nШукайте файл: {filename}"), bgcolor="green")
                page.snack_bar.open = True
                page.update()
            except Exception as ex:
                pass
        else:
            # На Windows викликаємо красиве вікно "Зберегти як..."
            save_picker.save_file(
                file_name=filename,
                allowed_extensions=["html"]
            )

    btn_pick = ft.IconButton(icon=ft.Icons.ADD_A_PHOTO_ROUNDED, icon_size=50, icon_color="blue_900", on_click=lambda _: fp_picker.pick_files())
    btn_analyze = ft.IconButton(icon=ft.Icons.FINGERPRINT, icon_size=50, icon_color="green_700", visible=False, on_click=on_analyze)
    btn_save = ft.IconButton(icon=ft.Icons.SAVE_ALT, icon_size=50, icon_color="deep_orange_700", visible=False, on_click=on_save_report_click, tooltip="Зберегти звіт (HTML + Фото)")

    main_buttons_row = ft.Row([btn_pick, btn_analyze, btn_save], alignment=ft.MainAxisAlignment.SPACE_EVENLY, visible=True)

    page.add(
        ft.Column([
            top_bar,
            img_placeholder,
            img_preview,
            quality_check_panel,
            options_panel,
            main_buttons_row,
            ft.Container(height=5),
            risk_circle,
            ft.Container(height=5),
            report_container
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    )

ft.app(target=main)
