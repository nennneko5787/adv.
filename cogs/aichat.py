import uuid
from typing import List

import discord
from discord import app_commands
from discord.ext import commands
from openai import AsyncOpenAI
from pydantic import BaseModel


class Character(BaseModel):
    name: str
    feeling: str
    currentLocation: str


class ChatResponse(BaseModel):
    character: Character
    message: str
    choices: List[str]


class AIChatCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ai = AsyncOpenAI(
            api_key="paicha_is_god", base_url="https://capi.voids.top/v2/"
        )

    def createEmbed(self, chatResponse: ChatResponse) -> discord.Embed:
        embed = discord.Embed(description=chatResponse.message)
        embed.set_author(name=chatResponse.character.name)
        embed.set_footer(
            text=f"今の気分: {chatResponse.character.feeling} | 現在地: {chatResponse.character.currentLocation}"
        )

        # 選択肢を箇条書きでEmbedに追加
        if chatResponse.choices:
            formatted_choices = "\n".join(
                f"- :regional_indicator_{chr(97 + i)}: {choice}"
                for i, choice in enumerate(chatResponse.choices)
            )
            embed.add_field(name="選択肢一覧", value=formatted_choices, inline=False)

        return embed

    def createResponseView(
        self, chatResponse: ChatResponse, returnCallback, modalCallback
    ) -> discord.ui.View:
        view = discord.ui.View(timeout=None)
        for i, choice in enumerate(chatResponse.choices):
            button = discord.ui.Button(
                style=discord.ButtonStyle.blurple,
                emoji=discord.PartialEmoji.from_str(
                    f":regional_indicator_{chr(97 + i)}:"
                ),
                custom_id=choice,
            )
            button.callback = returnCallback
            view.add_item(button)

        modalButton = discord.ui.Button(
            style=discord.ButtonStyle.blurple,
            label="別の言葉を返す",
            custom_id=str(uuid.uuid4()),
        )
        modalButton.callback = modalCallback
        view.add_item(modalButton)

        return view

    @app_commands.command(
        name="new", description="新しいキャラクターとの会話を開始します。"
    )
    @app_commands.rename(intro="キャラクター説明")
    @app_commands.describe(intro="キャラクターの説明。")
    async def newCommand(self, interaction: discord.Interaction, intro: str):
        await interaction.response.defer()

        messages = [
            {
                "role": "system",
                "content": (
                    "アドベンチャーゲームのように会話を返します。ユーザーからのキャラクター説明は以下のとおりです。\n"
                    f"{intro}\n\nchoicesには会話の選択肢を返してください。"
                    "選択肢は最大24個まで増やすことができます。\nあなたは最初に私に話しかけてください。"
                ),
            }
        ]

        response = await self.ai.chat.completions.parse(
            messages=messages,
            model="gemini-2.5-flash",
            response_format=ChatResponse,
        )
        messages.append(
            {
                "role": "assistant",
                "content": response.choices[0].message.model_dump_json(),
            }
        )

        async def returnResponse(inter: discord.Interaction):
            if interaction.user.id != inter.user.id:
                return

            await inter.response.defer()
            messages.append({"role": "user", "content": inter.data["custom_id"]})

            await inter.edit_original_response(content="生成中...", view=None)
            response = await self.ai.chat.completions.parse(
                messages=messages,
                model="gemini-2.5-flash",
                response_format=ChatResponse,
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": response.choices[0].message.model_dump_json(),
                }
            )

            chatResponse = response.choices[0].message.parsed
            view = self.createResponseView(chatResponse, returnResponse, openModal)
            await inter.edit_original_response(
                embed=self.createEmbed(chatResponse),
                view=view,
            )

        _self = self

        async def openModal(inter: discord.Interaction):
            class Modal(discord.ui.Modal, title="別の言葉を返す"):
                choice = discord.ui.TextInput(label="返す内容")

                async def on_submit(self, modelIntaraction: discord.Interaction):
                    if interaction.user.id != modelIntaraction.user.id:
                        return

                    await modelIntaraction.response.defer()
                    messages.append({"role": "user", "content": self.choice.value})

                    await modelIntaraction.edit_original_response(
                        content="生成中...", view=None
                    )
                    response = await _self.ai.chat.completions.parse(
                        messages=messages,
                        model="gemini-2.5-flash",
                        response_format=ChatResponse,
                    )
                    messages.append(
                        {
                            "role": "assistant",
                            "content": response.choices[0].message.model_dump_json(),
                        }
                    )

                    chatResponse = response.choices[0].message.parsed
                    view = _self.createResponseView(
                        chatResponse, returnResponse, openModal
                    )
                    await modelIntaraction.edit_original_response(
                        embed=_self.createEmbed(chatResponse),
                        view=view,
                    )

            await inter.response.send_modal(
                Modal(timeout=None, custom_id=str(uuid.uuid4()))
            )

        chatResponse = response.choices[0].message.parsed
        view = self.createResponseView(chatResponse, returnResponse, openModal)

        await interaction.followup.send(
            embed=self.createEmbed(chatResponse),
            view=view,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AIChatCog(bot))
