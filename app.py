import os
import logging
from typing import Dict, Optional
from flask import Flask, request
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse  # Correction ici
from dotenv import load_dotenv
import google.generativeai as genai
from datetime import datetime, timedelta

# Chargement des variables d'environnement
load_dotenv()

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# Configuration Twilio
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_NUMBER = os.getenv('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')

# Initialisation des clients
try:
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    model = genai.GenerativeModel('gemini-pro')  # Modèle plus stable
except Exception as e:
    logger.error(f"Erreur d'initialisation: {e}")
    raise

# Configuration des domaines
DOMAINS = {
    'programmation': {
        'expert_whatsapp': os.getenv('PROGRAMMATION_WHATSAPP', 'whatsapp:+237698856730'),
        'expert_phone': os.getenv('PROGRAMMATION_PHONE', '+237698856730'),
        'keywords': ['1', 'prog', 'code', 'dev', 'python'],
        'resources': {
            'fr': ['Python: https://docs.python.org/fr/3/tutorial/'],
            'en': ['Python: https://docs.python.org/3/tutorial/']
        }
    },
    'design': {
        'expert_whatsapp': os.getenv('DESIGN_WHATSAPP', 'whatsapp:+237698856730'),
        'expert_phone': os.getenv('DESIGN_PHONE', '+237698856730'),
        'keywords': ['2', 'design', 'graphisme', 'canva'],
        'resources': {
            'fr': ['Canva: https://www.canva.com/fr_fr/learn/design/'],
            'en': ['Canva: https://www.canva.com/learn/design/']
        }
    }
}

# Messages optimisés
MESSAGES = {
    'welcome': "Bienvenue! Choisissez:\n1. Programmation 💻\n2. Design 🎨",
    'ask_name': "Quel est votre prénom ? 👋",
    'resources': "📖 Ressources {domain}:\n{resources}\n\nContact expert ? (Oui/Non)",
    'contact_options': "Contact par:\n1. Message\n2. Appel\n3. Les deux",
    'confirmations': {
        'message': "✅ Message envoyé!",
        'call': "✅ Appel initié!",
        'both': "✅ Message et appel envoyés!"
    },
    'error': "❌ Action non disponible"
}

class ConversationManager:
    def __init__(self):
        self.sessions = {}
        
    def get_session(self, user_id: str) -> Dict:
        if user_id not in self.sessions:
            self.sessions[user_id] = {
                'lang': 'fr',
                'step': 'init',
                'data': {},
                'last_active': datetime.now()
            }
        return self.sessions[user_id]
    
    def reset_if_inactive(self, session: Dict):
        if (datetime.now() - session['last_active']) > timedelta(minutes=30):
            session.update({'step': 'init', 'data': {}})

class TwilioService:
    @staticmethod
    def send_whatsapp(to: str, body: str) -> bool:
        try:
            twilio_client.messages.create(
                body=body,
                from_=TWILIO_WHATSAPP_NUMBER,
                to=to
            )
            return True
        except Exception as e:
            logger.error(f"Erreur WhatsApp: {e}")
            return False
    
    @staticmethod
    def make_call(to: str, message: str) -> bool:
        try:
            twilio_client.calls.create(
                twiml=f'<Response><Say language="fr-FR">{message}</Say></Response>',
                to=to,
                from_=TWILIO_PHONE_NUMBER
            )
            return True
        except Exception as e:
            logger.error(f"Erreur appel: {e}")
            return False

# Initialisation des services
conv_manager = ConversationManager()
twilio_service = TwilioService()

@app.route('/webhook', methods=['POST'])
def whatsapp_webhook():
    try:
        user_id = request.values.get('From', '')
        message = request.values.get('Body', '').strip().lower()
        
        if not user_id or not message:
            return str(MessagingResponse().message("Message invalide"))
        
        session = conv_manager.get_session(user_id)
        conv_manager.reset_if_inactive(session)
        session['last_active'] = datetime.now()
        
        # Gestion des étapes de conversation
        if session['step'] == 'init':
            session['data']['name'] = message
            session['step'] = 'choose_domain'
            return str(MessagingResponse().message(MESSAGES['welcome']))
        
        elif session['step'] == 'choose_domain':
            for domain, config in DOMAINS.items():
                if message in config['keywords']:
                    session['data']['domain'] = domain
                    session['step'] = 'offer_resources'
                    resources = "\n".join(config['resources']['fr'])
                    return str(MessagingResponse().message(
                        MESSAGES['resources'].format(domain=domain, resources=resources)
                    ))
            return str(MessagingResponse().message(MESSAGES['welcome']))
        
        elif session['step'] == 'offer_resources':
            if message in ['oui', 'yes']:
                session['step'] = 'choose_contact'
                return str(MessagingResponse().message(MESSAGES['contact_options']))
            session['step'] = 'init'
            return str(MessagingResponse().message(MESSAGES['welcome']))
        
        elif session['step'] == 'choose_contact':
            domain_data = DOMAINS.get(session['data']['domain'], {})
            contact_msg = f"Nouveau contact: {session['data']['name']}"
            
            if message in ['1', 'message']:
                success = twilio_service.send_whatsapp(
                    domain_data.get('expert_whatsapp'), contact_msg)
                response = MESSAGES['confirmations']['message'] if success else MESSAGES['error']
            
            elif message in ['2', 'appel']:
                success = twilio_service.make_call(
                    domain_data.get('expert_phone'), contact_msg)
                response = MESSAGES['confirmations']['call'] if success else MESSAGES['error']
            
            elif message in ['3', 'both']:
                msg_success = twilio_service.send_whatsapp(
                    domain_data.get('expert_whatsapp'), contact_msg)
                call_success = twilio_service.make_call(
                    domain_data.get('expert_phone'), contact_msg)
                response = MESSAGES['confirmations']['both'] if (msg_success and call_success) else MESSAGES['error']
            
            else:
                response = MESSAGES['error']
            
            session['step'] = 'init'
            return str(MessagingResponse().message(response))
        
        return str(MessagingResponse().message(MESSAGES['error']))
    
    except Exception as e:
        logger.error(f"Erreur webhook: {e}")
        return str(MessagingResponse().message("Erreur serveur"))

@app.route('/voice', methods=['POST'])
def voice_webhook():
    response = VoiceResponse()
    response.say("Service vocal non configuré", voice='woman', language='fr-FR')
    return str(response), 200, {'Content-Type': 'text/xml'}

if __name__ == '__main__':
    required_vars = ['TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_PHONE_NUMBER']
    if missing := [var for var in required_vars if not os.getenv(var)]:
        logger.error(f"Variables manquantes: {missing}")
        exit(1)
    
    logger.info("🚀 Lancement de l'application...")
    app.run(host='0.0.0.0', port=5000, debug=True)