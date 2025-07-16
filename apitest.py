import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    print("❌ GEMINI_API_KEY manquant dans .env")
    exit(1)

genai.configure(api_key=GEMINI_API_KEY)

print("🔍 Vérification des modèles Gemini disponibles...\n")

try:
    # Lister tous les modèles disponibles
    models = genai.list_models()
    
    print("📋 Modèles disponibles:")
    for model in models:
        print(f"  • {model.name}")
        if 'generateContent' in model.supported_generation_methods:
            print(f"    ✅ Supporte generateContent")
        else:
            print(f"    ❌ Ne supporte pas generateContent")
    
    print("\n🧪 Test des modèles recommandés:")
    
    # Tester les modèles courants
    test_models = [
        'gemini-1.5-flash',
        'gemini-1.5-pro',
        'gemini-pro',
        'models/gemini-1.5-flash',
        'models/gemini-1.5-pro'
    ]
    
    for model_name in test_models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content("Dis juste 'OK'")
            print(f"  ✅ {model_name}: {response.text.strip()}")
        except Exception as e:
            print(f"  ❌ {model_name}: {str(e)}")
    
except Exception as e:
    print(f"❌ Erreur lors de la vérification: {e}")
    print("\n💡 Vérifiez votre clé API Gemini:")
    print("   1. Allez sur https://aistudio.google.com/app/apikey")
    print("   2. Créez une nouvelle clé API")
    print("   3. Mettez-la dans votre fichier .env")