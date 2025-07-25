import datetime
import threading
import json
import math
import time
from websocket import WebSocketApp, WebSocketConnectionClosedException
from flask import redirect
from sqlalchemy import delete
from app.core.main.BasePlugin import BasePlugin
from app.database import session_scope, get_now_to_utc, row2dict, convert_local_to_utc, convert_utc_to_local
from plugins.Friends2GIS.models import FriendLocation
from plugins.Friends2GIS.forms.SettingsForm import SettingsForm
from plugins.Friends2GIS.forms.FriendLocationForm import FriendLocationForm
from app.core.lib.common import addNotify, callPluginFunction
from app.core.lib.constants import CategoryNotify
from app.extensions import cache

class Friends2GIS(BasePlugin):

    def __init__(self,app):
        super().__init__(app,__name__)
        self.title = "Friends2GIS"
        self.description = """Get location from 2GIS Friends"""
        self.category = "App"
        self.version = "0.1"
        self.actions = []
        self.author = "Eraser"
        self.ws = None
        self.thread = None
        self.reconnect_interval = 5  # Задержка переподключения (секунды)
        self.is_running = False
        self.viewport = None

    def initialization(self):
        self.last_update = None
        token = self.config.get("token")
        if not token:
            self.logger.warning("Please set token in config")
            addNotify("Empty TOKEN", "Please set token in config", CategoryNotify.Error, self.name)
            return

        coordinates = []
        with session_scope() as session:
            users = session.query(FriendLocation).all()
            for user in users:
                coordinates.append((user.lat, user.lng))

        self.viewport = self.calculate_viewport(coordinates, padding=0.1)
        self.connect()

    def calculate_viewport(self, coordinates, padding=0.1):
        if not coordinates:
            return {
                "topLeft": {"lon": 0, "lat": 0},
                "bottomRight": {"lon": 0, "lat": 0}
            }

        # Извлекаем все долготы и широты
        lats, lons = zip(*coordinates)  # Распаковываем список кортежей в два списка

        min_lon, max_lon = min(lons), max(lons)
        min_lat, max_lat = min(lats), max(lats)

        return {
            "topLeft": {
                "lon": min_lon - padding,
                "lat": max_lat + padding
            },
            "bottomRight": {
                "lon": max_lon + padding,
                "lat": min_lat - padding
            }
        }

    def connect(self):
        if self.is_running:
            return

        token = self.config.get("token")
        ws_url = f"wss://zond.api.2gis.ru/api/1.1/user/ws?appVersion=6.31.0&channels=markers,sharing,routes&token={token}"
        self.is_running = True
        self.ws = WebSocketApp(
            ws_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )

        self.logger.info("Запуск WebSocket-клиента")

        self.thread = threading.Thread(target=self._run_websocket)
        self.thread.daemon = True  # Поток завершится при выходе из основной программы
        self.thread.start()

    def _run_websocket(self):
        """Внутренний метод для запуска WebSocket."""
        while self.is_running:
            try:
                self.ws.run_forever()
            except WebSocketConnectionClosedException:
                self.logger.warning("Соединение разорвано. Переподключение...")
                time.sleep(self.reconnect_interval)
            except Exception as e:
                self.logger.exception(f"Критическая ошибка: {e}")
                break

    def disconnect(self):
        """Корректная остановка клиента."""
        self.is_running = False
        if self.ws:
            self.ws.close()
        if self.thread:
            self.thread.join()
        self.logger.info("WebSocket остановлен")

    def on_message(self, ws, message):
        # Можно разобрать JSON, если сервер присылает его
        try:
            data = json.loads(message)
            self.logger.debug(data)
            type_message = data.get("type")
            payload = data.get("payload")
            if type_message == "initialState":
                profiles = payload.get("profiles",[])
                self.update_friends(profiles)
                states = payload.get("states",[])
                for state in states:
                    self.update_state(state)
            elif type_message == "friendState":
                self.update_state(payload)
                self.last_update = get_now_to_utc()
                self.viewportChanged(payload["location"])
        except json.JSONDecodeError as ex:
            self.logger.exception(ex)
        except Exception as ex:
            self.logger.exception(ex)

    def on_error(self, ws, error):
        self.logger.error(f"Ошибка: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        self.logger.warning("### Соединение закрыто ###")
        if self.is_running:
            self.logger.info(f"Попытка переподключения через {self.reconnect_interval} сек...")
            time.sleep(self.reconnect_interval)
            self.connect()

    def on_open(self, ws):
        self.logger.info("### Подключено к серверу 2GIS ###")
        sharers = []
        with session_scope() as session:
            users = session.query(FriendLocation).all()
            for user in users:
                sharers.append(str(user.id_user))
        payload = {"type":"bindRoutes","payload":{"sharers":sharers}}
        self.sendPayload(payload)
        payload = {"type":"viewportChanged","payload":{"viewport":self.viewport,"zoom":15}}
        self.sendPayload(payload)

    def expand_viewport_if_needed(self, point, padding=0.1):
        top_left = self.viewport["topLeft"]
        bottom_right = self.viewport["bottomRight"]
        lon, lat = point["lon"], point["lat"]
        # Проверяем, находится ли точка внутри viewport
        is_inside = (
            (bottom_right["lon"] >= lon >= top_left["lon"]) and
            (top_left["lat"] >= lat >= bottom_right["lat"])
        )
        if is_inside:
            return False  # Не нужно расширять
        # Вычисляем текущие размеры viewport
        lon_size = bottom_right["lon"] - top_left["lon"]
        lat_size = top_left["lat"] - bottom_right["lat"]
        # Добавляем запас (padding)
        lon_padding = lon_size * padding
        lat_padding = lat_size * padding
        # Расширяем границы, чтобы включить точку + запас
        new_top_left = {
            "lon": min(top_left["lon"], lon - lon_padding),
            "lat": max(top_left["lat"], lat + lat_padding)
        }
        new_bottom_right = {
            "lon": max(bottom_right["lon"], lon + lon_padding),
            "lat": min(bottom_right["lat"], lat - lat_padding)
        }
        self.viewport = {
            "topLeft": new_top_left,
            "bottomRight": new_bottom_right
        }
        return True

    def viewportChanged(self,location):
        update = self.expand_viewport_if_needed(location)
        if self.ws and update:
            # {"type":"viewportChanged","payload":{"viewport":{"topLeft":{"lon":49.66339149419425,"lat":58.58453094647541},"bottomRight":{"lon":49.69966481183402,"lat":58.555611780572974}},"zoom":15}}
            payload = {"type":"viewportChanged","payload":{"viewport":self.viewport,"zoom":15}}
            self.sendPayload(payload)

    def sendPayload(self, payload):
        if self.ws:
            self.logger.debug("Send: " + json.dumps(payload))
            self.ws.send(json.dumps(payload))

    def admin(self, request):
        op = request.args.get("op", None)

        if op == "user_edit":
            id = int(request.args.get("id"))
            with session_scope() as session:
                location = session.get(FriendLocation, id)
                form = FriendLocationForm(obj=location)
                if form.validate_on_submit():
                    form.populate_obj(location)
                    session.commit()
                    return redirect(self.name)
            return self.render("2gis_location_user.html", {"form": form})

        if op == "user_delete":
            id = int(request.args.get("id"))
            with session_scope() as session:
                sql = delete(FriendLocation).where(FriendLocation.id == id)
                session.execute(sql)
                session.commit()
            return redirect(self.name)

        settings = SettingsForm()
        if request.method == 'GET':
            settings.token.data = self.config.get('token','')
            settings.min_update_interval.data = self.config.get("min_update_interval", 30)
        else:
            if settings.validate_on_submit():
                self.config["token"] = settings.token.data
                self.config["min_update_interval"] = settings.min_update_interval.data
                self.saveConfig()
                self.disconnect()
                self.connect()
                return redirect(self.name)

        locations = FriendLocation.query.order_by(FriendLocation.name).all()
        locations = [row2dict(location) for location in locations]

        content = {
            'locations': locations,
            'form': settings,
            'last_update': convert_utc_to_local(self.last_update)
        }
        return self.render('2gis_location_main.html', content)

    def update_friends(self, profiles):
        with session_scope() as session:
            for profile in profiles:
                rec = session.query(FriendLocation).where(FriendLocation.id_user == profile["id"]).one_or_none()

                if not rec:
                    rec = FriendLocation()
                    rec.id_user = profile["id"]
                    rec.name = profile["name"]
                    rec.image = ""
                    session.add(rec)
                    self.logger.info(f'Добавлен новый пользователь {rec.name}!')
                    addNotify('Внимание!',f'Добавлен новый пользователь {rec.name}!',CategoryNotify.Info, self.name)

                rec.name = profile["name"]
                rec.image = profile.get('logo') if profile.get('logo') else ""

                session.commit()

    def update_state(self, state):

        user_id = state["id"]
        last_seen = state["lastSeen"]
        last_seen_dt = datetime.datetime.fromtimestamp(last_seen / 1000)
        min_update_interval = self.config.get("min_update_interval", 30)

        # Проверяем кэш: если обновляли недавно — пропускаем
        last_cached_update = cache.get(self.name + "_" + user_id)
        if last_cached_update and (last_seen_dt - last_cached_update).total_seconds() < min_update_interval:
            return

        with session_scope() as session:
            rec = session.query(FriendLocation).where(FriendLocation.id_user == state["id"]).one_or_none()
            if not rec:
                return

            target_date = rec.last_update if rec.last_update else datetime.datetime.now()
            if target_date == last_seen_dt:
                return

            cache.set(self.name + "_" + user_id, last_seen_dt)

            rec.last_update = convert_local_to_utc(last_seen_dt)
            location = state["location"]
            battery = state["battery"]

            if rec.lat == location['lat'] and rec.lng == location['lon'] and rec.battery_level == int(battery['level'] * 100):
                return

            if rec.speed:
                rec.speed = location["speed"]
            else:
                rec.speed = self.get_speed(rec, location, last_seen_dt)

            rec.lat = location['lat']
            rec.lng = location['lon']
            if location['accuracy']:
                rec.accuracy = location['accuracy']

            rec.battery_level = int(battery['level'] * 100)
            rec.battery_charging = 1 if battery['isCharging'] else 0

            if rec.sendtogps:
                args = {
                    'device': rec.id_user,
                    'lat': rec.lat,
                    'lon': rec.lng,
                    'accuracy': rec.accuracy,
                    'address': rec.address,
                    'speed': rec.speed,
                    'battery': rec.battery_level,
                    'charging': rec.battery_charging,
                    'provider': self.name,
                    'added': rec.last_update,
                }
                callPluginFunction("GpsTracker","addGpsPosition",args)

            session.commit()

    def get_speed(self, last: FriendLocation, new, time_new):
        time_last = last.last_update
        if not last.lat or not last.lng:
            return 0
        dist = self.calculate_the_distance(last.lat, last.lng, new['lat'], new['lon'])
        diff = time_new.timestamp() - time_last.timestamp()
        if diff == 0:
            return 0
        return round(dist / diff * 3.6, 2)  # km/h

    def calculate_the_distance(self, latA, lonA, latB, lonB):
        EARTH_RADIUS = 6372795

        lat1 = math.radians(latA)
        lat2 = math.radians(latB)
        long1 = math.radians(lonA)
        long2 = math.radians(lonB)

        cl1 = math.cos(lat1)
        cl2 = math.cos(lat2)
        sl1 = math.sin(lat1)
        sl2 = math.sin(lat2)

        delta = long2 - long1
        cdelta = math.cos(delta)
        sdelta = math.sin(delta)

        y = math.sqrt((cl2 * sdelta) ** 2 + (cl1 * sl2 - sl1 * cl2 * cdelta) ** 2)
        x = sl1 * sl2 + cl1 * cl2 * cdelta

        ad = math.atan2(y, x)

        dist = round(ad * EARTH_RADIUS)
        return dist
