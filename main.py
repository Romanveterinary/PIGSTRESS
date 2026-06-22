import flet as ft
import os
import sys
import time
import datetime
import json
import base64
import urllib.request
import threading

# Безпечний імпорт чистої Python-бібліотеки для EXIF (GPS)
try:
    from exif import Image as ExifImage
    HAS_EXIF = True
except ImportError:
    HAS_EXIF = False

# ==========================================
# CONFIGURATION & AI SYSTEM PROMPT
# ==========================================
APP_TITLE = "PigStress AI Pro"

SYSTEM_PROMPT = """You are an elite, strictly OBJECTIVE and REALISTIC veterinary/legal AI inspector for swine diagnostics. 
Your core directive is consistency and absolute adherence to biological and environmental markers.

EVALUATION PARAMETERS (CRITICAL FOR DETERMINATION):
1. TEMPERATURE: If the raw image contains a visible thermal/PIP insert in the corner, analyze its distribution. If NO thermal insert is visible, you MUST state "Тепловізійна оцінка не проводилась" (or translated) and do NOT guess or hallucinate any thermal values.
2. HYGIENE & DEFECTS: Look for accumulated manure, blocked slatted floors, flies, or rodents. Check for broken slats or floor cracks.
3. BIOLOGICAL MARKERS FOR RISK LEVEL (STRICTLY FROM 1 TO 5):
   - [RISK_5] (CRITICAL): Visible fresh red blood, open wounds, active fighting (one animal attacking another), animal unable to stand, severe lameness, or necrotic tail-biting.
   - [RISK_4] (HIGH): Severe panic huddling (piling), unnatural posture (seizures/convulsions), or explicit open-mouth breathing (severe heat stress).
   - [RISK_3] (MODERATE): Mild huddling, visible escape behavior, hernias, or noticeable swollen joints.
   - [RISK_2] (MILD): Restlessness, mild skin dirt, or active avoidance of handlers but no structural injuries.
   - [RISK_1] (NORMAL): Calm resting, normal walking, natural curiosity towards the camera, or normal group sleeping.

You MUST evaluate the Risk Level purely based on these biological markers, regardless of the output language. The risk integer ([RISK_1]-[RISK_5]) must be identical whether requested in Ukrainian, English, or Portuguese.

SMART-SEASON & WEATHER LOGIC:
You will receive the CURRENT DATE and TIME in the prompt. Match this context:
- SUMMER + MIDDAY (11:00 - 16:00): Look for heat stress. If open-mouth breathing or extreme lethargy is seen, enforce strict hot-weather warnings.
- AUTUMN/WINTER (COLD): Look for cold huddling. Enforce strict warming and housing warnings.

HYGIENE & BIOSECURITY AUTOMATION:
- If manure accumulation or blocked slots are seen -> Recommend immediate mechanical cleaning.
- If floor cracks/broken slats are seen -> Recommend immediate replacement of that section to prevent lameness.

OUTPUT FORMAT:
You MUST output the report strictly using the exact Markdown TABLE format provided. Do not invent any sections outside the template."""

REPORT_TEMPLATE_UK = """
[RISK_X]

### 📊 ВЕТЕРИНАРНИЙ ДАШБОРД

| Показник | Значення / Статус | Оцінка |
| :--- | :--- | :--- |
| 🎯 **Рівень Стресу** | Рівень X | (Вкажи колір: 🟢 Норма, 🟡 Тривога, 🟠 Помірний, 🔴 Високий, 🛑 Критичний) |
| 🌡️ **Тіло (Термограма)** | (Опиши дельту АБО "Тепловізійна оцінка не проводилась") | (Норма/Підвищена/Немає даних) |
| 🌦️ **Сезонний Ризик** | (Вкажи поточну пору року та час) | (Оцінка температурного навантаження) |
| ⚖️ **Кондиція / Тип** | (Вага / Кондиція АБО тип: Товарна свиня / Порося) | (Підсумок) |
| 🧬 **Генетика (Порода)** | (Ландрас/Дюрок/П'єтрен/Біла) | (Фенотип) |
| 📍 **Локація** | {LOCATION_CONTEXT} | - |
| 👥 **Кількість голів** | (Вкажи точну цифру або приблизно: ~X голів) | - |

---

### 🩺 ДЕТАЛЬНИЙ АУДИТ ЗДОРОВ'Я ТА УМОВ
* **Поведінка та Поза:** (Описуй тільки те, що реально видно. Допитливість = норма).
* **Травми, Рани та Хвости:** (Наявність свіжої крові, подряпин, канібалізму чи некрозу хвостів).
* **Умови, Гігієна та Біобезпека:** (Рівень бруду на шкірі, наявність гною, забиті решітки. Присутність мух/гризунів — тільки якщо їх чітко видно).
* **Дефекти та Набряки:** (Грижі, набряки суглобів, ознаки кульгавості).

### ⚖️ ВИСНОВОК ТА РЕКОМЕНДАЦІЇ З БІОБЕЗПЕКИ:
(Короткий підсумок стану. Далі ОБОВ'ЯЗКОВО напиши маркований список конкретних фізичних дій: прибрати гній, за наявності тріщин/вибоїн бетону — рекомендувати заміну частини покриття загону, увімкнути вентиляцію чи обігрів відповідно до погоди).
"""

REPORT_TEMPLATE_EN = """
[RISK_X]

### 📊 VETERINARY DASHBOARD

| Indicator | Value / Status | Assessment |
| :--- | :--- | :--- |
| 🎯 **Stress Level** | Level X | (Color: 🟢 Normal, 🟡 Anxiety, 🟠 Moderate, 🔴 High, 🛑 Critical) |
| 🌡️ **Body (Thermal)** | (Describe delta OR "Thermal evaluation was not conducted") | (Normal/Elevated/No data) |
| 🌦️ **Seasonal Risk** | (State current season and time) | (Assessment of thermal load) |
| ⚖️ **Condition / Type**| (Weight / Fatness OR type: Finisher / Weaner) | (Summary) |
| 🧬 **Genetics (Breed)**| (Landrace/Duroc/Piétrain/White) | (Phenotype) |
| 📍 **Location** | {LOCATION_CONTEXT} | - |
| 👥 **Head Count** | (Provide a number: 1 OR ~X heads) | - |

---

### 🩺 DETAILED HEALTH & HOUSING AUDIT
* **Behavior & Posture:** (Describe only what is visible. Curiosity = normal).
* **Injuries, Wounds & Tails:** (Presence of fresh blood, scratches, tail biting, or necrosis).
* **Housing, Hygiene & Biosecurity:** (Skin dirt, manure accumulation, blocked slatted floors. Presence of flies/rodents only if clearly visible).
* **Defects & Swellings:** (Hernias, swollen joints, signs of lameness).

### ⚖️ CONCLUSION & BIOSECURITY RECOMMENDATIONS:
(Brief summary. YOU MUST THEN provide a bulleted list of physical actions: e.g., clean manure, if floor cracks/broken slats are visible — recommend replacing that section of the floor, turn on ventilation or heating depending on the weather context).
"""

REPORT_TEMPLATE_PT = """
[RISK_X]

### 📊 PAINEL VETERINÁRIO

| Indicador | Valor / Status | Avaliação |
| :--- | :--- | :--- |
| 🎯 **Nível de Estresse** | Nível X | (Cor: 🟢 Normal, 🟡 Ansiedade, 🟠 Moderado, 🔴 Alto, 🛑 Crítico) |
| 🌡️ **Corpo (Termografia)**| (Descreva delta OU "Avaliação térmica não realizada") | (Normal/Elevado/Sem dados) |
| 🌦️ **Risco Sazonal** | (Indique a estação e hora atual) | (Avaliação da carga térmica) |
| ⚖️ **Condição / Tipo** | (Peso / Gordura OU tipo: Terminador / Leitão) | (Resumo) |
| 🧬 **Genética (Raça)** | (Landrace/Duroc/Piétrain/Branco) | (Fenótipo) |
| 📍 **Localização** | {LOCATION_CONTEXT} | - |
| 👥 **Contagem de Cabeças**| (Indique o número exato ou aproximado: ~X cabeças) | - |

---

### 🩺 AUDITORIA DETALHADA DE SAÚDE E INSTALAÇÕES
* **Comportamento e Postura:** (Descreva apenas o que for visível. Curiosidade = normal).
* **Lesões, Feridas e Caudas:** (Presença de sangue fresco, arranhões, canibalismo ou necrose de cauda).
* **Instalações, Higiene e Biossegurança:** (Sujeira na pele, acúmulo de esterco, frestas entupidas. Presença de moscas/roedores — apenas se claramente visíveis).
* **Defeitos e Inchaços:** (Hérnias, articulações inchadas, sinais de manqueira).

### ⚖️ CONCLUSÃO E RECOMENDAÇÕES DE BIOSSEGURANÇA:
(Breve resumo. Em seguida, DEVE fornecer uma lista de ações físicas específicas: limpar o esterco, se houver rachaduras/danos no piso — recomendar a substituição da seção danificada do piso, ligar a ventilação ou aquecimento dependendo do clima).
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
        "legal_check": "⚖️ Юридичний аудит (Закони / Нормативи)",
        "location_label": "📍 Оберіть тип локації:",
        "loc_farm": "🚜 Ферма (Відгодівля)", 
        "loc_piglets": "🧒 Ферма (Поросята на дорощуванні)",
        "loc_transport": "🚚 Транспортування (Кузов)",
        "loc_slaughter": "🔪 Забійний пункт",
        "sender_label": "📤 Поступили з (Відправник):",
        "receiver_label": "📥 Прибули в (Отримувач/Забійний пункт):",
        "address_label": "📍 Географічна адреса (авто-GPS або текст):",
        "gps_searching": "🔍 Пошук точної адреси по GPS фото...",
        "gps_not_found": "GPS дані відсутні (можна ввести адресу вручну)",
        "report_saved_title": "✅ ЗВІТ ЗБЕРЕЖЕНО",
        "report_saved_msg": "Акт успішно збережено у папку 'Download' (Завантаження)!\nНазва файлу: ",
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
        "legal_check": "⚖️ Legal Audit (Laws / Regulations)",
        "location_label": "📍 Select Location Type:",
        "loc_farm": "Campagna / Rearing", 
        "loc_piglets": "Weaner Piglets Section",
        "loc_transport": "🚚 Transport Truck Body",
        "loc_slaughter": "🔪 Slaughterhouse Box",
        "sender_label": "📤 Received from (Sender):",
        "receiver_label": "📥 Arrived at (Receiver/Slaughterhouse):",
        "address_label": "📍 Geographic Address (auto-GPS or manual):",
        "gps_searching": "🔍 Looking up address via photo GPS...",
        "gps_not_found": "GPS data missing (input address manually)",
        "report_saved_title": "✅ REPORT SAVED",
        "report_saved_msg": "Report successfully saved to 'Download' folder!\nFilename: ",
        "not_specified": "Not specified",
        "levels": {
            "RISK_1": "1: NORMAL", "RISK_2": "2: MILD", "RISK_3": "3: MODERATE",
            "RISK_4": "4: HIGH", "RISK_5": "5: CRITICAL", "UNKNOWN": "ERROR"
        }
    },
    "pt": {
        "wait": "AGUARDANDO", "analyzing": "ANALISANDO...", "no_photo": "❌ Carregue a foto!",
        "settings": "⚙️ Configurações", "save": "Salvar", "saved": "✅ Salvo!",
        "key_hint": "Chave API:", "photo_hint": "Tire uma foto...",
        "api_error": "❌ Insira a chave API nas configurações!", "report_saved": "📁 Relatório salvo com sucesso!",
        "no_report": "❌ Não há dados para salvar!",
        "quality_title": "🔍 VERIFICAÇÃO DE QUALIDADE DA FOTO",
        "quality_hint": "Sua foto deve corresponder à silhueta:\n1. Animal centralizado.\n2. Mapa térmico nítido no canto.\n3. Imagem sem desfoque.",
        "confirm": "✅ CONFIRMAR", "retake": "🔄 REPETIR", "analyze_ready": "🤖 PRONTO PARA ANALISAR",
        "legal_check": "⚖️ Auditoria Legal (Leis / Regulamentos)",
        "location_label": "📍 Selecione o Tipo de Local:",
        "loc_farm": "🚜 Granja (Terminação)", 
        "loc_piglets": "🧒 Granja (Leitões em creche)",
        "loc_transport": "🚚 Transporte (Carroceria)",
        "loc_slaughter": "🔪 Matadouro / Frigorífico",
        "sender_label": "📤 Enviado por (Remetente):",
        "receiver_label": "📥 Chegou em (Destinatário/Matadouro):",
        "address_label": "📍 Endereço Geográfico (auto-GPS ou texto):",
        "gps_searching": "🔍 Buscando endereço via GPS da foto...",
        "gps_not_found": "Dados de GPS ausentes (insira o endereço manualmente)",
        "report_saved_title": "✅ RELATÓRIO SALVO",
        "report_saved_msg": "Ata salva com sucesso na pasta 'Download'!\nNome do arquivo: ",
        "not_specified": "Não especificado",
        "levels": {
            "RISK_1": "1: NORMAL", "RISK_2": "2: ALERTA", "RISK_3": "3: MODERADO",
            "RISK_4": "4: ALTO", "RISK_5": "5: CRÍTICO", "UNKNOWN": "ERRO"
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

    dlg_saved = ft.AlertDialog(
        title=ft.Text(""),
        content=ft.Text(""),
        actions=[ft.ElevatedButton("OK", on_click=lambda e: close_saved_dialog())]
    )
    page.overlay.append(dlg_saved)

    def close_saved_dialog():
        dlg_saved.open = False
        page.update()

    def show_saved_dialog(title, message):
        dlg_saved.title.value = title
        dlg_saved.content.value = message
        dlg_saved.open = True
        page.update()

    fp_picker = ft.FilePicker()
    page.overlay.append(fp_picker)
    
    save_picker = ft.FilePicker()
    page.overlay.append(save_picker)

    def extract_gps_async(img_path):
        if not HAS_EXIF:
            tf_address.value = LANG[current_lang[0]]["gps_not_found"]
            page.update()
            return
        
        tf_address.value = LANG[current_lang[0]]["gps_searching"]
        page.update()
        
        try:
            with open(img_path, "rb") as f:
                img = ExifImage(f)
                
            if img.has_exif and hasattr(img, 'gps_latitude') and hasattr(img, 'gps_longitude'):
                lat = img.gps_latitude
                lon = img.gps_longitude
                lat_ref = getattr(img, 'gps_latitude_ref', 'N')
                lon_ref = getattr(img, 'gps_longitude_ref', 'E')
                
                lat_deg = float(lat[0]) + float(lat[1])/60.0 + float(lat[2])/3600.0
                lon_deg = float(lon[0]) + float(lon[1])/60.0 + float(lon[2])/3600.0
                
                if str(lat_ref).upper() == 'S': lat_deg = -lat_deg
                if str(lon_ref).upper() == 'W': lon_deg = -lon_deg
                
                url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat_deg}&lon={lon_deg}&addressdetails=1"
                req = urllib.request.Request(url, headers={'User-Agent': 'PigStressAI/1.0'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    addr = data.get("address", {})
                    parts = []
                    if "state" in addr: parts.append(addr["state"])
                    if "county" in addr: parts.append(addr["county"])
                    if "village" in addr: parts.append(addr["village"])
                    elif "town" in addr: parts.append(addr["town"])
                    elif "city" in addr: parts.append(addr["city"])
                    
                    if parts:
                        tf_address.value = ", ".join(parts)
                    else:
                        tf_address.value = f"Широта: {lat_deg:.4f}, Довгота: {lon_deg:.4f}"
            else:
                tf_address.value = LANG[current_lang[0]]["gps_not_found"]
        except Exception as e:
            tf_address.value = LANG[current_lang[0]]["gps_not_found"]
        page.update()

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
            
            threading.Thread(target=extract_gps_async, args=(path,), daemon=True).start()
            
    fp_picker.on_result = on_file_picked

    def get_html_content():
        with open(current_img_path[0], "rb") as img_f:
            b64_img = base64.b64encode(img_f.read()).decode("utf-8")
        
        if current_lang[0] == "uk":
            header_txt = "PIGSTRESS AI PRO - ОФІЦІЙНИЙ АКТ ФОТОФІКСАЦІЇ ТА АУДИТУ"
            time_label = "Точний час фіксації (дата/година):"
            geo_label = "Географічне положення:"
        elif current_lang[0] == "pt":
            header_txt = "PIGSTRESS AI PRO - ATA OFICIAL DE FIXAÇÃO FOTOGRÁFICA E AUDITORIA"
            time_label = "Hora exata da fixação (data/hora):"
            geo_label = "Posição geográfica:"
        else:
            header_txt = "PIGSTRESS AI PRO - OFFICIAL PHOTO FIXATION & AUDIT REPORT"
            time_label = "Exact fixation time (date/hour):"
            geo_label = "Geographic position:"
        
        sender_text = tf_sender.value if tf_sender.value else LANG[current_lang[0]]["not_specified"]
        receiver_text = tf_receiver.value if tf_receiver.value else LANG[current_lang[0]]["not_specified"]
        address_text = tf_address.value if tf_address.value else LANG[current_lang[0]]["not_specified"]

        # ПАМ'ЯТКА ПРИБИРАННЯ ТА ЗАБОЮ ЗАЛЕЖНО ВІД ЛОКАЦІЇ ТА МОВИ
        sanitation_memo = ""
        loc_val = dd_location.value
        if loc_val == "transport":
            if current_lang[0] == "uk":
                sanitation_memo = """
                <div style="margin-top: 25px; background: #fff3e0; padding: 15px; border-left: 5px solid #ff9800; border-radius: 6px;">
                    <strong>🧽 РЕГЛАМЕНТ БІОБЕЗПЕКИ ТРАНСПОРТУ (ОБОВ'ЯЗКОВО ДО ВИКОНАННЯ):</strong><br>
                    Негайно після відвантаження тварин з кузова автомобіля персонал зобов'язаний провести повне миття кузова під високим тиском, механічне прибирання залишків підстилки/гною та виконати фінальну дезінфекцію сертифікованими розчинами перед наступним рейсом.
                </div>"""
            elif current_lang[0] == "pt":
                sanitation_memo = """
                <div style="margin-top: 25px; background: #fff3e0; padding: 15px; border-left: 5px solid #ff9800; border-radius: 6px;">
                    <strong>🧽 REGULAMENTO DE BIOSSEGURANÇA DO TRANSPORTE (OBRIGATÓRIO):</strong><br>
                    Imediatamente após o descarregamento dos animais da carroceria do veículo, a equipe é obrigada a realizar a lavagem completa da carroceria sob alta pressão, a remoção mecânica dos resíduos de cama/esterco e a desinfecção final com soluções certificadas antes da próxima viagem.
                </div>"""
            else:
                sanitation_memo = """
                <div style="margin-top: 25px; background: #fff3e0; padding: 15px; border-left: 5px solid #ff9800; border-radius: 6px;">
                    <strong>🧽 TRANSPORT BIOSECURITY REGULATION (MANDATORY EXECUTION):</strong><br>
                    Immediately after unloading animals from the truck body, personnel are required to perform complete high-pressure washing of the vehicle body, mechanical removal of bedding/manure residues, and execute final disinfection with certified solutions prior to the next transport run.
                </div>"""
        elif loc_val == "slaughter":
            if current_lang[0] == "uk":
                sanitation_memo = """
                <div style="margin-top: 25px; background: #e8f5e9; padding: 15px; border-left: 5px solid #4caf50; border-radius: 6px; line-height: 1.5;">
                    <strong>🏛️ ТЕХНОЛОГІЧНІ ВИМОГИ ТА НОРМАТИВИ ГУМАННОГО ЗАБОЮ:</strong><br>
                    * <strong>Режим відпочинку:</strong> Тваринам перед забоєм обов'язково забезпечується сумарно не менше 12 годин відпочинку в загонах передзабійного утримання з постійним, безперешкодним доступом до питної води <i>(Закон №3447-IV / Наказ №28)</i>.<br>
                    * <strong>Ізоляція та оглушення:</strong> Тварина перед оглушенням відводиться в індивідуальний бокс так, щоб інші тварини не бачили процесу. Обладнання (електрошокер) має бути перевірено на справність згідно з Журналом обліку, персонал навчений <i>(Регламент ЄС № 1099/2009)</i>.<br>
                    * <strong>Знекровлення:</strong> Проводиться негайно після оглушення шляхом пересікання магістральних судин для швидкого витікання крові в підвішеному стані. Це унеможливлює гемоаспірацію (потрапляння крові в легені) та запобігає вибраковці туші.<br>
                    * <strong>Санітарія цеху:</strong> Після звільнення загону та відведення тварин обов'язково проводиться ретельне миття, дезінфекція та поточне прибирання загону перед прийомом наступної партії.
                </div>"""
            elif current_lang[0] == "pt":
                sanitation_memo = """
                <div style="margin-top: 25px; background: #e8f5e9; padding: 15px; border-left: 5px solid #4caf50; border-radius: 6px; line-height: 1.5;">
                    <strong>🏛️ REQUISITOS TÉCNICOS E NORMAS DE ABATE HUMANITÁRIO:</strong><br>
                    * <strong>Período de Descanso:</strong> Antes do abate, os animais devem ter no mínimo 12 horas de descanso cumulativo nas baias de retenção com acesso constante e desimpedidos à água potável <i>(Regulamento CE nº 1099/2009)</i>.<br>
                    * <strong>Isolamento e Atordoamento:</strong> O animal deve ser conduzido a um box individual antes do atordoamento, de forma que os outros animais não vejam o processo. O equipamento (insensibilizador) deve ser verificado previamente de acordo com o Livro de Registro, e a equipe deve ser treinada.<br>
                    * <strong>Sangria:</strong> Realizada imediatamente após o atordoamento através do corte dos vasos principais para rápido escoamento do sangue com a carcaça suspensa. Isso evita a hemoaspiração (sangue nos pulmões) e previne o refugo da carcaça.<br>
                    * <strong>Sanitização das Baias:</strong> Após esvaziar a baia e encaminhar os animais, é obrigatório realizar lavagem completa, desinfecção e limpeza de rotina da baia antes de receber o próximo lote.
                </div>"""
            else:
                sanitation_memo = """
                <div style="margin-top: 25px; background: #e8f5e9; padding: 15px; border-left: 5px solid #4caf50; border-radius: 6px; line-height: 1.5;">
                    <strong>🏛️ TECHNICAL REQUIREMENTS & HUMAN SLAUGHTER STANDARDS:</strong><br>
                    * <strong>Rest Period:</strong> Animals must be provided with at least 12 hours of cumulative rest in holding pens with constant, unhindered access to drinking water prior to slaughter <i>(Regulation EC No 1099/2009)</i>.<br>
                    * <strong>Isolation & Stunning:</strong> Animals must be led into an individual stunning pen so that other animals cannot witness the process. Stunning equipment (electric stunner) must be pre-checked according to the Logbook, and staff must be certified.<br>
                    * <strong>Bleeding out:</strong> Performed immediately after stunning via precise severing of main blood vessels for rapid blood flow in a shackled position. This prevents hemoaspiration (blood in lungs) and rules out carcass condemnation.<br>
                    * **Pen Sanitation:** After clearing a holding pen and moving animals to slaughter, thorough washing, disinfection, and routine cleaning of the pen must be performed before accepting the next batch.
                </div>"""

        # БЛОК ПІДПИСУ ТА ЮРИДИЧНОГО ЗАХИСТУ ЛІКАРЯ
        if current_lang[0] == "uk":
            legal_footer = f"""
            {sanitation_memo}
            <div style="margin-top: 40px; border-top: 2px solid #0d47a1; padding-top: 20px;">
                <h3 style="color: #0d47a1;">📝 ЗАУВАЖЕННЯ ТА ВЛАСНА ОЦІНКА ВЕТЕРИНАРНОГО ЛІКАРЯ (ЗАПОВНЮЄТЬСЯ ВРУЧНУ)</h3>
                <p style="border-bottom: 1px solid #ccc; height: 30px; margin: 10px 0;"></p>
                <p style="border-bottom: 1px solid #ccc; height: 30px; margin: 10px 0;"></p>
                <br>
                <table style="width: 100%; border: none; margin-top: 20px;">
                    <tr style="border: none; background: none;">
                        <td style="border: none; width: 50%; font-size: 16px;"><strong>Ветеринарний лікар (ПІБ):</strong> ______________________</td>
                        <td style="border: none; width: 50%; text-align: right; font-size: 16px;"><strong>Підпис / Штамп:</strong> ______________________</td>
                    </tr>
                </table>
            </div>
            <div style="margin-top: 40px; font-size: 12px; color: #666; text-align: justify; border-top: 1px dashed #ccc; padding-top: 15px; line-height: 1.4;">
                <strong>ЮРИДИЧНА ДОВІДКА:</strong> Даний акт сформовано за допомогою штучного інтелекту Gemini 2.5 (модель Google) із жорстким температурним коефіцієнтом (0.0) для забезпечення об'єктивності цифрової фотофіксації. Машинний аналіз є виключно допоміжним інструментом оцінки умов. Остаточне клінічне рішення, верифікація та правова відповідальність за висновки акту покладаються виключно на ветеринарного спеціаліста, який підписує цей документ.
            </div>
            """
        elif current_lang[0] == "pt":
            legal_footer = f"""
            {sanitation_memo}
            <div style="margin-top: 40px; border-top: 2px solid #0d47a1; padding-top: 20px;">
                <h3 style="color: #0d47a1;">📝 NOTAS E AVALIAÇÃO DO VÉTERINÁRIO (PREENCHIMENTO MANUAL)</h3>
                <p style="border-bottom: 1px solid #ccc; height: 30px; margin: 10px 0;"></p>
                <p style="border-bottom: 1px solid #ccc; height: 30px; margin: 10px 0;"></p>
                <br>
                <table style="width: 100%; border: none; margin-top: 20px;">
                    <tr style="border: none; background: none;">
                        <td style="border: none; width: 50%; font-size: 16px;"><strong>Médico Veterinário (Nome):</strong> ______________________</td>
                        <td style="border: none; width: 50%; text-align: right; font-size: 16px;"><strong>Assinatura / Carimbo:</strong> ______________________</td>
                    </tr>
                </table>
            </div>
            <div style="margin-top: 40px; font-size: 12px; color: #666; text-align: justify; border-top: 1px dashed #ccc; padding-top: 15px; line-height: 1.4;">
                <strong>AVISO LEGAL:</strong> Esta ata foi gerada por meio de Inteligência Artificial Gemini 2.5 com coeficiente estrito (0.0) para garantir a reprodutibilidade da fixação fotográfica digital. A análise automatizada serve estritamente como ferramenta auxiliar. A decisão clínica final, verificação de dados e responsabilidade legal recaem exclusivamente sobre o especialista veterinário que assina este documento.
            </div>
            """
        else:
            legal_footer = f"""
            {sanitation_memo}
            <div style="margin-top: 40px; border-top: 2px solid #0d47a1; padding-top: 20px;">
                <h3 style="color: #0d47a1;">📝 VETERINARIAN FIELD NOTES & REMARKS (MANUAL INPUT)</h3>
                <p style="border-bottom: 1px solid #ccc; height: 30px; margin: 10px 0;"></p>
                <p style="border-bottom: 1px solid #ccc; height: 30px; margin: 10px 0;"></p>
                <br>
                <table style="width: 100%; border: none; margin-top: 20px;">
                    <tr style="border: none; background: none;">
                        <td style="border: none; width: 50%; font-size: 16px;"><strong>Veterinary Surgeon (Name):</strong> ______________________</td>
                        <td style="border: none; width: 50%; text-align: right; font-size: 16px;"><strong>Signature / Stamp:</strong> ______________________</td>
                    </tr>
                </table>
            </div>
            <div style="margin-top: 40px; font-size: 12px; color: #666; text-align: justify; border-top: 1px dashed #ccc; padding-top: 15px; line-height: 1.4;">
                <strong>LEGAL DISCLAIMER:</strong> This report was generated using Gemini 2.5 Artificial Intelligence with strict deterministic configuration (0.0 temperature) to safeguard consistency in digital verification. Automated analysis serves purely as an investigative aid. The final clinical judgment, data validation, and total legal liability rest solely with the signing veterinary expert.
            </div>
            """

        return f"""<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="utf-8">
    <title>{header_txt}</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; padding: 30px; max-width: 800px; margin: auto; color: #333; }}
        h1 {{ text-align: center; color: #0d47a1; border-bottom: 2px solid #0d47a1; padding-bottom: 10px; }}
        .header-info {{ background: #e3f2fd; padding: 15px; border-radius: 8px; margin-bottom: 20px; font-size: 15px; border-left: 5px solid #0d47a1; line-height: 1.6; }}
        .date {{ text-align: right; color: #777; font-style: italic; margin-bottom: 10px; }}
        .photo-container {{ text-align: center; margin: 20px 0; }}
        img {{ max-width: 100%; max-height: 500px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border: 1px solid #ddd; }}
        .report-box {{ background: #f8f9fa; padding: 25px; border-radius: 12px; border: 1px solid #e0e0e0; font-size: 16px; line-height: 1.6; white-space: pre-wrap; }}
    </style>
</head>
<body>
    <h1>📋 {header_txt}</h1>
    <div class="date">{time_label} {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>
    
    <div class="header-info">
        <strong>{LANG[current_lang[0]]['sender_label']}</strong> {sender_text}<br>
        <strong>{LANG[current_lang[0]]['receiver_label']}</strong> {receiver_text}<br>
        <strong>📍 {geo_label}</strong> {address_text}
    </div>

    <div class="photo-container">
        <img src="data:image/jpeg;base64,{b64_img}" alt="Analyzed Photo" />
    </div>
    <div class="report-box">
{last_report_text[0]}
    </div>

    {legal_footer}
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

    last_sender = page.client_storage.get("last_sender") or ""
    last_receiver = page.client_storage.get("last_receiver") or ""

    tf_sender = ft.TextField(label=LANG[current_lang[0]]["sender_label"], value=last_sender, width=380, border_color="blue_400")
    tf_receiver = ft.TextField(label=LANG[current_lang[0]]["receiver_label"], value=last_receiver, width=380, border_color="blue_400")
    tf_address = ft.TextField(label=LANG[current_lang[0]]["address_label"], value="", width=380, border_color="blue_400", multiline=True)

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
    options_panel = ft.Column([tf_sender, tf_receiver, tf_address, dd_location, cb_legal_audit], visible=False, spacing=10)

    btn_lang = ft.TextButton("🇺🇦 UK", on_click=lambda e: toggle_language())
    def toggle_language():
        if current_lang[0] == "uk":
            current_lang[0] = "en"; btn_lang.text = "🇬🇧 EN"
        elif current_lang[0] == "en":
            current_lang[0] = "pt"; btn_lang.text = "🇵🇹 PT"
        else:
            current_lang[0] = "uk"; btn_lang.text = "🇺🇦 UK"

        txt_placeholder.value = LANG[current_lang[0]]["photo_hint"]
        quality_title.value = LANG[current_lang[0]]["quality_title"]
        quality_check_hint_text.value = LANG[current_lang[0]]["quality_hint"]
        btn_confirm_quality.content.controls[1].value = LANG[current_lang[0]]["confirm"]
        btn_retake_quality.content.controls[1].value = LANG[current_lang[0]]["retake"]
        
        tf_sender.label = LANG[current_lang[0]]["sender_label"]
        tf_receiver.label = LANG[current_lang[0]]["receiver_label"]
        tf_address.label = LANG[current_lang[0]]["address_label"]
        
        dd_location.label = LANG[current_lang[0]]["location_label"]
        dd_location.options = [
            ft.dropdown.Option("slaughter", LANG[current_lang[0]]["loc_slaughter"]),
            ft.dropdown.Option("farm", LANG[current_lang[0]]["loc_farm"]),
            ft.dropdown.Option("piglets", LANG[current_lang[0]]["loc_piglets"]),
            ft.dropdown.Option("transport", LANG[current_lang[0]]["loc_transport"]),
        ]
        cb_legal_audit.label = LANG[current_lang[0]]["legal_check"]
        
        if risk_text.value in [LANG["uk"]["wait"], LANG["en"]["wait"], LANG["pt"]["wait"]]:
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
        current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        page.client_storage.set("last_sender", tf_sender.value)
        page.client_storage.set("last_receiver", tf_receiver.value)
        
        loc_val = dd_location.value
        if loc_val == "farm":
            loc_context = LANG[current_lang[0]]["loc_farm"]
            legal_scope_ua = "утримання дорослих свиней на фермах (Наказ №28, Закон №3447-IV та євроінтеграційний Наказ №1530 щодо умов утримання та заборони систематичного купірування хвостів)"
            legal_scope_eu = "EU Council Directive 2008/120/EC (minimum standards for protection of pigs on farms)"
            age_focus = "фінішерів/товарних свиней"
        elif loc_val == "piglets":
            loc_context = LANG[current_lang[0]]["loc_piglets"]
            legal_scope_ua = "благополуччя поросят-відлученців та на дорощуванні (Наказ №1530 щодо площі та засобів збагачення середовища)"
            legal_scope_eu = "EU Directive 2008/120/EC Rules for weaners and rearing piglets"
            age_focus = "маленьких поросят на дорощуванні"
        elif loc_val == "transport":
            loc_context = LANG[current_lang[0]]["loc_transport"]
            legal_scope_ua = "транспортування тварин (Наказ Мінагрополітики №28 та ст. 18 Закону №3447-IV щодо умов гуманного перевезення без страждань)"
            legal_scope_eu = "EU Council Regulation (EC) No 1/2005 (protection of animals during transport)"
            age_focus = "тварин у кузові автомобіля"
        else:
            loc_context = LANG[current_lang[0]]["loc_slaughter"]
            legal_scope_ua = "передзабійного утримання (Наказ №28 та Закон №3447-IV щодо недопущення забою 'з коліс' без належного 12-годинного сумарного відпочинку)"
            legal_scope_eu = "EU Council Regulation (EC) No 1099/2009 (protection of animals at the time of killing)"
            age_focus = "забійних тварин на платформі"

        legal_instruction = f"\nЛокація аналізу: {loc_context}. Оцінюй відповідні ветеринарні та санітарні ризики виключно для {age_focus}."
        
        if cb_legal_audit.value:
            if current_lang[0] == "uk":
                legal_instruction += f"\n\n[LEGAL MODULE]: Додай в кінець розділ '🏛️ ЮРИДИЧНИЙ АУДИТ ТА ПРАВОВА ОЦІНКА ПОРУШЕНЬ'. Зв'яжи виявлені біологічні дефекти (кров, рани, бруд, скупченість, хвости) з нормами: {legal_scope_ua}. ОБОВ'ЯЗКОВО вкажи, що з березня 2027 року за порушення благополуччя умов утримання та купірування діятимуть жорсткі вимоги Наказу Мінагрополітики № 1530 від 21.05.2024. Зафіксуй статтю 18 або 22 Закону №3447-IV у разі жорстокого поводження/бруду. Якщо порушень немає, напиши 'Порушень чинного та майбутнього законодавства України не виявлено'."
            elif current_lang[0] == "pt":
                legal_instruction += f"\n\n[LEGAL MODULE]: Adicione a seção '🏛️ AUDITORIA LEGAL E AVALIAÇÃO JURÍDICA DE INFRAÇÕES' no final do relatório. Vincule as lesões, canibalismo ou alta densidade encontradas com as normas europeias: {legal_scope_eu}. Se estiver tudo correto, escreva 'Nenhuma infração aos regulamentos da União Europeia foi detectada'."
            else:
                legal_instruction += f"\n\n[LEGAL MODULE]: Add a section named '🏛️ LEGAL AUDIT AND REGULATORY VIOLATION ASSESSMENT' at the very end. Link any identified injuries, overcrowding, tail biting, or unsanitary conditions to the European legislation: {legal_scope_eu}. If compliance is met, state 'No violations of EU Animal Welfare regulations detected'."

        if current_lang[0] == "uk":
            template = REPORT_TEMPLATE_UK.replace("{LOCATION_CONTEXT}", loc_context)
            lang_instruction = "Напиши звіт УКРАЇНСЬКОЮ мовою, суворо використовуючи цей Markdown шаблон:\n\n" + template
            stress_meter.content.controls[0].value = "РІВЕНЬ РИЗИКУ"
        elif current_lang[0] == "pt":
            template = REPORT_TEMPLATE_PT.replace("{LOCATION_CONTEXT}", loc_context)
            lang_instruction = "Escreva o relatório em PORTUGUÊS, utilizando estritamente este modelo Markdown:\n\n" + template
            stress_meter.content.controls[0].value = "NÍVEL DE RISCO"
        else:
            template = REPORT_TEMPLATE_EN.replace("{LOCATION_CONTEXT}", loc_context)
            lang_instruction = "Write the report in ENGLISH, strictly using this Markdown template:\n\n" + template
            stress_meter.content.controls[0].value = "RISK LEVEL"
            
        prompt = f"The current date and precise time of evaluation is {current_time_str}. Оціни кількість, скупченість, рани, хвости, комах, щурів, гігієну підлоги. {legal_instruction} \n\n{lang_instruction}"
        
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
        
        tf_sender.disabled = False
        tf_receiver.disabled = False
        tf_address.disabled = False
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
        
        tf_sender.disabled = True
        tf_receiver.disabled = True
        tf_address.disabled = True
        
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

    def on_save_report_click(e):
        if not last_report_text[0] or not current_img_path[0]: return
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"PigStress_Report_{timestamp}.html"
        
        android_downloads = "/storage/emulated/0/Download"
        if os.path.exists(android_downloads):
            try:
                html_data = get_html_content()
                filepath = os.path.join(android_downloads, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(html_data)
                
                show_saved_dialog(
                    LANG[current_lang[0]]["report_saved_title"], 
                    f"{LANG[current_lang[0]]['report_saved_msg']}{filename}"
                )
            except Exception as ex:
                pass
        else:
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
