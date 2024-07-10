# server.py

import asyncio
import websockets
from websockets.frames import CloseCode
import json
import uvloop

clients = {}  # to store connected clients
groups = {}  # to store groups and their members


async def query_to_dict(path):
    # Convert query string to dict
    _queries = path.split("?")[-1].split("&")
    _dict = dict(item.split('=') for item in _queries)
    return _dict


async def register(websocket, path):
    # Register a new client
    params = await query_to_dict(path)
    _registered_id = params.get('id', None)
    if not _registered_id:
        return await websocket.close(code=CloseCode.INVALID_DATA, reason="Invalid channel id")
    clients[_registered_id] = websocket
    await websocket.send(json.dumps({"type": "info", "message": "You are connected!"}))


async def unregister(path):
    # Unregister a client
    params = await query_to_dict(path)
    _registered_id = params.get('id', None)
    if _registered_id in clients:
        del clients[_registered_id]


async def handler(websocket, path):
    # Handle incoming messages
    await register(websocket, path)
    try:
        async for message in websocket:
            data = json.loads(message)
            if data['type'] == 'message':
                await handle_message(websocket, data, path)
            elif data['type'] == 'group_message':
                await handle_group_message(websocket, data, path)
            elif data['type'] == 'join_group':
                await handle_join_group(websocket, data, path)
    finally:
        await unregister(path)


async def handle_message(websocket, data, path):
    # Handle One2One incoming messages
    params = await query_to_dict(path)
    _sender_id = params.get('id', None)
    target = data['target']
    message = data['message']
    for _receiver_id, _websocket in clients.items():
        if _receiver_id == target and _websocket != websocket:
            await _websocket.send(json.dumps({"type": "message", "from": _sender_id, "message": message}))


async def handle_join_group(websocket, data, path):
    # Handle Group joining
    params = await query_to_dict(path)
    _sender_id = params.get('id', None)
    group = data['group']
    if group not in groups:
        groups[group] = set()
    groups[group].add(_sender_id)
    await websocket.send(json.dumps({"type": "info", "message": f"You have joined group {group}"}))


async def handle_group_message(websocket, data, path):
    # Handle Group incoming messages
    params = await query_to_dict(path)
    _sender_id = params.get('id', None)
    group = data['group']
    message = data['message']
    if group in groups:
        for _receiver_id in groups[group]:
            _websocket = clients[_receiver_id]
            if _websocket != websocket:
                await _websocket.send(json.dumps(
                    {"type": "group_message", "from": _sender_id, "group": group, "message": message}))


async def main():
    await websockets.serve(handler, "localhost", 8000)


if __name__ == "__main__":
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    loop = uvloop.new_event_loop()
    asyncio.set_event_loop(loop)

    server = asyncio.ensure_future(main())

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        server.cancel()
        loop.run_until_complete(server)
    finally:
        loop.close()
