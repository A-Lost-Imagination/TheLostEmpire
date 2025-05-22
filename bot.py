import random
import re
from datetime import datetime
from telebot import TeleBot, types
from pymongo import MongoClient

# ============================= #
#     #ADMIN_AUTHORISATION     #
# ============================= #

import os
from dotenv import load_dotenv
from telebot import TeleBot
from pymongo import MongoClient

# Load environment variables from .env file
load_dotenv()

# Read from environment
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

# Setup bot
bot = TeleBot(BOT_TOKEN)

# Authorized users and admins
AUTHORIZED_USERS = {7545214543, 7552178223, 5053815620, 5236728354}
ADMINS = {7545214543, 7552178223, 5053815620, 5236728354}

# MongoDB Setup
client = MongoClient(MONGO_URI)
db = client['your_database']
users_col = db['users']
inventory_col = db['inventory']


# ============================ #
#      GLOBAL MEMORY TRACKERS #
# ============================ #

user_last_message_id = {}
user_used_callbacks = {}

# ========================== #
#   #IMAGE_AND_VIDEO_URLS   #
# ========================== #

IMAGES = {
    'start_img': 'https://t.me/TheLostEmpireUpdates/2',
    'welcome_img': 'https://t.me/TheLostEmpireUpdates/4',
    'gender_img': 'https://t.me/TheLostEmpireUpdates/6',
    'destination_img': 'https://t.me/TheLostEmpireUpdates/5',
    'north_img': 'https://t.me/TheLostEmpireUpdates/8',
    'south_img': 'https://t.me/TheLostEmpireUpdates/7',
    'west_img': 'https://t.me/TheLostEmpireUpdates/10',
    'east_img': 'https://t.me/TheLostEmpireUpdates/9'
}

# ===================== #
#     #INITIAL_SETUP    #
# ===================== #

@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id

    if user_id not in AUTHORIZED_USERS:
        bot.reply_to(message, "You are not authorized to use this bot.")
        return

    existing_user = users_col.find_one({"_id": user_id})

    if existing_user and existing_user.get("destination"):
        bot.reply_to(message, "You have already started the bot.")
        return

    markup = types.ForceReply(selective=False)
    sent = bot.send_photo(message.chat.id, IMAGES['start_img'],
        caption="Welcome to The Lost Empire!\nPlease provide your 'Player Name' to proceed",
        reply_markup=markup)
    user_last_message_id[user_id] = sent.message_id


@bot.message_handler(func=lambda msg: msg.reply_to_message and msg.reply_to_message.caption and "Player Name" in msg.reply_to_message.caption)
def receive_player_name(message):
    user_id = message.from_user.id
    name = message.text.strip()

    users_col.replace_one({"_id": user_id}, {
        "_id": user_id,
        "player_name": name,
        "join_date": datetime.now().strftime("%d/%m/%Y"),
        "gender": None,
        "destination": None,
        "energy": 100,
        "exp": 0,
        "status": "None",
        "health": 100
    }, upsert=True)

    inventory_col.replace_one({"_id": user_id}, default_inventory(user_id), upsert=True)

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Answer The Questions", callback_data="take_test"))
    sent = bot.send_photo(user_id, IMAGES['welcome_img'],
        caption=f"Mmm... Another traveler, eh?\nYou must be {name}\nAnswer two questions, and I shall open the gates for you!",
        reply_markup=markup)
    user_last_message_id[user_id] = sent.message_id


@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    msg_id = call.message.message_id
    data = call.data

    # Prevent repeated button use
    if user_id in user_used_callbacks and data in user_used_callbacks[user_id]:
        bot.answer_callback_query(call.id, "You cannot go back to the past!", show_alert=True)
        return

    # Delete previous bot message if exists
    if user_id in user_last_message_id:
        try:
            bot.delete_message(user_id, user_last_message_id[user_id])
        except Exception:
            pass  # Ignore if message already deleted

    user_last_message_id[user_id] = msg_id
    user_used_callbacks.setdefault(user_id, set()).add(data)

    if data == "take_test":
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("Male", callback_data="gender_male"),
            types.InlineKeyboardButton("Female", callback_data="gender_female"),
            types.InlineKeyboardButton("Dead", callback_data="gender_third")
        )
        sent = bot.send_photo(user_id, IMAGES['gender_img'],
            caption="Tell me—are you a boy, a girl, or... something else?", reply_markup=markup)
        user_last_message_id[user_id] = sent.message_id

    elif data.startswith("gender_"):
        gender = data.split("_")[1]
        users_col.update_one({"_id": user_id}, {"$set": {"gender": gender}})

        caption = {
            "male": "A young boy, eh? Where are you headed?",
            "female": "A young lady out here? Brave. Where to now?",
            "third": "A dead one? Fascinating. Where to now?"
        }.get(gender, "Where are you headed?")

        markup = types.InlineKeyboardMarkup()
        for d in ["East", "West", "North", "South", "Random"]:
            markup.add(types.InlineKeyboardButton(d, callback_data=f"dest_{d.lower()}"))
        sent = bot.send_photo(user_id, IMAGES['destination_img'], caption=caption, reply_markup=markup)
        user_last_message_id[user_id] = sent.message_id

    elif data.startswith("dest_"):
        dest = data.split("_")[1]
        if dest == "random":
            dest = random.choice(["east", "west", "north", "south"])

        users_col.update_one({"_id": user_id}, {"$set": {"destination": dest, "status": "Traveler"}})
        inventory_col.update_one({"_id": user_id}, {"$inc": {"coins": 1000, "bread": 1, "meat": 1, "beer": 1}})

        suffix = {"north": "North☃️", "south": "South🏜️", "west": "West🏝️", "east": "East🏔️"}.get(dest, dest)

        bot.send_message(user_id, "Before you go, the old man gave you a gift!\n\n🪙 Coins: +1000\n🍞 Bread: +1\n🍗 Meat: +1\n🍺 Beer: +1")
        bot.send_photo(user_id, IMAGES[f"{dest}_img"], caption=f"Welcome to the {suffix}")

# ===================== #
#        ME_PAGE         #
# ===================== #

@bot.message_handler(commands=['me'])
def show_me(message):
    user_id = message.from_user.id
    user_data = users_col.find_one({"_id": user_id})
    if not user_data:
        bot.reply_to(message, "You haven't started the game yet. Use /start.")
        return

    gender_map = {"male": "Male", "female": "Female", "third": "Unknown"}
    gender = gender_map.get(user_data.get("gender"), "Unknown")
    location = {"north": "North☃️", "south": "South🏜️", "west": "West🏝️", "east": "East🏔️"}.get(user_data.get("destination", ""), "Unknown")

    response = f"""📚 My Information:

• Name - {user_data.get("player_name", "Unknown")}
• Gender - {gender}
• ID - {user_id}

• Energy - {user_data.get("energy", 100)}
• Health - {user_data.get("health", 100)}
• Exp - {user_data.get("exp", 0)}

• Status - {user_data.get("status", "none")}
• Location - {location}
• Languages - English

Joined on : {user_data.get("join_date", "Unknown")}"""
    bot.reply_to(message, response)


# ===================== #
#        INVENTORY        #
# ===================== #

@bot.message_handler(commands=['inv'])
def inventory_cmd(message):
    user_id = message.from_user.id
    inv = inventory_col.find_one({"_id": user_id})
    user = users_col.find_one({"_id": user_id})
    if not inv or not user:
        bot.reply_to(message, "You haven't started the game yet.")
        return

    text = (
        f"Inventory : {user['player_name']}\n\n"
        f"🪙 Coins : {inv['coins']}\n"
        f"⚜️ Gold : {inv['gold']}\n"
        f"💎 Diamond : {inv['diamond']}\n\n"
        f"🍞 Bread : {inv['bread']}\n"
        f"🍗 Meat : {inv['meat']}\n"
        f"🍺 Beer : {inv['beer']}\n\n"
        f"⚒️ Weapon : {inv['weapon']}\n"
        f"🧬 Potion : {inv['potion']}"
    )
    bot.reply_to(message, text)

def default_inventory(user_id):
    return {
        "_id": user_id,
        "coins": 0,
        "gold": 0,
        "diamond": 0,
        "bread": 0,
        "meat": 0,
        "beer": 0,
        "weapon": "none",
        "potion": "none"
    }

# ===================== #
#    ADMIN_COMMANDS     #
# ===================== #

@bot.message_handler(commands=['auth'])
def authorize_user(message):
    if message.from_user.id in ADMINS:
        try:
            user_id = int(message.text.split()[1])
            AUTHORIZED_USERS.add(user_id)
            bot.reply_to(message, f"User {user_id} has been authorized.")
        except:
            bot.reply_to(message, "Invalid format. Use /auth <user_id>")

@bot.message_handler(commands=['unauth'])
def unauthorize_user(message):
    if message.from_user.id in ADMINS:
        try:
            user_id = int(message.text.split()[1])
            AUTHORIZED_USERS.discard(user_id)
            bot.reply_to(message, f"User {user_id} has been unauthorized.")
        except:
            bot.reply_to(message, "Invalid format. Use /unauth <user_id>")

@bot.message_handler(commands=['admin'])
def add_admin(message):
    if message.from_user.id in ADMINS:
        try:
            user_id = int(message.text.split()[1])
            ADMINS.add(user_id)
            AUTHORIZED_USERS.add(user_id)
            bot.reply_to(message, f"User {user_id} added as admin.")
        except:
            bot.reply_to(message, "Invalid format. Use /admin <user_id>")

@bot.message_handler(commands=['unadmin'])
def remove_admin(message):
    if message.from_user.id in ADMINS:
        try:
            user_id = int(message.text.split()[1])
            ADMINS.discard(user_id)
            bot.reply_to(message, f"User {user_id} removed from admin.")
        except:
            bot.reply_to(message, "Invalid format. Use /unadmin <user_id>")

@bot.message_handler(commands=['reset'])
def reset_game(message):
    user_id = message.from_user.id

    users_col.delete_one({"_id": user_id})
    inventory_col.delete_one({"_id": user_id})

    # Clear in-memory states for this user
    user_last_message_id.pop(user_id, None)
    user_used_callbacks.pop(user_id, None)

    bot.reply_to(message, "Your game has been reset. Send /start to begin a new adventure!")

@bot.message_handler(commands=['add'])
def add_item(message):
    if message.from_user.id not in ADMINS:
        bot.reply_to(message, "You are not authorized to use this command.")
        return

    try:
        args = message.text.split()
        if len(args) < 4:
            bot.reply_to(message, "Invalid format. Use /add \"item\" \"quantity\" <user_id>")
            return

        item = args[1].lower()
        quantity = args[2]
        user_id = int(args[3])

        if item not in ['coins', 'gold', 'diamond', 'bread', 'meat', 'beer', 'weapon', 'potion']:
            bot.reply_to(message, f"Invalid item name: {item}")
            return

        if item in ['weapon', 'potion']:
            # Set string value instead of incrementing
            inventory_col.update_one({"_id": user_id}, {"$set": {item: quantity}})
            bot.reply_to(message, f"{item.title()} has been set to '{quantity}' for user {user_id}.")
        else:
            quantity = int(quantity)
            inventory_col.update_one({"_id": user_id}, {"$inc": {item: quantity}})
            bot.reply_to(message, f"Added {quantity} {item} to user {user_id}.")
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")

@bot.message_handler(commands=['change'])
def change_user_field(message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        bot.reply_to(message, "You are not authorized to use this command.")
        return

    try:
        # Command format: /change <user_id> <field> <new_value>
        args = message.text.split(maxsplit=3)
        if len(args) < 4:
            bot.reply_to(message, "Invalid format. Use /change <user_id> <field> <new_value>")
            return

        target_user_id = int(args[1])
        field = args[2].lower()
        new_value = args[3]

        allowed_fields = {'energy', 'health', 'exp', 'status', 'destination'}

        if field not in allowed_fields:
            bot.reply_to(message, f"Field '{field}' cannot be changed or doesn't exist.")
            return

        # Convert numeric fields to int
        if field in {'energy', 'health', 'exp'}:
            new_value = int(new_value)

        # Update in DB
        users_col.update_one({"_id": target_user_id}, {"$set": {field: new_value}})

        bot.reply_to(message, f"User {target_user_id}'s {field} has been updated to {new_value}.")

    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")


from datetime import datetime, timedelta

# TRAVEL_CMD
allowed_destinations = ['north', 'south', 'east', 'west']  # example valid places

@bot.message_handler(commands=['travel'])
def travel_command(message):
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        bot.reply_to(message, "Please specify a destination. Usage: /travel <destination>")
        return

    destination = args[1].strip().lower()

    if destination not in allowed_destinations:
        bot.reply_to(message, f"'{destination}' is not a valid destination. Allowed: {', '.join(allowed_destinations)}")
        return

    # Fetch user data
    user_data = users_col.find_one({"_id": user_id})
    if not user_data:
        bot.reply_to(message, "You haven't started the game yet. Use /start to begin.")
        return

    # Status check
    status = user_data.get("status", "Traveler")
    if status != "Traveler":
        bot.reply_to(message, "You cannot travel to other kingdom without a travel pass!")
        return

    # Cooldown check
    last_travel = user_data.get("last_travel")
    if last_travel:
        last_travel_dt = datetime.strptime(last_travel, "%Y-%m-%d %H:%M:%S")
        if datetime.utcnow() - last_travel_dt < timedelta(hours=24):
            remaining = timedelta(hours=24) - (datetime.utcnow() - last_travel_dt)
            hours, remainder = divmod(remaining.seconds, 3600)
            minutes = remainder // 60
            bot.reply_to(message, f"You can travel again in {remaining.days}d {hours}h {minutes}m.")
            return

    # Coin check
    inv = inventory_col.find_one({"_id": user_id})
    coins = inv.get("coins", 0) if inv else 0
    if coins < 1000:
        bot.reply_to(message, f"You need 1000 coins to travel, but you only have {coins}.")
        return

    # Deduct 1000 coins and update destination and timestamp
    inventory_col.update_one({"_id": user_id}, {"$inc": {"coins": -1000}})
    users_col.update_one({"_id": user_id}, {
        "$set": {
            "destination": destination,
            "last_travel": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        }
    })
    # Destination image URLs + emojis
    welcome_data = {
        "north": {
            "image": "https://t.me/TheLostEmpireUpdates/8",
            "caption": "Welcome to the North☃️"
        },
        "south": {
            "image": "https://t.me/TheLostEmpireUpdates/7",
            "caption": "Welcome to the South🏜️"
        },
        "east": {
            "image": "https://t.me/TheLostEmpireUpdates/9",
            "caption": "Welcome to the East🏔️"
        },
        "west": {
            "image": "https://t.me/TheLostEmpireUpdates/10",
            "caption": "Welcome to the West🏝️"
        }
    }

    welcome = welcome_data.get(destination)
    if welcome:
        bot.send_photo(user_id, welcome["image"], caption=welcome["caption"])
        bot.send_message(user_id, f"✅ Your destination has been set to {destination.capitalize()}. 1000 coins have been deducted.")



# =============== #
#     POLLING     #
# =============== #

bot.infinity_polling(skip_pending=True)

