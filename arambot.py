import discord
from discord import app_commands
import requests
import random
import matplotlib.pyplot as plt
from PIL import Image
from io import BytesIO
import numpy as np
import math
import asyncio
from dc_serverinfo import discord_guild_id, discord_bot_token, image_channel_or_user_id
import difflib

# Set up Discord client and command tree with default intents
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

def create_champion_grid(team, latest_version):
    # Generates a grid image of champion icons for a given team.

    num_champs = len(team)
    cols = math.ceil(math.sqrt(num_champs))
    rows = math.ceil(num_champs / cols)

    # Create a matplotlib figure with subplots for each champion
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 3, rows * 3.5), facecolor='black')
    fig.subplots_adjust(hspace=0.3, wspace=0.1)
    axes = axes.flatten()

    for i, champ in enumerate(team):
        # Download champion icon from riot API
        img_url = f"https://ddragon.leagueoflegends.com/cdn/{latest_version}/img/champion/{champ[1]}.png"
        response = requests.get(img_url)
        img = Image.open(BytesIO(response.content))
        axes[i].imshow(np.array(img))
        axes[i].axis('off')
        # Add champion name below the icon
        # Use a smaller font size for long champion names
        name = champ[0]
        voffset = -0.08 if len(name) > 11 else -0.05
        fontsize = 24 if len(name) > 11 else 30
        axes[i].text(0.5, voffset, name, fontsize=fontsize, color='white', ha='center', va='top', transform=axes[i].transAxes, wrap=True)

    # Hide any unused axis (this prevents white squares in empty spaces of the grid)
    for j in range(num_champs, len(axes)):
        axes[j].axis('off')

    plt.tight_layout()
    img_buffer = BytesIO()
    plt.savefig(img_buffer, format='png', facecolor='black', edgecolor='none', bbox_inches='tight', pad_inches=0.1)
    img_buffer.seek(0)
    plt.close()

    return img_buffer

class TeamButtons(discord.ui.View):
    # Discord UI View for showing buttons to reveal each team's champions.

    def __init__(self, team1_img, team2_img):
        super().__init__(timeout=180)  # Set timeout to 180 seconds
        self.team1_img = team1_img
        self.team2_img = team2_img

    async def on_timeout(self):
        # Called when the view times out; deletes the message if possible
        try:
            global team1_url, team2_url, userOrChannel
            # Post Team 1 image to the channel
            embed_team1 = discord.Embed(title="Team 1", color=discord.Color.blue())
            if userOrChannel:
                embed_team1.set_image(url=team1_url)
                await self.message.channel.send(embed=embed_team1)
            else:
                file_team1 = discord.File(BytesIO(self.team1_img.getvalue()), filename="team1.png")
                embed_team1.set_image(url="attachment://team1.png")
                await self.message.channel.send(file=file_team1, embed=embed_team1)

            # Post Team 2 image to the channel
            embed_team2 = discord.Embed(title="Team 2", color=discord.Color.red())
            if userOrChannel:
                embed_team2.set_image(url=team2_url)
                await self.message.channel.send(embed=embed_team2)
            else:
                file_team2 = discord.File(BytesIO(self.team2_img.getvalue()), filename="team2.png")
                embed_team2.set_image(url="attachment://team2.png")
                await self.message.channel.send(file=file_team2, embed=embed_team2)

            # Clean up image buffers
            self.team1_img.close()
            self.team2_img.close()
        except:
            pass
        try:
            await self.message.delete()
        except discord.errors.NotFound:
            pass  # Message was already deleted

    @discord.ui.button(label="Team 1", style=discord.ButtonStyle.primary)
    async def team1_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        global team1_url,userOrChannel
        # Show Team 1's champions as an ephemeral embed
        embed = discord.Embed(title="Team 1")
        if userOrChannel:
            embed.set_image(url=team1_url)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            file = discord.File(BytesIO(self.team1_img.getvalue()), filename="team1.png")
            embed.set_image(url="attachment://team1.png")
            await interaction.response.send_message(file=file, embed=embed, ephemeral=True)

    @discord.ui.button(label="Team 2", style=discord.ButtonStyle.red)
    async def team2_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        global team2_url,userOrChannel
        # Show Team 2's champions as an ephemeral embed
        embed = discord.Embed(title="Team 2")
        if userOrChannel:
            embed.set_image(url=team2_url)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            file = discord.File(BytesIO(self.team2_img.getvalue()), filename="team2.png")
            embed.set_image(url="attachment://team2.png")
            await interaction.response.send_message(file=file, embed=embed, ephemeral=True)

# Bot Startup event
@client.event
async def on_ready():
    # Sync commands when the bot is ready
    await tree.sync(guild=discord.Object(id=discord_guild_id))
    print("Bot primed and ready!")

# Command parameter definitions
@tree.command(name="aramroll", description="Get random ARAM champions", guild=discord.Object(id=discord_guild_id))
@app_commands.describe(
    champions_per_team="Number of champions for Team 1 (between 1 and 81).",
    champions_per_team_2="Number of champions for Team 2 (between 0 and 81, default: Same as Team 1).",
    allow_overlap="Allow overlap between teams (default: False).",
    ban_role="Ban role (default: None, options: Tank, Mage, Marksman, Fighter, Assassin, Support). Spaces and minor spelling errors don't matter.",
    strict_role_bans="Also ban champs with banned role as secondary role (default: True, options: True/False).",
    ban_champions="Comma-separated list of champion names to ban (default: None). Spaces and minor spelling errors don't matter."
)
@app_commands.choices(
    allow_overlap=[
        app_commands.Choice(name="False", value=0),
        app_commands.Choice(name="True", value=1)
    ],
    strict_role_bans=[
        app_commands.Choice(name="False", value=0),
        app_commands.Choice(name="True", value=1)
    ]
)

# Autocomplete for ban_role parameter, but didn't get it working yet.
#async def ban_role_autocomplete(interaction: discord.Interaction, current: str):
#    roles = [
#        app_commands.Choice(name="Tanks", value="Tank"),
#        app_commands.Choice(name="Mages", value="Mage"),
#        app_commands.Choice(name="Marksmen", value="Marksman"),
#        app_commands.Choice(name="Fighters", value="Fighter"),
#        app_commands.Choice(name="Assassins", value="Assassin"),
#        app_commands.Choice(name="Supports", value="Support")
#    ]
#    # Optionally filter by current input
#    return [role for role in roles if current.lower() in role.name.lower()]
#@app_commands.autocomplete(
#    ban_role=ban_role_autocomplete
#)

# Slash command to roll random ARAM teams and display them with images.
async def slash_command(
    interaction: discord.Interaction,
    champions_per_team: int,
    champions_per_team_2: int = None,
    allow_overlap: app_commands.Choice[int] = 0,
    ban_role: str = None,
    strict_role_bans: app_commands.Choice[int] = 1,
    ban_champions: str = None,
):
    try:
        strict_role_bans = strict_role_bans.value
    except: 
        pass
    try:
        allow_overlap = allow_overlap.value
    except:
        pass


    # Use champions_per_team_2 if provided, otherwise use champions_per_team for both teams
    if champions_per_team_2 is None:
        champions_per_team_2 = champions_per_team
    if (
        champions_per_team < 1 or champions_per_team > 81
        or champions_per_team_2 < 0 or champions_per_team_2 > 81
    ):
        await interaction.response.send_message("Please choose a number between 1/0 and 81 for both teams.")
        return

    await interaction.response.defer()  # Defer response for processing

    # Fetch latest League of Legends Version from Riot API
    versions_url = "https://ddragon.leagueoflegends.com/api/versions.json"
    response = requests.get(versions_url)
    versions = response.json()
    latest_version = versions[0]

    # Fetch champion data for the latest version
    champion_url = f"https://ddragon.leagueoflegends.com/cdn/{latest_version}/data/en_US/champion.json"
    champion_response = requests.get(champion_url)
    champion_data = champion_response.json()



    # Prepare role bans only if ban_role is set
    normalized_ban_roles = set()
    if ban_role:
        input_roles = [role.strip().lower() for role in ban_role.split(",")]
        valid_roles = ["tank", "mage", "marksman", "fighter", "assassin", "support"]
        for r in input_roles:
            match = difflib.get_close_matches(r, valid_roles, n=1, cutoff=0.6)
            if match:
                normalized_ban_roles.add(match[0].capitalize())

    # Prepare champion name bans only if ban_champions is set
    ban_champ_names = set()
    if ban_champions:
        input_champs = [c.strip().lower() for c in ban_champions.split(",")]
        champ_name_map = {champ['name'].lower(): champ['id'] for champ in champion_data['data'].values()}
        for c in input_champs:
            match = difflib.get_close_matches(c, champ_name_map.keys(), n=1, cutoff=0.7)
            if match:
                ban_champ_names.add(match[0])

    filtered_cnames = []
    for champ in champion_data['data'].values():
        champ_tags = champ.get("tags", [])
        champ_name_lower = champ['name'].lower()
        # Ban if champion name is in ban_champ_names
        if  champ_name_lower in ban_champ_names:
            continue
        if normalized_ban_roles:
            if strict_role_bans:
                # Remove if any tag matches
                if not set(champ_tags).intersection(normalized_ban_roles):
                    filtered_cnames.append([champ['name'], champ['id']])
            else:
                # Only consider the first tag
                if not (champ_tags and champ_tags[0] in normalized_ban_roles):
                    filtered_cnames.append([champ['name'], champ['id']])
        else:
            filtered_cnames.append([champ['name'], champ['id']])
    cnames = filtered_cnames

    
    if allow_overlap:
        if len(cnames) < max(champions_per_team, champions_per_team_2):
            await interaction.followup.send(f"There are only {len(cnames)} champions available after bans, which is fewer than the {max(champions_per_team, champions_per_team_2)} requested.")
            return
    else:
        if len(cnames) < (champions_per_team + champions_per_team_2):
            await interaction.followup.send(f"There are only {len(cnames)} champions available after bans, which is fewer than the {champions_per_team + champions_per_team_2} requested.")
            return

    random.shuffle(cnames)  # Shuffle for randomness

    # Split into two teams with possibly different sizes
    team1 = cnames[:champions_per_team]
    if allow_overlap:
        random.shuffle(cnames)  # Shuffle again if allowing overlap
        team2 = cnames[:champions_per_team]
    else:
        team2 = cnames[champions_per_team:champions_per_team + champions_per_team_2]

    if champions_per_team == champions_per_team_2:
        m1 = f"Teams with {champions_per_team} champions each have been rolled."
    else:
        m1 = f"Teams with {champions_per_team} and {champions_per_team_2} champions have been rolled."

    # Sort teams alphabetically by champion name
    team1 = sorted(team1, key=lambda x: x[0])
    team2 = sorted(team2, key=lambda x: x[0])

    # Generate images for both teams
    team1_img = create_champion_grid(team1, latest_version)
    if champions_per_team_2:
        team2_img = create_champion_grid(team2, latest_version)
    else:
        team2_img = create_champion_grid(team1, latest_version)

    # Specify the channel ID where images should be sent
    global userOrChannel
    try:
        userOrChannel = await client.fetch_user(image_channel_or_user_id)
    except discord.NotFound:
        try:
            userOrChannel = await client.fetch_channel(image_channel_or_user_id)
        except discord.NotFound:
            userOrChannel = None

    if userOrChannel:
        # Send images to the specified channel and get their CDN URLs
        file_team1 = discord.File(BytesIO(team1_img.getvalue()), filename="team1.png")
        file_team2 = discord.File(BytesIO(team2_img.getvalue()), filename="team2.png")

        msg_team1 = await userOrChannel.send(file=file_team1)
        msg_team2 = await userOrChannel.send(file=file_team2)

        global team1_url, team2_url
        team1_url = msg_team1.attachments[0].url
        team2_url = msg_team2.attachments[0].url


    embed1 = discord.Embed(title=m1, color=discord.Color.lighter_grey())
    view = TeamButtons(team1_img, team2_img)

    # Send the initial message with buttons
    message = await interaction.followup.send(embed=embed1, view=view)
    view.message = message

    # # Delete the temporary message after sending the main message
    # try:
    #     await temp_msg.delete()
    # except discord.errors.NotFound:
    #     pass

    # Just incase they don't get deleted properly in message timeout
    await asyncio.sleep(1000)
    try:
        team1_img.close()
        team2_img.close()
    except:
        pass


# Start the Discord bot
client.run(discord_bot_token)