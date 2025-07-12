from typing import Optional, Type
import requests
import time
import json
import hydra
import os
from omegaconf import DictConfig, OmegaConf, ListConfig
import sacn
from math import ceil, floor
from concurrent.futures import ThreadPoolExecutor
from omegaconf_helpers import omegaconf_universal_load, create_patch_from_omegaconf, tidy_yaml
# from scripts.local_env import DEFAULT_OMAEGACONFS, FS_DUMP_DIR, DEFAULT_PRESETS, OMEGACONF_DUMP_DIR


try:
    import tdutils as tdu
    dbg = tdu.debug.debug
except (ModuleNotFoundError, AttributeError):
    import logging
    logger = logging.getLogger(__name__)
    dbg = logger.debug

file_path = os.path.dirname(os.path.realpath(__file__))




# https://github.com/Aircoookie/WLED/wiki/HTTP-request-API
# https://github.com/Aircoookie/WLED/wiki/JSON-API
# https://github.com/Aircoookie/WLED/wiki/Sync-WLED-devices-(UDP-Notifier)
# https://github.com/Aircoookie/WLED/blob/master/wled00/udp.cpp#L11

import socket
sock = None


class WledDMX:
    LEDS_PER_UNIVERSE = 170 # 512//3
    SEND_OUT_INTERVAL = 0.3
    def __init__(self, wled):
        self.wled = wled
        self.sender = None

    def start(self):
        WledDMX.set_send_interval(WledDMX.SEND_OUT_INTERVAL)
        if self.sender is None:
            self.sender = sacn.sACNsender()
        strips = self.wled.cfg["hw"]["led"]["ins"]
        # assert len(strips) == 1 # Assertion is no longer valid and needed
        self.n_leds = sum(strip["len"] for strip in strips)
        self.n_universes = ceil(self.n_leds / WledDMX.LEDS_PER_UNIVERSE)
        for i in range(1, self.n_universes+1):
            self.sender.activate_output(i)
        for sender in self.get_senders():
            sender.destination = self.wled.ip
        self.sender.start()

    def get_senders(self):
        return [self.sender[i] for i in self.sender.get_active_outputs()]

    def set_data(self, data):
        assert len(data) == 3 * self.n_leds
        for i, sender in enumerate(self.get_senders()):
            sender.dmx_data = data[i*3*WledDMX.LEDS_PER_UNIVERSE : (i+1)*3*WledDMX.LEDS_PER_UNIVERSE]
    
    def stop(self):
        if self.sender is not None: self.sender.stop()
        self.sender = None

    def __del__(self):
        self.stop()

    @classmethod
    def set_send_interval(cls, interval_s=1.0):
        sacn.sending.sender_handler.SEND_OUT_INTERVAL = interval_s



class Wled:
    _tcp_state_post_timeout: float = 2. # seconds
    _tcp_fs_list_timeout: float = 2. # seconds


    def __init__(self, ip):
        self.ip = ip
        self.udp_port = None
        self.name = None
        self.current_json = None
        self.cfg = None
        self.presets = None
        self.dmx = WledDMX(self)
    
    
    def __str__(self):
        return f"WLED '{self.name}' at {self.ip}"

    def __repr__(self) -> str:
        return self.__str__()

    def print(self, intro=""):
        print(f"{intro}{self}", flush=True)

    def log(self, intro=""):
        logger.info(f"{intro}{self}")

    @classmethod
    def from_udp_multicast(cls, row):
        wled =  cls(ip=row[0].val)
        wled.udp_port = int(row[1].val)
        wled.name = row[2].val
        return wled

    @classmethod
    def from_one_ip(cls, ip, name=None, cache_fs=True):
        w = Wled(ip)
        w.name = name
        if not name or cache_fs:
            w.cache_fs()
            w.name = w.cfg["id"]["name"]
        return w

    ## Endpoints 
    def http_endpoint(self):
        return f"http://{self.ip}/win"

    def json_endpoint(self):
        return f"http://{self.ip}/json"

    def json_state_endpoint(self):
        return f"http://{self.ip}/json/state"

    def json_info_endpoint(self):
        return f"http://{self.ip}/json/info"
    
    def json_si_endpoint(self):
        return f"http://{self.ip}/json/si"

    def edit_endpoint(self):
        return f"http://{self.ip}/edit"

    ## Request helpers
    def http_request_multi(self, params):
        req_str = self.http_endpoint()
        req_str += "".join([f"&{p[0]}={p[1]}" for p in params])
        # tdu.debug.debug(req_str)
        return requests.get(req_str)

    def http_request_one(self, param, value):
        return self.http_request_multi([(param, value)])

    def _send_udp(self, msg):
        # tdu.debug.debug(f"udp {self.udp_port}, msg: {msg}")
        global sock
        if sock is None:
            sock = socket.socket(socket.AF_INET, # Internet
                                 socket.SOCK_DGRAM) # UDP
        sock.sendto(msg, (self.ip, self.udp_port))

    def send_udp_sync_v5(self, brightness=255, col=[255,0,0], fx=0, fx_speed=10, fx_intensity=255, col_sec=[0, 255,0], transition_delay=0, palette=0):
        p = []
        # Byte Index	Var Name	Description	Notifier Version
        # https://github.com/Aircoookie/WLED/blob/master/wled00/udp.cpp#L11
        # 0	-	Packet Purpose Byte*	0
        p += [0]
        # 1	callMode	Packet Reason**	0
        p += [1]
        # 2	bri	Master Brightness	0
        p += [brightness]
        # 3	col[0]	Primary Red Value	0
        # 4	col[1]	Primary Green Value	0
        # 5	col[2]	Primary Blue Value	0
        p += col
        # 6	nightlightActive	Nightlight running?	0
        # 7	nightlightDelayMins	Nightlight Time	0
        p += [0, 0]
        # 8	effectCurrent	Effect Index	0
        # 9	effectSpeed	Effect Speed	0
        # https://github.com/Aircoookie/WLED/blob/master/wled00/FX.h#L121
        # https://github.com/Aircoookie/WLED/blob/master/wled00/FX.h#L931
        p += [fx, fx_speed]
        # 10	white	Primary White Value	1
        p += [255]
        # 11	-	Version Byte***	1
        p += [5]
        # 12	colSec[0]	Secondary Red Value	2
        # 13	colSec[1]	Secondary Green Value	2
        # 14	colSec[2]	Secondary Blue Value	2
        p += col_sec
        # 15	whiteSec	Secondary White Value	2
        p += [255]
        # 16	effectIntensity	Effect Intensity	3
        p += [fx_intensity]
        # 17	transitionDelay	Transition Duration Upper	4
        # 18	transitionDelay	Transition Duration Lower	4
        p += [transition_delay<<8, transition_delay%(1<<8)]
        # 19	effectPalette	FastLED palette	5
        p += [palette]
        # 20-23	-	Zeros	-
        p += [0]*4
        p = bytes(p)
        self._send_udp(p)

    def send_udp_sync_v9(self, brightness=255, col=[255,0,0, 0], fx=0, fx_speed=10, fx_intensity=255, transition_delay=1000, palette=0, 
            nightlightActive=0, nightlightDelayMins=60,
            secondary_color=[0, 255, 0, 0], tertiary_color=[0, 0, 255, 0],
            follow_up=False, sync_groups={1}, timebase_shift=0):
        udpOut = [0] * 37
        callMode = 1 # CALL_MODE_DIRECT_CHANGE
        bri = brightness
        col += [0] * (4 - len(col))
        effectCurrent = fx
        effectSpeed = fx_speed
        colSec = secondary_color + ([0] * (4 - len(secondary_color)))
        effectIntensity = fx_intensity
        transitionDelay = int(transition_delay) # in milliseconds
        effectPalette = palette
        tertiary_color += ([0] * (4 - len(tertiary_color)))
        colTer = 0
        colTer += (tertiary_color[0] & 0xFF) << 16
        colTer += (tertiary_color[1] & 0xFF) << 8
        colTer += (tertiary_color[2] & 0xFF) << 0
        colTer += (tertiary_color[3] & 0xFF) << 24
        followUp = follow_up
        # timebase is the base for calculating all the times in the effects, in ms
        # see https://github.com/Aircoookie/WLED/blob/v0.13.0-b5/wled00/FX_fcn.cpp#L119
        # https://github.com/Aircoookie/WLED/blob/v0.13.0-b5/wled00/src/dependencies/toki/Toki.h#L31

        current_time = time.time()
        t = floor(current_time*1000 + timebase_shift) # just millis
        unix = floor(current_time)
        toki_getTimeSource = 160 
        ms = floor((current_time % 1) * 1000)
        syncGroups = 0
        for g in sync_groups:
            syncGroups += 1 << (int(g)-1)

        # Copy below from
        # C:\Users\okdim\YandexDisk\coding_leisure\Arduino\WLED\wled00\udp.cpp:L7
        udpOut[0] = 0; # //0: wled notifier protocol 1: WARLS protocol
        udpOut[1] = callMode;
        udpOut[2] = bri;
        udpOut[3] = col[0];
        udpOut[4] = col[1];
        udpOut[5] = col[2];
        udpOut[6] = nightlightActive;
        udpOut[7] = nightlightDelayMins;
        udpOut[8] = effectCurrent;
        udpOut[9] = effectSpeed;
        udpOut[10] = col[3];
        # //compatibilityVersionByte: 
        # //0: old 1: supports white 2: supports secondary color
        # //3: supports FX intensity, 24 byte packet 4: supports transitionDelay 5: sup palette
        # //6: supports timebase syncing, 29 byte packet 7: supports tertiary color 8: supports sys time sync, 36 byte packet
        # //9: supports sync groups, 37 byte packet
        udpOut[11] = 9; 
        udpOut[12] = colSec[0];
        udpOut[13] = colSec[1];
        udpOut[14] = colSec[2];
        udpOut[15] = colSec[3];
        udpOut[16] = effectIntensity;
        udpOut[17] = (transitionDelay >> 0) & 0xFF;
        udpOut[18] = (transitionDelay >> 8) & 0xFF;
        udpOut[19] = effectPalette;
        # uint32_t colTer = strip.getSegment(strip.getMainSegmentId()).colors[2];
        udpOut[20] = (colTer >> 16) & 0xFF;
        udpOut[21] = (colTer >>  8) & 0xFF;
        udpOut[22] = (colTer >>  0) & 0xFF;
        udpOut[23] = (colTer >> 24) & 0xFF;
        
        udpOut[24] = followUp;
        # uint32_t t = millis() + strip.timebase_shift;
        udpOut[25] = (t >> 24) & 0xFF;
        udpOut[26] = (t >> 16) & 0xFF;
        udpOut[27] = (t >>  8) & 0xFF;
        udpOut[28] = (t >>  0) & 0xFF;

        # //sync system time
        # udpOut[29] = toki.getTimeSource();
        udpOut[29] = toki_getTimeSource
        # Toki::Time tm = toki.getTime();
        # uint32_t unix = tm.sec;
        udpOut[30] = (unix >> 24) & 0xFF;
        udpOut[31] = (unix >> 16) & 0xFF;
        udpOut[32] = (unix >>  8) & 0xFF;
        udpOut[33] = (unix >>  0) & 0xFF;
        # uint16_t ms = tm.ms;
        udpOut[34] = (ms >> 8) & 0xFF;
        udpOut[35] = (ms >> 0) & 0xFF;

        # //sync groups
        udpOut[36] = syncGroups;
        udpOut = bytes(udpOut)
        self._send_udp(udpOut)

    def send_udp_sync(self, brightness=255, col=[255,0,0, 0], fx=0, fx_speed=10, fx_intensity=255, transition_delay=1000, palette=0, 
            nightlightActive=0, nightlightDelayMins=60,
            secondary_color=[0, 255, 0, 0], tertiary_color=[0, 0, 255, 0],
            follow_up=False, sync_groups={1}, timebase_shift=0):
        self.send_udp_sync_v9(brightness=brightness, col=col, fx=fx, fx_speed=fx_speed, fx_intensity=fx_intensity,
                transition_delay=transition_delay, palette=palette,
                nightlightActive=nightlightActive, nightlightDelayMins=nightlightDelayMins,
                secondary_color=secondary_color, tertiary_color=tertiary_color,
                follow_up=follow_up, sync_groups=sync_groups, timebase_shift=timebase_shift)

    @classmethod
    def parse_udp_sync(cls, bts): # this hasa to be a classmethod, because the sync can come from any of the Wleds
        udp_in = list(bts)
        if udp_in[0] == 0:
            version = udp_in[11]
            if (version >= 9):
                return cls.parse_udp_sync_v9(bts)
            else:
                logger.exception(f"Recieved a WLED UDP notification with version {version} < 9: {udp_in}")
                return {}
        elif udp_in[0] == 255:
            return cls.parse_udp_sys_info(bts)
        else:
            logger.exception(f"Recieved a realtime protocol notification, skipping: {udp_in}")
            return {}

    @classmethod
    def parse_udp_sync_v9(cls, bts): # this hasa to be a classmethod, because the sync can come from any of the Wleds
        udp_in = list(bts)
        if (len(udp_in) < 37):
            logger.exception(f"Recieved a short WLED UDP notification ({len(udp_in)} < 37) : {udp_in}")
            return {}

        # Prepare the variables
        col = [0]*4
        colSec = [0]*4
        msg_type = "udp_sync"

        # Copy below from
        # C:\Users\okdim\YandexDisk\coding_leisure\Arduino\WLED\wled00\udp.cpp:L7
        # then select, press Ctrl+H to Replace, then press the Find In Selection button
        #
        # udpOut\[(\d+)\] = (.*);
        # $2 = udp_in[$1]
        # 0 = udp_in[0] # //0: wled notifier protocol 1: WARLS protocol
        # and then modify to taste
        callMode = udp_in[1]
        bri = udp_in[2]
        col[0] = udp_in[3]
        col[1] = udp_in[4]
        col[2] = udp_in[5]
        nightlightActive = udp_in[6]
        nightlightDelayMins = udp_in[7]
        effectCurrent = udp_in[8]
        effectSpeed = udp_in[9]
        col[3] = udp_in[10]
        # //compatibilityVersionByte: 
        # //0: old 1: supports white 2: supports secondary color
        # //3: supports FX intensity, 24 byte packet 4: supports transitionDelay 5: sup palette
        # //6: supports timebase_shift syncing, 29 byte packet 7: supports tertiary color 8: supports sys time sync, 36 byte packet
        # //9: supports sync groups, 37 byte packet
        version = udp_in[11] 
        colSec[0] = udp_in[12]
        colSec[1] = udp_in[13]
        colSec[2] = udp_in[14]
        colSec[3] = udp_in[15]
        effectIntensity = udp_in[16]
        transitionDelay = (udp_in[17] & 0xFF) << 0
        transitionDelay += (udp_in[18] & 0xFF) << 8
        effectPalette = udp_in[19]
        # uint32_t colTer = strip.getSegment(strip.getMainSegmentId()).colors[2];
        colTer  = (udp_in[20] & 0xFF) << 16
        colTer += (udp_in[21] & 0xFF) << 8
        colTer += (udp_in[22] & 0xFF) << 0
        colTer += (udp_in[23] & 0xFF) << 24
        
        followUp = udp_in[24]
        # uint32_t t = millis() + strip.timebase_shift;
        t  = (udp_in[25] & 0xFF) << 24
        t += (udp_in[26] & 0xFF) << 16
        t += (udp_in[27] & 0xFF) << 8
        t += (udp_in[28] & 0xFF) << 0

        # //sync system time
        # toki.getTimeSource() = udp_in[29]
        toki_getTimeSource = udp_in[29]
        # Toki::Time tm = toki.getTime();
        # uint32_t unix = tm.sec;
        unix  = (udp_in[30] & 0xFF) << 24
        unix += (udp_in[31] & 0xFF) << 16
        unix += (udp_in[32] & 0xFF) << 8
        unix += (udp_in[33] & 0xFF) << 0
        # uint16_t ms = tm.ms;
        ms = (udp_in[34] & 0xFF) << 8
        ms += (udp_in[35] & 0xFF) << 0

        # //sync groups
        syncGroups = udp_in[36]

        # modify the needed
        return locals()

    @classmethod
    def parse_udp_sys_info(cls, bts): # this hasa to be a classmethod, because the sync can come from any of the Wleds
        # see https://github.com/Aircoookie/WLED/blob/7e1920dc4b871f442ea7de2889fd8ce8db63c088/wled00/udp.cpp#L481
        udp_in = list(bts)
        msg_type = "udp_sys_info"
        if (len(udp_in) < 44):
            logger.exception(f"Recieved a short udp_sys_info notification ({len(udp_in)} < 44) : {udp_in}")
            return {}
        if (udp_in[1] != 1):
            logger.exception(f"Recieved a strange udp_sys_info, skipping: {udp_in}")
            return {}
        ip = udp_in[2:6]
        name = bts[6:6+32].decode("utf-8").rstrip('\x00')
        #define NODE_TYPE_ID_UNDEFINED        0
        #define NODE_TYPE_ID_ESP8266         82
        #define NODE_TYPE_ID_ESP32           32
        node_type = "undefined"
        if udp_in[38] == 82:
            node_type = "esp8266"
        elif udp_in[38] == 32:
            node_type = "esp32"

        wled_id = udp_in[39]
        build  = (udp_in[40] & 0xFF) << 0
        build += (udp_in[41] & 0xFF) << 8
        build += (udp_in[42] & 0xFF) << 16
        build += (udp_in[43] & 0xFF) << 24

        return locals()




    # Json state requests
    def get_json(self):
        self.current_json = requests.get(self.json_endpoint()).json()
        return self.current_json

    def get_json_info(self):
        return requests.get(self.json_info_endpoint()).json()

    def get_json_state(self):
        return requests.get(self.json_state_endpoint()).json()

    def post_json_state(self, new_json={}):
        return requests.post(self.json_state_endpoint(), json=new_json, timeout=self._tcp_state_post_timeout)

    def post_json_info(self, new_json={}):
        return requests.post(self.json_info_endpoint(), json=new_json)

    # Json si
    def post_json_si(self, new_json={}):
        return requests.post(self.json_si_endpoint(), json=new_json, timeout=self._tcp_state_post_timeout)

    # FS helpers
    def get_fs_list(self):
        return requests.get(self.edit_endpoint() + "?list", timeout=self._tcp_fs_list_timeout).json()

    def get_fs_file(self, filename):
        return requests.get(self.edit_endpoint() + "?edit=" + filename)

    def upload_fs_file(self, filename, contents):
        return requests.post(self.edit_endpoint(), files={filename:contents})

    def _attr_name_from_filename(self, filename):
        if not filename.endswith(".json"): raise ValueError(f"filename {filename} in the FS does not end in json, but attr name creation requested")
        filename = filename.replace("/", "")
        return filename[:-5]

    def cache_fs(self):
        """Reads all the json files in the FS into the member dictionaries of this object with the name deduced from the filename"""
        for fp in self.get_fs_list():
            fn = fp["name"]
            if fn.endswith(".json"):
                self.__setattr__(self._attr_name_from_filename(fn), self.get_fs_file(fn).json())
        self.udp_port = self.cfg["if"]["sync"]["port0"]
        

    def get_cfg(self):
        self.cfg = self.get_fs_file("cfg.json").json()
        return self.cfg

    def get_presets(self):
        self.presets = self.get_fs_file("presets.json").json()
        return self.presets

    def upload_cfg(self):
        cfg_json = json.dumps(self.cfg, separators=(',', ':'))
        return self.upload_fs_file("cfg.json", cfg_json.encode("utf-8"))

    def upload_presets(self):
        cfg_json = json.dumps(self.presets, separators=(',', ':'))
        return self.upload_fs_file("presets.json", cfg_json.encode("utf-8"))
        
    
    # Higher level functions
    def get_nodes(self):
       return requests.get(self.json_endpoint() + "/nodes").json()["nodes"]

    def reset_timers_cfg(self):
        for t in self.cfg["timers"]["ins"]:
            t["en"] = 0

    def set_solid_color(self, r, g, b, via_http=False):
        if via_http:
            new_state = {
                "FX": 0,
                "R": r,
                "G": g,
                "B": b,
            }
            self.http_request_multi(new_state.items())
        else:
            self.send_udp_sync(fx=0, col=[r, g, b])

    def set_on_off(self, on=True, n_seg=1):
        new_state = {
                "seg": [{
                    "on": on
                }]*n_seg
            }
        self.post_json_state(new_state)

    def set_preset(self, ps=0, eff_intensity=None, eff_speed=None):
        new_state = {
            "ps": ps,
        }
        if eff_intensity is not None or eff_speed is not None:
            seg = {}
            if eff_intensity is not None: seg['ix'] = eff_intensity
            if eff_speed is not None: seg['sx'] = eff_speed
            new_state["seg"] = seg
            
        self.post_json_state(new_state)


    def set_playlist(self, pl=0):
        new_state = {
            "ps": pl, # Note you should always set the preset, not the playlist
        }            
        self.post_json_state(new_state)


    def set_effect(self, fx=0):
        new_state = {
            "FX": fx,
        }
        self.http_request_multi(new_state.items())

    def update_time(self):
        self.http_request_one("ST", int(time.time()))

    def reset(self):
        return requests.get(f"http://{self.ip}/reset").status_code

    def update_firmware(self, filename):
        if not os.path.isfile(filename):
            raise ValueError(f"The specified firmware file {filename} does not exist")
        with open(filename, "rb") as firmware:
            req = requests.post(f"http://{self.ip}/update", files={"update": firmware })
            logger.info(f"Done sending firmware: {self}")
            return req

    def set_random_seed(self, seed=42):
        return self.post_json_state({"random_seed": seed})

    def set_fake_NTP(self, time_source):
        return self.post_json_state({"time_source": time_source})


class Wleds:
    def __init__(self, wleds=[]):
        self.wleds = wleds
    
    @classmethod
    def from_udp_multicast_table(cls, box):
        return cls(wleds = list(Wled.from_udp_multicast(row) for row in box.rows()))

    @classmethod
    def from_one_node(cls, wled):
        wleds = [wled]
        for node in wled.get_nodes():
            try:
                w = Wled.from_one_ip(node["ip"], node["name"])
                wleds.append(w)
            except Exception as e:
                logger.warning(f"Error while initializing {e}")
        new_wleds = cls(wleds = wleds)
        new_wleds.sort()
        return new_wleds

    @classmethod
    def from_one_ip(cls, ip, cache_fs=True):
        w = Wled.from_one_ip(ip)      
        wleds =  Wleds.from_one_node(w)
        if cache_fs: wleds.cache_fs()
        return wleds

    # def cache_fs(self):
    #     with ThreadPoolExecutor() as ex:
    #         for w in self:
    #             ex.submit(w.cache_fs)

    # @classmethod
    # def to_omegaconf(self):
    #     pass

    def get_by_ip(self, ip) -> Optional[Type[Wled]]:
        wleds = list(wled for wled in self if wled.ip == ip)
        if len(wleds) == 1:
            return wleds[0]
        elif len(wleds) == 0:
            return None
        else:
            raise ValueError(f"More than one ({len(wleds)}) wled with IP {ip} found")

    def get_by_name(self, name) -> Optional[Type[Wled]]:
        wleds = list(wled for wled in self if wled.name == name)
        if len(wleds) == 1:
            return wleds[0]
        elif len(wleds) == 0:
            return None
        else:
            raise ValueError(f"More than one ({len(wleds)}) wled with name '{name}' found")

    def get_names(self):
        return list(wled.name for wled in self)

    def get_ips(self):
        return list(wled.ip for wled in self)

    def remove(self, wled):
        return self.wleds.remove(wled)

    def append(self, wled):
        return self.wleds.append(wled)

    def sort(self):
        self.wleds = list(sorted(self.wleds, key=lambda w: w.name))
        return self
    
    def filter(self, filter_lambda):
        wleds = list(filter(filter_lambda, self.wleds))
        return self.__class__(wleds)

    def __getitem__(self, item) -> Optional[Type[Wled]]:
        return self.get_by_name(item)

    def __iter__(self):
        return self.wleds.__iter__()
    
    def __len__(self):
        return self.wleds.__len__()
    
    def __getattr__(self, attr):
        if attr not in Wled.__dict__.keys():
            raise AttributeError(f"Neither '{self.__class__.__name__}' nor Wled object has no attribute '{attr}'")
        orig_fun = getattr(Wled, attr)
        def new_fun(*args, **kwargs):
            returns = []
            with ThreadPoolExecutor() as ex:
                for wled in self:
                    returns.append(ex.submit(orig_fun, wled, *args, **kwargs))
            return [r.result() for r in returns]
        return new_fun

    def reconfig_from_omegaconf(self, keep_presets=True):
        returns = []
        with ThreadPoolExecutor() as ex:
            for wled in self:
                returns.append(ex.submit(Wled.reconfig_from_omegaconf, wled, keep_presets=keep_presets))
        returns = [r.result() for r in returns]
        self.wleds = returns
        return self

    def __str__(self):
        return str(self.wleds)

    def __repr__(self) -> str:
        return self.__str__()
        
if __name__ == "__main__":
    print("No action defined yet.")

    
