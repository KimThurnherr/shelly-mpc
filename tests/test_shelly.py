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


LISTS = {"isok": True, "data": {
    "devices": {
        "a1b2c3d4e5f6": {"name": "Esstisch", "room_id": 1, "category": "light"},
        "2cf43268c9e5": {"name": "Reduit", "room_id": 2, "category": "relay"},
        "aabbccddeeff": {"name": "Gateway", "room_id": 1, "category": "gateway", "ip": "192.0.2.10"},
        "aabbccddeeff_2200": {"name": "Wohnzimmer", "room_id": 1, "category": "thermostat"},
    },
    "rooms": {"1": {"name": "Stube"}, "2": {"name": "Keller"}}}}
GW_CLOUD = [{"id": "aabbccddeeff", "online": 1, "status": {
    "blutrv:200": {"id": 200, "battery": 90, "rssi": -60},
    "blutrv_rstatus:200": {"status": {"trv:0": {"current_C": 19.5, "target_C": 21, "pos": 30}}}}}]


def handler(url, kw):
    if url.endswith("/interface/device/get_all_lists"):
        return 200, LISTS
    if url.endswith("/v2/devices/api/get"):
        return 200, GW_CLOUD
    if url.startswith("http://192.0.2.10"):
        if kw["json"]["method"] == "BluTrv.Call":
            return 200, {"id": 1, "result": None}
        return 200, {"id": 1, "result": {"blutrv:200": {}}}
    return 404, None


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
            return handler(url, kw)
        s._lists_cache.update(ts=0.0, data=None)
        httpx.post = Recorder(h)
        res = s.list_devices()
        by = {d["id"]: d for d in res["devices"]}
        self.assertEqual(by["a1b2c3d4e5f6"]["name"], "Esstisch")
        self.assertEqual(by["a1b2c3d4e5f6"]["room"], "Stube")
        self.assertEqual(by["a1b2c3d4e5f6"]["lights"][0]["brightness"], 50)
        self.assertEqual(by["2cf43268c9e5"]["switches"][0]["name"], "Reduit")

    def test_trv_list_and_set_by_name(self):
        s._lists_cache.update(ts=0.0, data=None)
        rec = Recorder(handler)
        httpx.post = rec
        lst = s.list_trvs()
        t = lst["trvs"][0]
        self.assertEqual((t["name"], t["room"], t["current_c"], t["target_c"]), ("Wohnzimmer", "Stube", 19.5, 21))
        res = s.set_trv_target("wohnzimmer", 21.55)
        url, kw = rec.calls[-1]
        self.assertEqual(url, "http://192.0.2.10/rpc")
        self.assertEqual(kw["json"]["params"], {"id": 200, "method": "TRV.SetTarget",
                                                "params": {"id": 0, "target_C": 21.6}})
        self.assertTrue(res["success"])

    def test_trv_boost_by_id(self):
        s._lists_cache.update(ts=0.0, data=None)
        rec = Recorder(handler)
        httpx.post = rec
        s.set_trv_boost("aabbccddeeff:200", duration=600)
        self.assertEqual(rec.calls[-1][1]["json"]["params"]["params"], {"id": 0, "duration": 600})

    def test_trv_validation(self):
        with self.assertRaises(ValueError):
            s.set_trv_target("Wohnzimmer", 35)
        with self.assertRaises(ValueError):
            s.set_trv_override("Wohnzimmer", duration=5)
        s._lists_cache.update(ts=0.0, data=None)
        httpx.post = Recorder(handler)
        with self.assertRaises(ValueError):
            s.set_trv_target("Keller", 20)


    def _scene_handler(self):
        scenes = {"isok": True, "data": {"scene_scripts": {"1764245018369": {
            "_enabled": True, "_id": "1764245018369", "_name": "1764245018369", "_file_modtag": "x",
            "_meta": {"name": "Heizung aus", "roomn": "General"},
            "if": {"or": []}, "do": [{"r": "dev:%d:tgt2201" % int("aabbccddeeff", 16), "set": 14}]}}}}

        def h(url, kw):
            if url.endswith("/scene/list"):
                return 200, scenes
            if url.endswith(("/scene/enable", "/scene/manual_run", "/scene/edit")):
                return 200, {"isok": True}
            return handler(url, kw)
        return h

    def test_scenes(self):
        s._lists_cache.update(ts=0.0, data=None)
        rec = Recorder(self._scene_handler())
        httpx.post = rec
        lst = s.list_scenes()
        self.assertEqual(lst["scenes"][0]["actions"][0]["target"], "Wohnzimmer [tgt2201]")
        prev = s.run_scene("heizung aus")
        self.assertTrue(prev["preview"])
        self.assertFalse(any(u.endswith("/scene/manual_run") for u, _ in rec.calls))
        s.run_scene("Heizung aus", confirm=True)
        self.assertEqual(rec.calls[-1][1]["data"]["id"], "1764245018369")
        self.assertFalse(s.set_scene_enabled("Heizung aus", True)["executed"])
        s.set_scene_enabled("1764245018369", False)
        self.assertEqual(rec.calls[-1][1]["data"]["enabled"], "false")

    def test_edit_scene(self):
        rec = Recorder(self._scene_handler())
        httpx.post = rec
        new_do = [{"r": "dev:1:tgt2200", "set": 16}]
        prev = s.edit_scene("Heizung aus", {"do": new_do})
        self.assertTrue(prev["preview"])
        out = s.edit_scene("Heizung aus", {"do": new_do}, confirm=True)
        body = json.loads(rec.calls[-1][1]["data"]["scene_script"])
        self.assertEqual(body["do"], new_do)
        self.assertNotIn("_file_modtag", body)
        self.assertEqual(out["previous_script"]["do"][0]["set"], 14)
        with self.assertRaises(ValueError):
            s.edit_scene("Heizung aus", {"_id": "1"})

    def test_create_scene(self):
        base = self._scene_handler()

        def h(url, kw):
            if url.endswith("/scene/add"):
                return 200, {"isok": True, "data": {"scene_id": "1793900000001"}}
            return base(url, kw)
        rec = Recorder(h)
        httpx.post = rec
        new_do = [{"r": "dev:1:tgt2201", "set": 14}]
        prev = s.create_scene("Heizung aus Freitag", {"do": new_do}, copy_from="Heizung aus")
        self.assertTrue(prev["preview"])
        self.assertFalse(any(u.endswith("/scene/add") for u, _ in rec.calls))
        out = s.create_scene("Heizung aus Freitag", {"do": new_do}, copy_from="Heizung aus", confirm=True)
        self.assertEqual(out["id"], "1793900000001")
        body = json.loads(rec.calls[-1][1]["data"]["scene_script"])
        self.assertEqual(body["_meta"]["name"], "Heizung aus Freitag")
        self.assertEqual(body["do"], new_do)
        self.assertNotIn("_id", body)
        self.assertNotIn("_file_modtag", body)
        with self.assertRaises(ValueError):
            s.create_scene("heizung aus", {"if": {"or": []}, "do": new_do})
        with self.assertRaises(ValueError):
            s.create_scene("Ohne Aktion", {"if": {"or": []}})

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
            self.assertEqual(c.get("http://testserver//healthz").status_code, 200)
        os.environ["MCP_PATH_PREFIX"] = "/shelly"
        try:
            with TestClient(s.build_http_app("x" * 40)) as c:
                self.assertEqual(c.get("/shelly/healthz").status_code, 200)
                self.assertEqual(c.post("/shelly/mcp", json={}).status_code, 401)
        finally:
            del os.environ["MCP_PATH_PREFIX"]


if __name__ == "__main__":
    unittest.main()
