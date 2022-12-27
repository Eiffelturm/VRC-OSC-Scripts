"""
VRCClock
(c) 2022 Eiffelturm
"""

import time, os, threading

from yaml import load
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

# OSC
import threading

from pythonosc import udp_client
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer

os.system("title " + os.path.basename(__file__).replace(".py", ""))

config = {}

print("[VRCClock ©️ Eiffelturm] VRCClock is now running")
print("Find more scripts and updates at https://cloud.gamingecke.space/s/OSCScripts | News and changelogs at https://social.gamingecke.space/@eiffelturm")

'''
MAIN ROUTINE
'''
def sending():
    client = udp_client.SimpleUDPClient("127.0.0.1", 9000)
    while True:
        if config['Pause']:
            continue

        current_time = time.strftime((config['ClockFormat']), time.localtime())
        current_time = current_time.format(timezone = time.tzname[1])
            
        print("[VRCClock]", current_time)
        client.send_message("/chatbox/input", (current_time, True))
        # client.send_message("/chatbox/input", ("*macht sich Frühstück*", True))
        time.sleep(1.5)

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
        print("[VRCClock] Loading config from", cfgfile)
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