import flet as ft
import os
import sys
import datetime
import json
import base64
import urllib.request
import threading

try:
    from PIL import Image as PILImage
    import io
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

import document_processor as doc_proc
import individual_analyzer as ind_anf

# ==========================================
# CONFIGURATION & AI SYSTEM PROMPT
# ==========================================
APP_TITLE = "PigStress AI Pro"

SYSTEM_PROMPT = """You are an elite, strictly OBJECTIVE veterinary/legal AI inspector for swine diagnostics. 

EVALUATION PARAMETERS:
1. THERMAL: If thermal/PIP insert exists, analyze it. If NOT, strictly state "Тепловізійна оцінка не проводилась" and do not guess.
2. HYGIENE: Look for manure, blocked slatted floors, flies, rodents, or broken floor slats.
3. VISUAL WEIGHT ESTIMATION: Estimate the approximate average live weight of the group (e.g., '~110-115 kg').
4. BIOLOGICAL MARKERS FOR RISK LEVEL (1 TO 5):
   - [RISK_5] (CRITICAL): Fresh red blood, open wounds, active fighting, unable to stand, severe lameness, necrotic tails.
   - [RISK_4] (HIGH): Severe panic huddling, unnatural posture, open-mouth breathing.
   - [RISK_3] (MODERATE): Mild huddling, escape behavior, hernias, swollen joints.
   - [RISK_2] (MILD): Restlessness, mild skin dirt.
   - [RISK_1] (NORMAL): Calm resting, normal walking.

SMART-SEASON LOGIC:
- SUMMER + MIDDAY: Warn about heat stress.
- AUTUMN/WINTER: Warn about cold stress.

OUTPUT FORMAT:
Generate the report strictly using the exact Markdown TABLE template provided."""

def load_regulations():
    laws_text = "\n\n--- LEGAL KNOWLEDGE BASE (STRICT INSTRUCTIONS: USE ONLY THESE REGULATIONS FOR LEGAL AUDIT, DO NOT INVENT) ---\n"
    base_dir = os.path.dirname(os.path.abspath(__file__)) if not getattr(sys, 'frozen', False) else os.path.dirname(sys.executable)
    reg_dir = os.path.join(base_dir, "regulations")
    
    for file_name in ["ua_laws.json", "eu_laws.json"]:
        path = os.path.join(reg_dir, file_name)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    laws_text += f"\nSource: {file_name}\n"
                    laws_text += json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            except Exception as e:
                print(f"Помилка завантаження {file_name}: {e}")
    return laws_text

SYSTEM_PROMPT += load_regulations()

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

---

### 🩺 ДЕТАЛЬНИЙ АУДИТ ЗДОРОВ'Я ТА УМОВ
* **Поведінка та Поза:** (Тільки те, що реально видно).
* **Травми, Рани та Хвости:** (Кров, подряпини, канібалізм).
* **Гігієна та Біобезпека:** (Бруд, гній, забиті решітки).
* **Дефекти та Набряки:** (Грижі, кульгавість).

### ⚖️ ВИСНОВОК ТА РЕКОМЕНДАЦІЇ:
(Короткий підсумок та фізичні дії).
"""

def get_compressed_b64(image_path, max_size=(800, 800), quality=70):
    if HAS_PIL and image_path and os.path.exists(image_path):
        try:
            img = PILImage.open(image_path)
            try:
                from PIL import ImageOps
                img = ImageOps.exif_transpose(img)
            except: pass
            
            img.thumbnail(max_size)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
        except Exception as e:
            pass
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as img_f:
            return base64.b64encode(img_f.read()).decode("utf-8")
    return ""

def main(page: ft.Page):
    page.title = APP_TITLE
    page.theme_mode = "light"
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

    global_docs_base64 = [None, None, None, None]
    global_individual_reports = []
    
    current_telemetry = {
        "time": None, 
        "lat": None, 
        "lon": None, 
        "maps_link": None
    }

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

    # Апаратна геолокація Flet
    def handle_location(e):
        current_telemetry["lat"] = e.latitude
        current_telemetry["lon"] = e.longitude
        current_telemetry["maps_link"] = f"https://www.google.com/maps?q={e.latitude},{e.longitude}"
        current_telemetry["time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        threading.Thread(target=process_analysis).start()

    def handle_location_error(e):
        current_telemetry["lat"] = None
        current_telemetry["lon"] = None
        current_telemetry["maps_link"] = None
        current_telemetry["time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        threading.Thread(target=process_analysis).start()

    try:
        geolocator = ft.Geolocator(
            on_position=handle_location,
            on_error=handle_location_error
        )
        page.overlay.append(geolocator)
    except Exception:
        geolocator = None

    fp_picker = ft.FilePicker()
    save_picker = ft.FilePicker()
    page.overlay.extend([fp_picker, save_picker])

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
            
    fp_picker.on_result = on_file_picked

    def get_html_content():
        b64_img = get_compressed_b64(current_img_path[0])
        sender_text = tf_sender.value or "Не вказано"
        receiver_text = tf_receiver.value or "Не вказано"

        telemetry_time = current_telemetry['time'] or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if current_telemetry['lat'] and current_telemetry['lon']:
            telemetry_gps = f"<a href='{current_telemetry['maps_link']}' target='_blank'>🗺️ Відкрити на Google Maps</a> ({current_telemetry['lat']:.6f}, {current_telemetry['lon']:.6f})"
        else:
            telemetry_gps = "<span style='color: #d32f2f; font-weight: bold;'>АППАРАТНИЙ GPS ВІДСУТНІЙ (немає сигналу або заборонено доступ)</span>"
        
        telemetry_html_block = f"""
        <div style="margin-top: 20px; background: #fffde7; border-left: 5px solid #fbc02d; padding: 15px; border-radius: 6px;">
            <h3 style="color: #f57f17; margin-top: 0; margin-bottom: 10px;">📡 АПАРАТНА ТЕЛЕМЕТРІЯ (ФІКСАЦІЯ)</h3>
            <div style="font-size: 14px; line-height: 1.6;">
                <strong>🕒 Системний час (момент аналізу):</strong> {telemetry_time}<br>
                <strong>📍 Апаратні GPS Координати:</strong> {telemetry_gps}
            </div>
        </div>
        """

        sanitation_memo = ""
        if dd_location.value == "transport":
            sanitation_memo = """
            <div style="margin-top: 25px; background: #fff3e0; padding: 15px; border-left: 5px solid #ff9800; border-radius: 6px;">
                <strong>🧽 РЕГЛАМЕНТ БІОБЕЗПЕКИ ТРАНСПОРТУ:</strong><br>
                Негайно після відвантаження тварин з кузова автомобіля персонал зобов'язаний провести повне миття кузова під високим тиском та дезінфекцію перед наступним рейсом.
            </div>"""
        elif dd_location.value == "slaughter":
            sanitation_memo = """
            <div style="margin-top: 25px; background: #e8f5e9; padding: 15px; border-left: 5px solid #4caf50; border-radius: 6px; line-height: 1.5;">
                <strong>🏛️ НОРМАТИВИ ГУМАННОГО ЗАБОЮ:</strong><br>
                * Не менше 12 годин відпочинку з доступом до води <i>(Закон №3447-IV)</i>.<br>
                * Ізоляція перед оглушенням.<br>
                * Негайне знекровлення для запобігання гемоаспірації.
            </div>"""

        legal_footer = f"""
        {sanitation_memo}
        <div style="margin-top: 40px; border-top: 2px solid #0d47a1; padding-top: 20px;">
            <h3 style="color: #0d47a1;">📝 ВЛАСНА ОЦІНКА ВЕТЕРИНАРНОГО ЛІКАРЯ</h3>
            <p style="border-bottom: 1px solid #ccc; height: 30px; margin: 10px 0;"></p>
            <p style="border-bottom: 1px solid #ccc; height: 30px; margin: 10px 0;"></p>
            <table style="width: 100%; border: none; margin-top: 20px;">
                <tr style="border: none; background: none;">
                    <td style="border: none; width: 50%; font-size: 16px;"><strong>Лікар (ПІБ):</strong> ______________________</td>
                    <td style="border: none; width: 50%; text-align: right; font-size: 16px;"><strong>Підпис:</strong> ______________________</td>
                </tr>
            </table>
        </div>
        """

        ind_html = ""
        if global_individual_reports:
            ind_html += "<div style='page-break-before: always; margin-top: 50px;'>"
            ind_html += "<h2 style='color: #b71c1c; border-bottom: 2px solid #b71c1c; padding-bottom: 10px;'>🔬 ДОДАТОК: ІНДИВІДУАЛЬНИЙ ОГЛЯД</h2>"
            for idx, rep in enumerate(global_individual_reports):
                ind_html += f"<h4 style='color: #555;'>Об'єкт {idx+1} (Час: {rep['time']})</h4>"
                ind_html += f"<div class='box' style='border-left: 5px solid #b71c1c;'>{rep['text']}</div>"
                ind_html += f"<div style='text-align: center; margin-top: 15px;'><img src='data:image/jpeg;base64,{rep['img_b64']}' style='max-height: 400px; border-radius: 8px;'/></div><br>"
            ind_html += "</div>"

        docs_html = ""
        if any(global_docs_base64):
            docs_html += "<div style='page-break-before: always; margin-top: 50px;'>"
            docs_html += "<h2 style='color: #0d47a1; border-bottom: 2px solid #0d47a1; padding-bottom: 10px;'>📄 ДОДАТОК: СУПРОВІДНА ДОКУМЕНТАЦІЯ</h2>"
            doc_names = ["Свідоцтво 1", "Свідоцтво 2", "Відомість", "Харчовий ланцюг"]
            for idx, b64 in enumerate(global_docs_base64):
                if b64:
                    docs_html += f"<h4 style='color: #555; margin-bottom: 5px;'>{doc_names[idx]}</h4>"
                    docs_html += f"<img src='data:image/jpeg;base64,{b64}' style='max-width: 100%; max-height: 600px; border: 1px solid #ccc; margin-bottom: 25px; border-radius: 8px;'><br>"
            docs_html += "</div>"

        return f"""<!DOCTYPE html><html lang="uk"><head><meta charset="utf-8"><title>Акт Фотофіксації</title>
        <style>body {{ font-family: sans-serif; padding: 30px; max-width: 800px; margin: auto; color: #333; line-height: 1.6; }}
        h1 {{ text-align: center; color: #0d47a1; border-bottom: 2px solid #0d47a1; }} .info {{ background: #e3f2fd; padding: 15px; border-left: 5px solid #0d47a1; }}
        img {{ max-width: 100%; border-radius: 10px; border: 1px solid #ddd; }} .box {{ background: #f8f9fa; padding: 25px; border-radius: 10px; border: 1px solid #e0e0e0; white-space: pre-wrap; }}
        </style></head><body>
        <h1>📋 PIGSTRESS AI - АКТ ПРИЙМАННЯ</h1>
        <div class="info"><strong>Відправник:</strong> {sender_text}<br><strong>Отримувач:</strong> {receiver_text}</div>
        {telemetry_html_block}
        <div style="text-align: center; margin: 20px 0;"><img src="data:image/jpeg;base64,{b64_img}" /></div>
        <div class="box">{last_report_text[0]}</div>
        {legal_footer}
        {ind_html}
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

    tf_sender = ft.TextField(label="Відправник", value=page.client_storage.get("last_sender") or "", width=380)
    tf_receiver = ft.TextField(label="Отримувач", value=page.client_storage.get("last_receiver") or "", width=380)
    dd_location = ft.Dropdown(label="Тип локації", options=[ft.dropdown.Option("slaughter", "Забійний пункт"), ft.dropdown.Option("farm", "Ферма"), ft.dropdown.Option("transport", "Транспорт")], value="slaughter", width=380)
    cb_legal = ft.Checkbox(label="⚖️ Юридичний аудит (Закони)", value=False)
    options_panel = ft.Column([tf_sender, tf_receiver, dd_location, cb_legal], visible=False, spacing=10)

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
            legal_instr = "Додай розділ '⚖️ ЮРИДИЧНИЙ АУДИТ'. Зв'язуй порушення ВИКЛЮЧНО з нормативною базою, наданою в LEGAL KNOWLEDGE BASE. Вигадувати інші закони заборонено."
            
        sys_time = current_telemetry['time'] or datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        prompt = f"Час проведення аналізу: {sys_time}. Локація: {loc_ctx}. {legal_instr} Напиши звіт українською за шаблоном:\n{REPORT_TEMPLATE_UK.replace('{LOCATION_CONTEXT}', loc_ctx)}"
        
        api_key = get_saved_key()
        if not api_key: risk_text.value = "❌ Помилка ключа"; progress_ring.visible = False; risk_circle.content.controls[0].visible = True; page.update(); return

        try:
            b64_img = get_compressed_b64(current_img_path[0])
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            payload = {"system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]}, "contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}}]}], "generationConfig": {"temperature": 0.0}}
            
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req) as response:
                res = json.loads(response.read().decode('utf-8'))
                text = res['candidates'][0]['content']['parts'][0]['text']
            last_report_text[0] = text
            
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
        risk_circle.bgcolor = "blue_700"; risk_circle.content.controls[0].visible = False; progress_ring.visible = True; risk_text.value = "GPS/АНАЛІЗ..."
        btn_pick.disabled = True; btn_analyze.disabled = True; btn_save.visible = False; report_container.visible = False
        page.update()
        
        if geolocator:
            try:
                geolocator.get_current_position()
            except Exception:
                handle_location_error(None)
        else:
            handle_location_error(None)

    def on_save_click(e):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fn = f"PigStress_Report_{timestamp}.html"
        andr_dl = "/storage/emulated/0/Download"
        if os.path.exists(andr_dl):
            with open(os.path.join(andr_dl, fn), "w", encoding="utf-8") as f: f.write(get_html_content())
            dlg = ft.AlertDialog(title=ft.Text("✅ ЗБЕРЕЖЕНО"), content=ft.Text(f"Акт збережено у Download:\n{fn}"))
            page.overlay.append(dlg); dlg.open = True; page.update()
        else: save_picker.save_file(file_name=fn, allowed_extensions=["html"])

    btn_pick = ft.IconButton(icon=ft.Icons.ADD_A_PHOTO, icon_size=40, icon_color="blue_900", on_click=lambda _: fp_picker.pick_files(file_type=ft.FilePickerFileType.IMAGE))
    btn_analyze = ft.IconButton(icon=ft.Icons.FINGERPRINT, icon_size=40, icon_color="green_700", visible=False, on_click=on_analyze)
    btn_save = ft.IconButton(icon=ft.Icons.SAVE_ALT, icon_size=40, icon_color="deep_orange_700", visible=False, on_click=on_save_click)

    express_view = ft.Column([
        img_placeholder, img_preview, options_panel,
        ft.Row([btn_pick, btn_analyze, btn_save], alignment=ft.MainAxisAlignment.SPACE_EVENLY),
        risk_circle, report_container
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)

    main_content = ft.Container(content=express_view)

    def show_express(e=None):
        main_content.content = express_view
        page.update()

    def show_docs(e=None):
        main_content.content = doc_proc.get_document_processor_view(page, show_express, global_docs_base64)
        page.update()

    def show_individual(e=None):
        main_content.content = ind_anf.get_individual_analyzer_view(page, show_express, global_individual_reports)
        page.update()

    def on_exit_click(e):
        try:
            page.window.destroy()
        except:
            pass
        os._exit(0)

    top_bar = ft.Row([
        ft.Text(APP_TITLE, size=22, weight="bold", color="blue_900"),
        ft.Row([
            ft.IconButton(icon=ft.Icons.SETTINGS, on_click=lambda e: (setattr(dlg_settings, 'open', True), page.update())),
            ft.IconButton(icon=ft.Icons.EXIT_TO_APP, icon_color="red_900", on_click=on_exit_click)
        ])
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    nav_tabs = ft.Row([
        ft.ElevatedButton("🚚 Група", icon=ft.Icons.GROUPS, on_click=show_express, bgcolor="blue_50", color="blue_900"),
        ft.ElevatedButton("📄 Папери", icon=ft.Icons.DOCUMENT_SCANNER, on_click=show_docs, bgcolor="blue_50", color="blue_900"),
        ft.ElevatedButton("🔬 Огляд", icon=ft.Icons.BIOTECH, on_click=show_individual, bgcolor="red_50", color="red_900"),
    ], alignment=ft.MainAxisAlignment.CENTER, spacing=5)

    if geolocator:
        page.add(ft.Row([ft.ElevatedButton("Надати дозвіл на GPS", on_click=lambda e: geolocator.request_permission())], alignment=ft.MainAxisAlignment.CENTER))

    page.add(
        ft.Column([
            top_bar,
            nav_tabs,
            ft.Divider(),
            main_content
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    )

ft.app(target=main)
