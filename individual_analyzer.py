import flet as ft
import urllib.request
import json
import base64
import threading
import os
import datetime

IND_SYSTEM_PROMPT = """You are an expert veterinary clinical inspector performing an individual animal welfare and diagnostic assessment.
You are examining a close-up image of a single pig (primarily focusing on the head, ears, or specific injury zones).

CRITICAL FIRST STEP - DETERMINE IMAGE TYPE:
Determine if the image is a Thermal/Infrared photo (contains false colors like glowing red/white, blue/green cold spots, thermal scales) OR a Standard Visible-Light photo.

SCENARIO A: THERMAL IMAGE
1. THERMAL STRESS MARKER: Analyze the temperature delta between the eye (medial canthus) and the ear tip/canal. High eye temp relative to the ear indicates acute physiological stress.
2. SWELLING TEMPERATURE: Analyze swellings. Cold areas (blue/green) indicate chronic lesions, old hematomas, or ischemia. Hot areas (red/white) indicate acute inflammation.

SCENARIO B: STANDARD VISIBLE-LIGHT IMAGE
1. Explicitly state in the report: "Тепловізійна оцінка не проводилась (звичайне фото)". Do not hallucinate thermal data.

FOR BOTH SCENARIOS (CLINICAL AUDIT):
1. SYMMETRY OF SWELLINGS: Examine the geometry of the head/zone. Asymmetric swelling = mechanical trauma, blunt force, or localized abscess. Symmetric swelling = potential systemic pathology (e.g., edema disease, infection).
2. TRAUMA & BLOOD: Look for fresh red blood, skin cuts, linear bruises (beat marks from prods/whips), and signs of abuse.

OUTPUT FORMAT:
Generate a dedicated "Акт індивідуального клінічного огляду тварини" strictly in Ukrainian, using Markdown format with a structured clinical table."""

def get_individual_analyzer_view(page: ft.Page, on_back_click, global_individual_reports):
    def get_api_key():
        try:
            if os.path.exists("pig_api_key.txt"):
                with open("pig_api_key.txt", "r") as f: return f.read().strip()
        except: pass
        return page.client_storage.get("gemini_api_key") or ""

    current_ind_path = [None]

    lbl_title = ft.Text("🔬 ІНДИВІДУАЛЬНИЙ КЛІНІЧНИЙ ОГЛЯД (ГОЛОВА/ТРАВМИ)", size=18, weight="bold", color="blue_900")
    img_preview = ft.Image(width=380, height=220, fit=ft.ImageFit.CONTAIN, visible=False, border_radius=10)
    
    progress_bar = ft.ProgressBar(width=380, visible=False)
    txt_status = ft.Text("Зробіть фото голови свині (тепловізор або звичайна камера):", color="grey_800")
    
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
        txt_status.value = "🤖 Аналіз симетричності, травм та теплових маркерів..."
        page.update()

        def run():
            try:
                with open(current_ind_path[0], "rb") as img_f:
                    b64_img = base64.b64encode(img_f.read()).decode("utf-8")
                
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
                payload = {
                    "system_instruction": {"parts": [{"text": IND_SYSTEM_PROMPT}]},
                    "contents": [{
                        "parts": [
                            {"text": "Проведи клінічний огляд голови або зони ураження свині. Визнач тип фотографії. Оціни симетричність, набряки, травми та кров. Якщо це тепловізор, додай аналіз дельти температур ока/вуха та характеру набряку (гарячий/холодний)."},
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
                
                # Збереження для подальшого експорту (якщо потрібно)
                report_data = {
                    "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "text": response_text,
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

    btn_pick = ft.ElevatedButton("📸 Фото голови / Зони ураження", icon=ft.Icons.CAMERA, on_click=lambda _: ind_picker.pick_files())
    btn_analyze = ft.ElevatedButton("🔬 Провести клінічний аналіз", icon=ft.Icons.ANALYTICS, visible=False, bgcolor="red_900", color="white", on_click=run_clinical_analysis)
    btn_back = ft.TextButton("⬅️ Назад до головного екрану", on_click=on_back_click)

    view = ft.Column([
        btn_back,
        lbl_title,
        ft.Divider(),
        img_preview,
        btn_pick,
        ft.Container(height=5),
        txt_status,
        progress_bar,
        btn_analyze,
        res_container
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15)

    return view
