#!/usr/bin/env python

from string import printable
from curses import erasechar, wrapper
import asyncio

lines = []
Y, X = 0, 0
max_lines = 0

screen = None

WRITER = None






import asyncio
import logging
import sys
import ssl

SERVER_ADDRESS = ('', 6215)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(name)s: %(message)s',
    stream=sys.stderr,
)





async def write(writer):
    while True:
        sys.stdout.write(">> ")
        sys.stdout.flush()
        line = await loop.run_in_executor(None, sys.stdin.readline)
        writer.write(line.encode())
        writer.write(b'\x00')
        await writer.drain()
        post_message(screen, ">>> ".join(line).encode())

async def read(reader):
    while True:
        flavor = await reader.read(1)
        length = await reader.read(4)
        data = await reader.read(int.from_bytes(length, 'big'))
        if data:
            post_message(screen, data)


async def echo(reader, writer):
    global WRITER
    WRITER = writer

    loop.create_task(read(reader))
    
    while True:
        try:
            await asyncio.sleep(0)
        except KeyboardInterrupt:
            writer.close()
            break










def write_prompt(stdscr, y, x, prompt):
    stdscr.move(y, x)
    stdscr.clrtoeol()
    stdscr.addstr(y, x, prompt)

async def prompt(stdscr, y, x, prompt=">>> "): # MAX_Y - 1, 0
    write_prompt(stdscr, y, x, prompt)    

    #input...
    pre_y, pre_x = stdscr.getyx()
    chararray = []

    stdscr.nodelay(True)
    global WRITER
    while True:
        await asyncio.sleep(0)
        char = stdscr.getch()

        if char == -1:
            continue
        
        if char in (13, 10): # return pressed
            output_string = "".join(chararray)
            WRITER.write(b'0')
            WRITER.write(bytes([len(output_string)]).rjust(4, b'\x00'))
            WRITER.write(output_string.encode())
            await WRITER.drain()
            if output_string == ":q":
                #TODO: shut down tasks
                break
            chararray = []
            post_message(stdscr, output_string)
            write_prompt(stdscr, y, x, prompt)
            stdscr.refresh()
        elif char in (ord(erasechar()), 263): # 263 is backspace on raspi
            post_y, post_x = stdscr.getyx()
            if post_x > pre_x:
                del chararray[-1]
                stdscr.move(post_y, (post_x - 1))
                stdscr.clrtoeol()
                stdscr.refresh()
        elif chr(char) in printable: # If we can print the character
            try:
                chararray.append(chr(char))
                stdscr.addch(char)
            except:
                pass

async def randommsg(stdscr):
    while True:
        await asyncio.sleep(1)
        post_message(stdscr, str(Y))
        stdscr.refresh()

def post_message(stdscr, message):
    global lines, max_lines
    y, x = stdscr.getyx()
    lines.append(message)
    if len(lines) > max_lines:
        lines = lines[1:]
        stdscr.clear()
        for i, line in enumerate(lines):
            stdscr.addstr(i, 0, line)
    else:
        stdscr.addstr(len(lines), 0, message)
    stdscr.move(y, x)
        
    

def main(stdscr):
    global Y, X, max_lines, screen, loop, server
    screen = stdscr
    Y, X = stdscr.getmaxyx()
    


    
    max_lines = (Y - 3)
    loop.create_task(prompt(stdscr, (Y-1), 0))
    
    stdscr.clear()

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:

        server.close()
        loop.run_until_complete(server.wait_closed())

        loop.close()



loop = asyncio.get_event_loop();
ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
ssl_context.check_hostname = False
ssl_context.load_cert_chain('cert/cert.pem', 'cert/key.pem')
    
factory = asyncio.start_server(echo, *SERVER_ADDRESS, ssl=ssl_context)
server = loop.run_until_complete(factory)

wrapper(main)
