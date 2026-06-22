import flet as ft
import os
import sys
import time
import datetime
import json
import base64
import urllib.request
import threading

# Підключаємо наші нові модулі!
import document_processor as doc_proc
import individual_analyzer as ind_anf

try:
    from exif import Image as ExifImage
    HAS_EXIF = True
except ImportError:
    HAS_EXIF = False

# ==========================================
# CONFIGURATION & AI SYSTEM PROMPT
# ==========================================
APP_TITLE = "PigStress AI Pro"

SYSTEM_PROMPT = """You are an elite, strictly OBJECTIVE veterinary/legal AI inspector for swine diagnostics. 

EVALUATION PARAMETERS:
1. THERMAL: If thermal/PIP insert exists, analyze it. If NOT, strictly state "Тепловізійна оцінка не проводилась" and do not guess.
2. HYGIENE: Look for manure, blocked slatted floors, flies, rodents, or broken floor slats.
3. VISUAL WEIGHT ESTIMATION (NEW): Based on body proportions and environment, estimate the approximate average live weight of the group (e.g., '~110-115 kg').
4. BIOLOGICAL MARKERS FOR RISK LEVEL (1 TO 5):
   - [RISK_5] (CRITICAL): Fresh red blood, open wounds, active fighting, unable to stand, severe lameness, necrotic tails.
   - [RISK_4] (HIGH): Severe panic huddling, unnatural posture, open-mouth breathing.
   - [RISK_3] (MODERATE): Mild huddling, escape behavior, hernias, swollen joints.
   - [RISK_2] (MILD): Restlessness, mild skin dirt.
   - [RISK_1] (NORMAL): Calm resting, normal walking.

SMART-SEASON LOGIC:
- SUMMER + MIDDAY (11:00 - 16:00): Warn about heat stress, recommend shifting transport hours.
- AUTUMN/WINTER (COLD): Warn about cold huddling, recommend heating/bedding.

HYGIENE AUTOMATION:
- Dirty floor/blocked slots -> Recommend mechanical cleaning.
- Cracks/broken slats -> Recommend replacing floor sections.

OUTPUT FORMAT:
Generate the report strictly using the exact Markdown TABLE template provided."""

REPORT_TEMPLATE_UK = """
[RISK_X]

### 📊 ВЕТЕРИНАРНИЙ ДАШБОРД (ЕКСПРЕС-ГРУПА)

| Показник | Значення / Статус | Оцінка |
| :--- | :--- | :--- |
| 🎯 **Рівень Стресу** | Рівень X | (Колір: 🟢 Норма, 🟡 Тривога, 🟠 Помірний, 🔴 Високий, 🛑 Критичний) |
| 🌡️ **Тіло (Термограма)** | (Опиши дельту АБО "Тепловізійна оцінка не проводилась") | (Норма/Підвищена/Немає даних) |
| 🌦️ **Сезонний Ризик** | (Вкажи поточну пору року та час) | (Оцінка температурного навантаження) |
| ⚖️ **Орієнтовна Вага** | (Напр.: ~110-115 кг) | (Тип: Товарна свиня / Порося) |
| 📍 **Локація** | {LOCATION_CONTEXT} | - |
| 👥 **Кількість голів** | (Видима на фото: ~X голів) | - |

---

### 🩺 ДЕТАЛЬНИЙ АУДИТ ЗДОРОВ'Я ТА УМОВ
* **Поведінка та Поза:** (Тільки те, що реально видно).
* **Травми, Рани та Хвости:** (Кров, подряпини, канібалізм).
* **Гігієна та Біобезпека:** (Бруд, гній, забиті решітки).
* **Дефекти та Набряки:** (Грижі, кульгавість).

### ⚖️ ВИСНОВОК ТА РЕКОМЕНДАЦІЇ:
(Короткий підсумок та фізичні дії: прибрати гній, за наявності тріщин - замінити покриття).
"""

LANG = {"uk": {"wait": "ОЧІКУВАННЯ", "analyzing": "АНАЛІЗ...", "levels": {"RISK_1": "1: НОРМА", "RISK_2": "2: ТРИВОГА", "RISK_3": "3: ПОМІРНИЙ", "RISK_4": "4: ВИСОКИЙ", "RISK_5": "5: КРИТИЧНО", "UNKNOWN": "ПОМИЛКА"}}}

def main(page: ft.Page):
    page.title = APP_TITLE
    page.theme_mode = "light"
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

    # Глобальні змінні для нових модулів
    global_docs_base64 = [None, None, None, None]
    global_individual_reports = []

    current_lang = ["uk"]
    current_img_path = [None]
    last_report_text = [""]

    if getattr(sys, 'frozen', False): SAFE_DIR = os.path.dirname(sys.executable)
    else: SAFE_DIR = os.path.dirname(os.path.abspath(__file__))
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
        page.client_storage.set("gemini_api_key", key)

    tf_settings_key = ft.TextField(label="Gemini API Key", value=get_saved_key(), password=True, can_reveal_password=True)
    def on_save_settings(e):
        save_key(tf_settings_key.value)
        dlg_settings.open = False
        page.snack_bar = ft.SnackBar(ft.Text("✅ Збережено!", color="white"), bgcolor="green")
        page.snack_bar.open = True
        page.update()

    dlg_settings = ft.AlertDialog(title=ft.Text("⚙️ Налаштування"), content=ft.Column([ft.Text("API Key:"), tf_settings_key], tight=True), actions=[ft.ElevatedButton("Зберегти", on_click=on_save_settings)])
    page.overlay.append(dlg_settings)

    fp_picker = ft.FilePicker()
    save_picker = ft.FilePicker()
    page.overlay.extend([fp_picker, save_picker])

    def extract_gps_async(img_path):
        if not HAS_EXIF:
            tf_address.value = "GPS відсутній"
            page.update()
            return
        tf_address.value = "🔍 Пошук по GPS..."
        page.update()
        try:
            with open(img_path, "rb") as f: img = ExifImage(f)
            if img.has_exif and hasattr(img, 'gps_latitude') and hasattr(img, 'gps_longitude'):
                lat, lon = img.gps_latitude, img.gps_longitude
                lat_deg = float(lat[0]) + float(lat[1])/60.0 + float(lat[2])/3600.0
                lon_deg = float(lon[0]) + float(lon[1])/60.0 + float(lon[2])/3600.0
                if str(getattr(img, 'gps_latitude_ref', 'N')).upper() == 'S': lat_deg = -lat_deg
                if str(getattr(img, 'gps_longitude_ref', 'E')).upper() == 'W': lon_deg = -lon_deg
                
                url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat_deg}&lon={lon_deg}&addressdetails=1"
                req = urllib.request.Request(url, headers={'User-Agent': 'PigStressAI/1.0'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    addr = data.get("address", {})
                    parts = [addr.get(k) for k in ["state", "county", "village", "town", "city"] if k in addr]
                    tf_address.value = ", ".join(parts) if parts else f"{lat_deg:.4f}, {lon_deg:.4f}"
            else: tf_address.value = "GPS відсутній"
        except: tf_address.value = "GPS відсутній"
        page.update()

    def on_file_picked(e):
        if e.files:
            path = e.files[0].path
            current_img_path[0] = path
            img_preview.src = path
            img_preview.visible = True
            img_placeholder.visible = False
            risk_circle.visible = True
            risk_circle.bgcolor = "grey"
            risk_text.value = "🤖 ГОТОВИЙ ДО АНАЛІЗУ"
            btn_analyze.visible = True
            btn_analyze.disabled = False
            options_panel.visible = True
            report_container.visible = False
            page.update()
            threading.Thread(target=extract_gps_async, args=(path,), daemon=True).start()
            
    fp_picker.on_result = on_file_picked

    def get_html_content():
        with open(current_img_path[0], "rb") as img_f: b64_img = base64.b64encode(img_f.read()).decode("utf-8")
        
        sender_text = tf_sender.value or "Не вказано"
        receiver_text = tf_receiver.value or "Не вказано"
        address_text = tf_address.value or "Не вказано"

        sanitation_memo = ""
        if dd_location.value == "transport":
            sanitation_memo = """<div style="margin-top: 25px; background: #fff3e0; padding: 15px; border-left: 5px solid #ff9800; border-radius: 6px;"><strong>🧽 РЕГЛАМЕНТ БІОБЕЗПЕКИ ТРАНСПОРТУ:</strong><br>Після відвантаження обов'язкове миття кузова та дезінфекція перед наступним рейсом.</div>"""
        elif dd_location.value == "slaughter":
            sanitation_memo = """<div style="margin-top: 25px; background: #e8f5e9; padding: 15px; border-left: 5px solid #4caf50; border-radius: 6px;"><strong>🏛️ НОРМАТИВИ ГУМАННОГО ЗАБОЮ:</strong><br>* 12 годин відпочинку та водопій (Закон №3447-IV).<br>* Ізоляція від інших при оглушенні. Перевірений електрошокер.<br>* Негайне знекровлення для запобігання гемоаспірації.</div>"""

        legal_footer = f"""
        {sanitation_memo}
        <div style="margin-top: 40px; border-top: 2px solid #0d47a1; padding-top: 20px;">
            <h3 style="color: #0d47a1;">📝 ЗАУВАЖЕННЯ ВЕТЕРИНАРНОГО ЛІКАРЯ</h3>
            <p style="border-bottom: 1px solid #ccc; height: 30px;"></p><p style="border-bottom: 1px solid #ccc; height: 30px;"></p>
            <table style="width: 100%; border: none; margin-top: 20px;"><tr style="border: none; background: none;">
                <td style="border: none; width: 50%; font-size: 16px;"><strong>Ветеринарний лікар:</strong> ________________</td>
                <td style="border: none; width: 50%; text-align: right; font-size: 16px;"><strong>Підпис/Штамп:</strong> ________________</td>
            </tr></table>
        </div>
        """

        # Додаємо сторінку з документами (якщо вони були завантажені у Вкладці 2)
        docs_html = ""
        if any(global_docs_base64):
            docs_html += "<div style='page-break-before: always; margin-top: 50px;'>"
            docs_html += "<h2 style='color: #0d47a1; border-bottom: 2px solid #0d47a1; padding-bottom: 10px;'>📄 ДОДАТОК: СУПРОВІДНА ДОКУМЕНТАЦІЯ</h2>"
            doc_names = ["Ветеринарне свідоцтво (QR)", "Ветеринарне свідоцтво (Бирки)", "Відомість переміщення", "Харчовий ланцюг"]
            for idx, b64 in enumerate(global_docs_base64):
                if b64:
                    docs_html += f"<h4 style='color: #555; margin-bottom: 5px;'>Додаток {idx+1}: {doc_names[idx]}</h4>"
                    docs_html += f"<img src='data:image/jpeg;base64,{b64}' style='max-width: 100%; max-height: 900px; border: 1px solid #ccc; margin-bottom: 25px; border-radius: 8px;'><br>"
            docs_html += "</div>"

        return f"""<!DOCTYPE html><html lang="uk"><head><meta charset="utf-8"><title>Акт Фотофіксації</title>
        <style>body {{ font-family: sans-serif; padding: 30px; max-width: 800px; margin: auto; color: #333; line-height: 1.6; }}
        h1 {{ text-align: center; color: #0d47a1; border-bottom: 2px solid #0d47a1; }} .info {{ background: #e3f2fd; padding: 15px; border-left: 5px solid #0d47a1; }}
        img {{ max-width: 100%; border-radius: 10px; border: 1px solid #ddd; }} .box {{ background: #f8f9fa; padding: 25px; border-radius: 10px; border: 1px solid #e0e0e0; white-space: pre-wrap; }}
        </style></head><body>
        <h1>📋 PIGSTRESS AI - АКТ ПРИЙМАННЯ ТА АУДИТУ</h1>
        <div style="text-align: right; color: #777;">{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>
        <div class="info"><strong>Відправник:</strong> {sender_text}<br><strong>Отримувач:</strong> {receiver_text}<br><strong>Локація:</strong> {address_text}</div>
        <div style="text-align: center; margin: 20px 0;"><img src="data:image/jpeg;base64,{b64_img}" /></div>
        <div class="box">{last_report_text[0]}</div>
        {legal_footer}
        {docs_html}
        </body></html>"""

    def on_save_result(e: ft.FilePickerResultEvent):
        if e.path:
            try:
                with open(e.path, "w", encoding="utf-8") as f: f.write(get_html_content())
                page.snack_bar = ft.SnackBar(ft.Text("✅ Звіт успішно збережено!", color="white"), bgcolor="green"); page.snack_bar.open = True
            except: pass
            page.update()
    save_picker.on_result = on_save_result

    # Елементи форми (Експрес)
    tf_sender = ft.TextField(label="Відправник", value=page.client_storage.get("last_sender") or "", width=380)
    tf_receiver = ft.TextField(label="Отримувач", value=page.client_storage.get("last_receiver") or "", width=380)
    tf_address = ft.TextField(label="GPS Адреса", width=380, multiline=True)
    dd_location = ft.Dropdown(label="Тип локації", options=[ft.dropdown.Option("slaughter", "Забійний пункт"), ft.dropdown.Option("farm", "Ферма"), ft.dropdown.Option("transport", "Транспорт")], value="slaughter", width=380)
    cb_legal = ft.Checkbox(label="⚖️ Юридичний аудит (Закони)", value=False)
    options_panel = ft.Column([tf_sender, tf_receiver, tf_address, dd_location, cb_legal], visible=False, spacing=10)

    # UI Аналізу
    img_preview = ft.Image(width=380, height=220, fit=ft.ImageFit.CONTAIN, visible=False, border_radius=10)
    img_placeholder = ft.Container(content=ft.Column([ft.Icon(ft.Icons.CAMERA_ALT, size=40, color="grey"), ft.Text("Фото групи тварин...", color="grey")], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER), width=380, height=220, bgcolor="#EEEEEE", border_radius=10)
    
    risk_text = ft.Text("ОЧІКУВАННЯ", color="white", weight="bold")
    progress_ring = ft.ProgressRing(color="white", visible=False)
    risk_circle = ft.Container(width=140, height=140, border_radius=70, bgcolor="grey", content=ft.Column([ft.Icon(ft.Icons.MONITOR_HEART, color="white", size=30), progress_ring, risk_text], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER), shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.BLACK26))
    
    ai_answer = ft.Markdown(selectable=True, extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED)
    report_container = ft.Container(content=ft.Column([ai_answer], scroll=ft.ScrollMode.AUTO), padding=15, bgcolor="#F5F5F5", border_radius=10, height=350, visible=False)

    def process_analysis():
        page.client_storage.set("last_sender", tf_sender.value); page.client_storage.set("last_receiver", tf_receiver.value)
        loc_map = {"farm": "Ферма", "slaughter": "Забійний пункт", "transport": "Транспорт (Кузов)"}
        loc_ctx = loc_map[dd_location.value]
        
        legal_instr = ""
        if cb_legal.value:
            legal_instr = "Додай розділ '⚖️ ЮРИДИЧНИЙ АУДИТ'. Зв'яжи порушення з Наказом №28, №1530 та Законом №3447-IV."
            
        prompt = f"Час: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}. Локація: {loc_ctx}. {legal_instr} Напиши звіт українською за шаблоном:\n{REPORT_TEMPLATE_UK.replace('{LOCATION_CONTEXT}', loc_ctx)}"
        
        api_key = get_saved_key()
        if not api_key: risk_text.value = "❌ Помилка ключа"; progress_ring.visible = False; risk_circle.content.controls[0].visible = True; page.update(); return

        try:
            with open(current_img_path[0], "rb") as f: b64_img = base64.b64encode(f.read()).decode("utf-8")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            payload = {"system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]}, "contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}}]}], "generationConfig": {"temperature": 0.0}}
            
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req) as response:
                res = json.loads(response.read().decode('utf-8'))
                text = res['candidates'][0]['content']['parts'][0]['text']
            last_report_text[0] = text
            
            # Парсинг ризику
            if "[RISK_1]" in text: risk_circle.bgcolor = "green"; risk_text.value = "1: НОРМА"
            elif "[RISK_2]" in text: risk_circle.bgcolor = "lightgreen"; risk_text.value = "2: ТРИВОГА"
            elif "[RISK_3]" in text: risk_circle.bgcolor = "orange"; risk_text.value = "3: ПОМІРНИЙ"
            elif "[RISK_4]" in text: risk_circle.bgcolor = "deeporange"; risk_text.value = "4: ВИСОКИЙ"
            elif "[RISK_5]" in text: risk_circle.bgcolor = "red"; risk_text.value = "5: КРИТИЧНО"
            
            for i in range(1, 6): text = text.replace(f"[RISK_{i}]", "")
            ai_answer.value = text.strip()
            report_container.visible = True
            btn_save.visible = True
        except Exception as e:
            risk_text.value = "❌ Помилка"; print(e)
            
        progress_ring.visible = False
        risk_circle.content.controls[0].visible = True
        btn_pick.disabled = False; btn_analyze.disabled = False
        page.update()

    def on_analyze(e):
        risk_circle.bgcolor = "blue_700"; risk_circle.content.controls[0].visible = False; progress_ring.visible = True; risk_text.value = "АНАЛІЗ..."
        btn_pick.disabled = True; btn_analyze.disabled = True; btn_save.visible = False; report_container.visible = False
        page.update(); threading.Thread(target=process_analysis).start()

    def on_save_click(e):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fn = f"PigStress_Report_{timestamp}.html"
        andr_dl = "/storage/emulated/0/Download"
        if os.path.exists(andr_dl):
            with open(os.path.join(andr_dl, fn), "w", encoding="utf-8") as f: f.write(get_html_content())
            dlg = ft.AlertDialog(title=ft.Text("✅ ЗБЕРЕЖЕНО"), content=ft.Text(f"Акт збережено у Download:\n{fn}"))
            page.overlay.append(dlg); dlg.open = True; page.update()
        else: save_picker.save_file(file_name=fn, allowed_extensions=["html"])

    btn_pick = ft.IconButton(icon=ft.Icons.ADD_A_PHOTO, icon_size=40, icon_color="blue_900", on_click=lambda _: fp_picker.pick_files())
    btn_analyze = ft.IconButton(icon=ft.Icons.FINGERPRINT, icon_size=40, icon_color="green_700", visible=False, on_click=on_analyze)
    btn_save = ft.IconButton(icon=ft.Icons.SAVE_ALT, icon_size=40, icon_color="deep_orange_700", visible=False, on_click=on_save_click)

    # ==========================================
    # НАВІГАЦІЯ ТА ЗБІРКА ЕКРАНІВ
    # ==========================================
    
    # 1. Екран Експрес-Група
    express_view = ft.Column([
        img_placeholder, img_preview, options_panel,
        ft.Row([btn_pick, btn_analyze, btn_save], alignment=ft.MainAxisAlignment.SPACE_EVENLY),
        risk_circle, report_container
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)

    # Контейнер, в який ми будемо підвантажувати різні екрани
    main_content = ft.Container(content=express_view)

    # Функції перемикання екранів
    def show_express(e=None):
        main_content.content = express_view
        page.update()

    def show_docs(e=None):
        main_content.content = doc_proc.get_document_processor_view(page, show_express, global_docs_base64)
        page.update()

    def show_individual(e=None):
        main_content.content = ind_anf.get_individual_analyzer_view(page, show_express, global_individual_reports)
        page.update()

    # Верхня панель (Заголовок + Налаштування)
    top_bar = ft.Row([
        ft.Text(APP_TITLE, size=22, weight="bold", color="blue_900"),
        ft.IconButton(icon=ft.Icons.SETTINGS, on_click=lambda e: (setattr(dlg_settings, 'open', True), page.update()))
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    # Панель вкладок (Режими)
    nav_tabs = ft.Row([
        ft.ElevatedButton("🚚 Група", icon=ft.Icons.GROUPS, on_click=show_express, bgcolor="blue_50", color="blue_900"),
        ft.ElevatedButton("📄 Папери", icon=ft.Icons.DOCUMENT_SCANNER, on_click=show_docs, bgcolor="blue_50", color="blue_900"),
        ft.ElevatedButton("🔬 Огляд", icon=ft.Icons.BIOTECH, on_click=show_individual, bgcolor="red_50", color="red_900"),
    ], alignment=ft.MainAxisAlignment.CENTER, spacing=5)

    page.add(
        ft.Column([
            top_bar,
            nav_tabs,
            ft.Divider(),
            main_content
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    )

ft.app(target=main)
