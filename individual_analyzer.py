import flet as ft
import urllib.request
import json
import base64
import threading
import os
import datetime

IND_SYSTEM_PROMPT = """Ти — експертний ветеринарний клінічний інспектор. Оглядаєш фотографію тварини зблизька.

КРИТИЧНО: Визнач тип зображення (тепловізор чи звичайне фото). Якщо це звичайне фото, жорстко вкажи: "Тепловізійна оцінка не проводилась".

ОБОВ'ЯЗКОВІ ПАРАМЕТРИ АНАЛІЗУ:
1. СИМЕТРІЯ: Оціни геометрію голови/зони. Асиметрія = механічна травма або абсцес.
2. НАБРЯКИ ТА ТРАВМИ: Кров, порізи, лінійні синці, некроз тканин.
3. ОЧІ ТА СЛИЗОВІ: Колір очей, стан слизових (бліді, гіперемовані/червоні, жовтяничні), виділення, слізні доріжки, енофтальм.
4. ЗАБРУДНЕНІСТЬ: Стан шкірного покриву / оперення (гній, бруд, фекалії).
5. ТЕПЛОВА ДЕЛЬТА (якщо є PiP / тепловізор): Різниця температур між оком та периферичними зонами.

--- ВЕТЕРИНАРНІ ДІАГНОСТИЧНІ ТРИГЕРИ ТА ПІДОЗРИ ---
- СВИНІ (Некроз вух, ціаноз кінчиків вух/кінцівок, крововиливи): Вкажи підозру на АЧС (Африканську чуму свиней) або цирковірусну інфекцію.
- СВИНІ (Чіткі червоні/багряні плями, еритематозні ураження шкіри): Вкажи підозру на бешиху свиней.
- ВРХ / ДРІБНА РОГАТА ХУДОБА (Виразки слизових, сильна слинотеча, ураження носового дзеркала): Вкажи підозру на вірусні інфекції / везикулярні патології.
- ПТИЦЯ (Синюшність/набряк гребеня, сережок, набряк синусів, витікання): Вкажи підозру на респіраторні або системні інфекції птиці.

--- ОБОВ'ЯЗКОВИЙ АЛГОРИТМ БЕЗПЕКИ ПРИ БУДЬ-ЯКИХ ПАТОЛОГІЯХ ---
Якщо виявлено будь-який нетиповий вигляд, підозрілий симптом або погіршення стану, в розділі рекомендацій ОБОВ'ЯЗКОВО вкажи такі дії:
1. Звернути особливу увагу на поведінку тварини (активність, пригнічення, апетит, координація).
2. Провести обов'язкову ректальну термометрію (поголовну або індивідуальну).
3. Негайно від'єднати (ізолювати) тварину від основного стада / поголів'я в окремий загін (карантин).
4. Провести динамічний клінічний нагляд за твариною до встановлення остаточного діагнозу.

ФОРМАТ ВИВОДУ (СУВОРИЙ ШАБЛОН):
Згенеруй звіт ВИКЛЮЧНО українською мовою у форматі Markdown-таблиці.

### 🔬 Акт індивідуального клінічного огляду

| Параметр | Висновок / Оцінка |
| :--- | :--- |
| **Тип зображення** | (Вкажи тип) |
| **Симетрія** | (Розгорнутий опис) |
| **Набряки / Травми** | (Розгорнутий опис або "Не виявлено") |
| **Очі / Слизові** | (Розгорнутий опис стану та виділень) |
| **Забрудненість** | (Розгорнутий опис стану) |
| **Теплова дельта** | (Опис або "Тепловізійна оцінка не проводилась") |
| **Діагностична підозра** | (Опиши ймовірні захворювання на основі симптомів або вкажи "Клінічно здорова / Специфічних маркерів інфекцій не виявлено") |

### ⚠️ Рекомендації та алгоритм дій лікаря:
(Якщо виявлено відхилення — обов'язково опиши дії щодо ізоляції, термометрії та нагляду за алгоритмом безпеки).
"""

def get_individual_analyzer_view(page: ft.Page, on_back_click, global_individual_reports):
    def get_api_key():
        try:
            if os.path.exists("pig_api_key.txt"):
                with open("pig_api_key.txt", "r") as f: return f.read().strip()
        except: pass
        return page.client_storage.get("gemini_api_key") or ""

    current_ind_path = [None]
    last_report_text = [""]
    last_b64_img = [""]

    lbl_title = ft.Text("🔬 ІНДИВІДУАЛЬНИЙ КЛІНІЧНИЙ ОГЛЯД", size=18, weight="bold", color="blue_900")
    
    dd_species = ft.Dropdown(
        label="Вид тварини (Індивідуальний огляд)", 
        options=[ft.dropdown.Option(x) for x in ["Свиня", "ВРХ", "Вівці", "Кози", "Індики", "Кури", "Кролі"]], 
        value="Свиня", 
        width=380
    )
    
    img_preview = ft.Image(width=380, height=220, fit=ft.ImageFit.CONTAIN, visible=False, border_radius=10)
    progress_bar = ft.ProgressBar(width=380, visible=False)
    txt_status = ft.Text("Виберіть вид та завантажте фото (тепловізор або звичайна камера):", color="grey_800")
    
    md_output = ft.Markdown(selectable=True, extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED)
    res_container = ft.Container(content=ft.Column([md_output], scroll=ft.ScrollMode.AUTO), padding=15, bgcolor="#F5F5F5", border_radius=10, height=280, visible=False)

    def get_html_content():
        b64_img = last_b64_img[0]
        species = dd_species.value
        time_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report_text = last_report_text[0]
        
        return f"""<!DOCTYPE html><html lang="uk"><head><meta charset="utf-8"><title>Індивідуальний Аналіз</title>
        <style>body {{ font-family: sans-serif; padding: 30px; max-width: 800px; margin: auto; color: #333; line-height: 1.6; }}
        h1 {{ text-align: center; color: #b71c1c; border-bottom: 2px solid #b71c1c; }} .info {{ background: #ffebee; padding: 15px; border-left: 5px solid #b71c1c; margin-bottom: 20px; }}
        img {{ max-width: 100%; border-radius: 10px; border: 1px solid #ddd; }} .box {{ background: #f8f9fa; padding: 25px; border-radius: 10px; border: 1px solid #e0e0e0; white-space: pre-wrap; }}
        table {{ border-collapse: collapse; width: 100%; }} th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }} th {{ background-color: #f2f2f2; }}
        </style></head><body>
        <h1>🔬 АКТ ІНДИВІДУАЛЬНОГО КЛІНІЧНОГО ОГЛЯДУ</h1>
        <div class="info"><strong>Вид тварини:</strong> {species}<br><strong>Час фіксації:</strong> {time_now}</div>
        <div style="text-align: center; margin: 20px 0;"><img src="data:image/jpeg;base64,{b64_img}" /></div>
        <div class="box">{report_text}</div>
        <div style="margin-top: 40px; border-top: 2px solid #b71c1c; padding-top: 20px;">
            <h3 style="color: #b71c1c;">📝 ВЛАСНА ОЦІНКА ВЕТЕРИНАРНОГО ЛІКАРЯ</h3>
            <p style="border-bottom: 1px solid #ccc; height: 30px; margin: 10px 0;"></p>
            <p style="border-bottom: 1px solid #ccc; height: 30px; margin: 10px 0;"></p>
            <table style="width: 100%; border: none; margin-top: 20px;">
                <tr style="border: none; background: none;">
                    <td style="border: none; width: 50%; font-size: 16px;"><strong>Лікар (ПІБ):</strong> ______________________</td>
                    <td style="border: none; width: 50%; text-align: right; font-size: 16px;"><strong>Підпис:</strong> ______________________</td>
                </tr>
            </table>
        </div>
        </body></html>"""

    save_picker = ft.FilePicker()
    page.overlay.append(save_picker)
    
    def on_save_result(e: ft.FilePickerResultEvent):
        if e.path:
            try:
                with open(e.path, "w", encoding="utf-8") as f: f.write(get_html_content())
                txt_status.value = "✅ Звіт успішно збережено!"
                page.update()
            except Exception as ex:
                txt_status.value = f"❌ Помилка збереження: {ex}"
                page.update()
    
    save_picker.on_result = on_save_result

    def on_save_click(e):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        species_val = dd_species.value
        base_fn = f"Індивідуальний_аналіз_{timestamp}_{species_val}"
        
        andr_dl = "/storage/emulated/0/Download"
        
        if os.path.exists(andr_dl):
            reports_dir = os.path.join(andr_dl, "PigStress_Reports")
            os.makedirs(reports_dir, exist_ok=True)
            html_path = os.path.join(reports_dir, f"{base_fn}.html")
            
            try:
                with open(html_path, "w", encoding="utf-8") as f: 
                    f.write(get_html_content())
                dlg = ft.AlertDialog(title=ft.Text("✅ ЗБЕРЕЖЕНО"), content=ft.Text(f"Акт збережено в:\nDownload/PigStress_Reports/"))
                page.overlay.append(dlg)
                dlg.open = True
                page.update()
            except Exception as ex:
                txt_status.value = f"❌ Помилка запису: {ex}"
                page.update()
        else: 
            save_picker.save_file(file_name=f"{base_fn}.html", allowed_extensions=["html"])

    def on_ind_photo_picked(e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            path = e.files[0].path
            current_ind_path[0] = path
            img_preview.src = path
            img_preview.visible = True
            btn_analyze.visible = True
            btn_save.visible = False
            res_container.visible = False
            txt_status.value = "Фото завантажено. Готово до клінічної експертизи."
            page.update()

    ind_picker = ft.FilePicker(on_result=on_ind_photo_picked)
    page.overlay.append(ind_picker)

    def run_clinical_analysis(e):
        api_key = get_api_key()
        if not api_key:
            txt_status.value = "❌ Введіть API ключ на головному екрані!"
            page.update()
            return

        progress_bar.visible = True
        btn_analyze.disabled = True
        btn_save.visible = False
        txt_status.value = "🤖 Аналіз патологій, травм та теплових маркерів..."
        page.update()

        def run():
            try:
                with open(current_ind_path[0], "rb") as img_f:
                    b64_img = base64.b64encode(img_f.read()).decode("utf-8")
                    last_b64_img[0] = b64_img
                
                species_val = dd_species.value
                species_markers = {
                    "Свиня": "Зосередься на: некроз вушних раковин, 'слізні доріжки', запалі очі, червоні запалені очі, виділення з носа, слинотеча, піна з рота, набряклий язик, асиметрія рила.",
                    "ВРХ": "Зосередься на: червоні запалені очі, рясні виділення, слинотеча, набряклий язик, запалі очі, симетрія морди.",
                    "Вівці": "Зосередься на: запалені очі, виділення, стан слизових, набряки підщелепного простору.",
                    "Кози": "Зосередься на: пошкодження рогів, виділення, запалення слизових, слинотеча.",
                    "Індики": "Зосередься на: запалені очі, виділення з дзьоба, набряк синусів, травми дзьоба.",
                    "Кури": "Зосередься на: виділення з очей/дзьоба, блідість гребеня, набряк голови, заплющені очі.",
                    "Кріль": "Зосередься на: положення та некроз вух, виділення, слинотеча."
                }
                
                prompt_text = f"Вид тварин: {species_val}. {species_markers.get(species_val, '')}\nПроведи клінічний огляд голови або зони ураження. Визнач тип фото. Оціни симетричність, набряки, травми, слизові оболонки та бруд. Якщо це PiP тепловізор, додай аналіз дельти температур."

                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
                payload = {
                    "system_instruction": {"parts": [{"text": IND_SYSTEM_PROMPT}]},
                    "contents": [{
                        "parts": [
                            {"text": prompt_text},
                            {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}}
                        ]
                    }],
                    "generationConfig": {"temperature": 0.0}
                }
                
                req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req) as response:
                    res_data = json.loads(response.read().decode('utf-8'))
                    response_text = res_data['candidates'][0]['content']['parts'][0]['text']
                
                last_report_text[0] = response_text
                md_output.value = response_text
                res_container.visible = True
                btn_save.visible = True
                
                report_data = {
                    "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "text": f"[{species_val}] " + response_text,
                    "img_b64": b64_img
                }
                global_individual_reports.append(report_data)
                
                txt_status.value = "✅ Акт індивідуального клінічного огляду сформовано!"
            except Exception as ex:
                txt_status.value = f"❌ Помилка експертизи: {ex}"
            
            progress_bar.visible = False
            btn_analyze.disabled = False
            page.update()

        threading.Thread(target=run, daemon=True).start()

    btn_pick = ft.ElevatedButton("📸 Фото голови / Зони", icon=ft.Icons.CAMERA, on_click=lambda _: ind_picker.pick_files(file_type=ft.FilePickerFileType.IMAGE))
    btn_analyze = ft.ElevatedButton("🔬 Провести клінічний аналіз", icon=ft.Icons.ANALYTICS, visible=False, bgcolor="red_900", color="white", on_click=run_clinical_analysis)
    btn_save = ft.ElevatedButton("💾 Зберегти HTML-Звіт", icon=ft.Icons.SAVE, visible=False, bgcolor="green_900", color="white", on_click=on_save_click)
    btn_back = ft.TextButton("⬅️ Назад до головного екрану", on_click=on_back_click)

    view = ft.Column([
        btn_back,
        lbl_title,
        ft.Divider(),
        dd_species,
        img_preview,
        ft.Row([btn_pick, btn_analyze, btn_save], alignment=ft.MainAxisAlignment.CENTER, wrap=True),
        ft.Container(height=5),
        txt_status,
        progress_bar,
        res_container
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15)

    return view
