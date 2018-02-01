
import asyncio
import logging
import sys
import ssl


SERVER_ADDRESS = (str(sys.argv[1]), 6215)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(name)s: %(message)s',
    stream=sys.stderr,
)
log = logging.getLogger('main')

event_loop = asyncio.get_event_loop()


async def write(writer):
    while True:
        sys.stdout.write(">> ")
        sys.stdout.flush()
        line = await event_loop.run_in_executor(None, sys.stdin.readline)
        # HERE ##############################
        writer.write(b'0')
        writer.write(bytes([len(line)]).rjust(4, b'\x00'))
        writer.write(line.encode())
        
        await writer.drain()

async def read(reader):
    while True:
        data = await reader.read(128)
        terminate = data.endswith(b'\x00')
        data = data.rstrip(b'\x00')
        if data:
            sys.stdout.write(data.decode())
            sys.stdout.flush()
        
async def echo_client(address, messages):
    log = logging.getLogger('echo_client')

    log.debug('connecting to {} port {}'.format(*address))


    ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH,)
    ssl_context.check_hostname = False
    ssl_context.load_verify_locations('cert/cert.pem')
    reader, writer = await asyncio.open_connection(*SERVER_ADDRESS,
                                                   ssl=ssl_context)
    
    event_loop.create_task(write(writer))
    event_loop.create_task(read(reader))
        
    while True:
        try:
            await asyncio.sleep(0)
        except KeyboardInterrupt:
            writer.close()
            break

try:
    event_loop.run_until_complete(
        echo_client(SERVER_ADDRESS, MESSAGES)
    )
finally:
    log.debug('closing event loop')
    event_loop.close()
