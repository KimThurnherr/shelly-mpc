import json
import os
import unittest

import httpx

os.environ.update({
    "SHELLY_CLOUD_SERVER": "shelly-00-eu.shelly.cloud",
    "SHELLY_CLOUD_AUTH_KEY": "testkey",
    "SHELLY_GATEWAYS": "Wohnung=http://192.0.2.10",
    "SHELLY_CLOUD_MIN_INTERVAL": "0",
})
import shelly_mcp as s  # noqa: E402

s.CLOUD_MIN_INTERVAL = 0


class Recorder:
    def __init__(self, handler):
        self.calls = []
        self.handler = handler

    def __call__(self, url, **kw):
        self.calls.append((url, kw))
        status, body = self.handler(url, kw)
        return httpx.Response(status, json=body, request=httpx.Request("POST", url))


GW_STATUS = {"blutrv:200": {"id": 200, "current_C": 19.5, "target_C": 21, "pos": 30, "battery": 90, "rssi": -70}}
GW_CONFIG = {"blutrv:200": {"id": 200, "name": "Wohnzimmer"}}


def gw_handler(url, kw):
    m = kw["json"]["method"]
    if m == "Shelly.GetStatus":
        return 200, {"id": 1, "result": GW_STATUS}
    if m == "Shelly.GetConfig":
        return 200, {"id": 1, "result": GW_CONFIG}
    if m == "BluTrv.Call":
        return 200, {"id": 1, "result": None}
    return 200, {"id": 1, "error": {"code": -114, "message": "nope"}}


class Tests(unittest.TestCase):
    def setUp(self):
        self._orig = httpx.post

    def tearDown(self):
        httpx.post = self._orig

    def test_set_light_body_and_key_in_query(self):
        rec = Recorder(lambda u, k: (200, None))
        httpx.post = rec
        res = s.set_light("A1B2C3D4E5F6", on=True, brightness=40, temperature=3000, mode="white")
        url, kw = rec.calls[0]
        self.assertEqual(url, "https://shelly-00-eu.shelly.cloud/v2/devices/api/set/light")
        self.assertEqual(kw["params"], {"auth_key": "testkey"})
        self.assertEqual(kw["json"]["id"], "a1b2c3d4e5f6")
        self.assertEqual(kw["json"]["brightness"], 40)
        self.assertNotIn("testkey", json.dumps(res))

    def test_light_validation(self):
        with self.assertRaises(ValueError):
            s.set_light("a1b2c3d4e5f6", brightness=150)
        with self.assertRaises(ValueError):
            s.set_light("a1b2c3d4e5f6")
        with self.assertRaises(ValueError):
            s.set_light("../etc", on=True)

    def test_cloud_error_text(self):
        httpx.post = Recorder(lambda u, k: (400, {"error": "DEVICE_OFFLINE", "data": {"messages": []}}))
        with self.assertRaises(s.ShellyError) as cm:
            s.set_switch("a1b2c3d4e5f6", on=True)
        self.assertIn("DEVICE_OFFLINE", str(cm.exception))

    def test_cloud_host_restricted(self):
        os.environ["SHELLY_CLOUD_SERVER"] = "evil.example.com"
        try:
            with self.assertRaises(RuntimeError):
                s._cloud_server()
        finally:
            os.environ["SHELLY_CLOUD_SERVER"] = "shelly-00-eu.shelly.cloud"

    def test_group(self):
        rec = Recorder(lambda u, k: (200, {"failedCommands": {}}))
        httpx.post = rec
        res = s.set_group(False, lights=["a1b2c3d4e5f6_1"], switches=["b1b2c3d4e5f6"])
        body = rec.calls[0][1]["json"]
        self.assertEqual(body["light"]["ids"], ["a1b2c3d4e5f6_1"])
        self.assertEqual(body["switch"]["ids"], ["b1b2c3d4e5f6_0"])
        self.assertTrue(res["success"])

    def test_list_devices(self):
        def h(url, kw):
            if url.endswith("/device/all_status"):
                self.assertEqual(kw["data"]["auth_key"], "testkey")
                return 200, {"isok": True, "data": {"devices_status": {
                    "a1b2c3d4e5f6": {"_dev_info": {"gen": "G2", "online": True, "code": "SNDM-0013US"},
                                     "light:0": {"output": True, "brightness": 50}},
                    "2cf43268c9e5": {"_dev_info": {"gen": "G1", "online": True, "code": "SHSW-1"},
                                     "relays": [{"ison": False}]}}}}
            return 200, [{"id": "a1b2c3d4e5f6", "settings": {"sys": {"device": {"name": "Esstisch"}}}},
                         {"id": "2cf43268c9e5", "settings": {"name": "Reduit"}}]
        httpx.post = Recorder(h)
        res = s.list_devices()
        names = {d["id"]: d["name"] for d in res["devices"]}
        self.assertEqual(names, {"a1b2c3d4e5f6": "Esstisch", "2cf43268c9e5": "Reduit"})
        esstisch = next(d for d in res["devices"] if d["id"] == "a1b2c3d4e5f6")
        self.assertEqual(esstisch["lights"][0]["brightness"], 50)

    def test_trv_list_and_set_by_name(self):
        rec = Recorder(gw_handler)
        httpx.post = rec
        lst = s.list_trvs()
        self.assertEqual(lst["trvs"][0]["name"], "Wohnzimmer")
        res = s.set_trv_target("wohnzimmer", 21.55)
        call = rec.calls[-1][1]["json"]
        self.assertEqual(call["method"], "BluTrv.Call")
        self.assertEqual(call["params"], {"id": 200, "method": "TRV.SetTarget",
                                          "params": {"id": 0, "target_C": 21.6}})
        self.assertTrue(res["success"])

    def test_trv_by_gateway_id_skips_lookup(self):
        rec = Recorder(gw_handler)
        httpx.post = rec
        s.set_trv_boost("Wohnung:200", duration=600)
        self.assertEqual(len(rec.calls), 1)
        self.assertEqual(rec.calls[0][1]["json"]["params"]["params"], {"id": 0, "duration": 600})

    def test_trv_validation(self):
        with self.assertRaises(ValueError):
            s.set_trv_target("Wohnung:200", 35)
        with self.assertRaises(ValueError):
            s.set_trv_override("Wohnung:200", duration=5)
        httpx.post = Recorder(gw_handler)
        with self.assertRaises(ValueError):
            s.set_trv_target("Keller", 20)

    def test_gateway_parsing(self):
        os.environ["SHELLY_GATEWAYS"] = "http://192.0.2.10, Buero=192.0.2.11"
        try:
            self.assertEqual(s._gateways(), [{"name": "gw1", "url": "http://192.0.2.10"},
                                             {"name": "Buero", "url": "http://192.0.2.11"}])
        finally:
            os.environ["SHELLY_GATEWAYS"] = "Wohnung=http://192.0.2.10"


class AuthTests(unittest.TestCase):
    def test_token_required(self):
        with self.assertRaises(RuntimeError):
            s._validate_auth_token("kurz")

    def test_http_auth(self):
        from starlette.testclient import TestClient
        app = s.build_http_app("x" * 40)
        with TestClient(app) as c:
            self.assertEqual(c.get("/healthz").status_code, 200)
            self.assertEqual(c.post("/mcp", json={}).status_code, 401)
            self.assertEqual(c.get("//healthz").status_code, 200)


if __name__ == "__main__":
    unittest.main()
