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
    _id = params.get('id', None)
    if not _id:
        return await websocket.close(code=CloseCode.INVALID_DATA, reason="Invalid channel id")
    clients[websocket] = {'id': _id, 'groups': set()}
    await websocket.send(json.dumps({"type": "info", "message": "You are connected!"}))


async def unregister(websocket):
    # Unregister a client
    if websocket in clients:
        for group in clients[websocket]['groups']:
            groups[group].remove(websocket)
            if len(groups[group]) == 0:
                del groups[group]
        del clients[websocket]


async def handler(websocket, path):
    # Handle incoming messages
    await register(websocket, path)
    try:
        async for message in websocket:
            data = json.loads(message)
            if data['type'] == 'message':
                await handle_message(websocket, data)
            elif data['type'] == 'group_message':
                await handle_group_message(websocket, data)
            elif data['type'] == 'join_group':
                await handle_join_group(websocket, data)
    finally:
        await unregister(websocket)


async def handle_message(websocket, data):
    # Handle One2One incoming messages
    target = data['target']
    message = data['message']
    for client in clients:
        if clients[client]['id'] == target:
            await client.send(json.dumps({"type": "message", "from": clients[websocket]['id'], "message": message}))


async def handle_group_message(websocket, data):
    # Handle Group incoming messages
    group = data['group']
    message = data['message']
    if group in groups:
        for member in groups[group]:
            if member != websocket:
                await member.send(json.dumps(
                    {"type": "group_message", "from": clients[websocket]['id'], "group": group, "message": message}))


async def handle_join_group(websocket, data):
    # Handle Group joining
    group = data['group']
    if group not in groups:
        groups[group] = set()
    groups[group].add(websocket)
    clients[websocket]['groups'].add(group)
    await websocket.send(json.dumps({"type": "info", "message": f"You have joined group {group}"}))


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
