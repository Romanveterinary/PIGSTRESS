import flet as ft
import urllib.request
import json
import base64
import threading
import os
import datetime

IND_SYSTEM_PROMPT = """Ти — експертний ветеринарний клінічний інспектор, що проводить індивідуальну оцінку благополуччя та діагностику тварини.
Ти оглядаєш фотографію однієї тварини зблизька (зосереджуючись переважно на голові, вухах, носі, очах, пащі або специфічних зонах ураження).

КРИТИЧНИЙ ПЕРШИЙ КРОК - ВИЗНАЧЕННЯ ТИПУ ЗОБРАЖЕННЯ:
Визнач, чи є зображення тепловізійним/інфрачервоним (містить штучні кольори, як-от яскраво червоний/білий, холодні сині/зелені плями, теплові шкали) АБО це звичайне фото у видимому світлі.

СЦЕНАРІЙ А: ТЕПЛОВІЗІЙНЕ ЗОБРАЖЕННЯ
1. МАРКЕР ТЕПЛОВОГО СТРЕСУ: Проаналізуй дельту температур між оком та кінцівками (вуха/дзьоб). Висока температура ока відносно кінцівок свідчить про гострий фізіологічний стрес.
2. ТЕМПЕРАТУРА НАБРЯКІВ: Проаналізуй набряки. Холодні зони (сині/зелені) вказують на хронічні ураження, старі гематоми або ішемію. Гарячі зони (червоні/білі) вказують на гостре запалення.

СЦЕНАРІЙ Б: ЗВИЧАЙНЕ ФОТО У ВИДИМОМУ СВІТЛІ
1. Чітко вкажи у звіті: "Тепловізійна оцінка не проводилась (звичайне фото)". Не вигадуй теплові дані.

ДЛЯ ОБОХ СЦЕНАРІЇВ (КЛІНІЧНИЙ АУДИТ):
1. СИМЕТРІЯ НАБРЯКІВ: Досліди геометрію голови/зони. Асиметричний набряк = механічна травма, тупий удар або локалізований абсцес. Симетричний набряк = потенційна системна патологія.
2. ТРАВМИ ТА КРОВ: Шукай свіжу червону кров, порізи шкіри, лінійні синці та ознаки знущань.
3. ЦІЛЬОВІ ПАТОЛОГІЧНІ МАРКЕРИ: Активно шукай специфічні маркери, зазначені у запиті (наприклад, запалення очей, виділення, слинотеча, енофтальм, некроз).

ФОРМАТ ВИВОДУ:
Згенеруй "Акт індивідуального клінічного огляду тварини" виключно українською мовою у форматі Markdown із структурованою клінічною таблицею."""

def get_individual_analyzer_view(page: ft.Page, on_back_click, global_individual_reports):
    def get_api_key():
        try:
            if os.path.exists("pig_api_key.txt"):
                with open("pig_api_key.txt", "r") as f: return f.read().strip()
        except: pass
        return page.client_storage.get("gemini_api_key") or ""

    current_ind_path = [None]

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
    res_container = ft.Container(content=md_output, padding=15, bgcolor="#F5F5F5", border_radius=10, height=280, visible=False)

    def on_ind_photo_picked(e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            path = e.files[0].path
            current_ind_path[0] = path
            img_preview.src = path
            img_preview.visible = True
            btn_analyze.visible = True
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
        txt_status.value = "🤖 Аналіз патологій, травм та теплових маркерів..."
        page.update()

        def run():
            try:
                with open(current_ind_path[0], "rb") as img_f:
                    b64_img = base64.b64encode(img_f.read()).decode("utf-8")
                
                species_val = dd_species.value
                species_markers = {
                    "Свиня": "Зосередься на: некроз вушних раковин, 'слізні доріжки' (патьоки під очима від аміаку), запалі очі (енофтальм/зневоднення), червоні запалені очі, виділення з носа, слинотеча, піна з рота, набряклий язик, асиметрія рила.",
                    "ВРХ": "Зосередься на: червоні запалені очі, рясні виділення з носа або очей, слинотеча, набряклий язик, запалі очі (зневоднення), симетрія морди.",
                    "Вівці": "Зосередься на: запалені очі, виділення з носа/очей, стан слизових оболонок, ознаки зневоднення (енофтальм), набряки підщелепного простору.",
                    "Кози": "Зосередься на: пошкодження рогів, виділення з носа/очей, запалення слизових, набряки суглобів, слинотеча.",
                    "Індики": "Зосередься на: запалені очі, виділення з дзьоба/очей, набряк синусів (під очима), травми дзьоба, стан придатків голови.",
                    "Кури": "Зосередься на: виділення з очей/дзьоба, блідість/синюшність гребеня, набряк голови, заплющені або запалі очі.",
                    "Цесарка": "Зосередься на: виділення з носових отворів, запалення слизових, набряки в області голови, травми від розкльову.",
                    "Кріль": "Зосередься на: положення та некроз вух, виділення з очей та носа, слинотеча (мокра мордочка), запалені очі."
                }
                
                prompt_text = f"Вид тварин: {species_val}. {species_markers.get(species_val, '')}\nПроведи клінічний огляд голови або зони ураження. Визнач тип фотографії. Оціни симетричність, набряки, травми, слизові оболонки та кров. Якщо це тепловізор, додай аналіз дельти температур."

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
                
                md_output.value = response_text
                res_container.visible = True
                
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
    btn_back = ft.TextButton("⬅️ Назад до головного екрану", on_click=on_back_click)

    view = ft.Column([
        btn_back,
        lbl_title,
        ft.Divider(),
        dd_species,
        img_preview,
        btn_pick,
        ft.Container(height=5),
        txt_status,
        progress_bar,
        btn_analyze,
        res_container
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15)

    return view
