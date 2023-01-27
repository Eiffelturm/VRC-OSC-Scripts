"""
VRCEverything
(c) 2022 Eiffelturm

VRCNowPlaying
(c) 2022 CyberKitsune & MatchaCat

VRCClock
(c) 2022 Eiffelturm

VRCSystemStats
(c) 2022 Eiffelturm
"""

import asyncio
import time, os
import traceback
from datetime import timedelta
from pythonosc import udp_client

from yaml import load
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

from winsdk.windows.media.control import \
    GlobalSystemMediaTransportControlsSessionManager as MediaManager
from winsdk.windows.media.control import \
    GlobalSystemMediaTransportControlsSessionPlaybackStatus

import psutil
import gpustat

# OSC
import threading

from pythonosc import udp_client
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer

os.system("title " + os.path.basename(__file__).replace(".py", ""))

class NoMediaRunningException(Exception):
    pass

config = {
    'EnableNowPlaying': True,
    'EnableClock': True,
    'EnableSystemStats': True,
    'DisplayFormat': "Now playing: {song_artist} - {song_title}{song_position}",
    'PausedFormat': 'Nothing playing',
    'ClockFormat': '{timezone}: %H:%M',
    'Delay': 5,
    'OverrideMusic': True,
    'OverrideMusicDelay': 2,
    'AFK': False
    }

last_displayed_song = ("","")

print("[VRCEverything ©️ Eiffelturm and others] VRCEverything is now running")
print("Find more scripts and updates at https://cloud.gamingecke.space/s/OSCScripts | News and changelogs at https://social.gamingecke.space/@eiffelturm")

async def get_media_info():
    sessions = await MediaManager.request_async()

    current_session = sessions.get_current_session()
    if current_session:  # there needs to be a media session running
        if True: # TODO: Media player selection
            info = await current_session.try_get_media_properties_async()

            # song_attr[0] != '_' ignores system attributes
            info_dict = {song_attr: info.__getattribute__(song_attr) for song_attr in dir(info) if song_attr[0] != '_'}

            # converts winrt vector to list
            info_dict['genres'] = list(info_dict['genres'])

            pbinfo = current_session.get_playback_info()

            info_dict['status'] = pbinfo.playback_status

            tlprops = current_session.get_timeline_properties()

            if tlprops.end_time != timedelta(0):
                info_dict['pos'] = tlprops.position
                info_dict['end'] = tlprops.end_time

            return info_dict
    else:
        raise NoMediaRunningException("No media source running.")

def get_td_string(td):
    seconds = abs(int(td.seconds))

    minutes, seconds = divmod(seconds, 60)
    return '%i:%02i' % (minutes, seconds)

# def replace_umlauts(text: str):
#     vowel_char_map = {ord('ä'):'ae', ord('ü'):'ue', ord('ö'):'oe', ord('ß'):'ss'}
#     return text.translate(vowel_char_map)

def sending():
    global config, last_displayed_song

    lastPaused = False
    client = udp_client.SimpleUDPClient("127.0.0.1", 9000)
    while True:
        if config['Pause']:
            continue

        if config['EnableNowPlaying'] and not (config['EnableWhenAFK'] and config['AFK']):
            for i in range(int(config['Delay'] * 100)):
                try:
                    current_media_info = asyncio.run(get_media_info()) # Fetches currently playing song for winsdk
                except NoMediaRunningException:
                    time.sleep(1.5)
                    continue
                except Exception as e:
                    print("!!!", e, traceback.format_exc())
                    time.sleep(1.5)
                    continue

                song_artist, song_title = (current_media_info['artist'], current_media_info['title'])

                song_position = ""

                if 'pos' in current_media_info:
                    song_position = " <%s / %s>" % (get_td_string(current_media_info['pos']), get_td_string(current_media_info['end']))

                current_song_string = config['MusicFormat'].format(song_artist=song_artist, song_title=song_title, song_position=song_position)

                if len(current_song_string) >= 144 :
                    current_song_string = current_song_string[:144]
                if current_media_info['status'] == GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING:
                    if last_displayed_song != (song_artist, song_title):
                        last_displayed_song = (song_artist, song_title)
                        print("[VRCNowPlaying]", current_song_string)
                    client.send_message("/chatbox/input", (current_song_string, True))
                    lastPaused = False
                    time.sleep(1.5) # 1.5 seconds delay to update without flashing
                
                elif current_media_info['status'] == GlobalSystemMediaTransportControlsSessionPlaybackStatus.PAUSED and not lastPaused:
                    # client.send_message("/chatbox/input", (config['PausedFormat'], True))
                    last_displayed_song = ("", "")
                    lastPaused = True

            if lastPaused is False and config['OverrideMusic'] is True:
                delay = int(config['OverrideMusicDelay'] * 100)
            else:
                delay = int(config['Delay'] * 100)

        # Clock
        
        if config['Pause']:
            print("Skipping")
            continue

        if config['EnableClock'] and not (config['EnableWhenAFK'] and config['AFK']):
            current_time = time.strftime((config['ClockFormat']), time.localtime())
            current_time = current_time.format(timezone = time.tzname[1])
                
            print("[VRCClock]", current_time)
            client.send_message("/chatbox/input", (current_time, True))
            time.sleep(delay)

        # System Stats

        if config['Pause']:
            continue

        statsDisplayed = False
        if config['EnableSystemStats'] and not (config['EnableWhenAFK'] and config['AFK']):
            for i in range(delay):
                if config['DisplayMaxCPUCore'] is True:
                    cpu = max(psutil.cpu_percent(percpu=True))
                else:
                    cpu = psutil.cpu_percent()

                ram = psutil.virtual_memory().percent

                if config['AMDMode'] is False:
                    
                    try:
                        gpu = gpustat.new_query().jsonify()['gpus'][0]
                    except FileNotFoundError:
                        print("[VRCSystemStats] NVML Error: If you have an AMD graphics card, enable AMDMode in the config.")
                    
                    gpu_name = ' '.join(gpu['name'].split(' ')[2:4])
                    temperature = gpu['temperature.gpu']
                    power = gpu['power.draw']
                    fans = gpu['fan.speed']

                    if fans is None:
                        fans = "incognito"
                    else:
                        fans = f"{fans}%"

                    system_stats = config['Format'].format(cpu=cpu, ram=ram, gpu_name=gpu_name, temperature=temperature, fans=fans, power=power)
                
                else:
                    system_stats = config['AMDFormat'].format(cpu=cpu, ram=ram)
                
                if statsDisplayed is False:
                    print("[VRCSystemStats]", system_stats)
                    statsDisplayed = True

                client.send_message("/chatbox/input", (system_stats, True))
                # time.sleep(1.5) # 1.5 seconds delay to update without flashing
                time.sleep(1.5)

        # Custom Status

        if config['Pause']:
            continue

        if config['EnableCustomStatus'] or (config['EnableWhenAFK'] and config['AFK']):
            print("[VRCCustomStatus]", config['CustomStatus'])
            client.send_message("/chatbox/input", (config['CustomStatus'], True))
            
            if (config['EnableWhenAFK'] and config['AFK']):
                time.sleep(config['Delay'] * 100)
            else:
                time.sleep(delay)

        # Earmuffs

        # if config['Pause']:
        #     continue

class OSCServer():
    def __init__(self):
        global config
        self.dispatcher = Dispatcher()
        self.dispatcher.set_default_handler(self._def_osc_dispatch)

        self.dispatcher.map("/avatar/parameters/AFK", self._osc_updateafk)
        self.dispatcher.map("/avatar/parameters/Earmuffs", self._osc_updateconf)

        for key in config.keys():
            if key == 'CustomStatus':
                self.dispatcher.map("/avatar/parameters/vrcosc-%s" % key, self._osc_updatestatus)
            else:
                self.dispatcher.map("/avatar/parameters/vrcosc-%s" % key, self._osc_updateconf)

        self.server = BlockingOSCUDPServer(("127.0.0.1", 9001), self.dispatcher)
        self.server_thread = threading.Thread(target=self._process_osc)

    def launch(self):
        self.server_thread.start()

    def shutdown(self):
        self.server.shutdown()
        self.server_thread.join()

    def _osc_updateconf(self, address: str, *args):
        key = address.split("vrcosc-")[1]
        print("[OSCThread]", key, "is now", args[0])
        config[key] = args[0]
    
    def _osc_updatestatus(self, address: str, status_int: int):
        key = address.split("vrcosc-")[1]
        print(f"[OSCThread] {key} is now '{config['CustomStatusMapping'][status_int]}'")
        config[key] = config['CustomStatusMapping'][status_int]

    def _osc_updateafk(self, address: str, afk_value: bool):
        if config['EnableWhenAFK'] is False:
            return

        if afk_value:
            print(f"[OSCThread] Now AFK, enabling VRCCustomStatus and disabling other modules")
        else:
            print(f"[OSCThread] No longer AFK, reverting to original settings")
        
        config['AFK'] = afk_value

    def _def_osc_dispatch(self, address, *args):
        pass
        #print(f"{address}: {args}")

    def _process_osc(self):
        print("[OSCThread] Launching OSC server thread!")
        self.server.serve_forever()

def main():
    global config
    # Load config
    cfgfile = f"{os.path.dirname(os.path.realpath(__file__))}\Tools\Config.yml"
    if os.path.exists(cfgfile):
        print("[VRCEverything] Loading config from", cfgfile)
        with open(cfgfile, 'r', encoding="UTF-8") as f:
            config = load(f, Loader=Loader)

    send_thread = threading.Thread(target=sending)
    send_thread.start()

    osc = OSCServer()
    osc.launch()

    send_thread.join()

    if osc is not None:
        osc.shutdown()

if __name__ == "__main__":
    main()