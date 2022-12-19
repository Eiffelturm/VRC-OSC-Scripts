"""
VRCSubs - A script to create "subtitles" for yourself using the VRChat textbox!
(c) 2022 CyberKitsune, Eiffelturm & other contributors.
"""

import queue, threading, datetime, os, time, textwrap
import speech_recognition as sr
import Translators

from speech_recognition import UnknownValueError, WaitTimeoutError, AudioData
from pythonosc import udp_client
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
from yaml import load
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader


config = {'FollowMicMute': True, 'CapturedLanguage': "en-US", 'EnableTranslation': False, 'TranslateMethod': "Google", 'TranslateToken': "", "TranslateTo": "en-US", 'AllowOSCControl': True, 'Pause': False, 'TranslateInterumResults': True, 'OSCControlPort': 9001}
state = {'selfMuted': False}
state_lock = threading.Lock()

r = sr.Recognizer()
audio_queue = queue.Queue()

def conv_langcode(langcode) -> str:
    langsplit = langcode.split('-')[0]
    if langsplit == "zh":
        if langcode == "zh-CN":
            return langcode
        return "zh-TW"
    if langsplit == "yue":
        return "zh-TW"

    return langsplit

'''
STATE MANAGEMENT
This should be thread safe
'''
def get_state(key):
    global state, state_lock
    state_lock.acquire()
    result = None
    if key in state:
        result = state[key]
    state_lock.release()
    return result

def set_state(key, value):
    global state, state_lock
    state_lock.acquire()
    state[key] = value
    state_lock.release()

'''
SOUND PROCESSING THREAD
'''
def process_sound():
    global audio_queue, r, config
    client = udp_client.SimpleUDPClient("127.0.0.1", 9000)
    current_text = ""
    last_text = ""
    last_disp_time = datetime.datetime.now()
    translator = None
    
    if config['ExtraLogging']:
        print("[ProcessThread] Starting audio processing!")
    while True:
        if config['EnableTranslation'] and translator is None:
            tclass = None
            if config['ExtraLogging']:
                print("[ProcessThread] Enabling Translation!")
            if config['TranslateMethod'] in Translators.registered_translators:
                tclass = Translators.registered_translators[config['TranslateMethod']]
            targs = config['TranslateToken']

            try:
                translator = tclass(targs)
            except Exception as e:
                if config['ExtraLogging']:
                    print("[ProcessThread] Unable to initalize translator!", e)
            
        
        ad, final = audio_queue.get()

        if config['FollowMicMute'] and get_state("selfMuted"):
            continue

        if config['Pause']:
            continue

        if config['ShowChatbox']:
            client.send_message("/chatbox/typing", (not final))

        if config['EnableTranslation'] and not config['TranslateInterumResults'] and not final:
            continue

        text = None
        
        time_now = datetime.datetime.now()
        difference = time_now - last_disp_time
        if difference.total_seconds() < 1 and not final:
            continue
        
        try:
            #client.send_message("/chatbox/typing", True)
            text = r.recognize_google(ad, language=config['CapturedLanguage'])
        except UnknownValueError:
            #client.send_message("/chatbox/typing", False)
            continue
        except TimeoutError:
            #client.send_message("/chatbox/typing", False)
            print("[ProcessThread] Timeout Error when recognizing speech!")
            continue
        except Exception as e:
            print("[ProcessThread] Exception!", e)
            #client.send_message("/chatbox/typing", False)
            continue

        current_text = text

        if last_text == current_text:
            continue

        last_text = current_text

        diff_in_milliseconds = difference.total_seconds() * 1000
        if diff_in_milliseconds < 1500:
            ms_to_sleep = 1500 - diff_in_milliseconds
            if config['EnableRateLimit'] and config['ExtraLogging']:
                print("[ProcessThread] Sending too many messages! Delaying by", (ms_to_sleep / 1000.0), "sec to not hit rate limit!")
            time.sleep(ms_to_sleep / 1000.0)

        if config['EnableTranslation'] and translator is not None and config['CapturedLanguage'] != config['TranslateTo']:
            try:
                origin = current_text
                translation = translator.translate(source_lang=config['CapturedLanguage'], target_lang=config['TranslateTo'], text=current_text)

                if config['EnableSecondTranslation'] and config['TranslateTo'] != config['TranslateToSecond']:
                    second_translation = translator.translate(source_lang=config['CapturedLanguage'], target_lang=config['TranslateToSecond'], text=current_text)
                    current_text = config['SecondTranslationFormat'].format(translation=translation, second_translation=second_translation, translation_language=conv_langcode(config['TranslateTo']).upper(), second_translation_language=conv_langcode(config['TranslateToSecond']).upper(), captured_language=config['CapturedLanguage'])
                else:
                    current_text = config['TranslationFormat'].format(translation=translation, translation_language=conv_langcode(config['TranslateTo']).upper(), captured_language=config['CapturedLanguage'])

                if config['ExtraLogging']:
                    # print(f"[ProcessThread] Recognized: {translation} ({origin} [%s->%s])" % (config['CapturedLanguage'], config['TranslateTo']))
                    print(f"[ProcessThread] Recognized: {translation} ({origin})")
                else:
                    # print("[Translation]", translation)
                    if config['EnableSecondTranslation'] and config['TranslateTo'] != config['TranslateToSecond']:
                        print(config['ShortSecondTranslationFormat'].format(translation=translation, second_translation=second_translation, translation_language=conv_langcode(config['TranslateTo']).upper(), second_translation_language=conv_langcode(config['TranslateToSecond']).upper(), captured_language=config['CapturedLanguage']))
                    else:
                        print(config['ShortTranslationFormat'].format(translation=translation, translation_language=conv_langcode(config['TranslateTo']).upper(), captured_language=config['CapturedLanguage']))
            
            except Exception as e:
                print("[ProcessThread] Translating ran into an error!", e)
        else:
            print("[ProcessThread] Recognized:", current_text)

        if config['ShowChatbox']:
            if len(current_text) > 144:
                current_text = textwrap.wrap(current_text, width=144)[-1]

            last_disp_time = datetime.datetime.now()

            client.send_message("/chatbox/input", [current_text, True])

'''
AUDIO COLLECTION THREAD
'''
def collect_audio():
    global audio_queue, r, config
    mic = sr.Microphone()
    if config['ExtraLogging']:
        print("[AudioThread] Starting audio collection!")
        did = mic.get_pyaudio().PyAudio().get_default_input_device_info()
        print("[AudioThread] Using", did.get('name'), "as Microphone!")
    with mic as source:
        audio_buf = None
        buf_size = 0
        while True:
            audio = None
            try:
                audio = r.listen(source, phrase_time_limit=1, timeout=0.1)
            except WaitTimeoutError:
                if audio_buf is not None:
                    audio_queue.put((audio_buf, True))
                    audio_buf = None
                    buf_size = 0
                continue

            if audio is not None:
                if audio_buf is None:
                    audio_buf = audio
                else:
                    buf_size += 1
                    if buf_size > 10:
                        audio_buf = audio
                        buf_size = 0
                    else:
                        audio_buf = AudioData(audio_buf.frame_data + audio.frame_data, audio.sample_rate, audio.sample_width)
                    
                audio_queue.put((audio_buf, False))
                   

'''
OSC BLOCK
TODO: This maybe should be bundled into a class
'''
class OSCServer():
    def __init__(self):
        global config
        self.dispatcher = Dispatcher()
        self.dispatcher.set_default_handler(self._def_osc_dispatch)
        self.dispatcher.map("/avatar/parameters/MuteSelf", self._osc_muteself)

        for key in config.keys():
            if key in ['CapturedLanguage', 'TranslateTo', 'TranslateToSecond']:
                self.dispatcher.map("/avatar/parameters/vrcsub-%s" % key, self._osc_updatelang)
            else:
                self.dispatcher.map("/avatar/parameters/vrcsub-%s" % key, self._osc_updateconf)

        self.server = BlockingOSCUDPServer(("127.0.0.1", config['OSCControlPort']), self.dispatcher)
        self.server_thread = threading.Thread(target=self._process_osc)

    def launch(self):
        self.server_thread.start()

    def shutdown(self):
        self.server.shutdown()
        self.server_thread.join()

    def _osc_muteself(self, address: str, *args):
        if config['ExtraLogging']:
            print("[OSCThread] Mute is now", args[0])
        set_state("selfMuted", args[0])

    def _osc_updateconf(self, address: str, *args):
        key = address.split("vrcsub-")[1]
        if config['ExtraLogging']:
            print("[OSCThread]", key, "is now", args[0])
        config[key] = args[0]

    def _osc_updatelang(self, address: str, language_int: int):
        key = address.split("vrcsub-")[1]
        if config['ExtraLogging']:
            print("[OSCThread]", key, "is now", config['LanguageMapping'][language_int])
        config[key] = config['LanguageMapping'][language_int]

    def _def_osc_dispatch(self, address, *args):
        pass
        #print(f"{address}: {args}")

    def _process_osc(self):
        if config['ExtraLogging']:
            print("[OSCThread] Launching OSC server thread!")
        self.server.serve_forever()


'''
MAIN ROUTINE
'''
def main():
    global config
    # Load config
    cfgfile = f"{os.path.dirname(os.path.realpath(__file__))}\Tools\Config.yml"
    if os.path.exists(cfgfile):
        print("[VRCSubs] Loading config from", cfgfile)
        new_config = None
        with open(cfgfile, 'r') as f:
            new_config = load(f, Loader=Loader)
        if new_config is not None:
            for key in new_config:
                config[key] = new_config[key]

    # Start threads
    pst = threading.Thread(target=process_sound)
    pst.start()

    cat = threading.Thread(target=collect_audio)
    cat.start()
    
    osc = None
    launchOSC = False

    if config['ExtraLogging']:
        if config['FollowMicMute']:
            print("[VRCSubs] FollowMicMute is enabled in the config, speech recognition will pause when your mic is muted in-game!")
        else:
            print("[VRCSubs] FollowMicMute is NOT enabled in the config, speech recognition will work even while muted in-game!")

        if config['AllowOSCControl']:
            print("[VRCSubs] AllowOSCControl is enabled in the config, will listen for OSC controls!")


        if config['TranslateTo'] == config['CapturedLanguage'] and config['EnableTranslation']:
            print("[VRCSubs] TranslateTo is set to the same language as CapturedLanguage, translation is disabled!")
        elif config['EnableTranslation']:
            print(f"[VRCSubs] Translation is enabled. Recognized text will be translated from {conv_langcode(config['CapturedLanguage']).upper()} to {conv_langcode(config['TranslateTo']).upper()}.")

    if config['AllowOSCControl'] or config['FollowMicMute']:
        launchOSC = True

    if launchOSC:
        osc = OSCServer()
        osc.launch()

    pst.join()
    cat.join()
    
    if osc is not None:
        osc.shutdown()

if __name__ == "__main__":
    main()