import os

# Wir simulieren die Umgebungsvariablen für den Test
os.environ["REDIS_HOST"] = "redis"
os.environ["OPENAI_API_KEY"] = "dummy"  # Wird hier nicht gebraucht
os.environ["TEAMS_WEBHOOK_URL"] = "dummy"

from app.core.vault import PIIVault
from app.core.scanner import PIIScanner
from app.core.database import get_redis_client


def run_test():
    print("⏳ Initialisiere Systeme (Lade GLiNER Modell... das kann kurz dauern)...")

    # 1. Setup
    redis_client = get_redis_client()
    vault = PIIVault(redis_client)
    scanner = PIIScanner(vault)

    # 2. Der Test-Satz
    text = (
        "Mein Name ist Peter Müller, ich wohne in Hamburg und meine Mail ist "
        "peter.mueller@example.com."
    )
    print(f"\n📝 Original: {text}")

    # 3. Die 'Waschstraße' (Clean)
    anonymized_text = scanner.clean(text)
    print(f"🛡️  Gefiltert: {anonymized_text}")

    # 4. Überprüfung
    if "<" in anonymized_text and "Peter Müller" not in anonymized_text:
        print("\n✅ TEST ERFOLGREICH: Namen und Daten wurden ersetzt!")
    else:
        print("\n❌ TEST FEHLGESCHLAGEN: Daten sind noch sichtbar.")


if __name__ == "__main__":
    run_test()

