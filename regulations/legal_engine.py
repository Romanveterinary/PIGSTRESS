import json
import os

class LegalEngine:
    def __init__(self, data_path="regulations/eu_laws.json"):
        self.data_path = data_path
        self.laws = self._load_laws()

    def _load_laws(self):
        if os.path.exists(self.data_path):
            with open(self.data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def get_violation_info(self, issue_key, lang="en"):
        """
        Повертає опис порушення згідно з регламентами ЄС.
        У майбутньому розширимо логіку для різних мов.
        """
        law = self.laws.get(issue_key)
        if law:
            return f"{law['title']}: {law['description']}"
        return "No specific EU regulation found for this issue."

# Приклад використання в майбутньому:
# engine = LegalEngine()
# print(engine.get_violation_info("transport_1_2005"))
