import flet as ft
import urllib.request
import json
import base64
import threading
import os

DOC_SYSTEM_PROMPT = """You are an elite expert veterinary auditor. Your task is to perform an advanced cross-check OCR on swine transit documents.
Analyze the provided batch of documents (Vet Certificate Part 1, Vet Certificate Part 2, Movement Sheet, Food Chain Info).

CRITICAL CROSS-CHECK RULES:
1. Extract the 'Номер відомості' and 'Реєстраційний номер господарства' from the Movement Sheet (Відомість переміщення).
2. Find where the 'Номер відомості' is written inside the Veterinary Certificate (Ветеринарне свідоцтво).
3. COMPARE THEM: Explicitly state if the document numbers MATCH or if there is a MISMATCH.
4. Extract ALL Identification Numbers (ТАТУ/БИРКИ) from the special remarks ('Особливі відмітки') of the Veterinary Certificate.
5. Food Chain Information (Харчовий ланцюг): If present, mark as 'В наявності'. If the 4th image is missing, mark as clear dash '—'.
6. QR Code: Locate and extract the digital URL link from the Vet Certificate's QR code if visible.

Present the consolidated audit strictly in a clean Markdown table format with a dedicated section for '⚖️ ВЕТЕРИНАРНА ВЕРИФІКАЦІЯ ДОКУМЕНТІВ'."""

def get_document_processor_view(page: ft.Page, on_back_click, global_docs_base64):
    def get_api_key():
        try:
            if os.path.exists("pig_api_key.txt"):
                with open("pig_api_key.txt", "r") as f: return f.read().strip()
        except: pass
        return page.client_storage.get("gemini_api_key") or ""

    doc_paths = [None, None, None, None]
    doc_labels = [
        "Ветеринарне свідоцтво (Фото з QR-кодом)",
        "Ветеринарне свідоцтво (Особливі відмітки/Бирки)",
        "Відомість переміщення тварин",
        "Інформація про харчовий ланцюг (за наявності)"
    ]

    lbl_title = ft.Text("🔍 ПЕРЕХРЕСНИЙ АУДИТ ДОКУМЕНТІВ (QR & OCR)", size=18, weight="bold", color="blue_900")
    txt_status = ft.Text("Завантажте документи для автоматичної верифікації номерів:", color="grey_800")
    progress_bar = ft.ProgressBar(width=380, visible=False)
    
    md_output = ft.Markdown(selectable=True, extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED)
    res_container = ft.Container(content=md_output, padding=15, bgcolor="#F5F5F5", border_radius=10, height=280, visible=False)

    status_icons = [ft.Icon(ft.Icons.RADIO_BUTTON_UNCHECKED, color="grey") for _ in range(4)]
    
    def make_pick_handler(idx):
        def handler(e: ft.FilePickerResultEvent):
            if e.files and len(e.files) > 0:
                path = e.files[0].path
                doc_paths[idx] = path
                status_icons[idx].name = ft.Icons.CHECK_CIRCLE
                status_icons[idx].color = "green"
                
                try:
                    with open(path, "rb") as img_f:
                        global_docs_base64[idx] = base64.b64encode(img_f.read()).decode("utf-8")
                except:
                    pass
                
                # Дозволяємо сканувати, якщо є перші 3 критичні документи, харчовий ланцюг - опціонально
                if doc_paths[0] and doc_paths[1] and doc_paths[2]:
                    btn_scan.visible = True
                    txt_status.value = "👍 Основні документи готові до перехресної верифікації!"
                page.update()
        return handler

    pickers = []
    rows = []
    for i in range(4):
        p = ft.FilePicker(on_result=make_pick_handler(i))
        pickers.append(p)
        page.overlay.append(p)
        
        rows.append(ft.Row([
            status_icons[i],
            ft.Text(doc_labels[i], weight="bold", expand=True),
            ft.IconButton(ft.Icons.CENTER_FOCUS_STRONG if i==0 else ft.Icons.UPLOAD_FILE, on_click=lambda _, picker=p: picker.pick_files())
        ], width=380))

    def start_ocr(e):
        api_key = get_api_key()
        if not api_key:
            txt_status.value = "❌ Введіть API ключ на головному екрані!"
            page.update()
            return

        progress_bar.visible = True
        btn_scan.disabled = True
        txt_status.value = "🤖 Робот проводить звірку номерів відомостей та зчитує QR-код..."
        page.update()

        def run():
            try:
                parts_payload = [{"text": "Проведи повний перехресний аудит пакету документів. Порівняй номери відомості у свідоцтві та відомості переміщення. Зчитай бирки з особливих відміток. Відповідь надай українською мовою."}]
                for b64 in global_docs_base64:
                    if b64:
                        parts_payload.append({"inline_data": {"mime_type": "image/jpeg", "data": b64}})
                
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
                payload = {
                    "system_instruction": {"parts": [{"text": DOC_SYSTEM_PROMPT}]},
                    "contents": [{"parts": parts_payload}],
                    "generationConfig": {"temperature": 0.0}
                }
                
                req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req) as response:
                    res_data = json.loads(response.read().decode('utf-8'))
                    response_text = res_data['candidates'][0]['content']['parts'][0]['text']
                
                md_output.value = response_text
                res_container.visible = True
                txt_status.value = "✅ Перехресна верифікація документів завершена успішно!"
            except Exception as ex:
                txt_status.value = f"❌ Помилка звірки документів: {ex}"
            
            progress_bar.visible = False
            btn_scan.disabled = False
            page.update()

        threading.Thread(target=run, daemon=True).start()

    btn_scan = ft.ElevatedButton("🔍 Запустити верифікацію та звірку номерів", icon=ft.Icons.FACT_CHECK, visible=False, bgcolor="blue_900", color="white", on_click=start_ocr)
    btn_back = ft.TextButton("⬅️ Назад до головного екрану", on_click=on_back_click)

    view = ft.Column([
        btn_back,
        lbl_title,
        ft.Divider(),
        txt_status,
        ft.Column(rows, spacing=10),
        progress_bar,
        ft.Container(height=5),
        btn_scan,
        res_container
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15)

    return view
