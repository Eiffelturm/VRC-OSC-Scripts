"""
VRCSystemStats
(c) 2022 Eiffelturm
"""

import time, os
from pythonosc import udp_client

from yaml import load
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

import psutil
import gpustat

# OSC
import threading

from pythonosc import udp_client
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer

os.system("title " + os.path.basename(__file__).replace(".py", ""))

config = {}

print("[VRCSystemStats ©️ Eiffelturm] VRCSystemStats is now running")
print("Find more scripts and updates at https://cloud.gamingecke.space/s/OSCScripts | News and changelogs at https://social.gamingecke.space/@eiffelturm")

def sending():
    client = udp_client.SimpleUDPClient("127.0.0.1", 9000)
    while True:
        if config['Pause']:
            continue

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
        
        print("[VRCSystemStats]", system_stats)
        client.send_message("/chatbox/input", (system_stats, True))
        time.sleep(1.5) # 1.5 seconds delay to update without flashing

class OSCServer():
    def __init__(self):
        global config
        self.dispatcher = Dispatcher()
        self.dispatcher.set_default_handler(self._def_osc_dispatch)

        for key in config.keys():
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
        print("[VRCSystemStats] Loading config from", cfgfile)
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