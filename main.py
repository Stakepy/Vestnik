import discord
from discord.ext import commands, tasks
import asyncio
import requests
from bs4 import BeautifulSoup
import os
import sys
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

ALLOWED_GUILD_IDS = [guild_id]
VOICE_CHANNELS = {guild_id: voice_id}
TELEGRAM_URL = "https://t.me/s/sirena_dp"

SIREN_START_AUDIO = "siren/siren_start.mp3"
SIREN_END_AUDIO = "siren/siren_end.mp3"
LOGIN_AUDIO = "siren/login.mp3"

LAST_PROCESSED_MESSAGE_TIME = None


@bot.event
async def on_ready():
    print(f"Бот {bot.user} готов к работе!")
    bot.loop.create_task(stay_in_voice())
    check_siren.start()
    await bot.tree.sync()
    await play_login_audio()


async def stay_in_voice():
    while True:
        for guild_id, channel_id in VOICE_CHANNELS.items():
            guild = bot.get_guild(guild_id)
            if guild:
                channel = guild.get_channel(channel_id)
                if channel:
                    voice_client = guild.voice_client
                    if not voice_client or not voice_client.is_connected() or voice_client.channel.id != channel_id:
                        if voice_client:
                            await voice_client.disconnect()
                        try:
                            await channel.connect()
                            print(f"Подключился к каналу {channel.name}")
                        except discord.ClientException as e:
                            print(f"Ошибка подключения: {e}")
        await asyncio.sleep(5)


@tasks.loop(seconds=30)
async def check_siren():
    global LAST_PROCESSED_MESSAGE_TIME
    try:
        response = requests.get(TELEGRAM_URL, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        messages = soup.find_all('div', class_='tgme_widget_message_wrap js-widget_message_wrap')

        if messages:
            latest_message = messages[-1]
            message_time = datetime.fromisoformat(latest_message.find('time', class_='time')['datetime'])
            message_text = latest_message.find('div', class_='tgme_widget_message_text').text

            if LAST_PROCESSED_MESSAGE_TIME is None or message_time > LAST_PROCESSED_MESSAGE_TIME:
                LAST_PROCESSED_MESSAGE_TIME = message_time
                if "Оголошено тривогу" in message_text:
                    await play_audio(SIREN_START_AUDIO)
                elif "ВІДБІЙ ТРИВОГИ" in message_text:
                    await play_audio(SIREN_END_AUDIO)
    except requests.RequestException as e:
        print(f"Ошибка запроса Telegram: {e}")


async def play_audio(file_path):
    print(f"Попытка воспроизведения: {file_path}")
    for guild_id in VOICE_CHANNELS:
        guild = bot.get_guild(guild_id)
        if guild:
            voice_client = guild.voice_client
            if voice_client and voice_client.is_connected():
                if not voice_client.is_playing():
                    try:
                        voice_client.play(discord.FFmpegPCMAudio(file_path))
                        print(f"Воспроизводится аудио: {file_path}")
                    except Exception as e:
                        print(f"Ошибка воспроизведения: {e}")
                else:
                    print("Бот уже воспроизводит аудио")
            else:
                print("Бот не подключен к голосовому каналу")


async def play_login_audio():
    await asyncio.sleep(5)
    await play_audio(LOGIN_AUDIO)


@bot.tree.command(name="restart", description="Перезапуск бота")
async def restart(interaction: discord.Interaction):
    if interaction.guild_id not in ALLOWED_GUILD_IDS:
        await interaction.response.send_message("Эта команда недоступна.")
        return
    await interaction.response.send_message("Перезапуск...")
    await play_audio(LOGIN_AUDIO)
    os.execv(sys.executable, ['python'] + sys.argv)


@bot.event
async def on_voice_state_update(member, before, after):
    if member == bot.user:
        guild_id = before.channel.guild.id if before.channel else after.channel.guild.id
        if guild_id in VOICE_CHANNELS:
            target_channel_id = VOICE_CHANNELS[guild_id]
            if after.channel and after.channel.id != target_channel_id:
                target_channel = bot.get_channel(target_channel_id)
                if target_channel:
                    await member.move_to(target_channel)
            elif not after.channel:
                target_channel = bot.get_channel(target_channel_id)
                if target_channel:
                    await target_channel.connect()


async def main():
    TOKEN = "token"
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
