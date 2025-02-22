from util.logz import create_logger
from flask_restful import Resource

from flask import request
from jklm import JKLM
from jklm.exceptions import RoomNotFoundException

from config import (
    NICKNAME,
    CONNECTION
)

import requests
from threading import Thread

import time
import json
import hashlib

image = open("logo.png", "rb").read()
session = JKLM(NICKNAME, pfp=image, connection=json.loads(CONNECTION) if CONNECTION else None)
room_data = {}

res = requests.get("https://cdn.jsdelivr.net/gh/joseph-gerald/jklm-py-client@main/answers/popsauce_pairs.txt")
answers = {x.split(":", 1)[0]: x.split(":", 1)[1].strip() for x in res.text.split("\n") if x}

def sha1(input):
    if isinstance(input, str):
        input = input.encode()
    return hashlib.sha1(input).hexdigest()

def dispatch_bot_to(room_id):
    global session, room_data

    room_data[room_id] = { "success": None }
    room_data[room_id]["expecting_image"] = False
    room_data[room_id]["challenge"] = {
        "end_time": 0,
        "image": None,
        "prompt": None,
        "text": None,
        "hash": None
    }

    settings = {
        "auto_answer": False,
        "auto_join": False,
        "auto_announce": False,
    }

    def chat_handler(code, raw_data):
        challenge = room_data[room_id]["challenge"]

        event = raw_data[0]
        data = raw_data[1]

        # 0 CODE = Kicked from room (event = TYPE ["KICKED" | "BAN"], data = INFO)

        if (code == 0):
            print("[X] Kicked from room:", data)
            return

        match event:
            case "chat":
                message = raw_data[2]
                
                if data["peerId"] == session.peer_id:
                    return

                print(f"[CHAT] {data['nickname']}: {message}")

                if not message.startswith("!"):
                    return
                
                command = message[1:].split(" ")[0]
                args = message[1:].split(" ")[1:]

                match command:
                    case "help":
                        print(f"[!] {data['nickname']} requested help")
                        session.send_chat_message("""\\n\\n
        !help - Show this message\\n
        !join - Join the round\\n
        !settings - Show the current settings
                        """.replace("\n",""))
                        session.send_chat_message("""\\n
        !answer - answers the question\\n
        !announce - sends answer in chat\\n
        !toggle <setting> - toggles setting ON/OFF\\n
                        """.replace("\n",""))
                    case "join":
                        print(f"[!] {data['nickname']} requested to join")
                        session.join_round()
                    case "settings" | "config" | "conf":
                        print(f"[!] {data['nickname']} requested settings")
                        session.send_chat_message(f"""\\n\\n
        auto_answer: {"ON" if settings['auto_answer'] else "OFF"}\\n
        auto_join: {"ON" if settings['auto_join'] else "OFF"}\\n
        auto_announce: {"ON" if settings['auto_announce'] else "OFF"}
                        """.replace("\n",""))
                    case "toggle" | "t":
                        if len(args) == 0:
                            session.send_chat_message(f"[x] Missing setting to toggle")
                            return
                        
                        setting = args[0]

                        if (setting == "all"):
                            settings["auto_answer"] = not settings["auto_answer"]
                            settings["auto_join"] = not settings["auto_join"]
                            settings["auto_announce"] = not settings["auto_announce"]

                            session.send_chat_message(f"""\\n\\n
            auto_answer: {"ON" if settings['auto_answer'] else "OFF"}\\n
            auto_join: {"ON" if settings['auto_join'] else "OFF"}\\n
            auto_announce: {"ON" if settings['auto_announce'] else "OFF"}
                            """.replace("\n",""))
                            return

                        # add suport for missing undderscores e.g auto_join can be shortened to autojoin

                        for _setting in settings:
                            if setting == _setting.replace("_", ""):
                                setting = _setting
                                break

                        if setting not in settings:
                            session.send_chat_message(f"[x] Unknown setting: {setting}")
                            return
                        
                        settings[setting] = not settings[setting]
                        
                        status = "ON" if settings[setting] else "OFF"
                        session.send_chat_message(f"\\n\\n         [x] Set {setting} to {status}\\n\\n")
                    case "answer":
                        if not challenge["answer"]:
                            session.send_chat_message(f"[x] No answer indexed for this challenge")
                            return
                        else:
                            session.submit_guess(challenge["answer"])
                    case "announce":
                        if not challenge["answer"]:
                            session.send_chat_message(f"[x] No answer indexed for this challenge")
                            return
                        else:
                            session.send_chat_message(f"\\n         [o] The answer is: {challenge['answer']}\\n")
                    case _:
                        session.send_chat_message(f"[x] Unknown command: {command}")

            case "chatterAdded":
                print(f"[+] {data} joined the room")
            case "chatterRemoved":
                print(f"[-] {data} left the room")
            case "setPlayerCount":
                print(f"[!] {data} players in the room")
            case _:
                print(f"[UNHANDLED CHAT EVENT] {event}:", data)

    def game_handler(code, raw_data):
        challenge = room_data[room_id]["challenge"]
        expecting_image = room_data[room_id]["expecting_image"]
        event = raw_data[0]
        data = raw_data[1]

        # -1 CODE = Image data
        # 0 CODE = Kicked from room (event = TYPE ["KICKED" | "BAN"], data = INFO)

        if (code == 0):
            print("[X] Kicked from room:", data)
            return

        if (code == -1):
            if challenge == None or challenge["image"] == None:
                return
            
            asset_type = challenge["image"]["type"]
            extension = ""

            match asset_type:
                case "image/svg+xml":
                    extension = "svg"
                case "image/png":
                    extension = "png"
                case "image/jpeg":
                    extension = "jpeg"

            challenge["hash"] = sha1(challenge["prompt"].encode() + raw_data)
            challenge["image"]["extension"] = extension

            print("[?] Challenge Hash:", challenge["hash"])
            
            answer = answers.get(challenge["hash"])
            challenge["answer"] = answer

            if answer:
                print("[!] Answer is indexed:", answer)

                if settings["auto_answer"]:
                    session.submit_guess(answer)

                if settings["auto_announce"]:
                    session.send_chat_message(f"[o] The answer is: {answer}")
            else:
                print("[!] Answer was not indexed")
                session.send_chat_message(f"[x] No answer indexed for this challenge")

            room_data[room_id]["expecting_image"] = False

            return

        match event:
            case "startChallenge":
                print("\n[!] New Challenge Started")

                challenge["end_time"] = data["endTime"] if "endTime" in data else 0
                challenge["image"] = data["image"]
                challenge["prompt"] = data["prompt"]
                challenge["text"] = data["text"]

                if challenge["image"]:
                    expecting_image = True
                    print("[?] Image Challenge", challenge["prompt"])
                else:
                    expecting_image = False
                    challenge["hash"] = sha1(challenge["prompt"] + challenge["text"])

                    print("[?] Text Challenge:", challenge["prompt"])
                    print("[?] Challenge Hash:", challenge["hash"])
                    print("[?]", challenge["text"])

                    answer = answers.get(challenge["hash"])
                    challenge["answer"] = answer
        
                    if answer:
                        print("[!] Answer is indexed:", answer)

                        if settings["auto_answer"]:
                            session.submit_guess(answer)

                        if settings["auto_announce"]:
                            session.send_chat_message(f"[o] The answer is: {answer}")
                    else:
                        print("[!] Answer was not indexed")
                        session.send_chat_message(f"[x] No answer indexed for this challenge")


            case "endChallenge":
                return
                print("\n[!] Challenge Ended")
                print("[X] Correct Answer:", data["source"])
                
            case "setPlayerState":
                return
                event, peer_id, data = raw_data
                    
                guess = data["guess"]
                found_answer = data["hasFoundSource"]
                points = data["points"]
                elapsed_time = data["elapsedTime"]

                if (peer_id == session.peer_id):
                    return

                print(f"[!] {peer_id} {data}")
                
                if peer_id == session.peer_id:
                    return

                player = list(filter(lambda x: x["profile"]["peerId"] == peer_id, session.game["players"]))[0]

                if found_answer:
                    print(f"[!] {player['profile']['nickname']} with {points} points guessed it in {elapsed_time} seconds")
                else:
                    print(f"[!] {player['profile']['nickname']} with {points} points guessed {guess}")

            case "updatePlayer":
                return
                event, peer_id, data, online = raw_data

                player = list(filter(lambda x: x["profile"]["peerId"] == peer_id, session.game["players"]))[0]

                if online:
                    print(f"[+] {player['profile']['nickname']} reconnected to the game")
                else:
                    print(f"[-] {player['profile']['nickname']} disconnected from the game")

            case "addPlayer":
                return
                print(f"[+] {data['profile']['nickname']} joined the game")

            case "setMilestone":
                if settings["auto_join"]:
                    session.send_chat_message(f"[!] Automatically joining round")
                    session.join_round()

            case _:
                print(f"[UNHANDLED GAME EVENT] {event}:", raw_data)

        room_data[room_id]["expecting_image"] = expecting_image
        room_data[room_id]["challenge"] = challenge

    try:
        challenge = room_data[room_id]["challenge"]
        expecting_image = room_data[room_id]["expecting_image"]

        session.connect(room_id, chat_handler=chat_handler, game_handler=game_handler)
        # Checks if a challenge is already started

        if ("challenge" in session.game["milestone"]):
            print("\n[!] Challenge already started")
            
            current_challenge = session.game["milestone"]["challenge"]
            
            # If the challenge has ended but the next one hasn't started yet endTime will be null
            challenge["end_time"] = current_challenge["endTime"] if "endTime" in current_challenge else 0
            challenge["image"] = current_challenge["image"]
            challenge["prompt"] = current_challenge["prompt"]
            challenge["text"] = current_challenge["text"]

            if challenge["image"]:
                expecting_image = True
                print("[?] Image Challenge", challenge["prompt"])
            else:
                expecting_image = False

                challenge["hash"] = sha1(challenge["prompt"] + challenge["text"])

                print("[?] Text Challenge:", challenge["prompt"])
                print("[?]", challenge["text"])
                print("[?] Challenge Hash:", challenge["hash"])

        room_data[room_id]["expecting_image"] = expecting_image
        room_data[room_id]["challenge"] = challenge

        session.send_chat_message("""\\n\\n
        POPBOT - v1.0.0\\n
        Do !help to see available commands\\n
        
        """.replace("\n",""))
        room_data[room_id]["success"] = True
    except Exception as e:
        room_data[room_id]["success"] = False
        print("[X] Failed to dispatch:", e)
        return
    
class DispatchBot(Resource):
    def __init__(self):
        self.logger = create_logger()

    def post(self):
        data = request.json
        self.logger.info(f"Received request: {data}")
        
        code = data.get("code")

        if code is None:
            self.logger.error("No code provided")
            return {"error": "No code provided"}, 400

        if len(code) != 4:
            self.logger.error("Invalid code length")
            return {"error": "Invalid code length"}, 400
        
        try:
            res = session.get_room_server(code)
        except RoomNotFoundException:
            res = None

        if res is None:
            self.logger.error("No room found")
            return {"error": "Room not found"}, 404
        
        thread = Thread(target=dispatch_bot_to, args=(code,))
        thread.start()

        while room_data.get(code) is None or room_data[code].get("success") is None:
            time.sleep(0.1)
        
        success = room_data[code]["success"]

        if not success:
            self.logger.error("Failed to dispatch bot")
            return {"error": "Failed to dispatch bot"}, 500
        else:
            self.logger.info("Bot dispatched successfully")
            return {"message": "Bot dispatched"}, 200

