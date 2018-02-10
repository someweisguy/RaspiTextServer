#!/usr/bin/env python3

from asyncio import get_event_loop, sleep, start_server, Task
from curses import wrapper
from ssl import create_default_context, Purpose
from string import printable
from collections import namedtuple
import os.path
import json

# TODO: Make user input multi line.
# TODO: Make outbound messages justified right
# TODO: Phone must send unicode message body
# TODO: Save messages in sqlite3 .db files

Contact = namedtuple('Contact', 'phone_number name')

printable_chars = [c for c in printable if c is not chr(10)]


class Server:
    def __init__(self, stdscr, port, certfile, keyfile):
        assert os.path.isfile(certfile)
        assert os.path.isfile(keyfile)

        self.loop = get_event_loop()
        self.screen = stdscr
        self.screen.nodelay(True)
        self.screen.keypad(False)

        self.contacts = self.get_contacts()
        self.destination_address = self.contacts[0].name

        self.attached_sockets = []
        self.received_messages = []

        ssl_context = create_default_context(Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(certfile, keyfile)

        user_output = self.loop.create_task(self.user_output())
        user_output.add_done_callback(self.shutdown)

        factory = start_server(self.handle_socket, '', port, ssl=ssl_context)
        self.server = self.loop.run_until_complete(factory)

        self.screen.clear()
        self.draw_header()

        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            user_output.cancel()
        finally:
            with open('contacts.json', '+w') as contacts:
                json.dump(self.contacts, contacts)
                
            self.shutdown()

    @staticmethod
    def get_contacts():
        if not os.path.isfile('contacts.json'):
            return [Contact("5551234", "ExampleName")]
        else:
            with open('contacts.json', 'r') as file:
                contacts = json.load(file)

        return [Contact(*c) for c in contacts]

    def post_message(self, message):
        y, x = self.screen.getyx()
        y_max, x_max = self.screen.getmaxyx()

        lines = [message[i:i + x_max] for i in range(0, len(message), x_max)]

        for line in lines:
            self.received_messages.append(line)

        if len(self.received_messages) > y_max - 1:
            self.received_messages = self.received_messages[len(lines):]

        self.screen.clear()
        self.draw_header()
        for i, msg in enumerate(self.received_messages):
            self.screen.addstr(i, 0, msg)
        self.screen.move(y, x)

    def send_message(self, message, argument=0):
        if not len(self.attached_sockets):
            self.post_message("No client sockets attached.")
        for writer in self.attached_sockets:
            writer.write(bytes([argument]))
            writer.write(bytes([len(message)]).rjust(4, b'\x00'))
            writer.write(message.encode())
            writer.drain()

    def draw_header(self):
        max_y, _ = self.screen.getmaxyx()

        name = self.lookup_by_number(self.destination_address)
        if name is not None:
            prompt = name + ": "
        else:
            prompt = self.destination_address + ": "

        self.screen.move(max_y - 1, 0)
        self.screen.clrtoeol()
        self.screen.addstr(max_y - 1, 0, prompt)
        self.screen.refresh()

    async def handle_socket(self, reader, writer):
        self.attached_sockets.append(writer)
        self.post_message("Client connected")

        try:
            while True:
                _ = await reader.read(1)  # For future use in MMS
                length = int.from_bytes((await reader.read(4)), 'big')
                # TODO: Test bad length int
                data = str((await reader.read(length)).decode())
                if data:
                    delimiter_idx = data.find("/")
                    sender = data[:delimiter_idx]
                    message = data[delimiter_idx + 1:]

                    name = self.lookup_by_number(sender)
                    if name is not None:
                        self.post_message("From " + name + ": " + message)
                    else:
                        self.post_message("From " + sender + ": " + message)
                else:
                    break
        except (KeyboardInterrupt, ConnectionResetError):
            pass
        finally:
            self.post_message("Client disconnected")
            writer.close()
            self.attached_sockets.remove(writer)

    async def user_output(self):
        message = ""

        while True:
            await sleep(0)

            try:
                key = chr(self.screen.getch())
            except ValueError:
                continue  # No key pressed
            except KeyboardInterrupt:
                break

            y_now, x_now = self.screen.getyx()
            _, x_max = self.screen.getmaxyx()

            if key == chr(10) and not message == "":
                if message == "/quit":
                    break
                else:
                    self.handle_output(message)
                    message = ""
            elif key == chr(127) and not message == "":
                message = message[:-1]
                self.screen.move(y_now, x_now - 1)
                self.screen.clrtoeol()
                self.screen.refresh()
            elif key in printable_chars and x_now < x_max - 1:
                message = message + key
                self.screen.addstr(key)

    def handle_output(self, message):
        if message[0] == "/":
            args = message.split(" ")
            if args[0] == "/x":
                self.post_message(
                    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
                    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
                    )
            elif args[0] == "/add":
                self.add_contact(args)
            elif args[0] == "/del":
                self.del_contact(args)
            elif args[0] == "/send":
                self.send_new(args)
            elif args[0] == "/list":
                self.list_contacts(args)
            else:
                self.post_message("Command unknown.")
        else:
            self.send_message(self.destination_address + "/" + message)
            name = self.lookup_by_number(self.destination_address)
            if name is not None:
                self.post_message("To " + name + ": " + message)
            else:
                self.post_message(
                    "To " + self.destination_address + ": " + message)

        self.draw_header()

    def send_new(self, args):
        if len(args) == 2:
            phone_number = self.lookup_by_name(args[1])
            if phone_number is not None:
                self.destination_address = phone_number
            else:
                self.post_message(args[1] + " not found in contacts.")
        else:
            self.post_message("Usage of /send is '/set NAME'")

    def add_contact(self, args):
        if len(args) == 3 and args[1].isdigit():
            self.contacts.append(Contact(args[1], args[2]))
            self.post_message(args[2] + " added to contacts!")
        else:
            self.post_message("Usage of /add is '/add PHONE_NUMBER NAME'")

    def del_contact(self, args):
        if len(args) == 2:
            for item in self.contacts:
                if args[1] == item.name or args[1] == item.phone_number:
                    self.contacts.remove(item)
                    self.post_message(args[1] + " deleted from contacts!")
                    return
            else:
                self.post_message(args[1] + " was not found in contacts.")
        else:
            self.post_message("Usage of /del is '/del NAME'")

    def list_contacts(self, args):
        if len(args) == 1:
            for item in self.contacts:
                self.post_message(item.name + " -> " + item.phone_number)
        else:
            self.post_message("Usage of /list is '/list'")

    def lookup_by_name(self, name):
        for item in self.contacts:
            if item.name == name:
                return item.phone_number
        else:
            return None

    def lookup_by_number(self, phone_number):
        for item in self.contacts:
            if item.phone_number == phone_number:
                return item.name
        else:
            return None

    def shutdown(self, _=None):
        for socket in self.attached_sockets:
            socket.close()
        for task in Task.all_tasks(self.loop):
            task.cancel()
        self.server.close()
        self.loop.run_until_complete(self.server.wait_closed())
        self.loop.stop()


def main(stdscr):
    Server(stdscr, 6215, 'cert/cert.pem', 'cert/key.pem')


if __name__ == "__main__":
    try:
        wrapper(main)
    except AssertionError:
        print("Certificates not found!")
