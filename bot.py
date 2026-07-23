import os, json, time
from collections import defaultdict
import discord
from discord import app_commands
from discord.ext import commands
from googletrans import Translator

TOKEN=os.getenv("DISCORD_TOKEN","YOUR_TOKEN")

USER_COOLDOWN=8
USER_MINUTE_LIMIT=10
USER_DAILY_LIMIT=100
GLOBAL_DAILY_LIMIT=1500
CACHE_HOURS=24
MAX_MESSAGE_LENGTH=1000

DATA="/data" if os.path.exists("/data") else "."
os.makedirs(DATA,exist_ok=True)

CACHE_FILE=f"{DATA}/cache.json"
USAGE_FILE=f"{DATA}/usage.json"

def load(p,d):
    if os.path.exists(p):
        return json.load(open(p))
    return d

def save(p,d):
    json.dump(d,open(p,"w"),indent=2)

cache=load(CACHE_FILE,{})
usage=load(USAGE_FILE,{"users":{},"global":0})

translator=Translator()

intents=discord.Intents.default()
bot=commands.Bot(command_prefix="!",intents=intents)

cooldowns={}
minute=defaultdict(list)

async def translate(inter:discord.Interaction,target:str):
    msg=inter.target
    if msg.author.bot:
        return await inter.response.send_message("Bots cannot be translated.",ephemeral=True)
    text=msg.content.strip()
    if not text:
        return await inter.response.send_message("No text.",ephemeral=True)
    if len(text)>MAX_MESSAGE_LENGTH:
        return await inter.response.send_message("Message too long.",ephemeral=True)

    now=time.time()
    uid=str(inter.user.id)
    if uid in cooldowns and now-cooldowns[uid]<USER_COOLDOWN:
        return await inter.response.send_message("Cooldown active.",ephemeral=True)
    cooldowns[uid]=now

    minute[uid]=[t for t in minute[uid] if now-t<60]
    if len(minute[uid])>=USER_MINUTE_LIMIT:
        return await inter.response.send_message("Minute limit reached.",ephemeral=True)
    minute[uid].append(now)

    u=usage["users"].setdefault(uid,0)
    if u>=USER_DAILY_LIMIT:
        return await inter.response.send_message("Daily limit reached.",ephemeral=True)
    if usage["global"]>=GLOBAL_DAILY_LIMIT:
        return await inter.response.send_message("Global limit reached.",ephemeral=True)

    key=f"{target}:{text}"
    if key in cache and now-cache[key]["time"]<CACHE_HOURS*3600:
        result=cache[key]["text"]
    else:
        tr=translator.translate(text,dest=target)
        result=tr.text
        cache[key]={"text":result,"time":now}
        save(CACHE_FILE,cache)

    usage["users"][uid]+=1
    usage["global"]+=1
    save(USAGE_FILE,usage)

    e=discord.Embed(title="Translation")
    e.add_field(name="Original",value=text[:1024],inline=False)
    e.add_field(name="Translated",value=result[:1024],inline=False)
    await inter.response.send_message(embed=e,ephemeral=True)

class EN(app_commands.ContextMenu):
    def __init__(self):
        super().__init__(name="Translate to English",callback=self.cb)
    async def cb(self,interaction,message):
        interaction.target=message
        await translate(interaction,"en")

class ES(app_commands.ContextMenu):
    def __init__(self):
        super().__init__(name="Translate to Spanish",callback=self.cb)
    async def cb(self,interaction,message):
        interaction.target=message
        await translate(interaction,"es")

@bot.event
async def on_ready():
    try:
        bot.tree.add_command(EN())
        bot.tree.add_command(ES())
    except:
        pass
    await bot.tree.sync()
    print(bot.user)

bot.run(TOKEN)
















