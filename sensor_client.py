import asyncio
import logging
import socket
import struct
from threading import Thread

log = logging.getLogger(__name__)

class SensorClient(Thread):
    buffer_size = 1024
    data = None

    def __init__(self, server, server_port=5555, callback_objects=()):
        Thread.__init__(self)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.reader, self.writer = None, None
        self.callback = [i.callback for i in callback_objects]

        self.connect(server, server_port)

    def run(self):
        self.loop.run_forever()

    async def connect(self, server, server_port):
        self.reader, self.writer = await asyncio.open_connection(server, server_port, loop=self.loop)
        self.handle_read()

    async def handle_read(self):
        while True:
            try:
                data = await self.reader.read(self.buffer_size)
                if not data:
                    break
                self.on_data(data)
            except (asyncio.CancelledError, ConnectionResetError):
                break

    def on_data(self, data):
        self.data = self.decode_pos(data)

        if self.data:
            for callback in self.callback:
                try:
                    callback(self.data)
                except Exception as e:
                    log.exception(e)

    @staticmethod
    def sensor_31(data):
        # empty = struct.unpack('b4b4b4b', data[:13])
        dt = struct.unpack("3f", data[13:25])
        speed = struct.unpack("6b", data[-6:])
        return {"data": dt, "speed": speed}

    @staticmethod
    def sensor_53(data):
        crc, _, trigger = struct.unpack("3b", data[:3])
        speed = struct.unpack("2b", data[3:5])
        axis_xy = struct.unpack("2f", data[5:13])
        euler_data = struct.unpack("3f", data[13:25])
        quaternion = struct.unpack("4f", data[25:41])
        accel = struct.unpack("3f", data[41:])
        return {
            "trigger": trigger,
            "speed": speed,
            "axisXY": axis_xy,
            "eulerData": euler_data,
            "quaternion": quaternion,
            "accel": accel,
        }

    def decode_pos(self, data):
        data_len = len(data)
        if not data_len % 53:
            return self.sensor_53(data[-53:])
        elif not data_len % 31:
            return self.sensor_31(data[-31:])
        else:
            log.warning("Unknown sensor data len: %i", data_len)

    @staticmethod
    def split_list(lst, group_len):
        data_len = len(lst)
        kol_in_group = data_len // group_len
        return [lst[i:i + kol_in_group] for i in range(0, data_len, kol_in_group)]
