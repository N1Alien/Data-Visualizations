import streamlit as st
import ollama
import speech_recognition as sr
import os
import tempfile
from gtts import gTTS
from deep_translator import GoogleTranslator
import time
import re

# --- Konfiguracja strony ---
st.set_page_config(page_title="Lokalny Nauczyciel", page_icon="🇪🇸", layout="centered")
st.title("🇪🇸 Głosowy Trener Hiszpańskiego")

def transcribe_audio(audio_file_buffer):
    recognizer = sr.Recognizer()
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
            temp_audio.write(audio_file_buffer.read())
            temp_audio_path = temp_audio.name
            
        with sr.AudioFile(temp_audio_path) as source:
            audio_data = recognizer.record(source)
            
        if os.path.exists(temp_audio_path):
            os.unlink(temp_audio_path)
            
        return recognizer.recognize_google(audio_data, language="es-ES")
    except Exception as e:
        return f"[Błąd przetwarzania mowy: {e}]"

def generate_audio(text_to_speak):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            temp_filename = fp.name
            tts = gTTS(text=text_to_speak, lang='es', slow=False)
            tts.save(temp_filename)
            
        with open(temp_filename, "rb") as f:
            audio_bytes = f.read()
            
        if os.path.exists(temp_filename):
            os.unlink(temp_filename)
        return audio_bytes
    except Exception as e:
        return None



# --- Inicjalizacja stanu ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "input_counter" not in st.session_state:
    st.session_state.input_counter = 0

# Panel boczny
with st.sidebar:
    st.header("Ustawienia")
    if st.button("Zresetuj czat"):
        st.session_state.messages = []
        st.session_state.input_counter += 1
        st.rerun()

# --- RENDEROWANIE HISTORII CZATU ---
# To miejsce odpowiada za to, by tłumaczenie i audio NIE znikały z ekranu
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg["role"] == "assistant" and msg.get("translation"):
            st.info(f"🇬🇧 **English:** {msg['translation']}")
        if msg.get("audio"):
            st.audio(msg["audio"], format="audio/mp3", autoplay=msg.get("autoplay", False))

# --- PANEL WEJŚCIOWY ---
st.write("---")
st.subheader("🗣️ Rozmowa Głosowa")

# Dynamiczny klucz (audio_key) czyści mikrofon po każdym wysłaniu, zapobiegając zawieszeniu
audio_key = f"audio_input_{st.session_state.input_counter}"
audio_file = st.audio_input("Kliknij mikrofon, nagraj mowę po hiszpańsku i zatrzymaj:", key=audio_key)

# --- PROCESOWANIE LOGIKI ---
if audio_file:
    with st.spinner("Przetwarzanie Twojego głosu na tekst..."):
        extracted_text = transcribe_audio(audio_file)
        
    if not extracted_text.startswith("[Błąd"):
        # Wyciszamy automatyczne odtwarzanie dźwięku dla wszystkich starych wiadomości
        for msg in st.session_state.messages:
            if "autoplay" in msg:
                msg["autoplay"] = False
                
        # 1. Zapis głosu użytkownika
        st.session_state.messages.append({"role": "user", "content": extracted_text, "translation": None, "audio": None})
        
        # 2. Przygotowanie promptu dla Ollama
        system_prompt = {
            "role": "system",
            "content": "Eres un profesor de español nativo. Habla SIEMPRE en español de forma clara, corrige amablemente los errores del usuario y fomenta la conversación. Responde de forma muy concisa."
        }
        ollama_messages = [system_prompt] + [
            {"role": m["role"], "content": m["content"]} for m in st.session_state.messages
        ]
        
        # 3. Generowanie odpowiedzi asystenta (Ollama + Tłumacz Google + gTTS)
        spanish_response = None
        english_translation = None
        audio_data = None
        
        with st.spinner("Nauczyciel myśli..."):
            try:
                res = ollama.chat(model='llama3', messages=ollama_messages)
                spanish_response = res['message']['content'].strip()
            except Exception as ollama_err:
                st.error(f"Błąd Ollama: {ollama_err}")
                spanish_response = None
        
        if spanish_response and not spanish_response.startswith("["):
            with st.spinner("Tłumaczenie na angielski..."):
                try:
                    english_translation = GoogleTranslator(source='es', target='en').translate(spanish_response)
                except Exception as trans_err:
                    st.warning(f"Problem z tłumaczeniem: {trans_err}")
                    english_translation = "(Translation unavailable)"
            
            with st.spinner("Generowanie głosu..."):
                try:
                    audio_data = generate_audio(spanish_response)
                except Exception as audio_err:
                    st.warning(f"Problem z generowaniem audio: {audio_err}")
                    audio_data = None
            
            # Wyświetlamy wszystko na żywo na ekranie
            with st.chat_message("assistant"):
                st.write(spanish_response)
                if english_translation:
                    st.info(f"🇬🇧 **English:** {english_translation}")
                if audio_data:
                    st.audio(audio_data, format="audio/mp3", autoplay=True)
            
            # 4. Zapis kompletnego zestawu do st.session_state (aby pętla historii to pamiętała)
            st.session_state.messages.append({
                "role": "assistant",
                "content": spanish_response,
                "translation": english_translation,
                "audio": audio_data,
                "autoplay": False
            })
        
        # 5. Odświeżenie widżetu audio i przeładowanie strony
        st.session_state.input_counter += 1
        st.rerun()
    else:
        st.error(f"Nie udało się rozpoznać mowy: {extracted_text}")
