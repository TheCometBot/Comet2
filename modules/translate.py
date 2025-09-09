from googletrans import Translator

def translate(text, dest='en'):
    translator = Translator()
    try:
        translated = translator.translate(text, dest=dest)
        return translated.text
    except Exception as e:
        print(f"Translation error: {e}")
        return text