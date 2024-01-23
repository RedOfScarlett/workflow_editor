import os
import asyncio
import traceback
import uuid
import nodes
import struct
import aiohttp
from aiohttp import web
import mimetypes

async def send_socket_catch_exception(function, message):
    try:
        await function(message)
    except (aiohttp.ClientError, aiohttp.ClientPayloadError, ConnectionResetError) as err:
        print("send error:", err)

@web.middleware
async def cache_control(request: web.Request, handler):
    response: web.Response = await handler(request)
    if request.path.endswith('.js') or request.path.endswith('.css'):
        response.headers.setdefault('Cache-Control', 'no-cache')
    return response

def create_cors_middleware(allowed_origin: str):
    @web.middleware
    async def cors_middleware(request: web.Request, handler):
        if request.method == "OPTIONS":
            # Pre-flight request. Reply successfully:
            response = web.Response()
        else:
            response = await handler(request)

        response.headers['Access-Control-Allow-Origin'] = allowed_origin
        response.headers['Access-Control-Allow-Methods'] = 'POST, GET, DELETE, PUT, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response

    return cors_middleware

class PromptServer():
    def __init__(self, loop):
        PromptServer.instance = self
        mimetypes.init()
        mimetypes.types_map['.js'] = 'application/javascript; charset=utf-8'
        self.prompt_queue = None
        self.loop = loop
        self.messages = asyncio.Queue()
        middlewares = [cache_control]
        middlewares.append(create_cors_middleware("*"))
        max_upload_size = round(8 * 1024 * 1024)
        self.app = web.Application(client_max_size=max_upload_size, middlewares=middlewares)
        self.sockets = dict()
        self.web_root = os.path.join(os.path.dirname(
            os.path.realpath(__file__)), "web")
        routes = web.RouteTableDef()
        self.routes = routes
        self.last_node_id = None
        self.client_id = None

        @routes.get('/ws')
        async def websocket_handler(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            sid = request.rel_url.query.get('clientId', '')
            if sid:
                # Reusing existing session, remove old
                self.sockets.pop(sid, None)
            else:
                sid = uuid.uuid4().hex

            self.sockets[sid] = ws

            try:
                # Send initial state to the new client
                await self.send("status", { "status": self.get_queue_info(), 'sid': sid }, sid)
                # On reconnect if we are the currently executing client send the current node
                if self.client_id == sid and self.last_node_id is not None:
                    await self.send("executing", { "node": self.last_node_id }, sid)
                    
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.ERROR:
                        print('ws connection closed with exception %s' % ws.exception())
            finally:
                self.sockets.pop(sid, None)
            return ws

        @routes.get("/")
        async def get_root(request):
            return web.FileResponse(os.path.join(self.web_root, "index.html"))

        def node_info(node_class):
            obj_class = nodes.NODE_CLASS_MAPPINGS[node_class]
            info = {}
            info['inputs'] = {
                                "required": [attribute.toJSON() for attribute in obj_class.required_inputs],
                                "optional": [attribute.toJSON() for attribute in obj_class.optional_inputs]
                            }
            info['attributes'] = {
                                    "required": [attribute.toJSON() for attribute in obj_class.required_attributes],
                                    "optional": [attribute.toJSON() for attribute in obj_class.optional_attributes]
                                }
            info['outputs'] = [attribute.toJSON() for attribute in obj_class.outputs]
            info['name'] = node_class
            info['display_name'] = nodes.NODE_DISPLAY_NAME_MAPPINGS[node_class] if node_class in nodes.NODE_DISPLAY_NAME_MAPPINGS.keys() else node_class
            info['description'] = obj_class.DESCRIPTION if hasattr(obj_class,'DESCRIPTION') else ''
            info['category'] = obj_class.category if hasattr(obj_class,'category') else "Function"
            return info

        @routes.get("/object_info")
        async def get_object_info(request):
            out = {}
            for x in nodes.NODE_CLASS_MAPPINGS:
                try:
                    out[x] = node_info(x)
                except Exception as e:
                    print(f"[ERROR] An error occurred while retrieving information for the '{x}' node.", file=sys.stderr)
                    traceback.print_exc()
            return web.json_response(out)

    def add_routes(self):
        self.app.add_routes(self.routes)
        self.app.add_routes([
            web.static('/', self.web_root, follow_symlinks=True),
        ])

    async def send(self, event, data, sid=None):
        if isinstance(data, (bytes, bytearray)):
            await self.send_bytes(event, data, sid)
        else:
            await self.send_json(event, data, sid)

    def encode_bytes(self, event, data):
        if not isinstance(event, int):
            raise RuntimeError(f"Binary event types must be integers, got {event}")

        packed = struct.pack(">I", event)
        message = bytearray(packed)
        message.extend(data)
        return message

    async def send_bytes(self, event, data, sid=None):
        message = self.encode_bytes(event, data)

        if sid is None:
            for ws in self.sockets.values():
                await send_socket_catch_exception(ws.send_bytes, message)
        elif sid in self.sockets:
            await send_socket_catch_exception(self.sockets[sid].send_bytes, message)

    async def send_json(self, event, data, sid=None):
        message = {"type": event, "data": data}
        if sid is None:
            for ws in self.sockets.values():
                await send_socket_catch_exception(ws.send_json, message)
        elif sid in self.sockets:
            await send_socket_catch_exception(self.sockets[sid].send_json, message)
    
    def send_sync(self, event, data, sid=None):
        self.loop.call_soon_threadsafe(
            self.messages.put_nowait, (event, data, sid))

    def queue_updated(self):
        self.send_sync("status", { "status": self.get_queue_info() })

    async def publish_loop(self):
        while True:
            msg = await self.messages.get()
            await self.send(*msg)

    async def start(self, address, port, verbose=True, call_on_start=None):
        runner = web.AppRunner(self.app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, address, port)
        await site.start()

        if address == '':
            address = '0.0.0.0'
        if verbose:
            print("Starting server\n")
            print("To see the GUI go to: http://{}:{}".format(address, port))
        if call_on_start is not None:
            call_on_start(address, port)
